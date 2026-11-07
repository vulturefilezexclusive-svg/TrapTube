import AVFoundation
import Foundation
import Combine
import Accelerate

private enum TrapTubeVisualizerDSP {
    static let fftSize = 1024
    static let window: [Float] = (0..<1024).map { 0.5 * (1 - cos(2 * Float.pi * Float($0) / 1024)) }
    nonisolated(unsafe) static let setup: FFTSetup = vDSP_create_fftsetup(10, FFTRadix(kFFTRadix2))!
}

@MainActor
final class AudioEngineManager: ObservableObject {
    static let frequencies: [Float] = [32, 64, 125, 250, 500, 1_000, 2_000, 3_000, 4_000, 5_000, 6_000, 7_000, 8_000, 10_000, 12_000, 16_000]
    static let presetNames = ["Hip Hop Boost", "Bass Heavy", "Vocal Clarity", "Flat"]

    @Published private(set) var currentTrack: Track?
    @Published private(set) var isPlaying = false
    @Published private(set) var currentTime: TimeInterval = 0
    @Published private(set) var duration: TimeInterval = 0
    @Published private(set) var playbackError: String?
    @Published private(set) var eqGains = Array(repeating: Float(0), count: 16)
    @Published private(set) var bassBoost: Float = 0
    @Published private(set) var masterGain: Float = 1
    @Published private(set) var currentPreset = "Flat"
    @Published private(set) var visualizerLevels = Array(repeating: Float(0), count: 48)
    @Published private(set) var visualizerWaveform = Array(repeating: Float(0), count: 48)
    @Published var isShuffled = false
    @Published var repeatsTrack = false

    private let engine = AVAudioEngine()
    private let playerNode = AVAudioPlayerNode()
    private let equalizer = AVAudioUnitEQ(numberOfBands: 16)
    private let bassStage = AVAudioUnitEQ(numberOfBands: 1)
    private let masterStage = AVAudioUnitEQ(numberOfBands: 0)
    private var currentFile: AVAudioFile?
    // Compatibility decoder used when AVAudioEngine cannot schedule a valid imported file.
    // AVAudioPlayer supports the native iOS audio formats and prevents a working import
    // from becoming unplayable solely because the EQ graph cannot start on a device.
    private var compatibilityPlayer: AVAudioPlayer?
    private var queue: [Track] = []
    private var queueIndex = 0
    private var engineConfigured = false
    private var playbackGeneration = 0
    private var scheduledStartTime: TimeInterval = 0
    private var visualizerTapInstalled = false

    init() { configureGraph() }

    var clippingWarning: Bool { masterGain > 1.0 || (eqGains.max() ?? 0) > 6 }

    func play(_ track: Track, from tracks: [Track]) {
        queue = tracks
        queueIndex = tracks.firstIndex(where: { $0.id == track.id }) ?? 0
        start(track, at: 0, autoplay: true)
    }

    func togglePlayback() {
        guard currentTrack != nil else { return }
        if isPlaying {
            if let compatibilityPlayer {
                compatibilityPlayer.pause()
            } else {
                playerNode.pause()
            }
            isPlaying = false
        } else if let compatibilityPlayer {
            guard compatibilityPlayer.play() else {
                failPlayback(trackName: currentTrack?.title ?? "Audio", error: NSError(
                    domain: "TrapTube.CompatibilityPlayer",
                    code: -2,
                    userInfo: [NSLocalizedDescriptionKey: "iOS could not resume the imported audio file."]
                ))
                return
            }
            isPlaying = true
        } else {
            do {
                try startEngineIfNeeded()
                playerNode.play()
                isPlaying = true
            } catch {
                if let track = currentTrack {
                    startCompatibilityPlayback(track, at: currentTime, autoplay: true, engineError: error)
                }
            }
        }
    }

    func next() {
        guard !queue.isEmpty else { return }
        if repeatsTrack, let track = currentTrack { start(track, at: 0, autoplay: true); return }
        if isShuffled, queue.count > 1 {
            var newIndex = queueIndex
            while newIndex == queueIndex { newIndex = Int.random(in: queue.indices) }
            queueIndex = newIndex
        } else {
            guard queueIndex + 1 < queue.count else {
                stopPlayback(clearTrack: false)
                currentTime = duration
                return
            }
            queueIndex += 1
        }
        start(queue[queueIndex], at: 0, autoplay: true)
    }

    func previous() {
        guard !queue.isEmpty else { return }
        if currentTime > 3 { seek(to: 0); return }
        queueIndex = (queueIndex - 1 + queue.count) % queue.count
        start(queue[queueIndex], at: 0, autoplay: true)
    }

    func seek(to time: TimeInterval) {
        guard let track = currentTrack else { return }
        let target = min(max(0, time), max(duration, 0))
        start(track, at: target, autoplay: isPlaying)
    }

    func refreshProgress() {
        guard isPlaying else { return }
        if let compatibilityPlayer {
            currentTime = compatibilityPlayer.currentTime
        } else if let renderTime = playerNode.lastRenderTime,
                  let playerTime = playerNode.playerTime(forNodeTime: renderTime),
                  playerTime.sampleRate > 0 {
            currentTime = scheduledStartTime + Double(playerTime.sampleTime) / playerTime.sampleRate
        } else {
            return
        }
        if duration > 0, currentTime >= duration - 0.15 {
            isPlaying = false
            next()
        }
    }

    func clearPlaybackError() { playbackError = nil }

    func setBand(_ index: Int, gain: Float) {
        guard equalizer.bands.indices.contains(index) else { return }
        let clamped = min(max(gain, -12), 12)
        let band = equalizer.bands[index]
        band.filterType = .parametric
        band.bypass = false
        band.gain = clamped
        eqGains[index] = clamped
        currentPreset = "Custom"
        updateMasterStage()
    }

    func setBassBoost(_ gain: Float) {
        let clamped = min(max(gain, 0), 20)
        bassStage.bands[0].filterType = .lowShelf
        bassStage.bands[0].bypass = false
        bassStage.bands[0].gain = clamped
        bassBoost = clamped
        updateMasterStage()
    }

    func setMasterGain(_ gain: Float) {
        masterGain = min(max(gain, 0), 2)
        updateMasterStage()
    }

    func applyPreset(_ name: String) {
        let preset: [Float]
        switch name {
        case "Hip Hop Boost":
            preset = [10, 9, 7, 4, 1, -1, -1, 0, 2, 3, 3, 2, 1, 1, 0, -1]; setBassBoost(8)
        case "Bass Heavy":
            preset = [12, 11, 9, 6, 3, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]; setBassBoost(12)
        case "Vocal Clarity":
            preset = [-3, -2, 0, 3, 5, 6, 6, 4, 2, 0, 1, 2, 2, 2, 1, 0]; setBassBoost(0)
        default:
            preset = Array(repeating: 0, count: 16); setBassBoost(0)
        }
        for index in preset.indices { equalizer.bands[index].gain = preset[index] }
        eqGains = preset
        currentPreset = name
        updateMasterStage()
    }

    private func configureGraph() {
        engine.attach(playerNode); engine.attach(equalizer); engine.attach(bassStage); engine.attach(masterStage)
        for (index, band) in equalizer.bands.enumerated() {
            band.filterType = .parametric; band.frequency = Self.frequencies[index]; band.bandwidth = 1.25; band.gain = 0; band.bypass = false
        }
        let bass = bassStage.bands[0]
        bass.filterType = .lowShelf; bass.frequency = 90; bass.bandwidth = 0.7; bass.gain = 0; bass.bypass = false
        masterStage.globalGain = 0
        engine.connect(playerNode, to: equalizer, format: nil)
        engine.connect(equalizer, to: bassStage, format: nil)
        engine.connect(bassStage, to: masterStage, format: nil)
        engine.connect(masterStage, to: engine.mainMixerNode, format: nil)
        installVisualizerTap()
        engine.mainMixerNode.outputVolume = 1
        updateMasterStage()
        engineConfigured = true
    }


    private func installVisualizerTap() {
        guard !visualizerTapInstalled else { return }
        visualizerTapInstalled = true
        masterStage.installTap(onBus: 0, bufferSize: 2048, format: nil) { [weak self] buffer, _ in
            guard let channels = buffer.floatChannelData else { return }
            let frameCount = Int(buffer.frameLength)
            guard frameCount >= TrapTubeVisualizerDSP.fftSize else { return }
            let channelCount = Int(buffer.format.channelCount)
            let fftSize = Self.visualizerFFTSize
            var mono = [Float](repeating: 0, count: fftSize)
            for index in 0..<fftSize {
                var sample: Float = 0
                for channel in 0..<channelCount { sample += channels[channel][index] }
                mono[index] = sample / Float(max(1, channelCount))
            }
            var waveform = [Float](repeating: 0, count: 48)
            for index in 0..<waveform.count {
                let sourceIndex = index * fftSize / waveform.count
                waveform[index] = mono[sourceIndex]
            }

            var windowed = [Float](repeating: 0, count: fftSize)
            vDSP_vmul(mono, 1, TrapTubeVisualizerDSP.window, 1, &windowed, 1, vDSP_Length(fftSize))
            var real = [Float](repeating: 0, count: fftSize / 2)
            var imaginary = [Float](repeating: 0, count: fftSize / 2)
            real.withUnsafeMutableBufferPointer { realPointer in
                imaginary.withUnsafeMutableBufferPointer { imaginaryPointer in
                    var split = DSPSplitComplex(realp: realPointer.baseAddress!, imagp: imaginaryPointer.baseAddress!)
                    windowed.withUnsafeBytes { bytes in
                        vDSP_ctoz(bytes.baseAddress!.assumingMemoryBound(to: DSPComplex.self), 2, &split, 1, vDSP_Length(fftSize / 2))
                    }
                    vDSP_fft_zrip(TrapTubeVisualizerDSP.setup, &split, 1, 10, FFTDirection(FFT_FORWARD))
                }
            }

            let bandCount = 48
            let binCount = fftSize / 2
            var levels = [Float](repeating: 0, count: bandCount)
            for band in 0..<bandCount {
                let low = max(1, Int(pow(Double(binCount), Double(band) / Double(bandCount))))
                let high = min(binCount, max(low + 1, Int(pow(Double(binCount), Double(band + 1) / Double(bandCount)))))
                var peak: Float = 0
                for bin in low..<high {
                    let magnitude = sqrt(real[bin] * real[bin] + imaginary[bin] * imaginary[bin]) / Float(fftSize)
                    peak = max(peak, magnitude)
                }
                levels[band] = min(1, pow(max(0, peak * 7.5), 0.68))
            }

            Task { @MainActor [weak self] in
                guard let self else { return }
                self.visualizerLevels = levels
                self.visualizerWaveform = waveform
            }
        }
    }

    private func updateMasterStage() {
        for index in equalizer.bands.indices {
            let band = equalizer.bands[index]
            band.bypass = false
            band.gain = eqGains[index]
        }
        let bass = bassStage.bands[0]
        bass.bypass = false
        bass.gain = bassBoost
        let peakBoost = max(0, eqGains.max() ?? 0) + bassBoost
        let headroom = -min(18, peakBoost * 0.5)
        let gainDB = masterGain == 0 ? -96 : 20 * log10(masterGain)
        masterStage.globalGain = max(-96, min(12, gainDB + headroom))
    }

    private func start(_ track: Track, at time: TimeInterval, autoplay: Bool) {
        playbackGeneration += 1
        let generation = playbackGeneration
        playerNode.stop()
        compatibilityPlayer?.stop()
        compatibilityPlayer = nil
        currentFile = nil
        currentTrack = track
        playbackError = nil
        let fileURL = LibraryStore.audioURL(for: track.fileName).standardizedFileURL
        guard FileManager.default.fileExists(atPath: fileURL.path) else {
            failPlayback(trackName: track.title, error: NSError(domain: "TrapTube.Library", code: 404, userInfo: [NSLocalizedDescriptionKey: "The imported audio file is missing from the app's library."]))
            return
        }
        do {
            try configureAudioSession()
            let file = try AVAudioFile(forReading: fileURL)
            guard file.length > 0, file.processingFormat.sampleRate.isFinite, file.processingFormat.sampleRate > 0 else {
                throw NSError(domain: "TrapTube.AudioFile", code: -50, userInfo: [NSLocalizedDescriptionKey: "The file has no readable audio frames or an invalid sample rate."])
            }
            currentFile = file
            duration = Double(file.length) / file.processingFormat.sampleRate
            if duration <= 0 { duration = track.duration }
            currentTime = min(max(0, time), duration)
            scheduledStartTime = currentTime
            try startEngineIfNeeded()
            let startFrame = AVAudioFramePosition(currentTime * file.processingFormat.sampleRate)
            let remainingFrames = max(0, file.length - startFrame)
            guard remainingFrames > 0 else { throw NSError(domain: "TrapTube.AudioFile", code: -50, userInfo: [NSLocalizedDescriptionKey: "The requested playback position is beyond the end of the file."]) }
            let frameCount = AVAudioFrameCount(min(remainingFrames, AVAudioFramePosition(UInt32.max)))
            playerNode.scheduleSegment(file, startingFrame: startFrame, frameCount: frameCount, at: nil) { [weak self] in
                DispatchQueue.main.async { [weak self] in
                    guard let self, self.playbackGeneration == generation, self.isPlaying else { return }
                    self.isPlaying = false
                    self.next()
                }
            }
            if autoplay { playerNode.play(); isPlaying = true } else { isPlaying = false }
        } catch {
            startCompatibilityPlayback(track, at: time, autoplay: autoplay, engineError: error)
        }
    }

    private func startCompatibilityPlayback(_ track: Track, at time: TimeInterval, autoplay: Bool, engineError: Error) {
        playerNode.stop()
        compatibilityPlayer?.stop()
        compatibilityPlayer = nil
        isPlaying = false
        let fileURL = LibraryStore.audioURL(for: track.fileName).standardizedFileURL
        do {
            try configureAudioSession()
            let fallback = try AVAudioPlayer(contentsOf: fileURL)
            guard fallback.duration.isFinite, fallback.duration > 0 else {
                throw NSError(domain: "TrapTube.CompatibilityPlayer", code: -3, userInfo: [
                    NSLocalizedDescriptionKey: "The imported file opened but did not report a valid audio duration."
                ])
            }
            fallback.currentTime = min(max(0, time), fallback.duration)
            fallback.volume = 1
            fallback.prepareToPlay()
            duration = fallback.duration
            currentTime = fallback.currentTime
            compatibilityPlayer = fallback
            currentFile = nil
            playbackError = nil
            if autoplay {
                guard fallback.play() else {
                    throw NSError(domain: "TrapTube.CompatibilityPlayer", code: -4, userInfo: [
                        NSLocalizedDescriptionKey: "iOS opened the imported file but could not begin playback."
                    ])
                }
                isPlaying = true
            } else {
                isPlaying = false
            }
        } catch {
            let engine = engineError as NSError
            let fallback = error as NSError
            failPlayback(trackName: track.title, error: NSError(
                domain: "TrapTube.Playback",
                code: fallback.code,
                userInfo: [NSLocalizedDescriptionKey:
                    "The equalizer playback path failed (\(engine.domain) / \(engine.code)), and the iOS compatibility player also failed (\(fallback.domain) / \(fallback.code)): \(fallback.localizedDescription)"
                ]
            ))
        }
    }

    private func configureAudioSession() throws {
        let session = AVAudioSession.sharedInstance()
        try session.setCategory(.playback, mode: .default, options: [.allowAirPlay, .allowBluetoothA2DP])
        try session.setActive(true)
    }

    private func startEngineIfNeeded() throws {
        guard engineConfigured else { throw NSError(domain: "TrapTube.AudioEngine", code: -1, userInfo: [NSLocalizedDescriptionKey: "The audio graph is not configured."]) }
        if !engine.isRunning {
            engine.prepare()
            try engine.start()
        }
        // Re-assert every filter after a route change or engine restart. Some
        // AVAudioEngine graph restarts restore unit defaults unless parameters are reapplied.
        updateMasterStage()
    }

    private func failPlayback(trackName: String, error: Error) {
        stopPlayback(clearTrack: true)
        let ns = error as NSError
        playbackError = "Couldn't play \(trackName). \(ns.localizedDescription) (\(ns.domain), code \(ns.code)). Try re-importing the file or using MP3, M4A, AAC, WAV or AIFF audio."
    }

    private func stopPlayback(clearTrack: Bool) {
        playbackGeneration += 1
        playerNode.stop()
        compatibilityPlayer?.stop()
        compatibilityPlayer = nil
        currentFile = nil
        isPlaying = false
        if clearTrack { currentTrack = nil; currentTime = 0; duration = 0; scheduledStartTime = 0 }
    }
}
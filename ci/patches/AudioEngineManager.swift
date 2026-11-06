import AVFoundation
import Foundation
import Combine

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
    @Published var isShuffled = false
    @Published var repeatsTrack = false

    private let engine = AVAudioEngine()
    private let playerNode = AVAudioPlayerNode()
    private let equalizer = AVAudioUnitEQ(numberOfBands: 16)
    private let bassStage = AVAudioUnitEQ(numberOfBands: 1)
    // AVFoundation has no AVAudioUnitDynamicsProcessor type. Keep this graph
    // compile-safe and use the final EQ stage for master gain/headroom.
    private let masterStage = AVAudioUnitEQ(numberOfBands: 0)
    private var currentFile: AVAudioFile?
    private var queue: [Track] = []
    private var queueIndex = 0
    private var engineConfigured = false

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
            playerNode.pause()
            isPlaying = false
        } else {
            do {
                try startEngineIfNeeded()
                playerNode.play()
                isPlaying = true
            } catch { playbackError = error.localizedDescription }
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
                playerNode.stop()
                isPlaying = false
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
        start(track, at: min(max(0, time), duration), autoplay: isPlaying)
    }

    func refreshProgress() {
        guard isPlaying, let renderTime = playerNode.lastRenderTime, let playerTime = playerNode.playerTime(forNodeTime: renderTime), playerTime.sampleRate > 0 else { return }
        currentTime = Double(playerTime.sampleTime) / playerTime.sampleRate
        if duration > 0, currentTime >= duration - 0.15 {
            isPlaying = false
            next()
        }
    }

    func clearPlaybackError() { playbackError = nil }

    func setBand(_ index: Int, gain: Float) {
        guard equalizer.bands.indices.contains(index) else { return }
        let clamped = min(max(gain, -12), 12)
        equalizer.bands[index].gain = clamped
        eqGains[index] = clamped
        currentPreset = "Custom"
        updateMasterStage()
    }

    func setBassBoost(_ gain: Float) {
        let clamped = min(max(gain, 0), 20)
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
            preset = [6, 5, 4, 2, 0, 1, 2, 3, 4, 4, 3, 2, 1, 1, 0, -1]
            setBassBoost(5)
        case "Bass Heavy":
            preset = [8, 7, 6, 4, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
            setBassBoost(10)
        case "Vocal Clarity":
            preset = [-2, -1, 0, 1, 2, 3, 3, 2, 1, 0, 1, 2, 2, 2, 1, 0]
            setBassBoost(0)
        default:
            preset = Array(repeating: 0, count: 16)
            setBassBoost(0)
        }
        for index in preset.indices { equalizer.bands[index].gain = preset[index] }
        eqGains = preset
        currentPreset = name
        updateMasterStage()
    }

    private func configureGraph() {
        engine.attach(playerNode)
        engine.attach(equalizer)
        engine.attach(bassStage)
        engine.attach(masterStage)
        for (index, band) in equalizer.bands.enumerated() {
            band.filterType = .parametric
            band.frequency = Self.frequencies[index]
            band.bandwidth = 1.0
            band.gain = 0
            band.bypass = false
        }
        let bassBand = bassStage.bands[0]
        bassBand.filterType = .lowShelf
        bassBand.frequency = 90
        bassBand.bandwidth = 0.7
        bassBand.gain = 0
        bassBand.bypass = false
        masterStage.globalGain = 0
        engine.connect(playerNode, to: equalizer, format: nil)
        engine.connect(equalizer, to: bassStage, format: nil)
        engine.connect(bassStage, to: masterStage, format: nil)
        engine.connect(masterStage, to: engine.mainMixerNode, format: nil)
        engineConfigured = true
    }

    private func updateMasterStage() {
        // Compensate for EQ boosts to retain some output headroom. The warning
        // shown in the UI still flags aggressive user gain settings.
        let peakBoost = max(0, eqGains.max() ?? 0) + bassBoost
        let headroom = -min(18, peakBoost * 0.5)
        let gainDB = masterGain == 0 ? -96 : 20 * log10(masterGain)
        masterStage.globalGain = max(-96, min(12, gainDB + headroom))
    }

    private func start(_ track: Track, at time: TimeInterval, autoplay: Bool) {
        do {
            let file = try AVAudioFile(forReading: LibraryStore.audioURL(for: track.fileName))
            currentFile = file
            currentTrack = track
            duration = Double(file.length) / file.processingFormat.sampleRate
            currentTime = min(max(0, time), duration)
            playerNode.stop()
            try startEngineIfNeeded()
            let sampleRate = file.processingFormat.sampleRate
            let startFrame = AVAudioFramePosition(currentTime * sampleRate)
            let remainingFrames = max(0, file.length - startFrame)
            let frameCount = AVAudioFrameCount(min(remainingFrames, AVAudioFramePosition(UInt32.max)))
            playerNode.scheduleSegment(file, startingFrame: startFrame, frameCount: frameCount, at: nil) { [weak self] in
                DispatchQueue.main.async { [weak self] in
                    guard let self, self.isPlaying else { return }
                    self.isPlaying = false
                    self.next()
                }
            }
            if autoplay { playerNode.play(); isPlaying = true } else { isPlaying = false }
            playbackError = nil
        } catch {
            isPlaying = false
            playbackError = "Couldn't play this audio file: \(error.localizedDescription)"
        }
    }

    private func startEngineIfNeeded() throws {
        guard engineConfigured else { return }
        if !engine.isRunning {
            try AVAudioSession.sharedInstance().setCategory(.playback, mode: .default, options: [.allowAirPlay, .allowBluetoothA2DP])
            try AVAudioSession.sharedInstance().setActive(true)
            engine.prepare()
            try engine.start()
        }
    }
}

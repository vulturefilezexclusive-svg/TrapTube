import Foundation
import AVFoundation
import Combine
import Demucs

enum Stem: String, CaseIterable, Identifiable, Sendable {
    case drums = "Drums", bass = "Bass", other = "Other", vocals = "Vocals"
    var id: String { rawValue }
    var icon: String {
        switch self {
        case .vocals: return "mic.fill"
        case .drums: return "drum.fill"
        case .bass: return "guitars.fill"
        case .other: return "waveform"
        }
    }
}

enum StemProcessingError: LocalizedError, Sendable {
    case unreadableAudio, invalidSampleRate, modelDownload, outputWrite(String)
    var errorDescription: String? {
        switch self {
        case .unreadableAudio: return "TrapTube could not decode this audio file into stereo PCM."
        case .invalidSampleRate: return "The imported file has an invalid sample rate."
        case .modelDownload: return "The enhanced HTDemucs FT model is not downloaded yet."
        case .outputWrite(let detail): return detail
        }
    }
}

private enum TrapTubeDemucsCache {
    static let configured: Bool = {
        let cache = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("TrapTube/Demucs", isDirectory: true)
        DemucsEngine.configureCacheDirectory(cache)
        return true
    }()
}

@MainActor
final class StemSeparationService: ObservableObject {
    enum Availability: Equatable {
        case bundled, missingModel
        var title: String { self == .bundled ? "HTDemucs FT ready" : "Enhanced model needs download" }
        var detail: String {
            self == .bundled
                ? "Fine-tuned four-stem model is cached on this device. Metal GPU inference runs locally."
                : "Download the 333 MB HTDemucs FT model once. TrapTube caches it locally and reuses it for future separations."
        }
    }

    @Published private(set) var availability: Availability = .missingModel
    @Published private(set) var isDownloading = false
    @Published private(set) var downloadProgress = 0.0
    @Published private(set) var isProcessing = false
    @Published private(set) var progress = 0.0
    @Published private(set) var statusMessage = "Ready"
    @Published private(set) var errorMessage: String?
    @Published private(set) var outputs: [Stem: URL] = [:]
    @Published private(set) var playingStem: Stem?
    private var audioPlayer: AVAudioPlayer?

    init() {
        _ = TrapTubeDemucsCache.configured
        refresh()
    }

    func refresh() {
        availability = DemucsEngine.isDownloaded(.fineTunedAll) ? .bundled : .missingModel
    }

    func downloadModel() {
        guard !isDownloading, availability != .bundled else { return }
        isDownloading = true
        downloadProgress = 0
        errorMessage = nil
        statusMessage = "Downloading enhanced model…"
        Task.detached(priority: .utility) {
            do {
                try await DemucsEngine.download(.fineTunedAll) { update in
                    Task { @MainActor in
                        self.downloadProgress = update.fraction
                        self.statusMessage = "Downloading model · \(Int(update.fraction * 100))%"
                    }
                }
                await self.finishDownload()
            } catch {
                await self.failDownload(error.localizedDescription)
            }
        }
    }

    private func finishDownload() {
        isDownloading = false
        downloadProgress = 1
        availability = DemucsEngine.isDownloaded(.fineTunedAll) ? .bundled : .missingModel
        statusMessage = availability == .bundled ? "Enhanced model ready" : "Model download incomplete"
    }

    private func failDownload(_ message: String) {
        isDownloading = false
        errorMessage = message
        statusMessage = "Model download failed"
        refresh()
    }

    func separate(track: Track) {
        guard !isProcessing else { return }
        guard availability == .bundled else {
            errorMessage = StemProcessingError.modelDownload.localizedDescription
            return
        }
        isProcessing = true
        progress = 0
        errorMessage = nil
        outputs = [:]
        statusMessage = "Preparing audio…"
        let source = LibraryStore.audioURL(for: track.fileName)
        let destination = LibraryStore.appDirectory.appendingPathComponent("Stems", isDirectory: true)
            .appendingPathComponent(track.id.uuidString, isDirectory: true)

        Task.detached(priority: .userInitiated) {
            do {
                let pcm = try Self.readStereo(source)
                let engine = DemucsEngine()
                await self.updateProgress(0.03, message: "Loading enhanced model…")
                try await engine.load(.fineTunedAll)
                try await engine.warmup()
                let separated = try await engine.separate(
                    left: pcm.left,
                    right: pcm.right,
                    sampleRate: pcm.sampleRate
                ) { update in
                    Task { @MainActor in
                        self.updateProgress(update.fraction, message: "Separating chunk \(update.chunkIndex) of \(update.totalChunks)…")
                    }
                }
                try FileManager.default.createDirectory(at: destination, withIntermediateDirectories: true)
                var result: [Stem: URL] = [:]
                for separatedStem in separated {
                    guard let kind = Stem(rawValue: separatedStem.kind.rawValue.capitalized) else { continue }
                    let outputURL = destination.appendingPathComponent("\(kind.rawValue.lowercased()).wav")
                    try Self.writeWAV(left: separatedStem.left, right: separatedStem.right,
                                      sampleRate: Double(pcm.sampleRate), url: outputURL)
                    result[kind] = outputURL
                }
                guard result.count == Stem.allCases.count else {
                    throw StemProcessingError.outputWrite("The enhanced model did not return all four expected stems.")
                }
                await self.finish(result: result)
            } catch {
                await self.finish(error: error.localizedDescription)
            }
        }
    }

    private func updateProgress(_ value: Double, message: String) {
        progress = min(1, max(0, value))
        statusMessage = message
    }

    private func finish(result: [Stem: URL]) {
        outputs = result
        progress = 1
        statusMessage = "Enhanced separation complete"
        isProcessing = false
    }

    private func finish(error: String) {
        errorMessage = error
        statusMessage = "Separation failed"
        isProcessing = false
    }

    nonisolated private static func readStereo(_ url: URL) throws -> (left: [Float], right: [Float], sampleRate: UInt32) {
        let file = try AVAudioFile(forReading: url)
        let sourceFormat = file.processingFormat
        guard sourceFormat.sampleRate.isFinite, sourceFormat.sampleRate > 0,
              sourceFormat.channelCount > 0, file.length > 0,
              let source = AVAudioPCMBuffer(pcmFormat: sourceFormat, frameCapacity: AVAudioFrameCount(file.length)) else {
            throw StemProcessingError.unreadableAudio
        }
        try file.read(into: source)
        guard let target = AVAudioFormat(commonFormat: .pcmFormatFloat32, sampleRate: sourceFormat.sampleRate,
                                         channels: 2, interleaved: false),
              let converter = AVAudioConverter(from: sourceFormat, to: target) else {
            throw StemProcessingError.unreadableAudio
        }
        let capacity = AVAudioFrameCount(ceil(Double(source.frameLength) * target.sampleRate / sourceFormat.sampleRate) + 1024)
        guard let converted = AVAudioPCMBuffer(pcmFormat: target, frameCapacity: capacity) else {
            throw StemProcessingError.unreadableAudio
        }
        var supplied = false
        var conversionError: NSError?
        let status = converter.convert(to: converted, error: &conversionError) { _, inputStatus in
            guard !supplied else { inputStatus.pointee = .endOfStream; return nil }
            supplied = true
            inputStatus.pointee = .haveData
            return source
        }
        if let conversionError { throw conversionError }
        guard status != .error, converted.frameLength > 0,
              let channels = converted.floatChannelData else { throw StemProcessingError.unreadableAudio }
        let count = Int(converted.frameLength)
        return (
            Array(UnsafeBufferPointer(start: channels[0], count: count)),
            Array(UnsafeBufferPointer(start: channels[1], count: count)),
            UInt32(target.sampleRate)
        )
    }

    nonisolated private static func writeWAV(left: [Float], right: [Float], sampleRate: Double, url: URL) throws {
        guard left.count == right.count,
              let format = AVAudioFormat(commonFormat: .pcmFormatFloat32, sampleRate: sampleRate, channels: 2, interleaved: false),
              let buffer = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: AVAudioFrameCount(left.count)),
              let channels = buffer.floatChannelData else {
            throw StemProcessingError.outputWrite("Could not allocate a stereo WAV for a separated stem.")
        }
        buffer.frameLength = AVAudioFrameCount(left.count)
        left.withUnsafeBufferPointer { channels[0].update(from: $0.baseAddress!, count: left.count) }
        right.withUnsafeBufferPointer { channels[1].update(from: $0.baseAddress!, count: right.count) }
        let file = try AVAudioFile(forWriting: url, settings: format.settings)
        try file.write(from: buffer)
    }

    func play(_ stem: Stem) {
        stopPlayback()
        guard let url = outputs[stem] else { return }
        do {
            try AVAudioSession.sharedInstance().setCategory(.playback, mode: .default)
            try AVAudioSession.sharedInstance().setActive(true)
            audioPlayer = try AVAudioPlayer(contentsOf: url)
            audioPlayer?.play()
            playingStem = stem
        } catch { errorMessage = "Couldn't play \(stem.rawValue): \(error.localizedDescription)" }
    }

    func stopPlayback() {
        audioPlayer?.stop()
        audioPlayer = nil
        playingStem = nil
    }
}

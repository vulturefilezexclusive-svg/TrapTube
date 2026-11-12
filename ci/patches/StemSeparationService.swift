import Foundation
import AVFoundation
import Combine
import Demucs
import Metal
import os

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
    case unreadableAudio, invalidSampleRate, modelDownload, outputWrite(String), modelLoad(String)
    var errorDescription: String? {
        switch self {
        case .modelLoad(let detail): return "Model loading failed. \(detail)"
        case .unreadableAudio: return "TrapTube could not decode this audio file into stereo PCM."
        case .invalidSampleRate: return "The imported file has an invalid sample rate."
        case .modelDownload: return "No usable HTDemucs model is downloaded yet. Tap Download first."
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

/// Rust prints panic messages to stderr, which iOS discards. This copies stderr into memory
/// while a model loads, so a "worker panicked" error can show the real panic text on screen.
private final class StderrCapture: @unchecked Sendable {
    private let lock = NSLock()
    private var captured = Data()
    private var saved: Int32 = -1
    private var pipe: Pipe?

    func start() {
        let pipe = Pipe()
        self.pipe = pipe
        saved = dup(STDERR_FILENO)
        dup2(pipe.fileHandleForWriting.fileDescriptor, STDERR_FILENO)
        pipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let chunk = handle.availableData
            guard let self, !chunk.isEmpty else { return }
            self.lock.lock(); self.captured.append(chunk); self.lock.unlock()
            if self.saved >= 0 { chunk.withUnsafeBytes { _ = Darwin.write(self.saved, $0.baseAddress, chunk.count) } }
        }
    }

    /// Restores stderr and returns the last ~3 KB that was written while capturing.
    func stop() -> String {
        if saved >= 0 { dup2(saved, STDERR_FILENO); close(saved); saved = -1 }
        if let pipe {
            pipe.fileHandleForReading.readabilityHandler = nil
            try? pipe.fileHandleForWriting.close()
            if let rest = try? pipe.fileHandleForReading.readToEnd(), !rest.isEmpty {
                lock.lock(); captured.append(rest); lock.unlock()
            }
        }
        pipe = nil
        lock.lock(); defer { lock.unlock() }
        return String(decoding: captured.suffix(3_000), as: UTF8.self).trimmingCharacters(in: .whitespacesAndNewlines)
    }
}

/// The two weight files TrapTube can use. FT (333 MB) is best quality; the standard four-stem
/// model (84 MB) needs far less memory and is the automatic fallback.
private enum TrapTubeModel {
    static let primary = DemucsModel.fineTunedAll
    static let fallback = DemucsModel.fourStem
    /// Heuristic, not measured: below this much free app memory, prefer the small model first.
    static let fineTunedMemoryFloor = 2_000_000_000

    static func label(_ model: DemucsModel) -> String { model == fallback ? "HTDemucs standard" : "HTDemucs FT" }
    static func minimumBytes(_ model: DemucsModel) -> Int64 { model == fallback ? 70_000_000 : 280_000_000 }

    /// `isDownloaded` only checks that a file exists, so a partial or empty download passes it.
    /// A file far smaller than the published size is deleted so it can be downloaded again.
    static func isUsable(_ model: DemucsModel) -> Bool {
        guard DemucsEngine.isDownloaded(model), let url = DemucsEngine.downloadedFileURL(for: model) else { return false }
        let size = ((try? FileManager.default.attributesOfItem(atPath: url.path))?[.size] as? NSNumber)?.int64Value ?? 0
        if size < minimumBytes(model) { _ = DemucsEngine.deleteDownload(model); return false }
        return true
    }

    static var memoryIsTight: Bool {
        let available = os_proc_available_memory()
        return available > 0 && available < fineTunedMemoryFloor
    }

    static func downloadTarget() -> DemucsModel { memoryIsTight ? fallback : primary }
}

@MainActor
final class StemSeparationService: ObservableObject {
    enum Availability: Equatable {
        case bundled, missingModel
        var title: String { self == .bundled ? "HTDemucs ready" : "Model needs download" }
        var detail: String {
            self == .bundled
                ? "A four-stem model is cached on this device. Metal GPU inference runs locally; if the large model fails to load, the smaller one is used automatically."
                : "Download the HTDemucs model once (333 MB, or 84 MB on low-memory devices). TrapTube caches it locally and reuses it."
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
        availability = (TrapTubeModel.isUsable(TrapTubeModel.primary) || TrapTubeModel.isUsable(TrapTubeModel.fallback)) ? .bundled : .missingModel
    }

    func downloadModel() {
        guard !isDownloading, availability != .bundled else { return }
        isDownloading = true
        downloadProgress = 0
        errorMessage = nil
        statusMessage = "Downloading model…"
        let target = TrapTubeModel.downloadTarget()
        Task.detached(priority: .utility) {
            do {
                try await DemucsEngine.download(target) { update in
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
        refresh()
        statusMessage = availability == .bundled ? "Model ready" : "Model download incomplete or too small; try again"
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
            let engine = DemucsEngine()
            do {
                let pcm = try Self.readStereo(source)
                await self.updateProgress(0.03, message: "Loading model…")
                _ = try await Self.loadEngine(engine) { message in
                    Task { @MainActor in self.updateProgress(0.03, message: message) }
                }
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
                    guard separatedStem.left.count == pcm.left.count,
                          separatedStem.right.count == pcm.right.count else {
                        throw StemProcessingError.outputWrite("\(separatedStem.kind.rawValue) returned an unexpected output length.")
                    }
                    guard separatedStem.left.allSatisfy(\.isFinite),
                          separatedStem.right.allSatisfy(\.isFinite) else {
                        throw StemProcessingError.outputWrite("\(separatedStem.kind.rawValue) returned non-finite audio samples.")
                    }
                    guard let kind = Stem(rawValue: separatedStem.kind.rawValue.capitalized) else { continue }
                    let outputURL = destination.appendingPathComponent("\(kind.rawValue.lowercased()).wav")
                    try Self.writeWAV(left: separatedStem.left, right: separatedStem.right,
                                      sampleRate: Double(pcm.sampleRate), url: outputURL)
                    result[kind] = outputURL
                }
                guard result.count == Stem.allCases.count else {
                    throw StemProcessingError.outputWrite("The enhanced model did not return all four expected stems.")
                }
                _ = await engine.unload()
                await self.finish(result: result)
            } catch {
                _ = await engine.unload()
                await self.finish(error: error.localizedDescription)
            }
        }
    }

    /// Loads and warms up a model, trying the preferred one first and the other as a fallback.
    /// Every failure keeps its stderr text, so a Rust panic message reaches the screen.
    nonisolated private static func loadEngine(_ engine: DemucsEngine, report: @escaping @Sendable (String) -> Void) async throws -> DemucsModel {
        guard MTLCreateSystemDefaultDevice() != nil else {
            throw StemProcessingError.modelLoad("This device did not provide a Metal GPU, which HTDemucs needs.")
        }
        let order = TrapTubeModel.memoryIsTight
            ? [TrapTubeModel.fallback, TrapTubeModel.primary]
            : [TrapTubeModel.primary, TrapTubeModel.fallback]
        let candidates = order.filter { TrapTubeModel.isUsable($0) }
        guard !candidates.isEmpty else { throw StemProcessingError.modelDownload }

        var failures: [String] = []
        for model in candidates {
            report("Loading \(TrapTubeModel.label(model))…")
            let capture = StderrCapture()
            capture.start()
            do {
                _ = try await engine.load(model)
                try await engine.warmup()
                _ = capture.stop()
                return model
            } catch {
                let log = capture.stop()
                _ = await engine.unload()
                failures.append("\(TrapTubeModel.label(model)): \(error.localizedDescription)" + (log.isEmpty ? "" : "\n\(log)"))
            }
        }
        throw StemProcessingError.modelLoad(failures.joined(separator: "\n\n"))
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
              sourceFormat.channelCount > 0, file.length > 0 else {
            throw StemProcessingError.unreadableAudio
        }
        let duration = Double(file.length) / sourceFormat.sampleRate
        guard duration <= 8 * 60 else {
            throw StemProcessingError.outputWrite("For memory safety, HTDemucs FT currently accepts tracks up to 8 minutes long.")
        }
        guard let source = AVAudioPCMBuffer(pcmFormat: sourceFormat, frameCapacity: AVAudioFrameCount(file.length)) else {
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

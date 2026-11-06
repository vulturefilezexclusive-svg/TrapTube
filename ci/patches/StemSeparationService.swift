import Foundation
import AVFoundation
import CoreML
import Combine

enum Stem: String, CaseIterable, Identifiable {
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

enum DemucsError: LocalizedError {
    case modelMissing, invalidModel(String), processing(String)
    var errorDescription: String? {
        switch self {
        case .modelMissing: return "The licensed HTDemucs model is missing from this installation. Reinstall a complete TrapTube build."
        case .invalidModel(let detail): return "The bundled HTDemucs model has an unexpected interface: \(detail)"
        case .processing(let detail): return detail
        }
    }
}

private enum HTDemucsRuntime {
    static let modelName = "HTDemucs_SourceSeparation_F32"
    static let sampleRate = 44_100.0
    static let segmentLength = 343_980
    static let overlap = 0.25

    static func modelURL() throws -> URL {
        guard let url = Bundle.main.url(forResource: modelName, withExtension: "mlmodelc"),
              FileManager.default.fileExists(atPath: url.appendingPathComponent("model.mil").path) &&
              FileManager.default.fileExists(atPath: url.appendingPathComponent("coremldata.bin").path) else {
            throw DemucsError.modelMissing
        }
        return url
    }

    static func readStereo(_ url: URL) throws -> (left: [Float], right: [Float]) {
        let file = try AVAudioFile(forReading: url)
        guard file.length > 0,
              let source = AVAudioPCMBuffer(pcmFormat: file.processingFormat, frameCapacity: AVAudioFrameCount(file.length)) else {
            throw DemucsError.processing("The selected song has no readable audio samples.")
        }
        try file.read(into: source)
        guard let target = AVAudioFormat(commonFormat: .pcmFormatFloat32, sampleRate: sampleRate, channels: 2, interleaved: false),
              let converter = AVAudioConverter(from: source.format, to: target) else {
            throw DemucsError.processing("Could not convert the song to stereo 44.1 kHz audio.")
        }
        let capacity = AVAudioFrameCount(ceil(Double(source.frameLength) * sampleRate / source.format.sampleRate) + 1024)
        guard let converted = AVAudioPCMBuffer(pcmFormat: target, frameCapacity: capacity) else {
            throw DemucsError.processing("Could not allocate the converted audio buffer.")
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
        guard status != .error, converted.frameLength > 0, let channels = converted.floatChannelData else {
            throw DemucsError.processing("Audio conversion returned no usable samples.")
        }
        let count = Int(converted.frameLength)
        return (Array(UnsafeBufferPointer(start: channels[0], count: count)),
                Array(UnsafeBufferPointer(start: channels[1], count: count)))
    }

    static func predict(left: [Float], right: [Float], model: MLModel) throws -> [[Float]] {
        let input = try MLMultiArray(shape: [1, 2, NSNumber(value: segmentLength)], dataType: .float32)
        let inputStrides = input.strides.map { $0.intValue }
        let inputPtr = input.dataPointer.bindMemory(to: Float.self, capacity: input.count)
        for i in 0..<segmentLength {
            inputPtr[i * inputStrides[2]] = left[i]
            inputPtr[inputStrides[1] + i * inputStrides[2]] = right[i]
        }
        let provider = try MLDictionaryFeatureProvider(dictionary: ["mix": MLFeatureValue(multiArray: input)])
        let result = try model.prediction(from: provider)
        guard let output = result.featureValue(for: "sources")?.multiArrayValue else {
            throw DemucsError.invalidModel("Expected output feature 'sources'; got \(result.featureNames.sorted()).")
        }
        let shape = output.shape.map { $0.intValue }
        guard shape == [1, 8, segmentLength], output.dataType == .float32 else {
            throw DemucsError.invalidModel("Expected Float32 tensor [1, 8, \(segmentLength)]; got shape \(shape), type \(output.dataType).")
        }
        let strides = output.strides.map { $0.intValue }
        let ptr = output.dataPointer.bindMemory(to: Float.self, capacity: output.count)
        var channels = [[Float]]()
        for channel in 0..<8 {
            let base = channel * strides[1]
            var samples = [Float](repeating: 0, count: segmentLength)
            for i in 0..<segmentLength { samples[i] = ptr[base + i * strides[2]] }
            channels.append(samples)
        }
        return channels
    }

    static func writeWAV(left: [Float], right: [Float], url: URL) throws {
        guard left.count == right.count,
              let format = AVAudioFormat(commonFormat: .pcmFormatFloat32, sampleRate: sampleRate, channels: 2, interleaved: false),
              let buffer = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: AVAudioFrameCount(left.count)),
              let channels = buffer.floatChannelData else {
            throw DemucsError.processing("Could not allocate the separated WAV output.")
        }
        buffer.frameLength = AVAudioFrameCount(left.count)
        left.withUnsafeBufferPointer { channels[0].update(from: $0.baseAddress!, count: left.count) }
        right.withUnsafeBufferPointer { channels[1].update(from: $0.baseAddress!, count: right.count) }
        let file = try AVAudioFile(forWriting: url, settings: format.settings)
        try file.write(from: buffer)
    }
}

@MainActor
final class StemSeparationService: ObservableObject {
    enum Availability: Equatable {
        case ready, missingModel
        var title: String { self == .ready ? "HTDemucs ready" : "Model not installed" }
        var detail: String {
            self == .ready
                ? "HTDemucs is bundled for on-device separation into vocals, drums, bass and other."
                : "The licensed HTDemucs Core ML model is missing or incomplete in this installation."
        }
    }

    @Published private(set) var availability: Availability = .missingModel
    @Published private(set) var isProcessing = false
    @Published private(set) var progress = 0.0
    @Published private(set) var statusMessage = "Ready"
    @Published private(set) var errorMessage: String?
    @Published private(set) var outputs: [Stem: URL] = [:]
    @Published private(set) var playingStem: Stem?
    private var audioPlayer: AVAudioPlayer?

    init() { refresh() }

    func refresh() {
        do { _ = try HTDemucsRuntime.modelURL(); availability = .ready }
        catch { availability = .missingModel }
    }

    func separate(track: Track) {
        guard !isProcessing else { return }
        guard availability == .ready else { errorMessage = DemucsError.modelMissing.localizedDescription; return }
        isProcessing = true
        progress = 0
        errorMessage = nil
        outputs = [:]
        statusMessage = "Preparing audio…"
        let source = LibraryStore.audioURL(for: track.fileName)
        let destination = LibraryStore.appDirectory.appendingPathComponent("Stems", isDirectory: true)
            .appendingPathComponent(track.id.uuidString, isDirectory: true)

        Task.detached(priority: .userInitiated) { [weak self] in
            do {
                let result = try Self.run(source: source, destination: destination) { value, message in
                    Task { @MainActor [weak self] in self?.progress = value; self?.statusMessage = message }
                }
                await MainActor.run {
                    self?.outputs = result
                    self?.progress = 1
                    self?.statusMessage = "Separation complete"
                    self?.isProcessing = false
                }
            } catch {
                await MainActor.run {
                    self?.errorMessage = error.localizedDescription
                    self?.statusMessage = "Separation failed"
                    self?.isProcessing = false
                }
            }
        }
    }

    nonisolated private static func run(source: URL, destination: URL, progress: @escaping (Double, String) -> Void) throws -> [Stem: URL] {
        let config = MLModelConfiguration()
        config.computeUnits = .cpuOnly
        let model = try MLModel(contentsOf: HTDemucsRuntime.modelURL(), configuration: config)
        progress(0.03, "Decoding stereo audio…")
        let (left, right) = try HTDemucsRuntime.readStereo(source)
        guard !left.isEmpty, left.count == right.count else { throw DemucsError.processing("The song could not be decoded as stereo audio.") }
        guard left.count <= Int(8 * 60 * HTDemucsRuntime.sampleRate) else {
            throw DemucsError.processing("Songs longer than 8 minutes are blocked to protect iPhone memory. Trim the audio and import it again.")
        }

        let length = HTDemucsRuntime.segmentLength
        let stride = Int(Double(length) * (1 - HTDemucsRuntime.overlap))
        let lastOffset = max(0, left.count - length)
        let chunks = max(1, Int(ceil(Double(lastOffset) / Double(stride))) + 1)
        let weights = (0..<length).map { i -> Float in
            Float(i < length / 2 ? i + 1 : length - i) / Float(length / 2)
        }
        var sumsL = (0..<4).map { _ in [Float](repeating: 0, count: left.count) }
        var sumsR = (0..<4).map { _ in [Float](repeating: 0, count: left.count) }
        var weightSums = [Float](repeating: 0, count: left.count)

        for chunk in 0..<chunks {
            let offset = min(chunk * stride, lastOffset)
            let valid = min(length, left.count - offset)
            var l = Array(left[offset..<(offset + valid)])
            var r = Array(right[offset..<(offset + valid)])
            if valid < length {
                l.append(contentsOf: repeatElement(0, count: length - valid))
                r.append(contentsOf: repeatElement(0, count: length - valid))
            }
            progress(0.08 + 0.78 * Double(chunk) / Double(chunks), "Separating segment \(chunk + 1) of \(chunks)…")
            let output = try HTDemucsRuntime.predict(left: l, right: r, model: model)
            for stem in 0..<4 {
                let channelL = output[stem * 2], channelR = output[stem * 2 + 1]
                for i in 0..<valid {
                    sumsL[stem][offset + i] += channelL[i] * weights[i]
                    sumsR[stem][offset + i] += channelR[i] * weights[i]
                }
            }
            for i in 0..<valid { weightSums[offset + i] += weights[i] }
        }

        try FileManager.default.createDirectory(at: destination, withIntermediateDirectories: true)
        var result: [Stem: URL] = [:]
        for (index, stem) in Stem.allCases.enumerated() {
            for i in 0..<left.count where weightSums[i] > 0 {
                sumsL[index][i] /= weightSums[i]
                sumsR[index][i] /= weightSums[i]
            }
            let url = destination.appendingPathComponent("\(stem.rawValue.lowercased()).wav")
            try HTDemucsRuntime.writeWAV(left: sumsL[index], right: sumsR[index], url: url)
            result[stem] = url
        }
        progress(1, "Separation complete")
        return result
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

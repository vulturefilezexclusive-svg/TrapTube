import Foundation
import AVFoundation
import Accelerate
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
    static let nFFT = 4096
    static let hop = 1024
    static let bins = 2048
    static let frames = (segmentLength + hop - 1) / hop
    static let pad = hop / 2 * 3
    static let sourceOrder: [Stem] = [.drums, .bass, .other, .vocals]
    static let window: [Float] = (0..<nFFT).map { 0.5 - 0.5 * cos(2 * Float.pi * Float($0) / Float(nFFT)) }
    static let inverseEnvelope: [Float] = {
        var envelope = [Float](repeating: 0, count: nFFT + hop * (frames + 3))
        for f in 0..<(frames + 4) { for k in 0..<nFFT { envelope[f * hop + k] += window[k] * window[k] } }
        let start = nFFT / 2 + pad
        return envelope[start..<(start + segmentLength)].map { 1 / $0 }
    }()

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

    static func reflectPad(_ x: [Float], left: Int, right: Int) -> [Float] {
        precondition(x.count > 1 && left < x.count && right < x.count)
        var result = [Float](repeating: 0, count: left + x.count + right)
        for i in 0..<left { result[i] = x[left - i] }
        result.replaceSubrange(left..<(left + x.count), with: x)
        for i in 0..<right { result[left + x.count + i] = x[x.count - 2 - i] }
        return result
    }

    static func spectrogram(_ x: [Float]) throws -> (real: [Float], imaginary: [Float]) {
        guard x.count == segmentLength else { throw DemucsError.processing("Invalid HTDemucs segment length.") }
        let padded = reflectPad(reflectPad(x, left: pad, right: pad + frames * hop - x.count), left: nFFT / 2, right: nFFT / 2)
        let fft = try vDSP.DiscreteFourierTransform(count: nFFT, direction: .forward, transformType: .complexComplex, ofType: Float.self)
        let zeros = [Float](repeating: 0, count: nFFT)
        var frame = zeros, re = zeros, im = zeros
        var real = [Float](repeating: 0, count: bins * frames), imaginary = real
        let scale = 1 / Float(nFFT).squareRoot()
        for f in 0..<frames {
            let start = (f + 2) * hop
            vDSP.multiply(padded[start..<(start + nFFT)], window, result: &frame)
            fft.transform(inputReal: frame, inputImaginary: zeros, outputReal: &re, outputImaginary: &im)
            for bin in 0..<bins {
                real[bin * frames + f] = re[bin] * scale
                imaginary[bin * frames + f] = im[bin] * scale
            }
        }
        return (real, imaginary)
    }

    static func inverseSpectrogram(real: ArraySlice<Float>, imaginary: ArraySlice<Float>) throws -> [Float] {
        guard real.count == bins * frames, imaginary.count == bins * frames else { throw DemucsError.processing("Invalid HTDemucs frequency tensor size.") }
        let fft = try vDSP.DiscreteFourierTransform(count: nFFT, direction: .inverse, transformType: .complexComplex, ofType: Float.self)
        var inReal = [Float](repeating: 0, count: nFFT), inImaginary = [Float](repeating: 0, count: nFFT)
        var outReal = inReal, outImaginary = inReal
        let origin = nFFT / 2 + pad
        var output = [Float](repeating: 0, count: segmentLength)
        let scale = 1 / Float(nFFT).squareRoot()
        for f in 0..<frames {
            for bin in 0..<bins {
                inReal[bin] = real[real.startIndex + bin * frames + f]
                inImaginary[bin] = imaginary[imaginary.startIndex + bin * frames + f]
            }
            fft.transform(inputReal: inReal, inputImaginary: inImaginary, outputReal: &outReal, outputImaginary: &outImaginary)
            let frameStart = (f + 2) * hop - origin
            let lower = max(0, -frameStart), upper = min(nFFT, segmentLength - frameStart)
            if lower < upper {
                for k in lower..<upper { output[frameStart + k] += (2 * outReal[k] - inReal[0]) * scale * window[k] }
            }
        }
        return vDSP.multiply(output, inverseEnvelope)
    }

    static func validateDSPRoundTrip() throws {
        let signal = (0..<segmentLength).map { i -> Float in
            let t = Double(i) / sampleRate
            return Float(0.4 * sin(2 * Double.pi * 55 * t) + 0.3 * sin(2 * Double.pi * 1_234.5 * t) + 0.2 * sin(2 * Double.pi * 9_876 * t))
        }
        let spec = try spectrogram(signal)
        let restored = try inverseSpectrogram(real: spec.real[...], imaginary: spec.imaginary[...])
        let worst = (8_192..<(segmentLength - 8_192)).reduce(Float.zero) { max($0, abs(restored[$1] - signal[$1])) }
        guard worst < 1e-4 else { throw DemucsError.processing("HTDemucs STFT/iSTFT self-check failed (max error \(worst)); no stems were written.") }
    }

    static func makeFloat16Array(shape: [Int], values: [Float]) throws -> MLMultiArray {
        let array = try MLMultiArray(shape: shape.map { NSNumber(value: $0) }, dataType: .float16)
        guard array.count == values.count else { throw DemucsError.processing("HTDemucs input tensor size mismatch.") }
        let strides = array.strides.map(\.intValue)
        let ptr = array.dataPointer.bindMemory(to: Float16.self, capacity: array.count)
        if shape.count == 3 {
            for c in 0..<shape[1] { for i in 0..<shape[2] { ptr[c * strides[1] + i * strides[2]] = Float16(values[c * shape[2] + i]) } }
        } else {
            for c in 0..<shape[1] { for f in 0..<shape[2] { for t in 0..<shape[3] {
                ptr[c * strides[1] + f * strides[2] + t * strides[3]] = Float16(values[c * shape[2] * shape[3] + f * shape[3] + t])
            } } }
        }
        return array
    }

    static func readFloat16(_ array: MLMultiArray, shape expected: [Int], name: String) throws -> [Float] {
        let shape = array.shape.map(\.intValue)
        guard shape == expected, array.dataType == .float16 else { throw DemucsError.invalidModel("\(name) expected Float16 \(expected), got \(array.dataType) \(shape).") }
        let strides = array.strides.map(\.intValue)
        let ptr = array.dataPointer.bindMemory(to: Float16.self, capacity: array.count)
        var result = [Float](repeating: 0, count: array.count)
        if expected.count == 3 {
            for c in 0..<expected[1] { for i in 0..<expected[2] { result[c * expected[2] + i] = Float(ptr[c * strides[1] + i * strides[2]]) } }
        } else {
            for c in 0..<expected[1] { for f in 0..<expected[2] { for t in 0..<expected[3] {
                result[c * expected[2] * expected[3] + f * expected[3] + t] = Float(ptr[c * strides[1] + f * strides[2] + t * strides[3]])
            } } }
        }
        guard result.allSatisfy(\.isFinite) else { throw DemucsError.processing("HTDemucs returned NaN or infinite output; no stems were written.") }
        return result
    }

    static func predict(left: [Float], right: [Float], model: MLModel) throws -> [[[Float]]] {
        let leftSpec = try spectrogram(left), rightSpec = try spectrogram(right)
        let spectral = leftSpec.real + leftSpec.imaginary + rightSpec.real + rightSpec.imaginary
        let wave = try makeFloat16Array(shape: [1, 2, segmentLength], values: left + right)
        let spec = try makeFloat16Array(shape: [1, 4, bins, frames], values: spectral)
        let input = try MLDictionaryFeatureProvider(dictionary: [
            "audio_waveform": MLFeatureValue(multiArray: wave),
            "spectral_magnitude": MLFeatureValue(multiArray: spec)
        ])
        let prediction = try model.prediction(from: input)
        guard let timeArray = prediction.featureValue(for: "time_output")?.multiArrayValue,
              let freqArray = prediction.featureValue(for: "freq_output")?.multiArrayValue else {
            throw DemucsError.invalidModel("Expected time_output and freq_output; got \(prediction.featureNames.sorted()).")
        }
        let time = try readFloat16(timeArray, shape: [1, 8, segmentLength], name: "time_output")
        let freq = try readFloat16(freqArray, shape: [1, 16, bins, frames], name: "freq_output")
        let plane = bins * frames
        var stems = Array(repeating: Array(repeating: [Float](repeating: 0, count: segmentLength), count: 2), count: 4)
        for source in 0..<4 { for channel in 0..<2 {
            let base = (source * 4 + channel * 2) * plane
            let spectralWave = try inverseSpectrogram(real: freq[base..<(base + plane)], imaginary: freq[(base + plane)..<(base + 2 * plane)])
            let timeBase = (source * 2 + channel) * segmentLength
            for i in 0..<segmentLength { stems[source][channel][i] = spectralWave[i] + time[timeBase + i] }
        } }
        return stems
    }

    static func segment(of audio: [[Float]], at offset: Int) -> [[Float]] {
        let length = audio[0].count
        let valid = min(segmentLength, length - offset)
        let start = offset - (segmentLength - valid) / 2
        let from = max(0, start), to = min(length, start + segmentLength)
        return audio.map { channel in
            var output = [Float](repeating: 0, count: segmentLength)
            if from < to { output.replaceSubrange((from - start)..<(to - start), with: channel[from..<to]) }
            return output
        }
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
        case bundled, missingModel
        var title: String { self == .bundled ? "HTDemucs model bundled" : "Model not installed" }
        var detail: String {
            self == .bundled
                ? "Model files are present. The Float16 tensor schema and STFT/iSTFT reconstruction are checked when separation starts."
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
        do { _ = try HTDemucsRuntime.modelURL(); availability = .bundled }
        catch { availability = .missingModel }
    }

    func separate(track: Track) {
        guard !isProcessing else { return }
        guard availability == .bundled else { errorMessage = DemucsError.modelMissing.localizedDescription; return }
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
        try HTDemucsRuntime.validateDSPRoundTrip()
        let config = MLModelConfiguration()
        config.computeUnits = .cpuAndGPU
        let model = try MLModel(contentsOf: HTDemucsRuntime.modelURL(), configuration: config)
        let inputNames = Set(model.modelDescription.inputDescriptionsByName.keys)
        let outputNames = Set(model.modelDescription.outputDescriptionsByName.keys)
        guard inputNames == ["audio_waveform", "spectral_magnitude"],
              outputNames == ["time_output", "freq_output"] else {
            throw DemucsError.invalidModel("Inputs \(inputNames.sorted()); outputs \(outputNames.sorted()).")
        }
        for name in inputNames {
            guard model.modelDescription.inputDescriptionsByName[name]?.multiArrayConstraint?.dataType == .float16 else {
                throw DemucsError.invalidModel("Input \(name) is not Float16.")
            }
        }
        for name in outputNames {
            guard model.modelDescription.outputDescriptionsByName[name]?.multiArrayConstraint?.dataType == .float16 else {
                throw DemucsError.invalidModel("Output \(name) is not Float16.")
            }
        }
        progress(0.03, "Decoding stereo audio…")
        let (left, right) = try HTDemucsRuntime.readStereo(source)
        guard !left.isEmpty, left.count == right.count else { throw DemucsError.processing("The song could not be decoded as stereo audio.") }
        guard left.count <= Int(3 * 60 * HTDemucsRuntime.sampleRate) else {
            throw DemucsError.processing("Songs longer than 3 minutes are blocked to protect iPhone memory. Trim the audio and import it again.")
        }
        let length = HTDemucsRuntime.segmentLength
        let stride = length * 3 / 4
        let offsets = Array(Swift.stride(from: 0, to: left.count, by: stride))
        let half = length / 2
        let weights = (0..<length).map { Float($0 < half ? $0 + 1 : length - $0) / Float(half) }
        var sumsL = (0..<4).map { _ in [Float](repeating: 0, count: left.count) }
        var sumsR = (0..<4).map { _ in [Float](repeating: 0, count: left.count) }
        var weightSums = [Float](repeating: 0, count: left.count)
        for (chunk, offset) in offsets.enumerated() {
            let segment = HTDemucsRuntime.segment(of: [left, right], at: offset)
            let valid = min(length, left.count - offset)
            let trim = (length - valid) / 2
            progress(0.08 + 0.78 * Double(chunk + 1) / Double(offsets.count), "Separating segment \(chunk + 1) of \(offsets.count)…")
            let output = try HTDemucsRuntime.predict(left: segment[0], right: segment[1], model: model)
            for stem in 0..<4 { for channel in 0..<2 { for i in 0..<valid {
                if channel == 0 { sumsL[stem][offset + i] += output[stem][channel][trim + i] * weights[i] }
                else { sumsR[stem][offset + i] += output[stem][channel][trim + i] * weights[i] }
            } } }
            for i in 0..<valid { weightSums[offset + i] += weights[i] }
        }
        try FileManager.default.createDirectory(at: destination, withIntermediateDirectories: true)
        var result: [Stem: URL] = [:]
        for index in 0..<4 {
            for i in 0..<left.count where weightSums[i] > 0 {
                sumsL[index][i] /= weightSums[i]
                sumsR[index][i] /= weightSums[i]
            }
            let stem = HTDemucsRuntime.sourceOrder[index]
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

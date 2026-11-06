import Foundation
import AVFoundation
import Accelerate
import CoreML
import Combine

enum Stem: String, CaseIterable, Identifiable {
    case drums = "Drums"
    case bass = "Bass"
    case vocals = "Vocals"
    case other = "Other"
    var id: String { rawValue }
    var modelIndex: Int {
        switch self { case .drums: return 0; case .bass: return 1; case .other: return 2; case .vocals: return 3 }
    }
    var icon: String {
        switch self { case .vocals: return "mic.fill"; case .drums: return "drum.fill"; case .bass: return "guitars.fill"; case .other: return "waveform" }
    }
}

enum DemucsError: LocalizedError {
    case modelNotFound, processingFailed(String)
    var errorDescription: String? {
        switch self {
        case .modelNotFound: return "HTDemucs Core ML model is missing. Rebuild using the repository's model-download workflow."
        case .processingFailed(let message): return message
        }
    }
}

private enum HTDemucsDSP {
    static let fftSize = 4096
    static let hopSize = 1024
    static let numBins = 2048   // fftSize / 2
    static let numFrames = 336
    static let segmentLength = 343980
    static let sampleRate: Double = 44100
    static let overlap: Double = 0.25

    // Periodic Hann window (matches PyTorch's hann_window with periodic=True)
    static let window: [Float] = (0..<fftSize).map {
        Float(0.5 * (1.0 - cos(2.0 * .pi * Double($0) / Double(fftSize))))
    }

    /// Reflect-pad a signal with asymmetric left/right amounts (matches PyTorch's F.pad with mode='reflect')
    static func reflectPad(signal: [Float], left: Int, right: Int) -> [Float] {
        let n = signal.count
        var padded = [Float](repeating: 0, count: n + left + right)
        for i in 0..<left {
            padded[i] = signal[left - i]
        }
        signal.withUnsafeBufferPointer { src in
            padded.withUnsafeMutableBufferPointer { dst in
                memcpy(dst.baseAddress! + left, src.baseAddress!, n * MemoryLayout<Float>.size)
            }
        }
        for i in 0..<right {
            padded[left + n + i] = signal[n - 2 - i]
        }
        return padded
    }

    /// Load entire audio file as stereo Float32 arrays, resampled to 44100 Hz
    static func loadFullAudio(url: URL) throws -> (left: [Float], right: [Float]) {
        _ = url.startAccessingSecurityScopedResource()
        defer { url.stopAccessingSecurityScopedResource() }

        let sourceFile = try AVAudioFile(forReading: url)
        let targetFormat = AVAudioFormat(
            commonFormat: .pcmFormatFloat32,
            sampleRate: sampleRate,
            channels: 2,
            interleaved: false
        )!

        let totalFrames = AVAudioFrameCount(
            Double(sourceFile.length) * sampleRate / sourceFile.processingFormat.sampleRate
        )
        guard let outputBuffer = AVAudioPCMBuffer(pcmFormat: targetFormat, frameCapacity: totalFrames) else {
            throw DemucsError.processingFailed("Failed to create audio buffer")
        }

        if sourceFile.processingFormat.sampleRate == sampleRate && sourceFile.processingFormat.channelCount == 2 {
            try sourceFile.read(into: outputBuffer)
        } else {
            guard let converter = AVAudioConverter(from: sourceFile.processingFormat, to: targetFormat) else {
                throw DemucsError.processingFailed("Cannot convert audio format")
            }
            let srcBuffer = AVAudioPCMBuffer(pcmFormat: sourceFile.processingFormat, frameCapacity: AVAudioFrameCount(sourceFile.length))!
            try sourceFile.read(into: srcBuffer)
            var error: NSError?
            converter.convert(to: outputBuffer, error: &error) { _, outStatus in
                outStatus.pointee = .haveData
                return srcBuffer
            }
            if let error { throw error }
        }

        let count = Int(outputBuffer.frameLength)
        let leftPtr = outputBuffer.floatChannelData![0]
        let rightCh = outputBuffer.format.channelCount > 1 ? 1 : 0
        let rightPtr = outputBuffer.floatChannelData![rightCh]

        let left = Array(UnsafeBufferPointer(start: leftPtr, count: count))
        let right = Array(UnsafeBufferPointer(start: rightPtr, count: count))
        return (left, right)
    }

    /// Forward STFT using vDSP. Frame count derived from signal length.
    static func forwardSTFT(signal: [Float]) -> (real: [Float], imag: [Float], frames: Int) {
        let log2n = vDSP_Length(log2(Float(fftSize)))
        guard let fftSetup = vDSP_create_fftsetup(log2n, FFTRadix(kFFTRadix2)) else { return ([], [], 0) }
        defer { vDSP_destroy_fftsetup(fftSetup) }

        let halfN = fftSize / 2
        let totalFrames = max(1, (signal.count - fftSize) / hopSize + 1)
        var allReal = [Float](repeating: 0, count: numBins * totalFrames)
        var allImag = [Float](repeating: 0, count: numBins * totalFrames)
        var frame = [Float](repeating: 0, count: fftSize)
        var rp = [Float](repeating: 0, count: halfN)
        var ip = [Float](repeating: 0, count: halfN)

        for f in 0..<totalFrames {
            let start = f * hopSize
            let avail = min(fftSize, max(0, signal.count - start))
            vDSP_vclr(&frame, 1, vDSP_Length(fftSize))
            if avail > 0 {
                signal.withUnsafeBufferPointer { buf in
                    frame.withUnsafeMutableBufferPointer { dst in
                        memcpy(dst.baseAddress!, buf.baseAddress! + start, avail * MemoryLayout<Float>.size)
                    }
                }
            }

            vDSP_vmul(frame, 1, window, 1, &frame, 1, vDSP_Length(fftSize))

            frame.withUnsafeBufferPointer { src in
                src.baseAddress!.withMemoryRebound(to: DSPComplex.self, capacity: halfN) { complexPtr in
                    rp.withUnsafeMutableBufferPointer { rpBuf in
                        ip.withUnsafeMutableBufferPointer { ipBuf in
                            var sc = DSPSplitComplex(realp: rpBuf.baseAddress!, imagp: ipBuf.baseAddress!)
                            vDSP_ctoz(complexPtr, 2, &sc, 1, vDSP_Length(halfN))
                        }
                    }
                }
            }

            rp.withUnsafeMutableBufferPointer { rpBuf in
                ip.withUnsafeMutableBufferPointer { ipBuf in
                    var sc = DSPSplitComplex(realp: rpBuf.baseAddress!, imagp: ipBuf.baseAddress!)
                    vDSP_fft_zrip(fftSetup, &sc, 1, log2n, FFTDirection(kFFTDirection_Forward))
                }
            }

            allReal[f] = rp[0] * 0.5
            allImag[f] = 0
            for k in 1..<numBins {
                let idx = k * totalFrames + f
                allReal[idx] = rp[k] * 0.5
                allImag[idx] = ip[k] * 0.5
            }
        }

        return (allReal, allImag, totalFrames)
    }

    /// Compute spectral input matching Python's _spec + _magnitude with cac=True.
    static func computeSpectralInput(left: [Float], right: [Float]) -> [Float] {
        let le = numFrames
        let specPadLeft = hopSize / 2 * 3
        let specPadRight = specPadLeft + le * hopSize - segmentLength

        let channelSize = numBins * le
        var result = [Float](repeating: 0, count: 4 * channelSize)

        for (ch, signal) in [left, right].enumerated() {
            let padded = reflectPad(signal: signal, left: specPadLeft, right: specPadRight)
            let (real, imag, _) = forwardSTFT(signal: padded)
            let realCh = ch * 2
            let imagCh = ch * 2 + 1
            result.withUnsafeMutableBufferPointer { dst in
                real.withUnsafeBufferPointer { src in
                    memcpy(dst.baseAddress! + realCh * channelSize, src.baseAddress!, channelSize * MemoryLayout<Float>.size)
                }
                imag.withUnsafeBufferPointer { src in
                    memcpy(dst.baseAddress! + imagCh * channelSize, src.baseAddress!, channelSize * MemoryLayout<Float>.size)
                }
            }
        }

        // Normalize to match Python's torch.stft(normalized=True)
        var normScale = Float(1.0 / sqrt(Double(fftSize)))
        vDSP_vsmul(result, 1, &normScale, &result, 1, vDSP_Length(result.count))

        return result
    }

    /// Inverse STFT with overlap-add. Frame count derived from input array size.
    static func inverseSTFT(real: [Float], imag: [Float], outputLength: Int) -> [Float] {
        let log2n = vDSP_Length(log2(Float(fftSize)))
        guard let fftSetup = vDSP_create_fftsetup(log2n, FFTRadix(kFFTRadix2)) else { return [] }
        defer { vDSP_destroy_fftsetup(fftSetup) }

        let halfN = fftSize / 2
        let totalFrames = real.count / numBins
        var output = [Float](repeating: 0, count: outputLength)
        var windowSum = [Float](repeating: 0, count: outputLength)
        var rp = [Float](repeating: 0, count: halfN)
        var ip = [Float](repeating: 0, count: halfN)
        var frame = [Float](repeating: 0, count: fftSize)

        for f in 0..<totalFrames {
            rp[0] = real[f] * 2.0
            ip[0] = 0
            for k in 1..<numBins {
                let idx = k * totalFrames + f
                rp[k] = real[idx] * 2.0
                ip[k] = imag[idx] * 2.0
            }

            rp.withUnsafeMutableBufferPointer { rpBuf in
                ip.withUnsafeMutableBufferPointer { ipBuf in
                    var sc = DSPSplitComplex(realp: rpBuf.baseAddress!, imagp: ipBuf.baseAddress!)
                    vDSP_fft_zrip(fftSetup, &sc, 1, log2n, FFTDirection(kFFTDirection_Inverse))
                }
            }

            rp.withUnsafeBufferPointer { rpBuf in
                ip.withUnsafeBufferPointer { ipBuf in
                    var sc = DSPSplitComplex(
                        realp: UnsafeMutablePointer(mutating: rpBuf.baseAddress!),
                        imagp: UnsafeMutablePointer(mutating: ipBuf.baseAddress!)
                    )
                    frame.withUnsafeMutableBufferPointer { dst in
                        dst.baseAddress!.withMemoryRebound(to: DSPComplex.self, capacity: halfN) { complexPtr in
                            vDSP_ztoc(&sc, 1, complexPtr, 2, vDSP_Length(halfN))
                        }
                    }
                }
            }

            var scale: Float = 1.0 / Float(2 * fftSize)
            vDSP_vsmul(frame, 1, &scale, &frame, 1, vDSP_Length(fftSize))
            vDSP_vmul(frame, 1, window, 1, &frame, 1, vDSP_Length(fftSize))

            let start = f * hopSize
            for i in 0..<fftSize {
                let idx = start + i
                if idx < outputLength {
                    output[idx] += frame[i]
                    windowSum[idx] += window[i] * window[i]
                }
            }
        }

        for i in 0..<outputLength {
            if windowSum[i] > 1e-8 {
                output[i] /= windowSum[i]
            }
        }
        return output
    }

    /// Inverse STFT matching Python's _ispec for a single mono channel.
    static func inverseSpec(real: [Float], imag: [Float]) -> [Float] {
        let le = numFrames
        let totalFrames = le + 4
        let specPad = hopSize / 2 * 3
        let centerPad = fftSize / 2

        var paddedReal = [Float](repeating: 0, count: numBins * totalFrames)
        var paddedImag = [Float](repeating: 0, count: numBins * totalFrames)
        for bin in 0..<numBins {
            let srcOffset = bin * le
            let dstOffset = bin * totalFrames + 2
            real.withUnsafeBufferPointer { src in
                paddedReal.withUnsafeMutableBufferPointer { dst in
                    memcpy(dst.baseAddress! + dstOffset, src.baseAddress! + srcOffset, le * MemoryLayout<Float>.size)
                }
            }
            imag.withUnsafeBufferPointer { src in
                paddedImag.withUnsafeMutableBufferPointer { dst in
                    memcpy(dst.baseAddress! + dstOffset, src.baseAddress! + srcOffset, le * MemoryLayout<Float>.size)
                }
            }
        }

        let rawLen = (totalFrames - 1) * hopSize + fftSize
        let rawOutput = inverseSTFT(real: paddedReal, imag: paddedImag, outputLength: rawLen)
        let trimStart = centerPad + specPad
        return Array(rawOutput[trimStart..<trimStart + segmentLength])
    }

    /// Extract a 2D channel from a 4D MLMultiArray, respecting strides
    static func extractChannel(from array: MLMultiArray, batch: Int, channel: Int, height: Int, width: Int) -> [Float] {
        let strides = array.strides.map { $0.intValue }
        let baseOffset = batch * strides[0] + channel * strides[1]
        let hStride = strides[2]
        let wStride = strides[3]
        var result = [Float](repeating: 0, count: height * width)

        if array.dataType == .float32 {
            let ptr = array.dataPointer.bindMemory(to: Float.self, capacity: array.count)
            if wStride == 1 {
                result.withUnsafeMutableBufferPointer { dst in
                    for h in 0..<height {
                        memcpy(dst.baseAddress! + h * width, ptr + baseOffset + h * hStride, width * 4)
                    }
                }
            } else {
                for h in 0..<height {
                    for w in 0..<width {
                        result[h * width + w] = ptr[baseOffset + h * hStride + w * wStride]
                    }
                }
            }
        } else if array.dataType == .float16 {
            let ptr = array.dataPointer.assumingMemoryBound(to: UInt16.self)
            if wStride == 1 {
                for h in 0..<height {
                    let rowStart = baseOffset + h * hStride
                    var srcBuf = vImage_Buffer(
                        data: UnsafeMutablePointer(mutating: ptr + rowStart),
                        height: 1, width: vImagePixelCount(width), rowBytes: width * 2)
                    result.withUnsafeMutableBufferPointer { dst in
                        var dstBuf = vImage_Buffer(
                            data: dst.baseAddress! + h * width,
                            height: 1, width: vImagePixelCount(width), rowBytes: width * 4)
                        vImageConvert_Planar16FtoPlanarF(&srcBuf, &dstBuf, 0)
                    }
                }
            } else {
                for h in 0..<height {
                    for w in 0..<width {
                        result[h * width + w] = array[[batch, channel, h, w] as [NSNumber]].floatValue
                    }
                }
            }
        }
        return result
    }

    /// Extract a 1D channel from a 3D MLMultiArray, respecting strides
    static func extractChannel1D(from array: MLMultiArray, batch: Int, channel: Int, width: Int) -> [Float] {
        let strides = array.strides.map { $0.intValue }
        let baseOffset = batch * strides[0] + channel * strides[1]
        let wStride = strides[2]
        var result = [Float](repeating: 0, count: width)

        if array.dataType == .float32 {
            let ptr = array.dataPointer.bindMemory(to: Float.self, capacity: array.count)
            if wStride == 1 {
                result.withUnsafeMutableBufferPointer { dst in
                    memcpy(dst.baseAddress!, ptr + baseOffset, width * MemoryLayout<Float>.size)
                }
            } else {
                for w in 0..<width { result[w] = ptr[baseOffset + w * wStride] }
            }
        } else if array.dataType == .float16 {
            let ptr = array.dataPointer.assumingMemoryBound(to: UInt16.self)
            if wStride == 1 {
                var srcBuf = vImage_Buffer(
                    data: UnsafeMutablePointer(mutating: ptr + baseOffset),
                    height: 1, width: vImagePixelCount(width), rowBytes: width * 2)
                result.withUnsafeMutableBufferPointer { dst in
                    var dstBuf = vImage_Buffer(
                        data: dst.baseAddress!, height: 1,
                        width: vImagePixelCount(width), rowBytes: width * 4)
                    vImageConvert_Planar16FtoPlanarF(&srcBuf, &dstBuf, 0)
                }
            } else {
                for w in 0..<width { result[w] = array[[batch, channel, w] as [NSNumber]].floatValue }
            }
        }
        return result
    }

    /// Write stereo Float32 audio to a WAV file
    static func writeWAV(left: [Float], right: [Float], to url: URL) throws {
        let format = AVAudioFormat(commonFormat: .pcmFormatFloat32, sampleRate: sampleRate, channels: 2, interleaved: false)!
        let count = AVAudioFrameCount(min(left.count, right.count))
        guard let buffer = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: count) else {
            throw DemucsError.processingFailed("Failed to create output buffer")
        }
        buffer.frameLength = count
        left.withUnsafeBufferPointer { src in
            buffer.floatChannelData![0].update(from: src.baseAddress!, count: Int(count))
        }
        right.withUnsafeBufferPointer { src in
            buffer.floatChannelData![1].update(from: src.baseAddress!, count: Int(count))
        }
        let file = try AVAudioFile(forWriting: url, settings: format.settings)
        try file.write(from: buffer)
    }

    // MARK: - Segment Processing

    /// Process a single segment through the model, returning per-stem stereo audio.
    static func processSegment(left: [Float], right: [Float], model: MLModel) throws -> [(left: [Float], right: [Float])] {
        let spectralData = computeSpectralInput(left: left, right: right)

        let spectral = try MLMultiArray(shape: [1, 4, 2048, 336], dataType: .float32)
        let spectralCount = 4 * numBins * numFrames
        let spectralPtr = spectral.dataPointer.bindMemory(to: Float.self, capacity: spectralCount)
        let spectralStrides = spectral.strides.map { $0.intValue }
        if spectralStrides.last == 1 && spectralStrides[2] == numFrames {
            spectralData.withUnsafeBufferPointer { src in
                memcpy(spectralPtr, src.baseAddress!, spectralCount * MemoryLayout<Float>.size)
            }
        } else {
            for c in 0..<4 {
                for h in 0..<numBins {
                    for w in 0..<numFrames {
                        spectralPtr[c * spectralStrides[1] + h * spectralStrides[2] + w * spectralStrides[3]] =
                            spectralData[c * numBins * numFrames + h * numFrames + w]
                    }
                }
            }
        }

        let waveform = try MLMultiArray(shape: [1, 2, 343980], dataType: .float32)
        let wavePtr = waveform.dataPointer.bindMemory(to: Float.self, capacity: 2 * segmentLength)
        left.withUnsafeBufferPointer { src in memcpy(wavePtr, src.baseAddress!, segmentLength * 4) }
        right.withUnsafeBufferPointer { src in memcpy(wavePtr + segmentLength, src.baseAddress!, segmentLength * 4) }

        let inputFeatures = try MLDictionaryFeatureProvider(dictionary: [
            "spectral_magnitude": MLFeatureValue(multiArray: spectral),
            "audio_waveform": MLFeatureValue(multiArray: waveform)
        ])
        let output = try model.prediction(from: inputFeatures)

        guard let freqOut = output.featureValue(for: "freq_output")?.multiArrayValue,
              let timeOut = output.featureValue(for: "time_output")?.multiArrayValue else {
            throw DemucsError.processingFailed("Missing model output")
        }

        let ispecScale = Float(sqrt(Double(fftSize)))
        var results: [(left: [Float], right: [Float])] = []

        for stem in Stem.allCases {
            let i = stem.modelIndex
            let freqLR = extractChannel(from: freqOut, batch: 0, channel: 4 * i,     height: numBins, width: numFrames)
            let freqLI = extractChannel(from: freqOut, batch: 0, channel: 4 * i + 1, height: numBins, width: numFrames)
            let freqRR = extractChannel(from: freqOut, batch: 0, channel: 4 * i + 2, height: numBins, width: numFrames)
            let freqRI = extractChannel(from: freqOut, batch: 0, channel: 4 * i + 3, height: numBins, width: numFrames)

            var freqLeft = inverseSpec(real: freqLR, imag: freqLI)
            var freqRight = inverseSpec(real: freqRR, imag: freqRI)
            var scale = ispecScale
            vDSP_vsmul(freqLeft, 1, &scale, &freqLeft, 1, vDSP_Length(freqLeft.count))
            vDSP_vsmul(freqRight, 1, &scale, &freqRight, 1, vDSP_Length(freqRight.count))

            let timeLeft = extractChannel1D(from: timeOut, batch: 0, channel: 2 * i, width: segmentLength)
            let timeRight = extractChannel1D(from: timeOut, batch: 0, channel: 2 * i + 1, width: segmentLength)

            var stemLeft = [Float](repeating: 0, count: segmentLength)
            var stemRight = [Float](repeating: 0, count: segmentLength)
            vDSP_vadd(freqLeft, 1, timeLeft, 1, &stemLeft, 1, vDSP_Length(segmentLength))
            vDSP_vadd(freqRight, 1, timeRight, 1, &stemRight, 1, vDSP_Length(segmentLength))
            results.append((left: stemLeft, right: stemRight))
        }
        return results
    }

    /// Build triangular overlap-add window (matches Python apply.py)
    static func buildWeight() -> [Float] {
        let half = segmentLength / 2
        var w = [Float](repeating: 0, count: segmentLength)
        for i in 0..<half { w[i] = Float(i + 1) }
        for i in half..<segmentLength { w[i] = Float(segmentLength - i) }
        var maxVal: Float = 0
        vDSP_maxv(w, 1, &maxVal, vDSP_Length(segmentLength))
        if maxVal > 0 { var inv = 1.0 / maxVal; vDSP_vsmul(w, 1, &inv, &w, 1, vDSP_Length(segmentLength)) }
        return w
    }
}



@MainActor
final class StemSeparationService: ObservableObject {
    enum Availability: Equatable {
        case ready, missingModel
        var title: String { self == .ready ? "HTDemucs ready" : "Model not installed" }
        var detail: String {
            self == .ready
                ? "On-device HTDemucs separates local audio into vocals, drums, bass and other."
                : "The HTDemucs model was not included in this build. Rebuild through GitHub Actions to download and bundle it."
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
        availability = Bundle.main.url(forResource: "HTDemucs_SourceSeparation_F32", withExtension: "mlmodelc") == nil
            ? .missingModel : .ready
    }

    func separate(track: Track) {
        guard !isProcessing else { return }
        guard availability == .ready else { errorMessage = DemucsError.modelNotFound.localizedDescription; return }
        isProcessing = true
        progress = 0
        errorMessage = nil
        outputs = [:]
        statusMessage = "Preparing audio…"
        let sourceURL = LibraryStore.audioURL(for: track.fileName)
        let outputDirectory = LibraryStore.appDirectory
            .appendingPathComponent("Stems", isDirectory: true)
            .appendingPathComponent(track.id.uuidString, isDirectory: true)

        Task.detached(priority: .userInitiated) { [weak self] in
            do {
                let result = try Self.runSeparation(sourceURL: sourceURL, outputDirectory: outputDirectory) { value, message in
                    Task { @MainActor [weak self] in
                        self?.progress = value
                        self?.statusMessage = message
                    }
                }
                await MainActor.run {
                    self?.outputs = result
                    self?.isProcessing = false
                    self?.progress = 1
                    self?.statusMessage = "Separation complete"
                }
            } catch {
                await MainActor.run {
                    self?.isProcessing = false
                    self?.errorMessage = error.localizedDescription
                    self?.statusMessage = "Separation failed"
                }
            }
        }
    }

    nonisolated private static func runSeparation(
        sourceURL: URL,
        outputDirectory: URL,
        progress: @escaping (Double, String) -> Void
    ) throws -> [Stem: URL] {
        let modelURL = Bundle.main.url(forResource: "HTDemucs_SourceSeparation_F32", withExtension: "mlmodelc")
        guard let modelURL else { throw DemucsError.modelNotFound }
        let configuration = MLModelConfiguration()
        configuration.computeUnits = .cpuOnly
        let model = try MLModel(contentsOf: modelURL, configuration: configuration)

        progress(0.04, "Decoding and resampling audio…")
        let (left, right) = try HTDemucsDSP.loadFullAudio(url: sourceURL)
        guard !left.isEmpty, left.count == right.count else {
            throw DemucsError.processingFailed("The selected file contains no usable stereo audio.")
        }

        let totalSamples = left.count
        let segmentLength = HTDemucsDSP.segmentLength
        let stride = Int(Double(segmentLength) * (1.0 - HTDemucsDSP.overlap))
        let chunkCount = max(1, Int(ceil(Double(max(0, totalSamples - segmentLength)) / Double(stride))) + 1)
        let weight = HTDemucsDSP.buildWeight()

        // Four stereo accumulators; memory use is substantial on long tracks.
        var accL = Stem.allCases.map { _ in [Float](repeating: 0, count: totalSamples) }
        var accR = Stem.allCases.map { _ in [Float](repeating: 0, count: totalSamples) }
        var weightSum = [Float](repeating: 0, count: totalSamples)

        for chunk in 0..<chunkCount {
            let offset = min(chunk * stride, max(0, totalSamples - segmentLength))
            let chunkLength = min(segmentLength, totalSamples - offset)
            var segmentL = Array(left[offset..<(offset + chunkLength)])
            var segmentR = Array(right[offset..<(offset + chunkLength)])
            if segmentL.count < segmentLength {
                let padding = segmentLength - segmentL.count
                segmentL.append(contentsOf: repeatElement(Float(0), count: padding))
                segmentR.append(contentsOf: repeatElement(Float(0), count: padding))
            }
            progress(0.10 + 0.78 * Double(chunk) / Double(chunkCount), "Separating segment \(chunk + 1) of \(chunkCount)…")
            let stems = try HTDemucsDSP.processSegment(left: segmentL, right: segmentR, model: model)
            for stemIndex in Stem.allCases.indices {
                for i in 0..<chunkLength {
                    accL[stemIndex][offset + i] += stems[stemIndex].left[i] * weight[i]
                    accR[stemIndex][offset + i] += stems[stemIndex].right[i] * weight[i]
                }
            }
            for i in 0..<chunkLength { weightSum[offset + i] += weight[i] }
        }

        try FileManager.default.createDirectory(at: outputDirectory, withIntermediateDirectories: true)
        var result: [Stem: URL] = [:]
        progress(0.91, "Writing separated audio files…")
        for (index, stem) in Stem.allCases.enumerated() {
            for i in 0..<totalSamples where weightSum[i] > 1e-8 {
                accL[index][i] /= weightSum[i]
                accR[index][i] /= weightSum[i]
            }
            let url = outputDirectory.appendingPathComponent("\(stem.rawValue.lowercased()).wav")
            try HTDemucsDSP.writeWAV(left: accL[index], right: accR[index], to: url)
            result[stem] = url
        }
        progress(1, "Complete")
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

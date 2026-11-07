import Foundation
import Demucs

@main
struct DemucsSmoke {
    static func main() async throws {
        let cache = FileManager.default.temporaryDirectory
            .appendingPathComponent("TrapTube-Demucs-FT-Smoke", isDirectory: true)
        DemucsEngine.configureCacheDirectory(cache)

        print("Downloading HTDemucs FT weights if not cached…")
        try await DemucsEngine.download(.fineTunedAll) { update in
            print("Model download: \(Int(update.fraction * 100))%")
        }

        let engine = DemucsEngine()
        print("Loading fine-tuned four-stem model…")
        try await engine.load(.fineTunedAll)
        try await engine.warmup()

        let sampleRate: UInt32 = 44_100
        let sampleCount = Int(sampleRate) * 10
        var left = [Float](repeating: 0, count: sampleCount)
        var right = [Float](repeating: 0, count: sampleCount)
        for index in 0..<sampleCount {
            let time = Double(index) / Double(sampleRate)
            left[index] = Float(0.16 * sin(2 * .pi * 55 * time) + 0.08 * sin(2 * .pi * 440 * time) + 0.035 * sin(2 * .pi * 1_600 * time))
            right[index] = Float(0.14 * sin(2 * .pi * 61 * time) + 0.07 * sin(2 * .pi * 523.25 * time) + 0.04 * sin(2 * .pi * 2_100 * time))
        }

        print("Running a 10-second stereo inference across the chunk boundary…")
        let stems = try await engine.separate(left: left, right: right, sampleRate: sampleRate) { update in
            print("Inference: chunk \(update.chunkIndex)/\(update.totalChunks), \(Int(update.fraction * 100))%")
        }

        let expected: Set<String> = ["drums", "bass", "other", "vocals"]
        let actual = Set(stems.map { $0.kind.rawValue })
        guard actual == expected else {
            throw NSError(domain: "TrapTube.DemucsSmoke", code: 1, userInfo: [
                NSLocalizedDescriptionKey: "Unexpected stem set: \(actual.sorted())"
            ])
        }
        for stem in stems {
            guard stem.left.count == sampleCount, stem.right.count == sampleCount else {
                throw NSError(domain: "TrapTube.DemucsSmoke", code: 2, userInfo: [
                    NSLocalizedDescriptionKey: "\(stem.kind.rawValue) returned the wrong sample count."
                ])
            }
            guard stem.left.allSatisfy(\.isFinite), stem.right.allSatisfy(\.isFinite) else {
                throw NSError(domain: "TrapTube.DemucsSmoke", code: 3, userInfo: [
                    NSLocalizedDescriptionKey: "\(stem.kind.rawValue) returned non-finite samples."
                ])
            }
        }
        await engine.unload()
        print("PASS: HTDemucs FT loaded, warmed up, and returned four finite, full-length stereo stems.")
    }
}

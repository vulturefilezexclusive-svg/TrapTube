import Foundation
import Combine
import ffmpegkit

struct TypeTypeInstance: Decodable {
    let name: String?
    let version: String?
    let apiVersion: Int?
    let guestAllowed: Bool?
    let supportedServices: [Int]?
}

struct TypeTypeVideo: Decodable, Identifiable {
    let id: String
    let title: String
    let url: String
    let thumbnailUrl: String
    let uploaderName: String
    let uploaderUrl: String?
    let duration: Int64
    let viewCount: Int64?
    let streamType: String?
    let isLive: Bool?
    let shortDescription: String?

    var displayDuration: String {
        let total = max(0, Int(duration))
        return String(format: "%d:%02d", total / 60, total % 60)
    }

    var watchParameter: String {
        guard let components = URLComponents(string: url) else { return id }
        if let value = components.queryItems?.first(where: { $0.name == "v" })?.value, !value.isEmpty { return value }
        let last = components.path.split(separator: "/").last.map(String.init) ?? id
        return last
    }
}

struct TypeTypeSearchPage: Decodable {
    let items: [TypeTypeVideo]
    let nextpage: String?
    let searchSuggestion: String?
    let isCorrectedSearch: Bool?
}

struct TypeTypeService {
    static let baseAddress = URL(string: "https://watch.typetype.video")!
    private let defaults = UserDefaults.standard
    private var token: String? { defaults.string(forKey: "typetype.accessToken") }

    enum ServiceError: LocalizedError {
        case invalidAddress, guestNotAllowed, missingToken, badResponse(Int, String)
        var errorDescription: String? {
            switch self {
            case .invalidAddress: return "The TypeType server address is invalid."
            case .guestNotAllowed: return "This TypeType instance does not allow guest access. Sign-in is required."
            case .missingToken: return "TypeType did not return an access token."
            case let .badResponse(code, message): return "TypeType returned HTTP \(code): \(message)"
            }
        }
    }

    func checkHealth(baseAddress: String = "https://watch.typetype.video") async throws -> String {
        let instance = try await connect()
        return "Connected to \(instance.name ?? "TypeType") · v\(instance.version ?? "unknown") · API \(instance.apiVersion ?? 0)"
    }

    func connect() async throws -> TypeTypeInstance {
        let instance: TypeTypeInstance = try await request(path: "/api/instance", authenticated: false)
        if token == nil || token?.isEmpty == true {
            guard instance.guestAllowed == true else { throw ServiceError.guestNotAllowed }
            struct GuestResponse: Decodable { let accessToken: String?; let token: String? }
            let response: GuestResponse = try await request(path: "/api/auth/guest", method: "POST", body: Data("{}".utf8), authenticated: false)
            guard let accessToken = response.accessToken ?? response.token, !accessToken.isEmpty else { throw ServiceError.missingToken }
            defaults.set(accessToken, forKey: "typetype.accessToken")
        }
        return instance
    }

    func trending(serviceID: Int = 0) async throws -> [TypeTypeVideo] {
        try await ensureToken()
        return try await request(path: "/api/trending", query: [URLQueryItem(name: "service", value: String(serviceID))], authenticated: true)
    }

    func search(query: String, serviceID: Int = 0, nextPage: String? = nil) async throws -> TypeTypeSearchPage {
        try await ensureToken()
        var items = [URLQueryItem(name: "q", value: query), URLQueryItem(name: "service", value: String(serviceID))]
        if let nextPage, !nextPage.isEmpty { items.append(URLQueryItem(name: "nextpage", value: nextPage)) }
        return try await request(path: "/api/search", query: items, authenticated: true)
    }

    func watchURL(for video: TypeTypeVideo) -> URL? {
        var components = URLComponents(url: Self.baseAddress, resolvingAgainstBaseURL: false)
        components?.path = "/watch"
        components?.queryItems = [URLQueryItem(name: "v", value: video.watchParameter)]
        return components?.url
    }

    private func ensureToken() async throws {
        if token?.isEmpty != false { _ = try await connect() }
    }

    private func request<T: Decodable>(path: String, method: String = "GET", query: [URLQueryItem] = [], body: Data? = nil, authenticated: Bool = true) async throws -> T {
        var components = URLComponents(url: Self.baseAddress, resolvingAgainstBaseURL: false)!
        components.path = path
        components.queryItems = query.isEmpty ? nil : query
        guard let url = components.url else { throw ServiceError.invalidAddress }
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.timeoutInterval = 30
        request.httpBody = body
        if body != nil { request.setValue("application/json", forHTTPHeaderField: "Content-Type") }
        if authenticated, let token { request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw ServiceError.badResponse(-1, "No HTTP response") }
        guard (200..<300).contains(http.statusCode) else {
            let detail = String(data: data.prefix(400), encoding: .utf8) ?? "Request failed"
            throw ServiceError.badResponse(http.statusCode, detail)
        }
        do { return try JSONDecoder().decode(T.self, from: data) }
        catch { throw ServiceError.badResponse(200, "The server response did not match the expected TypeType data format.") }
    }
}

enum TrapTubeDownloadPaths {
    static var appDirectory: URL {
        FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("TrapTube", isDirectory: true)
    }

    static var downloadsDirectory: URL {
        appDirectory.appendingPathComponent("Downloads", isDirectory: true)
    }
}

struct TrapTubeDownloadedMedia: Codable, Identifiable {
    let id: String
    let title: String
    let fileName: String
    let mode: String
    let sizeBytes: Int64
    let createdAt: Date

    var fileURL: URL {
        TrapTubeDownloadPaths.downloadsDirectory.appendingPathComponent(fileName)
    }
}

struct TrapTubeDownloadTask: Identifiable {
    let id: String
    var title: String
    var mode: String
    var status: String
    var stage: String
    var progress: Double
    var downloadedBytes: Int64
    var totalBytes: Int64
    var speedBytesPerSecond: Int64
    var error: String?
}

enum TrapTubeFFmpegOperation: String, CaseIterable, Identifiable {
    case remuxMP4
    case convertM4A
    case convertWAV
    case extractThumbnail

    var id: String { rawValue }
    var title: String {
        switch self {
        case .remuxMP4: return "Remux to MP4 (no re-encode)"
        case .convertM4A: return "Convert audio to M4A"
        case .convertWAV: return "Convert audio to WAV"
        case .extractThumbnail: return "Extract thumbnail"
        }
    }
}

enum TrapTubeFFmpegError: LocalizedError {
    case failed(String)
    case missingOutput

    var errorDescription: String? {
        switch self {
        case .failed(let details):
            return details.isEmpty ? "FFmpeg could not process this media file." : details
        case .missingOutput:
            return "FFmpeg finished without creating the expected output file."
        }
    }
}

private final class TrapTubeFFmpegCancellation: @unchecked Sendable {
    private let lock = NSLock()
    private var sessionID: Int64?
    private var cancelled = false

    func attach(_ id: Int64) {
        lock.lock(); sessionID = id; let shouldCancel = cancelled; lock.unlock()
        if shouldCancel { FFmpegKit.cancel(id) }
    }

    func cancel() {
        lock.lock(); cancelled = true; let id = sessionID; lock.unlock()
        if let id { FFmpegKit.cancel(id) }
    }
}

private final class TrapTubeTransferRateMeter: @unchecked Sendable {
    private let lock = NSLock()
    private var lastDate = Date()
    private var lastBytes: Int64 = 0

    func update(_ bytes: Int64) -> Int64 {
        lock.lock(); defer { lock.unlock() }
        let now = Date()
        let elapsed = max(0.1, now.timeIntervalSince(lastDate))
        let rate = Int64(Double(max(0, bytes - lastBytes)) / elapsed)
        lastDate = now; lastBytes = bytes
        return rate
    }
}

enum TrapTubeFFmpegProcessor {
    static func execute(_ arguments: [String],
                        progress: ((Int64, Double) -> Void)? = nil) async throws {
        let cancellation = TrapTubeFFmpegCancellation()
        try await withTaskCancellationHandler {
            try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
                let session = FFmpegKit.executeWithArgumentsAsync(
                    arguments,
                    withCompleteCallback: { session in
                        if ReturnCode.isSuccess(session.getReturnCode()) {
                            continuation.resume()
                        } else {
                            continuation.resume(throwing: TrapTubeFFmpegError.failed(session.getOutput()))
                        }
                    },
                    withLogCallback: nil,
                    withStatisticsCallback: { statistics in
                        progress?(Int64(statistics.getSize()), statistics.getSpeed())
                    }
                )
                cancellation.attach(session.getSessionId())
            }
        } onCancel: {
            cancellation.cancel()
        }
    }
}

@MainActor
final class TrapTubeDownloadManager: ObservableObject {
    static let shared = TrapTubeDownloadManager()
    @Published private(set) var jobs: [TrapTubeDownloadTask] = []
    @Published private(set) var completed: [TrapTubeDownloadedMedia] = []
    @Published var lastError: String?
    private let resolver = TrapTubeStreamResolver()
    private var workers: [String: Task<Void, Never>] = [:]
    private var manifestURL: URL { TrapTubeDownloadPaths.appDirectory.appendingPathComponent("downloads.json") }
    private var queueURL: URL { TrapTubeDownloadPaths.appDirectory.appendingPathComponent("queue.json") }

    private init() { restore() }

    func enqueue(videoURL: URL, title: String, mode: String, quality: String,
                 format: String, bitrate: Int?, height: Int?) async {
        lastError = nil
        do {
            let media = try await resolver.resolve(videoURL, title: title)
            let id = UUID().uuidString
            let chosenVideo = media.videoAssets.sorted { ($0.height ?? 0) < ($1.height ?? 0) }
                .last(where: { height == nil || ($0.height ?? 0) <= height! }) ?? media.videoAssets.last
            let chosenAudio = media.audioAssets.max(by: { ($0.bitrate ?? 0) < ($1.bitrate ?? 0) })
            let chosenMuxed = media.muxedAssets.sorted { ($0.height ?? 0) < ($1.height ?? 0) }
                .last(where: { height == nil || ($0.height ?? 0) <= height! }) ?? media.muxedAssets.last
            if mode == "audio" && chosenAudio == nil && chosenMuxed == nil { throw TrapTubeResolverError.noStreams }
            if mode != "audio" && chosenVideo == nil && chosenMuxed == nil { throw TrapTubeResolverError.noStreams }
            var job = TrapTubeDownloadTask(id: id, title: title, mode: mode, status: "queued", stage: "Streams resolved",
                progress: 0, downloadedBytes: 0, totalBytes: 0, speedBytesPerSecond: 0, error: nil,
                sourceURL: videoURL, selectedVideoURL: chosenVideo?.url, selectedAudioURL: chosenAudio?.url,
                partialFileName: nil, outputFileName: nil, resumeOffset: 0)
            if mode == "audio" { job.selectedVideoURL = nil }
            if chosenMuxed != nil { job.selectedVideoURL = chosenMuxed?.url; job.selectedAudioURL = nil }
            jobs.insert(job, at: 0)
            persistQueue()
            start(jobID: id, media: media, video: mode == "audio" ? nil : (chosenVideo ?? chosenMuxed),
                  audio: mode == "audio" ? (chosenAudio ?? chosenMuxed) : chosenAudio, format: format)
        } catch { lastError = error.localizedDescription }
    }

    private func start(jobID: String, media: TrapTubeResolvedMedia, video: TrapTubeFlatAsset?,
                       audio: TrapTubeFlatAsset?, format: String) {
        workers[jobID]?.cancel()
        workers[jobID] = Task { [weak self] in
            await self?.run(jobID: jobID, media: media, video: video, audio: audio, format: format)
        }
    }

    private func run(jobID: String, media: TrapTubeResolvedMedia, video: TrapTubeFlatAsset?,
                     audio: TrapTubeFlatAsset?, format: String) async {
        defer { workers[jobID] = nil }
        guard let index = jobs.firstIndex(where: { $0.id == jobID }) else { return }
        jobs[index].status = "running"; jobs[index].stage = "Downloading streams"; persistQueue()
        do {
            let dir = TrapTubeDownloadPaths.downloadsDirectory
            try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
            var inputURLs: [URL] = []
            let assets = [video, audio].compactMap { $0 }
            for (assetIndex, asset) in assets.enumerated() {
                let ext = asset.isManifest ? (asset.mimeType.contains("mpegurl") ? "m3u8" : "mpd") : (asset.url.pathExtension.isEmpty ? "media" : asset.url.pathExtension)
                let partialName = "\(jobID)-\(assetIndex).partial.\(ext)"
                let partialURL = dir.appendingPathComponent(partialName)
                let offset = (try? FileManager.default.attributesOfItem(atPath: partialURL.path)[.size] as? NSNumber)?.int64Value ?? 0
                jobs[index].partialFileName = partialName; jobs[index].resumeOffset = offset; persistQueue()
                if asset.isManifest {
                    // FFmpeg reads the exposed manifest directly so relative HLS segments,
                    // encryption keys, initialization maps and byte ranges remain valid.
                    inputURLs.append(asset.url)
                    continue
                }
                let downloaded = try await TrapTubeFlatTransfer.download(asset, to: partialURL, startingAt: offset) { [weak self] bytes, total, speed in
                    Task { @MainActor in
                        guard let self, let i = self.jobs.firstIndex(where: { $0.id == jobID }) else { return }
                        self.jobs[i].downloadedBytes = bytes
                        self.jobs[i].totalBytes = total
                        self.jobs[i].speedBytesPerSecond = speed
                        self.jobs[i].progress = total > 0 ? min(0.98, Double(bytes) / Double(total)) : 0
                        self.persistQueue()
                    }
                }
                inputURLs.append(downloaded)
            }
            guard let first = inputURLs.first else { throw TrapTubeResolverError.noStreams }
            let outputExt = format == "m4a" || modeFor(jobID) == "audio" ? (format == "wav" ? "wav" : "m4a") : "mp4"
            let outputName = "\(jobID).\(outputExt)"
            let outputURL = dir.appendingPathComponent(outputName)
            jobs[index].stage = "Muxing / finalizing"; persistQueue()
            let rateMeter = TrapTubeTransferRateMeter()
            let stats: (Int64, Double) -> Void = { [weak self] bytes, _ in
                let measuredSpeed = rateMeter.update(bytes)
                Task { @MainActor in
                    guard let self, let i = self.jobs.firstIndex(where: { $0.id == jobID }) else { return }
                    self.jobs[i].stage = "Receiving / muxing stream"
                    self.jobs[i].downloadedBytes = bytes
                    self.jobs[i].speedBytesPerSecond = measuredSpeed
                    self.jobs[i].progress = 0
                    self.persistQueue()
                }
            }
            if modeFor(jobID) == "audio" {
                try await TrapTubeMP4Box.extractAudio(input: first, output: outputURL, format: outputExt, progress: stats)
            } else {
                try await TrapTubeMP4Box.mux(video: first, audio: inputURLs.count > 1 ? inputURLs[1] : nil, output: outputURL, progress: stats)
            }
            let size = (try? FileManager.default.attributesOfItem(atPath: outputURL.path)[.size] as? NSNumber)?.int64Value ?? 0
            let item = TrapTubeDownloadedMedia(id: UUID().uuidString, title: media.title, fileName: outputName,
                mode: modeFor(jobID), sizeBytes: size, createdAt: Date())
            completed.insert(item, at: 0); persistCompleted()
            jobs[index].status = "saved"; jobs[index].stage = "Saved to device"; jobs[index].progress = 1
            jobs[index].outputFileName = outputName; jobs[index].speedBytesPerSecond = 0
            persistQueue()
        } catch is CancellationError {
            if let i = jobs.firstIndex(where: { $0.id == jobID }) { jobs[i].status = "paused"; jobs[i].stage = "Paused · can resume"; persistQueue() }
        } catch {
            if let i = jobs.firstIndex(where: { $0.id == jobID }) { jobs[i].status = "failed"; jobs[i].error = error.localizedDescription; persistQueue() }
        }
    }

    private func modeFor(_ id: String) -> String { jobs.first(where: { $0.id == id })?.mode ?? "video" }

    func cancel(_ id: String) async {
        workers[id]?.cancel(); workers[id] = nil
        if let i = jobs.firstIndex(where: { $0.id == id }) { jobs[i].status = "paused"; jobs[i].stage = "Paused · can resume"; persistQueue() }
    }

    func resume(_ id: String) {
        guard let job = jobs.first(where: { $0.id == id }), let source = job.sourceURL else { return }
        Task {
            do {
                let media = try await resolver.resolve(source, title: job.title)
                let selectedVideo = media.videoAssets.first(where: { $0.url == job.selectedVideoURL }) ?? media.muxedAssets.first(where: { $0.url == job.selectedVideoURL })
                let selectedAudio = media.audioAssets.first(where: { $0.url == job.selectedAudioURL })
                let video = job.mode == "audio" ? nil : selectedVideo
                let audio = job.mode == "audio"
                    ? (selectedAudio ?? media.muxedAssets.first(where: { $0.url == job.selectedVideoURL }))
                    : selectedAudio
                start(jobID: id, media: media, video: video, audio: audio, format: job.mode == "audio" ? "m4a" : "mp4")
            } catch { lastError = error.localizedDescription }
        }
    }

    func remove(_ item: TrapTubeDownloadedMedia) {
        try? FileManager.default.removeItem(at: item.fileURL)
        completed.removeAll { $0.id == item.id }; persistCompleted()
    }

    func process(_ item: TrapTubeDownloadedMedia, operation: TrapTubeFFmpegOperation) async throws {
        let ext = operation == .convertWAV ? "wav" : (operation == .extractThumbnail ? "jpg" : (operation == .convertM4A ? "m4a" : "mp4"))
        let name = "\(UUID().uuidString).\(ext)"
        let output = TrapTubeDownloadPaths.downloadsDirectory.appendingPathComponent(name)
        if operation == .convertM4A || operation == .convertWAV {
            try await TrapTubeMP4Box.extractAudio(input: item.fileURL, output: output, format: ext)
        } else {
            var args = ["-y", "-i", item.fileURL.path]
            args += operation == .extractThumbnail ? ["-frames:v","1","-q:v","2"] : ["-map","0","-c","copy","-movflags","+faststart"]
            args.append(output.path); try await TrapTubeFFmpegProcessor.execute(args)
        }
        let size = (try? FileManager.default.attributesOfItem(atPath: output.path)[.size] as? NSNumber)?.int64Value ?? 0
        completed.insert(TrapTubeDownloadedMedia(id: UUID().uuidString, title: "\(item.title) · \(operation.title)",
            fileName: name, mode: operation == .extractThumbnail ? "thumbnail" : (ext == "mp4" ? "video" : "audio"),
            sizeBytes: size, createdAt: Date()), at: 0)
        persistCompleted()
    }

    private func restore() {
        try? FileManager.default.createDirectory(at: TrapTubeDownloadPaths.appDirectory, withIntermediateDirectories: true)
        if let data = try? Data(contentsOf: manifestURL), let saved = try? JSONDecoder().decode([TrapTubeDownloadedMedia].self, from: data) {
            completed = saved.filter { FileManager.default.fileExists(atPath: $0.fileURL.path) }
        }
        if let data = try? Data(contentsOf: queueURL), let saved = try? JSONDecoder().decode([TrapTubeDownloadTask].self, from: data) {
            jobs = saved.map { job in var copy = job; if copy.status == "running" { copy.status = "paused"; copy.stage = "Paused · resume available" }; return copy }
        }
    }

    private func persistQueue() {
        do { try FileManager.default.createDirectory(at: TrapTubeDownloadPaths.appDirectory, withIntermediateDirectories: true)
            try JSONEncoder().encode(jobs).write(to: queueURL, options: .atomic) }
        catch { lastError = "Could not persist download queue: \(error.localizedDescription)" }
    }

    private func persistCompleted() {
        do { try FileManager.default.createDirectory(at: TrapTubeDownloadPaths.appDirectory, withIntermediateDirectories: true)
            try JSONEncoder().encode(completed).write(to: manifestURL, options: .atomic) }
        catch { lastError = "Could not save downloads: \(error.localizedDescription)" }
    }
}

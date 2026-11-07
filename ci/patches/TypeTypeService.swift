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

    func createDownloadJob(videoURL: URL, options: TypeTypeDownloadOptions) async throws -> TypeTypeCreateDownloadResponse {
        try await ensureToken()
        let payload = TypeTypeCreateDownloadRequest(url: videoURL.absoluteString, options: options)
        let body = try JSONEncoder().encode(payload)
        return try await request(path: "/api/downloader/jobs", method: "POST", body: body, authenticated: true)
    }

    func fetchDownloadJob(id: String) async throws -> TypeTypeDownloadJob {
        try await ensureToken()
        let safeID = id.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? id
        return try await request(path: "/api/downloader/jobs/\(safeID)", authenticated: true)
    }

    func cancelDownloadJob(id: String) async throws {
        try await ensureToken()
        let safeID = id.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? id
        let _: TypeTypeCancelDownloadResponse = try await request(
            path: "/api/downloader/jobs/\(safeID)/cancel",
            method: "POST",
            authenticated: true
        )
    }

    func downloadArtifact(id: String, fallbackTitle: String) async throws -> URL {
        try await ensureToken()
        let safeID = id.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? id
        var components = URLComponents(url: Self.baseAddress, resolvingAgainstBaseURL: false)!
        components.path = "/api/downloader/jobs/\(safeID)/artifact"
        components.queryItems = [URLQueryItem(name: "download", value: "1")]
        guard let url = components.url else { throw ServiceError.invalidAddress }
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.timeoutInterval = 180
        if let token { request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }

        let (temporaryURL, response) = try await URLSession.shared.download(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw ServiceError.badResponse(-1, "No artifact response was received.")
        }
        guard (200..<300).contains(http.statusCode) else {
            let detail = try? String(contentsOf: temporaryURL, encoding: .utf8)
            throw ServiceError.badResponse(http.statusCode, detail ?? "The download artifact could not be retrieved.")
        }

        let directory = LibraryStore.appDirectory.appendingPathComponent("Downloads", isDirectory: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let proposed = http.suggestedFilename ?? "\(fallbackTitle).\(http.mimeType?.contains("audio") == true ? "m4a" : "mp4")"
        let safeName = proposed
            .replacingOccurrences(of: "/", with: "_")
            .replacingOccurrences(of: ":", with: "_")
            .trimmingCharacters(in: .whitespacesAndNewlines)
        let destination = directory.appendingPathComponent(safeName.isEmpty ? "\(UUID().uuidString).bin" : safeName)
        if FileManager.default.fileExists(atPath: destination.path) {
            try FileManager.default.removeItem(at: destination)
        }
        try FileManager.default.moveItem(at: temporaryURL, to: destination)
        return destination
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

struct TypeTypeCreateDownloadRequest: Encodable {
    let url: String
    let options: TypeTypeDownloadOptions
}

struct TypeTypeCreateDownloadResponse: Decodable {
    let id: String
    let cached: Bool?
}

private struct TypeTypeCancelDownloadResponse: Decodable {
    let status: String?
}

struct TypeTypeDownloadOptions: Encodable {
    var mode: String
    var quality: String?
    var format: String?
    var bitrate: Int?
    var height: Int?
    var allowQualityFallback: Bool = true
    var sponsorBlock: Bool = false
    var sponsorBlockCategories: [String]? = nil
    var thumbnailOnly: Bool? = nil
    var subtitles: TypeTypeSubtitleOptions? = nil
}

struct TypeTypeSubtitleOptions: Encodable {
    var enabled: Bool
    var auto: Bool
    var embed: Bool
    var languages: [String]
    var format: String
}

struct TypeTypeDownloadJob: Decodable, Identifiable {
    struct Resolved: Decodable {
        let videoItag: String?
        let audioItag: String?
        let height: Int?
        let fps: Int?
        let videoCodec: String?
        let audioCodec: String?
        let container: String?
        let bitrate: Int?
        let fileName: String?
    }

    let id: String
    let url: String
    let status: String
    let title: String?
    let resolved: Resolved?
    let progressPercent: Int?
    let downloadedBytes: Int64?
    let totalBytes: Int64?
    let speedBytesPerSecond: Int64?
    let etaSeconds: Int?
    let stage: String?
    let errorCode: String?
    let error: String?
}

struct TrapTubeDownloadedMedia: Codable, Identifiable {
    let id: String
    let title: String
    let fileName: String
    let mode: String
    let sizeBytes: Int64
    let createdAt: Date

    var fileURL: URL {
        LibraryStore.appDirectory
            .appendingPathComponent("Downloads", isDirectory: true)
            .appendingPathComponent(fileName)
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

enum TrapTubeFFmpegProcessor {
    static func execute(_ arguments: [String]) async throws {
        try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
            FFmpegKit.executeWithArgumentsAsync(arguments, withCompleteCallback: { session in
                if ReturnCode.isSuccess(session.getReturnCode()) {
                    continuation.resume()
                } else {
                    continuation.resume(throwing: TrapTubeFFmpegError.failed(session.getOutput()))
                }
            })
        }
    }
}

@MainActor
final class TrapTubeDownloadManager: ObservableObject {
    static let shared = TrapTubeDownloadManager()

    @Published private(set) var jobs: [TrapTubeDownloadTask] = []
    @Published private(set) var completed: [TrapTubeDownloadedMedia] = []
    @Published var lastError: String?

    private let service = TypeTypeService()
    private var monitorTasks: [String: Task<Void, Never>] = [:]
    private var isRestored = false

    private var downloadsDirectory: URL {
        LibraryStore.appDirectory.appendingPathComponent("Downloads", isDirectory: true)
    }

    private var manifestURL: URL {
        LibraryStore.appDirectory.appendingPathComponent("downloads.json")
    }

    private init() { restoreCompleted() }

    func enqueue(
        videoURL: URL,
        title: String,
        mode: String,
        quality: String,
        format: String,
        bitrate: Int?,
        height: Int?,
        sponsorBlock: Bool,
        subtitles: Bool
    ) async {
        lastError = nil
        do {
            var options = TypeTypeDownloadOptions(
                mode: mode,
                quality: quality,
                format: format,
                bitrate: bitrate,
                height: height,
                allowQualityFallback: true,
                sponsorBlock: sponsorBlock,
                sponsorBlockCategories: sponsorBlock
                    ? ["sponsor", "selfpromo", "interaction", "intro", "outro", "preview", "filler", "music_offtopic"]
                    : nil,
                thumbnailOnly: mode == "thumbnail" ? true : nil,
                subtitles: subtitles && mode == "video"
                    ? TypeTypeSubtitleOptions(enabled: true, auto: true, embed: true, languages: ["en"], format: "srt")
                    : nil
            )
            if mode == "thumbnail" {
                options.quality = nil
                options.format = format.isEmpty ? "jpg" : format
            }

            let remote = try await service.createDownloadJob(videoURL: videoURL, options: options)
            let initial = TrapTubeDownloadTask(
                id: remote.id,
                title: title,
                mode: mode,
                status: "queued",
                stage: remote.cached == true ? "cached result queued" : "queued",
                progress: 0,
                downloadedBytes: 0,
                totalBytes: 0,
                speedBytesPerSecond: 0,
                error: nil
            )
            jobs.insert(initial, at: 0)
            monitorTasks[remote.id] = Task { [weak self] in
                await self?.monitor(jobID: remote.id, fallbackTitle: title, mode: mode)
            }
        } catch {
            lastError = error.localizedDescription
        }
    }

    func cancel(_ id: String) async {
        monitorTasks[id]?.cancel()
        monitorTasks[id] = nil
        do {
            try await service.cancelDownloadJob(id: id)
            updateJob(id) { $0.status = "cancelled"; $0.stage = "cancelled" }
        } catch {
            lastError = error.localizedDescription
        }
    }

    func remove(_ item: TrapTubeDownloadedMedia) {
        try? FileManager.default.removeItem(at: item.fileURL)
        completed.removeAll { $0.id == item.id }
        persistCompleted()
    }

    func process(_ item: TrapTubeDownloadedMedia, operation: TrapTubeFFmpegOperation) async throws {
        let source = item.fileURL
        guard FileManager.default.fileExists(atPath: source.path) else {
            throw CocoaError(.fileNoSuchFile)
        }

        let extensionName: String
        switch operation {
        case .remuxMP4: extensionName = "mp4"
        case .convertM4A: extensionName = "m4a"
        case .convertWAV: extensionName = "wav"
        case .extractThumbnail: extensionName = "jpg"
        }
        let outputName = "\(source.deletingPathExtension().lastPathComponent)-\(operation.rawValue)-\(UUID().uuidString.prefix(6)).\(extensionName)"
        let output = downloadsDirectory.appendingPathComponent(outputName)
        var arguments = ["-y", "-i", source.path]
        switch operation {
        case .remuxMP4:
            arguments += ["-map", "0", "-c", "copy", "-movflags", "+faststart"]
        case .convertM4A:
            arguments += ["-vn", "-c:a", "aac", "-b:a", "256k"]
        case .convertWAV:
            arguments += ["-vn", "-c:a", "pcm_s16le"]
        case .extractThumbnail:
            arguments += ["-frames:v", "1", "-q:v", "2"]
        }
        arguments.append(output.path)

        try await TrapTubeFFmpegProcessor.execute(arguments)
        guard FileManager.default.fileExists(atPath: output.path),
              let attributes = try? FileManager.default.attributesOfItem(atPath: output.path),
              let size = (attributes[.size] as? NSNumber)?.int64Value,
              size > 0 else {
            throw TrapTubeFFmpegError.missingOutput
        }

        let outputMode: String
        switch operation {
        case .remuxMP4: outputMode = "video"
        case .convertM4A, .convertWAV: outputMode = "audio"
        case .extractThumbnail: outputMode = "thumbnail"
        }
        let processed = TrapTubeDownloadedMedia(
            id: UUID().uuidString,
            title: "\(item.title) · \(operation.title)",
            fileName: outputName,
            mode: outputMode,
            sizeBytes: size,
            createdAt: Date()
        )
        completed.insert(processed, at: 0)
        persistCompleted()
    }

    private func monitor(jobID: String, fallbackTitle: String, mode: String) async {
        defer { monitorTasks[jobID] = nil }
        do {
            for _ in 0..<600 {
                if Task.isCancelled { return }
                let remote = try await service.fetchDownloadJob(id: jobID)
                updateJob(jobID) {
                    $0.title = remote.title ?? $0.title
                    $0.status = remote.status
                    $0.stage = remote.stage ?? remote.status
                    $0.progress = min(1, max(0, Double(remote.progressPercent ?? 0) / 100))
                    $0.downloadedBytes = remote.downloadedBytes ?? $0.downloadedBytes
                    $0.totalBytes = remote.totalBytes ?? $0.totalBytes
                    $0.speedBytesPerSecond = remote.speedBytesPerSecond ?? $0.speedBytesPerSecond
                    $0.error = remote.error
                }

                if remote.status == "failed" {
                    updateJob(jobID) { $0.error = remote.error ?? "The TypeType downloader reported a failure." }
                    return
                }

                if remote.status == "done" {
                    updateJob(jobID) { $0.stage = "Saving to device"; $0.progress = 1 }
                    let fileURL = try await service.downloadArtifact(id: jobID, fallbackTitle: remote.title ?? fallbackTitle)
                    let attributes = try FileManager.default.attributesOfItem(atPath: fileURL.path)
                    let size = (attributes[.size] as? NSNumber)?.int64Value ?? 0
                    let item = TrapTubeDownloadedMedia(
                        id: UUID().uuidString,
                        title: remote.title ?? fallbackTitle,
                        fileName: fileURL.lastPathComponent,
                        mode: mode,
                        sizeBytes: size,
                        createdAt: Date()
                    )
                    completed.insert(item, at: 0)
                    persistCompleted()
                    updateJob(jobID) { $0.status = "saved"; $0.stage = "Saved to device"; $0.progress = 1 }
                    return
                }

                try await Task.sleep(nanoseconds: 1_500_000_000)
            }
            updateJob(jobID) { $0.status = "failed"; $0.error = "The download timed out while waiting for the server." }
        } catch {
            if !Task.isCancelled {
                updateJob(jobID) { $0.status = "failed"; $0.error = error.localizedDescription }
            }
        }
    }

    private func updateJob(_ id: String, _ change: (inout TrapTubeDownloadTask) -> Void) {
        guard let index = jobs.firstIndex(where: { $0.id == id }) else { return }
        change(&jobs[index])
    }

    private func restoreCompleted() {
        guard !isRestored else { return }
        isRestored = true
        guard let data = try? Data(contentsOf: manifestURL),
              let saved = try? JSONDecoder().decode([TrapTubeDownloadedMedia].self, from: data) else { return }
        completed = saved.filter { FileManager.default.fileExists(atPath: $0.fileURL.path) }
    }

    private func persistCompleted() {
        do {
            try FileManager.default.createDirectory(at: LibraryStore.appDirectory, withIntermediateDirectories: true)
            let data = try JSONEncoder().encode(completed)
            try data.write(to: manifestURL, options: .atomic)
        } catch {
            lastError = "Could not save the downloads list: \(error.localizedDescription)"
        }
    }
}
    func createDownloadJob(videoURL: URL, options: TypeTypeDownloadOptions) async throws -> TypeTypeDownloadJob {
        try await ensureToken()
        let payload = TypeTypeCreateDownloadRequest(url: videoURL.absoluteString, options: options)
        let body = try JSONEncoder().encode(payload)
        return try await request(path: "/api/downloader/jobs", method: "POST", body: body, authenticated: true)
    }

    func fetchDownloadJob(id: String) async throws -> TypeTypeDownloadJob {
        try await ensureToken()
        let safeID = id.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? id
        return try await request(path: "/api/downloader/jobs/\(safeID)", authenticated: true)
    }

    func cancelDownloadJob(id: String) async throws -> TypeTypeDownloadJob {
        try await ensureToken()
        let safeID = id.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? id
        return try await request(path: "/api/downloader/jobs/\(safeID)/cancel", method: "POST", authenticated: true)
    }

    func downloadArtifact(id: String, fallbackTitle: String) async throws -> URL {
        try await ensureToken()
        let safeID = id.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? id
        var components = URLComponents(url: Self.baseAddress, resolvingAgainstBaseURL: false)!
        components.path = "/api/downloader/jobs/\(safeID)/artifact"
        components.queryItems = [URLQueryItem(name: "download", value: "1")]
        guard let url = components.url else { throw ServiceError.invalidAddress }
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.timeoutInterval = 180
        if let token { request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }

        let (temporaryURL, response) = try await URLSession.shared.download(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw ServiceError.badResponse(-1, "No artifact response was received.")
        }
        guard (200..<300).contains(http.statusCode) else {
            let detail = try? String(contentsOf: temporaryURL, encoding: .utf8)
            throw ServiceError.badResponse(http.statusCode, detail ?? "The download artifact could not be retrieved.")
        }

        let directory = LibraryStore.appDirectory.appendingPathComponent("Downloads", isDirectory: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let proposed = http.suggestedFilename ?? "\(fallbackTitle).\(http.mimeType?.contains("audio") == true ? "m4a" : "mp4")"
        let safeName = proposed
            .replacingOccurrences(of: "/", with: "_")
            .replacingOccurrences(of: ":", with: "_")
            .trimmingCharacters(in: .whitespacesAndNewlines)
        let destination = directory.appendingPathComponent(safeName.isEmpty ? "\(UUID().uuidString).bin" : safeName)
        if FileManager.default.fileExists(atPath: destination.path) {
            try FileManager.default.removeItem(at: destination)
        }
        try FileManager.default.moveItem(at: temporaryURL, to: destination)
        return destination
    }


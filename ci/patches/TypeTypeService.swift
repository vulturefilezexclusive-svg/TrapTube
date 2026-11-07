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

        let directory = TrapTubeDownloadPaths.downloadsDirectory
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

enum TrapTubeFFmpegProcessor {
    static func execute(_ arguments: [String]) async throws {
        try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
            _ = FFmpegKit.executeWithArgumentsAsync(arguments, withCompleteCallback: { session in
                if ReturnCode.isSuccess(session.getReturnCode()) {
                    continuation.resume()
                } else {
                    continuation.resume(throwing: TrapTubeFFmpegError.failed(session.getOutput()))
                }
            })
        }
    }
}

enum TrapTubeAssetKind: String, Codable { case video, audio, muxed }

struct TrapTubeFlatAsset: Codable, Identifiable, Hashable {
    var id: String { url.absoluteString + "|" + kind.rawValue }
    let url: URL
    let kind: TrapTubeAssetKind
    let mimeType: String
    let height: Int?
    let bitrate: Int?
    let label: String
    let isManifest: Bool
    let headers: [String: String]
}

struct TrapTubeResolvedMedia: Codable {
    let title: String
    let sourceURL: URL
    let videoAssets: [TrapTubeFlatAsset]
    let audioAssets: [TrapTubeFlatAsset]
    let muxedAssets: [TrapTubeFlatAsset]
    let supportsSeparateAudioVideo: Bool
}

enum TrapTubeResolverError: LocalizedError {
    case unsupportedSite, noStreams, unsupportedManifest(String), badResponse
    var errorDescription: String? {
        switch self {
        case .unsupportedSite: return "This website needs a dedicated TrapTube provider adapter. No compatible stream metadata was exposed."
        case .noStreams: return "No downloadable media streams were exposed by this URL."
        case .unsupportedManifest(let detail): return detail
        case .badResponse: return "The media source returned an invalid response."
        }
    }
}

/// Provider adapters can be added without changing the transfer or muxing layers.
/// This default adapter deliberately resolves only direct media and exposed HLS/DASH manifests.
struct TrapTubeStreamResolver {
    func resolve(_ source: URL, title: String) async throws -> TrapTubeResolvedMedia {
        guard let scheme = source.scheme?.lowercased(), ["http", "https"].contains(scheme), source.host != nil else {
            throw TrapTubeResolverError.unsupportedSite
        }
        var request = URLRequest(url: source)
        request.httpMethod = "GET"
        request.timeoutInterval = 25
        request.setValue("TrapTube/1.0", forHTTPHeaderField: "User-Agent")
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse, (200..<400).contains(http.statusCode) else {
            throw TrapTubeResolverError.badResponse
        }
        let mime = (http.mimeType ?? "").lowercased()
        let ext = source.pathExtension.lowercased()
        if ext == "m3u8" || mime.contains("mpegurl") {
            return try parseHLS(data: data, source: source, title: title)
        }
        if ext == "mpd" || mime.contains("dash+xml") {
            return try parseDASH(data: data, source: source, title: title)
        }
        if mime.hasPrefix("video/") || mime.hasPrefix("audio/") ||
            ["mp4","m4v","mov","webm","m4a","mp3","aac","wav","flac"].contains(ext) {
            let kind: TrapTubeAssetKind = mime.hasPrefix("audio/") || ["m4a","mp3","aac","wav","flac"].contains(ext) ? .audio : .muxed
            let asset = TrapTubeFlatAsset(url: source, kind: kind, mimeType: mime, height: nil,
                bitrate: nil, label: kind == .audio ? "Original audio" : "Original media",
                isManifest: false, headers: [:])
            return TrapTubeResolvedMedia(title: title, sourceURL: source,
                videoAssets: [], audioAssets: kind == .audio ? [asset] : [],
                muxedAssets: kind == .muxed ? [asset] : [], supportsSeparateAudioVideo: false)
        }
        throw TrapTubeResolverError.unsupportedSite
    }

    private func parseHLS(data: Data, source: URL, title: String) throws -> TrapTubeResolvedMedia {
        guard let text = String(data: data, encoding: .utf8), text.contains("#EXTM3U") else { throw TrapTubeResolverError.badResponse }
        let lines = text.components(separatedBy: .newlines).map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
        var videos: [TrapTubeFlatAsset] = []
        var audios: [TrapTubeFlatAsset] = []
        var muxed: [TrapTubeFlatAsset] = []
        var pendingHeight: Int?
        var pendingBandwidth: Int?
        var audioGroup: String?
        var audioGroups: [String: URL] = [:]
        for line in lines where !line.isEmpty {
            if line.hasPrefix("#EXT-X-MEDIA:") && line.contains("TYPE=AUDIO") {
                let attrs = parseAttributes(String(line.dropFirst("#EXT-X-MEDIA:".count)))
                if let group = attrs["GROUP-ID"], let uri = attrs["URI"], let url = URL(string: uri, relativeTo: source)?.absoluteURL {
                    audioGroups[group] = url
                }
            } else if line.hasPrefix("#EXT-X-STREAM-INF:") {
                let attrs = parseAttributes(String(line.dropFirst("#EXT-X-STREAM-INF:".count)))
                pendingBandwidth = Int(attrs["BANDWIDTH"] ?? "")
                if let resolution = attrs["RESOLUTION"], let h = Int(resolution.split(separator: "x").last ?? "") { pendingHeight = h }
                audioGroup = attrs["AUDIO"]
            } else if !line.hasPrefix("#"), let url = URL(string: line, relativeTo: source)?.absoluteURL {
                if pendingHeight != nil || pendingBandwidth != nil {
                    videos.append(TrapTubeFlatAsset(url: url, kind: .video, mimeType: "application/vnd.apple.mpegurl",
                        height: pendingHeight, bitrate: pendingBandwidth, label: pendingHeight.map { "\($0)p" } ?? "Video stream",
                        isManifest: true, headers: [:]))
                    if let group = audioGroup, let audioURL = audioGroups[group] {
                        audios.append(TrapTubeFlatAsset(url: audioURL, kind: .audio, mimeType: "application/vnd.apple.mpegurl",
                            height: nil, bitrate: nil, label: "Audio", isManifest: true, headers: [:]))
                    }
                    pendingHeight = nil; pendingBandwidth = nil; audioGroup = nil
                } else {
                    muxed.append(TrapTubeFlatAsset(url: url, kind: .muxed, mimeType: "application/vnd.apple.mpegurl",
                        height: nil, bitrate: nil, label: "HLS stream", isManifest: true, headers: [:]))
                }
            }
        }
        guard !videos.isEmpty || !muxed.isEmpty else {
            let asset = TrapTubeFlatAsset(url: source, kind: .muxed, mimeType: "application/vnd.apple.mpegurl",
                height: nil, bitrate: nil, label: "HLS stream", isManifest: true, headers: [:])
            muxed = [asset]
        }
        return TrapTubeResolvedMedia(title: title, sourceURL: source, videoAssets: videos,
            audioAssets: audios, muxedAssets: muxed, supportsSeparateAudioVideo: !videos.isEmpty && !audios.isEmpty)
    }

    private func parseDASH(data: Data, source: URL, title: String) throws -> TrapTubeResolvedMedia {
        guard let xml = String(data: data, encoding: .utf8), xml.contains("<MPD") else { throw TrapTubeResolverError.badResponse }
        // Resolve explicit BaseURL representations. SegmentTemplate/SegmentTimeline streams
        // require a site-specific adapter and are intentionally not guessed.
        let blocks = xml.components(separatedBy: "<Representation").dropFirst()
        var video: [TrapTubeFlatAsset] = [], audio: [TrapTubeFlatAsset] = [], muxed: [TrapTubeFlatAsset] = []
        for block in blocks {
            guard let end = block.range(of: "</Representation>") else { continue }
            let segment = String(block[..<end.lowerBound])
            guard let tagEnd = segment.firstIndex(of: ">") else { continue }
            let attrs = parseAttributes(String(segment[..<tagEnd]))
            guard let baseRange = segment.range(of: "<BaseURL>"),
                  let baseEnd = segment.range(of: "</BaseURL>") else { continue }
            let base = String(segment[baseRange.upperBound..<baseEnd.lowerBound]).trimmingCharacters(in: .whitespacesAndNewlines)
            guard let url = URL(string: base, relativeTo: source)?.absoluteURL else { continue }
            let type = (attrs["mimeType"] ?? attrs["contentType"] ?? "").lowercased()
            let h = Int(attrs["height"] ?? "")
            let rate = Int(attrs["bandwidth"] ?? "")
            let kind: TrapTubeAssetKind = type.contains("audio") ? .audio : (type.contains("video") ? .video : .muxed)
            let asset = TrapTubeFlatAsset(url: url, kind: kind, mimeType: type, height: h, bitrate: rate,
                label: h.map { "\($0)p" } ?? (kind == .audio ? "Audio" : "DASH media"),
                isManifest: false, headers: [:])
            switch kind { case .video: video.append(asset); case .audio: audio.append(asset); case .muxed: muxed.append(asset) }
        }
        guard !video.isEmpty || !audio.isEmpty || !muxed.isEmpty else {
            throw TrapTubeResolverError.unsupportedManifest("This DASH manifest uses segment templates rather than direct BaseURL assets. A provider adapter is required.")
        }
        return TrapTubeResolvedMedia(title: title, sourceURL: source, videoAssets: video, audioAssets: audio,
            muxedAssets: muxed, supportsSeparateAudioVideo: !video.isEmpty && !audio.isEmpty)
    }

    private func parseAttributes(_ value: String) -> [String: String] {
        var result: [String: String] = [:]
        let pattern = #"([A-Z0-9-]+)=("[^"]*"|[^,]*)"#
        guard let regex = try? NSRegularExpression(pattern: pattern) else { return result }
        let ns = value as NSString
        for match in regex.matches(in: value, range: NSRange(location: 0, length: ns.length)) where match.numberOfRanges > 2 {
            let key = ns.substring(with: match.range(at: 1))
            let raw = ns.substring(with: match.range(at: 2))
            result[key] = raw.trimmingCharacters(in: CharacterSet(charactersIn: "\""))
        }
        return result
    }
}

struct TrapTubeDownloadTask: Codable, Identifiable {
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
    var sourceURL: URL?
    var selectedVideoURL: URL?
    var selectedAudioURL: URL?
    var partialFileName: String?
    var outputFileName: String?
    var resumeOffset: Int64
}

enum TrapTubeFlatTransferError: LocalizedError {
    case serverDoesNotSupportResume, invalidStatus(Int)
    var errorDescription: String? {
        switch self {
        case .serverDoesNotSupportResume: return "The server does not support byte-range resume; restart the transfer to continue."
        case .invalidStatus(let code): return "Media transfer failed with HTTP \(code)."
        }
    }
}

enum TrapTubeFlatTransfer {
    /// Downloads to a stable partial file. If interrupted, the next run resumes with Range.
    static func download(_ asset: TrapTubeFlatAsset, to destination: URL,
                         startingAt offset: Int64 = 0,
                         progress: @escaping (Int64, Int64, Int64) -> Void) async throws -> URL {
        var request = URLRequest(url: asset.url)
        request.timeoutInterval = 180
        request.setValue("TrapTube/1.0", forHTTPHeaderField: "User-Agent")
        for (key, value) in asset.headers { request.setValue(value, forHTTPHeaderField: key) }
        if offset > 0 { request.setValue("bytes=\(offset)-", forHTTPHeaderField: "Range") }
        let (bytes, response) = try await URLSession.shared.bytes(for: request)
        guard let http = response as? HTTPURLResponse else { throw TrapTubeResolverError.badResponse }
        if offset > 0 && http.statusCode == 200 { throw TrapTubeFlatTransferError.serverDoesNotSupportResume }
        guard http.statusCode == 200 || http.statusCode == 206 else { throw TrapTubeFlatTransferError.invalidStatus(http.statusCode) }
        let total = Int64(http.expectedContentLength) > 0 ? Int64(http.expectedContentLength) + offset : 0
        try FileManager.default.createDirectory(at: destination.deletingLastPathComponent(), withIntermediateDirectories: true)
        if !FileManager.default.fileExists(atPath: destination.path) { FileManager.default.createFile(atPath: destination.path, contents: nil) }
        let handle = try FileHandle(forWritingTo: destination)
        if offset == 0 { try handle.truncate(atOffset: 0) } else { try handle.seekToEnd() }
        var received: Int64 = 0
        var windowBytes: Int64 = 0
        var windowStart = Date()
        do {
            for try await byte in bytes {
                try Task.checkCancellation()
                try handle.write(contentsOf: Data([byte]))
                received += 1; windowBytes += 1
                if received % 262144 == 0 {
                    let elapsed = max(0.1, Date().timeIntervalSince(windowStart))
                    progress(offset + received, total, Int64(Double(windowBytes) / elapsed))
                    windowBytes = 0; windowStart = Date()
                }
            }
            try handle.close()
        } catch {
            try? handle.close()
            throw error
        }
        progress(offset + received, total, 0)
        return destination
    }
}

enum TrapTubeMP4Box {
    static func mux(video: URL, audio: URL?, output: URL) async throws {
        var args = ["-y", "-i", video.path]
        if let audio { args += ["-i", audio.path] }
        args += audio == nil
            ? ["-map", "0:v?", "-map", "0:a?", "-c", "copy", "-movflags", "+faststart", output.path]
            : ["-map", "0:v:0", "-map", "1:a:0", "-c", "copy", "-movflags", "+faststart", output.path]
        try await TrapTubeFFmpegProcessor.execute(args)
        guard FileManager.default.fileExists(atPath: output.path) else { throw TrapTubeFFmpegError.missingOutput }
    }

    static func extractAudio(input: URL, output: URL, format: String) async throws {
        let codec = format == "wav" ? "pcm_s16le" : "aac"
        try await TrapTubeFFmpegProcessor.execute(["-y", "-i", input.path, "-vn", "-c:a", codec, output.path])
        guard FileManager.default.fileExists(atPath: output.path) else { throw TrapTubeFFmpegError.missingOutput }
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
            if modeFor(jobID) == "audio" {
                try await TrapTubeMP4Box.extractAudio(input: first, output: outputURL, format: outputExt)
            } else {
                try await TrapTubeMP4Box.mux(video: first, audio: inputURLs.count > 1 ? inputURLs[1] : nil, output: outputURL)
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
                let video = media.videoAssets.first(where: { $0.url == job.selectedVideoURL }) ?? media.muxedAssets.first(where: { $0.url == job.selectedVideoURL })
                let audio = media.audioAssets.first(where: { $0.url == job.selectedAudioURL })
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

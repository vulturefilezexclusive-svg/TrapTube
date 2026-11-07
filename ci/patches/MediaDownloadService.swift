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
    let representationID: String? = nil
    let streamIndex: Int? = nil
}

struct TrapTubeResolvedMedia: Codable {
    let title: String
    let sourceURL: URL
    let videoAssets: [TrapTubeFlatAsset]
    let audioAssets: [TrapTubeFlatAsset]
    let muxedAssets: [TrapTubeFlatAsset]
    let supportsSeparateAudioVideo: Bool
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

protocol TrapTubeStreamProviderAdapter {
    func canResolve(_ source: URL) -> Bool
    func resolve(_ source: URL, title: String) async throws -> TrapTubeResolvedMedia
}

struct TrapTubeStreamResolver {
    private let adapters: [any TrapTubeStreamProviderAdapter]
    init(adapters: [any TrapTubeStreamProviderAdapter] = [TrapTubeYouTubeAdapter()]) { self.adapters = adapters }

    func resolve(_ source: URL, title: String) async throws -> TrapTubeResolvedMedia {
        if let adapter = adapters.first(where: { $0.canResolve(source) }) {
            return try await adapter.resolve(source, title: title)
        }
        guard let scheme = source.scheme?.lowercased(), ["http", "https"].contains(scheme), source.host != nil else {
            throw TrapTubeResolverError.unsupportedSite
        }
        let ext = source.pathExtension.lowercased()
        var head = URLRequest(url: source)
        head.httpMethod = "HEAD"; head.timeoutInterval = 20
        head.setValue("TrapTube/1.0", forHTTPHeaderField: "User-Agent")
        let headResponse = try? await URLSession.shared.data(for: head)
        let http = headResponse?.1 as? HTTPURLResponse
        let mime = (http?.mimeType ?? "").lowercased()
        if mime.hasPrefix("video/") || mime.hasPrefix("audio/") ||
            ["mp4","m4v","mov","webm","m4a","mp3","aac","wav","flac"].contains(ext) {
            let kind: TrapTubeAssetKind = mime.hasPrefix("audio/") || ["m4a","mp3","aac","wav","flac"].contains(ext) ? .audio : .muxed
            let asset = TrapTubeFlatAsset(url: source, kind: kind, mimeType: mime, height: nil, bitrate: nil,
                label: kind == .audio ? "Original audio" : "Original media", isManifest: false, headers: [:])
            return TrapTubeResolvedMedia(title: title, sourceURL: source, videoAssets: [],
                audioAssets: kind == .audio ? [asset] : [], muxedAssets: kind == .muxed ? [asset] : [],
                supportsSeparateAudioVideo: false)
        }
        let isHLS = ext == "m3u8" || mime.contains("mpegurl")
        let isDASH = ext == "mpd" || mime.contains("dash+xml")
        var request = URLRequest(url: source)
        request.httpMethod = "GET"; request.timeoutInterval = 25
        request.setValue("TrapTube/1.0", forHTTPHeaderField: "User-Agent")
        if !isHLS && !isDASH && mime.contains("text/html") {
            request.setValue("bytes=0-1048575", forHTTPHeaderField: "Range")
        } else if !isHLS && !isDASH {
            throw TrapTubeResolverError.unsupportedSite
        }
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let manifestResponse = response as? HTTPURLResponse,
              (200..<400).contains(manifestResponse.statusCode) else { throw TrapTubeResolverError.badResponse }
        if isHLS { return try parseHLS(data: data, source: source, title: title) }
        if isDASH { return try parseDASH(data: data, source: source, title: title) }
        if let candidate = htmlMediaCandidates(data: data, baseURL: source).first {
            return try await resolve(candidate, title: title)
        }
        throw TrapTubeResolverError.unsupportedSite
    }

    private func htmlMediaCandidates(data: Data, baseURL: URL) -> [URL] {
        guard let html = String(data: data, encoding: .utf8) else { return [] }
        let patterns = [
            #"<(?:video|source)[^>]+src=["']([^"']+)["']"#,
            #"(?:src|href)=["']([^"']+\.(?:m3u8|mpd|mp4|m4v|webm|m4a|mp3|aac)(?:\?[^"']*)?)["']"#
        ]
        var candidates: [URL] = []
        for pattern in patterns {
            guard let regex = try? NSRegularExpression(pattern: pattern, options: [.caseInsensitive]) else { continue }
            let ns = html as NSString
            for match in regex.matches(in: html, range: NSRange(location: 0, length: ns.length)) where match.numberOfRanges > 1 {
                let raw = ns.substring(with: match.range(at: 1)).replacingOccurrences(of: "&amp;", with: "&")
                if let url = URL(string: raw, relativeTo: baseURL)?.absoluteURL,
                   ["http", "https"].contains(url.scheme?.lowercased() ?? "") {
                    candidates.append(url)
                }
            }
        }
        var seen = Set<String>()
        return candidates.filter { seen.insert($0.absoluteString).inserted }
    }

    private func parseHLS(data: Data, source: URL, title: String) throws -> TrapTubeResolvedMedia {
        guard let text = String(data: data, encoding: .utf8), text.contains("#EXTM3U") else {
            throw TrapTubeResolverError.badResponse
        }
        let lines = text.components(separatedBy: .newlines).map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
        let isMasterPlaylist = text.contains("#EXT-X-STREAM-INF")
        var videos: [TrapTubeFlatAsset] = [], audios: [TrapTubeFlatAsset] = [], muxed: [TrapTubeFlatAsset] = []
        var pendingHeight: Int?, pendingBandwidth: Int?, audioGroup: String?
        var audioGroups: [String: URL] = [:]
        for line in lines where !line.isEmpty {
            if line.hasPrefix("#EXT-X-MEDIA:") && line.contains("TYPE=AUDIO") {
                let attrs = parseAttributes(String(line.dropFirst("#EXT-X-MEDIA:".count)))
                if let group = attrs["GROUP-ID"], let uri = attrs["URI"],
                   let url = URL(string: uri, relativeTo: source)?.absoluteURL { audioGroups[group] = url }
            } else if line.hasPrefix("#EXT-X-STREAM-INF:") {
                let attrs = parseAttributes(String(line.dropFirst("#EXT-X-STREAM-INF:".count)))
                pendingBandwidth = Int(attrs["BANDWIDTH"] ?? "")
                if let resolution = attrs["RESOLUTION"], let h = Int(resolution.split(separator: "x").last ?? "") {
                    pendingHeight = h
                }
                audioGroup = attrs["AUDIO"]
            } else if isMasterPlaylist && !line.hasPrefix("#"), let url = URL(string: line, relativeTo: source)?.absoluteURL {
                if pendingHeight != nil || pendingBandwidth != nil {
                    videos.append(TrapTubeFlatAsset(url: url, kind: .video, mimeType: "application/vnd.apple.mpegurl",
                        height: pendingHeight, bitrate: pendingBandwidth, label: pendingHeight.map { "\($0)p" } ?? "Video",
                        isManifest: true, headers: [:]))
                    if let group = audioGroup, let audioURL = audioGroups[group] {
                        audios.append(TrapTubeFlatAsset(url: audioURL, kind: .audio, mimeType: "application/vnd.apple.mpegurl",
                            height: nil, bitrate: nil, label: "Audio", isManifest: true, headers: [:]))
                    } else {
                        muxed.append(TrapTubeFlatAsset(url: url, kind: .muxed, mimeType: "application/vnd.apple.mpegurl",
                            height: pendingHeight, bitrate: pendingBandwidth, label: "Muxed HLS",
                            isManifest: true, headers: [:]))
                    }
                    pendingHeight = nil; pendingBandwidth = nil; audioGroup = nil
                } else {
                    muxed.append(TrapTubeFlatAsset(url: url, kind: .muxed, mimeType: "application/vnd.apple.mpegurl",
                        height: nil, bitrate: nil, label: "HLS stream", isManifest: true, headers: [:]))
                }
            }
        }
        if videos.isEmpty && muxed.isEmpty {
            muxed = [TrapTubeFlatAsset(url: source, kind: .muxed, mimeType: "application/vnd.apple.mpegurl",
                height: nil, bitrate: nil, label: "HLS stream", isManifest: true, headers: [:])]
        }
        return TrapTubeResolvedMedia(title: title, sourceURL: source, videoAssets: videos,
            audioAssets: audios, muxedAssets: muxed, supportsSeparateAudioVideo: !videos.isEmpty && !audios.isEmpty)
    }

    private func parseDASH(data: Data, source: URL, title: String) throws -> TrapTubeResolvedMedia {
        guard let xml = String(data: data, encoding: .utf8), xml.contains("<MPD") else {
            throw TrapTubeResolverError.badResponse
        }
        let usesSegmentTemplate = xml.contains("<SegmentTemplate") || xml.contains("<SegmentList") || xml.contains("<SegmentBase")
        let blocks = xml.components(separatedBy: "<Representation").dropFirst()
        var video: [TrapTubeFlatAsset] = [], audio: [TrapTubeFlatAsset] = [], muxed: [TrapTubeFlatAsset] = []
        for (index, block) in blocks.enumerated() {
            guard let end = block.range(of: "</Representation>") else { continue }
            let segment = String(block[..<end.lowerBound])
            guard let tagEnd = segment.firstIndex(of: ">") else { continue }
            let attrs = parseAttributes(String(segment[..<tagEnd]))
            let baseStart = segment.range(of: "<BaseURL>")
            let baseEnd = segment.range(of: "</BaseURL>")
            let explicitBase: URL? = {
                guard let baseStart, let baseEnd else { return nil }
                let raw = String(segment[baseStart.upperBound..<baseEnd.lowerBound]).trimmingCharacters(in: .whitespacesAndNewlines)
                return URL(string: raw, relativeTo: source)?.absoluteURL
            }()
            let url = usesSegmentTemplate ? source : (explicitBase ?? source)
            let type = (attrs["mimeType"] ?? attrs["contentType"] ?? "").lowercased()
            let h = Int(attrs["height"] ?? ""), rate = Int(attrs["bandwidth"] ?? "")
            let id = attrs["id"]
            let kind: TrapTubeAssetKind = type.contains("audio") ? .audio : (type.contains("video") ? .video : .muxed)
            let asset = TrapTubeFlatAsset(url: url, kind: kind, mimeType: type, height: h, bitrate: rate,
                label: h.map { "\($0)p" } ?? (kind == .audio ? "DASH audio" : "DASH media"),
                isManifest: usesSegmentTemplate || explicitBase == nil, headers: [:],
                representationID: id, streamIndex: index)
            switch kind { case .video: video.append(asset); case .audio: audio.append(asset); case .muxed: muxed.append(asset) }
        }
        guard !video.isEmpty || !audio.isEmpty || !muxed.isEmpty else {
            throw TrapTubeResolverError.unsupportedManifest("The DASH manifest contains no addressable representations.")
        }
        return TrapTubeResolvedMedia(title: title, sourceURL: source, videoAssets: video, audioAssets: audio,
            muxedAssets: muxed, supportsSeparateAudioVideo: !video.isEmpty && !audio.isEmpty)
    }
    private func parseAttributes(_ value: String) -> [String: String] {
        var result: [String: String] = [:]
        guard let regex = try? NSRegularExpression(pattern: #"([A-Za-z0-9-]+)=("[^"]*"|[^,]*)"#, options: [.caseInsensitive]) else {
            return result
        }
        let ns = value as NSString
        for match in regex.matches(in: value, range: NSRange(location: 0, length: ns.length)) where match.numberOfRanges > 2 {
            result[ns.substring(with: match.range(at: 1))] =
                ns.substring(with: match.range(at: 2)).trimmingCharacters(in: CharacterSet(charactersIn: "\""))
        }
        return result
    }
}


struct TrapTubeYouTubeAdapter: TrapTubeStreamProviderAdapter {
    func canResolve(_ source: URL) -> Bool {
        let host = source.host?.lowercased() ?? ""
        return host == "youtu.be" || host == "youtube.com" || host.hasSuffix(".youtube.com") ||
            host == "youtube-nocookie.com" || host.hasSuffix(".youtube-nocookie.com")
    }

    func resolve(_ source: URL, title: String) async throws -> TrapTubeResolvedMedia {
        guard let videoID = videoIdentifier(from: source) else { throw TrapTubeResolverError.unsupportedSite }
        var watchComponents = URLComponents(string: "https://www.youtube.com/watch")!
        watchComponents.queryItems = [URLQueryItem(name: "v", value: videoID), URLQueryItem(name: "hl", value: "en")]
        let watchURL = watchComponents.url!
        var watchRequest = URLRequest(url: watchURL)
        watchRequest.timeoutInterval = 25
        watchRequest.setValue("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Version/18.0 Mobile/15E148 Safari/604.1", forHTTPHeaderField: "User-Agent")
        if let cookie = cookieHeader(for: watchURL) { watchRequest.setValue(cookie, forHTTPHeaderField: "Cookie") }
        let (pageData, pageResponse) = try await URLSession.shared.data(for: watchRequest)
        guard let pageHTTP = pageResponse as? HTTPURLResponse, (200..<400).contains(pageHTTP.statusCode),
              let page = String(data: pageData, encoding: .utf8) else { throw TrapTubeResolverError.badResponse }

        guard let apiKey = capture(#""INNERTUBE_API_KEY"\s*:\s*"([^"]+)""#, in: page) else {
            throw TrapTubeResolverError.unsupportedManifest("YouTube did not expose its player API configuration for this request.")
        }
        let clientVersion = capture(#""INNERTUBE_CLIENT_VERSION"\s*:\s*"([^"]+)""#, in: page) ?? "2.20261106.01.00"
        var endpoint = URLComponents(string: "https://www.youtube.com/youtubei/v1/player")!
        endpoint.queryItems = [URLQueryItem(name: "key", value: apiKey), URLQueryItem(name: "prettyPrint", value: "false")]
        var playerRequest = URLRequest(url: endpoint.url!)
        playerRequest.httpMethod = "POST"
        playerRequest.timeoutInterval = 30
        playerRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
        playerRequest.setValue("https://www.youtube.com", forHTTPHeaderField: "Origin")
        playerRequest.setValue(watchURL.absoluteString, forHTTPHeaderField: "Referer")
        playerRequest.setValue("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Version/18.0 Mobile/15E148 Safari/604.1", forHTTPHeaderField: "User-Agent")
        if let cookie = cookieHeader(for: watchURL) { playerRequest.setValue(cookie, forHTTPHeaderField: "Cookie") }
        let payload: [String: Any] = [
            "videoId": videoID,
            "contentCheckOk": true,
            "racyCheckOk": true,
            "context": ["client": [
                "clientName": "WEB",
                "clientVersion": clientVersion,
                "hl": "en",
                "gl": Locale.current.region?.identifier ?? "US"
            ]]
        ]
        playerRequest.httpBody = try JSONSerialization.data(withJSONObject: payload)
        let (playerData, playerResponse) = try await URLSession.shared.data(for: playerRequest)
        guard let http = playerResponse as? HTTPURLResponse, (200..<300).contains(http.statusCode),
              let root = try JSONSerialization.jsonObject(with: playerData) as? [String: Any] else {
            throw TrapTubeResolverError.badResponse
        }
        let status = (root["playabilityStatus"] as? [String: Any])?["status"] as? String ?? "UNKNOWN"
        guard status == "OK" else {
            let reason = (root["playabilityStatus"] as? [String: Any])?["reason"] as? String
                ?? "YouTube did not authorize playback for this video."
            throw TrapTubeResolverError.unsupportedManifest(reason)
        }
        let details = root["videoDetails"] as? [String: Any]
        let resolvedTitle = details?["title"] as? String ?? title
        let streaming = root["streamingData"] as? [String: Any] ?? [:]
        let muxedRows = streaming["formats"] as? [[String: Any]] ?? []
        let adaptiveRows = streaming["adaptiveFormats"] as? [[String: Any]] ?? []
        var videos: [TrapTubeFlatAsset] = []
        var audios: [TrapTubeFlatAsset] = []
        var muxed: [TrapTubeFlatAsset] = []
        let cookie = cookieHeader(for: URL(string: "https://googlevideo.com")!)
        var headers = [
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Version/18.0 Mobile/15E148 Safari/604.1",
            "Referer": "https://www.youtube.com/"
        ]
        if let cookie { headers["Cookie"] = cookie }

        for row in muxedRows {
            guard let rawURL = row["url"] as? String, let url = URL(string: rawURL) else { continue }
            let mime = (row["mimeType"] as? String ?? "").components(separatedBy: ";").first ?? ""
            let height = row["height"] as? Int
            let bitrate = row["bitrate"] as? Int
            muxed.append(TrapTubeFlatAsset(url: url, kind: .muxed, mimeType: mime, height: height,
                bitrate: bitrate, label: row["qualityLabel"] as? String ?? "Muxed", isManifest: false,
                headers: headers))
        }
        for row in adaptiveRows {
            guard let rawURL = row["url"] as? String, let url = URL(string: rawURL) else { continue }
            let mime = (row["mimeType"] as? String ?? "").components(separatedBy: ";").first ?? ""
            let height = row["height"] as? Int
            let bitrate = row["bitrate"] as? Int
            if mime.lowercased().hasPrefix("audio/") {
                audios.append(TrapTubeFlatAsset(url: url, kind: .audio, mimeType: mime, height: nil,
                    bitrate: bitrate, label: row["audioQuality"] as? String ?? "Audio", isManifest: false,
                    headers: headers))
            } else if mime.lowercased().hasPrefix("video/") {
                videos.append(TrapTubeFlatAsset(url: url, kind: .video, mimeType: mime, height: height,
                    bitrate: bitrate, label: row["qualityLabel"] as? String ?? height.map { "\($0)p" } ?? "Video",
                    isManifest: false, headers: headers))
            }
        }
        guard !videos.isEmpty || !audios.isEmpty || !muxed.isEmpty else {
            throw TrapTubeResolverError.unsupportedManifest(
                "YouTube did not expose direct media URLs. Ciphered or protected formats are not decoded by this adapter."
            )
        }
        return TrapTubeResolvedMedia(title: resolvedTitle, sourceURL: source, videoAssets: videos,
            audioAssets: audios, muxedAssets: muxed, supportsSeparateAudioVideo: !videos.isEmpty && !audios.isEmpty)
    }

    private func videoIdentifier(from url: URL) -> String? {
        let host = url.host?.lowercased() ?? ""
        if host == "youtu.be" { return url.path.split(separator: "/").first.map(String.init) }
        let parts = url.path.split(separator: "/").map(String.init)
        if let watch = URLComponents(url: url, resolvingAgainstBaseURL: false)?
            .queryItems?.first(where: { $0.name == "v" })?.value, !watch.isEmpty { return watch }
        if let index = parts.firstIndex(where: { ["shorts", "embed", "live"].contains($0) }), parts.indices.contains(index + 1) {
            return parts[index + 1]
        }
        return nil
    }

    private func capture(_ pattern: String, in text: String) -> String? {
        guard let regex = try? NSRegularExpression(pattern: pattern),
              let match = regex.firstMatch(in: text, range: NSRange(text.startIndex..., in: text)),
              match.numberOfRanges > 1, let range = Range(match.range(at: 1), in: text) else { return nil }
        return String(text[range])
    }

    private func cookieHeader(for url: URL) -> String? {
        let cookies = HTTPCookieStorage.shared.cookies(for: url) ?? []
        guard !cookies.isEmpty else { return nil }
        return cookies.map { "\($0.name)=\($0.value)" }.joined(separator: "; ")
    }
}

enum TrapTubeFlatTransferError: LocalizedError {
    case invalidStatus(Int)
    var errorDescription: String? {
        switch self { case .invalidStatus(let code): return "Media transfer failed with HTTP \(code)." }
    }
}

enum TrapTubeFlatTransfer {
    static func download(_ asset: TrapTubeFlatAsset, to destination: URL, startingAt offset: Int64 = 0,
                         progress: @escaping (Int64, Int64, Int64) -> Void) async throws -> URL {
        var request = URLRequest(url: asset.url)
        request.timeoutInterval = 180
        request.setValue("TrapTube/1.0", forHTTPHeaderField: "User-Agent")
        for (key, value) in asset.headers { request.setValue(value, forHTTPHeaderField: key) }
        if offset > 0 { request.setValue("bytes=\(offset)-", forHTTPHeaderField: "Range") }
        let (bytes, response) = try await URLSession.shared.bytes(for: request)
        guard let http = response as? HTTPURLResponse else { throw TrapTubeResolverError.badResponse }
        guard http.statusCode == 200 || http.statusCode == 206 else {
            throw TrapTubeFlatTransferError.invalidStatus(http.statusCode)
        }
        let effectiveOffset: Int64 = http.statusCode == 206 ? offset : 0
        let total = http.expectedContentLength > 0 ? http.expectedContentLength + effectiveOffset : 0
        try FileManager.default.createDirectory(at: destination.deletingLastPathComponent(), withIntermediateDirectories: true)
        if !FileManager.default.fileExists(atPath: destination.path) {
            FileManager.default.createFile(atPath: destination.path, contents: nil)
        }
        let handle = try FileHandle(forWritingTo: destination)
        if effectiveOffset == 0 { try handle.truncate(atOffset: 0) } else { try handle.seekToEnd() }
        var received: Int64 = 0, windowBytes: Int64 = 0, windowStart = Date()
        var buffer = Data()
        do {
            for try await byte in bytes {
                try Task.checkCancellation()
                buffer.append(byte); received += 1; windowBytes += 1
                if buffer.count >= 65536 {
                    try handle.write(contentsOf: buffer); buffer.removeAll(keepingCapacity: true)
                }
                if received % 262144 == 0 {
                    let elapsed = max(0.1, Date().timeIntervalSince(windowStart))
                    progress(effectiveOffset + received, total, Int64(Double(windowBytes) / elapsed))
                    windowBytes = 0; windowStart = Date()
                }
            }
            if !buffer.isEmpty { try handle.write(contentsOf: buffer) }
            try handle.close()
        } catch {
            try? handle.close()
            throw error
        }
        progress(effectiveOffset + received, total, 0)
        return destination
    }
}

enum TrapTubeMP4Box {
    static func mux(video: URL, audio: URL?, output: URL, videoStreamIndex: Int? = nil, audioStreamIndex: Int? = nil, progress: ((Int64, Double) -> Void)? = nil) async throws {
        var args = ["-y", "-i", video.absoluteString.hasPrefix("http") ? video.absoluteString : video.path]
        if let audio { args += ["-i", audio.absoluteString.hasPrefix("http") ? audio.absoluteString : audio.path] }
        args += audio == nil
            ? ["-map", videoStreamIndex.map { "0:\($0)" } ?? "0:v?", "-map", "0:a?", "-c", "copy", "-movflags", "+faststart", output.path]
            : ["-map", videoStreamIndex.map { "0:\($0)" } ?? "0:v:0", "-map", audioStreamIndex.map { "1:\($0)" } ?? "1:a:0", "-c", "copy", "-movflags", "+faststart", output.path]
        try await TrapTubeFFmpegProcessor.execute(args, progress: progress)
        guard FileManager.default.fileExists(atPath: output.path) else { throw TrapTubeFFmpegError.missingOutput }
    }

    static func extractAudio(input: URL, output: URL, format: String, streamIndex: Int? = nil,
                             progress: ((Int64, Double) -> Void)? = nil) async throws {
        let codec = format == "wav" ? "pcm_s16le" : "aac"
        let inputPath = input.absoluteString.hasPrefix("http") ? input.absoluteString : input.path
        try await TrapTubeFFmpegProcessor.execute(["-y", "-i", inputPath, "-map", streamIndex.map { "0:\($0)" } ?? "0:a:0?", "-vn", "-c:a", codec, output.path], progress: progress)
        guard FileManager.default.fileExists(atPath: output.path) else { throw TrapTubeFFmpegError.missingOutput }
    }
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
                    self.jobs[i].stage = "Processing stream"
                    self.jobs[i].downloadedBytes = bytes
                    self.jobs[i].speedBytesPerSecond = measuredSpeed
                    self.jobs[i].progress = 0
                    self.persistQueue()
                }
            }
            if modeFor(jobID) == "audio" {
                try await TrapTubeMP4Box.extractAudio(input: first, output: outputURL, format: outputExt, streamIndex: audio?.streamIndex ?? video?.streamIndex, progress: stats)
            } else {
                try await TrapTubeMP4Box.mux(video: first, audio: inputURLs.count > 1 ? inputURLs[1] : nil, output: outputURL, videoStreamIndex: video?.streamIndex, audioStreamIndex: audio?.streamIndex, progress: stats)
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
            if let i = jobs.firstIndex(where: { $0.id == jobID }) {
                if Task.isCancelled {
                    jobs[i].status = "paused"; jobs[i].stage = "Paused · can resume"
                } else {
                    jobs[i].status = "failed"; jobs[i].error = error.localizedDescription
                }
                persistQueue()
            }
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

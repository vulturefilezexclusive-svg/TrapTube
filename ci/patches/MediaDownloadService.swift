import Foundation
import SwiftUI
import WebKit
import ffmpegkit

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
    var headers: [String: String]
    var representationID: String? = nil
    var streamIndex: Int? = nil
    var initializationURL: URL? = nil
    var segmentURLs: [URL] = []
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
    var selectedVideoStreamIndex: Int? = nil
    var selectedAudioStreamIndex: Int? = nil
    var selectedVideoRepresentationID: String? = nil
    var selectedAudioRepresentationID: String? = nil
    var selectedVideoHeight: Int? = nil
    var selectedVideoBitrate: Int? = nil
    var selectedAudioBitrate: Int? = nil
    var selectedVideoMimeType: String? = nil
    var selectedAudioMimeType: String? = nil
    var outputFormat: String? = nil
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

enum TrapTubeWebCookieBridge {
    @MainActor
    static func cookieHeader(for url: URL) async -> String? {
        let cookies: [HTTPCookie] = await withCheckedContinuation { continuation in
            WKWebsiteDataStore.default().httpCookieStore.getAllCookies { continuation.resume(returning: $0) }
        }
        let host = url.host?.lowercased() ?? ""
        let matching = cookies.filter { cookie in
            let domain = cookie.domain.lowercased().trimmingCharacters(in: CharacterSet(charactersIn: "."))
            return host == domain || host.hasSuffix("." + domain)
        }
        guard !matching.isEmpty else { return nil }
        return matching.map { "\($0.name)=\($0.value)" }.joined(separator: "; ")
    }

    static func headers(for url: URL, userAgent: String = "TrapTube/1.0",
                        referer: URL? = nil) async -> [String: String] {
        var headers = ["User-Agent": userAgent]
        if let referer { headers["Referer"] = referer.absoluteString }
        if let cookie = await TrapTubeWebCookieBridge.cookieHeader(for: url) { headers["Cookie"] = cookie }
        return headers
    }

    static func forwarding(_ existing: [String: String], from source: URL, to destination: URL) async -> [String: String] {
        guard source.host?.lowercased() != destination.host?.lowercased() else { return existing }
        var safe = existing.filter {
            let key = $0.key.lowercased()
            return key != "cookie" && key != "authorization" && !key.hasPrefix("x-api-key")
        }
        if let cookie = await cookieHeader(for: destination) { safe["Cookie"] = cookie }
        return safe
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
        let providerHeaders = await TrapTubeWebCookieBridge.headers(for: source)
        var head = URLRequest(url: source)
        head.httpMethod = "HEAD"; head.timeoutInterval = 20
        providerHeaders.forEach { head.setValue($0.value, forHTTPHeaderField: $0.key) }
        let headResponse = try? await URLSession.shared.data(for: head)
        let http = headResponse?.1 as? HTTPURLResponse
        let mime = (http?.mimeType ?? "").lowercased()
        let disposition = http?.value(forHTTPHeaderField: "Content-Disposition") ?? ""
        let filenameExtension: String = {
            guard let match = disposition.range(of: #"filename\*?=(?:UTF-8'')?[\"']?([^;\"']+)"#,
                                                options: .regularExpression) else { return "" }
            let value = String(disposition[match]).split(separator: "=", maxSplits: 1).last.map(String.init) ?? ""
            return URL(fileURLWithPath: value.trimmingCharacters(in: CharacterSet(charactersIn: "\"' "))).pathExtension.lowercased()
        }()
        let mediaExtension = ext.isEmpty ? filenameExtension : ext
        let audioExtensions = ["m4a","mp3","aac","wav","flac","ogg","opus"]
        let mediaExtensions = ["mp4","m4v","mov","webm","mkv","avi","ts"] + audioExtensions
        if mime.hasPrefix("video/") || mime.hasPrefix("audio/") || mediaExtensions.contains(mediaExtension) {
            let kind: TrapTubeAssetKind = mime.hasPrefix("audio/") || audioExtensions.contains(mediaExtension) ? .audio : .muxed
            let asset = TrapTubeFlatAsset(url: source, kind: kind, mimeType: mime, height: nil, bitrate: nil,
                label: kind == .audio ? "Original audio" : "Original media", isManifest: false, headers: providerHeaders)
            return TrapTubeResolvedMedia(title: title, sourceURL: source, videoAssets: [],
                audioAssets: kind == .audio ? [asset] : [], muxedAssets: kind == .muxed ? [asset] : [],
                supportsSeparateAudioVideo: false)
        }
        let isHLS = ext == "m3u8" || mime.contains("mpegurl")
        let isDASH = ext == "mpd" || mime.contains("dash+xml")
        var request = URLRequest(url: source)
        request.httpMethod = "GET"; request.timeoutInterval = 25
        providerHeaders.forEach { request.setValue($0.value, forHTTPHeaderField: $0.key) }
        if !isHLS && !isDASH {
            // Some providers reject HEAD; inspect a bounded initial response instead.
            request.setValue("bytes=0-1048575", forHTTPHeaderField: "Range")
        }
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let manifestResponse = response as? HTTPURLResponse,
              (200..<400).contains(manifestResponse.statusCode) else { throw TrapTubeResolverError.badResponse }
        let responseMime = (manifestResponse.mimeType ?? "").lowercased()
        let responseDisposition = manifestResponse.value(forHTTPHeaderField: "Content-Disposition") ?? ""
        let responseFilenameExtension: String = {
            guard let match = responseDisposition.range(of: #"filename\*?=(?:UTF-8'')?[\"']?([^;\"']+)"#,
                                                        options: .regularExpression) else { return "" }
            let value = String(responseDisposition[match]).split(separator: "=", maxSplits: 1).last.map(String.init) ?? ""
            return URL(fileURLWithPath: value.trimmingCharacters(in: CharacterSet(charactersIn: "\"' "))).pathExtension.lowercased()
        }()
        let signatureExtension: String = {
            if data.count >= 8, String(data: data[4..<8], encoding: .ascii) == "ftyp" { return "mp4" }
            if data.count >= 4, data.prefix(4) == Data([0x1A, 0x45, 0xDF, 0xA3]) { return "webm" }
            if data.count >= 4, data.prefix(4) == Data("fLaC".utf8) { return "flac" }
            if data.count >= 12, data.prefix(4) == Data("RIFF".utf8), String(data: data[8..<12], encoding: .ascii) == "WAVE" { return "wav" }
            if data.count >= 3, data.prefix(3) == Data("ID3".utf8) { return "mp3" }
            if data.count >= 2, data[0] == 0xFF, data[1] & 0xF6 == 0xF0 { return "aac" }
            return ""
        }()
        let responseExtension = responseFilenameExtension.isEmpty ? signatureExtension : responseFilenameExtension
        let responseAudioExtensions = ["m4a","mp3","aac","wav","flac","ogg","opus"]
        let responseMediaExtensions = ["mp4","m4v","mov","webm","mkv","avi","ts"] + responseAudioExtensions
        if responseMime.hasPrefix("video/") || responseMime.hasPrefix("audio/") || responseMediaExtensions.contains(responseExtension) {
            let kind: TrapTubeAssetKind = responseMime.hasPrefix("audio/") || responseAudioExtensions.contains(responseExtension) ? .audio : .muxed
            let asset = TrapTubeFlatAsset(url: source, kind: kind, mimeType: responseMime, height: nil, bitrate: nil,
                label: kind == .audio ? "Original audio" : "Original media", isManifest: false, headers: providerHeaders)
            return TrapTubeResolvedMedia(title: title, sourceURL: source, videoAssets: [],
                audioAssets: kind == .audio ? [asset] : [], muxedAssets: kind == .muxed ? [asset] : [],
                supportsSeparateAudioVideo: false)
        }
        if isHLS || responseMime.contains("mpegurl") || responseExtension == "m3u8" {
            return try await parseHLS(data: data, source: source, title: title, headers: providerHeaders)
        }
        if isDASH || responseMime.contains("dash+xml") || responseExtension == "mpd" {
            return try parseDASH(data: data, source: source, title: title, headers: providerHeaders)
        }
        let responseMime = ((response as? HTTPURLResponse)?.mimeType ?? mime).lowercased()
        if responseMime.hasPrefix("video/") || responseMime.hasPrefix("audio/") {
            let kind: TrapTubeAssetKind = responseMime.hasPrefix("audio/") ? .audio : .muxed
            let asset = TrapTubeFlatAsset(url: source, kind: kind, mimeType: responseMime, height: nil, bitrate: nil,
                label: "Original media", isManifest: false, headers: providerHeaders)
            return TrapTubeResolvedMedia(title: title, sourceURL: source, videoAssets: [],
                audioAssets: kind == .audio ? [asset] : [], muxedAssets: kind == .muxed ? [asset] : [],
                supportsSeparateAudioVideo: false)
        }
        if responseMime.contains("text/html") || responseMime.isEmpty,
           let candidate = htmlMediaCandidates(data: data, baseURL: source).first {
            return try await resolve(candidate, title: title)
        }
        throw TrapTubeResolverError.unsupportedSite
    }

    func resolveManifest(_ source: URL, title: String, format: String,
                         headers: [String: String]) async throws -> TrapTubeResolvedMedia {
        var request = URLRequest(url: source)
        request.httpMethod = "GET"
        request.timeoutInterval = 30
        headers.forEach { request.setValue($0.value, forHTTPHeaderField: $0.key) }
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
            throw TrapTubeResolverError.badResponse
        }
        if format == "hls" {
            return try await parseHLS(data: data, source: source, title: title, headers: headers)
        }
        return try parseDASH(data: data, source: source, title: title, headers: headers)
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

    private func parseHLS(data: Data, source: URL, title: String, headers: [String: String]) async throws -> TrapTubeResolvedMedia {
        guard let text = String(data: data, encoding: .utf8), text.contains("#EXTM3U") else {
            throw TrapTubeResolverError.badResponse
        }
        let lines = text.components(separatedBy: .newlines).map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
        let isMasterPlaylist = text.contains("#EXT-X-STREAM-INF")
        if !isMasterPlaylist {
            let media = parseHLSMediaPlaylist(lines, source: source)
            let asset = TrapTubeFlatAsset(url: source, kind: .muxed, mimeType: "application/vnd.apple.mpegurl",
                height: nil, bitrate: nil, label: "HLS media", isManifest: media.segmentURLs.isEmpty,
                headers: headers, initializationURL: media.initializationURL, segmentURLs: media.segmentURLs)
            return TrapTubeResolvedMedia(title: title, sourceURL: source, videoAssets: [],
                audioAssets: [], muxedAssets: [asset], supportsSeparateAudioVideo: false)
        }

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
            } else if !line.hasPrefix("#"), let url = URL(string: line, relativeTo: source)?.absoluteURL,
                      pendingHeight != nil || pendingBandwidth != nil {
                let media = await loadHLSVariant(url, from: source, headers: headers)
                let videoAsset = TrapTubeFlatAsset(url: url, kind: .video, mimeType: "application/vnd.apple.mpegurl",
                    height: pendingHeight, bitrate: pendingBandwidth, label: pendingHeight.map { "\($0)p" } ?? "Video",
                    isManifest: media.segmentURLs.isEmpty, headers: headers,
                    initializationURL: media.initializationURL, segmentURLs: media.segmentURLs)
                videos.append(videoAsset)
                if let group = audioGroup, let audioURL = audioGroups[group] {
                    let audioMedia = await loadHLSVariant(audioURL, from: source, headers: headers)
                    audios.append(TrapTubeFlatAsset(url: audioURL, kind: .audio, mimeType: "application/vnd.apple.mpegurl",
                        height: nil, bitrate: nil, label: "Audio", isManifest: audioMedia.segmentURLs.isEmpty,
                        headers: headers, initializationURL: audioMedia.initializationURL, segmentURLs: audioMedia.segmentURLs))
                } else {
                    muxed.append(TrapTubeFlatAsset(url: url, kind: .muxed, mimeType: "application/vnd.apple.mpegurl",
                        height: pendingHeight, bitrate: pendingBandwidth, label: pendingHeight.map { "\($0)p · muxed" } ?? "Muxed HLS",
                        isManifest: media.segmentURLs.isEmpty, headers: headers,
                        initializationURL: media.initializationURL, segmentURLs: media.segmentURLs))
                }
                pendingHeight = nil; pendingBandwidth = nil; audioGroup = nil
            }
        }
        if videos.isEmpty && muxed.isEmpty {
            muxed = [TrapTubeFlatAsset(url: source, kind: .muxed, mimeType: "application/vnd.apple.mpegurl",
                height: nil, bitrate: nil, label: "HLS stream", isManifest: true, headers: headers)]
        }
        return TrapTubeResolvedMedia(title: title, sourceURL: source, videoAssets: videos,
            audioAssets: audios, muxedAssets: muxed, supportsSeparateAudioVideo: !videos.isEmpty && !audios.isEmpty)
    }

    private func loadHLSVariant(_ url: URL, from source: URL, headers: [String: String]) async -> (initializationURL: URL?, segmentURLs: [URL]) {
        var request = URLRequest(url: url)
        request.timeoutInterval = 20
        let requestHeaders = await TrapTubeWebCookieBridge.forwarding(headers, from: source, to: url)
        requestHeaders.forEach { request.setValue($0.value, forHTTPHeaderField: $0.key) }
        guard let (data, response) = try? await URLSession.shared.data(for: request),
              let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode),
              let text = String(data: data, encoding: .utf8), text.contains("#EXTM3U") else {
            return (nil, [])
        }
        return parseHLSMediaPlaylist(text.components(separatedBy: .newlines).map {
            $0.trimmingCharacters(in: .whitespacesAndNewlines)
        }, source: url)
    }

    private func parseHLSMediaPlaylist(_ lines: [String], source: URL) -> (initializationURL: URL?, segmentURLs: [URL]) {
        let encrypted = lines.contains { line in
            line.hasPrefix("#EXT-X-KEY:") && !line.uppercased().contains("METHOD=NONE")
        }
        let hasByteRanges = lines.contains { $0.hasPrefix("#EXT-X-BYTERANGE:") }
        let isCompleteVOD = lines.contains("#EXT-X-ENDLIST")
        guard !encrypted, !hasByteRanges, isCompleteVOD else { return (nil, []) }

        var initializationURL: URL?
        if let mapLine = lines.first(where: { $0.hasPrefix("#EXT-X-MAP:") }) {
            let attrs = parseAttributes(String(mapLine.dropFirst("#EXT-X-MAP:".count)))
            if let uri = attrs["URI"] { initializationURL = URL(string: uri, relativeTo: source)?.absoluteURL }
        }
        var expectsSegment = false
        var segments: [URL] = []
        for line in lines where !line.isEmpty {
            if line.hasPrefix("#EXTINF:") {
                expectsSegment = true
            } else if expectsSegment && !line.hasPrefix("#") {
                if let url = URL(string: line, relativeTo: source)?.absoluteURL { segments.append(url) }
                expectsSegment = false
            }
        }
        guard !segments.isEmpty else { return (nil, []) }
        return (initializationURL, segments)
    }
    private func parseDASH(data: Data, source: URL, title: String, headers: [String: String]) throws -> TrapTubeResolvedMedia {
        guard let xml = String(data: data, encoding: .utf8), xml.contains("<MPD") else {
            throw TrapTubeResolverError.badResponse
        }
        let mpdDuration = parseISODuration(attribute("mediaPresentationDuration", in: xml) ?? "")
        let mpdHeaderEnd = xml.range(of: "<Period")?.lowerBound ?? xml.endIndex
        let mpdHeader = String(xml[..<mpdHeaderEnd])
        let mpdTemplate = element("SegmentTemplate", in: mpdHeader)
        let mpdList = element("SegmentList", in: mpdHeader)
        let mpdSegmentBase = element("SegmentBase", in: mpdHeader)
        let mpdBase = elementText("BaseURL", in: mpdHeader)
        var video: [TrapTubeFlatAsset] = [], audio: [TrapTubeFlatAsset] = [], muxed: [TrapTubeFlatAsset] = []
        let periodParts = xml.components(separatedBy: "<Period")
        let periodBodies: [String] = periodParts.count > 1
            ? periodParts.dropFirst().map { part in
                if let end = part.range(of: "</Period>") { return String(part[..<end.lowerBound]) }
                return part
            }
            : [xml]
        for periodBody in periodBodies {
            let periodTagEnd = periodBody.firstIndex(of: ">")
            let periodAttributes = periodTagEnd.map { parseAttributes(String(periodBody[..<$0])) } ?? [:]
            let periodDuration = parseISODuration(periodAttributes["duration"] ?? "")
            let durationSeconds = periodDuration > 0 ? periodDuration : mpdDuration
            let periodHeaderEnd = periodBody.range(of: "<AdaptationSet")?.lowerBound ?? periodBody.endIndex
            let periodHeader = String(periodBody[..<periodHeaderEnd])
            let periodTemplate = element("SegmentTemplate", in: periodHeader) ?? mpdTemplate
            let periodList = element("SegmentList", in: periodHeader) ?? mpdList
            let periodSegmentBase = element("SegmentBase", in: periodHeader) ?? mpdSegmentBase
            let periodBase = elementText("BaseURL", in: periodHeader) ?? mpdBase
            let adaptationSets = periodBody.components(separatedBy: "<AdaptationSet").dropFirst()
            for adaptation in adaptationSets {
            guard let adaptationEnd = adaptation.range(of: "</AdaptationSet>"),
                  let adaptationTagEnd = adaptation.firstIndex(of: ">") else { continue }
            let adaptationBody = String(adaptation[..<adaptationEnd.lowerBound])
            let adaptationAttributes = parseAttributes(String(adaptation[..<adaptationTagEnd]))
            let inheritedType = (adaptationAttributes["mimeType"] ?? adaptationAttributes["contentType"] ?? "").lowercased()
            let adaptationHeaderEnd = adaptationBody.range(of: "<Representation")?.lowerBound ?? adaptationBody.endIndex
            let adaptationHeader = String(adaptationBody[..<adaptationHeaderEnd])
            let inheritedTemplate = element("SegmentTemplate", in: adaptationHeader) ?? periodTemplate
            let inheritedList = element("SegmentList", in: adaptationHeader) ?? periodList
            let inheritedSegmentBase = element("SegmentBase", in: adaptationHeader) ?? periodSegmentBase
            let inheritedBase = elementText("BaseURL", in: adaptationHeader) ?? periodBase
            let representations = adaptationBody.components(separatedBy: "<Representation").dropFirst()
            for block in representations {
                guard let end = block.range(of: "</Representation>") else { continue }
                let segment = String(block[..<end.lowerBound])
                guard let tagEnd = segment.firstIndex(of: ">") else { continue }
                let attrs = parseAttributes(String(segment[..<tagEnd]))
                let representationBase = elementText("BaseURL", in: segment) ?? inheritedBase
                let resolvedBase = representationBase.flatMap { URL(string: $0.trimmingCharacters(in: .whitespacesAndNewlines), relativeTo: source)?.absoluteURL } ?? source
                let type = (attrs["mimeType"] ?? attrs["contentType"] ?? inheritedType).lowercased()
                let height = Int(attrs["height"] ?? "")
                let bitrate = Int(attrs["bandwidth"] ?? "")
                let representationID = attrs["id"]
                let template = element("SegmentTemplate", in: segment) ?? inheritedTemplate
                let list = element("SegmentList", in: segment) ?? inheritedList
                let segmentBase = element("SegmentBase", in: segment) ?? inheritedSegmentBase
                var initializationURL: URL?
                var segmentURLs: [URL] = []

                if let template {
                    let templateAttributes = parseAttributes(template.tag)
                    let mediaPattern = templateAttributes["media"]
                    let initializationPattern = templateAttributes["initialization"]
                    let timescale = Int64(templateAttributes["timescale"] ?? "1") ?? 1
                    let startNumber = Int64(templateAttributes["startNumber"] ?? "1") ?? 1
                    if let initializationPattern {
                        let expanded = expandDASHTemplate(initializationPattern, representationID: representationID,
                            bandwidth: bitrate, number: startNumber, time: 0)
                        initializationURL = URL(string: expanded, relativeTo: resolvedBase)?.absoluteURL
                    }
                    if let mediaPattern {
                        let timeline = element("SegmentTimeline", in: template.body)?.body ?? ""
                        if !timeline.isEmpty {
                            let entries = timeline.components(separatedBy: "<S").dropFirst()
                            var currentTime: Int64 = 0
                            var currentNumber = startNumber
                            for (entryIndex, entry) in entries.enumerated() {
                                guard let tagEnd = entry.firstIndex(of: ">") else { continue }
                                let values = parseAttributes(String(entry[..<tagEnd]))
                                guard let segmentDuration = Int64(values["d"] ?? ""), segmentDuration > 0 else { continue }
                                let startTime = Int64(values["t"] ?? "") ?? currentTime
                                let repeatCount = Int64(values["r"] ?? "0") ?? 0
                                var count: Int64
                                if repeatCount >= 0 {
                                    count = repeatCount + 1
                                } else {
                                    let nextTime: Int64? = entries.dropFirst(entryIndex + 1).first.flatMap { next in
                                        guard let nextEnd = next.firstIndex(of: ">") else { return nil }
                                        return Int64(parseAttributes(String(next[..<nextEnd]))["t"] ?? "")
                                    }
                                    let endTime = nextTime ?? (durationSeconds > 0 ? Int64((durationSeconds * Double(timescale)).rounded(.up)) : nil)
                                    guard let endTime, endTime > startTime else {
                                        throw TrapTubeResolverError.unsupportedManifest("DASH timeline has an open-ended repeat without a known period duration.")
                                    }
                                    count = Int64(ceil(Double(endTime - startTime) / Double(segmentDuration)))
                                }
                                guard count > 0, count <= 10000, Int64(segmentURLs.count) + count <= 10000 else {
                                    throw TrapTubeResolverError.unsupportedManifest("DASH timeline contains too many segments to queue safely.")
                                }
                                for offset in 0..<count {
                                    let number = currentNumber + offset
                                    let time = startTime + offset * segmentDuration
                                    let expanded = expandDASHTemplate(mediaPattern, representationID: representationID,
                                        bandwidth: bitrate, number: number, time: time)
                                    if let url = URL(string: expanded, relativeTo: resolvedBase)?.absoluteURL { segmentURLs.append(url) }
                                }
                                currentNumber += count
                                currentTime = startTime + count * segmentDuration
                            }
                        } else if let segmentDuration = Int64(templateAttributes["duration"] ?? ""), segmentDuration > 0,
                                  durationSeconds > 0, timescale > 0 {
                            let count = Int64(ceil(durationSeconds * Double(timescale) / Double(segmentDuration)))
                            guard count > 0, count <= 10000 else {
                                throw TrapTubeResolverError.unsupportedManifest("DASH duration template contains too many segments.")
                            }
                            for offset in 0..<count {
                                let expanded = expandDASHTemplate(mediaPattern, representationID: representationID,
                                    bandwidth: bitrate, number: startNumber + offset, time: offset * segmentDuration)
                                if let url = URL(string: expanded, relativeTo: resolvedBase)?.absoluteURL { segmentURLs.append(url) }
                            }
                        }
                    }
                } else if let list {
                    let listBody = list.body
                    if let initTag = firstTag("Initialization", in: listBody) {
                        let initAttrs = parseAttributes(initTag)
                        if let raw = initAttrs["sourceURL"] {
                            initializationURL = URL(string: raw, relativeTo: resolvedBase)?.absoluteURL
                        }
                    }
                    let segmentTags = allTags("SegmentURL", in: listBody)
                    for tag in segmentTags {
                        let values = parseAttributes(tag)
                        if let raw = values["media"], let url = URL(string: raw, relativeTo: resolvedBase)?.absoluteURL {
                            segmentURLs.append(url)
                        }
                    }
                }

                let kind: TrapTubeAssetKind = type.contains("audio") ? .audio : (type.contains("video") ? .video : .muxed)
                let label = height.map { "\($0)p" } ?? (kind == .audio ? "DASH audio" : "DASH media")
                let segmented = !segmentURLs.isEmpty
                let hasDirectBase = representationBase != nil || inheritedBase != nil
                let needsManifestReader = template != nil || list != nil || segmentBase != nil || !hasDirectBase
                let assetURL = segmented || needsManifestReader ? source : resolvedBase
                let asset = TrapTubeFlatAsset(url: assetURL, kind: kind, mimeType: type, height: height, bitrate: bitrate,
                    label: label, isManifest: needsManifestReader && !segmented, headers: headers, representationID: representationID,
                    streamIndex: nil, initializationURL: initializationURL, segmentURLs: segmentURLs)
                switch kind { case .video: video.append(asset); case .audio: audio.append(asset); case .muxed: muxed.append(asset) }
            }
            }
        }
        guard !video.isEmpty || !audio.isEmpty || !muxed.isEmpty else {
            throw TrapTubeResolverError.unsupportedManifest("The DASH manifest contains no addressable representations.")
        }
        return TrapTubeResolvedMedia(title: title, sourceURL: source, videoAssets: video, audioAssets: audio,
            muxedAssets: muxed, supportsSeparateAudioVideo: !video.isEmpty && !audio.isEmpty)
    }

    private func attribute(_ name: String, in text: String) -> String? {
        guard let tagEnd = text.firstIndex(of: ">") else { return nil }
        return parseAttributes(String(text[..<tagEnd]))[name]
    }

    private func element(_ name: String, in text: String) -> (tag: String, body: String)? {
        guard let start = text.range(of: "<\(name)"),
              let tagEnd = text[start.lowerBound...].firstIndex(of: ">") else { return nil }
        let tag = String(text[start.lowerBound...tagEnd])
        if let close = text.range(of: "</\(name)>", range: tagEnd..<text.endIndex) {
            return (tag, String(text[tagEnd..<close.lowerBound]))
        }
        return (tag, "")
    }

    private func elementText(_ name: String, in text: String) -> String? {
        guard let opening = text.range(of: "<\(name)>"),
              let closing = text.range(of: "</\(name)>", range: opening.upperBound..<text.endIndex) else { return nil }
        return String(text[opening.upperBound..<closing.lowerBound])
    }

    private func firstTag(_ name: String, in text: String) -> String? {
        guard let start = text.range(of: "<\(name)"),
              let end = text[start.lowerBound...].firstIndex(of: ">") else { return nil }
        return String(text[start.lowerBound...end])
    }

    private func allTags(_ name: String, in text: String) -> [String] {
        var output: [String] = []
        var search = text.startIndex
        while let start = text.range(of: "<\(name)", range: search..<text.endIndex),
              let end = text[start.lowerBound...].firstIndex(of: ">") {
            output.append(String(text[start.lowerBound...end]))
            search = text.index(after: end)
        }
        return output
    }

    private func parseISODuration(_ value: String) -> Double {
        guard let regex = try? NSRegularExpression(pattern: #"^PT(?:(\d+(?:\.\d+)?)H)?(?:(\d+(?:\.\d+)?)M)?(?:(\d+(?:\.\d+)?)S)?$"#),
              let match = regex.firstMatch(in: value, range: NSRange(value.startIndex..., in: value)) else { return 0 }
        func number(_ index: Int) -> Double {
            guard match.range(at: index).location != NSNotFound,
                  let range = Range(match.range(at: index), in: value) else { return 0 }
            return Double(value[range]) ?? 0
        }
        return number(1) * 3600 + number(2) * 60 + number(3)
    }

    private func expandDASHTemplate(_ template: String, representationID: String?, bandwidth: Int?,
                                   number: Int64, time: Int64) -> String {
        let escapeToken = "\u{0}"
        var output = template.replacingOccurrences(of: "$$", with: escapeToken)
        if let regex = try? NSRegularExpression(pattern: #"\$(Number|Time|Bandwidth)%0(\d+)d\$"#) {
            let ns = output as NSString
            for match in regex.matches(in: output, range: NSRange(location: 0, length: ns.length)).reversed() {
                guard match.numberOfRanges == 3 else { continue }
                let key = ns.substring(with: match.range(at: 1))
                let width = Int(ns.substring(with: match.range(at: 2))) ?? 1
                let value = key == "Number" ? number : (key == "Time" ? time : Int64(bandwidth ?? 0))
                let formatted = String(format: "%0*lld", width, value)
                if let range = Range(match.range, in: output) { output.replaceSubrange(range, with: formatted) }
            }
        }
        output = output.replacingOccurrences(of: "$RepresentationID$", with: representationID ?? "")
            .replacingOccurrences(of: "$Bandwidth$", with: String(bandwidth ?? 0))
            .replacingOccurrences(of: "$Number$", with: String(number))
            .replacingOccurrences(of: "$Time$", with: String(time))
            .replacingOccurrences(of: escapeToken, with: "$")
        return output
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
        if let cookie = await TrapTubeWebCookieBridge.cookieHeader(for: watchURL) { watchRequest.setValue(cookie, forHTTPHeaderField: "Cookie") }
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
        if let cookie = await TrapTubeWebCookieBridge.cookieHeader(for: watchURL) { playerRequest.setValue(cookie, forHTTPHeaderField: "Cookie") }
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
        let baseHeaders = [
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Version/18.0 Mobile/15E148 Safari/604.1",
            "Referer": "https://www.youtube.com/"
        ]

        for row in muxedRows {
            guard let rawURL = row["url"] as? String, let url = URL(string: rawURL) else { continue }
            let mime = (row["mimeType"] as? String ?? "").components(separatedBy: ";").first ?? ""
            let height = row["height"] as? Int
            let bitrate = row["bitrate"] as? Int
            var headers = baseHeaders
            if let cookie = await TrapTubeWebCookieBridge.cookieHeader(for: url) { headers["Cookie"] = cookie }
            muxed.append(TrapTubeFlatAsset(url: url, kind: .muxed, mimeType: mime, height: height,
                bitrate: bitrate, label: row["qualityLabel"] as? String ?? "Muxed", isManifest: false,
                headers: headers, representationID: (row["itag"] as? Int).map(String.init)))
        }
        for row in adaptiveRows {
            guard let rawURL = row["url"] as? String, let url = URL(string: rawURL) else { continue }
            let mime = (row["mimeType"] as? String ?? "").components(separatedBy: ";").first ?? ""
            let height = row["height"] as? Int
            let bitrate = row["bitrate"] as? Int
            var headers = baseHeaders
            if let cookie = await TrapTubeWebCookieBridge.cookieHeader(for: url) { headers["Cookie"] = cookie }
            if mime.lowercased().hasPrefix("audio/") {
                audios.append(TrapTubeFlatAsset(url: url, kind: .audio, mimeType: mime, height: nil,
                    bitrate: bitrate, label: row["audioQuality"] as? String ?? "Audio", isManifest: false,
                    headers: headers, representationID: (row["itag"] as? Int).map(String.init)))
            } else if mime.lowercased().hasPrefix("video/") {
                videos.append(TrapTubeFlatAsset(url: url, kind: .video, mimeType: mime, height: height,
                    bitrate: bitrate, label: row["qualityLabel"] as? String ?? height.map { "\($0)p" } ?? "Video",
                    isManifest: false, headers: headers, representationID: (row["itag"] as? Int).map(String.init)))
            }
        }
        if videos.isEmpty || audios.isEmpty {
            let dashManifest = (streaming["dashManifestUrl"] as? String).flatMap(URL.init(string:))
            let hlsManifest = (streaming["hlsManifestUrl"] as? String).flatMap(URL.init(string:))
            if let manifest = dashManifest ?? hlsManifest {
                let manifestFormat = dashManifest != nil ? "dash" : "hls"
                var manifestHeaders = baseHeaders
                if let cookie = await TrapTubeWebCookieBridge.cookieHeader(for: manifest) {
                    manifestHeaders["Cookie"] = cookie
                }
                if let parsed = try? await TrapTubeStreamResolver(adapters: []).resolveManifest(
                    manifest, title: resolvedTitle, format: manifestFormat, headers: manifestHeaders
                ) {
                    func withHeaders(_ asset: TrapTubeFlatAsset) -> TrapTubeFlatAsset {
                        var copy = asset
                        copy.headers = manifestHeaders
                        return copy
                    }
                    videos += parsed.videoAssets.map(withHeaders)
                    audios += parsed.audioAssets.map(withHeaders)
                    muxed += parsed.muxedAssets.map(withHeaders)
                }
                if videos.isEmpty && audios.isEmpty && muxed.isEmpty {
                    muxed.append(TrapTubeFlatAsset(url: manifest, kind: .muxed,
                        mimeType: manifestFormat == "hls" ? "application/vnd.apple.mpegurl" : "application/dash+xml",
                        height: nil, bitrate: nil, label: "YouTube adaptive manifest", isManifest: true,
                        headers: manifestHeaders))
                }
            }
        }
        guard !videos.isEmpty || !audios.isEmpty || !muxed.isEmpty else {
            throw TrapTubeResolverError.unsupportedManifest(
                "YouTube did not expose direct media URLs or a usable manifest. Ciphered or protected formats are not decoded by this adapter."
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

}

enum TrapTubeFlatTransferError: LocalizedError {
    case invalidStatus(Int)
    var errorDescription: String? {
        switch self { case .invalidStatus(let code): return "Media transfer failed with HTTP \(code)." }
    }
}

enum TrapTubeFlatTransfer {
    static func download(_ asset: TrapTubeFlatAsset, to destination: URL, startingAt offset: Int64 = 0,
                         rangeAttempt: Int = 0,
                         progress: @escaping (Int64, Int64, Int64) -> Void) async throws -> URL {
        var request = URLRequest(url: asset.url)
        request.timeoutInterval = 180
        request.setValue("TrapTube/1.0", forHTTPHeaderField: "User-Agent")
        request.setValue("identity", forHTTPHeaderField: "Accept-Encoding")
        for (key, value) in asset.headers { request.setValue(value, forHTTPHeaderField: key) }
        if offset > 0 { request.setValue("bytes=\(offset)-", forHTTPHeaderField: "Range") }
        let (bytes, response) = try await URLSession.shared.bytes(for: request)
        guard let http = response as? HTTPURLResponse else { throw TrapTubeResolverError.badResponse }
        if http.statusCode == 416, offset > 0,
           let contentRange = http.value(forHTTPHeaderField: "Content-Range"),
           let totalText = contentRange.split(separator: "/").last,
           let total = Int64(totalText), total == offset {
            progress(offset, total, 0)
            return destination
        }
        if http.statusCode == 416, offset > 0,
           let contentRange = http.value(forHTTPHeaderField: "Content-Range"),
           let totalString = contentRange.split(separator: "/").last,
           let expected = Int64(totalString),
           let actual = (try? FileManager.default.attributesOfItem(atPath: destination.path)[.size] as? NSNumber)?.int64Value,
           actual == expected {
            return destination
        }
        guard http.statusCode == 200 || http.statusCode == 206 else {
            throw TrapTubeFlatTransferError.invalidStatus(http.statusCode)
        }
        let effectiveOffset: Int64 = http.statusCode == 206 ? offset : 0
        var total = http.expectedContentLength > 0 ? http.expectedContentLength + effectiveOffset : 0
        if http.statusCode == 206 {
            guard let contentRange = http.value(forHTTPHeaderField: "Content-Range"),
                  let rangeValue = contentRange.split(separator: " ").last else {
                throw TrapTubeResolverError.unsupportedManifest("The server returned a partial response without a valid Content-Range header.")
            }
            let rangeParts = rangeValue.split(separator: "/")
            let bounds = rangeParts.first?.split(separator: "-") ?? []
            guard bounds.count == 2, let receivedStart = Int64(bounds[0]),
                  receivedStart == offset else {
                throw TrapTubeResolverError.unsupportedManifest("The server returned a mismatched byte range; the partial file was not appended.")
            }
            if rangeParts.count == 2, let advertisedTotal = Int64(rangeParts[1]), advertisedTotal > 0 {
                total = advertisedTotal
            }
        }
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
        let finalBytes = effectiveOffset + received
        if total > 0 && finalBytes < total {
            if http.statusCode == 200 && offset > 0 {
                throw TrapTubeResolverError.unsupportedManifest("This server ignored the resume range and returned an incomplete response. The partial file was kept, but this source does not currently support byte-range resume.")
            }
            guard rangeAttempt < 16 else {
                throw TrapTubeResolverError.unsupportedManifest("The server repeatedly returned incomplete byte ranges. The partial file was kept; resume the task to continue.")
            }
            return try await download(asset, to: destination, startingAt: finalBytes,
                                      rangeAttempt: rangeAttempt + 1, progress: progress)
        }
        progress(finalBytes, total, 0)
        return destination
    }

    static func downloadSegmented(_ asset: TrapTubeFlatAsset, jobID: String, assetIndex: Int,
                                  directory: URL,
                                  progress: @escaping (Int64, Int64, Int64) -> Void) async throws -> URL {
        guard !asset.segmentURLs.isEmpty else { throw TrapTubeResolverError.noStreams }
        let workDirectory = directory.appendingPathComponent("\(jobID)-\(assetIndex)-segments", isDirectory: true)
        try FileManager.default.createDirectory(at: workDirectory, withIntermediateDirectories: true)
        var pieces: [URL] = []
        var completedBytes: Int64 = 0
        var aggregateTotal: Int64 = 0
        var aggregateSpeed: Int64 = 0

        func fetch(_ url: URL, name: String) async throws {
            let partial = workDirectory.appendingPathComponent(name)
            let marker = workDirectory.appendingPathComponent(name + ".complete")
            let offset = (try? FileManager.default.attributesOfItem(atPath: partial.path)[.size] as? NSNumber)?.int64Value ?? 0
            if FileManager.default.fileExists(atPath: marker.path) {
                completedBytes += offset; aggregateTotal += offset; pieces.append(partial)
                return
            }
            let requestHeaders = await TrapTubeWebCookieBridge.forwarding(asset.headers, from: asset.url, to: url)
            let descriptor = TrapTubeFlatAsset(url: url, kind: asset.kind, mimeType: asset.mimeType,
                height: asset.height, bitrate: asset.bitrate, label: asset.label, isManifest: false,
                headers: requestHeaders)
            var lastTotal: Int64 = 0
            let result = try await download(descriptor, to: partial, startingAt: offset) { bytes, total, speed in
                lastTotal = total
                aggregateSpeed = speed
                progress(completedBytes + bytes, aggregateTotal + total, speed)
            }
            let size = (try? FileManager.default.attributesOfItem(atPath: result.path)[.size] as? NSNumber)?.int64Value ?? 0
            try Data().write(to: marker, options: .atomic)
            completedBytes += size
            aggregateTotal += max(lastTotal, size)
            pieces.append(result)
        }

        if let initializationURL = asset.initializationURL {
            try await fetch(initializationURL, name: "init.partial")
        }
        for (index, segmentURL) in asset.segmentURLs.enumerated() {
            try Task.checkCancellation()
            try await fetch(segmentURL, name: String(format: "segment-%06d.partial", index))
        }

        let outputExtension = asset.mimeType.contains("mpegurl") ? (asset.initializationURL == nil ? "ts" : "mp4") : "mp4"
        let output = directory.appendingPathComponent("\(jobID)-\(assetIndex).segmented.\(outputExtension)")
        if !FileManager.default.fileExists(atPath: output.path) {
            FileManager.default.createFile(atPath: output.path, contents: nil)
        }
        let outputHandle = try FileHandle(forWritingTo: output)
        try outputHandle.truncate(atOffset: 0)
        do {
            for piece in pieces {
                let input = try FileHandle(forReadingFrom: piece)
                defer { try? input.close() }
                while let chunk = try input.read(upToCount: 1_048_576), !chunk.isEmpty {
                    try Task.checkCancellation()
                    try outputHandle.write(contentsOf: chunk)
                }
            }
            try outputHandle.close()
        } catch {
            try? outputHandle.close()
            throw error
        }
        progress(completedBytes, aggregateTotal, aggregateSpeed)
        return output
    }
}

enum TrapTubeMP4Box {
    private static func headerArgument(_ headers: [String: String]) -> String {
        headers.map { "\($0.key): \($0.value)\r\n" }.sorted().joined()
    }

    static func mux(video: URL, audio: URL?, output: URL, videoStreamIndex: Int? = nil,
                    audioStreamIndex: Int? = nil, videoHeaders: [String: String] = [:],
                    audioHeaders: [String: String] = [:],
                    progress: ((Int64, Double) -> Void)? = nil) async throws {
        var args = ["-y"]
        if video.scheme == "http" || video.scheme == "https", !videoHeaders.isEmpty {
            args += ["-headers", headerArgument(videoHeaders)]
        }
        args += ["-i", video.absoluteString.hasPrefix("http") ? video.absoluteString : video.path]
        if let audio {
            if (audio.scheme == "http" || audio.scheme == "https"), !audioHeaders.isEmpty {
                args += ["-headers", headerArgument(audioHeaders)]
            }
            args += ["-i", audio.absoluteString.hasPrefix("http") ? audio.absoluteString : audio.path]
        }
        args += audio == nil
            ? ["-map", videoStreamIndex.map { "0:\($0)" } ?? "0:v?", "-map", "0:a?", "-c", "copy", "-movflags", "+faststart", output.path]
            : ["-map", videoStreamIndex.map { "0:\($0)" } ?? "0:v:0", "-map", audioStreamIndex.map { "1:\($0)" } ?? "1:a:0", "-c", "copy", "-movflags", "+faststart", output.path]
        try await TrapTubeFFmpegProcessor.execute(args, progress: progress)
        guard FileManager.default.fileExists(atPath: output.path) else { throw TrapTubeFFmpegError.missingOutput }
    }

    static func extractAudio(input: URL, output: URL, format: String, streamIndex: Int? = nil,
                             headers: [String: String] = [:],
                             progress: ((Int64, Double) -> Void)? = nil) async throws {
        let codec = format == "wav" ? "pcm_s16le" : "aac"
        var args = ["-y"]
        if (input.scheme == "http" || input.scheme == "https"), !headers.isEmpty {
            args += ["-headers", headerArgument(headers)]
        }
        let inputPath = input.absoluteString.hasPrefix("http") ? input.absoluteString : input.path
        args += ["-i", inputPath, "-map", streamIndex.map { "0:\($0)" } ?? "0:a:0?", "-vn", "-c:a", codec, output.path]
        try await TrapTubeFFmpegProcessor.execute(args, progress: progress)
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

private final class TrapTubeAggregateProgress: @unchecked Sendable {
    private let lock = NSLock()
    private var completedBytes: Int64 = 0
    private var completedTotal: Int64 = 0
    private var currentTotal: Int64 = 0

    func report(bytes: Int64, total: Int64, speed: Int64) -> (Int64, Int64, Int64) {
        lock.lock(); defer { lock.unlock() }
        currentTotal = max(currentTotal, total)
        return (completedBytes + bytes, completedTotal + max(currentTotal, total), speed)
    }

    func finishAsset(actualBytes: Int64) {
        lock.lock(); defer { lock.unlock() }
        completedBytes += actualBytes
        completedTotal += max(currentTotal, actualBytes)
        currentTotal = 0
    }
}

@MainActor
final class TrapTubeDownloadManager: ObservableObject {
    static let shared = TrapTubeDownloadManager()
    @Published private(set) var jobs: [TrapTubeDownloadTask] = []
    @Published private(set) var completed: [TrapTubeDownloadedMedia] = []
    @Published private(set) var availableVideoHeights: [Int] = []
    @Published private(set) var availableAudioBitrates: [Int] = []
    @Published var lastError: String?
    private let resolver = TrapTubeStreamResolver()
    private var workers: [String: Task<Void, Never>] = [:]
    private var workerTokens: [String: UUID] = [:]
    private var manifestURL: URL { TrapTubeDownloadPaths.appDirectory.appendingPathComponent("downloads.json") }
    private var queueURL: URL { TrapTubeDownloadPaths.appDirectory.appendingPathComponent("queue.json") }

    private init() { restore() }

    func inspect(videoURL: URL, title: String) async {
        do {
            let media = try await resolver.resolve(videoURL, title: title)
            availableVideoHeights = Array(Set((media.videoAssets + media.muxedAssets).compactMap(\.height).filter { $0 > 0 })).sorted(by: >)
            availableAudioBitrates = Array(Set((media.audioAssets + media.muxedAssets).compactMap(\.bitrate).filter { $0 > 0 })).sorted(by: >)
            lastError = nil
        } catch {
            availableVideoHeights = []
            availableAudioBitrates = []
            lastError = error.localizedDescription
        }
    }

    private func bestVideoAsset(in assets: [TrapTubeFlatAsset], maximumHeight: Int?) -> TrapTubeFlatAsset? {
        let sorted = assets.sorted { ($0.height ?? 0) < ($1.height ?? 0) }
        guard let maximumHeight else { return sorted.last }
        let eligible = sorted.filter { ($0.height ?? 0) <= maximumHeight }
        return eligible.last ?? sorted.first
    }

    func enqueue(videoURL: URL, title: String, mode: String, quality: String,
                 format: String, bitrate: Int?, height: Int?) async {
        lastError = nil
        do {
            let media = try await resolver.resolve(videoURL, title: title)
            let id = UUID().uuidString
            let chosenVideo = bestVideoAsset(in: media.videoAssets, maximumHeight: height)
            let audioCandidates = media.audioAssets.isEmpty ? media.muxedAssets : media.audioAssets
            let eligibleAudio = audioCandidates.filter { bitrate == nil || ($0.bitrate ?? 0) <= bitrate! }
            let chosenAudio = eligibleAudio.max(by: { ($0.bitrate ?? 0) < ($1.bitrate ?? 0) })
                ?? audioCandidates.max(by: { ($0.bitrate ?? 0) < ($1.bitrate ?? 0) })
            let chosenMuxed = bestVideoAsset(in: media.muxedAssets, maximumHeight: height)
            let separatePairIsBest = chosenVideo != nil && chosenAudio != nil &&
                (chosenMuxed == nil || (chosenVideo?.height ?? 0) >= (chosenMuxed?.height ?? 0))
            let hasSeparatePair = mode != "audio" && separatePairIsBest
            let selectedVideo = mode == "audio" ? nil : (hasSeparatePair ? chosenVideo : (chosenMuxed ?? chosenVideo))
            let selectedAudio = mode == "audio" ? (chosenAudio ?? chosenMuxed) : (hasSeparatePair ? chosenAudio : nil)
            if mode == "audio" && selectedAudio == nil { throw TrapTubeResolverError.noStreams }
            if mode != "audio" && selectedVideo == nil { throw TrapTubeResolverError.noStreams }
            let job = TrapTubeDownloadTask(id: id, title: title, mode: mode, status: "queued", stage: "Streams resolved",
                progress: 0, downloadedBytes: 0, totalBytes: 0, speedBytesPerSecond: 0, error: nil,
                sourceURL: videoURL, selectedVideoURL: selectedVideo?.url, selectedAudioURL: selectedAudio?.url,
                selectedVideoStreamIndex: selectedVideo?.streamIndex, selectedAudioStreamIndex: selectedAudio?.streamIndex,
                selectedVideoRepresentationID: selectedVideo?.representationID, selectedAudioRepresentationID: selectedAudio?.representationID,
                selectedVideoHeight: selectedVideo?.height, selectedVideoBitrate: selectedVideo?.bitrate,
                selectedAudioBitrate: selectedAudio?.bitrate,
                selectedVideoMimeType: selectedVideo?.mimeType, selectedAudioMimeType: selectedAudio?.mimeType,
                outputFormat: format, partialFileName: nil, outputFileName: nil, resumeOffset: 0)
            jobs.insert(job, at: 0)
            persistQueue()
            start(jobID: id, media: media, video: selectedVideo, audio: selectedAudio, format: format)
        } catch { lastError = error.localizedDescription }
    }

    private func start(jobID: String, media: TrapTubeResolvedMedia, video: TrapTubeFlatAsset?,
                       audio: TrapTubeFlatAsset?, format: String) {
        workers[jobID]?.cancel()
        let token = UUID()
        workerTokens[jobID] = token
        workers[jobID] = Task { [weak self] in
            await self?.run(jobID: jobID, workerToken: token, media: media, video: video, audio: audio, format: format)
        }
    }

    private func updateJob(_ id: String, _ update: (inout TrapTubeDownloadTask) -> Void) {
        guard let index = jobs.firstIndex(where: { $0.id == id }) else { return }
        update(&jobs[index])
        persistQueue()
    }

    private func run(jobID: String, workerToken: UUID, media: TrapTubeResolvedMedia, video: TrapTubeFlatAsset?,
                     audio: TrapTubeFlatAsset?, format: String) async {
        defer {
            if workerTokens[jobID] == workerToken {
                workers[jobID] = nil
                workerTokens[jobID] = nil
            }
        }
        guard jobs.contains(where: { $0.id == jobID }) else { return }
        updateJob(jobID) { $0.status = "running"; $0.stage = "Downloading streams"; $0.error = nil }
        do {
            let dir = TrapTubeDownloadPaths.downloadsDirectory
            try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
            var inputURLs: [URL] = []
            let aggregate = TrapTubeAggregateProgress()
            let assets = [video, audio].compactMap { $0 }

            for (assetIndex, asset) in assets.enumerated() {
                try Task.checkCancellation()
                let ext = asset.isManifest
                    ? (asset.mimeType.contains("mpegurl") ? "m3u8" : "mpd")
                    : (asset.url.pathExtension.isEmpty ? "media" : asset.url.pathExtension)
                let partialName = "\(jobID)-\(assetIndex).partial.\(ext)"
                let partialURL = dir.appendingPathComponent(partialName)
                let offset = (try? FileManager.default.attributesOfItem(atPath: partialURL.path)[.size] as? NSNumber)?.int64Value ?? 0

                if asset.isManifest && asset.segmentURLs.isEmpty {
                    updateJob(jobID) { $0.partialFileName = partialName; $0.resumeOffset = 0; $0.stage = "Preparing manifest input" }
                    inputURLs.append(asset.url)
                    continue
                }

                updateJob(jobID) {
                    $0.partialFileName = asset.segmentURLs.isEmpty ? partialName : "\(jobID)-\(assetIndex)-segments"
                    $0.resumeOffset = offset
                    $0.stage = asset.segmentURLs.isEmpty ? "Downloading media stream" : "Downloading DASH segments"
                }

                let progressHandler: (Int64, Int64, Int64) -> Void = { [weak self] bytes, total, speed in
                    let snapshot = aggregate.report(bytes: bytes, total: total, speed: speed)
                    Task { @MainActor in
                        guard let self, self.workerTokens[jobID] == workerToken else { return }
                        self.updateJob(jobID) {
                            $0.downloadedBytes = snapshot.0
                            $0.totalBytes = snapshot.1
                            $0.speedBytesPerSecond = snapshot.2
                            $0.progress = snapshot.1 > 0 ? min(0.98, Double(snapshot.0) / Double(snapshot.1)) : 0
                        }
                    }
                }

                let downloaded: URL
                if !asset.segmentURLs.isEmpty {
                    downloaded = try await TrapTubeFlatTransfer.downloadSegmented(asset, jobID: jobID,
                        assetIndex: assetIndex, directory: dir, progress: progressHandler)
                } else {
                    downloaded = try await TrapTubeFlatTransfer.download(asset, to: partialURL,
                        startingAt: offset, progress: progressHandler)
                }
                inputURLs.append(downloaded)
                let actualSize = (try? FileManager.default.attributesOfItem(atPath: downloaded.path)[.size] as? NSNumber)?.int64Value ?? 0
                aggregate.finishAsset(actualBytes: actualSize)
            }

            guard let first = inputURLs.first else { throw TrapTubeResolverError.noStreams }
            let isAudioOnly = modeFor(jobID) == "audio"
            let outputExt = isAudioOnly ? (format == "wav" ? "wav" : "m4a") : "mp4"
            let outputName = "\(jobID).\(outputExt)"
            let outputURL = dir.appendingPathComponent(outputName)
            updateJob(jobID) { $0.stage = "Muxing / finalizing"; $0.speedBytesPerSecond = 0 }

            let rateMeter = TrapTubeTransferRateMeter()
            let stats: (Int64, Double) -> Void = { [weak self] bytes, _ in
                let measuredSpeed = rateMeter.update(bytes)
                Task { @MainActor in
                    guard let self, self.workerTokens[jobID] == workerToken else { return }
                    self.updateJob(jobID) {
                        $0.stage = "Processing stream"
                        $0.downloadedBytes = bytes
                        $0.speedBytesPerSecond = measuredSpeed
                    }
                }
            }

            if isAudioOnly {
                let audioAsset = audio ?? video
                try await TrapTubeMP4Box.extractAudio(input: first, output: outputURL, format: outputExt,
                    streamIndex: audioAsset?.isManifest == true || audioAsset?.segmentURLs.isEmpty == false ? nil : audioAsset?.streamIndex,
                    headers: audioAsset?.headers ?? [:], progress: stats)
            } else {
                let videoAsset = video
                let audioAsset = audio
                try await TrapTubeMP4Box.mux(video: first, audio: inputURLs.count > 1 ? inputURLs[1] : nil,
                    output: outputURL,
                    videoStreamIndex: videoAsset?.isManifest == true || videoAsset?.segmentURLs.isEmpty == false ? nil : videoAsset?.streamIndex,
                    audioStreamIndex: audioAsset?.isManifest == true || audioAsset?.segmentURLs.isEmpty == false ? nil : audioAsset?.streamIndex,
                    videoHeaders: videoAsset?.headers ?? [:], audioHeaders: audioAsset?.headers ?? [:], progress: stats)
            }

            guard workerTokens[jobID] == workerToken else { return }
            let size = (try? FileManager.default.attributesOfItem(atPath: outputURL.path)[.size] as? NSNumber)?.int64Value ?? 0
            let item = TrapTubeDownloadedMedia(id: UUID().uuidString, title: media.title, fileName: outputName,
                mode: modeFor(jobID), sizeBytes: size, createdAt: Date())
            completed.insert(item, at: 0)
            persistCompleted()
            updateJob(jobID) {
                $0.status = "saved"
                $0.stage = "Saved to device"
                $0.progress = 1
                $0.outputFileName = outputName
                $0.speedBytesPerSecond = 0
            }
        } catch is CancellationError {
            guard workerTokens[jobID] == workerToken else { return }
            updateJob(jobID) { $0.status = "paused"; $0.stage = "Paused · can resume" }
        } catch {
            guard workerTokens[jobID] == workerToken else { return }
            updateJob(jobID) {
                if Task.isCancelled {
                    $0.status = "paused"
                    $0.stage = "Paused · resume available"
                } else {
                    $0.status = "failed"
                    $0.error = error.localizedDescription
                }
            }
        }
    }

    private func modeFor(_ id: String) -> String { jobs.first(where: { $0.id == id })?.mode ?? "video" }

    func cancel(_ id: String) async {
        workers[id]?.cancel(); workers[id] = nil; workerTokens[id] = nil
        if let i = jobs.firstIndex(where: { $0.id == id }) { jobs[i].status = "paused"; jobs[i].stage = "Paused · can resume"; persistQueue() }
    }

    private func restoredVideoAsset(in media: TrapTubeResolvedMedia, for job: TrapTubeDownloadTask) -> TrapTubeFlatAsset? {
        let candidates = media.videoAssets + media.muxedAssets
        if let representationID = job.selectedVideoRepresentationID,
           let match = candidates.first(where: { $0.representationID == representationID }) { return match }
        if let mime = job.selectedVideoMimeType, let height = job.selectedVideoHeight,
           let bitrate = job.selectedVideoBitrate,
           let match = candidates.first(where: { $0.mimeType == mime && $0.height == height && $0.bitrate == bitrate }) { return match }
        if let mime = job.selectedVideoMimeType, let height = job.selectedVideoHeight,
           let match = candidates.first(where: { $0.mimeType == mime && $0.height == height }) { return match }
        if let url = job.selectedVideoURL,
           let match = candidates.first(where: { $0.url == url && $0.streamIndex == job.selectedVideoStreamIndex }) { return match }
        if let height = job.selectedVideoHeight {
            let eligible = candidates.filter { ($0.height ?? 0) <= height }
            return eligible.max { ($0.height ?? 0) < ($1.height ?? 0) }
        }
        return candidates.max { ($0.height ?? 0) < ($1.height ?? 0) }
    }

    private func restoredAudioAsset(in media: TrapTubeResolvedMedia, for job: TrapTubeDownloadTask) -> TrapTubeFlatAsset? {
        let candidates = media.audioAssets + media.muxedAssets
        if let representationID = job.selectedAudioRepresentationID,
           let match = candidates.first(where: { $0.representationID == representationID }) { return match }
        if let mime = job.selectedAudioMimeType,
           let match = candidates.first(where: { $0.mimeType == mime && $0.bitrate == job.selectedAudioBitrate }) { return match }
        if let url = job.selectedAudioURL,
           let match = candidates.first(where: { $0.url == url && $0.streamIndex == job.selectedAudioStreamIndex }) { return match }
        guard job.mode == "audio" else { return nil }
        return candidates.max { ($0.bitrate ?? 0) < ($1.bitrate ?? 0) }
    }

    func resume(_ id: String) {
        guard let job = jobs.first(where: { $0.id == id }), let source = job.sourceURL else { return }
        Task {
            do {
                let media = try await resolver.resolve(source, title: job.title)
                let selectedVideo = restoredVideoAsset(in: media, for: job)
                let selectedAudio = restoredAudioAsset(in: media, for: job)
                let video = job.mode == "audio" ? nil : selectedVideo
                start(jobID: id, media: media, video: video, audio: selectedAudio,
                      format: job.outputFormat ?? (job.mode == "audio" ? "m4a" : "mp4"))
            } catch {
                lastError = error.localizedDescription
            }
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
            jobs = saved.map { job in
                var copy = job
                if copy.status == "running" || copy.status == "queued" {
                    copy.status = "paused"
                    copy.stage = "Paused · resume available"
                }
                return copy
            }
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

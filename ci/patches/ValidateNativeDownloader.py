#!/usr/bin/env python3
from pathlib import Path
import sys

service, player, settings = map(lambda value: Path(value).read_text(), sys.argv[1:4])
combined = "\n".join((service, player, settings))
required = {
    "TrapTubeStreamResolver": service,
    "TrapTubeProviderRegistry": service,
    "static var builtIn": service,
    "func registering(_ adapter:": service,
    "func removing(providerIdentifier:": service,
    "func adapter(for source: URL)": service,
    "providerIdentifier": service,
    "TrapTubeYouTubeAdapter": service,
    "formatURL(from row:": service,
    "signatureCipher": service,
    "TrapTubeFlatTransfer": service,
    "TrapTubeDownloadTask": service,
    "TrapTubeMP4Box": service,
    "TrapTubeDownloadManager": service,
    "SegmentTemplate": service,
    "SegmentTimeline": service,
    "inferredPeriodDuration": service,
    "BYTERANGE=": service,
    "rangeAttempt": service,
    "Content-Range": service,
    "Content-Disposition": service,
    "signatureExtension": service,
    "availableAudioBitrates": service,
    "selectedVideoBitrate": service,
    "outputFormat": service,
    "workerTokens": service,
    "bestVideoAsset": service,
    "downloadSegmented": service,
    "chunkSize: Int64 = 4 * 1024 * 1024": service,
    "nativeFirst": service,
    "boundedGET": service,
    "xmlUnescape": service,
    'splitElements("Representation", in: adaptationBody)': service,
    "parseHLSMediaPlaylist": service,
    '["-map", videoStreamIndex.map { "0:\\($0)" } ?? "0:v:0"': service,
    '"-vn"': service,
    "Content-Range": service,
    "startingAt offset": service,
    "maximumConcurrentTransfers": service,
    "TrapTubeWebCookieBridge": service,
    "TrapTubeAggregateProgress": service,
    'setValue("bytes=': service,
    "resume(_ id: String)": service,
    "queue.json": service,
    "StreamingHomeWebView": player,
    "YouTubeWatchSheet": player,
    "lastLoaded": player,
    'document.querySelectorAll("video, audio")': player,
    "const mediaGraphs = new WeakMap();": player,
    "const chooseMediaElement = () => {": player,
    "activeSource.connect(filters[0])": player,
    "YouTubePlayerWebView(": player,
    "gains: player.eqGains": player,
    "master: player.masterGain": player,
    "discoveryPlaceholder": player,
    "latestVideoTitle = title": player,
    "postWatch(target, anchor)": player,
    "history[method] = function": player,
    "This HLS playlist is encrypted": service,
    "TrapTubeHuePicker": settings,
    "TrapTube discovery tab": settings,
    "hexString(initialColor)": settings,
    "AngularGradient": settings,
    "LinearGradient(colors: [.white, .clear]": settings,
    "brightness = 1 -": settings,
    "availableAudioBitrates": player,
    "WAV · PCM": player,
    "TrapTubeYouTubeActionSheet": player,
    "TrapTubeDownloadOptionsSheet": player,
    "sectionHeader(icon:": player,
    "Download options": player,
    "Open TrapTube video actions": player,
    "availableVideoCodecs": service,
    "codec: mode == \"video\" ? codec : nil": player,
    "case convertMP3": service,
    "libmp3lame": service,
    "saveThumbnail(videoID: String": service,
    "youtubeVideoID": player,
    "rawMime": service,
}
missing = [name for name, source in required.items() if name not in source]
if missing:
    raise SystemExit("Native downloader validation failed; missing: " + ", ".join(missing))

legacy_marker = "Type" + "Type"
forbidden = (legacy_marker, "type" + "type", "v" + "ds-")
found = [token for token in forbidden if token.lower() in combined.lower()]
if found:
    raise SystemExit("Obsolete provider identifiers remain in runtime overlays: " + ", ".join(found))

if "import ffmpegkit" not in service or "import WebKit" not in service:
    raise SystemExit("Downloader framework imports are incomplete.")

print("Native downloader source checks passed.")

#!/usr/bin/env python3
from pathlib import Path
import sys

service, player, settings = map(lambda value: Path(value).read_text(), sys.argv[1:4])
combined = "\n".join((service, player, settings))
required = {
    "TrapTubeStreamResolver": service,
    "TrapTubeYouTubeAdapter": service,
    "TrapTubeFlatTransfer": service,
    "TrapTubeDownloadTask": service,
    "TrapTubeMP4Box": service,
    "TrapTubeDownloadManager": service,
    "SegmentTemplate": service,
    "SegmentTimeline": service,
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
    "parseHLSMediaPlaylist": service,
    "TrapTubeWebCookieBridge": service,
    "TrapTubeAggregateProgress": service,
    "workerTokens": service,
    'setValue("bytes=': service,
    "resume(_ id: String)": service,
    "queue.json": service,
    "StreamingHomeWebView": player,
    "YouTubeWatchSheet": player,
    "TrapTubeHuePicker": settings,
    "AngularGradient": settings,
    "availableAudioBitrates": player,
    "WAV · PCM": player,
}
missing = [name for name, source in required.items() if name not in source]
if missing:
    raise SystemExit("Native downloader validation failed; missing: " + ", ".join(missing))

legacy_marker = "Type" + "Type"
forbidden = (legacy_marker, "typetype", "vds-")
found = [token for token in forbidden if token.lower() in combined.lower()]
if found:
    raise SystemExit("Obsolete provider identifiers remain in runtime overlays: " + ", ".join(found))

if "import ffmpegkit" not in service or "import WebKit" not in service:
    raise SystemExit("Downloader framework imports are incomplete.")

print("Native downloader source checks passed.")

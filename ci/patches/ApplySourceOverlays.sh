#!/usr/bin/env bash
set -euo pipefail
ROOT="$1"
test -d "$ROOT"
test -f "$ROOT/TrapTube.xcodeproj/project.pbxproj"
test -s ci/patches/AudioEngineManager.swift
test -s ci/patches/LibraryStore.swift
test -s ci/patches/StemStudioView.swift
test -s ci/patches/KeepImportAction.py
test -s ci/patches/FFmpegKit-LICENSE
test -s ci/patches/FFmpegKit-NOTICE.md
test -s ci/demucs-smoke/Package.swift
test -s ci/demucs-smoke/Sources/DemucsSmoke/main.swift

SERVICE_SOURCE="$(find "$ROOT" -type f -name AudioEngineManager.swift -print -quit)"
VIEW_SOURCE="$(find "$ROOT" -type f -name HomeView.swift -print -quit)"
MODEL_SOURCE="$(find "$ROOT" -type f -name Track.swift -print -quit)"
COMPONENTS_FILE="$(find "$ROOT" -type f -name Components.swift -print -quit)"
PROJECT_FILE="$(find "$ROOT" -type f -name project.pbxproj -print -quit)"
test -n "$SERVICE_SOURCE" && test -n "$VIEW_SOURCE" && test -n "$MODEL_SOURCE" && test -n "$COMPONENTS_FILE" && test -n "$PROJECT_FILE"

SERVICES_DIR="$(dirname "$SERVICE_SOURCE")"
VIEWS_DIR="$(dirname "$VIEW_SOURCE")"
MODELS_DIR="$(dirname "$MODEL_SOURCE")"
cp ci/patches/AudioEngineManager.swift "$SERVICES_DIR/AudioEngineManager.swift"
cp ci/patches/LibraryStore.swift "$SERVICES_DIR/LibraryStore.swift"
cp ci/patches/ThemeManager.swift "$SERVICES_DIR/ThemeManager.swift"
cp ci/patches/MediaDownloadService.swift "$SERVICES_DIR/MediaDownloadService.swift"
python3 ci/patches/RenameLegacyDownloadService.py "$SERVICES_DIR" "$PROJECT_FILE"
cp ci/patches/GoogleYouTubeAuth.swift "$SERVICES_DIR/GoogleYouTubeAuth.swift"
cp ci/patches/StemSeparationService.swift "$SERVICES_DIR/StemSeparationService.swift"
cp ci/patches/SettingsView.swift "$VIEWS_DIR/SettingsView.swift"
cp ci/patches/YouTubeView.swift "$VIEWS_DIR/YouTubeView.swift"
cp ci/patches/StemStudioView.swift "$VIEWS_DIR/StemStudioView.swift"
cp ci/patches/HTDemucs-ATTRIBUTION.md "$MODELS_DIR/HTDemucs-ATTRIBUTION.md"

python3 ci/patches/KeepImportAction.py "$ROOT"
python3 ci/patches/ApplyVisualFeatures.py "$ROOT"
python3 ci/patches/ValidateNativeDownloader.py \
  "$SERVICES_DIR/MediaDownloadService.swift" \
  "$VIEWS_DIR/YouTubeView.swift" \
  "$VIEWS_DIR/SettingsView.swift"
python3 - "$COMPONENTS_FILE" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
source = path.read_text().replace('title: "YouTube"', 'title: "TrapTube"')
path.write_text(source)
PY
echo "TrapTube runtime overlays applied and validated."

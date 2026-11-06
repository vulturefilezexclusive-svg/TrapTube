from pathlib import Path
import sys

root = Path(sys.argv[1])

home = root / "TrapTube/Views/HomeView.swift"
source = home.read_text()
home_anchor = """                if !library.recentlyPlayed.isEmpty {
                    VStack(alignment: .leading, spacing: 8) {
                        SectionHeading(title: "Recently played", trailing: "On this device")
                        ForEach(library.recentlyPlayed.prefix(4)) { track in TrackRow(track: track, queue: library.recentlyPlayed) }
                    }
                    .padding(.horizontal, 16)
                }
"""
home_add = home_anchor + """
                Button { showImporter = true } label: {
                    Label(library.tracks.isEmpty ? "Import audio" : "Import more audio", systemImage: "plus")
                        .font(.headline.bold()).foregroundStyle(.white)
                        .frame(maxWidth: .infinity).padding(.vertical, 15)
                        .background(theme.accent, in: Capsule())
                }
                .buttonStyle(.plain)
                .accessibilityHint("Choose additional audio files to add to your local library")
                .padding(.horizontal, 16)
"""
if 'Label(library.tracks.isEmpty ? "Import audio" : "Import more audio"' not in source:
    if home_anchor not in source:
        raise SystemExit("HomeView import anchor not found; refusing to patch an unknown layout.")
    source = source.replace(home_anchor, home_add, 1)
    duplicate = """            Button { showImporter = true } label: {
                Label("Import audio", systemImage: "plus")
                    .font(.headline.bold()).foregroundStyle(.white)
                    .padding(.horizontal, 22).padding(.vertical, 13)
                    .background(theme.accent, in: Capsule())
            }
            .padding(.top, 4)
"""
    source = source.replace(duplicate, "", 1)
    home.write_text(source)

library = root / "TrapTube/Views/LibraryView.swift"
source = library.read_text()
old = """                if section != .playlists {
                    Button { showImporter = true } label: {
                        Label("Import audio", systemImage: "plus")
                            .font(.headline.bold()).foregroundStyle(.white)
                            .frame(maxWidth: .infinity).padding(.vertical, 15)
                            .background(theme.accent, in: Capsule())
                    }
                    .padding(.horizontal, 16)
                }
"""
new = """                Button { showImporter = true } label: {
                    Label(library.tracks.isEmpty ? "Import audio" : "Import more audio", systemImage: "plus")
                        .font(.headline.bold()).foregroundStyle(.white)
                        .frame(maxWidth: .infinity).padding(.vertical, 15)
                        .background(theme.accent, in: Capsule())
                }
                .buttonStyle(.plain)
                .accessibilityHint("Choose additional audio files to add to your local library")
                .padding(.horizontal, 16)
"""
if 'Label(library.tracks.isEmpty ? "Import audio" : "Import more audio"' not in source:
    if old not in source:
        raise SystemExit("LibraryView import anchor not found; refusing to patch an unknown layout.")
    source = source.replace(old, new, 1)
    library.write_text(source)

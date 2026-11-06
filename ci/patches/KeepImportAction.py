from pathlib import Path
import sys

root = Path(sys.argv[1])

home_anchor = """                if !library.recentlyPlayed.isEmpty {
                    VStack(alignment: .leading, spacing: 8) {
                        SectionHeading(title: "Recently played", trailing: "On this device")
                        ForEach(library.recentlyPlayed.prefix(4)) { track in TrackRow(track: track, queue: library.recentlyPlayed) }
                    }
                    .padding(.horizontal, 16)
                }
"""
library_anchor = """                if section != .playlists {
                    Button { showImporter = true } label: {
                        Label("Import audio", systemImage: "plus")
                            .font(.headline.bold()).foregroundStyle(.white)
                            .frame(maxWidth: .infinity).padding(.vertical, 15)
                            .background(theme.accent, in: Capsule())
                    }
                    .padding(.horizontal, 16)
                }
"""

def find_unique_with_anchor(filename, anchor):
    matches = [path for path in root.rglob(filename) if anchor in path.read_text()]
    if len(matches) != 1:
        raise SystemExit(f"Expected one {filename} containing the known import anchor; found {len(matches)}.")
    return matches[0]

home = find_unique_with_anchor("HomeView.swift", home_anchor)
source = home.read_text()
if 'Label(library.tracks.isEmpty ? "Import audio" : "Import more audio"' not in source:
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

library = find_unique_with_anchor("LibraryView.swift", library_anchor)
source = library.read_text()
if 'Label(library.tracks.isEmpty ? "Import audio" : "Import more audio"' not in source:
    library_add = """                Button { showImporter = true } label: {
                    Label(library.tracks.isEmpty ? "Import audio" : "Import more audio", systemImage: "plus")
                        .font(.headline.bold()).foregroundStyle(.white)
                        .frame(maxWidth: .infinity).padding(.vertical, 15)
                        .background(theme.accent, in: Capsule())
                }
                .buttonStyle(.plain)
                .accessibilityHint("Choose additional audio files to add to your local library")
                .padding(.horizontal, 16)
"""
    source = source.replace(library_anchor, library_add, 1)
    library.write_text(source)

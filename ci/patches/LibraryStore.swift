import AVFoundation
import Foundation
import Combine

@MainActor
final class LibraryStore: ObservableObject {
    @Published private(set) var tracks: [Track] = []
    @Published private(set) var playlists: [LocalPlaylist] = []
    @Published private(set) var recentTrackIDs: [UUID] = []
    @Published var alertMessage: String?

    private let fileManager = FileManager.default
    private let metadataURL: URL

    static var appDirectory: URL {
        FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("TrapTube", isDirectory: true)
    }

    static var tracksDirectory: URL { appDirectory.appendingPathComponent("Tracks", isDirectory: true) }
    static func audioURL(for fileName: String) -> URL { tracksDirectory.appendingPathComponent(fileName).standardizedFileURL }

    init() {
        try? fileManager.createDirectory(at: Self.tracksDirectory, withIntermediateDirectories: true)
        metadataURL = Self.appDirectory.appendingPathComponent("library.json")
        load()
    }

    var totalStorageBytes: Int64 { tracks.reduce(0) { $0 + $1.fileSizeBytes } }
    var recentlyPlayed: [Track] { recentTrackIDs.compactMap { id in tracks.first(where: { $0.id == id }) } }

    func importAudio(from urls: [URL]) async {
        var messages: [String] = []
        for sourceURL in urls {
            let source = sourceURL.standardizedFileURL
            let accessed = source.startAccessingSecurityScopedResource()
            defer { if accessed { source.stopAccessingSecurityScopedResource() } }
            var destination: URL?
            do {
                try fileManager.createDirectory(at: Self.tracksDirectory, withIntermediateDirectories: true)
                let ext = source.pathExtension.isEmpty ? "audio" : source.pathExtension.lowercased()
                let fileName = "\(UUID().uuidString).\(ext)"
                let target = Self.audioURL(for: fileName)
                destination = target
                try fileManager.copyItem(at: source, to: target)

                let attributes = try fileManager.attributesOfItem(atPath: target.path)
                let size = (attributes[.size] as? NSNumber)?.int64Value ?? 0
                guard size > 0 else { throw ImportError.emptyFile }

                let asset = AVURLAsset(url: target)
                let audioTracks = try await asset.loadTracks(withMediaType: .audio)
                guard !audioTracks.isEmpty else { throw ImportError.noAudioTrack }
                let loadedDuration = try await asset.load(.duration).seconds
                let duration = loadedDuration.isFinite && loadedDuration > 0 ? loadedDuration : 0
                let title = source.deletingPathExtension().lastPathComponent
                tracks.insert(
                    Track(title: title, artist: "Unknown artist", fileName: fileName, duration: duration, fileSizeBytes: size),
                    at: 0
                )
            } catch {
                if let destination { try? fileManager.removeItem(at: destination) }
                let nsError = error as NSError
                messages.append("\(source.lastPathComponent): \(error.localizedDescription) (\(nsError.domain) / \(nsError.code))")
            }
        }
        persist()
        if !messages.isEmpty { alertMessage = messages.joined(separator: "\n") }
    }

    enum ImportError: LocalizedError {
        case emptyFile, noAudioTrack
        var errorDescription: String? {
            switch self {
            case .emptyFile: return "The selected file is empty."
            case .noAudioTrack: return "This file does not contain a playable audio track."
            }
        }
    }

    func markPlayed(_ track: Track) {
        recentTrackIDs.removeAll { $0 == track.id }
        recentTrackIDs.insert(track.id, at: 0)
        recentTrackIDs = Array(recentTrackIDs.prefix(30))
        persist()
    }

    func setGenre(_ genre: String?, for track: Track) {
        guard let index = tracks.firstIndex(where: { $0.id == track.id }) else { return }
        tracks[index].genre = genre
        persist()
    }

    func createPlaylist(named name: String) {
        let cleanName = name.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !cleanName.isEmpty else { return }
        playlists.insert(LocalPlaylist(name: cleanName), at: 0)
        persist()
    }

    func add(_ track: Track, to playlist: LocalPlaylist) {
        guard let index = playlists.firstIndex(where: { $0.id == playlist.id }), !playlists[index].trackIDs.contains(track.id) else { return }
        playlists[index].trackIDs.append(track.id)
        persist()
    }

    func remove(_ track: Track, from playlist: LocalPlaylist) {
        guard let index = playlists.firstIndex(where: { $0.id == playlist.id }) else { return }
        playlists[index].trackIDs.removeAll { $0 == track.id }
        persist()
    }

    func tracks(in playlist: LocalPlaylist) -> [Track] {
        playlist.trackIDs.compactMap { id in tracks.first(where: { $0.id == id }) }
    }

    func delete(_ track: Track) {
        try? fileManager.removeItem(at: Self.audioURL(for: track.fileName))
        tracks.removeAll { $0.id == track.id }
        recentTrackIDs.removeAll { $0 == track.id }
        for index in playlists.indices { playlists[index].trackIDs.removeAll { $0 == track.id } }
        persist()
    }

    private func load() {
        guard let data = try? Data(contentsOf: metadataURL), let snapshot = try? JSONDecoder().decode(LibrarySnapshot.self, from: data) else { return }
        tracks = snapshot.tracks.filter { fileManager.fileExists(atPath: Self.audioURL(for: $0.fileName).path) }
        playlists = snapshot.playlists
        recentTrackIDs = snapshot.recentTrackIDs
    }

    private func persist() {
        let snapshot = LibrarySnapshot(tracks: tracks, playlists: playlists, recentTrackIDs: recentTrackIDs)
        do {
            try fileManager.createDirectory(at: Self.appDirectory, withIntermediateDirectories: true)
            try JSONEncoder().encode(snapshot).write(to: metadataURL, options: .atomic)
        } catch {
            alertMessage = "Could not save the music library: \(error.localizedDescription)"
        }
    }
}
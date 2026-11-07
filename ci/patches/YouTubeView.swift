import SwiftUI
import WebKit
import AVKit
import UIKit
import SafariServices

struct YouTubeView: View {
    @State private var didLaunchYouTube = false
    @State private var showYouTube = false
    @AppStorage("discovery.sourceURL") private var discoverySourceURL = ""

    private var homeURL: URL {
        let raw = discoverySourceURL.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let url = URL(string: raw), let scheme = url.scheme?.lowercased(), ["http", "https"].contains(scheme), url.host != nil else {
            return URL(string: "https://www.youtube.com/")!
        }
        return url
    }

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()
            VStack(spacing: 14) {
                ProgressView().tint(.white)
                Text("Opening Streaming Home").font(.headline).foregroundStyle(.white)
                Text("Your selected streaming website opens here. Set its address in Settings → Video discovery.")
                    .font(.caption).foregroundStyle(.white.opacity(0.65))
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 28)
            }
        }
        .onAppear {
            guard !didLaunchYouTube else { return }
            didLaunchYouTube = true
            showYouTube = true
        }
        .fullScreenCover(isPresented: $showYouTube) {
            YouTubeSafariView(url: homeURL)
                .ignoresSafeArea()
        }
    }
}

private struct YouTubeSafariView: UIViewControllerRepresentable {
    let url: URL

    func makeUIViewController(context: Context) -> SFSafariViewController {
        let configuration = SFSafariViewController.Configuration()
        configuration.entersReaderIfAvailable = false
        let controller = SFSafariViewController(url: url, configuration: configuration)
        controller.preferredControlTintColor = .systemPurple
        return controller
    }

    func updateUIViewController(_ controller: SFSafariViewController, context: Context) {}
}

private struct TrapTubePlayerMenu: View {
    @Environment(\.dismiss) private var dismiss
    let title: String
    let videoURL: URL
    let onPlayback: () -> Void

    @State private var showDownloads = false
    @State private var showMenuInfo = false
    @State private var menuInfoText = ""

    var body: some View {
        VStack(spacing: 0) {
            Capsule().fill(.white.opacity(0.35)).frame(width: 42, height: 5)
                .padding(.top, 10).padding(.bottom, 18)

            HStack(spacing: 12) {
                Image(uiImage: UIImage(named: "TrapTubeIcon") ?? UIImage(systemName: "app.fill")!).resizable().scaledToFill().frame(width: 54, height: 54)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                VStack(alignment: .leading, spacing: 4) {
                    Text(title).font(.headline.bold()).foregroundStyle(.white).lineLimit(1)
                    Text("TrapTube player").font(.caption.weight(.medium)).foregroundStyle(Color(hex: "A6A4A6"))
                }
                Spacer()
                Button { dismiss() } label: {
                    Image(systemName: "xmark").font(.headline.bold()).foregroundStyle(.white)
                        .frame(width: 38, height: 38).background(.white.opacity(0.12), in: Circle())
                }
                .accessibilityLabel("Close player menu")
            }
            .padding(.horizontal, 20).padding(.bottom, 14)

            ScrollView(showsIndicators: false) {
                VStack(spacing: 0) {
                    menuRow("Downloads", detail: "Video · Audio · Cover art", icon: "arrow.down.to.line") {
                        showDownloads = true
                    }
                    menuRow("Playback tools", detail: "Equalizer · Bass boost · Audio modes", icon: "waveform") {
                        dismiss()
                        onPlayback()
                    }
                    menuRow("Library", detail: "Your downloaded and imported media", icon: "rectangle.stack") {
                        menuInfoText = "Your downloaded media and imported tracks are stored in TrapTube's local library."
                        showMenuInfo = true
                    }
                    menuRow("Transcript", detail: "Available captions and transcript tools", icon: "captions.bubble") {
                        menuInfoText = "Transcript access depends on captions exposed by the selected streaming provider."
                        showMenuInfo = true
                    }
                    menuRow("Information", detail: "Media and stream information", icon: "info.circle") {
                        menuInfoText = "Playback and stream information depend on the selected provider and exposed media metadata."
                        showMenuInfo = true
                    }
                }
                .padding(.horizontal, 20)
            }

            Button("Close") { dismiss() }
                .font(.headline.bold()).foregroundStyle(.white).padding(.vertical, 18)
        }
        .background(Color(hex: "171618").ignoresSafeArea())
        .sheet(isPresented: $showDownloads) {
            TrapTubeDownloadsSheet(title: title, videoURL: videoURL)
                .presentationDetents([.large])
                .presentationDragIndicator(.visible)
                .preferredColorScheme(.dark)
        }
        .alert("TrapTube", isPresented: $showMenuInfo) {
            Button("OK", role: .cancel) { }
        } message: {
            Text(menuInfoText)
        }
    }

    private func menuRow(_ title: String, detail: String, icon: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(spacing: 15) {
                Image(systemName: icon).font(.system(size: 22, weight: .semibold))
                    .foregroundStyle(.white).frame(width: 32)
                VStack(alignment: .leading, spacing: 4) {
                    Text(title).font(.headline.bold()).foregroundStyle(.white)
                    Text(detail).font(.caption).foregroundStyle(Color(hex: "A6A4A6"))
                        .lineLimit(1)
                }
                Spacer(minLength: 8)
                Image(systemName: "chevron.right").font(.caption.bold())
                    .foregroundStyle(Color(hex: "8E8B90"))
            }
            .padding(.vertical, 16)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .overlay(alignment: .bottom) {
            Rectangle().fill(.white.opacity(0.08)).frame(height: 1)
        }
    }
}

private struct TrapTubeDownloadsSheet: View {
    @Environment(\.dismiss) private var dismiss
    @EnvironmentObject private var library: LibraryStore
    @StateObject private var manager = TrapTubeDownloadManager.shared

    let title: String
    let videoURL: URL

    @State private var mode = "video"
    @State private var quality = "best"
    @State private var format = "mp4"
    @AppStorage("video.preferredQuality") private var preferredVideoQuality = "auto"
    @State private var selectedVideo: TrapTubeDownloadedMedia?

    private var modeTitle: String {
        mode == "audio" ? "Audio" : "Video"
    }

    var body: some View {
        NavigationView {
            ScrollView(showsIndicators: false) {
                VStack(alignment: .leading, spacing: 18) {
                    VStack(alignment: .leading, spacing: 5) {
                        Text("DOWNLOAD MEDIA").font(.caption.bold()).tracking(1.4)
                            .foregroundStyle(Color(hex: "A6A4A6"))
                        Text(title).font(.title3.bold()).foregroundStyle(.white).lineLimit(2)
                        Text("TrapTube resolves exposed media streams, downloads supported assets locally, and merges compatible video/audio tracks on this device.")
                            .font(.caption).foregroundStyle(Color(hex: "A6A4A6"))
                    }

                    VStack(alignment: .leading, spacing: 12) {
                        Text("Download type").font(.headline.bold()).foregroundStyle(.white)
                        Picker("Download type", selection: $mode) {
                            Text("Video").tag("video")
                            Text("Audio").tag("audio")
                        }
                        .pickerStyle(.segmented)
                        .onChange(of: mode) { _, newMode in
                            quality = newMode == "video" && preferredVideoQuality != "auto"
                                ? "\(preferredVideoQuality)p" : "best"
                            format = newMode == "audio" ? "m4a" : "mp4"
                        }

                        if mode == "video" || mode == "audio" {
                            Picker(mode == "video" ? "Video quality" : "Audio quality", selection: $quality) {
                                Text("Best available").tag("best")
                                if mode == "video" {
                                    Text("2160p").tag("2160p")
                                    Text("1440p").tag("1440p")
                                    Text("1080p").tag("1080p")
                                    Text("720p").tag("720p")
                                    Text("480p").tag("480p")
                                    Text("360p").tag("360p")
                                } else {
                                    Text("Best available source").tag("best")
                                }
                            }
                            .pickerStyle(.menu)
                            .tint(Color(hex: "F04452"))

                            if mode == "audio" {
                                Text("The highest compatible source audio stream is selected automatically.")
                                    .font(.caption).foregroundStyle(Color(hex: "A6A4A6"))
                            }
                        }

                        Picker("File format", selection: $format) {
                            if mode == "video" {
                                Text("MP4 · iOS compatible").tag("mp4")
                            } else {
                                Text("M4A · AAC").tag("m4a")
                            }
                        }
                        .pickerStyle(.menu)
                        .tint(Color(hex: "F04452"))

                        if mode == "video" {
                            Text("TrapTube selects exposed video and audio renditions independently, then muxes compatible tracks into MP4.")
                                .font(.caption).foregroundStyle(Color(hex: "A6A4A6"))
                        }

                        Button {
                            Task {
                                await manager.enqueue(
                                    videoURL: videoURL,
                                    title: title,
                                    mode: mode,
                                    quality: quality,
                                    format: format,
                                    bitrate: nil,
                                    height: mode == "video"
                                        ? (quality == "best" ? 2160 : Int(quality.replacingOccurrences(of: "p", with: "")))
                                        : nil
                                )
                            }
                        } label: {
                            HStack(spacing: 9) {
                                Image(systemName: "arrow.down.circle.fill")
                                Text("Start \(modeTitle) Download").font(.headline.bold())
                            }
                            .foregroundStyle(.white)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 15)
                            .background(Color(hex: "E50920"), in: RoundedRectangle(cornerRadius: 15))
                        }
                        .buttonStyle(.plain)
                    }
                    .padding(16)
                    .background(.white.opacity(0.055), in: RoundedRectangle(cornerRadius: 20))

                    if !manager.jobs.isEmpty {
                        VStack(alignment: .leading, spacing: 12) {
                            Text("Download queue").font(.headline.bold()).foregroundStyle(.white)
                            ForEach(manager.jobs) { job in
                                VStack(alignment: .leading, spacing: 7) {
                                    HStack {
                                        Text(job.title).font(.subheadline.bold()).foregroundStyle(.white).lineLimit(1)
                                        Spacer()
                                        Text(job.status.capitalized).font(.caption.bold()).foregroundStyle(Color(hex: "F04452"))
                                    }
                                    if job.totalBytes > 0 {
                                        ProgressView(value: job.progress).tint(Color(hex: "E50920"))
                                    } else {
                                        ProgressView().tint(Color(hex: "E50920"))
                                    }
                                    Text(ByteCountFormatter.string(fromByteCount: job.downloadedBytes, countStyle: .file) +
                                         (job.totalBytes > 0 ? " / " + ByteCountFormatter.string(fromByteCount: job.totalBytes, countStyle: .file) : " received"))
                                        .font(.caption2.monospacedDigit()).foregroundStyle(Color(hex: "858185"))
                                    HStack {
                                        Text(job.stage.capitalized).font(.caption).foregroundStyle(Color(hex: "A6A4A6"))
                                        Spacer()
                                        if job.speedBytesPerSecond > 0 {
                                            Text(ByteCountFormatter.string(fromByteCount: job.speedBytesPerSecond, countStyle: .file) + "/s")
                                                .font(.caption.monospacedDigit()).foregroundStyle(Color(hex: "A6A4A6"))
                                        }
                                        if job.status == "queued" || job.status == "running" {
                                            Button("Pause") { Task { await manager.cancel(job.id) } }
                                                .font(.caption.bold()).foregroundStyle(Color(hex: "FF7A84"))
                                        } else if job.status == "paused" {
                                            Button("Resume") { manager.resume(job.id) }
                                                .font(.caption.bold()).foregroundStyle(Color(hex: "78D69A"))
                                        }
                                    }
                                    if let error = job.error {
                                        Text(error).font(.caption).foregroundStyle(Color(hex: "FF7A84"))
                                    }
                                }
                                .padding(12)
                                .background(.white.opacity(0.045), in: RoundedRectangle(cornerRadius: 13))
                            }
                        }
                    }

                    if !manager.completed.isEmpty {
                        VStack(alignment: .leading, spacing: 12) {
                            Text("Saved on this device").font(.headline.bold()).foregroundStyle(.white)
                            ForEach(manager.completed) { item in
                                downloadedRow(item)
                            }
                        }
                    }

                    if let error = manager.lastError {
                        Label(error, systemImage: "exclamationmark.triangle.fill")
                            .font(.caption).foregroundStyle(Color(hex: "FF7A84"))
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
                .padding(16)
            }
            .background(Color(hex: "0C0B0D").ignoresSafeArea())
            .navigationTitle("Downloads")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") { dismiss() }.foregroundStyle(.white)
                }
            }
        }
        .preferredColorScheme(.dark)
        .sheet(item: $selectedVideo) { item in
            TrapTubeDownloadedVideoPlayer(item: item)
                .preferredColorScheme(.dark)
        }
        .onAppear {
            if preferredVideoQuality != "auto" {
                quality = "\(preferredVideoQuality)p"
            }
        }
    }

    @ViewBuilder
    private func downloadedRow(_ item: TrapTubeDownloadedMedia) -> some View {
        HStack(spacing: 11) {
            Image(systemName: item.mode == "video" ? "film" : (item.mode == "thumbnail" ? "photo" : "waveform"))
                .font(.title3).foregroundStyle(Color(hex: "F04452")).frame(width: 30)
            VStack(alignment: .leading, spacing: 4) {
                Text(item.title).font(.subheadline.bold()).foregroundStyle(.white).lineLimit(2)
                Text("\(item.mode.capitalized) · \(ByteCountFormatter.string(fromByteCount: item.sizeBytes, countStyle: .file))")
                    .font(.caption).foregroundStyle(Color(hex: "A6A4A6"))
            }
            Spacer(minLength: 4)
            if item.mode == "video" {
                Button { selectedVideo = item } label: {
                    Image(systemName: "play.circle.fill").font(.title2).foregroundStyle(.white)
                }
                .accessibilityLabel("Play downloaded video")
            } else if item.mode == "audio" {
                Button {
                    Task { await library.importAudio(from: [item.fileURL]) }
                } label: {
                    Image(systemName: "plus.circle.fill").font(.title2).foregroundStyle(.white)
                }
                .accessibilityLabel("Add downloaded audio to music library")
            }
            Menu {
                if item.mode == "video" {
                    Button("Remux to MP4 (fast)") { process(item, .remuxMP4) }
                    Button("Extract thumbnail") { process(item, .extractThumbnail) }
                } else if item.mode == "audio" {
                    Button("Convert to M4A") { process(item, .convertM4A) }
                    Button("Convert to WAV") { process(item, .convertWAV) }
                }
                Button("Delete download", role: .destructive) { manager.remove(item) }
            } label: {
                Image(systemName: "ellipsis.circle").font(.title3).foregroundStyle(Color(hex: "A6A4A6"))
            }
        }
        .padding(12)
        .background(.white.opacity(0.045), in: RoundedRectangle(cornerRadius: 13))
    }

    private func process(_ item: TrapTubeDownloadedMedia, _ operation: TrapTubeFFmpegOperation) {
        Task {
            do { try await manager.process(item, operation: operation) }
            catch { manager.lastError = error.localizedDescription }
        }
    }
}

private struct TrapTubeDownloadedVideoPlayer: View {
    let item: TrapTubeDownloadedMedia
    @State private var player: AVPlayer

    init(item: TrapTubeDownloadedMedia) {
        self.item = item
        _player = State(initialValue: AVPlayer(url: item.fileURL))
    }

    var body: some View {
        VideoPlayer(player: player)
            .background(.black)
            .ignoresSafeArea()
            .onAppear { player.play() }
            .onDisappear { player.pause() }
    }
}

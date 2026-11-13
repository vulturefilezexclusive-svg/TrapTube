#!/usr/bin/env python3
"""Build II: wire YouTube Home/You tabs and compact the native YouTube shell."""
from pathlib import Path
import sys

root = Path(sys.argv[1])

def file(name):
    found = list(root.rglob(name))
    if not found:
        raise SystemExit(f"Missing required source: {name}")
    return found[0]

def rep(source, old, new, label):
    n = source.count(old)
    if n == 0:
        if new in source:
            return source
        raise SystemExit(f"Missing expected pattern: {label}")
    if n != 1:
        raise SystemExit(f"Ambiguous pattern ({n} matches): {label}")
    return source.replace(old, new, 1)

p = file("RootView.swift")
s = p.read_text()
s = rep(s, "enum Tab: Hashable { case home, library, youtube, stems, settings }",
        "enum Tab: Hashable { case home, you, youtube, stems, settings }", "tab enum")
s = rep(s, """                case .home: YouTubeView()
                case .library: LibraryView()
                case .youtube: HomeView()""",
        """                case .home: YouTubeView()
                case .you: YouTubeAccountView()
                case .youtube: HomeView()""", "tab destinations")
s = rep(s, "case .youtube: HomeView()",
        "case .youtube: TrapTubeDownloadsView()", "TrapTube tab shows downloads")
s = rep(s, """        .safeAreaInset(edge: .bottom, spacing: 8) {
            VStack(spacing: 9) {
                MiniPlayer { showPlayer = true }
                    .environmentObject(player).environmentObject(theme)
                BottomNavigation(selection: $selectedTab).environmentObject(theme)
            }
            .padding(.horizontal, 16)
            .padding(.top, 8)
            .padding(.bottom, 4)
            .trapGlass(radius: 24, accent: theme.accent)
        }""",
        """        .safeAreaInset(edge: .bottom, spacing: 0) {
            VStack(spacing: 5) {
                MiniPlayer { showPlayer = true }
                    .environmentObject(player).environmentObject(theme)
                BottomNavigation(selection: $selectedTab).environmentObject(theme)
            }
            .padding(.horizontal, 0)
            .padding(.top, 3)
            .padding(.bottom, 0)
            .background(.ultraThinMaterial)
        }""", "compact bottom inset")
p.write_text(s)

p = file("Components.swift")
s = p.read_text()
s = rep(s, 'tab(.library, icon: "books.vertical.fill", title: "Library")',
        'tab(.you, icon: "person.crop.circle.fill", title: "You")', "Library tab")
s = rep(s, """        .padding(.vertical, 9)
        .background(.ultraThinMaterial, in: Capsule())
        .overlay(Capsule().stroke(.white.opacity(0.12), lineWidth: 1))""",
        """        .padding(.vertical, 6)
        .background(.ultraThinMaterial)
        .overlay(alignment: .top) { Rectangle().fill(.white.opacity(0.10)).frame(height: 1) }""",
        "full-width compact navigation")
p.write_text(s)

p = file("YouTubeView.swift")
s = p.read_text()
s = rep(s, """                    Text("TrapTube").font(.system(size: 18, weight: .black, design: .rounded))
                        .tracking(-0.5).foregroundStyle(.white)
                    Text("HOME").font(.system(size: 8, weight: .black, design: .rounded))
                        .tracking(1).foregroundStyle(Color(hex: "FF6570"))
                        .padding(.horizontal, 6).padding(.vertical, 3)
                        .background(Color(hex: "E50920").opacity(0.18), in: Capsule())""",
        """                    Text("TrapTube").font(.system(size: 18, weight: .black, design: .rounded))
                        .tracking(-0.5).foregroundStyle(.white)""", "remove redundant HOME label")
s = rep(s, ".padding(.horizontal, 15).padding(.top, 8).padding(.bottom, 11)",
        ".padding(.horizontal, 13).padding(.top, 3).padding(.bottom, 6)", "compact branding")
s = rep(s, ".padding(.horizontal, 14).padding(.vertical, 9)",
        ".padding(.horizontal, 12).padding(.vertical, 6)", "compact search")
s = rep(s, "        .padding(.bottom, 8)\n    }\n\n    private func selectCategory",
        "        .padding(.bottom, 4)\n    }\n\n    private func selectCategory", "compact category strip")

account = r'''

/// YouTube account destination. Uses the default website data store so cookies
/// and the signed-in YouTube session are shared with the Home tab's WKWebView.
struct YouTubeAccountView: View {
    @State private var isLoading = true
    private let accountURL = URL(string: "https://www.youtube.com/feed/you")!

    var body: some View {
        ZStack(alignment: .top) {
            Color.black.ignoresSafeArea()
            YouTubeAccountWebView(url: accountURL, onLoading: { isLoading = $0 })
            if isLoading {
                HStack(spacing: 9) {
                    ProgressView().tint(.white)
                    Text("Loading your YouTube account…")
                        .font(.caption.weight(.semibold)).foregroundStyle(.white.opacity(0.82))
                }
                .padding(.horizontal, 14).padding(.vertical, 10)
                .background(.ultraThinMaterial, in: Capsule())
                .overlay(Capsule().stroke(.white.opacity(0.14), lineWidth: 1))
                .padding(.top, 14)
                .allowsHitTesting(false)
            }
        }
        .preferredColorScheme(.dark)
    }
}

private struct YouTubeAccountWebView: UIViewRepresentable {
    let url: URL
    let onLoading: (Bool) -> Void

    func makeCoordinator() -> Coordinator { Coordinator(onLoading: onLoading) }

    func makeUIView(context: Context) -> WKWebView {
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .default()
        configuration.allowsInlineMediaPlayback = true
        let view = WKWebView(frame: .zero, configuration: configuration)
        // Same mobile-Safari identity as the Home tab so the signed-in
        // session and Google's browser check behave identically here.
        view.customUserAgent = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1"
        view.isOpaque = false
        view.backgroundColor = .black
        view.scrollView.backgroundColor = .black
        view.scrollView.contentInsetAdjustmentBehavior = .automatic
        view.allowsBackForwardNavigationGestures = true
        view.navigationDelegate = context.coordinator
        context.coordinator.webView = view
        view.load(URLRequest(url: url, cachePolicy: .useProtocolCachePolicy, timeoutInterval: 30))
        return view
    }

    func updateUIView(_ uiView: WKWebView, context: Context) {
        context.coordinator.onLoading = onLoading
        if uiView.url == nil { uiView.load(URLRequest(url: url)) }
    }

    final class Coordinator: NSObject, WKNavigationDelegate {
        var onLoading: (Bool) -> Void
        weak var webView: WKWebView?
        init(onLoading: @escaping (Bool) -> Void) { self.onLoading = onLoading }
        func webView(_ webView: WKWebView, didStartProvisionalNavigation navigation: WKNavigation!) {
            DispatchQueue.main.async { self.onLoading(true) }
        }
        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            DispatchQueue.main.async { self.onLoading(false) }
        }
        func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
            DispatchQueue.main.async { self.onLoading(false) }
        }
        func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
            DispatchQueue.main.async { self.onLoading(false) }
        }
        func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction,
                     decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
            decisionHandler(.allow)
        }
    }
}

/// TrapTube tab: the home for in-app downloads. Media saved from the player
/// menu (audio, video, cover art) is stored by TrapTubeDownloadManager and
/// listed here with playback, library import, conversion, and delete.
struct TrapTubeDownloadsView: View {
    @EnvironmentObject private var library: LibraryStore
    @StateObject private var manager = TrapTubeDownloadManager.shared
    @State private var selectedVideo: TrapTubeDownloadedMedia?

    var body: some View {
        ScrollView(showsIndicators: false) {
            VStack(alignment: .leading, spacing: 18) {
                VStack(alignment: .leading, spacing: 5) {
                    Text("DOWNLOADS").font(.caption.bold()).tracking(1.4)
                        .foregroundStyle(Color(hex: "A6A4A6"))
                    Text("TrapTube downloads").font(.title2.bold()).foregroundStyle(.white)
                    Text("Audio and video you save from the player is stored here, on this device.")
                        .font(.caption).foregroundStyle(Color(hex: "A6A4A6"))
                }

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
                                ProgressView(value: job.progress).tint(Color(hex: "E50920"))
                                HStack {
                                    Text(job.stage.capitalized).font(.caption).foregroundStyle(Color(hex: "A6A4A6"))
                                    Spacer()
                                    if job.speedBytesPerSecond > 0 {
                                        Text(ByteCountFormatter.string(fromByteCount: job.speedBytesPerSecond, countStyle: .file) + "/s")
                                            .font(.caption.monospacedDigit()).foregroundStyle(Color(hex: "A6A4A6"))
                                    }
                                    if job.status == "queued" || job.status == "running" {
                                        Button("Cancel") { Task { await manager.cancel(job.id) } }
                                            .font(.caption.bold()).foregroundStyle(Color(hex: "FF7A84"))
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

                if manager.completed.isEmpty && manager.jobs.isEmpty {
                    VStack(spacing: 10) {
                        Image(systemName: "arrow.down.circle").font(.system(size: 34)).foregroundStyle(Color(hex: "F04452"))
                        Text("Nothing downloaded yet").font(.headline.bold()).foregroundStyle(.white)
                        Text("Open a video from the Home tab, tap the TrapTube player menu, and choose Downloads — the file will land here.")
                            .font(.caption).foregroundStyle(Color(hex: "A6A4A6"))
                            .multilineTextAlignment(.center)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(20)
                    .background(.white.opacity(0.045), in: RoundedRectangle(cornerRadius: 16))
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
        .preferredColorScheme(.dark)
        .sheet(item: $selectedVideo) { item in
            TrapTubeDownloadedVideoPlayer(item: item)
                .preferredColorScheme(.dark)
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
'''
if "struct YouTubeAccountView: View" not in s:
    s += account
p.write_text(s)
print("Build II hybrid navigation applied.")

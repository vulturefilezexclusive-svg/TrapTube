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
    @EnvironmentObject private var theme: ThemeManager
    @State private var isLoading = true
    @ObservedObject private var modCenter = TrapTubeModCenter.shared
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
        .sheet(item: $modCenter.activeRequest) { request in
            TrapTubeModSheet(request: request)
                .presentationDetents([.large])
                .presentationDragIndicator(.visible)
                .preferredColorScheme(.dark)
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
        TrapTubeModInstaller.install(into: configuration)
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
    @State private var laterItems: [TrapTubeDownloadLaterItem] = TrapTubeDownloadLaterStore.items

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

                if !laterItems.isEmpty {
                    VStack(alignment: .leading, spacing: 12) {
                        Text("Download later").font(.headline.bold()).foregroundStyle(.white)
                        ForEach(laterItems) { entry in
                            HStack(spacing: 11) {
                                AsyncImage(url: URL(string: "https://i.ytimg.com/vi/\(entry.videoID)/hqdefault.jpg")) { image in
                                    image.resizable().scaledToFill()
                                } placeholder: {
                                    Color.white.opacity(0.07)
                                }
                                .frame(width: 96, height: 60)
                                .clipShape(RoundedRectangle(cornerRadius: 10))
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(entry.title).font(.subheadline.bold()).foregroundStyle(.white).lineLimit(2)
                                    Text("Saved from the player menu").font(.caption).foregroundStyle(Color(hex: "A6A4A6"))
                                }
                                Spacer(minLength: 4)
                                Button("Download") { downloadLater(entry) }
                                    .font(.caption.bold()).foregroundStyle(Color(hex: "FF7A84"))
                                Button { removeLater(entry) } label: {
                                    Image(systemName: "trash").foregroundStyle(Color(hex: "A6A4A6"))
                                }
                                .accessibilityLabel("Remove from Download later")
                            }
                            .padding(12)
                            .background(.white.opacity(0.045), in: RoundedRectangle(cornerRadius: 13))
                        }
                    }
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

                if manager.completed.isEmpty && manager.jobs.isEmpty && laterItems.isEmpty {
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
        .onAppear { laterItems = TrapTubeDownloadLaterStore.items }
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

    private func removeLater(_ entry: TrapTubeDownloadLaterItem) {
        TrapTubeDownloadLaterStore.remove(videoID: entry.videoID)
        laterItems = TrapTubeDownloadLaterStore.items
    }

    private func downloadLater(_ entry: TrapTubeDownloadLaterItem) {
        Task {
            do {
                let info = try await TrapTubeInnerTube.fetchInfo(videoID: entry.videoID)
                guard let format = info.muxed.first, let url = URL(string: format.url) else {
                    manager.lastError = "No directly downloadable MP4 was found for this video."
                    return
                }
                manager.enqueueDirectDownload(remoteURL: url, title: info.title, mode: "video",
                                              fileName: trapTubeSafeFileName(info.title, ext: "mp4"),
                                              videoID: entry.videoID, convertToMP3: false,
                                              userAgent: info.userAgent)
                removeLater(entry)
            } catch {
                manager.lastError = error.localizedDescription
            }
        }
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

# ---------------------------------------------------------------------------
# Mod menu (phase 1): injected in-player button, mod + download sheets,
# direct downloads into the TrapTube tab store.
# ---------------------------------------------------------------------------

MOD_MENU_SWIFT = r'''

// MARK: - TrapTube mod menu (in-player button, mod sheet, direct downloads)
//
// Added by ApplyHybridNavigation.py. A small floating button is injected
// into the YouTube watch page inside both the Home and You web views;
// tapping it posts the current video id to TrapTubeModCenter, which
// presents TrapTubeModSheet. Downloads go through TrapTubeDownloadManager's
// direct-download path and land in the TrapTube tab (Downloads) store.

enum TrapTubeHSV {
    static func hsv(fromHex hex: String) -> (hue: Double, saturation: Double, brightness: Double) {
        let cleaned = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var value: UInt64 = 0
        Scanner(string: cleaned).scanHexInt64(&value)
        let r = Double((value >> 16) & 0xFF) / 255
        let g = Double((value >> 8) & 0xFF) / 255
        let b = Double(value & 0xFF) / 255
        let maxV = max(r, g, b)
        let minV = min(r, g, b)
        let delta = maxV - minV
        var h: Double = 0
        if delta > 0.0001 {
            if maxV == r { h = 60 * ((g - b) / delta).truncatingRemainder(dividingBy: 6) }
            else if maxV == g { h = 60 * ((b - r) / delta + 2) }
            else { h = 60 * ((r - g) / delta + 4) }
            if h < 0 { h += 360 }
        }
        let s = maxV == 0 ? 0 : delta / maxV
        return (h / 360, s, maxV)
    }

    static func rgb(hue: Double, saturation: Double, brightness: Double) -> (r: Int, g: Int, b: Int) {
        let c = brightness * saturation
        let h6 = ((hue.truncatingRemainder(dividingBy: 1) + 1).truncatingRemainder(dividingBy: 1)) * 6
        let x = c * (1 - abs(h6.truncatingRemainder(dividingBy: 2) - 1))
        let m = brightness - c
        var rp = 0.0, gp = 0.0, bp = 0.0
        switch Int(h6) % 6 {
        case 0: rp = c; gp = x
        case 1: rp = x; gp = c
        case 2: gp = c; bp = x
        case 3: gp = x; bp = c
        case 4: rp = x; bp = c
        default: rp = c; bp = x
        }
        return (Int(((rp + m) * 255).rounded()), Int(((gp + m) * 255).rounded()), Int(((bp + m) * 255).rounded()))
    }

    static func hex(hue: Double, saturation: Double, brightness: Double) -> String {
        let v = rgb(hue: hue, saturation: saturation, brightness: brightness)
        return String(format: "%02X%02X%02X", v.r, v.g, v.b)
    }
}

func trapTubeSafeFileName(_ raw: String, ext: String) -> String {
    let invalid = CharacterSet(charactersIn: "/:\\?%*|\"<>")
    let cleaned = raw.components(separatedBy: invalid).joined(separator: " ")
        .trimmingCharacters(in: .whitespacesAndNewlines)
    let base = cleaned.isEmpty ? "TrapTube download" : String(cleaned.prefix(80))
    return base + "." + ext
}

enum TrapTubeAccentColors {
    /// Gradient pair for the injected mod button. Reads the persisted HSV
    /// theme components (TrapTube.Theme.*) once they exist; falls back to
    /// the TrapTube brand reds.
    static var currentGradientHex: (String, String) {
        let defaults = UserDefaults.standard
        if defaults.object(forKey: "TrapTube.Theme.Hue") != nil {
            let h = defaults.double(forKey: "TrapTube.Theme.Hue")
            let s = defaults.double(forKey: "TrapTube.Theme.Saturation")
            let b = defaults.double(forKey: "TrapTube.Theme.Brightness")
            return ("#" + TrapTubeHSV.hex(hue: h, saturation: s, brightness: b),
                    "#" + TrapTubeHSV.hex(hue: h, saturation: s, brightness: b * 0.62))
        }
        return ("#FF303B", "#A90012")
    }
}

struct TrapTubeModRequest: Identifiable {
    let videoID: String
    let pageTitle: String
    var id: String { videoID }
}

final class TrapTubeModCenter: ObservableObject {
    static let shared = TrapTubeModCenter()
    @Published var activeRequest: TrapTubeModRequest?
    private init() {}
    func present(videoID: String, pageTitle: String) {
        DispatchQueue.main.async {
            self.activeRequest = TrapTubeModRequest(videoID: videoID, pageTitle: pageTitle)
        }
    }
}

final class TrapTubeModScriptHandler: NSObject, WKScriptMessageHandler {
    static let shared = TrapTubeModScriptHandler()
    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard message.name == "trapTubeMod",
              let body = message.body as? [String: Any],
              let videoID = body["videoID"] as? String, !videoID.isEmpty else { return }
        TrapTubeModCenter.shared.present(videoID: videoID, pageTitle: body["title"] as? String ?? "")
    }
}

enum TrapTubeModInstaller {
    static func install(into configuration: WKWebViewConfiguration) {
        configuration.userContentController.add(TrapTubeModScriptHandler.shared, name: "trapTubeMod")
        configuration.userContentController.addUserScript(
            WKUserScript(source: scriptSource, injectionTime: .atDocumentEnd, forMainFrameOnly: true))
    }

    static var scriptSource: String {
        let colors = TrapTubeAccentColors.currentGradientHex
        return #"""
        (() => {
          if (window.__trapTubeModInstalled) return;
          window.__trapTubeModInstalled = true;
          var BTN_ID = "traptube-mod-btn";
          function currentVideoID() {
            try {
              var u = new URL(window.location.href);
              if (u.pathname === "/watch") return u.searchParams.get("v");
              var m = u.pathname.match(/^\/(shorts|live|embed)\/([\w-]{6,})/);
              return m ? m[2] : null;
            } catch (e) { return null; }
          }
          function ensureButton() {
            try {
              var id = currentVideoID();
              var btn = document.getElementById(BTN_ID);
              if (!id) { if (btn) btn.remove(); return; }
              var player = document.querySelector("#movie_player") || document.querySelector(".html5-video-player");
              if (!player) { if (btn) btn.remove(); return; }
              if (!btn) {
                btn = document.createElement("button");
                btn.id = BTN_ID;
                btn.type = "button";
                btn.setAttribute("aria-label", "TrapTube menu");
                btn.textContent = "↓";
                btn.style.cssText = "position:absolute;top:54px;right:10px;z-index:2147483000;width:40px;height:40px;border-radius:12px;border:1px solid rgba(255,255,255,0.4);background:linear-gradient(135deg,\#(colors.0),\#(colors.1));color:#ffffff;font-size:21px;font-weight:900;line-height:1;display:flex;align-items:center;justify-content:center;cursor:pointer;box-shadow:0 4px 14px rgba(0,0,0,0.5);padding:0;margin:0;";
                btn.addEventListener("click", function (ev) {
                  ev.preventDefault(); ev.stopPropagation();
                  try { window.webkit.messageHandlers.trapTubeMod.postMessage({ videoID: currentVideoID() || "", title: document.title || "", url: window.location.href }); } catch (e) {}
                }, true);
                player.appendChild(btn);
              } else if (btn.parentElement !== player) {
                player.appendChild(btn);
              }
              try { if (window.getComputedStyle(player).position === "static") player.style.position = "relative"; } catch (e) {}
            } catch (e) {}
          }
          function start() {
            ensureButton();
            try { new MutationObserver(ensureButton).observe(document.documentElement, { childList: true, subtree: true }); } catch (e) {}
            setInterval(ensureButton, 1500);
            document.addEventListener("yt-navigate-finish", ensureButton);
          }
          if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
        })();
        """#
    }
}

// MARK: InnerTube stream resolution for the mod download sheet

struct TrapTubeStreamFormat: Identifiable {
    let itag: Int
    let url: String
    let mimeType: String
    let qualityLabel: String
    let height: Int
    let bitrate: Int
    let contentLength: Int64?
    let hasVideo: Bool
    let hasAudio: Bool
    var id: Int { itag }

    func sizeText(durationSeconds: Int) -> String {
        if let contentLength {
            return ByteCountFormatter.string(fromByteCount: contentLength, countStyle: .file)
        }
        if bitrate > 0, durationSeconds > 0 {
            let estimate = Int64(bitrate) * Int64(durationSeconds) / 8
            return "≈ " + ByteCountFormatter.string(fromByteCount: estimate, countStyle: .file)
        }
        return "Size unknown"
    }

    var audioKbps: Int { Int((Double(bitrate) / 1000).rounded()) }
}

struct TrapTubeCaptionTrack: Identifiable {
    let name: String
    let languageCode: String
    let baseURL: String
    let isAutomatic: Bool
    var id: String { baseURL }
}

struct TrapTubeVideoInfo {
    let videoID: String
    let title: String
    let author: String
    let durationSeconds: Int
    let userAgent: String
    let muxed: [TrapTubeStreamFormat]
    let audioOnly: [TrapTubeStreamFormat]
    let captions: [TrapTubeCaptionTrack]
}

enum TrapTubeModError: LocalizedError {
    case unplayable(String)
    var errorDescription: String? {
        switch self {
        case .unplayable(let detail):
            return "YouTube did not offer a directly downloadable stream for this video (\(detail))."
        }
    }
}

enum TrapTubeInnerTube {
    private struct ClientProfile {
        let name: String
        let apiKey: String
        let userAgent: String
        let client: [String: Any]
    }

    private static let profiles: [ClientProfile] = [
        ClientProfile(
            name: "ANDROID",
            apiKey: "AIzaSyA8eiZmM1FaDVjRy-df2KTyQ_vz_yYM39w",
            userAgent: "com.google.android.youtube/20.45.38 (Linux; U; Android 14; en_US; Pixel 8) gzip",
            client: ["clientName": "ANDROID", "clientVersion": "20.45.38", "androidSdkVersion": 34,
                     "osName": "Android", "osVersion": "14", "hl": "en", "gl": "US"]),
        ClientProfile(
            name: "IOS",
            apiKey: "AIzaSyB-63vPrdThhKuerbB2N_l7Kwwcxj6yUAc",
            userAgent: "com.google.ios.youtube/20.45.3 (iPhone16,2; U; CPU iOS 18_1_0 like Mac OS X)",
            client: ["clientName": "IOS", "clientVersion": "20.45.3", "deviceMake": "Apple",
                     "deviceModel": "iPhone16,2", "osName": "iPhone", "osVersion": "18.1.0", "hl": "en", "gl": "US"]),
        ClientProfile(
            name: "WEB_EMBEDDED_PLAYER",
            apiKey: "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8",
            userAgent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
            client: ["clientName": "WEB_EMBEDDED_PLAYER", "clientVersion": "1.20241110.01.00", "hl": "en", "gl": "US"])
    ]

    private static var cachedVisitorData: String?

    static func fetchInfo(videoID: String) async throws -> TrapTubeVideoInfo {
        var failures: [String] = []
        for profile in profiles {
            do {
                let json = try await playerResponse(videoID: videoID, profile: profile)
                if let playability = json["playabilityStatus"] as? [String: Any],
                   let status = playability["status"] as? String, status != "OK" {
                    failures.append("\(profile.name): \(playability["reason"] as? String ?? status)")
                    continue
                }
                guard let streaming = json["streamingData"] as? [String: Any] else {
                    failures.append("\(profile.name): no streaming data")
                    continue
                }
                let muxedRaw = parseFormats(streaming["formats"])
                let adaptiveRaw = parseFormats(streaming["adaptiveFormats"])
                let directMuxed = muxedRaw.filter { $0.hasVideo && $0.hasAudio && $0.mimeType.contains("mp4") }
                    .sorted { $0.height > $1.height }
                let directAudio = adaptiveRaw.filter { !$0.hasVideo && $0.hasAudio && $0.mimeType.contains("mp4") }
                    .sorted { $0.bitrate > $1.bitrate }
                if directMuxed.isEmpty && directAudio.isEmpty {
                    failures.append("\(profile.name): streams are signature-protected or not MP4")
                    continue
                }
                let details = json["videoDetails"] as? [String: Any]
                return TrapTubeVideoInfo(
                    videoID: videoID,
                    title: details?["title"] as? String ?? "YouTube video",
                    author: details?["author"] as? String ?? "",
                    durationSeconds: Int(details?["lengthSeconds"] as? String ?? "") ?? 0,
                    userAgent: profile.userAgent,
                    muxed: directMuxed,
                    audioOnly: directAudio,
                    captions: parseCaptions(json))
            } catch {
                failures.append("\(profile.name): \(error.localizedDescription)")
            }
        }
        throw TrapTubeModError.unplayable(failures.joined(separator: " · "))
    }

    private static func playerResponse(videoID: String, profile: ClientProfile) async throws -> [String: Any] {
        var client = profile.client
        if let visitor = await fetchVisitorData() { client["visitorData"] = visitor }
        var context: [String: Any] = ["client": client]
        if profile.name == "WEB_EMBEDDED_PLAYER" {
            context["thirdParty"] = ["embedUrl": "https://www.youtube.com/embed/\(videoID)"]
        }
        let body: [String: Any] = ["context": context, "videoId": videoID, "racyCheckOk": true, "contentCheckOk": true]
        guard let url = URL(string: "https://www.youtube.com/youtubei/v1/player?key=\(profile.apiKey)&prettyPrint=false") else {
            throw TrapTubeModError.unplayable("bad endpoint")
        }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(profile.userAgent, forHTTPHeaderField: "User-Agent")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        let (data, _) = try await URLSession.shared.data(for: request)
        guard let json = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            throw TrapTubeModError.unplayable("unexpected response")
        }
        return json
    }

    private static func fetchVisitorData() async -> String? {
        if let cachedVisitorData { return cachedVisitorData }
        guard let url = URL(string: "https://www.youtube.com/") else { return nil }
        var request = URLRequest(url: url)
        request.setValue("Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1",
                         forHTTPHeaderField: "User-Agent")
        guard let (data, _) = try? await URLSession.shared.data(for: request),
              let html = String(data: data, encoding: .utf8),
              let marker = html.range(of: "\"visitorData\":\"") else { return nil }
        let rest = html[marker.upperBound...]
        guard let end = rest.firstIndex(of: "\"") else { return nil }
        let value = String(rest[..<end]).replacingOccurrences(of: "\\u0026", with: "&")
        cachedVisitorData = value
        return value
    }

    private static func parseFormats(_ raw: Any?) -> [TrapTubeStreamFormat] {
        guard let list = raw as? [[String: Any]] else { return [] }
        return list.compactMap { entry in
            guard let url = entry["url"] as? String, !url.isEmpty else { return nil }
            let mime = entry["mimeType"] as? String ?? ""
            let isVideo = mime.hasPrefix("video/")
            let isAudio = mime.hasPrefix("audio/")
            return TrapTubeStreamFormat(
                itag: entry["itag"] as? Int ?? 0,
                url: url,
                mimeType: mime,
                qualityLabel: entry["qualityLabel"] as? String ?? "",
                height: entry["height"] as? Int ?? 0,
                bitrate: entry["bitrate"] as? Int ?? 0,
                contentLength: (entry["contentLength"] as? String).flatMap { Int64($0) },
                hasVideo: isVideo,
                hasAudio: isAudio || mime.contains("mp4a"))
        }
    }

    private static func parseCaptions(_ json: [String: Any]) -> [TrapTubeCaptionTrack] {
        guard let captions = json["captions"] as? [String: Any],
              let renderer = captions["playerCaptionsTracklistRenderer"] as? [String: Any],
              let tracks = renderer["captionTracks"] as? [[String: Any]] else { return [] }
        return tracks.compactMap { track in
            guard let base = track["baseUrl"] as? String, !base.isEmpty else { return nil }
            var name = track["languageCode"] as? String ?? "Captions"
            if let nameObject = track["name"] as? [String: Any] {
                if let simple = nameObject["simpleText"] as? String {
                    name = simple
                } else if let runs = nameObject["runs"] as? [[String: Any]] {
                    name = runs.compactMap { $0["text"] as? String }.joined()
                }
            }
            return TrapTubeCaptionTrack(
                name: name,
                languageCode: track["languageCode"] as? String ?? "",
                baseURL: base,
                isAutomatic: (track["kind"] as? String) == "asr")
        }
    }
}

enum TrapTubeCaptionSaver {
    static func fetchText(_ track: TrapTubeCaptionTrack, userAgent: String) async throws -> String {
        let separator = track.baseURL.contains("?") ? "&" : "?"
        guard let url = URL(string: track.baseURL + separator + "fmt=json3") else {
            throw TrapTubeModError.unplayable("bad caption URL")
        }
        var request = URLRequest(url: url)
        request.setValue(userAgent, forHTTPHeaderField: "User-Agent")
        let (data, _) = try await URLSession.shared.data(for: request)
        if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
           let events = json["events"] as? [[String: Any]] {
            let lines = events.compactMap { event -> String? in
                guard let segs = event["segs"] as? [[String: Any]] else { return nil }
                let line = segs.compactMap { $0["utf8"] as? String }.joined()
                    .trimmingCharacters(in: .whitespacesAndNewlines)
                return line.isEmpty ? nil : line
            }
            if !lines.isEmpty { return lines.joined(separator: "\n") }
        }
        // Fall back to the timed-text XML form and keep one caption per line.
        let xml = String(data: data, encoding: .utf8) ?? ""
        guard let regex = try? NSRegularExpression(pattern: "<text[^>]*>(.*?)</text>", options: [.dotMatchesLineSeparators]) else {
            return xml
        }
        let range = NSRange(xml.startIndex..., in: xml)
        var lines: [String] = []
        regex.enumerateMatches(in: xml, range: range) { match, _, _ in
            guard let match, let textRange = Range(match.range(at: 1), in: xml) else { return }
            var line = String(xml[textRange])
            line = line.replacingOccurrences(of: "&amp;", with: "&")
                .replacingOccurrences(of: "&quot;", with: "\"")
                .replacingOccurrences(of: "&#39;", with: "'")
                .replacingOccurrences(of: "&lt;", with: "<")
                .replacingOccurrences(of: "&gt;", with: ">")
                .trimmingCharacters(in: .whitespacesAndNewlines)
            if !line.isEmpty { lines.append(line) }
        }
        return lines.joined(separator: "\n")
    }
}

// MARK: Download later store (read by the TrapTube tab downloads view)

struct TrapTubeDownloadLaterItem: Codable, Identifiable {
    let videoID: String
    let title: String
    let addedAt: Date
    var id: String { videoID }
}

enum TrapTubeDownloadLaterStore {
    private static let key = "TrapTube.DownloadLater"

    static var items: [TrapTubeDownloadLaterItem] {
        guard let data = UserDefaults.standard.data(forKey: key),
              let decoded = try? JSONDecoder().decode([TrapTubeDownloadLaterItem].self, from: data) else { return [] }
        return decoded
    }

    static func contains(videoID: String) -> Bool {
        items.contains { $0.videoID == videoID }
    }

    static func add(videoID: String, title: String) {
        var list = items
        list.removeAll { $0.videoID == videoID }
        list.insert(TrapTubeDownloadLaterItem(videoID: videoID, title: title, addedAt: Date()), at: 0)
        save(list)
    }

    static func remove(videoID: String) {
        save(items.filter { $0.videoID != videoID })
    }

    private static func save(_ list: [TrapTubeDownloadLaterItem]) {
        if let data = try? JSONEncoder().encode(list) {
            UserDefaults.standard.set(data, forKey: key)
        }
    }
}

// MARK: Mod sheet

struct TrapTubeModSheet: View {
    let request: TrapTubeModRequest

    @Environment(\.dismiss) private var dismiss
    @EnvironmentObject private var theme: ThemeManager
    @EnvironmentObject private var library: LibraryStore
    @StateObject private var manager = TrapTubeDownloadManager.shared
    @State private var info: TrapTubeVideoInfo?
    @State private var infoFailed = false
    @State private var showDownloadSheet = false
    @State private var statusMessage: String?
    @State private var showCaptionsList = false
    @State private var showPlayNote = false
    @State private var playItem: TrapTubeDownloadedMedia?
    @State private var inLaterList = false

    private var displayTitle: String {
        info?.title ?? (request.pageTitle.isEmpty ? "YouTube video" : request.pageTitle)
    }
    private var displayChannel: String { info?.author ?? "" }
    private var downloadedCopy: TrapTubeDownloadedMedia? {
        manager.completed.first { $0.videoID == request.videoID }
    }

    var body: some View {
        VStack(spacing: 0) {
            Capsule().fill(.white.opacity(0.35)).frame(width: 42, height: 5)
                .padding(.top, 10).padding(.bottom, 14)

            HStack(spacing: 12) {
                AsyncImage(url: URL(string: "https://i.ytimg.com/vi/\(request.videoID)/hqdefault.jpg")) { image in
                    image.resizable().scaledToFill()
                } placeholder: {
                    Color.white.opacity(0.07)
                }
                .frame(width: 104, height: 64)
                .clipShape(RoundedRectangle(cornerRadius: 12))

                VStack(alignment: .leading, spacing: 4) {
                    Text(displayChannel.isEmpty ? displayTitle : "\(displayChannel) — \(displayTitle)")
                        .font(.headline.bold()).foregroundStyle(.white).lineLimit(3)
                    Text("TrapTube mod menu").font(.caption.weight(.medium)).foregroundStyle(Color(hex: "A6A4A6"))
                }
                Spacer(minLength: 4)
                Button { dismiss() } label: {
                    Image(systemName: "xmark").font(.headline.bold()).foregroundStyle(.white)
                        .frame(width: 38, height: 38).background(.white.opacity(0.12), in: Circle())
                }
                .accessibilityLabel("Close mod menu")
            }
            .padding(.horizontal, 20).padding(.bottom, 8)

            if let statusMessage {
                Text(statusMessage)
                    .font(.caption.weight(.semibold)).foregroundStyle(Color(hex: "FFC7CC"))
                    .fixedSize(horizontal: false, vertical: true)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal, 20).padding(.vertical, 6)
            }

            ScrollView(showsIndicators: false) {
                VStack(spacing: 0) {
                    modRow("Download", detail: downloadDetail, icon: "arrow.down.to.line") {
                        showDownloadSheet = true
                    }
                    modRow("Save image", detail: "Saves the video thumbnail into Downloads", icon: "photo") {
                        saveThumbnail()
                    }
                    modRow("Save captions",
                           detail: captionsDetail,
                           icon: "captions.bubble",
                           disabled: info == nil || info?.captions.isEmpty != false) {
                        withAnimation { showCaptionsList.toggle() }
                    }
                    if showCaptionsList, let info {
                        ForEach(info.captions) { track in
                            Button {
                                saveCaption(track)
                            } label: {
                                HStack(spacing: 15) {
                                    Image(systemName: "text.badge.plus").font(.system(size: 17, weight: .semibold))
                                        .foregroundStyle(theme.accent).frame(width: 32)
                                    Text(track.name + (track.isAutomatic ? " (auto-generated)" : ""))
                                        .font(.subheadline.weight(.semibold)).foregroundStyle(.white)
                                    Spacer()
                                    Image(systemName: "arrow.down").font(.caption.bold()).foregroundStyle(Color(hex: "8E8B90"))
                                }
                                .padding(.vertical, 12).padding(.leading, 24)
                                .contentShape(Rectangle())
                            }
                            .buttonStyle(.plain)
                        }
                    }
                    modRow("Copy information", detail: "Title, channel, and link", icon: "doc.on.doc") {
                        copyInformation()
                    }
                    modRow("Play in...", detail: playDetail, icon: "play.rectangle.on.rectangle") {
                        playAction()
                    }
                    if showPlayNote {
                        Text("This video isn't downloaded yet. Download it here first — after that it plays inside TrapTube from the TrapTube tab: videos in the EQ video player, audio in your library.")
                            .font(.caption).foregroundStyle(Color(hex: "A6A4A6"))
                            .fixedSize(horizontal: false, vertical: true)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(.vertical, 10).padding(.leading, 24)
                    }
                    modRow(inLaterList ? "Saved for later" : "Download later",
                           detail: inLaterList ? "Waiting in the TrapTube tab" : "Adds this video to the TrapTube tab list",
                           icon: inLaterList ? "checkmark.circle.fill" : "clock") {
                        toggleDownloadLater()
                    }
                }
                .padding(.horizontal, 20)
            }
        }
        .background(Color(hex: "141315").ignoresSafeArea())
        .task { await loadInfo() }
        .onAppear { inLaterList = TrapTubeDownloadLaterStore.contains(videoID: request.videoID) }
        .sheet(isPresented: $showDownloadSheet) {
            TrapTubeModDownloadSheet(videoID: request.videoID, preloaded: info)
                .presentationDetents([.large])
                .presentationDragIndicator(.visible)
                .preferredColorScheme(.dark)
        }
        .sheet(item: $playItem) { item in
            TrapTubeDownloadedVideoPlayer(item: item)
                .preferredColorScheme(.dark)
        }
    }

    private var downloadDetail: String {
        if info != nil { return "Video · Audio · Captions" }
        return infoFailed ? "Stream lookup failed — the sheet can retry" : "Fetching video data…"
    }

    private var captionsDetail: String {
        guard let info else { return infoFailed ? "Caption check failed" : "Checking captions…" }
        return info.captions.isEmpty ? "No captions for this video" : "\(info.captions.count) caption track\(info.captions.count == 1 ? "" : "s")"
    }

    private var playDetail: String {
        guard let copy = downloadedCopy else { return "In-app playback for downloads" }
        return copy.mode == "video" ? "Play the downloaded copy" : "Add the downloaded audio to your library"
    }

    private func modRow(_ title: String, detail: String, icon: String, disabled: Bool = false, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(spacing: 15) {
                Image(systemName: icon).font(.system(size: 21, weight: .semibold))
                    .foregroundStyle(theme.accent).frame(width: 32)
                VStack(alignment: .leading, spacing: 4) {
                    Text(title).font(.headline.bold()).foregroundStyle(.white)
                    Text(detail).font(.caption).foregroundStyle(Color(hex: "A6A4A6")).lineLimit(1)
                }
                Spacer(minLength: 8)
                Image(systemName: "chevron.right").font(.caption.bold()).foregroundStyle(Color(hex: "8E8B90"))
            }
            .padding(.vertical, 15)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .disabled(disabled)
        .opacity(disabled ? 0.45 : 1)
        .overlay(alignment: .bottom) { Rectangle().fill(.white.opacity(0.08)).frame(height: 1) }
    }

    private func loadInfo() async {
        do {
            info = try await TrapTubeInnerTube.fetchInfo(videoID: request.videoID)
        } catch {
            infoFailed = true
        }
    }

    private func saveThumbnail() {
        let videoID = request.videoID
        let title = displayTitle
        statusMessage = "Saving thumbnail…"
        Task {
            for name in ["maxresdefault", "hqdefault"] {
                guard let url = URL(string: "https://i.ytimg.com/vi/\(videoID)/\(name).jpg") else { continue }
                if let (data, response) = try? await URLSession.shared.data(from: url),
                   let http = response as? HTTPURLResponse, http.statusCode == 200,
                   data.count > (name == "maxresdefault" ? 12000 : 3000) {
                    do {
                        let directory = TrapTubeDownloadPaths.downloadsDirectory
                        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
                        let fileURL = directory.appendingPathComponent(trapTubeSafeFileName(title + " [thumbnail]", ext: "jpg"))
                        try data.write(to: fileURL)
                        manager.registerLocalFile(fileURL: fileURL, title: title + " · Thumbnail", mode: "thumbnail", videoID: videoID)
                        statusMessage = "Thumbnail saved to the TrapTube tab. (This build has no Photos permission configured, so it is stored with your downloads.)"
                    } catch {
                        statusMessage = error.localizedDescription
                    }
                    return
                }
            }
            statusMessage = "No thumbnail was available for this video."
        }
    }

    private func saveCaption(_ track: TrapTubeCaptionTrack) {
        let videoID = request.videoID
        let title = displayTitle
        let userAgent = info?.userAgent ?? "com.google.android.youtube/20.45.38 (Linux; U; Android 14; en_US; Pixel 8) gzip"
        statusMessage = "Saving captions…"
        Task {
            do {
                let text = try await TrapTubeCaptionSaver.fetchText(track, userAgent: userAgent)
                guard !text.isEmpty else { statusMessage = "That caption track came back empty."; return }
                let directory = TrapTubeDownloadPaths.downloadsDirectory
                try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
                let fileURL = directory.appendingPathComponent(trapTubeSafeFileName(title + " [\(track.languageCode)]", ext: "txt"))
                try text.write(to: fileURL, atomically: true, encoding: .utf8)
                manager.registerLocalFile(fileURL: fileURL, title: title + " · Captions (\(track.languageCode))", mode: "caption", videoID: videoID)
                statusMessage = "Captions saved to the TrapTube tab."
            } catch {
                statusMessage = "Captions failed: \(error.localizedDescription)"
            }
        }
    }

    private func copyInformation() {
        var lines = [displayTitle]
        if !displayChannel.isEmpty { lines.append(displayChannel) }
        lines.append("https://www.youtube.com/watch?v=\(request.videoID)")
        UIPasteboard.general.string = lines.joined(separator: "\n")
        statusMessage = "Copied video information."
    }

    private func playAction() {
        guard let copy = downloadedCopy else {
            withAnimation { showPlayNote.toggle() }
            return
        }
        if copy.mode == "video" {
            playItem = copy
        } else if copy.mode == "audio" {
            Task { await library.importAudio(from: [copy.fileURL]) }
            statusMessage = "Downloaded audio added to your library."
        } else {
            withAnimation { showPlayNote.toggle() }
        }
    }

    private func toggleDownloadLater() {
        if inLaterList {
            TrapTubeDownloadLaterStore.remove(videoID: request.videoID)
            inLaterList = false
            statusMessage = "Removed from Download later."
        } else {
            TrapTubeDownloadLaterStore.add(videoID: request.videoID, title: displayTitle)
            inLaterList = true
            statusMessage = "Saved — find it under Download later in the TrapTube tab."
        }
    }
}

// MARK: Mod download sheet (quality / format picker)

struct TrapTubeModDownloadSheet: View {
    let videoID: String
    let preloaded: TrapTubeVideoInfo?

    @Environment(\.dismiss) private var dismiss
    @EnvironmentObject private var theme: ThemeManager
    @StateObject private var manager = TrapTubeDownloadManager.shared
    @State private var info: TrapTubeVideoInfo?
    @State private var loadError: String?
    @State private var tab = 0
    @State private var selectedVideoItag: Int?
    @State private var selectedAudioItag: Int?
    @State private var audioFormat = "m4a"
    @State private var metaTitle = ""
    @State private var metaArtist = ""
    @State private var captionIndex = 0
    @State private var downloadStarted = false
    @State private var startedMessage: String?
    @State private var inLaterList = false

    private var selectedFormat: TrapTubeStreamFormat? {
        guard let info else { return nil }
        if tab == 0 {
            return info.muxed.first { $0.itag == selectedVideoItag } ?? info.muxed.first
        }
        return info.audioOnly.first { $0.itag == selectedAudioItag } ?? info.audioOnly.first
    }

    var body: some View {
        NavigationView {
            ScrollView(showsIndicators: false) {
                VStack(alignment: .leading, spacing: 18) {
                    if let info {
                        content(info)
                    } else if let loadError {
                        VStack(spacing: 10) {
                            Image(systemName: "exclamationmark.triangle.fill").font(.title2).foregroundStyle(Color(hex: "FF7A84"))
                            Text(loadError).font(.subheadline).foregroundStyle(.white)
                                .multilineTextAlignment(.center).fixedSize(horizontal: false, vertical: true)
                            Button("Try again") { Task { await load() } }
                                .font(.subheadline.bold()).foregroundStyle(theme.accent)
                        }
                        .frame(maxWidth: .infinity).padding(.top, 40)
                    } else {
                        VStack(spacing: 12) {
                            ProgressView().tint(.white)
                            Text("Fetching video data…").font(.subheadline.weight(.semibold)).foregroundStyle(.white.opacity(0.8))
                        }
                        .frame(maxWidth: .infinity).padding(.top, 60)
                    }
                }
                .padding(16)
            }
            .background(Color(hex: "0C0B0D").ignoresSafeArea())
            .navigationTitle("Download")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") { dismiss() }.foregroundStyle(.white)
                }
            }
        }
        .preferredColorScheme(.dark)
        .task { await load() }
        .onAppear { inLaterList = TrapTubeDownloadLaterStore.contains(videoID: videoID) }
    }

    @ViewBuilder
    private func content(_ info: TrapTubeVideoInfo) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            Text(info.author.isEmpty ? info.title : "\(info.author) — \(info.title)")
                .font(.headline.bold()).foregroundStyle(.white).lineLimit(2)
            if let format = selectedFormat {
                Text("\(tab == 0 ? format.qualityLabel : "\(format.audioKbps) kbps") · \(format.sizeText(durationSeconds: info.durationSeconds))")
                    .font(.caption.weight(.semibold)).foregroundStyle(theme.accent)
            }
        }

        Picker("Format", selection: $tab) {
            Text("Video (avc1)").tag(0)
            Text("Audio only").tag(1)
        }
        .pickerStyle(.segmented)

        if tab == 0 {
            if info.muxed.isEmpty {
                Text("YouTube did not offer a directly downloadable MP4 for this video. Audio-only may still be available.")
                    .font(.caption).foregroundStyle(Color(hex: "A6A4A6"))
                    .fixedSize(horizontal: false, vertical: true)
            } else {
                VStack(spacing: 8) {
                    ForEach(info.muxed) { format in
                        formatRow(label: "\(format.qualityLabel) · MP4",
                                  size: format.sizeText(durationSeconds: info.durationSeconds),
                                  selected: selectedFormat?.itag == format.itag) {
                            selectedVideoItag = format.itag
                        }
                    }
                }
            }
        } else {
            if info.audioOnly.isEmpty {
                Text("YouTube did not offer a directly downloadable AAC track for this video.")
                    .font(.caption).foregroundStyle(Color(hex: "A6A4A6"))
                    .fixedSize(horizontal: false, vertical: true)
            } else {
                VStack(spacing: 8) {
                    ForEach(info.audioOnly) { format in
                        formatRow(label: "\(format.audioKbps) kbps · AAC",
                                  size: format.sizeText(durationSeconds: info.durationSeconds),
                                  selected: selectedFormat?.itag == format.itag) {
                            selectedAudioItag = format.itag
                        }
                    }
                }

                VStack(alignment: .leading, spacing: 8) {
                    Text("Format").font(.subheadline.bold()).foregroundStyle(.white)
                    Picker("Format", selection: $audioFormat) {
                        Text("m4a").tag("m4a")
                        Text("mp3").tag("mp3")
                    }
                    .pickerStyle(.segmented)
                    Text(audioFormat == "mp3"
                         ? "The AAC track downloads first, then FFmpeg converts it to MP3 on this device."
                         : "The AAC track is saved as-is in an M4A file.")
                        .font(.caption).foregroundStyle(Color(hex: "A6A4A6"))
                }

                VStack(alignment: .leading, spacing: 10) {
                    Text("Edit metadata").font(.subheadline.bold()).foregroundStyle(.white)
                    TextField("Title", text: $metaTitle)
                        .textFieldStyle(.roundedBorder)
                    TextField("Artist / channel", text: $metaArtist)
                        .textFieldStyle(.roundedBorder)
                    Text("Used for the saved file's name in your downloads.")
                        .font(.caption).foregroundStyle(Color(hex: "A6A4A6"))
                }
            }
        }

        if !info.captions.isEmpty {
            HStack {
                Text("Captions").font(.subheadline.bold()).foregroundStyle(.white)
                Spacer()
                Picker("Captions", selection: $captionIndex) {
                    Text("Don't add captions").tag(0)
                    ForEach(Array(info.captions.enumerated()), id: \.offset) { index, track in
                        Text(track.name).tag(index + 1)
                    }
                }
                .pickerStyle(.menu)
                .tint(theme.accent)
            }
            Text("A chosen caption track is saved as a text file next to the download. (Embedding captions inside the media file isn't supported yet.)")
                .font(.caption).foregroundStyle(Color(hex: "A6A4A6"))
                .fixedSize(horizontal: false, vertical: true)
        }

        HStack {
            Text("Save in...").font(.subheadline.bold()).foregroundStyle(.white)
            Spacer()
            Text("Downloads").font(.subheadline).foregroundStyle(Color(hex: "A6A4A6"))
        }

        Button {
            toggleDownloadLater(info)
        } label: {
            HStack(spacing: 9) {
                Image(systemName: inLaterList ? "checkmark.circle.fill" : "clock")
                Text(inLaterList ? "Saved for later" : "Download later").font(.subheadline.bold())
            }
            .foregroundStyle(.white)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 12)
            .background(.white.opacity(0.07), in: RoundedRectangle(cornerRadius: 13))
        }
        .buttonStyle(.plain)

        Button {
            startDownload(info)
        } label: {
            HStack(spacing: 9) {
                Image(systemName: "arrow.down.circle.fill")
                Text(downloadButtonTitle(info)).font(.headline.bold())
            }
            .foregroundStyle(.white)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 15)
            .background(LinearGradient(colors: [theme.accent, theme.accent.opacity(0.62)],
                                       startPoint: .topLeading, endPoint: .bottomTrailing),
                        in: RoundedRectangle(cornerRadius: 15))
        }
        .buttonStyle(.plain)
        .disabled(selectedFormat == nil || downloadStarted)
        .opacity(selectedFormat == nil || downloadStarted ? 0.55 : 1)

        if let startedMessage {
            Text(startedMessage).font(.caption.weight(.semibold)).foregroundStyle(Color(hex: "FFC7CC"))
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    private func formatRow(label: String, size: String, selected: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(spacing: 10) {
                Text(label).font(.subheadline.weight(.semibold)).foregroundStyle(.white)
                Spacer()
                Text(size).font(.caption.monospacedDigit()).foregroundStyle(Color(hex: "A6A4A6"))
                Image(systemName: selected ? "checkmark.circle.fill" : "circle")
                    .foregroundStyle(selected ? theme.accent : Color.white.opacity(0.3))
            }
            .padding(.horizontal, 13).padding(.vertical, 12)
            .background(.white.opacity(selected ? 0.09 : 0.045), in: RoundedRectangle(cornerRadius: 13))
            .overlay(RoundedRectangle(cornerRadius: 13).stroke(selected ? theme.accent.opacity(0.5) : .white.opacity(0.07), lineWidth: 1))
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }

    private func downloadButtonTitle(_ info: TrapTubeVideoInfo) -> String {
        if downloadStarted { return "Download started" }
        guard let format = selectedFormat else { return "Download" }
        return "Download · \(format.sizeText(durationSeconds: info.durationSeconds))"
    }

    private func load() async {
        if let preloaded {
            info = preloaded
            applyDefaults(preloaded)
            return
        }
        loadError = nil
        do {
            let fetched = try await TrapTubeInnerTube.fetchInfo(videoID: videoID)
            info = fetched
            applyDefaults(fetched)
        } catch {
            loadError = error.localizedDescription
        }
    }

    private func applyDefaults(_ info: TrapTubeVideoInfo) {
        if selectedVideoItag == nil { selectedVideoItag = info.muxed.first?.itag }
        if selectedAudioItag == nil { selectedAudioItag = info.audioOnly.first?.itag }
        if metaTitle.isEmpty { metaTitle = info.title }
        if metaArtist.isEmpty { metaArtist = info.author }
    }

    private func toggleDownloadLater(_ info: TrapTubeVideoInfo) {
        if inLaterList {
            TrapTubeDownloadLaterStore.remove(videoID: videoID)
            inLaterList = false
        } else {
            TrapTubeDownloadLaterStore.add(videoID: videoID, title: info.title)
            inLaterList = true
        }
    }

    private func startDownload(_ info: TrapTubeVideoInfo) {
        guard let format = selectedFormat, let url = URL(string: format.url) else { return }
        let isAudio = tab == 1
        let title: String
        if isAudio {
            let t = metaTitle.trimmingCharacters(in: .whitespacesAndNewlines)
            let a = metaArtist.trimmingCharacters(in: .whitespacesAndNewlines)
            title = t.isEmpty ? info.title : (a.isEmpty ? t : "\(a) – \(t)")
        } else {
            title = info.title
        }
        manager.enqueueDirectDownload(
            remoteURL: url,
            title: title,
            mode: isAudio ? "audio" : "video",
            fileName: trapTubeSafeFileName(title, ext: isAudio ? "m4a" : "mp4"),
            videoID: videoID,
            convertToMP3: isAudio && audioFormat == "mp3",
            userAgent: info.userAgent)

        if captionIndex > 0, info.captions.indices.contains(captionIndex - 1) {
            let track = info.captions[captionIndex - 1]
            let userAgent = info.userAgent
            Task {
                if let text = try? await TrapTubeCaptionSaver.fetchText(track, userAgent: userAgent), !text.isEmpty {
                    let directory = TrapTubeDownloadPaths.downloadsDirectory
                    try? FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
                    let fileURL = directory.appendingPathComponent(trapTubeSafeFileName(title + " [\(track.languageCode)]", ext: "txt"))
                    if (try? text.write(to: fileURL, atomically: true, encoding: .utf8)) != nil {
                        manager.registerLocalFile(fileURL: fileURL, title: title + " · Captions (\(track.languageCode))", mode: "caption", videoID: videoID)
                    }
                }
            }
        }

        downloadStarted = true
        startedMessage = "Download started — track its progress in the TrapTube tab."
    }
}
'''

DIRECT_DOWNLOAD_SWIFT = r'''

// MARK: - Direct downloads for the mod menu (added by ApplyHybridNavigation.py)

enum TrapTubeDirectDownloadError: LocalizedError {
    case badStatus(Int)
    case emptyDownload

    var errorDescription: String? {
        switch self {
        case .badStatus(let code):
            return "The download server returned HTTP \(code)."
        case .emptyDownload:
            return "The download finished without producing a file."
        }
    }
}

/// Minimal URLSession download helper with progress, used by the mod
/// menu's direct-download path on TrapTubeDownloadManager. Downloads land
/// in a temporary file first; the manager moves them into the downloads
/// directory (the TrapTube tab store) when they finish.
final class TrapTubeDirectDownloader: NSObject, URLSessionDownloadDelegate {
    static let shared = TrapTubeDirectDownloader()

    private var session: URLSession!
    private var continuations: [Int: CheckedContinuation<URL, Error>] = [:]
    private var progressBlocks: [Int: (Double) -> Void] = [:]
    private let stateLock = NSLock()

    private override init() {
        super.init()
        session = URLSession(configuration: .default, delegate: self, delegateQueue: nil)
    }

    func download(from url: URL, userAgent: String?, onProgress: @escaping (Double) -> Void) async throws -> URL {
        var request = URLRequest(url: url)
        if let ua = userAgent, !ua.isEmpty {
            request.setValue(ua, forHTTPHeaderField: "User-Agent")
        }
        request.setValue("https://www.youtube.com/", forHTTPHeaderField: "Referer")
        return try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<URL, Error>) in
            let task = session.downloadTask(with: request)
            stateLock.lock()
            continuations[task.taskIdentifier] = continuation
            progressBlocks[task.taskIdentifier] = onProgress
            stateLock.unlock()
            task.resume()
        }
    }

    func urlSession(_ session: URLSession, downloadTask: URLSessionDownloadTask,
                    didWriteData bytesWritten: Int64, totalBytesWritten: Int64,
                    totalBytesExpectedToWrite: Int64) {
        guard totalBytesExpectedToWrite > 0 else { return }
        let fraction = Double(totalBytesWritten) / Double(totalBytesExpectedToWrite)
        stateLock.lock()
        let block = progressBlocks[downloadTask.taskIdentifier]
        stateLock.unlock()
        block?(fraction)
    }

    func urlSession(_ session: URLSession, downloadTask: URLSessionDownloadTask,
                    didFinishDownloadingTo location: URL) {
        // The file at `location` is deleted as soon as this callback
        // returns, so move it into the temp directory right here.
        let suggested = downloadTask.response?.suggestedFilename ?? "download.bin"
        let destination = FileManager.default.temporaryDirectory
            .appendingPathComponent("tt-direct-\(UUID().uuidString)-\(suggested)")
        let result: Result<URL, Error>
        if let http = downloadTask.response as? HTTPURLResponse, !(200...299).contains(http.statusCode) {
            result = .failure(TrapTubeDirectDownloadError.badStatus(http.statusCode))
        } else if (try? FileManager.default.moveItem(at: location, to: destination)) != nil {
            result = .success(destination)
        } else {
            result = .failure(TrapTubeDirectDownloadError.emptyDownload)
        }
        finish(taskIdentifier: downloadTask.taskIdentifier, result: result)
    }

    func urlSession(_ session: URLSession, task: URLSessionTask, didCompleteWithError error: Error?) {
        guard let error = error else { return }
        finish(taskIdentifier: task.taskIdentifier, result: .failure(error))
    }

    private func finish(taskIdentifier: Int, result: Result<URL, Error>) {
        stateLock.lock()
        let continuation = continuations.removeValue(forKey: taskIdentifier)
        progressBlocks.removeValue(forKey: taskIdentifier)
        stateLock.unlock()
        continuation?.resume(with: result)
    }
}
'''

# TypeTypeService.swift: videoID on downloaded media + direct-download API.
p = file("TypeTypeService.swift")
s = p.read_text()
if "var videoID: String?" not in s:
    s = rep(s, """struct TrapTubeDownloadedMedia: Codable, Identifiable {
    let id: String
    let title: String
    let fileName: String
    let mode: String
    let sizeBytes: Int64
    let createdAt: Date
""", """struct TrapTubeDownloadedMedia: Codable, Identifiable {
    let id: String
    let title: String
    let fileName: String
    let mode: String
    let sizeBytes: Int64
    let createdAt: Date
    var videoID: String? = nil
""", "downloaded media videoID")
if "final class TrapTubeDirectDownloader" not in s:
    s += DIRECT_DOWNLOAD_SWIFT
if "func enqueueDirectDownload" not in s:
    s = rep(s, """    func remove(_ item: TrapTubeDownloadedMedia) {
        try? FileManager.default.removeItem(at: item.fileURL)
        completed.removeAll { $0.id == item.id }
        persistCompleted()
    }
""", """    func remove(_ item: TrapTubeDownloadedMedia) {
        try? FileManager.default.removeItem(at: item.fileURL)
        completed.removeAll { $0.id == item.id }
        persistCompleted()
    }

    // MARK: Mod-menu direct downloads

    /// Registers a file that already lives in the downloads directory
    /// (thumbnail, captions) in the completed list shown by the TrapTube tab.
    func registerLocalFile(fileURL: URL, title: String, mode: String, videoID: String?) {
        let size = (try? FileManager.default.attributesOfItem(atPath: fileURL.path))
            .flatMap { ($0[.size] as? NSNumber)?.int64Value } ?? 0
        let item = TrapTubeDownloadedMedia(
            id: UUID().uuidString,
            title: title,
            fileName: fileURL.lastPathComponent,
            mode: mode,
            sizeBytes: size,
            createdAt: Date(),
            videoID: videoID
        )
        completed.insert(item, at: 0)
        persistCompleted()
    }

    /// Downloads a remote media URL straight into the TrapTube tab store,
    /// reporting progress through the same jobs list the downloads view
    /// already renders. Optionally converts audio to MP3 afterwards.
    func enqueueDirectDownload(remoteURL: URL, title: String, mode: String, fileName: String,
                               videoID: String?, convertToMP3: Bool, userAgent: String?) {
        lastError = nil
        let jobID = UUID().uuidString
        jobs.insert(TrapTubeDownloadTask(
            id: jobID, title: title, mode: mode, status: "downloading",
            stage: "Downloading", progress: 0, downloadedBytes: 0,
            totalBytes: 0, speedBytesPerSecond: 0, error: nil
        ), at: 0)
        Task { [weak self] in
            await self?.runDirectDownload(
                jobID: jobID, remoteURL: remoteURL, title: title, mode: mode,
                fileName: fileName, videoID: videoID,
                convertToMP3: convertToMP3, userAgent: userAgent)
        }
    }

    private func runDirectDownload(jobID: String, remoteURL: URL, title: String, mode: String,
                                   fileName: String, videoID: String?,
                                   convertToMP3: Bool, userAgent: String?) async {
        do {
            try FileManager.default.createDirectory(at: downloadsDirectory, withIntermediateDirectories: true)
            let tempURL = try await TrapTubeDirectDownloader.shared.download(
                from: remoteURL, userAgent: userAgent
            ) { [weak self] fraction in
                Task { @MainActor in
                    self?.updateJob(jobID) {
                        $0.progress = fraction
                        $0.stage = "Downloading \(Int(fraction * 100))%"
                    }
                }
            }

            var destination = downloadsDirectory.appendingPathComponent(fileName)
            if FileManager.default.fileExists(atPath: destination.path) {
                let base = destination.deletingPathExtension().lastPathComponent
                let ext = destination.pathExtension
                let suffix = String(UUID().uuidString.prefix(6))
                destination = downloadsDirectory.appendingPathComponent(
                    ext.isEmpty ? "\(base)-\(suffix)" : "\(base)-\(suffix).\(ext)")
            }
            try FileManager.default.moveItem(at: tempURL, to: destination)

            var finalURL = destination
            if convertToMP3 {
                updateJob(jobID) { $0.stage = "Converting to MP3"; $0.progress = 1 }
                let mp3URL = destination.deletingPathExtension().appendingPathExtension("mp3")
                do {
                    try await TrapTubeFFmpegProcessor.execute([
                        "-y", "-i", destination.path,
                        "-vn", "-codec:a", "libmp3lame", "-b:a", "192k",
                        "-id3v2_version", "3", "-metadata", "title=\(title)",
                        mp3URL.path
                    ])
                    guard FileManager.default.fileExists(atPath: mp3URL.path) else {
                        throw TrapTubeFFmpegError.missingOutput
                    }
                    try? FileManager.default.removeItem(at: destination)
                    finalURL = mp3URL
                } catch {
                    lastError = "MP3 conversion failed, so the M4A original was kept: \(error.localizedDescription)"
                }
            }

            let size = (try? FileManager.default.attributesOfItem(atPath: finalURL.path))
                .flatMap { ($0[.size] as? NSNumber)?.int64Value } ?? 0
            let item = TrapTubeDownloadedMedia(
                id: UUID().uuidString,
                title: title,
                fileName: finalURL.lastPathComponent,
                mode: mode,
                sizeBytes: size,
                createdAt: Date(),
                videoID: videoID
            )
            completed.insert(item, at: 0)
            persistCompleted()
            updateJob(jobID) { $0.status = "saved"; $0.stage = "Saved to device"; $0.progress = 1 }
        } catch {
            updateJob(jobID) { $0.status = "failed"; $0.stage = "Failed"; $0.error = error.localizedDescription }
            lastError = error.localizedDescription
        }
    }
""", "direct download manager API")
p.write_text(s)

# YouTubeView.swift: Home web view button injection + mod sheet, then the
# shared mod-menu implementation appended once.
p = file("YouTubeView.swift")
s = p.read_text()
if "homeModCenter" not in s:
    s = rep(s, """    @State private var isLoading = true
    @FocusState private var searchFocused: Bool
""", """    @State private var isLoading = true
    @FocusState private var searchFocused: Bool
    @ObservedObject private var homeModCenter = TrapTubeModCenter.shared
""", "home mod center")
    s = rep(s, """        .preferredColorScheme(.dark)
    }

    private var header: some View {""", """        .preferredColorScheme(.dark)
        .sheet(item: $homeModCenter.activeRequest) { request in
            TrapTubeModSheet(request: request)
                .presentationDetents([.large])
                .presentationDragIndicator(.visible)
                .preferredColorScheme(.dark)
        }
    }

    private var header: some View {""", "home mod sheet")
    s = rep(s, """        configuration.mediaTypesRequiringUserActionForPlayback = []
        let view = WKWebView(frame: .zero, configuration: configuration)
        // Present as mobile Safari""", """        configuration.mediaTypesRequiringUserActionForPlayback = []
        TrapTubeModInstaller.install(into: configuration)
        let view = WKWebView(frame: .zero, configuration: configuration)
        // Present as mobile Safari""", "home mod installer")
if "struct TrapTubeModSheet" not in s:
    s += MOD_MENU_SWIFT
p.write_text(s)


# ---------------------------------------------------------------------------
# Theme picker (phase 2): HSV components on ThemeManager, a Theme Color
# picker in Settings, and Home header accents rerouted to the live theme.
# ---------------------------------------------------------------------------

THEME_PICKER_SWIFT = r'''

// MARK: - Theme color picker (HSV wheel + component sliders + presets)
// Added by ApplyHybridNavigation.py (theme phase). Reads and writes the
// shared ThemeManager components, persisted under TrapTube.Theme.*.

struct TrapTubeThemePickerView: View {
    @EnvironmentObject private var theme: ThemeManager
    @Environment(\.dismiss) private var dismiss
    @State private var copiedHex = false

    private struct ThemePreset: Identifiable {
        let name: String
        let hex: String
        var id: String { hex }
    }

    private static let presets: [ThemePreset] = [
        ThemePreset(name: "TrapTube Red", hex: "E50920"),
        ThemePreset(name: "Crimson", hex: "DC143C"),
        ThemePreset(name: "Purple", hex: "7C3AED"),
        ThemePreset(name: "Royal Blue", hex: "4169E1"),
        ThemePreset(name: "Teal", hex: "14B8A6"),
        ThemePreset(name: "Emerald", hex: "10B981"),
        ThemePreset(name: "Orange", hex: "F97316"),
        ThemePreset(name: "Gold", hex: "D4AF37"),
        ThemePreset(name: "Hot Pink", hex: "FF69B4"),
        ThemePreset(name: "Violet", hex: "8B5CF6"),
        ThemePreset(name: "Mono White", hex: "F4F4F5")
    ]

    private static var hueColors: [Color] {
        (0...6).map { Color(hue: Double($0) / 6.0, saturation: 1, brightness: 1) }
    }

    var body: some View {
        NavigationStack {
            ScrollView(showsIndicators: false) {
                VStack(spacing: 22) {
                    wheel
                    previewCard
                    sliderCard
                    presetsCard
                    Button("Reset to TrapTube Red") { theme.reset() }
                        .font(.subheadline.bold())
                        .foregroundStyle(theme.accentSolid)
                    Text("The accent color and its opacity drive the tab bar tint, the Home header accents, the injected mod button, and buttons throughout the app. Changes apply live and are saved automatically.")
                        .font(.caption)
                        .foregroundStyle(Color(hex: "A6A4A6"))
                        .multilineTextAlignment(.center)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .padding(20)
            }
            .background(Color(hex: "080809").ignoresSafeArea())
            .navigationTitle("Theme Color")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done") { dismiss() }
                        .fontWeight(.semibold)
                        .tint(theme.accentSolid)
                }
            }
        }
        .preferredColorScheme(.dark)
    }

    // MARK: Wheel (angle = hue, distance from center = saturation)

    private var wheel: some View {
        let size: CGFloat = 264
        let radius = Double(size / 2)
        let thumbDistance = theme.themeSaturation * (radius - 16)
        let thumbAngle = theme.themeHue * 2 * Double.pi - Double.pi / 2
        return ZStack {
            Circle()
                .fill(AngularGradient(gradient: Gradient(colors: Self.hueColors),
                                      center: .center,
                                      startAngle: .degrees(-90),
                                      endAngle: .degrees(270)))
            Circle()
                .fill(RadialGradient(colors: [.white, .white.opacity(0)],
                                     center: .center, startRadius: 0, endRadius: CGFloat(radius)))
            Circle()
                .fill(Color.black.opacity(1 - theme.themeBrightness))
            Circle()
                .stroke(.white.opacity(0.14), lineWidth: 1)
            Circle()
                .fill(theme.accentSolid)
                .frame(width: 26, height: 26)
                .overlay(Circle().stroke(.white, lineWidth: 3))
                .shadow(color: .black.opacity(0.45), radius: 4, y: 2)
                .offset(x: CGFloat(cos(thumbAngle) * thumbDistance),
                        y: CGFloat(sin(thumbAngle) * thumbDistance))
        }
        .frame(width: size, height: size)
        .contentShape(Circle())
        .gesture(
            DragGesture(minimumDistance: 0)
                .onChanged { value in
                    let dx = Double(value.location.x) - radius
                    let dy = Double(value.location.y) - radius
                    let maxDistance = radius - 16
                    let distance = min(maxDistance, hypot(dx, dy))
                    var hue = (atan2(dy, dx) + Double.pi / 2) / (2 * Double.pi)
                    if hue < 0 { hue += 1 }
                    theme.applyComponents(hue: hue,
                                          saturation: distance / maxDistance,
                                          brightness: theme.themeBrightness,
                                          opacity: theme.themeOpacity)
                }
        )
        .accessibilityLabel("Color wheel. Drag to change hue and saturation.")
    }

    // MARK: Preview (resulting color over dark and light, hex + RGB)

    private var previewCard: some View {
        VStack(spacing: 10) {
            ZStack {
                HStack(spacing: 0) {
                    Color(hex: "0B0B0E")
                    Color.white
                }
                RoundedRectangle(cornerRadius: 12)
                    .fill(theme.accent)
                    .frame(width: 132, height: 44)
                    .overlay(RoundedRectangle(cornerRadius: 12).stroke(.white.opacity(0.25), lineWidth: 1))
            }
            .frame(height: 76)
            .clipShape(RoundedRectangle(cornerRadius: 16))
            .overlay(RoundedRectangle(cornerRadius: 16).stroke(.white.opacity(0.10), lineWidth: 1))

            HStack(spacing: 10) {
                Button {
                    UIPasteboard.general.string = theme.accentHexDisplay
                    copiedHex = true
                } label: {
                    HStack(spacing: 6) {
                        Text(theme.accentHexDisplay).font(.headline.monospaced())
                        Image(systemName: copiedHex ? "checkmark" : "doc.on.doc").font(.caption.bold())
                    }
                    .foregroundStyle(.white)
                }
                .buttonStyle(.plain)
                Spacer()
                Text(rgbaText)
                    .font(.caption.monospaced())
                    .foregroundStyle(Color(hex: "A6A4A6"))
            }
        }
        .padding(14)
        .background(.white.opacity(0.055), in: RoundedRectangle(cornerRadius: 20))
        .overlay(RoundedRectangle(cornerRadius: 20).stroke(.white.opacity(0.10), lineWidth: 1))
    }

    private var rgbaText: String {
        let rgb = TrapTubeHSV.rgb(hue: theme.themeHue, saturation: theme.themeSaturation, brightness: theme.themeBrightness)
        return "RGB \(rgb.r) \(rgb.g) \(rgb.b) · \(Int((theme.themeOpacity * 100).rounded()))%"
    }

    // MARK: Component sliders

    private var sliderCard: some View {
        VStack(spacing: 16) {
            componentSlider(
                title: "Saturation",
                value: theme.themeSaturation,
                stripColors: [Color(hue: theme.themeHue, saturation: 0, brightness: theme.themeBrightness),
                              theme.accentSolid]
            ) { theme.applyComponents(hue: theme.themeHue, saturation: $0, brightness: theme.themeBrightness, opacity: theme.themeOpacity) }

            componentSlider(
                title: "Brightness",
                value: theme.themeBrightness,
                stripColors: [.black, theme.accentSolid]
            ) { theme.applyComponents(hue: theme.themeHue, saturation: theme.themeSaturation, brightness: $0, opacity: theme.themeOpacity) }

            componentSlider(
                title: "Opacity",
                value: theme.themeOpacity,
                stripColors: [theme.accentSolid.opacity(0), theme.accentSolid]
            ) { theme.applyComponents(hue: theme.themeHue, saturation: theme.themeSaturation, brightness: theme.themeBrightness, opacity: $0) }
        }
        .padding(16)
        .background(.white.opacity(0.055), in: RoundedRectangle(cornerRadius: 20))
        .overlay(RoundedRectangle(cornerRadius: 20).stroke(.white.opacity(0.10), lineWidth: 1))
    }

    private func componentSlider(title: String, value: Double, stripColors: [Color],
                                 onChange: @escaping (Double) -> Void) -> some View {
        VStack(spacing: 7) {
            HStack {
                Text(title).font(.subheadline.bold()).foregroundStyle(.white)
                Spacer()
                Text("\(Int((value * 100).rounded()))%")
                    .font(.subheadline.monospacedDigit())
                    .foregroundStyle(Color(hex: "D2D0D2"))
            }
            RoundedRectangle(cornerRadius: 4)
                .fill(LinearGradient(colors: stripColors, startPoint: .leading, endPoint: .trailing))
                .frame(height: 8)
            Slider(value: Binding(get: { value }, set: onChange), in: 0...1)
                .tint(theme.accentSolid)
        }
    }

    // MARK: Presets

    private var presetsCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Preset themes").font(.headline.bold()).foregroundStyle(.white)
            LazyVGrid(columns: [GridItem(.adaptive(minimum: 76), spacing: 12)], spacing: 14) {
                ForEach(Self.presets) { preset in
                    Button {
                        let hsv = TrapTubeHSV.hsv(fromHex: preset.hex)
                        theme.applyComponents(hue: hsv.hue, saturation: hsv.saturation,
                                              brightness: hsv.brightness, opacity: 1)
                    } label: {
                        VStack(spacing: 7) {
                            Circle()
                                .fill(Color(hex: preset.hex))
                                .frame(width: 42, height: 42)
                                .overlay(Circle().stroke(.white.opacity(0.15), lineWidth: 1))
                            Text(preset.name)
                                .font(.caption2.weight(.semibold))
                                .foregroundStyle(.white)
                                .lineLimit(1)
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 7)
                        .background(theme.accentHex == preset.hex ? .white.opacity(0.10) : .clear,
                                    in: RoundedRectangle(cornerRadius: 13))
                        .overlay(RoundedRectangle(cornerRadius: 13)
                            .stroke(theme.accentHex == preset.hex ? theme.accentSolid : .white.opacity(0.07), lineWidth: 1))
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel("\(preset.name) theme")
                }
            }
        }
        .padding(16)
        .background(.white.opacity(0.055), in: RoundedRectangle(cornerRadius: 20))
        .overlay(RoundedRectangle(cornerRadius: 20).stroke(.white.opacity(0.10), lineWidth: 1))
    }
}
'''

def rep_all(source, old, new, label):
    n = source.count(old)
    if n == 0:
        if new in source:
            return source
        raise SystemExit(f"Missing expected pattern: {label}")
    return source.replace(old, new)

# ThemeManager.swift: HSV component state (TrapTube.Theme.*), persisted.
p = file("ThemeManager.swift")
s = p.read_text()
if "themeHue" not in s:
    s = rep(s, """    @Published private(set) var accentHex: String {
        didSet { UserDefaults.standard.set(accentHex, forKey: "theme.accent") }
    }
""", """    @Published private(set) var accentHex: String {
        didSet { UserDefaults.standard.set(accentHex, forKey: "theme.accent") }
    }

    /// HSV components of the current accent, persisted under
    /// TrapTube.Theme.* and edited by the Theme Color picker.
    @Published private(set) var themeHue: Double
    @Published private(set) var themeSaturation: Double
    @Published private(set) var themeBrightness: Double
    @Published private(set) var themeOpacity: Double
""", "theme component state")
    s = rep(s, """    init() {
        let saved = UserDefaults.standard.string(forKey: "theme.accent") ?? "E50920"
        accentHex = Self.accents.first(where: { $0.hex == saved })?.hex ?? "E50920"
    }
""", """    init() {
        let defaults = UserDefaults.standard
        let saved = defaults.string(forKey: "theme.accent") ?? "E50920"
        let isValidHex = saved.count == 6 && saved.allSatisfy { $0.isHexDigit }
        let initialHex = isValidHex ? saved.uppercased() : "E50920"
        accentHex = initialHex
        if defaults.object(forKey: "TrapTube.Theme.Hue") != nil {
            themeHue = defaults.double(forKey: "TrapTube.Theme.Hue")
            themeSaturation = defaults.double(forKey: "TrapTube.Theme.Saturation")
            themeBrightness = defaults.double(forKey: "TrapTube.Theme.Brightness")
            themeOpacity = defaults.object(forKey: "TrapTube.Theme.Opacity") != nil
                ? defaults.double(forKey: "TrapTube.Theme.Opacity") : 1
            accentHex = TrapTubeHSV.hex(hue: themeHue, saturation: themeSaturation, brightness: themeBrightness)
            defaults.set(accentHex, forKey: "theme.accent")
        } else {
            let hsv = TrapTubeHSV.hsv(fromHex: initialHex)
            themeHue = hsv.hue
            themeSaturation = hsv.saturation
            themeBrightness = hsv.brightness
            themeOpacity = 1
        }
    }
""", "theme init")
    s = rep(s, "    var accent: Color { Color(hex: accentHex) }",
    """    var accent: Color {
        Color(hue: themeHue, saturation: themeSaturation, brightness: themeBrightness, opacity: themeOpacity)
    }
    /// Full-opacity accent for text-critical surfaces.
    var accentSolid: Color { Color(hex: accentHex) }
    var accentHexDisplay: String { "#" + accentHex }""", "theme accent accessors")
    s = rep(s, "    var selectedAccent: AccentOption { Self.accents.first(where: { $0.hex == accentHex }) ?? Self.accents[0] }",
            "    var selectedAccent: AccentOption { Self.accents.first(where: { $0.hex == accentHex }) ?? AccentOption(name: \"Custom\", hex: accentHex) }",
            "theme selected accent")
    s = rep(s, """    func selectAccent(_ option: AccentOption) { accentHex = option.hex }
    func reset() { accentHex = "E50920" }""",
    """    func selectAccent(_ option: AccentOption) {
        let hsv = TrapTubeHSV.hsv(fromHex: option.hex)
        applyComponents(hue: hsv.hue, saturation: hsv.saturation, brightness: hsv.brightness, opacity: themeOpacity)
    }

    /// Single write path for the picker's wheel, sliders, and presets.
    func applyComponents(hue: Double, saturation: Double, brightness: Double, opacity: Double) {
        themeHue = min(1, max(0, hue))
        themeSaturation = min(1, max(0, saturation))
        themeBrightness = min(1, max(0, brightness))
        themeOpacity = min(1, max(0, opacity))
        accentHex = TrapTubeHSV.hex(hue: themeHue, saturation: themeSaturation, brightness: themeBrightness)
        let defaults = UserDefaults.standard
        defaults.set(themeHue, forKey: "TrapTube.Theme.Hue")
        defaults.set(themeSaturation, forKey: "TrapTube.Theme.Saturation")
        defaults.set(themeBrightness, forKey: "TrapTube.Theme.Brightness")
        defaults.set(themeOpacity, forKey: "TrapTube.Theme.Opacity")
    }

    func reset() {
        let hsv = TrapTubeHSV.hsv(fromHex: "E50920")
        applyComponents(hue: hsv.hue, saturation: hsv.saturation, brightness: hsv.brightness, opacity: 1)
    }""", "theme component writes")
p.write_text(s)

# SettingsView.swift: Appearance card + Theme Color sheet + picker view.
p = file("SettingsView.swift")
s = p.read_text()
if "showThemePicker" not in s:
    s = rep(s, "import SwiftUI\n\nstruct SettingsView: View {",
            "import SwiftUI\nimport UIKit\n\nstruct SettingsView: View {", "settings imports")
    s = rep(s, "    @State private var showCustomization = false\n",
            "    @State private var showCustomization = false\n    @State private var showThemePicker = false\n",
            "settings theme picker state")
    s = rep(s, """        .sheet(isPresented: $showEqualizer) { EqualizerView().environmentObject(player).environmentObject(theme).presentationDetents([.large]) }
""", """        .sheet(isPresented: $showEqualizer) { EqualizerView().environmentObject(player).environmentObject(theme).presentationDetents([.large]) }
        .sheet(isPresented: $showThemePicker) { TrapTubeThemePickerView().environmentObject(theme).presentationDetents([.large]).presentationDragIndicator(.visible) }
""", "settings theme picker sheet")
    s = rep(s, """                settingsCard(title: "Video discovery", icon: "play.rectangle.fill") {""",
    """                settingsCard(title: "Appearance", icon: "paintpalette.fill") {
                    HStack(spacing: 12) {
                        RoundedRectangle(cornerRadius: 9).fill(theme.accent).frame(width: 34, height: 34)
                            .overlay(RoundedRectangle(cornerRadius: 9).stroke(.white.opacity(0.16), lineWidth: 1))
                        VStack(alignment: .leading, spacing: 3) {
                            Text("Theme Color").font(.subheadline.bold()).foregroundStyle(.white)
                            Text("HSV wheel, sliders, and presets. Current accent: " + theme.accentHexDisplay)
                                .font(.caption).foregroundStyle(Color(hex: "A6A4A6"))
                        }
                        Spacer()
                        Button("Open") { showThemePicker = true }
                            .font(.subheadline.bold()).foregroundStyle(theme.accentSolid)
                    }
                }

                settingsCard(title: "Video discovery", icon: "play.rectangle.fill") {""",
            "settings appearance card")
if "struct TrapTubeThemePickerView" not in s:
    s += THEME_PICKER_SWIFT
p.write_text(s)

# YouTubeView.swift: Home header accents follow the live theme.
p = file("YouTubeView.swift")
s = p.read_text()
s = rep_all(s, "RadialGradient(colors: [Color(hex: \"A90012\").opacity(0.22), .clear],",
            "RadialGradient(colors: [theme.accent.opacity(0.22), .clear],", "home backdrop accent")
s = rep_all(s, ".shadow(color: Color(hex: \"F01D2D\").opacity(0.34), radius: 10, y: 3)",
            ".shadow(color: theme.accent.opacity(0.34), radius: 10, y: 3)", "home header shadow accent")
s = rep_all(s, ".tint(Color(hex: \"FF3948\"))", ".tint(theme.accent)", "home tint accent")
s = rep_all(s, "LinearGradient(colors: [Color(hex: \"FF303B\"), Color(hex: \"A90012\")]",
            "LinearGradient(colors: [theme.accent, theme.accent.opacity(0.62)]", "home gradient accents")
p.write_text(s)


# =====================================================================
# Round 3 - dead mod button fix, persistent playback + mini player,
# in-player stream EQ with proof of attachment, functional streaming
# quality presets, and an OLED dark mode switch.
#
# Item 1 diagnosis (from the shipped code): the script-message handler
# registration was CORRECT - TrapTubeModInstaller.install ran on the
# configuration both WKWebViews were created with, and both hosts
# observed the shared center and presented the sheet. The failure was
# in the page: the button lived INSIDE #movie_player, where the mobile
# player's full-surface gesture/chrome layers sit above it and swallow
# taps, and the click path had no fallback - a failed postMessage was
# swallowed by the never-throw handler and nothing else could happen.
# Fix: buttons are attached to document.body with position:fixed over
# the player's rect (recomputed on resize/scroll/SPA changes), handle
# touchstart AND click, and fall back to a traptube-mod:// /
# traptube-eq:// navigation that the coordinators intercept.
#
# Item 2 diagnosis: RootView switches tabs with a `switch` over
# @State selectedTab, so the inactive tab's whole hierarchy - including
# the WKWebView - is destroyed on every tab switch. Fix:
# TrapTubePlayerSession owns both watch web views for the app's
# lifetime; the host representables return the session's view and
# their dismantleUIView is a no-op, and the RootView mini player
# re-parents the SAME web view into a bar above the tab bar.
# =====================================================================

def splice_between(source, start_marker, end_marker, replacement, label):
    if replacement in source:
        return source
    if start_marker not in source:
        raise SystemExit("round3 splice start missing: " + label)
    i = source.index(start_marker)
    j = source.index(end_marker, i)
    return source[:i] + replacement + source[j:]


def splice_function(source, anchor, new_text, label):
    if new_text in source:
        return source
    if anchor not in source:
        raise SystemExit("round3 function anchor missing: " + label)
    i = source.index(anchor)
    brace = source.index("{", i)
    depth = 0
    k = brace
    in_str = False
    esc = False
    in_comment = False
    while k < len(source):
        ch = source[k]
        nxt = source[k + 1] if k + 1 < len(source) else ""
        if in_comment:
            if ch == "\n":
                in_comment = False
        elif in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        else:
            if ch == "/" and nxt == "/":
                in_comment = True
            elif ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    break
        k += 1
    if depth != 0:
        raise SystemExit("round3 function brace match failed: " + label)
    return source[:i] + new_text + source[k + 1:]


p = file("YouTubeView.swift")
s = p.read_text()

# --- Item 1+3+4: replace the installer (new body-fixed buttons with a
# scheme fallback, EQ graph script, page-world quality script, and the
# trapTubeEQ / trapTubeState handlers registered alongside trapTubeMod).
NEW_INSTALLER = r'''enum TrapTubeModInstaller {
    static func install(into configuration: WKWebViewConfiguration) {
        let controller = configuration.userContentController
        controller.add(TrapTubeModScriptHandler.shared, name: "trapTubeMod")
        controller.add(TrapTubeWebEQScriptHandler.shared, name: "trapTubeEQ")
        controller.add(TrapTubeWatchStateHandler.shared, name: "trapTubeState")
        controller.addUserScript(WKUserScript(source: scriptSource, injectionTime: .atDocumentEnd, forMainFrameOnly: true))
        controller.addUserScript(WKUserScript(source: TrapTubeWebEQInstaller.scriptSource, injectionTime: .atDocumentEnd, forMainFrameOnly: true))
        controller.addUserScript(WKUserScript(source: TrapTubeQualityInstaller.scriptSource, injectionTime: .atDocumentEnd, forMainFrameOnly: true, in: .page))
    }

    private static var scriptSource: String {
        let colors = TrapTubeAccentColors.currentGradientHex
        return #"""
        (() => {
          if (window.__trapTubeModInstalled) return;
          window.__trapTubeModInstalled = true;
          var MOD_ID = "traptube-mod-btn";
          var EQ_ID = "traptube-eq-btn";
          var modBtn = null;
          var eqBtn = null;
          function currentVideoID() {
            try {
              var params = new URLSearchParams(window.location.search);
              var v = params.get("v");
              if (v) return v;
              var match = window.location.pathname.match(/\/shorts\/([\w-]{6,})/);
              if (match) return match[1];
              var canonical = document.querySelector("link[rel='canonical']");
              if (canonical && canonical.href) {
                var m2 = canonical.href.match(/[?&]v=([\w-]{6,})/);
                if (m2) return m2[1];
              }
            } catch (e) {}
            return null;
          }
          function playerRect() {
            var p = document.querySelector("#movie_player") || document.querySelector(".html5-video-player");
            if (!p) return null;
            var r = p.getBoundingClientRect();
            if (!r || r.width < 60 || r.height < 60) return null;
            return r;
          }
          function post(name, payload) {
            try {
              var handlers = window.webkit && window.webkit.messageHandlers;
              var h = handlers && handlers[name];
              if (h) { h.postMessage(payload); return true; }
            } catch (e) {}
            return false;
          }
          function fireMod() {
            var id = currentVideoID();
            if (!id) return;
            var payload = { videoID: id, title: document.title || "", url: window.location.href };
            if (!post("trapTubeMod", payload)) {
              try {
                window.location.href = "traptube-mod://open?v=" + encodeURIComponent(id) + "&t=" + encodeURIComponent(document.title || "");
              } catch (e) {}
            }
          }
          function fireEQ() {
            if (!post("trapTubeEQ", { action: "open" })) {
              try { window.location.href = "traptube-eq://open"; } catch (e) {}
            }
          }
          function makeButton(id, label, fontSize, fire) {
            var btn = document.createElement("button");
            btn.id = id;
            btn.type = "button";
            btn.setAttribute("aria-label", id === MOD_ID ? "TrapTube menu" : "TrapTube stream EQ");
            btn.textContent = label;
            btn.style.cssText = "position:fixed;z-index:2147483647;width:40px;height:40px;border-radius:12px;border:1px solid rgba(255,255,255,0.4);background:linear-gradient(135deg,\#(colors.0),\#(colors.1));color:#ffffff;font-size:" + fontSize + ";font-weight:900;line-height:1;display:none;align-items:center;justify-content:center;cursor:pointer;box-shadow:0 4px 14px rgba(0,0,0,0.5);padding:0;margin:0;pointer-events:auto;touch-action:manipulation;-webkit-tap-highlight-color:transparent;";
            var lastFire = 0;
            function handler(ev) {
              try { ev.preventDefault(); ev.stopPropagation(); } catch (e) {}
              var now = Date.now();
              if (now - lastFire < 700) return;
              lastFire = now;
              fire();
            }
            btn.addEventListener("touchstart", handler, { passive: false });
            btn.addEventListener("click", handler);
            document.body.appendChild(btn);
            return btn;
          }
          function ensure() {
            try {
              if (!document.body) return;
              if (modBtn && !document.contains(modBtn)) modBtn = null;
              if (eqBtn && !document.contains(eqBtn)) eqBtn = null;
              if (!modBtn) modBtn = makeButton(MOD_ID, "↓", "19px", fireMod);
              if (!eqBtn) eqBtn = makeButton(EQ_ID, "EQ", "12px", fireEQ);
              var id = currentVideoID();
              var r = id ? playerRect() : null;
              if (!r) {
                modBtn.style.display = "none";
                eqBtn.style.display = "none";
                return;
              }
              var top = Math.max(0, r.top + 54);
              modBtn.style.display = "flex";
              eqBtn.style.display = "flex";
              modBtn.style.left = (r.right - 50) + "px";
              modBtn.style.top = top + "px";
              eqBtn.style.left = (r.right - 98) + "px";
              eqBtn.style.top = top + "px";
            } catch (e) {}
          }
          function reportState() {
            try {
              var id = currentVideoID();
              var v = document.querySelector("#movie_player video") || document.querySelector("video");
              var title = (document.title || "").replace(/ - YouTube$/, "");
              post("trapTubeState", { videoID: id || "", title: title, playing: !!(v && !v.paused && !v.ended) });
            } catch (e) {}
          }
          function tick() { ensure(); reportState(); }
          function start() {
            tick();
            try {
              new MutationObserver(function () { ensure(); }).observe(document.documentElement, { childList: true, subtree: true });
            } catch (e) {}
            setInterval(tick, 1500);
            window.addEventListener("resize", ensure);
            window.addEventListener("scroll", ensure, true);
            document.addEventListener("yt-navigate-finish", function () { setTimeout(tick, 60); });
            document.addEventListener("play", reportState, true);
            document.addEventListener("pause", reportState, true);
          }
          if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", start);
          } else {
            start();
          }
        })()
        """#
    }
}
'''
s = splice_between(s, "enum TrapTubeModInstaller {", "\n// MARK: InnerTube stream resolution", NEW_INSTALLER, "mod installer round 3")

# --- Item 1: both coordinators intercept the fallback schemes.
s = rep_all(s, """        func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction,
                     decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
            decisionHandler(.allow)
        }""",
            """        func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction,
                     decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
            if TrapTubePlayerSession.shared.handleNavigationAction(navigationAction, webView: webView) {
                decisionHandler(.cancel)
                return
            }
            decisionHandler(.allow)
        }""", "coordinator scheme interception")
p.write_text(s)

# --- Item 2: both watch web views are now created once and owned by
# TrapTubePlayerSession; the representables return the shared view and
# never dismantle it, so tab switches cannot kill playback.
p = file("YouTubeView.swift")
s = p.read_text()

HOME_MAKE = """    func makeUIView(context: Context) -> WKWebView {
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .default()
        configuration.allowsInlineMediaPlayback = true
        configuration.mediaTypesRequiringUserActionForPlayback = []"""
HOME_NEW = """    func makeUIView(context: Context) -> WKWebView {
        let view = TrapTubePlayerSession.shared.webView(for: .home) {
            let configuration = WKWebViewConfiguration()
            configuration.websiteDataStore = .default()
            configuration.allowsInlineMediaPlayback = true
            configuration.mediaTypesRequiringUserActionForPlayback = []
            TrapTubeModInstaller.install(into: configuration)
            let created = WKWebView(frame: .zero, configuration: configuration)
            // Present as mobile Safari: Google refuses to run its sign-in flow
            // for the default WKWebView user agent ("browser may not be secure").
            created.customUserAgent = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1"
            created.isOpaque = false
            created.backgroundColor = .black
            created.scrollView.backgroundColor = .black
            created.underPageBackgroundColor = .black
            // Let the web view use the full safe area so the page header is
            // not pinned underneath the status bar.
            created.scrollView.contentInsetAdjustmentBehavior = .automatic
            created.allowsBackForwardNavigationGestures = true
            return created
        }
        view.navigationDelegate = context.coordinator
        context.coordinator.webView = view
        onCreated(view)
        if TrapTubePlayerSession.shared.claimInitialLoad(for: .home) {
            view.load(URLRequest(url: url, cachePolicy: .useProtocolCachePolicy, timeoutInterval: 30))
        }
        return view
    }

    static func dismantleUIView(_ uiView: WKWebView, coordinator: Coordinator) {
        // TrapTubePlayerSession owns this web view for the app's lifetime.
        // Leaving it in place here keeps any playing stream alive while the
        // session re-parents it into the mini player (or back to this tab);
        // SwiftUI destroying it on a tab switch is what stopped playback.
    }"""
s = splice_function(s, HOME_MAKE, HOME_NEW, "home makeUIView session-owned")

ACCOUNT_MAKE = """    func makeUIView(context: Context) -> WKWebView {
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .default()
        configuration.allowsInlineMediaPlayback = true
        TrapTubeModInstaller.install(into: configuration)"""
ACCOUNT_NEW = """    func makeUIView(context: Context) -> WKWebView {
        let view = TrapTubePlayerSession.shared.webView(for: .you) {
            let configuration = WKWebViewConfiguration()
            configuration.websiteDataStore = .default()
            configuration.allowsInlineMediaPlayback = true
            TrapTubeModInstaller.install(into: configuration)
            let created = WKWebView(frame: .zero, configuration: configuration)
            // Same mobile-Safari identity as the Home tab so the signed-in
            // session and the account surface behave identically.
            created.customUserAgent = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1"
            created.isOpaque = false
            created.backgroundColor = .black
            created.scrollView.backgroundColor = .black
            created.underPageBackgroundColor = .black
            // Full safe area: the account header must clear the status bar.
            created.scrollView.contentInsetAdjustmentBehavior = .automatic
            created.allowsBackForwardNavigationGestures = true
            return created
        }
        view.navigationDelegate = context.coordinator
        context.coordinator.webView = view
        if TrapTubePlayerSession.shared.claimInitialLoad(for: .you) {
            view.load(URLRequest(url: url, cachePolicy: .useProtocolCachePolicy, timeoutInterval: 30))
        }
        return view
    }

    static func dismantleUIView(_ uiView: WKWebView, coordinator: Coordinator) {
        // See YouTubeHomeWebView: the session owns the web view so playback
        // survives tab switches via the RootView mini player.
    }"""
s = splice_function(s, ACCOUNT_MAKE, ACCOUNT_NEW, "account makeUIView session-owned")

# --- Item 3: both hosts observe the EQ center and present the EQ sheet
# exactly like the mod sheet.
s = rep(s, "    @ObservedObject private var homeModCenter = TrapTubeModCenter.shared\n",
        "    @ObservedObject private var homeModCenter = TrapTubeModCenter.shared\n    @ObservedObject private var homeEQCenter = TrapTubeWebEQCenter.shared\n",
        "home EQ center wiring")
s = rep(s, """        .sheet(item: $homeModCenter.activeRequest) { request in
            TrapTubeModSheet(request: request)
                .presentationDetents([.large])
                .presentationDragIndicator(.visible)
                .preferredColorScheme(.dark)
        }""",
        """        .sheet(item: $homeModCenter.activeRequest) { request in
            TrapTubeModSheet(request: request)
                .presentationDetents([.large])
                .presentationDragIndicator(.visible)
                .preferredColorScheme(.dark)
        }
        .sheet(item: $homeEQCenter.activeRequest) { request in
            TrapTubeWebEQSheet(host: request.host)
                .environmentObject(theme)
        }""", "home EQ sheet")
s = rep(s, "    @ObservedObject private var modCenter = TrapTubeModCenter.shared\n",
        "    @ObservedObject private var modCenter = TrapTubeModCenter.shared\n    @ObservedObject private var eqCenter = TrapTubeWebEQCenter.shared\n",
        "account EQ center wiring")
s = rep(s, """        .sheet(item: $modCenter.activeRequest) { request in
            TrapTubeModSheet(request: request)
                .presentationDetents([.large])
                .presentationDragIndicator(.visible)
                .preferredColorScheme(.dark)
        }""",
        """        .sheet(item: $modCenter.activeRequest) { request in
            TrapTubeModSheet(request: request)
                .presentationDetents([.large])
                .presentationDragIndicator(.visible)
                .preferredColorScheme(.dark)
        }
        .sheet(item: $eqCenter.activeRequest) { request in
            TrapTubeWebEQSheet(host: request.host)
                .environmentObject(theme)
        }""", "account EQ sheet")

# --- Item 5 (Home surface): the Home backdrop follows the OLED switch.
s = rep(s, "Color(red: 0.025, green: 0.025, blue: 0.035).ignoresSafeArea()",
        "(theme.oledEnabled ? Color.black : Color(red: 0.025, green: 0.025, blue: 0.035)).ignoresSafeArea()",
        "home backdrop OLED")

# --- Item 4: the quality cap picks the download sheet's defaults.
s = rep(s, "            return info.muxed.first { $0.itag == selectedVideoItag } ?? info.muxed.first",
        "            return info.muxed.first { $0.itag == selectedVideoItag } ?? info.muxed.first { TrapTubeStreamingQuality.withinCap($0.height) } ?? info.muxed.first",
        "download sheet cap default")
s = rep(s, "        if selectedVideoItag == nil { selectedVideoItag = info.muxed.first?.itag }",
        "        if selectedVideoItag == nil { selectedVideoItag = (info.muxed.first { TrapTubeStreamingQuality.withinCap($0.height) } ?? info.muxed.first)?.itag }",
        "download sheet cap applyDefaults")
p.write_text(s)

# --- Round 3 types, appended to YouTubeView.swift.
ROUND3_SWIFT = r'''
// MARK: - Round 3: player session, stream EQ, quality caps

enum TrapTubeHostTab: Hashable {
    case home
    case you
}

/// Owns the two watch web views for the whole app lifetime. RootView's
/// tab switch destroys and recreates SwiftUI hierarchies, so anything
/// the views own dies with them - the session is what keeps a stream
/// (and its web view) alive across tab switches, and it re-parents the
/// SAME web view into the mini player instead of recreating it.
final class TrapTubePlayerSession: ObservableObject {
    static let shared = TrapTubePlayerSession()

    private var webViews: [TrapTubeHostTab: WKWebView] = [:]
    private var initialLoadClaimed: Set<TrapTubeHostTab> = []

    @Published private(set) var watchHost: TrapTubeHostTab?
    @Published private(set) var watchVideoID: String?
    @Published private(set) var watchTitle: String = ""
    @Published private(set) var watchIsPlaying: Bool = false
    private var dismissedVideoID: String?

    private init() {}

    func webView(for host: TrapTubeHostTab, builder: () -> WKWebView) -> WKWebView {
        if let existing = webViews[host] { return existing }
        let created = builder()
        webViews[host] = created
        return created
    }

    func webViewIfExists(for host: TrapTubeHostTab) -> WKWebView? { webViews[host] }

    func host(for webView: WKWebView?) -> TrapTubeHostTab? {
        guard let webView else { return nil }
        return webViews.first { $0.value === webView }?.key
    }

    func claimInitialLoad(for host: TrapTubeHostTab) -> Bool {
        if initialLoadClaimed.contains(host) { return false }
        initialLoadClaimed.insert(host)
        return true
    }

    /// Fallback channel for the injected player buttons: if the script
    /// message handler is unavailable in the page, the buttons navigate
    /// to traptube-mod:// / traptube-eq:// and both coordinators land
    /// here. Returns true when the navigation was handled (and must be
    /// cancelled).
    func handleNavigationAction(_ action: WKNavigationAction, webView: WKWebView) -> Bool {
        guard let url = action.request.url, let scheme = url.scheme else { return false }
        if scheme == "traptube-mod" {
            let items = URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems ?? []
            let videoID = items.first { $0.name == "v" }?.value ?? ""
            let title = items.first { $0.name == "t" }?.value ?? ""
            if !videoID.isEmpty {
                TrapTubeModCenter.shared.present(videoID: videoID, pageTitle: title)
            }
            return true
        }
        if scheme == "traptube-eq" {
            TrapTubeWebEQCenter.shared.present(host: host(for: webView))
            return true
        }
        return false
    }

    func reportWatchState(host: TrapTubeHostTab, videoID: String, title: String, playing: Bool) {
        if !videoID.isEmpty {
            if videoID == dismissedVideoID { return }
            dismissedVideoID = nil
            watchHost = host
            watchVideoID = videoID
            if !title.isEmpty { watchTitle = title }
            watchIsPlaying = playing
        } else if watchHost == host {
            watchHost = nil
            watchVideoID = nil
            watchIsPlaying = false
        }
    }

    func togglePlay() {
        guard let host = watchHost, let view = webViews[host] else { return }
        view.evaluateJavaScript("(() => { var v = document.querySelector('video'); if (!v) return; if (v.paused) { var p = v.play(); if (p && p.catch) p.catch(function(){}); } else { v.pause(); } })()")
        watchIsPlaying.toggle()
    }

    func closeMini() {
        guard let host = watchHost else { return }
        webViews[host]?.evaluateJavaScript("(() => { var v = document.querySelector('video'); if (v) v.pause(); })()")
        dismissedVideoID = watchVideoID
        watchHost = nil
        watchVideoID = nil
        watchIsPlaying = false
    }

    func applyQualityCapToAll() {
        let cap = TrapTubeStreamingQuality.cap
        for (_, view) in webViews {
            view.evaluateJavaScript("window.__trapTubeSetQualityCap && window.__trapTubeSetQualityCap(\(cap))", in: nil, in: WKContentWorld.page, completionHandler: { _ in })
        }
    }

    func applyWebEQToAll() {
        let json = TrapTubeWebEQ.shared.settingsJSON
        for (_, view) in webViews {
            view.evaluateJavaScript("window.__traptubeWebSetEQ && window.__traptubeWebSetEQ(\(json))")
        }
    }

    func requestEQStatus(for host: TrapTubeHostTab) {
        webViews[host]?.evaluateJavaScript("window.__traptubeWebEQReport && window.__traptubeWebEQReport()")
    }
}

final class TrapTubeWatchStateHandler: NSObject, WKScriptMessageHandler {
    static let shared = TrapTubeWatchStateHandler()
    private override init() { super.init() }

    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard message.name == "trapTubeState",
              let body = message.body as? [String: Any],
              let host = TrapTubePlayerSession.shared.host(for: message.webView) else { return }
        let videoID = body["videoID"] as? String ?? ""
        let title = body["title"] as? String ?? ""
        let playing = (body["playing"] as? NSNumber)?.boolValue ?? false
        DispatchQueue.main.async {
            TrapTubePlayerSession.shared.reportWatchState(host: host, videoID: videoID, title: title, playing: playing)
        }
    }
}

final class TrapTubeWebEQScriptHandler: NSObject, WKScriptMessageHandler {
    static let shared = TrapTubeWebEQScriptHandler()
    private override init() { super.init() }

    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard message.name == "trapTubeEQ",
              let body = message.body as? [String: Any] else { return }
        let host = TrapTubePlayerSession.shared.host(for: message.webView)
        if (body["action"] as? String) == "open" {
            TrapTubeWebEQCenter.shared.present(host: host)
        }
        if (body["type"] as? String) == "eqStatus" {
            TrapTubeWebEQCenter.shared.updateStatus(host: host, body: body)
        }
    }
}

struct TrapTubeWebEQRequest: Identifiable {
    let host: TrapTubeHostTab
    var id: String { host == .home ? "eq-home" : "eq-you" }
}

struct TrapTubeWebEQStatus {
    var state: String = "unknown"
    var level: Double = 0
    var message: String = ""
}

final class TrapTubeWebEQCenter: ObservableObject {
    static let shared = TrapTubeWebEQCenter()
    @Published var activeRequest: TrapTubeWebEQRequest?
    @Published private(set) var statuses: [TrapTubeHostTab: TrapTubeWebEQStatus] = [:]
    private init() {}

    func present(host: TrapTubeHostTab?) {
        DispatchQueue.main.async {
            self.activeRequest = TrapTubeWebEQRequest(host: host ?? .you)
        }
    }

    func updateStatus(host: TrapTubeHostTab?, body: [String: Any]) {
        guard let host else { return }
        var status = TrapTubeWebEQStatus()
        status.state = body["state"] as? String ?? "unknown"
        status.level = (body["level"] as? NSNumber)?.doubleValue ?? 0
        status.message = body["message"] as? String ?? ""
        DispatchQueue.main.async { self.statuses[host] = status }
    }
}

/// The stream EQ's settings (page-graph model mirrors the TypeType
/// watch sheet's WebAudio graph: 16 peaking bands, a 90 Hz lowshelf
/// for bass, and a master gain with boost headroom compensation).
final class TrapTubeWebEQ: ObservableObject {
    static let shared = TrapTubeWebEQ()
    static let frequencies = [32, 64, 125, 250, 500, 1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 10000, 12000, 16000]

    @Published var enabled: Bool { didSet { persist(); TrapTubePlayerSession.shared.applyWebEQToAll() } }
    @Published var gains: [Double] { didSet { persist(); TrapTubePlayerSession.shared.applyWebEQToAll() } }
    @Published var bass: Double { didSet { persist(); TrapTubePlayerSession.shared.applyWebEQToAll() } }
    @Published var master: Double { didSet { persist(); TrapTubePlayerSession.shared.applyWebEQToAll() } }
    @Published var presetName: String { didSet { persist() } }

    private init() {
        let defaults = UserDefaults.standard
        enabled = defaults.object(forKey: "TrapTube.WebEQ.Enabled") as? Bool ?? true
        let raw = defaults.array(forKey: "TrapTube.WebEQ.Gains") ?? []
        let parsed = raw.compactMap { ($0 as? NSNumber)?.doubleValue }
        gains = parsed.count == 16 ? parsed : [Double](repeating: 0, count: 16)
        bass = defaults.object(forKey: "TrapTube.WebEQ.Bass") as? Double ?? 0
        master = defaults.object(forKey: "TrapTube.WebEQ.Master") as? Double ?? 1
        presetName = defaults.string(forKey: "TrapTube.WebEQ.Preset") ?? "Flat"
    }

    private func persist() {
        let defaults = UserDefaults.standard
        defaults.set(enabled, forKey: "TrapTube.WebEQ.Enabled")
        defaults.set(gains, forKey: "TrapTube.WebEQ.Gains")
        defaults.set(bass, forKey: "TrapTube.WebEQ.Bass")
        defaults.set(master, forKey: "TrapTube.WebEQ.Master")
        defaults.set(presetName, forKey: "TrapTube.WebEQ.Preset")
    }

    var settingsJSON: String {
        let payload: [String: Any] = ["enabled": enabled, "gains": gains, "bass": bass, "master": master]
        guard let data = try? JSONSerialization.data(withJSONObject: payload),
              let text = String(data: data, encoding: .utf8) else { return "{}" }
        return text
    }

    func setBand(_ index: Int, _ value: Double) {
        guard gains.indices.contains(index) else { return }
        var next = gains
        next[index] = min(12, max(-12, value))
        gains = next
        if presetName != "Custom" { presetName = "Custom" }
    }

    func applyPreset(_ preset: TrapTubeWebEQPreset) {
        gains = preset.gains
        bass = preset.bass
        master = preset.master
        presetName = preset.name
    }
}

struct TrapTubeWebEQPreset: Identifiable {
    let name: String
    let gains: [Double]
    let bass: Double
    let master: Double
    var id: String { name }

    static let all: [TrapTubeWebEQPreset] = [
        TrapTubeWebEQPreset(name: "Trap", gains: [7, 6, 4, 1, -1, -1, 0, 1, 2, 2, 3, 3, 4, 4, 3, 2], bass: 8, master: 1.05),
        TrapTubeWebEQPreset(name: "Drill", gains: [8, 7, 5, 2, 0, -2, -1, 0, 1, 2, 3, 4, 5, 5, 4, 3], bass: 10, master: 1.05),
        TrapTubeWebEQPreset(name: "Hip-Hop", gains: [5, 5, 4, 2, 1, 0, 1, 2, 3, 3, 2, 2, 2, 1, 0, 0], bass: 6, master: 1.05),
        TrapTubeWebEQPreset(name: "Bass", gains: [10, 9, 7, 4, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], bass: 14, master: 0.95),
        TrapTubeWebEQPreset(name: "Clarity", gains: [-2, -2, -1, -3, -2, 0, 1, 2, 3, 4, 4, 3, 3, 4, 4, 5], bass: 2, master: 1.10),
        TrapTubeWebEQPreset(name: "Flat", gains: [Double](repeating: 0, count: 16), bass: 0, master: 1.0)
    ]
}

enum TrapTubeStreamingQuality {
    static var cap: Int { UserDefaults.standard.integer(forKey: "TrapTube.Streaming.MaxQuality") }
    static let presets: [(label: String, value: Int)] = [
        ("Auto", 0), ("2160p", 2160), ("1440p", 1440), ("1080p", 1080), ("720p", 720),
        ("480p", 480), ("360p", 360), ("240p", 240), ("144p", 144)
    ]

    static func label(for value: Int) -> String {
        presets.first { $0.value == value }?.label ?? "Auto"
    }

    static func withinCap(_ height: Int) -> Bool {
        cap == 0 || height <= cap
    }
}

/// Page-side WebAudio graph for youtube.com watch pages, injected into
/// both watch web views. Same parameter model as the TypeType watch
/// sheet's graph. The graph reports its REAL state back: the sheet's
/// "signal flowing" badge is driven by the analyser, and a stream
/// whose audio comes out of the graph silent while clearly playing
/// (the CORS-zeroed case) is auto-bypassed so playback is never muted
/// by the EQ, and reported honestly.
enum TrapTubeWebEQInstaller {
    static var scriptSource: String {
        #"""
        (() => {
          if (window.__trapTubeWebEQInstalled) return;
          window.__trapTubeWebEQInstalled = true;
          var HZ = [32, 64, 125, 250, 500, 1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 10000, 12000, 16000];
          var settings = \#(TrapTubeWebEQ.shared.settingsJSON);
          var ctx = null, source = null, filters = [], shelf = null, masterNode = null, analyser = null;
          var video = null, bypassed = false, silentChecks = 0, lastLevel = 0;
          function post(payload) {
            try {
              var h = window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.trapTubeEQ;
              if (h) h.postMessage(payload);
            } catch (e) {}
          }
          function applySettings() {
            if (!ctx || !filters.length) return;
            var t = ctx.currentTime;
            var i, g;
            for (i = 0; i < HZ.length; i++) {
              g = settings.enabled ? Number(settings.gains[i] || 0) : 0;
              filters[i].gain.setTargetAtTime(g, t, 0.03);
            }
            if (shelf) shelf.gain.setTargetAtTime(settings.enabled ? Number(settings.bass || 0) : 0, t, 0.03);
            if (masterNode) {
              var peak = 0;
              for (i = 0; i < HZ.length; i++) peak = Math.max(peak, Number(settings.gains[i] || 0));
              if (settings.enabled) peak += Number(settings.bass || 0); else peak = 0;
              var head = -Math.min(18, Math.max(0, peak) * 0.5);
              var m = settings.enabled ? Math.max(0, Math.min(2, Number(settings.master == null ? 1 : settings.master))) : 1;
              masterNode.gain.setTargetAtTime(m * Math.pow(10, head / 20), t, 0.03);
            }
          }
          window.__traptubeWebSetEQ = function (v) { if (v) settings = v; applySettings(); report(); };
          function measure() {
            if (!analyser) return 0;
            var data = new Uint8Array(analyser.fftSize);
            analyser.getByteTimeDomainData(data);
            var sum = 0, d;
            for (var i = 0; i < data.length; i++) { d = (data[i] - 128) / 128; sum += d * d; }
            return Math.sqrt(sum / data.length);
          }
          function currentState() {
            if (!video) return { state: "noelement", level: 0, message: "No video element on this page yet." };
            if (bypassed) return { state: "bypassed", level: 0, message: "This stream's audio is served in a way WebAudio cannot process (no CORS access), so it is playing unprocessed." };
            if (!ctx || !source) return { state: "noelement", level: 0, message: "The EQ graph has not been built yet." };
            if (ctx.state !== "running") return { state: "suspended", level: 0, message: "The audio path is paused - press play in the player to start the EQ." };
            if (lastLevel > 0.004) return { state: "flowing", level: lastLevel, message: "" };
            return { state: "attached", level: lastLevel, message: "The EQ is attached - waiting for audible signal (the video may be paused or in a quiet passage)." };
          }
          function report() {
            var s = currentState();
            post({ type: "eqStatus", state: s.state, level: s.level, message: s.message });
          }
          window.__traptubeWebEQReport = report;
          function bypass() {
            try {
              if (source && ctx) {
                try { source.disconnect(); } catch (e) {}
                source.connect(ctx.destination);
              }
            } catch (e) {}
            bypassed = true;
            report();
          }
          function attach() {
            var candidate = document.querySelector("#movie_player video") || document.querySelector("video.html5-main-video") || document.querySelector("video");
            if (!candidate) { video = null; return; }
            if (candidate === video) return;
            video = candidate;
            bypassed = false;
            silentChecks = 0;
            lastLevel = 0;
            try {
              var AC = window.AudioContext || window.webkitAudioContext;
              if (!AC) {
                post({ type: "eqStatus", state: "error", level: 0, message: "Web Audio is unavailable in this runtime." });
                return;
              }
              if (!ctx) ctx = new AC();
              if (video.__ttEQSource) {
                source = video.__ttEQSource;
                filters = video.__ttEQFilters || [];
                shelf = video.__ttEQShelf || null;
                masterNode = video.__ttEQMaster || null;
                analyser = video.__ttEQAnalyser || null;
              } else {
                source = ctx.createMediaElementSource(video);
                filters = HZ.map(function (f) {
                  var n = ctx.createBiquadFilter();
                  n.type = "peaking";
                  n.frequency.value = f;
                  n.Q.value = 1.15;
                  n.gain.value = 0;
                  return n;
                });
                shelf = ctx.createBiquadFilter();
                shelf.type = "lowshelf";
                shelf.frequency.value = 90;
                shelf.Q.value = 0.7;
                shelf.gain.value = 0;
                masterNode = ctx.createGain();
                masterNode.gain.value = 1;
                analyser = ctx.createAnalyser();
                analyser.fftSize = 512;
                var node = source;
                filters.forEach(function (n) { node.connect(n); node = n; });
                node.connect(shelf);
                shelf.connect(masterNode);
                masterNode.connect(analyser);
                analyser.connect(ctx.destination);
                video.__ttEQSource = source;
                video.__ttEQFilters = filters;
                video.__ttEQShelf = shelf;
                video.__ttEQMaster = masterNode;
                video.__ttEQAnalyser = analyser;
              }
              var resume = function () {
                if (ctx && ctx.state !== "running") {
                  ctx.resume().then(function () { report(); }).catch(function () { report(); });
                }
              };
              video.addEventListener("play", resume);
              video.addEventListener("playing", resume);
              if (ctx.state !== "running") ctx.resume().catch(function () {});
              applySettings();
              report();
            } catch (e) {
              post({ type: "eqStatus", state: "error", level: 0, message: "EQ attach failed: " + (e && e.message ? e.message : String(e)) });
            }
          }
          function monitor() {
            attach();
            if (ctx && source && !bypassed && video) {
              lastLevel = measure();
              var audible = !video.paused && !video.ended && !video.muted && video.volume > 0 && video.readyState > 2;
              if (ctx.state === "running" && audible && lastLevel < 0.0025) {
                silentChecks += 1;
                if (silentChecks >= 6) bypass();
              } else if (lastLevel >= 0.0025) {
                silentChecks = 0;
              }
            }
            report();
          }
          document.addEventListener("pointerdown", function () {
            if (ctx && ctx.state !== "running") ctx.resume().catch(function () {});
          }, true);
          document.addEventListener("yt-navigate-finish", function () { setTimeout(monitor, 120); });
          try {
            new MutationObserver(function () { attach(); }).observe(document.documentElement, { childList: true, subtree: true });
          } catch (e) {}
          setInterval(monitor, 1500);
          monitor();
        })()
        """#
    }
}

/// Page-world quality cap: reaches the page's own movie_player object
/// (only possible from the page content world) and pins every new
/// stream to the Settings preset via setPlaybackQualityRange.
enum TrapTubeQualityInstaller {
    static var scriptSource: String {
        #"""
        (() => {
          if (window.__trapTubeQualityInstalled) return;
          window.__trapTubeQualityInstalled = true;
          var cap = \#(TrapTubeStreamingQuality.cap);
          var LABELS = { 2160: "hd2160", 1440: "hd1440", 1080: "hd1080", 720: "hd720", 480: "large", 360: "medium", 240: "small", 144: "tiny" };
          function applyQuality() {
            try {
              if (!cap) return;
              var label = LABELS[cap];
              if (!label) return;
              var p = document.querySelector("#movie_player");
              if (!p) return;
              if (p.setPlaybackQualityRange) p.setPlaybackQualityRange("tiny", label);
              if (p.setPlaybackQuality) p.setPlaybackQuality(label);
            } catch (e) {}
          }
          window.__trapTubeSetQualityCap = function (c) { cap = Number(c) || 0; applyQuality(); };
          document.addEventListener("yt-navigate-finish", function () {
            setTimeout(applyQuality, 400);
            setTimeout(applyQuality, 1800);
          });
          document.addEventListener("yt-player-updated", function () { setTimeout(applyQuality, 400); });
          document.addEventListener("playing", function () { setTimeout(applyQuality, 600); }, true);
          setInterval(applyQuality, 6000);
          setTimeout(applyQuality, 800);
        })()
        """#
    }
}

/// Hosts the session's web view inside the mini player. Re-parenting
/// is plain UIKit addSubview: whichever container asks last (the host
/// tab's representable or this slot) holds the view.
final class TrapTubeWebContainerView: UIView {
    private weak var attachedView: WKWebView?

    func attach(host: TrapTubeHostTab) {
        guard let view = TrapTubePlayerSession.shared.webViewIfExists(for: host) else { return }
        if attachedView === view {
            view.frame = bounds
            return
        }
        detach()
        attachedView = view
        addSubview(view)
        view.frame = bounds
        view.autoresizingMask = [.flexibleWidth, .flexibleHeight]
    }

    func detach() {
        if let view = attachedView, view.superview === self {
            view.removeFromSuperview()
        }
        attachedView = nil
    }

    override func layoutSubviews() {
        super.layoutSubviews()
        attachedView?.frame = bounds
    }
}

struct TrapTubeWebSlotView: UIViewRepresentable {
    let host: TrapTubeHostTab

    func makeUIView(context: Context) -> TrapTubeWebContainerView {
        let container = TrapTubeWebContainerView()
        container.backgroundColor = .black
        container.attach(host: host)
        return container
    }

    func updateUIView(_ uiView: TrapTubeWebContainerView, context: Context) {
        uiView.attach(host: host)
    }

    static func dismantleUIView(_ uiView: TrapTubeWebContainerView, coordinator: ()) {
        uiView.detach()
    }
}

struct TrapTubeWebMiniPlayerBar: View {
    let host: TrapTubeHostTab
    let onReturn: () -> Void
    @ObservedObject private var session = TrapTubePlayerSession.shared
    @EnvironmentObject private var theme: ThemeManager

    var body: some View {
        HStack(spacing: 10) {
            TrapTubeWebSlotView(host: host)
                .frame(width: 104, height: 58)
                .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: 10, style: .continuous).stroke(.white.opacity(0.14), lineWidth: 1))
                .onTapGesture { onReturn() }
            VStack(alignment: .leading, spacing: 2) {
                Text(session.watchTitle.isEmpty ? "YouTube video" : session.watchTitle)
                    .font(.caption.bold()).foregroundStyle(.white).lineLimit(2)
                Text(host == .home ? "Playing from Home" : "Playing from You")
                    .font(.caption2).foregroundStyle(Color(hex: "A6A4A6"))
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .contentShape(Rectangle())
            .onTapGesture { onReturn() }
            Button {
                session.togglePlay()
            } label: {
                Image(systemName: session.watchIsPlaying ? "pause.fill" : "play.fill")
                    .font(.title3.bold()).foregroundStyle(.white)
                    .frame(width: 38, height: 40)
            }
            .buttonStyle(.plain)
            .accessibilityLabel(session.watchIsPlaying ? "Pause" : "Play")
            Button {
                session.closeMini()
            } label: {
                Image(systemName: "xmark")
                    .font(.subheadline.bold()).foregroundStyle(Color(hex: "A6A4A6"))
                    .frame(width: 34, height: 40)
            }
            .buttonStyle(.plain)
            .accessibilityLabel("Close mini player")
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 7)
        .background(theme.oledEnabled ? Color.black : Color(hex: "141315"))
        .overlay(alignment: .top) { Rectangle().fill(.white.opacity(0.09)).frame(height: 1) }
    }
}

struct TrapTubeWebEQSheet: View {
    let host: TrapTubeHostTab
    @Environment(\.dismiss) private var dismiss
    @EnvironmentObject private var theme: ThemeManager
    @ObservedObject private var eq = TrapTubeWebEQ.shared
    @ObservedObject private var center = TrapTubeWebEQCenter.shared

    private var status: TrapTubeWebEQStatus? { center.statuses[host] }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    statusBanner
                    Toggle(isOn: $eq.enabled) {
                        VStack(alignment: .leading, spacing: 3) {
                            Text("Stream EQ").font(.headline).foregroundStyle(.white)
                            Text("Processes the live YouTube stream in the page - the same band layout as the Stem Studio EQ graph. Changes apply live.").font(.caption).foregroundStyle(Color(hex: "A6A4A6"))
                        }
                    }
                    .tint(theme.accent)
                    presetRow
                    bandSliders
                    HStack(alignment: .top, spacing: 16) {
                        VStack(alignment: .leading, spacing: 6) {
                            Text("Bass").font(.caption.bold()).foregroundStyle(Color(hex: "D8D5D8"))
                            Slider(value: $eq.bass, in: 0...20, step: 1).tint(theme.accent)
                            Text("+\(Int(eq.bass)) dB").font(.caption2).foregroundStyle(Color(hex: "A6A4A6"))
                        }
                        VStack(alignment: .leading, spacing: 6) {
                            Text("Master").font(.caption.bold()).foregroundStyle(Color(hex: "D8D5D8"))
                            Slider(value: $eq.master, in: 0...2, step: 0.01).tint(theme.accent)
                            Text("\(Int(eq.master * 100))%").font(.caption2).foregroundStyle(Color(hex: "A6A4A6"))
                        }
                    }
                    Text("The badge above only turns green when the analyser actually measures your audio passing through the EQ. If a stream is served in a way WebAudio cannot tap, the sheet says so and playback continues unprocessed instead of going silent.")
                        .font(.caption2).foregroundStyle(Color(hex: "77747A"))
                }
                .padding(20)
            }
            .background(theme.background.ignoresSafeArea())
            .navigationTitle("Stream EQ")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }.foregroundStyle(theme.accent)
                }
            }
        }
        .presentationDetents([.large])
        .onAppear { TrapTubePlayerSession.shared.requestEQStatus(for: host) }
    }

    private var statusBanner: some View {
        let state = status?.state ?? "unknown"
        return HStack(alignment: .top, spacing: 10) {
            Image(systemName: bannerIcon(state))
                .font(.headline)
                .foregroundStyle(bannerColor(state))
            VStack(alignment: .leading, spacing: 3) {
                Text(bannerTitle(state)).font(.subheadline.bold()).foregroundStyle(.white)
                Text(bannerDetail(state)).font(.caption).foregroundStyle(Color(hex: "A6A4A6"))
                    .fixedSize(horizontal: false, vertical: true)
                if state == "flowing", let level = status?.level {
                    ProgressView(value: min(1, level * 6)).tint(.green)
                }
            }
            Spacer(minLength: 0)
        }
        .padding(13)
        .background(Color.white.opacity(0.06), in: RoundedRectangle(cornerRadius: 16, style: .continuous))
    }

    private func bannerIcon(_ state: String) -> String {
        switch state {
        case "flowing": return "checkmark.circle.fill"
        case "attached": return "waveform.circle.fill"
        case "suspended": return "pause.circle.fill"
        case "bypassed": return "exclamationmark.triangle.fill"
        case "error": return "xmark.octagon.fill"
        default: return "waveform.circle"
        }
    }

    private func bannerColor(_ state: String) -> Color {
        switch state {
        case "flowing": return .green
        case "attached": return theme.accent
        case "bypassed": return .orange
        case "error": return .red
        default: return Color(hex: "A6A4A6")
        }
    }

    private func bannerTitle(_ state: String) -> String {
        switch state {
        case "flowing": return "EQ attached - signal flowing"
        case "attached": return "EQ attached - waiting for audio"
        case "suspended": return "EQ path paused"
        case "noelement": return "No video on this page yet"
        case "bypassed": return "This stream can't be EQ'd in the browser"
        case "error": return "EQ attach failed"
        default: return "Checking the EQ path..."
        }
    }

    private func bannerDetail(_ state: String) -> String {
        if let message = status?.message, !message.isEmpty { return message }
        switch state {
        case "flowing": return "The analyser is measuring live audio through the EQ bands right now."
        case "attached": return "Press play in the player - the badge turns green once sound is flowing."
        case "suspended": return "Press play in the player to start the audio path."
        case "noelement": return "Open a video in this tab, then reopen this sheet."
        default: return "Open a video in this tab, then check again."
        }
    }

    private var presetRow: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(TrapTubeWebEQPreset.all) { preset in
                    Button {
                        eq.applyPreset(preset)
                    } label: {
                        Text(preset.name)
                            .font(.caption.bold())
                            .padding(.horizontal, 12).padding(.vertical, 7)
                            .background(eq.presetName == preset.name ? theme.accent : Color.white.opacity(0.08), in: Capsule())
                            .foregroundStyle(eq.presetName == preset.name ? .white : Color(hex: "D8D5D8"))
                    }
                    .buttonStyle(.plain)
                }
            }
        }
    }

    private var bandSliders: some View {
        VStack(spacing: 10) {
            ForEach(0..<16, id: \.self) { index in
                HStack(spacing: 10) {
                    Text(frequencyLabel(TrapTubeWebEQ.frequencies[index]))
                        .font(.caption2.bold()).foregroundStyle(Color(hex: "A6A4A6"))
                        .frame(width: 36, alignment: .leading)
                    Slider(value: Binding(
                        get: { eq.gains[index] },
                        set: { eq.setBand(index, $0) }
                    ), in: -12...12, step: 0.5)
                    .tint(theme.accent)
                    Text(String(format: "%+.0f", eq.gains[index]))
                        .font(.caption2.bold()).foregroundStyle(.white)
                        .frame(width: 30, alignment: .trailing)
                }
            }
        }
    }

    private func frequencyLabel(_ hz: Int) -> String {
        hz >= 1000 ? "\(hz / 1000)k" : "\(hz)"
    }
}
'''

p = file("YouTubeView.swift")
s = p.read_text()
if "struct TrapTubeWebEQSheet" not in s:
    s = s.rstrip("\n") + "\n" + ROUND3_SWIFT
    p.write_text(s)

# --- Item 5: OLED dark mode. ThemeManager gains the persisted switch;
# ThemeManager.background returns true black while it is on.
p = file("ThemeManager.swift")
s = p.read_text()
s = rep(s, "    @Published private(set) var backgroundHex = \"080809\"\n",
        "    @Published private(set) var backgroundHex = \"080809\"\n    @Published var oledEnabled = false { didSet { UserDefaults.standard.set(oledEnabled, forKey: \"TrapTube.Theme.OLED\") } }\n",
        "theme OLED flag")
s = rep(s, "    init() {\n        let defaults = UserDefaults.standard\n",
        "    init() {\n        let defaults = UserDefaults.standard\n        oledEnabled = defaults.bool(forKey: \"TrapTube.Theme.OLED\")\n",
        "theme OLED init")
s = rep(s, "    var background: Color { Color(hex: backgroundHex) }",
        "    var background: Color { oledEnabled ? .black : Color(hex: backgroundHex) }",
        "theme background OLED")
p.write_text(s)

# --- Item 5 + 4: Settings - the connection-check button becomes the
# OLED toggle; the static streaming-quality card becomes a real menu.
p = file("SettingsView.swift")
s = p.read_text()
s = rep(s, "    @State private var connectionStatus: String?\n    @State private var checkingConnection = false\n",
        "    // Round 3: the TypeType connection check is gone; the OLED dark mode toggle lives in its card.\n",
        "settings remove connection states")
s = rep(s, """                    Button {
                        checkingConnection = true; connectionStatus = nil
                        Task {
                            defer { checkingConnection = false }
                            do { connectionStatus = try await TypeTypeService().checkHealth() }
                            catch { connectionStatus = error.localizedDescription }
                        }
                    } label: {
                        Label(checkingConnection ? "Checking\u2026" : "Check TypeType connection", systemImage: "network")
                            .font(.subheadline.bold()).foregroundStyle(.white)
                            .frame(maxWidth: .infinity).padding(.vertical, 12)
                            .background(theme.accent, in: Capsule())
                    }
                    .disabled(checkingConnection)
                    if let connectionStatus {
                        Text(connectionStatus).font(.caption).foregroundStyle(connectionStatus.hasPrefix("Connected") ? Color.green : Color(hex: "FF7A84"))
                            .fixedSize(horizontal: false, vertical: true)
                    }""",
        """                    Toggle(isOn: $theme.oledEnabled) {
                        VStack(alignment: .leading, spacing: 3) {
                            Text("OLED Dark Mode").font(.subheadline.bold()).foregroundStyle(.white)
                            Text("Pure black backgrounds - saves battery on OLED screens.").font(.caption).foregroundStyle(Color(hex: "A6A4A6"))
                        }
                    }
                    .tint(theme.accent)""",
        "settings OLED toggle replaces connection check")
s = rep(s, "    @AppStorage(\"settings.shareDiagnostics\") private var shareDiagnostics = false\n",
        "    @AppStorage(\"settings.shareDiagnostics\") private var shareDiagnostics = false\n    @AppStorage(\"TrapTube.Streaming.MaxQuality\") private var streamingCap = 0\n",
        "settings streaming cap storage")
s = rep(s, """                settingsCard(title: "Streaming quality", icon: "slider.horizontal.3") {
                    Text("Quality choices are loaded from the active TypeType stream. Open a video and use the in-player Quality menu for available video renditions and the Audio menu for available audio tracks. TrapTube does not display fixed quality levels that the stream does not support.")
                        .font(.caption).foregroundStyle(Color(hex: "A6A4A6"))
                }""",
        """                settingsCard(title: "Streaming quality", icon: "slider.horizontal.3") {
                    HStack(spacing: 12) {
                        VStack(alignment: .leading, spacing: 3) {
                            Text("Maximum quality").font(.subheadline.bold()).foregroundStyle(.white)
                            Text("Caps every new stream in Home and You, and the download sheet's default pick.").font(.caption).foregroundStyle(Color(hex: "A6A4A6"))
                                .fixedSize(horizontal: false, vertical: true)
                        }
                        Spacer(minLength: 8)
                        Picker("Maximum quality", selection: $streamingCap) {
                            ForEach(TrapTubeStreamingQuality.presets.map { $0.value }, id: \\.self) { value in
                                Text(TrapTubeStreamingQuality.label(for: value)).tag(value)
                            }
                        }
                        .pickerStyle(.menu)
                        .tint(theme.accent)
                        .onChange(of: streamingCap) { _, _ in
                            TrapTubePlayerSession.shared.applyQualityCapToAll()
                        }
                    }
                }""",
        "settings streaming quality menu")
# The theme picker's and the Customize sheet's hardcoded near-black
# backgrounds follow the OLED switch via ThemeManager.background.
s = rep_all(s, ".background(Color(hex: \"080809\").ignoresSafeArea())",
            ".background(theme.background.ignoresSafeArea())", "settings surfaces OLED")
p.write_text(s)

# --- Item 2 + 5: RootView observes the session, hosts the mini player
# above the tab bar, and its bottom inset follows OLED.
p = file("RootView.swift")
s = p.read_text()
s = rep(s, "    @State private var showSplash = true\n",
        "    @State private var showSplash = true\n    @ObservedObject private var webSession = TrapTubePlayerSession.shared\n",
        "root session wiring")
s = rep(s, """                MiniPlayer { showPlayer = true }
                    .environmentObject(player).environmentObject(theme)""",
        """                if let host = webSession.watchHost,
                   (host == .home && selectedTab != .home) || (host == .you && selectedTab != .you) {
                    TrapTubeWebMiniPlayerBar(host: host) { selectedTab = host == .home ? .home : .you }
                        .environmentObject(theme)
                }
                MiniPlayer { showPlayer = true }
                    .environmentObject(player).environmentObject(theme)""",
        "root mini player bar")
s = rep(s, """            .padding(.bottom, 0)
            .background(.ultraThinMaterial)
        }""",
        """            .padding(.bottom, 0)
            .background {
                if theme.oledEnabled {
                    Color.black
                } else {
                    Rectangle().fill(.ultraThinMaterial)
                }
            }
        }""", "root inset OLED")
p.write_text(s)

# --- Item 5: the tab bar itself follows OLED.
p = file("Components.swift")
s = p.read_text()
s = rep(s, """        .padding(.vertical, 6)
        .background(.ultraThinMaterial)""",
        """        .padding(.vertical, 6)
        .background {
            if theme.oledEnabled {
                Color.black
            } else {
                Rectangle().fill(.ultraThinMaterial)
            }
        }""", "tab bar OLED")
p.write_text(s)

# =====================================================================
# Round 4 - ad blocking, ported from how the YTPlus/YTLite build
# actually does it (evidence: ~/workspace/traptube-hybrid/
# ad-blocking-research.md). YTLite's "Remove ads" (localization key
# RemoveAds, NSUserDefaults key noAds, Feed page row 1) is implemented
# by FeedManager as host RENDERER FILTERING over the protobuf section
# trees: ad renderers (tested via isAdRenderer: / hasAdLoggingData)
# are dropped before cells are built, and the player response's ad
# arrays (playerAdsArray / adSlotsArray) never reach playback. There
# is NO network layer in the dylib - zero NSURLProtocol /
# WKContentRuleList / canInitWithRequest references and zero ad-host
# or tracking-endpoint strings - so this round deliberately ships NO
# WKContentRuleList either. The web-view equivalent of the same layer:
# an in-page script hides ad renderers in the feed/watch DOM, clicks
# the skip button the moment an in-stream ad offers one, and mutes +
# fast-forwards unskippable ads (the ad still loads and plays -
# nothing is ever blocked). If YouTube's enforcement interstitial
# ever appears, the script detects it and stops all in-stream actions
# for the rest of that page load. A Block Ads toggle (default ON) in
# Settings rebuilds both web views live, and the page reports counts
# (hidden / skipped / fast-forwarded) to a session counter.
# =====================================================================

p = file("YouTubeView.swift")
s = p.read_text()

# --- The installer additionally registers the ad-block handler and,
# while the toggle is on, the document-start ad script. Both watch
# web views are configured exclusively through this installer.
s = rep(s, """        controller.add(TrapTubeWatchStateHandler.shared, name: "trapTubeState")
""",
        """        controller.add(TrapTubeWatchStateHandler.shared, name: "trapTubeState")
        controller.add(TrapTubeAdBlockHandler.shared, name: "trapTubeAds")
        if TrapTubeAdBlockCenter.isEnabled {
            controller.addUserScript(WKUserScript(source: TrapTubeAdBlockInstaller.scriptSource, injectionTime: .atDocumentStart, forMainFrameOnly: true))
        }
""", "installer ad block registration")

# --- The session stores its web-view builders so the Block Ads
# toggle can rebuild both views: a WKWebView's configuration is
# fixed at creation, so a fresh configuration means a fresh view.
s = rep(s, "    private var webViews: [TrapTubeHostTab: WKWebView] = [:]\n",
        "    private var webViews: [TrapTubeHostTab: WKWebView] = [:]\n    private var builders: [TrapTubeHostTab: () -> WKWebView] = [:]\n",
        "session builder store")
s = rep(s, """    func webView(for host: TrapTubeHostTab, builder: () -> WKWebView) -> WKWebView {
        if let existing = webViews[host] { return existing }
""",
        """    func webView(for host: TrapTubeHostTab, builder: () -> WKWebView) -> WKWebView {
        builders[host] = builder
        if let existing = webViews[host] { return existing }
""", "session builder capture")
s = rep(s, "    func applyQualityCapToAll() {",
        """    /// Round 4: the Block Ads toggle changes which user scripts a
    /// configuration carries; configurations are immutable after
    /// WKWebView creation, so toggling rebuilds both watch web views
    /// from their stored builders and reloads the page each was on.
    func rebuildWatchWebViews() {
        if !Thread.isMainThread {
            DispatchQueue.main.async { self.rebuildWatchWebViews() }
            return
        }
        for (host, builder) in builders {
            let currentURL = webViews[host]?.url
            let fresh = builder()
            webViews[host] = fresh
            if let currentURL {
                fresh.load(URLRequest(url: currentURL))
            }
        }
        objectWillChange.send()
    }

    func applyQualityCapToAll() {""", "session rebuild for ad toggle")
p.write_text(s)

# --- Round 4 types, appended to YouTubeView.swift.
ROUND4_SWIFT = r'''
// MARK: - Round 4: ad blocking (content-level port of YTLite's noAds)

/// Settings + session state for ad blocking. Mirrors YTLite's
/// "Remove ads" (defaults key noAds): the native build drops ad
/// renderers from the content it already fetched - it never blocks a
/// request - so the hybrid does the equivalent inside the page and
/// counts what it neutralizes.
final class TrapTubeAdBlockCenter: ObservableObject {
    static let shared = TrapTubeAdBlockCenter()
    static let enabledKey = "TrapTube.Ads.BlockEnabled"

    static var isEnabled: Bool {
        (UserDefaults.standard.object(forKey: enabledKey) as? Bool) ?? true
    }

    @Published var enabled: Bool {
        didSet {
            UserDefaults.standard.set(enabled, forKey: Self.enabledKey)
            TrapTubePlayerSession.shared.rebuildWatchWebViews()
        }
    }
    @Published private(set) var hiddenCount = 0
    @Published private(set) var skippedCount = 0
    @Published private(set) var fastForwardedCount = 0

    var neutralizedCount: Int { hiddenCount + skippedCount + fastForwardedCount }

    private init() {
        enabled = Self.isEnabled
    }

    func record(hidden: Int, skipped: Int, fastForwarded: Int) {
        DispatchQueue.main.async {
            self.hiddenCount += max(0, hidden)
            self.skippedCount += max(0, skipped)
            self.fastForwardedCount += max(0, fastForwarded)
        }
    }
}

final class TrapTubeAdBlockHandler: NSObject, WKScriptMessageHandler {
    static let shared = TrapTubeAdBlockHandler()
    private override init() { super.init() }

    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard message.name == "trapTubeAds",
              let body = message.body as? [String: Any] else { return }
        let hidden = (body["hidden"] as? NSNumber)?.intValue ?? 0
        let skipped = (body["skipped"] as? NSNumber)?.intValue ?? 0
        let fastForwarded = (body["fastforward"] as? NSNumber)?.intValue ?? 0
        TrapTubeAdBlockCenter.shared.record(hidden: hidden, skipped: skipped, fastForwarded: fastForwarded)
    }
}

/// The in-page half of the port. Where YTLite drops ad renderers from
/// the protobuf section tree before cells exist, this script hides the
/// DOM nodes that are the web renderers for ads; where the native
/// player simply never wires the response's ad arrays into playback,
/// this script lets the web player's ad load and "play" but clicks
/// Skip the moment it exists and mutes + fast-forwards the rest.
/// Nothing is intercepted or blocked at the network layer. If the
/// enforcement interstitial ever appears, all in-stream actions stop
/// for the remainder of the page load.
enum TrapTubeAdBlockInstaller {
    static var scriptSource: String {
        #"""
        (() => {
          if (window.__trapTubeAdsInstalled) return;
          window.__trapTubeAdsInstalled = true;
          var pending = { hidden: 0, skipped: 0, fastforward: 0 };
          var backedOff = false;
          var adActive = false;
          var ffCounted = false;
          var savedRate = 1;
          var savedMuted = false;
          var lastHideSweep = 0;
          function post() {
            if (!pending.hidden && !pending.skipped && !pending.fastforward) return;
            try {
              var h = window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.trapTubeAds;
              if (!h) return;
              h.postMessage({ hidden: pending.hidden, skipped: pending.skipped, fastforward: pending.fastforward });
              pending = { hidden: 0, skipped: 0, fastforward: 0 };
            } catch (e) {}
          }
          function bump(kind) { pending[kind] += 1; }
          function enforcementShowing() {
            try {
              if (document.querySelector("ytd-enforcement-message-view-model")) return true;
              var dialogs = document.querySelectorAll("tp-yt-paper-dialog");
              for (var i = 0; i < dialogs.length; i++) {
                var t = dialogs[i].textContent || "";
                if (t.indexOf("Ad blockers violate") !== -1) return true;
              }
            } catch (e) {}
            return false;
          }
          var AD_TAG_SELECTOR = [
            "ytd-ad-slot-renderer", "ytm-ad-slot-renderer",
            "ytd-display-ad-renderer", "ytm-display-ad-renderer",
            "ytd-promoted-sparkles-web-renderer", "ytm-promoted-sparkles-web-renderer",
            "ytd-promoted-sparkles-text-search-ad-renderer",
            "ytd-promoted-video-renderer", "ytm-promoted-video-renderer",
            "ytd-search-pyv-renderer",
            "ytd-in-feed-ad-layout-renderer", "ytm-in-feed-ad-layout-renderer",
            "ytd-banner-promo-renderer", "ytd-statement-banner-renderer",
            "ytd-mealbar-promo-renderer", "yt-mealbar-promo-renderer",
            "ytd-compact-promoted-video-renderer"
          ].join(",");
          var ITEM_SELECTOR = "ytd-rich-item-renderer,ytm-rich-item-renderer,ytd-rich-section-renderer,ytd-video-renderer,ytm-compact-video-renderer";
          function markHidden(el, countIt) {
            if (!el || el.__ttAdHidden) return;
            el.__ttAdHidden = true;
            try { el.style.setProperty("display", "none", "important"); } catch (e) {}
            if (countIt) bump("hidden");
          }
          function sweepHidden() {
            try {
              var items = document.querySelectorAll(ITEM_SELECTOR);
              for (var i = 0; i < items.length; i++) {
                var item = items[i];
                if (item.__ttAdHidden) continue;
                var child = item.querySelector(AD_TAG_SELECTOR);
                if (child && !child.__ttAdHidden) markHidden(item, true);
              }
              var ads = document.querySelectorAll(AD_TAG_SELECTOR + ",#masthead-ad");
              for (var j = 0; j < ads.length; j++) {
                var ad = ads[j];
                if (ad.__ttAdHidden) continue;
                var p = ad.parentElement;
                var insideHidden = false;
                while (p) { if (p.__ttAdHidden) { insideHidden = true; break; } p = p.parentElement; }
                if (!insideHidden) markHidden(ad, true);
              }
            } catch (e) {}
          }
          function playerEl() {
            return document.querySelector("#movie_player") || document.querySelector(".html5-video-player");
          }
          function mainVideo() {
            var p = playerEl();
            return (p && p.querySelector("video")) || document.querySelector("video");
          }
          function adShowing() {
            try {
              var p = playerEl();
              return !!(p && (p.classList.contains("ad-showing") || p.classList.contains("ad-interrupting")));
            } catch (e) {}
            return false;
          }
          function restoreFromAd() {
            if (!adActive) return;
            adActive = false;
            ffCounted = false;
            var v = mainVideo();
            if (v) {
              try { v.playbackRate = savedRate; } catch (e) {}
              try { v.muted = savedMuted; } catch (e) {}
            }
          }
          function sweepPlayer() {
            if (backedOff) return;
            if (enforcementShowing()) {
              backedOff = true;
              restoreFromAd();
              return;
            }
            try {
              if (!adShowing()) { restoreFromAd(); return; }
              var skip = document.querySelector(".ytp-skip-ad-button,.ytp-ad-skip-button-modern,.ytp-skip-ad-button-modern,.videoAdUiSkipButton");
              if (skip) {
                try { skip.click(); bump("skipped"); post(); } catch (e) {}
                return;
              }
              var v = mainVideo();
              if (!v) return;
              if (!adActive) {
                adActive = true;
                ffCounted = false;
                savedRate = v.playbackRate || 1;
                savedMuted = !!v.muted;
              }
              try { v.muted = true; } catch (e) {}
              try { if (v.playbackRate !== 16) v.playbackRate = 16; } catch (e) {}
              if (!ffCounted && v.readyState > 0 && !v.paused) { ffCounted = true; bump("fastforward"); }
              var overlays = document.querySelectorAll(".ytp-ad-player-overlay,.ytp-ad-overlay-container");
              for (var i = 0; i < overlays.length; i++) markHidden(overlays[i], false);
            } catch (e) {}
          }
          function start() {
            sweepHidden();
            try {
              new MutationObserver(function () {
                var now = Date.now();
                if (now - lastHideSweep > 700) { lastHideSweep = now; sweepHidden(); }
              }).observe(document.documentElement, { childList: true, subtree: true });
            } catch (e) {}
            setInterval(sweepPlayer, 400);
            setInterval(function () { sweepHidden(); post(); }, 2000);
            document.addEventListener("yt-navigate-finish", function () {
              restoreFromAd();
              setTimeout(sweepHidden, 120);
            });
          }
          if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", start);
          } else {
            start();
          }
        })()
        """#
    }
}
'''

p = file("YouTubeView.swift")
s = p.read_text()
if "enum TrapTubeAdBlockInstaller" not in s:
    s = s.rstrip("\n") + "\n" + ROUND4_SWIFT
    p.write_text(s)

# --- Settings: Block Ads toggle + session counter directly under
# the OLED toggle in the Video discovery card.
p = file("SettingsView.swift")
s = p.read_text()
s = rep(s, """    @AppStorage("TrapTube.Streaming.MaxQuality") private var streamingCap = 0
""",
        """    @AppStorage("TrapTube.Streaming.MaxQuality") private var streamingCap = 0
    @ObservedObject private var adBlockCenter = TrapTubeAdBlockCenter.shared
""", "settings ad center wiring")
s = rep(s, r"""                    Toggle(isOn: $theme.oledEnabled) {
                        VStack(alignment: .leading, spacing: 3) {
                            Text("OLED Dark Mode").font(.subheadline.bold()).foregroundStyle(.white)
                            Text("Pure black backgrounds - saves battery on OLED screens.").font(.caption).foregroundStyle(Color(hex: "A6A4A6"))
                        }
                    }
                    .tint(theme.accent)""",
        r"""                    Toggle(isOn: $theme.oledEnabled) {
                        VStack(alignment: .leading, spacing: 3) {
                            Text("OLED Dark Mode").font(.subheadline.bold()).foregroundStyle(.white)
                            Text("Pure black backgrounds - saves battery on OLED screens.").font(.caption).foregroundStyle(Color(hex: "A6A4A6"))
                        }
                    }
                    .tint(theme.accent)
                    Toggle(isOn: $adBlockCenter.enabled) {
                        VStack(alignment: .leading, spacing: 3) {
                            Text("Block Ads").font(.subheadline.bold()).foregroundStyle(.white)
                            Text("Hides sponsored items and skips or fast-forwards video ads in Home and You. Works on the page content itself - no requests are blocked, the same approach as the YouTube build.").font(.caption).foregroundStyle(Color(hex: "A6A4A6"))
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }
                    .tint(theme.accent)
                    if adBlockCenter.enabled {
                        Text("Ads neutralized this session: \(adBlockCenter.neutralizedCount)")
                            .font(.caption).foregroundStyle(Color(hex: "A6A4A6"))
                    }""",
        "settings block ads toggle")
p.write_text(s)

print("Build II hybrid navigation applied.")

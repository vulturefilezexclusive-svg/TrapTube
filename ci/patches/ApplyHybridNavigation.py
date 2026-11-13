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

# =====================================================================
# Round 5 - on-device fixes from the Round 3 build test (2026-11-13).
#
# Item 0 (Round 4 compile fix): build #396 failed with ONE error -
# generated YouTubeView.swift "assigning non-escaping parameter
# 'builder' to an '@escaping' closure" - because Round 4 taught
# TrapTubePlayerSession.webView(for:builder:) to STORE the builder in
# its builders dictionary (for rebuildWatchWebViews) without marking
# the parameter @escaping. Fixed below.
#
# Item 2 diagnosis (Home header all dead): the header actions were
# written against a @State copy of the web view captured in
# makeUIView (created(_:) / pendingURL queue from Round 1). Round 3
# moved ownership into TrapTubePlayerSession, but the header kept the
# old pattern: RootView's tab switch recreates YouTubeView (wiping the
# @State copy back to nil mid-session), and rebuildWatchWebViews()
# swaps the session's view for a fresh one the @State copy never
# learns about. So Sign in / refresh / search / chips navigated a
# detached view - or queued into pendingURL, which was only consumed
# at creation time and silently dropped. Fix: header actions route
# through the session, and both hosts become container views that
# re-attach whatever web view the session currently owns (the pattern
# the mini player already uses).
#
# Item 6 diagnosis (stuck "Loading your YouTube feed..." pill): the
# pill's isLoading only changed in WKNavigationDelegate callbacks.
# When YouTubeView is recreated over a live session web view, no new
# navigation starts, so no callback ever fires and the pill (initial
# value true) stays forever. Fix: the coordinators observe the web
# view's real isLoading via KVO (with .initial, so recreation syncs
# immediately), and each host view force-clears the pill after a 20 s
# timeout task if a load somehow never reports back.
#
# Item 3: the page WebAudio EQ honestly reports it cannot process
# most YouTube streams (no CORS access). The native route ships here:
# TrapTubeNativeStreamPlayer resolves the same video with the
# existing InnerTube resolver and plays it in AVPlayer with
# TrapTubeTapEQ attached and EqualizerView controls - reachable from
# the mod sheet's "Play in..." and from the Stream EQ sheet when the
# page graph reports bypassed/error.
#
# Item 4: the resolver now aggregates formats from EVERY client
# profile (adaptive AVC/VP9/AV1 video-only + AAC/Opus audio-only +
# muxed), the download sheet lists them all, adaptive picks download
# with the best paired audio and merge via FFmpegKit (AVC remux,
# VP9/AV1 transcode to H.264), and audio-only picks always convert
# to MP3.
#
# Item 5: downloaded-file playback hardening - see the
# AudioEngineManager.swift section below for the vector list.
# =====================================================================

# --- Item 0 + Items 2/6: YouTubeView.swift session and hosts --------
p = file("YouTubeView.swift")
s = p.read_text()

s = rep(s,
        "    func webView(for host: TrapTubeHostTab, builder: () -> WKWebView) -> WKWebView {",
        "    func webView(for host: TrapTubeHostTab, builder: @escaping () -> WKWebView) -> WKWebView {",
        "round5 session builder escaping fix")

s = rep(s, """    func applyQualityCapToAll() {""", """    /// Round 5: header actions (sign-in, refresh, search, category
    /// chips) route through the session so they always drive the web
    /// view that is actually on screen.
    func load(_ url: URL, for host: TrapTubeHostTab) {
        webViews[host]?.load(URLRequest(url: url, cachePolicy: .useProtocolCachePolicy, timeoutInterval: 30))
    }

    func reload(for host: TrapTubeHostTab) {
        webViews[host]?.reload()
    }

    func applyQualityCapToAll() {""",
        "round5 session load and reload")

# Home header: drop the stale @State web view / pending URL pattern.
s = rep(s, """struct YouTubeView: View {
    @EnvironmentObject private var theme: ThemeManager
    @State private var webView: WKWebView?
    @State private var pendingURL: URL?
    @State private var searchText = \"\"""", """struct YouTubeView: View {
    @EnvironmentObject private var theme: ThemeManager
    @State private var searchText = \"\"""",
        "round5 home stale webview state")

s = rep(s, """                    YouTubeHomeWebView(
                        url: homeURL,
                        onCreated: { created($0) },
                        onLoading: { isLoading = $0 }
                    )""", """                    YouTubeHomeWebView(
                        url: homeURL,
                        onLoading: { isLoading = $0 }
                    )""",
        "round5 home representable call")

s = rep(s, """        .sheet(item: $homeEQCenter.activeRequest) { request in
            TrapTubeWebEQSheet(host: request.host)
                .environmentObject(theme)
        }
    }""", """        .sheet(item: $homeEQCenter.activeRequest) { request in
            TrapTubeWebEQSheet(host: request.host)
                .environmentObject(theme)
        }
        // Round 5 (item 6): the loading pill is driven by the web
        // view's real isLoading (KVO in the coordinator); this task
        // force-clears it if a load ever outlives the timeout
        // without a finish/fail callback, so it can never linger.
        .task(id: isLoading) {
            guard isLoading else { return }
            try? await Task.sleep(nanoseconds: 20_000_000_000)
            if !Task.isCancelled { isLoading = false }
        }
    }""",
        "round5 home pill timeout")

s = rep(s, """            Button { webView?.reload() } label: {""", """            Button {
                // Round 5: reload the session-owned web view (the one
                // on screen); the pill lights and KVO/timeout clears it.
                isLoading = true
                TrapTubePlayerSession.shared.reload(for: .home)
            } label: {""",
        "round5 home reload button")

s = rep(s, """    private func load(_ url: URL) {
        guard url.host == "www.youtube.com" || url.host == "m.youtube.com" else { return }
        // If the web view has not been created yet (early tap on Sign in or a
        // category), queue the navigation instead of silently dropping it.
        if let webView {
            webView.load(URLRequest(url: url, cachePolicy: .useProtocolCachePolicy, timeoutInterval: 30))
        } else {
            pendingURL = url
        }
    }

    private func created(_ view: WKWebView) {
        webView = view
        if let pendingURL {
            self.pendingURL = nil
            view.load(URLRequest(url: pendingURL, cachePolicy: .useProtocolCachePolicy, timeoutInterval: 30))
        }
    }""", """    private func load(_ url: URL) {
        guard url.host == "www.youtube.com" || url.host == "m.youtube.com" else { return }
        // Round 5: route through TrapTubePlayerSession, which owns
        // the displayed web view for the app's lifetime. The old
        // version loaded a @State copy of the view (or queued into
        // pendingURL when the copy was nil); the copy was reset every
        // time RootView's tab switch recreated this view and went
        // stale when the session rebuilt its web views, so Sign in,
        // search and the category chips navigated a detached view -
        // or nothing at all.
        isLoading = true
        TrapTubePlayerSession.shared.load(url, for: .home)
    }""",
        "round5 home load routes via session")

p.write_text(s)

# --- Item 2/6 continued: both hosts become session-synced container
# views (TrapTubeWebContainerView - the same attach pattern the mini
# player uses), so a session rebuild is reflected on screen, the
# coordinator is rebound as delegate on the CURRENT web view, and the
# loading pill follows the view's real isLoading via KVO.
p = file("YouTubeView.swift")
s = p.read_text()

ROUND5_HOME_HOST = r'''private struct YouTubeHomeWebView: UIViewRepresentable {
    let url: URL
    let onLoading: (Bool) -> Void

    func makeCoordinator() -> Coordinator { Coordinator(onLoading: onLoading) }

    /// Builds the session's Home web view. Kept apart from the view
    /// lifecycle: TrapTubePlayerSession stores this builder and
    /// re-runs it when the Block Ads toggle rebuilds the watch views.
    static func buildWebView() -> WKWebView {
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

    /// Returns the session's current Home web view, creating it on
    /// first use, and (re)binds the coordinator as its navigation
    /// delegate and loading observer - including after a session
    /// rebuild swapped in a fresh instance.
    private func syncSessionView(coordinator: Coordinator) -> WKWebView {
        let view = TrapTubePlayerSession.shared.webView(for: .home) { Self.buildWebView() }
        if coordinator.webView !== view {
            view.navigationDelegate = coordinator
            coordinator.attach(to: view)
            if TrapTubePlayerSession.shared.claimInitialLoad(for: .home) {
                view.load(URLRequest(url: url, cachePolicy: .useProtocolCachePolicy, timeoutInterval: 30))
            } else if view.url == nil, !view.isLoading {
                view.load(URLRequest(url: url, cachePolicy: .useProtocolCachePolicy, timeoutInterval: 30))
            }
        }
        return view
    }

    func makeUIView(context: Context) -> TrapTubeWebContainerView {
        _ = syncSessionView(coordinator: context.coordinator)
        let container = TrapTubeWebContainerView()
        container.backgroundColor = .black
        container.attach(host: .home)
        return container
    }

    func updateUIView(_ uiView: TrapTubeWebContainerView, context: Context) {
        context.coordinator.onLoading = onLoading
        _ = syncSessionView(coordinator: context.coordinator)
        uiView.attach(host: .home)
    }

    static func dismantleUIView(_ uiView: TrapTubeWebContainerView, coordinator: Coordinator) {
        // The session owns the web view; detaching here lets RootView's
        // mini player slot take it over while another tab is showing.
        uiView.detach()
    }

    final class Coordinator: NSObject, WKNavigationDelegate {
        var onLoading: (Bool) -> Void
        weak var webView: WKWebView?
        private var loadingObservation: NSKeyValueObservation?

        init(onLoading: @escaping (Bool) -> Void) { self.onLoading = onLoading }

        /// Round 5 (item 6): the loading pill follows the web view's
        /// real isLoading via KVO. The .initial option reports the
        /// current state immediately, so a view recreated over an
        /// already-loaded page starts with the pill OFF (previously
        /// the pill only cleared when a brand-new navigation
        /// finished, which is why it could stick over a loaded feed).
        func attach(to view: WKWebView) {
            webView = view
            loadingObservation?.invalidate()
            loadingObservation = view.observe(\.isLoading, options: [.initial, .new]) { [weak self] observed, _ in
                let loading = observed.isLoading
                DispatchQueue.main.async { self?.onLoading(loading) }
            }
        }

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
            if TrapTubePlayerSession.shared.handleNavigationAction(navigationAction, webView: webView) {
                decisionHandler(.cancel)
                return
            }
            decisionHandler(.allow)
        }
    }
}

'''
s = splice_between(s,
                   "private struct YouTubeHomeWebView: UIViewRepresentable {",
                   "private struct TypeTypeVideoRow: View {",
                   ROUND5_HOME_HOST, "round5 home host")

ROUND5_ACCOUNT_HOST = r'''private struct YouTubeAccountWebView: UIViewRepresentable {
    let url: URL
    let onLoading: (Bool) -> Void

    func makeCoordinator() -> Coordinator { Coordinator(onLoading: onLoading) }

    /// Builds the session's You-tab web view (stored by the session
    /// and re-run when the watch web views are rebuilt).
    static func buildWebView() -> WKWebView {
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .default()
        configuration.allowsInlineMediaPlayback = true
        TrapTubeModInstaller.install(into: configuration)
        let created = WKWebView(frame: .zero, configuration: configuration)
        // Present as mobile Safari: Google refuses to run its sign-in flow
        // for the default WKWebView user agent ("browser may not be secure").
        created.customUserAgent = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1"
        created.isOpaque = false
        created.backgroundColor = .black
        created.scrollView.backgroundColor = .black
        created.underPageBackgroundColor = .black
        created.scrollView.contentInsetAdjustmentBehavior = .automatic
        created.allowsBackForwardNavigationGestures = true
        return created
    }

    /// Returns the session's current You-tab web view, creating it on
    /// first use, and (re)binds the coordinator as delegate/observer -
    /// including after a session rebuild.
    private func syncSessionView(coordinator: Coordinator) -> WKWebView {
        let view = TrapTubePlayerSession.shared.webView(for: .you) { Self.buildWebView() }
        if coordinator.webView !== view {
            view.navigationDelegate = coordinator
            coordinator.attach(to: view)
            if TrapTubePlayerSession.shared.claimInitialLoad(for: .you) {
                view.load(URLRequest(url: url, cachePolicy: .useProtocolCachePolicy, timeoutInterval: 30))
            } else if view.url == nil, !view.isLoading {
                view.load(URLRequest(url: url, cachePolicy: .useProtocolCachePolicy, timeoutInterval: 30))
            }
        }
        return view
    }

    func makeUIView(context: Context) -> TrapTubeWebContainerView {
        _ = syncSessionView(coordinator: context.coordinator)
        let container = TrapTubeWebContainerView()
        container.backgroundColor = .black
        container.attach(host: .you)
        return container
    }

    func updateUIView(_ uiView: TrapTubeWebContainerView, context: Context) {
        context.coordinator.onLoading = onLoading
        _ = syncSessionView(coordinator: context.coordinator)
        uiView.attach(host: .you)
    }

    static func dismantleUIView(_ uiView: TrapTubeWebContainerView, coordinator: Coordinator) {
        // The session owns the web view; detaching here lets RootView's
        // mini player slot take it over while another tab is showing.
        uiView.detach()
    }

    final class Coordinator: NSObject, WKNavigationDelegate {
        var onLoading: (Bool) -> Void
        weak var webView: WKWebView?
        private var loadingObservation: NSKeyValueObservation?

        init(onLoading: @escaping (Bool) -> Void) { self.onLoading = onLoading }

        /// Round 5 (item 6): same KVO loading binding as the Home host.
        func attach(to view: WKWebView) {
            webView = view
            loadingObservation?.invalidate()
            loadingObservation = view.observe(\.isLoading, options: [.initial, .new]) { [weak self] observed, _ in
                let loading = observed.isLoading
                DispatchQueue.main.async { self?.onLoading(loading) }
            }
        }

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
            if TrapTubePlayerSession.shared.handleNavigationAction(navigationAction, webView: webView) {
                decisionHandler(.cancel)
                return
            }
            decisionHandler(.allow)
        }
    }
}

'''
s = splice_between(s,
                   "private struct YouTubeAccountWebView: UIViewRepresentable {",
                   "/// TrapTube tab: the home for in-app downloads.",
                   ROUND5_ACCOUNT_HOST, "round5 account host")

# The You tab pill gets the same hard-timeout guard as Home.
s = rep(s, """        .sheet(item: $eqCenter.activeRequest) { request in
            TrapTubeWebEQSheet(host: request.host)
                .environmentObject(theme)
        }
        .preferredColorScheme(.dark)
    }
}""", """        .sheet(item: $eqCenter.activeRequest) { request in
            TrapTubeWebEQSheet(host: request.host)
                .environmentObject(theme)
        }
        // Round 5 (item 6): hard timeout so this loading state can
        // never linger either (it is KVO-driven like Home's).
        .task(id: isLoading) {
            guard isLoading else { return }
            try? await Task.sleep(nanoseconds: 20_000_000_000)
            if !Task.isCancelled { isLoading = false }
        }
        .preferredColorScheme(.dark)
    }
}""",
        "round5 account pill timeout")

p.write_text(s)

# --- Item 1: Settings cleanup - delete the watch.typetype.video
# server/connection block entirely; the card keeps the OLED toggle
# (Round 3) and the Block Ads toggle + counter (Round 4) under a
# plain "Playback" title.
p = file("SettingsView.swift")
s = p.read_text()
s = rep(s, """                settingsCard(title: "Video discovery", icon: "play.rectangle.fill") {
                    HStack(spacing: 10) {
                        Image(systemName: "server.rack").foregroundStyle(theme.accent)
                        VStack(alignment: .leading, spacing: 3) {
                            Text("watch.typetype.video").font(.subheadline.bold()).foregroundStyle(.white)
                            Text("Native feed and search use the TypeType server.").font(.caption).foregroundStyle(Color(hex: "A6A4A6"))
                        }
                    }""", """                settingsCard(title: "Playback", icon: "play.rectangle.fill") {""",
        "round5 settings server block removed")
s = rep(s, "// Round 3: the TypeType connection check is gone; the OLED dark mode toggle lives in its card.",
        "// Round 5: the TypeType connection/server block is gone entirely; this card keeps the OLED and Block Ads toggles.",
        "round5 settings comment refresh")
p.write_text(s)

# --- Item 4 (resolver side): enumerate EVERY format across all
# InnerTube client profiles - adaptive video-only (AVC/VP9/AV1 at
# every height), audio-only (AAC + Opus), plus the muxed ones - each
# remembering which profile (user agent) produced it.
p = file("YouTubeView.swift")
s = p.read_text()

s = rep(s, """    var audioKbps: Int { Int((Double(bitrate) / 1000).rounded()) }
}""", """    var audioKbps: Int { Int((Double(bitrate) / 1000).rounded()) }

    // Round 5: filled in by the resolver with the user agent of the
    // client profile that produced this format (requests for the
    // stream must carry the same agent).
    var userAgent: String = ""

    var videoCodecLabel: String {
        let mime = mimeType.lowercased()
        if mime.contains("av01") { return "AV1" }
        if mime.contains("vp09") || mime.contains("vp9") { return "VP9" }
        if mime.contains("avc1") { return "AVC" }
        if mime.contains("hvc1") || mime.contains("hev1") { return "HEVC" }
        return "Video"
    }

    var audioCodecLabel: String {
        let mime = mimeType.lowercased()
        if mime.contains("opus") { return "Opus" }
        if mime.contains("mp4a") { return "AAC" }
        return "Audio"
    }

    var containerLabel: String { mimeType.lowercased().contains("webm") ? "WebM" : "MP4" }

    var isAVCVideo: Bool { hasVideo && mimeType.lowercased().contains("avc1") }
    var isAACAudio: Bool { !hasVideo && hasAudio && mimeType.lowercased().contains("mp4a") }

    /// File extension matching this stream's real container.
    var streamFileExtension: String {
        if mimeType.lowercased().contains("webm") { return "webm" }
        return hasVideo ? "mp4" : "m4a"
    }
}""",
        "round5 stream format helpers")

s = rep(s, """    let muxed: [TrapTubeStreamFormat]
    let audioOnly: [TrapTubeStreamFormat]""", """    let muxed: [TrapTubeStreamFormat]
    let adaptiveVideo: [TrapTubeStreamFormat]
    let audioOnly: [TrapTubeStreamFormat]""",
        "round5 video info adaptive")

s = rep(s, """    private static func parseFormats(_ raw: Any?) -> [TrapTubeStreamFormat] {""",
        """    private static func parseFormats(_ raw: Any?, userAgent: String) -> [TrapTubeStreamFormat] {""",
        "round5 parseFormats signature")
s = rep(s, """                hasVideo: isVideo,
                hasAudio: isAudio || mime.contains("mp4a"))""", """                hasVideo: isVideo,
                hasAudio: isAudio || mime.contains("mp4a"),
                userAgent: userAgent)""",
        "round5 parseFormats userAgent")

ROUND5_FETCH_INFO = r'''    static func fetchInfo(videoID: String) async throws -> TrapTubeVideoInfo {
        // Round 5: aggregate across EVERY client profile instead of
        // stopping at the first usable one, so the download sheet and
        // the native player can offer all formats YouTube returns -
        // adaptive AVC/VP9/AV1 video-only at every height, AAC and
        // Opus audio-only at every bitrate, plus the muxed MP4s.
        // Formats are deduplicated by itag; the first profile that
        // offers an itag wins and its user agent travels with it.
        var failures: [String] = []
        var muxedByItag: [Int: TrapTubeStreamFormat] = [:]
        var adaptiveVideoByItag: [Int: TrapTubeStreamFormat] = [:]
        var audioByItag: [Int: TrapTubeStreamFormat] = [:]
        var title = ""
        var author = ""
        var durationSeconds = 0
        var captions: [TrapTubeCaptionTrack] = []
        var primaryUserAgent: String?

        for profile in profiles {
            do {
                let json = try await playerResponse(videoID: videoID, profile: profile)
                if let playability = json["playabilityStatus"] as? [String: Any],
                   let status = playability["status"] as? String, status != "OK" {
                    let reason = playability["reason"] as? String ?? status
                    failures.append("\(profile.name): \(reason)")
                    continue
                }
                guard let streaming = json["streamingData"] as? [String: Any] else {
                    failures.append("\(profile.name): no streaming data in the response")
                    continue
                }
                let details = json["videoDetails"] as? [String: Any]
                if title.isEmpty {
                    title = details?["title"] as? String ?? ""
                    author = details?["author"] as? String ?? ""
                    durationSeconds = Int(details?["lengthSeconds"] as? String ?? "") ?? 0
                }
                if captions.isEmpty { captions = parseCaptions(json) }
                if primaryUserAgent == nil { primaryUserAgent = profile.userAgent }

                for format in parseFormats(streaming["formats"], userAgent: profile.userAgent)
                where format.hasVideo && format.hasAudio && format.mimeType.contains("mp4") {
                    if muxedByItag[format.itag] == nil { muxedByItag[format.itag] = format }
                }
                for format in parseFormats(streaming["adaptiveFormats"], userAgent: profile.userAgent) {
                    if format.hasVideo && !format.hasAudio {
                        if adaptiveVideoByItag[format.itag] == nil { adaptiveVideoByItag[format.itag] = format }
                    } else if !format.hasVideo && format.hasAudio {
                        if audioByItag[format.itag] == nil { audioByItag[format.itag] = format }
                    } else if format.hasVideo && format.hasAudio && format.mimeType.contains("mp4") {
                        if muxedByItag[format.itag] == nil { muxedByItag[format.itag] = format }
                    }
                }
            } catch {
                failures.append("\(profile.name): \(error.localizedDescription)")
            }
        }

        let muxed = muxedByItag.values.sorted { ($0.height, $0.bitrate) > ($1.height, $1.bitrate) }
        let adaptiveVideo = adaptiveVideoByItag.values.sorted { ($0.height, $0.bitrate) > ($1.height, $1.bitrate) }
        let audioOnly = audioByItag.values.sorted { $0.bitrate > $1.bitrate }
        guard !muxed.isEmpty || !adaptiveVideo.isEmpty || !audioOnly.isEmpty else {
            throw TrapTubeModError.unplayable(failures.isEmpty ? "YouTube returned no downloadable streams" : failures.joined(separator: " · "))
        }
        return TrapTubeVideoInfo(
            videoID: videoID,
            title: title.isEmpty ? "YouTube video" : title,
            author: author,
            durationSeconds: durationSeconds,
            userAgent: primaryUserAgent ?? profiles[0].userAgent,
            muxed: muxed,
            adaptiveVideo: adaptiveVideo,
            audioOnly: audioOnly,
            captions: captions)
    }
'''
s = splice_function(s,
                    "    static func fetchInfo(videoID: String) async throws -> TrapTubeVideoInfo {",
                    ROUND5_FETCH_INFO, "round5 fetchInfo aggregation")
p.write_text(s)

# --- Item 4 (sheet side): list every format, pair adaptive picks
# with the best audio, and always convert audio-only picks to MP3.
p = file("YouTubeView.swift")
s = p.read_text()

s = rep(s, """    @State private var selectedVideoItag: Int?
    @State private var selectedAudioItag: Int?
    @State private var audioFormat = "m4a\"""", """    @State private var selectedVideoItag: Int?
    @State private var selectedAdaptiveItag: Int?
    @State private var selectedVideoIsAdaptive = false
    @State private var selectedAudioItag: Int?""",
        "round5 sheet selection state")

s = rep(s, """    private var selectedFormat: TrapTubeStreamFormat? {
        guard let info else { return nil }
        if tab == 0 {
            return info.muxed.first { $0.itag == selectedVideoItag } ?? info.muxed.first { TrapTubeStreamingQuality.withinCap($0.height) } ?? info.muxed.first
        }
        return info.audioOnly.first { $0.itag == selectedAudioItag } ?? info.audioOnly.first
    }""", """    private var selectedFormat: TrapTubeStreamFormat? {
        guard let info else { return nil }
        if tab == 0 {
            if selectedVideoIsAdaptive {
                return info.adaptiveVideo.first { $0.itag == selectedAdaptiveItag }
                    ?? info.adaptiveVideo.first { TrapTubeStreamingQuality.withinCap($0.height) }
                    ?? info.adaptiveVideo.first
            }
            return info.muxed.first { $0.itag == selectedVideoItag } ?? info.muxed.first { TrapTubeStreamingQuality.withinCap($0.height) } ?? info.muxed.first
        }
        return info.audioOnly.first { $0.itag == selectedAudioItag } ?? info.audioOnly.first
    }

    /// The audio stream an adaptive (video-only) download is paired
    /// with: the best AAC track when there is one (cleanest merge),
    /// otherwise the best audio track of any codec.
    private var pairedAudioFormat: TrapTubeStreamFormat? {
        guard let info else { return nil }
        return info.audioOnly.first { $0.isAACAudio } ?? info.audioOnly.first
    }

    private func headerSummary(_ format: TrapTubeStreamFormat, info: TrapTubeVideoInfo) -> String {
        if tab == 1 {
            return "\\(format.audioKbps) kbps · \\(format.audioCodecLabel) \\u{2192} MP3 · \\(format.sizeText(durationSeconds: info.durationSeconds))"
        }
        if selectedVideoIsAdaptive {
            let label = format.qualityLabel.isEmpty ? "\\(format.height)p" : format.qualityLabel
            return "\\(label) · \\(format.videoCodecLabel) + audio · \\(format.sizeText(durationSeconds: info.durationSeconds))"
        }
        return "\\(format.qualityLabel) · \\(format.sizeText(durationSeconds: info.durationSeconds))"
    }""",
        "round5 sheet selected format")

s = rep(s, """            if let format = selectedFormat {
                Text("\\(tab == 0 ? format.qualityLabel : "\\(format.audioKbps) kbps") · \\(format.sizeText(durationSeconds: info.durationSeconds))")
                    .font(.caption.weight(.semibold)).foregroundStyle(theme.accent)
            }""", """            if let format = selectedFormat {
                Text(headerSummary(format, info: info))
                    .font(.caption.weight(.semibold)).foregroundStyle(theme.accent)
            }""",
        "round5 sheet header summary")

s = rep(s, """            Text("Video (avc1)").tag(0)""",
        """            Text("Video").tag(0)""",
        "round5 sheet picker label")

s = rep(s, """        if tab == 0 {
            if info.muxed.isEmpty {
                Text("YouTube did not offer a directly downloadable MP4 for this video. Audio-only may still be available.")
                    .font(.caption).foregroundStyle(Color(hex: "A6A4A6"))
                    .fixedSize(horizontal: false, vertical: true)
            } else {
                VStack(spacing: 8) {
                    ForEach(info.muxed) { format in
                        formatRow(label: "\\(format.qualityLabel) · MP4",
                                  size: format.sizeText(durationSeconds: info.durationSeconds),
                                  selected: selectedFormat?.itag == format.itag) {
                            selectedVideoItag = format.itag
                        }
                    }
                }
            }
        } else {""", """        if tab == 0 {
            if info.muxed.isEmpty && info.adaptiveVideo.isEmpty {
                Text("YouTube did not offer a downloadable video stream for this video. Audio-only may still be available.")
                    .font(.caption).foregroundStyle(Color(hex: "A6A4A6"))
                    .fixedSize(horizontal: false, vertical: true)
            }
            if !info.muxed.isEmpty {
                Text("Video + audio · single file").font(.subheadline.bold()).foregroundStyle(.white)
                VStack(spacing: 8) {
                    ForEach(info.muxed) { format in
                        formatRow(label: "\\(format.qualityLabel) · MP4",
                                  size: format.sizeText(durationSeconds: info.durationSeconds),
                                  selected: !selectedVideoIsAdaptive && selectedFormat?.itag == format.itag) {
                            selectedVideoItag = format.itag
                            selectedVideoIsAdaptive = false
                        }
                    }
                }
            }
            if !info.adaptiveVideo.isEmpty {
                Text("Adaptive video · best audio added, then merged").font(.subheadline.bold()).foregroundStyle(.white)
                    .padding(.top, 6)
                VStack(spacing: 8) {
                    ForEach(info.adaptiveVideo) { format in
                        formatRow(label: "\\(format.qualityLabel.isEmpty ? "\\(format.height)p" : format.qualityLabel) · \\(format.videoCodecLabel) · \\(format.containerLabel)",
                                  size: format.sizeText(durationSeconds: info.durationSeconds),
                                  selected: selectedVideoIsAdaptive && selectedFormat?.itag == format.itag) {
                            selectedAdaptiveItag = format.itag
                            selectedVideoIsAdaptive = true
                        }
                    }
                }
                Text("AVC picks merge without re-encoding. VP9 and AV1 picks are converted to H.264 at the same height so the result plays in the TrapTube tab.")
                    .font(.caption).foregroundStyle(Color(hex: "A6A4A6"))
                    .fixedSize(horizontal: false, vertical: true)
            }
        } else {""",
        "round5 sheet video lists")

s = rep(s, """            if info.audioOnly.isEmpty {
                Text("YouTube did not offer a directly downloadable AAC track for this video.")
                    .font(.caption).foregroundStyle(Color(hex: "A6A4A6"))
                    .fixedSize(horizontal: false, vertical: true)
            } else {
                VStack(spacing: 8) {
                    ForEach(info.audioOnly) { format in
                        formatRow(label: "\\(format.audioKbps) kbps · AAC",
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

                VStack(alignment: .leading, spacing: 10) {""", """            if info.audioOnly.isEmpty {
                Text("YouTube did not offer a downloadable audio track for this video.")
                    .font(.caption).foregroundStyle(Color(hex: "A6A4A6"))
                    .fixedSize(horizontal: false, vertical: true)
            } else {
                VStack(spacing: 8) {
                    ForEach(info.audioOnly) { format in
                        formatRow(label: "\\(format.audioKbps) kbps · \\(format.audioCodecLabel)",
                                  size: format.sizeText(durationSeconds: info.durationSeconds),
                                  selected: selectedFormat?.itag == format.itag) {
                            selectedAudioItag = format.itag
                        }
                    }
                }

                Text("Whichever track you pick is downloaded and converted to MP3 automatically, then stored in the TrapTube tab for playback.")
                    .font(.caption).foregroundStyle(Color(hex: "A6A4A6"))
                    .fixedSize(horizontal: false, vertical: true)

                VStack(alignment: .leading, spacing: 10) {""",
        "round5 sheet audio lists")

s = rep(s, """    private func applyDefaults(_ info: TrapTubeVideoInfo) {
        if selectedVideoItag == nil { selectedVideoItag = (info.muxed.first { TrapTubeStreamingQuality.withinCap($0.height) } ?? info.muxed.first)?.itag }
        if selectedAudioItag == nil { selectedAudioItag = info.audioOnly.first?.itag }""", """    private func applyDefaults(_ info: TrapTubeVideoInfo) {
        if selectedVideoItag == nil { selectedVideoItag = (info.muxed.first { TrapTubeStreamingQuality.withinCap($0.height) } ?? info.muxed.first)?.itag }
        if selectedAdaptiveItag == nil { selectedAdaptiveItag = (info.adaptiveVideo.first { TrapTubeStreamingQuality.withinCap($0.height) } ?? info.adaptiveVideo.first)?.itag }
        if info.muxed.isEmpty, !info.adaptiveVideo.isEmpty { selectedVideoIsAdaptive = true }
        if selectedAudioItag == nil { selectedAudioItag = info.audioOnly.first?.itag }""",
        "round5 sheet defaults")

ROUND5_START_DOWNLOAD = r'''    private func startDownload(_ info: TrapTubeVideoInfo) {
        guard let format = selectedFormat else { return }
        let title: String
        if tab == 1 {
            let editedTitle = metaTitle.trimmingCharacters(in: .whitespacesAndNewlines)
            let editedArtist = metaArtist.trimmingCharacters(in: .whitespacesAndNewlines)
            title = editedTitle.isEmpty ? info.title : (editedArtist.isEmpty ? editedTitle : "\(editedArtist) – \(editedTitle)")
        } else {
            title = info.title
        }

        if tab == 1 {
            // Round 5: an audio-only pick ALWAYS ends as an MP3 in the
            // TrapTube tab, whichever stream was chosen (AAC or Opus).
            guard let url = URL(string: format.url) else { return }
            manager.enqueueDirectDownload(
                remoteURL: url,
                title: title,
                mode: "audio",
                fileName: trapTubeSafeFileName(title, ext: format.streamFileExtension),
                videoID: videoID,
                convertToMP3: true,
                userAgent: format.userAgent.isEmpty ? info.userAgent : format.userAgent)
        } else if selectedVideoIsAdaptive {
            // Round 5: a video-only pick downloads together with the
            // best paired audio and is merged by the manager (AVC
            // remux, VP9/AV1 transcode to H.264).
            guard let videoURL = URL(string: format.url),
                  let audio = pairedAudioFormat,
                  let audioURL = URL(string: audio.url) else {
                startedMessage = "No audio track is available to pair with this video stream."
                return
            }
            manager.enqueueAdaptiveDownload(
                videoURL: videoURL,
                audioURL: audioURL,
                title: title,
                videoIsAVC: format.isAVCVideo,
                audioIsAAC: audio.isAACAudio,
                videoID: videoID,
                videoUserAgent: format.userAgent.isEmpty ? info.userAgent : format.userAgent,
                audioUserAgent: audio.userAgent.isEmpty ? info.userAgent : audio.userAgent)
        } else {
            guard let url = URL(string: format.url) else { return }
            manager.enqueueDirectDownload(
                remoteURL: url,
                title: title,
                mode: "video",
                fileName: trapTubeSafeFileName(title, ext: "mp4"),
                videoID: videoID,
                convertToMP3: false,
                userAgent: format.userAgent.isEmpty ? info.userAgent : format.userAgent)
        }

        if captionIndex > 0, info.captions.indices.contains(captionIndex - 1) {
            let track = info.captions[captionIndex - 1]
            Task {
                if let captions = try? await TrapTubeCaptionSaver.fetchText(track, userAgent: info.userAgent) {
                    let fileName = trapTubeSafeFileName(title, ext: "captions.txt")
                    let url = TrapTubeDownloadPaths.downloadsDirectory.appendingPathComponent(fileName)
                    try? captions.write(to: url, atomically: true, encoding: .utf8)
                    if FileManager.default.fileExists(atPath: url.path) {
                        manager.registerLocalFile(fileURL: url, title: "\(title) — captions", mode: "text", videoID: videoID)
                    }
                }
            }
        }

        downloadStarted = true
        startedMessage = "Download started — track its progress in the TrapTube tab."
    }
'''
s = splice_function(s,
                    "    private func startDownload(_ info: TrapTubeVideoInfo) {",
                    ROUND5_START_DOWNLOAD, "round5 startDownload")

# Download later: fall back to the adaptive path when no muxed MP4
# exists, so the feature keeps working for every video.
s = rep(s, """                let info = try await TrapTubeInnerTube.fetchInfo(videoID: entry.videoID)
                guard let format = info.muxed.first, let url = URL(string: format.url) else {
                    manager.lastError = "No directly downloadable MP4 was found for this video."
                    return
                }
                manager.enqueueDirectDownload(remoteURL: url, title: info.title, mode: "video",
                                              fileName: trapTubeSafeFileName(info.title, ext: "mp4"),
                                              videoID: entry.videoID, convertToMP3: false,
                                              userAgent: info.userAgent)
                removeLater(entry)""", """                let info = try await TrapTubeInnerTube.fetchInfo(videoID: entry.videoID)
                if let format = info.muxed.first, let url = URL(string: format.url) {
                    manager.enqueueDirectDownload(remoteURL: url, title: info.title, mode: "video",
                                                  fileName: trapTubeSafeFileName(info.title, ext: "mp4"),
                                                  videoID: entry.videoID, convertToMP3: false,
                                                  userAgent: format.userAgent.isEmpty ? info.userAgent : format.userAgent)
                    removeLater(entry)
                    return
                }
                let adaptiveVideo = info.adaptiveVideo.first { $0.isAVCVideo } ?? info.adaptiveVideo.first
                let pairedAudio = info.audioOnly.first { $0.isAACAudio } ?? info.audioOnly.first
                guard let adaptiveVideo, let pairedAudio,
                      let videoURL = URL(string: adaptiveVideo.url),
                      let audioURL = URL(string: pairedAudio.url) else {
                    manager.lastError = "No downloadable video stream was found for this video."
                    return
                }
                manager.enqueueAdaptiveDownload(
                    videoURL: videoURL, audioURL: audioURL, title: info.title,
                    videoIsAVC: adaptiveVideo.isAVCVideo, audioIsAAC: pairedAudio.isAACAudio,
                    videoID: entry.videoID,
                    videoUserAgent: adaptiveVideo.userAgent.isEmpty ? info.userAgent : adaptiveVideo.userAgent,
                    audioUserAgent: pairedAudio.userAgent.isEmpty ? info.userAgent : pairedAudio.userAgent)
                removeLater(entry)""",
        "round5 download later adaptive fallback")

p.write_text(s)

# --- Item 4 (manager side): the adaptive download + merge job, and
# an honest MP3-fallback message (the kept original may be WebM now).
p = file("TypeTypeService.swift")
s = p.read_text()

s = rep(s, """    func process(_ item: TrapTubeDownloadedMedia, operation: TrapTubeFFmpegOperation) async throws {""", """    // MARK: Round 5 adaptive downloads (video-only + paired audio)

    /// Downloads a video-only stream and its paired audio stream,
    /// then merges them with FFmpeg: a straight remux when the video
    /// is AVC and the audio is AAC, a video-copy + AAC transcode when
    /// only the audio needs converting, and a full H.264 transcode
    /// (same height) for VP9/AV1 picks so the result plays in the
    /// TrapTube tab. Progress surfaces through the same jobs list as
    /// direct downloads.
    func enqueueAdaptiveDownload(videoURL: URL, audioURL: URL, title: String,
                                 videoIsAVC: Bool, audioIsAAC: Bool,
                                 videoID: String?, videoUserAgent: String?, audioUserAgent: String?) {
        lastError = nil
        let jobID = UUID().uuidString
        jobs.insert(TrapTubeDownloadTask(
            id: jobID, title: title, mode: "video", status: "downloading",
            stage: "Downloading video", progress: 0, downloadedBytes: 0,
            totalBytes: 0, speedBytesPerSecond: 0, error: nil
        ), at: 0)
        Task { [weak self] in
            await self?.runAdaptiveDownload(
                jobID: jobID, videoURL: videoURL, audioURL: audioURL, title: title,
                videoIsAVC: videoIsAVC, audioIsAAC: audioIsAAC,
                videoID: videoID, videoUserAgent: videoUserAgent, audioUserAgent: audioUserAgent)
        }
    }

    private func runAdaptiveDownload(jobID: String, videoURL: URL, audioURL: URL, title: String,
                                     videoIsAVC: Bool, audioIsAAC: Bool,
                                     videoID: String?, videoUserAgent: String?, audioUserAgent: String?) async {
        do {
            try FileManager.default.createDirectory(at: downloadsDirectory, withIntermediateDirectories: true)
            let videoTemp = try await TrapTubeDirectDownloader.shared.download(
                from: videoURL, userAgent: videoUserAgent
            ) { [weak self] fraction in
                Task { @MainActor in
                    self?.updateJob(jobID) {
                        $0.progress = fraction * 0.7
                        $0.stage = "Downloading video \\(Int(fraction * 100))%"
                    }
                }
            }
            updateJob(jobID) { $0.stage = "Downloading audio"; $0.progress = 0.7 }
            let audioTemp = try await TrapTubeDirectDownloader.shared.download(
                from: audioURL, userAgent: audioUserAgent
            ) { [weak self] fraction in
                Task { @MainActor in
                    self?.updateJob(jobID) {
                        $0.progress = 0.7 + fraction * 0.2
                        $0.stage = "Downloading audio \\(Int(fraction * 100))%"
                    }
                }
            }
            defer {
                try? FileManager.default.removeItem(at: videoTemp)
                try? FileManager.default.removeItem(at: audioTemp)
            }
            updateJob(jobID) {
                $0.stage = videoIsAVC ? "Processing (merging)" : "Processing (converting to H.264)"
                $0.progress = 0.95
            }

            var destination = downloadsDirectory.appendingPathComponent(trapTubeSafeFileName(title, ext: "mp4"))
            if FileManager.default.fileExists(atPath: destination.path) {
                let base = destination.deletingPathExtension().lastPathComponent
                let suffix = String(UUID().uuidString.prefix(6))
                destination = downloadsDirectory.appendingPathComponent("\\(base)-\\(suffix).mp4")
            }

            var arguments = ["-y", "-i", videoTemp.path, "-i", audioTemp.path,
                             "-map", "0:v:0", "-map", "1:a:0"]
            if videoIsAVC && audioIsAAC {
                arguments += ["-c", "copy"]
            } else if videoIsAVC {
                arguments += ["-c:v", "copy", "-c:a", "aac", "-b:a", "192k"]
            } else {
                arguments += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                              "-c:a", "aac", "-b:a", "192k"]
            }
            arguments += ["-movflags", "+faststart", "-metadata", "title=\\(title)", destination.path]
            try await TrapTubeFFmpegProcessor.execute(arguments)
            guard FileManager.default.fileExists(atPath: destination.path) else {
                throw TrapTubeFFmpegError.missingOutput
            }

            let size = (try? FileManager.default.attributesOfItem(atPath: destination.path))
                .flatMap { ($0[.size] as? NSNumber)?.int64Value } ?? 0
            let item = TrapTubeDownloadedMedia(
                id: UUID().uuidString,
                title: title,
                fileName: destination.lastPathComponent,
                mode: "video",
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

    func process(_ item: TrapTubeDownloadedMedia, operation: TrapTubeFFmpegOperation) async throws {""",
        "round5 adaptive download manager")

s = rep(s, """                    lastError = "MP3 conversion failed, so the M4A original was kept: \\(error.localizedDescription)\"""",
        """                    lastError = "MP3 conversion failed, so the downloaded original was kept: \\(error.localizedDescription)\"""",
        "round5 mp3 fallback message")
p.write_text(s)

# --- Item 3: native stream player with the working EQ --------------
p = file("YouTubeView.swift")
s = p.read_text()

# Mod sheet: "Play in..." expands; the first option streams the same
# video natively with the EQ attached.
s = rep(s, """    @State private var showPlayNote = false
    @State private var playItem: TrapTubeDownloadedMedia?""", """    @State private var showPlayNote = false
    @State private var showPlayOptions = false
    @State private var playItem: TrapTubeDownloadedMedia?
    @State private var nativePlay: TrapTubeNativePlayRequest?""",
        "round5 mod sheet native state")

s = rep(s, """                    modRow("Play in...", detail: playDetail, icon: "play.rectangle.on.rectangle") {
                        playAction()
                    }
                    if showPlayNote {
                        Text("This video isn't downloaded yet. Download it here first — after that it plays inside TrapTube from the TrapTube tab: videos in the EQ video player, audio in your library.")
                            .font(.caption).foregroundStyle(Color(hex: "A6A4A6"))
                            .fixedSize(horizontal: false, vertical: true)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(.vertical, 10).padding(.leading, 24)
                    }""", """                    modRow("Play in...", detail: playDetail, icon: "play.rectangle.on.rectangle") {
                        withAnimation { showPlayOptions.toggle() }
                    }
                    if showPlayOptions {
                        modRow("TrapTube Player (EQ)", detail: "Stream it now with the 16-band EQ", icon: "waveform") {
                            nativePlay = TrapTubeNativePlayRequest(videoID: request.videoID, title: displayTitle)
                        }
                        if downloadedCopy != nil {
                            modRow("Downloaded copy", detail: playDetail, icon: "arrow.down.circle") {
                                playAction()
                            }
                        } else {
                            Text("No downloaded copy yet — downloading it here also makes it playable from the TrapTube tab (videos in the EQ video player, audio in your library).")
                                .font(.caption).foregroundStyle(Color(hex: "A6A4A6"))
                                .fixedSize(horizontal: false, vertical: true)
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .padding(.vertical, 10).padding(.leading, 24)
                        }
                    }""",
        "round5 mod sheet play options")

s = rep(s, """        .sheet(item: $playItem) { item in
            TrapTubeDownloadedVideoPlayer(item: item)
                .preferredColorScheme(.dark)
        }
    }""", """        .sheet(item: $playItem) { item in
            TrapTubeDownloadedVideoPlayer(item: item)
                .preferredColorScheme(.dark)
        }
        .fullScreenCover(item: $nativePlay) { playRequest in
            TrapTubeNativeStreamPlayer(request: playRequest)
                .preferredColorScheme(.dark)
        }
    }""",
        "round5 mod sheet native cover")

# Stream EQ sheet: when the page graph reports it cannot process the
# stream, offer the native player instead of dead-ending.
s = rep(s, """    @ObservedObject private var eq = TrapTubeWebEQ.shared
    @ObservedObject private var center = TrapTubeWebEQCenter.shared""", """    @ObservedObject private var eq = TrapTubeWebEQ.shared
    @ObservedObject private var center = TrapTubeWebEQCenter.shared
    @ObservedObject private var playerSession = TrapTubePlayerSession.shared
    @State private var nativePlay: TrapTubeNativePlayRequest?""",
        "round5 eq sheet native state")

s = rep(s, """        .presentationDetents([.large])
        .onAppear { TrapTubePlayerSession.shared.requestEQStatus(for: host) }""", """        .presentationDetents([.large])
        .onAppear { TrapTubePlayerSession.shared.requestEQStatus(for: host) }
        .fullScreenCover(item: $nativePlay) { playRequest in
            TrapTubeNativeStreamPlayer(request: playRequest)
                .preferredColorScheme(.dark)
        }""",
        "round5 eq sheet native cover")

s = rep(s, """                if state == "flowing", let level = status?.level {
                    ProgressView(value: min(1, level * 6)).tint(.green)
                }
            }
            Spacer(minLength: 0)
        }""", """                if state == "flowing", let level = status?.level {
                    ProgressView(value: min(1, level * 6)).tint(.green)
                }
                if (state == "bypassed" || state == "error"),
                   playerSession.watchHost == host, let videoID = playerSession.watchVideoID {
                    Button {
                        nativePlay = TrapTubeNativePlayRequest(videoID: videoID, title: playerSession.watchTitle)
                    } label: {
                        Label("Play in TrapTube Player", systemImage: "play.rectangle.fill")
                            .font(.caption.bold()).foregroundStyle(.white)
                            .padding(.horizontal, 12).padding(.vertical, 8)
                            .background(theme.accent, in: Capsule())
                    }
                    .buttonStyle(.plain)
                    .padding(.top, 2)
                }
            }
            Spacer(minLength: 0)
        }""",
        "round5 eq sheet native button")

ROUND5_NATIVE_PLAYER_SWIFT = r'''

// MARK: - Round 5 native stream player (the EQ path that always works)
//
// The in-page WebAudio EQ cannot process most YouTube streams: the
// media is served without CORS access, so the graph measures silence
// and auto-bypasses. This player takes the route the app already
// owns - resolve the same video with TrapTubeInnerTube and play it
// in AVPlayer with TrapTubeTapEQ attached, the exact stack that
// equalizes downloaded files - with EqualizerView for the controls.

struct TrapTubeNativePlayRequest: Identifiable {
    let videoID: String
    let title: String
    var id: String { videoID }
}

@MainActor
final class TrapTubeNativeStreamPlayerModel: ObservableObject {
    enum Phase {
        case resolving
        case playing
        case failed(String)
    }

    let player = AVPlayer()
    @Published private(set) var phase: Phase = .resolving
    @Published private(set) var equalizerActive = false
    @Published private(set) var eqAttachFinished = false

    private var startTask: Task<Void, Never>?
    private var statusObservation: NSKeyValueObservation?
    private var attachGeneration = 0

    func start(videoID: String) {
        guard startTask == nil else { return }
        try? AVAudioSession.sharedInstance().setCategory(.playback, mode: .moviePlayback, options: [.allowAirPlay, .allowBluetoothA2DP])
        try? AVAudioSession.sharedInstance().setActive(true)
        startTask = Task { [weak self] in
            guard let self else { return }
            do {
                let info = try await TrapTubeInnerTube.fetchInfo(videoID: videoID)
                let item = try await Self.makePlayerItem(info: info)
                if Task.isCancelled { return }
                self.statusObservation = item.observe(\.status, options: [.new]) { [weak self] observedItem, _ in
                    guard observedItem.status == .failed else { return }
                    let message = observedItem.error?.localizedDescription ?? "The stream failed to load."
                    Task { @MainActor in self?.phase = .failed(message) }
                }
                self.player.replaceCurrentItem(with: item)
                self.phase = .playing
                self.player.play()
                // The EQ tap attaches alongside playback; it never
                // gates it, and a failure just leaves the badge honest.
                let generation = self.attachGeneration
                let attached = await TrapTubeTapEQ.shared.attach(to: item)
                if generation == self.attachGeneration, self.player.currentItem === item {
                    self.equalizerActive = attached
                    self.eqAttachFinished = true
                }
            } catch {
                if !Task.isCancelled { self.phase = .failed(error.localizedDescription) }
            }
        }
    }

    func stop() {
        attachGeneration += 1
        startTask?.cancel()
        startTask = nil
        statusObservation?.invalidate()
        statusObservation = nil
        player.pause()
        player.replaceCurrentItem(with: nil)
        equalizerActive = false
        eqAttachFinished = false
    }

    /// Muxed MP4 when YouTube offers one; otherwise an AVC + AAC
    /// composition built from the adaptive streams (the same pairing
    /// the download merge uses).
    private static func makePlayerItem(info: TrapTubeVideoInfo) async throws -> AVPlayerItem {
        if let muxed = info.muxed.first, let url = URL(string: muxed.url) {
            let asset = AVURLAsset(url: url, options: headerOptions(userAgent: muxed.userAgent.isEmpty ? info.userAgent : muxed.userAgent))
            return AVPlayerItem(asset: asset)
        }
        guard let video = info.adaptiveVideo.first(where: { $0.isAVCVideo }),
              let audio = info.audioOnly.first(where: { $0.isAACAudio }),
              let videoURL = URL(string: video.url),
              let audioURL = URL(string: audio.url) else {
            throw TrapTubeModError.unplayable("no stream this player can use (it needs a muxed MP4 or an AVC + AAC pair)")
        }
        let videoAsset = AVURLAsset(url: videoURL, options: headerOptions(userAgent: video.userAgent.isEmpty ? info.userAgent : video.userAgent))
        let audioAsset = AVURLAsset(url: audioURL, options: headerOptions(userAgent: audio.userAgent.isEmpty ? info.userAgent : audio.userAgent))
        guard let videoTrack = try await videoAsset.loadTracks(withMediaType: .video).first,
              let audioTrack = try await audioAsset.loadTracks(withMediaType: .audio).first else {
            throw TrapTubeModError.unplayable("the adaptive streams had no usable tracks")
        }
        let videoDuration = try await videoAsset.load(.duration)
        let audioDuration = try await audioAsset.load(.duration)
        let duration = CMTimeMinimum(videoDuration, audioDuration)
        guard duration.isValid, duration.seconds > 0 else {
            throw TrapTubeModError.unplayable("the adaptive streams reported no duration")
        }
        let composition = AVMutableComposition()
        guard let compositionVideo = composition.addMutableTrack(withMediaType: .video, preferredTrackID: kCMPersistentTrackID_Invalid),
              let compositionAudio = composition.addMutableTrack(withMediaType: .audio, preferredTrackID: kCMPersistentTrackID_Invalid) else {
            throw TrapTubeModError.unplayable("could not build the playback composition")
        }
        let range = CMTimeRange(start: .zero, duration: duration)
        try compositionVideo.insertTimeRange(range, of: videoTrack, at: .zero)
        try compositionAudio.insertTimeRange(range, of: audioTrack, at: .zero)
        compositionVideo.preferredTransform = try await videoTrack.load(.preferredTransform)
        return AVPlayerItem(asset: composition)
    }

    private static func headerOptions(userAgent: String) -> [String: Any] {
        ["AVURLAssetHTTPHeaderFieldsKey": ["User-Agent": userAgent, "Referer": "https://www.youtube.com/"]]
    }
}

struct TrapTubeNativeStreamPlayer: View {
    let request: TrapTubeNativePlayRequest

    @Environment(\.dismiss) private var dismiss
    @EnvironmentObject private var audio: AudioEngineManager
    @EnvironmentObject private var theme: ThemeManager
    @StateObject private var model = TrapTubeNativeStreamPlayerModel()
    @State private var showEqualizer = false

    var body: some View {
        ZStack(alignment: .topLeading) {
            Color.black.ignoresSafeArea()
            VideoPlayer(player: model.player)
                .background(.black)
                .ignoresSafeArea()

            VStack(alignment: .leading, spacing: 8) {
                HStack(spacing: 8) {
                    HStack(spacing: 6) {
                        Image(systemName: "waveform")
                        Text(badgeText)
                    }
                    .font(.caption2.bold())
                    .foregroundStyle(.white)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 7)
                    .background(.black.opacity(0.72), in: Capsule())
                    Spacer()
                    Button {
                        showEqualizer = true
                    } label: {
                        Label("EQ", systemImage: "slider.horizontal.3")
                            .font(.caption.bold()).foregroundStyle(.white)
                            .padding(.horizontal, 11).padding(.vertical, 8)
                            .background(.black.opacity(0.72), in: Capsule())
                    }
                    .accessibilityLabel("Open the equalizer")
                    Button {
                        dismiss()
                    } label: {
                        Image(systemName: "xmark")
                            .font(.caption.bold()).foregroundStyle(.white)
                            .frame(width: 30, height: 30)
                            .background(.black.opacity(0.72), in: Circle())
                    }
                    .accessibilityLabel("Close player")
                }
                if !request.title.isEmpty {
                    Text(request.title)
                        .font(.caption.weight(.semibold)).foregroundStyle(.white)
                        .lineLimit(2)
                        .padding(.horizontal, 10).padding(.vertical, 6)
                        .background(.black.opacity(0.55), in: RoundedRectangle(cornerRadius: 9))
                }
            }
            .padding(.top, 12)
            .padding(.horizontal, 12)

            if case .resolving = model.phase {
                VStack(spacing: 12) {
                    ProgressView().tint(.white)
                    Text("Resolving stream…").font(.subheadline.weight(.semibold)).foregroundStyle(.white.opacity(0.85))
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            }

            if case .failed(let message) = model.phase {
                VStack(spacing: 12) {
                    Image(systemName: "exclamationmark.triangle.fill").font(.title2).foregroundStyle(Color(hex: "FF7A84"))
                    Text(message).font(.subheadline).foregroundStyle(.white)
                        .multilineTextAlignment(.center)
                        .fixedSize(horizontal: false, vertical: true)
                    Button("Close") { dismiss() }
                        .font(.subheadline.bold()).foregroundStyle(.white)
                        .padding(.horizontal, 16).padding(.vertical, 9)
                        .background(.white.opacity(0.12), in: Capsule())
                }
                .padding(24)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(.black.opacity(0.66))
            }
        }
        .background(.black)
        .task { model.start(videoID: request.videoID) }
        .onDisappear { model.stop() }
        .onChange(of: audio.eqGains) { _, _ in TrapTubeTapEQ.shared.update(gains: audio.eqGains, bass: audio.bassBoost, master: audio.masterGain) }
        .onChange(of: audio.bassBoost) { _, _ in TrapTubeTapEQ.shared.update(gains: audio.eqGains, bass: audio.bassBoost, master: audio.masterGain) }
        .onChange(of: audio.masterGain) { _, _ in TrapTubeTapEQ.shared.update(gains: audio.eqGains, bass: audio.bassBoost, master: audio.masterGain) }
        .sheet(isPresented: $showEqualizer) {
            EqualizerView().environmentObject(audio).environmentObject(theme).presentationDetents([.large])
        }
    }

    private var badgeText: String {
        switch model.phase {
        case .resolving: return "RESOLVING…"
        case .failed: return "PLAYBACK FAILED"
        case .playing:
            if !model.eqAttachFinished { return "EQ ATTACHING…" }
            return model.equalizerActive ? "TRAPTUBE EQ ACTIVE" : "EQ UNAVAILABLE FOR THIS STREAM"
        }
    }
}
'''
if "struct TrapTubeNativeStreamPlayer" not in s:
    s += ROUND5_NATIVE_PLAYER_SWIFT
p.write_text(s)

# --- Item 5: downloaded-file playback crash audit + hardening -----
# Path audited in the generated sources: TrapTubeDownloadsView row
# play button -> .sheet(item:) -> TrapTubeDownloadedVideoPlayer ->
# TrapTubeEQMediaPlayer.play(url:) -> AVPlayerItem ->
# TrapTubeTapEQ.attach -> MTAudioProcessingTap (TapState).
# Vectors found and fixed:
#  (a) play(url:) never validated the file. A manifest entry whose
#      file was deleted or truncated (restoreCompleted only filters
#      at launch) produced a dead item and a wedged black player.
#      Fixed: existence + non-zero size check, a published
#      playbackError, and item-status observation so a corrupt file
#      surfaces its real error in the player view.
#  (b) play() only called player.play() AFTER the EQ attach awaited
#      asset track loading, inside an unstructured Task with no
#      cancellation: dismissing/reopening raced attach completions
#      against teardown and could stack taps. Fixed: playback starts
#      immediately, attach runs alongside under a generation token,
#      stop() cancels the task and invalidates the (single) status
#      observation exactly once.
#  (c) TapState.prepare force-unwrapped its freshly allocated
#      coefficient/delay/snapshot pointers on the audio render path.
#      Fixed: build through locals, publish once, no unwraps.
#  (d) attach(to:) happily stacked a second tap on an item that
#      already carried one (re-presentation), orphaning the first
#      tap's retained state. Fixed: early-out when a tap exists.
#  (e) Teardown: the player registered no KVO before (nothing to
#      double-remove); the one observation added by (a) is
#      invalidated in stop() and nowhere else.
p = file("AudioEngineManager.swift")
s = p.read_text()

s = rep(s, """    func attach(to item: AVPlayerItem) async -> Bool {
        guard let tracks = try? await item.asset.loadTracks(withMediaType: .audio), let track = tracks.first else { return false }""", """    func attach(to item: AVPlayerItem) async -> Bool {
        // Round 5: never stack a second tap on an item that already
        // carries one (a re-attach on sheet re-presentation used to
        // orphan the first tap's retained state).
        if let existingParameters = item.audioMix?.inputParameters,
           existingParameters.contains(where: { $0.audioTapProcessor != nil }) {
            return true
        }
        guard let tracks = try? await item.asset.loadTracks(withMediaType: .audio), let track = tracks.first else { return false }""",
        "round5 tap no stacking")

s = rep(s, """        guard isFloat32, channels > 0, sampleRate > 0 else { return }   // unsupported format: audio passes through untouched
        let count = TrapTubeTapEQ.sectionCount
        coefficients = .allocate(capacity: 5 * count)
        for section in 0..<count { Self.identity(coefficients! + section * 5) }
        setup = vDSP_biquad_CreateSetupD(coefficients!, vDSP_Length(count))
        delays = .allocate(capacity: delayLength * channels); delays!.initialize(repeating: 0, count: delayLength * channels)
        snapshot = .allocate(capacity: 18); snapshot!.initialize(repeating: 0, count: 18); snapshot![17] = 1
        appliedVersion = 0""", """        guard isFloat32, channels > 0, sampleRate > 0 else { return }   // unsupported format: audio passes through untouched
        let count = TrapTubeTapEQ.sectionCount
        // Round 5: no force unwraps on the render path - build
        // through locals and publish the pointers once, fully built.
        let newCoefficients = UnsafeMutablePointer<Double>.allocate(capacity: 5 * count)
        for section in 0..<count { Self.identity(newCoefficients + section * 5) }
        coefficients = newCoefficients
        setup = vDSP_biquad_CreateSetupD(newCoefficients, vDSP_Length(count))
        let newDelays = UnsafeMutablePointer<Float>.allocate(capacity: delayLength * channels)
        newDelays.initialize(repeating: 0, count: delayLength * channels)
        delays = newDelays
        let newSnapshot = UnsafeMutablePointer<Float>.allocate(capacity: 18)
        newSnapshot.initialize(repeating: 0, count: 18)
        newSnapshot[17] = 1
        snapshot = newSnapshot
        appliedVersion = 0""",
        "round5 tapstate unwraps")

ROUND5_EQ_MEDIA_PLAYER = r'''/// Plays any local audio/video file or progressive URL through AVPlayer with the shared EQ attached.
/// Bind `player` to a `VideoPlayer` or `AVPlayerViewController`.
///
/// Round 5 hardening (downloaded files crashed/wedged on open): the
/// file is validated BEFORE an item is built, item failures are
/// observed and published instead of leaving a silent black screen,
/// playback starts immediately (the EQ tap attaches alongside and
/// can never gate or kill it), and a generation counter makes attach
/// completions from a previous open harmless after stop().
@MainActor
final class TrapTubeEQMediaPlayer: ObservableObject {
    let player = AVPlayer()
    @Published private(set) var equalizerActive = false
    @Published private(set) var playbackError: String?

    private var attachTask: Task<Void, Never>?
    private var statusObservation: NSKeyValueObservation?
    private var currentItem: AVPlayerItem?
    private var generation = 0

    func play(url: URL) {
        stop()
        playbackError = nil

        // Never hand AVPlayer a file that is not really there: a
        // manifest entry whose file was deleted or left empty used
        // to become a dead item (and the racing tap attach made it
        // worse). Say so in the UI instead.
        let attributes = try? FileManager.default.attributesOfItem(atPath: url.path)
        let size = (attributes?[.size] as? NSNumber)?.int64Value ?? 0
        guard FileManager.default.fileExists(atPath: url.path), size > 0 else {
            playbackError = "This downloaded file is missing or empty. Delete it and download it again."
            return
        }

        try? AVAudioSession.sharedInstance().setCategory(.playback, mode: .moviePlayback, options: [.allowAirPlay, .allowBluetoothA2DP])
        try? AVAudioSession.sharedInstance().setActive(true)

        let item = AVPlayerItem(url: url)
        currentItem = item
        equalizerActive = false
        statusObservation = item.observe(\.status, options: [.new]) { [weak self] observedItem, _ in
            guard observedItem.status == .failed else { return }
            let message = observedItem.error?.localizedDescription ?? "This file could not be played."
            Task { @MainActor in self?.playbackError = message }
        }
        player.replaceCurrentItem(with: item)
        player.play()

        // The tap attaches alongside playback; failure just means the
        // file plays without EQ (the badge says so) - never silence.
        let playGeneration = generation
        attachTask = Task { [weak self] in
            let attached = await TrapTubeTapEQ.shared.attach(to: item)
            guard let self, self.generation == playGeneration, self.currentItem === item else { return }
            self.equalizerActive = attached
        }
    }

    func stop() {
        generation += 1
        attachTask?.cancel()
        attachTask = nil
        statusObservation?.invalidate()
        statusObservation = nil
        currentItem = nil
        player.pause()
        player.replaceCurrentItem(with: nil)
        equalizerActive = false
    }
}
'''
# TrapTubeEQMediaPlayer is the LAST declaration in this file, so the
# old class is replaced by truncating at its doc comment.
if "Round 5 hardening (downloaded files" not in s:
    r5_player_marker = "/// Plays any local audio/video file or progressive URL through AVPlayer with the shared EQ attached."
    if r5_player_marker not in s:
        raise SystemExit("round5 eq media player anchor missing")
    s = s[:s.index(r5_player_marker)] + ROUND5_EQ_MEDIA_PLAYER + "\n"
p.write_text(s)

# The downloaded-file player view surfaces the error honestly.
p = file("YouTubeView.swift")
s = p.read_text()
s = rep(s, """            VideoPlayer(player: mediaPlayer.player)
                .background(.black)
                .ignoresSafeArea()
            HStack(spacing: 6) {
                Image(systemName: "waveform")
                Text(mediaPlayer.equalizerActive ? "TRAPTUBE EQ ACTIVE" : "EQ UNAVAILABLE FOR THIS STREAM")
            }
            .font(.caption2.bold())
            .foregroundStyle(.white)
            .padding(.horizontal, 10)
            .padding(.vertical, 7)
            .background(.black.opacity(0.72), in: Capsule())
            .padding(.top, 12)
            .padding(.leading, 12)""", """            VideoPlayer(player: mediaPlayer.player)
                .background(.black)
                .ignoresSafeArea()
            VStack(alignment: .leading, spacing: 8) {
                HStack(spacing: 6) {
                    Image(systemName: "waveform")
                    Text(mediaPlayer.playbackError != nil ? "PLAYBACK FAILED" : (mediaPlayer.equalizerActive ? "TRAPTUBE EQ ACTIVE" : "EQ UNAVAILABLE FOR THIS STREAM"))
                }
                .font(.caption2.bold())
                .foregroundStyle(.white)
                .padding(.horizontal, 10)
                .padding(.vertical, 7)
                .background(.black.opacity(0.72), in: Capsule())
                if let playbackError = mediaPlayer.playbackError {
                    Text(playbackError)
                        .font(.caption.weight(.semibold)).foregroundStyle(.white)
                        .padding(.horizontal, 10).padding(.vertical, 7)
                        .background(Color(hex: "5A1019").opacity(0.9), in: RoundedRectangle(cornerRadius: 9))
                }
            }
            .padding(.top, 12)
            .padding(.leading, 12)""",
        "round5 downloaded player error surface")
p.write_text(s)

# --- Round 6: native player crash-proofing, EQ button opens the
# native player directly, downloads HTTP 403 ranged fallback --------
# Crash audit of the Round 5 native stream player path (the app died
# while the badge read RESOLVING...):
#  (a) makePlayerItem built its AVMutableComposition insert ranges
#      from the assets' reported durations. An asset's duration can
#      exceed its own track's timeRange, and inserting a range past
#      the end of a track raises inside AVFoundation instead of
#      throwing a Swift error - a hard crash in the middle of
#      resolving, uncapturable by do/catch. Fixed by construction:
#      insert ranges now come from each track's OWN loaded timeRange,
#      clamped to the shorter track, so an out-of-bounds insert is
#      impossible, and every failure lands in PLAYBACK FAILED.
#  (b) The start task checked cancellation only after the item was
#      built and awaited the EQ attach inline (no separate task to
#      cancel; an attach completing after dismissal could still
#      publish). Fixed to the downloaded player's pattern: checks
#      after every await, attach in its own task under the generation
#      token + current-item identity, stop() cancels both tasks and
#      invalidates the single status observation exactly once.
#  (c) TrapTubeInnerTube.cachedVisitorData was unsynchronized shared
#      mutable state while fetchInfo is called concurrently (mod
#      sheet, download sheet, download-later queue, native player) -
#      a data race on a String, i.e. memory corruption when two
#      first-fetches overlap. Now lock-guarded.
#  (d) Presentation: both native-player entry points presented a
#      fullScreenCover from INSIDE a sheet. Presentation is unified
#      at the host level through TrapTubeNativePlayCenter; sheets
#      dismiss first and the center defers until the dismissal lands.
# EQ button: the injected EQ button (script message + traptube-eq://
# fallback) now carries the video id and playback position and lands
# in TrapTubeNativePlayRouter, which opens the current video
# DIRECTLY in the native player (page video paused, position carried
# over). The stream EQ sheet remains only as the fallback when no
# video id is known, and its banner's native-player button is now
# always offered when a video is playing on that host.
# Downloads 403 audit: the header flow was already correct end to
# end (fetchInfo stamps every format with its minting profile's user
# agent; the sheet, Download later and the manager pass it through;
# TrapTubeDirectDownloader sends that UA + Referer; FFmpeg only ever
# reads local temp files, never URLs). What differs from the fetch
# path that googlevideo accepts (AVPlayer) is the request SHAPE: a
# plain full-file GET. The downloader now falls back on HTTP 403 to
# ranged chunk fetching with the exact AVPlayer header shape (same
# UA + Referer + Range on every chunk), and reports the failing host
# if both strategies are refused.
p = file("YouTubeView.swift")
s = p.read_text()

# (c) visitor-data cache lock (write site first, so the declaration
# rep's helper bodies can't make the write pattern ambiguous).
s = rep(s, r'''        cachedVisitorData = value''', r'''        storeVisitor(value)''',
        "round6 visitor store call")
s = rep(s, r'''        if let cachedVisitorData { return cachedVisitorData }''', r'''        if let cached = cachedVisitor() { return cached }''',
        "round6 visitor read call")
s = rep(s, r'''    private static var cachedVisitorData: String?''', r'''    private static var cachedVisitorData: String?
    // Round 6: fetchInfo runs concurrently (mod sheet, download
    // sheet, download-later queue, native player); the visitor cache
    // is shared mutable state and is now lock-guarded.
    private static let visitorDataLock = NSLock()

    private static func cachedVisitor() -> String? {
        visitorDataLock.lock()
        defer { visitorDataLock.unlock() }
        return cachedVisitorData
    }

    private static func storeVisitor(_ value: String) {
        visitorDataLock.lock()
        cachedVisitorData = value
        visitorDataLock.unlock()
    }''',
        "round6 visitor lock")

# EQ button payload: video id + position on both channels.
s = rep(s, r'''          function fireEQ() {
            if (!post("trapTubeEQ", { action: "open" })) {
              try { window.location.href = "traptube-eq://open"; } catch (e) {}
            }
          }''', r'''          function fireEQ() {
            var id = currentVideoID();
            var t = 0;
            try {
              var v = document.querySelector("#movie_player video") || document.querySelector("video");
              if (v && isFinite(v.currentTime)) t = Math.floor(v.currentTime);
            } catch (e) {}
            if (!post("trapTubeEQ", { action: "open", videoID: id || "", startAt: t })) {
              try { window.location.href = "traptube-eq://open?v=" + encodeURIComponent(id || "") + "&t=" + t; } catch (e) {}
            }
          }''',
        "round6 fireEQ payload")

# Session: the scheme fallback lands in the same router, and the
# session gains a pause for the page video.
s = rep(s, r'''        if scheme == "traptube-eq" {
            TrapTubeWebEQCenter.shared.present(host: host(for: webView))
            return true
        }''', r'''        if scheme == "traptube-eq" {
            // Round 6: the fallback channel carries the video id and
            // position too, and lands in the same router as the
            // script-message channel.
            let items = URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems ?? []
            let videoID = items.first { $0.name == "v" }?.value
            let startAt = items.first { $0.name == "t" }?.value.flatMap { Double($0) } ?? 0
            TrapTubeNativePlayRouter.openEQ(host: host(for: webView), videoID: videoID, startAt: startAt)
            return true
        }''',
        "round6 scheme eq route")
s = rep(s, r'''    func closeMini() {''', r'''    /// Round 6: opening the native player pauses the page video so
    /// the two never play over each other.
    func pauseWatchVideo(for host: TrapTubeHostTab) {
        webViews[host]?.evaluateJavaScript("(() => { var v = document.querySelector('video'); if (v && !v.paused) v.pause(); })()")
        if watchHost == host { watchIsPlaying = false }
    }

    func closeMini() {''',
        "round6 session pause")

# Script handler: EQ open routes to the native player.
s = rep(s, r'''        if (body["action"] as? String) == "open" {
            TrapTubeWebEQCenter.shared.present(host: host)
        }''', r'''        if (body["action"] as? String) == "open" {
            // Round 6: the EQ button opens the current video in the
            // native TrapTube player with the EQ attached; the router
            // falls back to the WebEQ sheet only when no video id is
            // known for this surface.
            let videoID = body["videoID"] as? String
            let startAt = (body["startAt"] as? NSNumber)?.doubleValue ?? 0
            TrapTubeNativePlayRouter.openEQ(host: host, videoID: videoID, startAt: startAt)
        }''',
        "round6 eq handler route")

# Mod sheet: native play goes through the shared center (this sheet
# dismisses first); the in-sheet cover and its state go away.
s = rep(s, r'''    @State private var showPlayOptions = false
    @State private var playItem: TrapTubeDownloadedMedia?
    @State private var nativePlay: TrapTubeNativePlayRequest?''', r'''    @State private var showPlayOptions = false
    @State private var playItem: TrapTubeDownloadedMedia?''',
        "round6 mod sheet state")
s = rep(s, r'''                        modRow("TrapTube Player (EQ)", detail: "Stream it now with the 16-band EQ", icon: "waveform") {
                            nativePlay = TrapTubeNativePlayRequest(videoID: request.videoID, title: displayTitle)
                        }''', r'''                        modRow("TrapTube Player (EQ)", detail: "Stream it now with the 16-band EQ", icon: "waveform") {
                            // Round 6: unified host-level
                            // presentation - dismiss this sheet and
                            // let the shared center present the player.
                            let videoID = request.videoID
                            let title = displayTitle
                            dismiss()
                            TrapTubeNativePlayCenter.shared.present(videoID: videoID, title: title, afterSheetDismissal: true)
                        }''',
        "round6 mod sheet native row")
s = rep(s, r'''        .sheet(item: $playItem) { item in
            TrapTubeDownloadedVideoPlayer(item: item)
                .preferredColorScheme(.dark)
        }
        .fullScreenCover(item: $nativePlay) { playRequest in
            TrapTubeNativeStreamPlayer(request: playRequest)
                .preferredColorScheme(.dark)
        }
    }''', r'''        .sheet(item: $playItem) { item in
            TrapTubeDownloadedVideoPlayer(item: item)
                .preferredColorScheme(.dark)
        }
    }''',
        "round6 mod sheet cover removed")

# Stream EQ sheet: same unification, and the native-player button is
# the main call to action whenever a video plays on this host.
s = rep(s, r'''    @ObservedObject private var playerSession = TrapTubePlayerSession.shared
    @State private var nativePlay: TrapTubeNativePlayRequest?''', r'''    @ObservedObject private var playerSession = TrapTubePlayerSession.shared''',
        "round6 eq sheet state")
s = rep(s, r'''        .presentationDetents([.large])
        .onAppear { TrapTubePlayerSession.shared.requestEQStatus(for: host) }
        .fullScreenCover(item: $nativePlay) { playRequest in
            TrapTubeNativeStreamPlayer(request: playRequest)
                .preferredColorScheme(.dark)
        }
    }''', r'''        .presentationDetents([.large])
        .onAppear { TrapTubePlayerSession.shared.requestEQStatus(for: host) }
    }''',
        "round6 eq sheet cover removed")
s = rep(s, r'''                if (state == "bypassed" || state == "error"),
                   playerSession.watchHost == host, let videoID = playerSession.watchVideoID {
                    Button {
                        nativePlay = TrapTubeNativePlayRequest(videoID: videoID, title: playerSession.watchTitle)
                    } label: {''', r'''                if playerSession.watchHost == host, let videoID = playerSession.watchVideoID {
                    // Round 6: the native player is this sheet's main
                    // call to action whenever a video is playing on
                    // this host - it is where the EQ always attaches.
                    Button {
                        dismiss()
                        TrapTubeNativePlayCenter.shared.present(videoID: videoID, title: playerSession.watchTitle, afterSheetDismissal: true)
                    } label: {''',
        "round6 eq sheet native button")

# Hosts: both present the native player from the shared center.
s = rep(s, r'''    @ObservedObject private var homeEQCenter = TrapTubeWebEQCenter.shared''', r'''    @ObservedObject private var homeEQCenter = TrapTubeWebEQCenter.shared
    @ObservedObject private var homeNativePlayCenter = TrapTubeNativePlayCenter.shared''',
        "round6 home center")
s = rep(s, r'''        .sheet(item: $homeEQCenter.activeRequest) { request in
            TrapTubeWebEQSheet(host: request.host)
                .environmentObject(theme)
        }''', r'''        .sheet(item: $homeEQCenter.activeRequest) { request in
            TrapTubeWebEQSheet(host: request.host)
                .environmentObject(theme)
        }
        .fullScreenCover(item: $homeNativePlayCenter.activeRequest) { playRequest in
            TrapTubeNativeStreamPlayer(request: playRequest)
                .preferredColorScheme(.dark)
        }''',
        "round6 home native cover")
s = rep(s, r'''    @ObservedObject private var modCenter = TrapTubeModCenter.shared
    @ObservedObject private var eqCenter = TrapTubeWebEQCenter.shared''', r'''    @ObservedObject private var modCenter = TrapTubeModCenter.shared
    @ObservedObject private var eqCenter = TrapTubeWebEQCenter.shared
    @ObservedObject private var nativePlayCenter = TrapTubeNativePlayCenter.shared''',
        "round6 account center")
s = rep(s, r'''        .sheet(item: $eqCenter.activeRequest) { request in
            TrapTubeWebEQSheet(host: request.host)
                .environmentObject(theme)
        }''', r'''        .sheet(item: $eqCenter.activeRequest) { request in
            TrapTubeWebEQSheet(host: request.host)
                .environmentObject(theme)
        }
        .fullScreenCover(item: $nativePlayCenter.activeRequest) { playRequest in
            TrapTubeNativeStreamPlayer(request: playRequest)
                .preferredColorScheme(.dark)
        }''',
        "round6 account native cover")

# The native player block itself: truncate the Round 5 block (it is
# the last thing in this file) and append the Round 6 version.
ROUND6_NATIVE_PLAYER_SWIFT = r'''

// MARK: - Round 6 native stream player (crash-proofed) + presentation
//
// Round 6 audit of the Round 5 player (the app crashed while the
// badge read RESOLVING...):
//  (a) makePlayerItem built its AVMutableComposition insert ranges
//      from the assets' reported durations. An asset's duration can
//      exceed its own track's timeRange, and inserting a range past
//      the end of a track raises inside AVFoundation instead of
//      throwing a Swift error - a hard crash mid-resolve. The ranges
//      now come from each track's OWN loaded timeRange, clamped to
//      the shorter track, so an out-of-bounds insert is impossible
//      by construction and every failure lands in PLAYBACK FAILED.
//  (b) The start task checked cancellation once and awaited the EQ
//      attach inline. It now checks cancellation/generation after
//      every await and attaches in a separate task - the exact
//      pattern the Round 5 downloaded-file player was hardened to -
//      and stop() cancels both tasks and invalidates the single
//      status observation exactly once.
//  (c) Presentation is unified through TrapTubeNativePlayCenter:
//      both tab hosts present the player; no sheet presents it from
//      inside itself anymore.

struct TrapTubeNativePlayRequest: Identifiable {
    let videoID: String
    let title: String
    var startAt: TimeInterval = 0
    var id: String { videoID }
}

/// The single presentation path for the native player. Both watch
/// hosts observe this center and present the player as a full-screen
/// cover; the mod sheet, the stream EQ sheet and the in-player EQ
/// button all land here.
final class TrapTubeNativePlayCenter: ObservableObject {
    static let shared = TrapTubeNativePlayCenter()
    @Published var activeRequest: TrapTubeNativePlayRequest?
    private var pendingPresent: DispatchWorkItem?
    private init() {}

    /// When the caller is a sheet it dismisses itself first and the
    /// presentation is deferred briefly so the dismissal completes -
    /// a cover presented over a still-dismissing sheet can be
    /// dropped by SwiftUI's presentation machinery.
    func present(videoID: String, title: String, startAt: TimeInterval = 0, afterSheetDismissal: Bool = false) {
        let request = TrapTubeNativePlayRequest(videoID: videoID, title: title, startAt: startAt)
        DispatchQueue.main.async {
            self.pendingPresent?.cancel()
            if afterSheetDismissal {
                let work = DispatchWorkItem { [weak self] in self?.activeRequest = request }
                self.pendingPresent = work
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.45, execute: work)
            } else {
                self.activeRequest = request
            }
        }
    }
}

enum TrapTubeNativePlayRouter {
    /// The in-player EQ button's intent: open the page's current
    /// video in the native TrapTube player with the EQ attached.
    /// Falls back to the stream EQ sheet only when no video id is
    /// known for the tapped surface.
    static func openEQ(host: TrapTubeHostTab?, videoID: String?, startAt: TimeInterval) {
        let session = TrapTubePlayerSession.shared
        var resolvedID = (videoID?.isEmpty == false) ? videoID : nil
        if resolvedID == nil, let host, session.watchHost == host {
            resolvedID = session.watchVideoID
        }
        if let host, let resolvedID {
            // The native player takes over the audio; pause the page
            // video so the two never play over each other.
            session.pauseWatchVideo(for: host)
            TrapTubeNativePlayCenter.shared.present(videoID: resolvedID, title: session.watchTitle, startAt: startAt)
        } else {
            TrapTubeWebEQCenter.shared.present(host: host)
        }
    }
}

@MainActor
final class TrapTubeNativeStreamPlayerModel: ObservableObject {
    enum Phase {
        case resolving
        case playing
        case failed(String)
    }

    let player = AVPlayer()
    @Published private(set) var phase: Phase = .resolving
    @Published private(set) var equalizerActive = false
    @Published private(set) var eqAttachFinished = false

    private var startTask: Task<Void, Never>?
    private var attachTask: Task<Void, Never>?
    private var statusObservation: NSKeyValueObservation?
    private var currentItem: AVPlayerItem?
    private var generation = 0

    func start(videoID: String, startAt: TimeInterval = 0) {
        guard startTask == nil else { return }
        try? AVAudioSession.sharedInstance().setCategory(.playback, mode: .moviePlayback, options: [.allowAirPlay, .allowBluetoothA2DP])
        try? AVAudioSession.sharedInstance().setActive(true)
        let startGeneration = generation
        startTask = Task { [weak self] in
            guard let self else { return }
            do {
                let info = try await TrapTubeInnerTube.fetchInfo(videoID: videoID)
                guard !Task.isCancelled, self.generation == startGeneration else { return }
                let item = try await Self.makePlayerItem(info: info)
                guard !Task.isCancelled, self.generation == startGeneration else { return }
                self.currentItem = item
                self.statusObservation = item.observe(\.status, options: [.new]) { [weak self] observedItem, _ in
                    guard observedItem.status == .failed else { return }
                    let message = observedItem.error?.localizedDescription ?? "The stream failed to load."
                    Task { @MainActor in self?.phase = .failed(message) }
                }
                self.player.replaceCurrentItem(with: item)
                self.phase = .playing
                if startAt > 5 {
                    // Pick up roughly where the page video left off;
                    // AVPlayer queues the seek until the item is ready.
                    self.player.seek(to: CMTime(seconds: startAt, preferredTimescale: 600),
                                     toleranceBefore: CMTime(seconds: 2, preferredTimescale: 600),
                                     toleranceAfter: .zero)
                }
                self.player.play()
                // The EQ tap attaches alongside playback in its own
                // task (the downloaded player's pattern): it never
                // gates playback, and stop() can cancel it cleanly.
                self.attachTask = Task { [weak self] in
                    let attached = await TrapTubeTapEQ.shared.attach(to: item)
                    guard let self, self.generation == startGeneration, self.currentItem === item else { return }
                    self.equalizerActive = attached
                    self.eqAttachFinished = true
                }
            } catch {
                if !Task.isCancelled, self.generation == startGeneration {
                    self.phase = .failed(error.localizedDescription)
                }
            }
        }
    }

    func stop() {
        generation += 1
        startTask?.cancel()
        startTask = nil
        attachTask?.cancel()
        attachTask = nil
        statusObservation?.invalidate()
        statusObservation = nil
        currentItem = nil
        player.pause()
        player.replaceCurrentItem(with: nil)
        equalizerActive = false
        eqAttachFinished = false
    }

    /// Muxed MP4 when YouTube offers one; otherwise an AVC + AAC
    /// composition built from the adaptive streams (the same pairing
    /// the download merge uses).
    private static func makePlayerItem(info: TrapTubeVideoInfo) async throws -> AVPlayerItem {
        if let muxed = info.muxed.first, let url = URL(string: muxed.url) {
            let asset = AVURLAsset(url: url, options: headerOptions(userAgent: muxed.userAgent.isEmpty ? info.userAgent : muxed.userAgent))
            return AVPlayerItem(asset: asset)
        }
        guard let video = info.adaptiveVideo.first(where: { $0.isAVCVideo }),
              let audio = info.audioOnly.first(where: { $0.isAACAudio }),
              let videoURL = URL(string: video.url),
              let audioURL = URL(string: audio.url) else {
            throw TrapTubeModError.unplayable("no stream this player can use (it needs a muxed MP4 or an AVC + AAC pair)")
        }
        let videoAsset = AVURLAsset(url: videoURL, options: headerOptions(userAgent: video.userAgent.isEmpty ? info.userAgent : video.userAgent))
        let audioAsset = AVURLAsset(url: audioURL, options: headerOptions(userAgent: audio.userAgent.isEmpty ? info.userAgent : audio.userAgent))
        guard let videoTrack = try await videoAsset.loadTracks(withMediaType: .video).first,
              let audioTrack = try await audioAsset.loadTracks(withMediaType: .audio).first else {
            throw TrapTubeModError.unplayable("the adaptive streams had no usable tracks")
        }
        // Round 6 defensive composition: the insert ranges are built
        // from each track's OWN loaded timeRange and clamped to the
        // shorter track - never from the assets' reported durations,
        // which can exceed a track's real range and make AVFoundation
        // raise (crash) instead of throwing. By construction each
        // insert range lies inside its track's timeRange.
        let videoRange = try await videoTrack.load(.timeRange)
        let audioRange = try await audioTrack.load(.timeRange)
        let target = CMTimeMinimum(videoRange.duration, audioRange.duration)
        guard videoRange.isValid, audioRange.isValid,
              target.isValid, target.isNumeric, target.seconds > 0 else {
            throw TrapTubeModError.unplayable("the adaptive streams reported no usable timeline")
        }
        let composition = AVMutableComposition()
        guard let compositionVideo = composition.addMutableTrack(withMediaType: .video, preferredTrackID: kCMPersistentTrackID_Invalid),
              let compositionAudio = composition.addMutableTrack(withMediaType: .audio, preferredTrackID: kCMPersistentTrackID_Invalid) else {
            throw TrapTubeModError.unplayable("could not build the playback composition")
        }
        do {
            try compositionVideo.insertTimeRange(CMTimeRange(start: videoRange.start, duration: target), of: videoTrack, at: .zero)
            try compositionAudio.insertTimeRange(CMTimeRange(start: audioRange.start, duration: target), of: audioTrack, at: .zero)
        } catch {
            throw TrapTubeModError.unplayable("could not assemble the video and audio streams (\(error.localizedDescription))")
        }
        if let transform = try? await videoTrack.load(.preferredTransform) {
            compositionVideo.preferredTransform = transform
        }
        return AVPlayerItem(asset: composition)
    }

    private static func headerOptions(userAgent: String) -> [String: Any] {
        ["AVURLAssetHTTPHeaderFieldsKey": ["User-Agent": userAgent, "Referer": "https://www.youtube.com/"]]
    }
}

struct TrapTubeNativeStreamPlayer: View {
    let request: TrapTubeNativePlayRequest

    @Environment(\.dismiss) private var dismiss
    @EnvironmentObject private var audio: AudioEngineManager
    @EnvironmentObject private var theme: ThemeManager
    @StateObject private var model = TrapTubeNativeStreamPlayerModel()
    @State private var showEqualizer = false

    var body: some View {
        ZStack(alignment: .topLeading) {
            Color.black.ignoresSafeArea()
            VideoPlayer(player: model.player)
                .background(.black)
                .ignoresSafeArea()

            VStack(alignment: .leading, spacing: 8) {
                HStack(spacing: 8) {
                    HStack(spacing: 6) {
                        Image(systemName: "waveform")
                        Text(badgeText)
                    }
                    .font(.caption2.bold())
                    .foregroundStyle(.white)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 7)
                    .background(.black.opacity(0.72), in: Capsule())
                    Spacer()
                    Button {
                        showEqualizer = true
                    } label: {
                        Label("EQ", systemImage: "slider.horizontal.3")
                            .font(.caption.bold()).foregroundStyle(.white)
                            .padding(.horizontal, 11).padding(.vertical, 8)
                            .background(.black.opacity(0.72), in: Capsule())
                    }
                    .accessibilityLabel("Open the equalizer")
                    Button {
                        dismiss()
                    } label: {
                        Image(systemName: "xmark")
                            .font(.caption.bold()).foregroundStyle(.white)
                            .frame(width: 30, height: 30)
                            .background(.black.opacity(0.72), in: Circle())
                    }
                    .accessibilityLabel("Close player")
                }
                if !request.title.isEmpty {
                    Text(request.title)
                        .font(.caption.weight(.semibold)).foregroundStyle(.white)
                        .lineLimit(2)
                        .padding(.horizontal, 10).padding(.vertical, 6)
                        .background(.black.opacity(0.55), in: RoundedRectangle(cornerRadius: 9))
                }
            }
            .padding(.top, 12)
            .padding(.horizontal, 12)

            if case .resolving = model.phase {
                VStack(spacing: 12) {
                    ProgressView().tint(.white)
                    Text("Resolving stream…").font(.subheadline.weight(.semibold)).foregroundStyle(.white.opacity(0.85))
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            }

            if case .failed(let message) = model.phase {
                VStack(spacing: 12) {
                    Image(systemName: "exclamationmark.triangle.fill").font(.title2).foregroundStyle(Color(hex: "FF7A84"))
                    Text(message).font(.subheadline).foregroundStyle(.white)
                        .multilineTextAlignment(.center)
                        .fixedSize(horizontal: false, vertical: true)
                    Button("Close") { dismiss() }
                        .font(.subheadline.bold()).foregroundStyle(.white)
                        .padding(.horizontal, 16).padding(.vertical, 9)
                        .background(.white.opacity(0.12), in: Capsule())
                }
                .padding(24)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(.black.opacity(0.66))
            }
        }
        .background(.black)
        .task { model.start(videoID: request.videoID, startAt: request.startAt) }
        .onDisappear { model.stop() }
        .onChange(of: audio.eqGains) { _, _ in TrapTubeTapEQ.shared.update(gains: audio.eqGains, bass: audio.bassBoost, master: audio.masterGain) }
        .onChange(of: audio.bassBoost) { _, _ in TrapTubeTapEQ.shared.update(gains: audio.eqGains, bass: audio.bassBoost, master: audio.masterGain) }
        .onChange(of: audio.masterGain) { _, _ in TrapTubeTapEQ.shared.update(gains: audio.eqGains, bass: audio.bassBoost, master: audio.masterGain) }
        .sheet(isPresented: $showEqualizer) {
            EqualizerView().environmentObject(audio).environmentObject(theme).presentationDetents([.large])
        }
    }

    private var badgeText: String {
        switch model.phase {
        case .resolving: return "RESOLVING…"
        case .failed: return "PLAYBACK FAILED"
        case .playing:
            if !model.eqAttachFinished { return "EQ ATTACHING…" }
            return model.equalizerActive ? "TRAPTUBE EQ ACTIVE" : "EQ UNAVAILABLE FOR THIS STREAM"
        }
    }
}
'''
if "Round 6 native stream player (crash-proofed)" not in s:
    r6_marker = "\n// MARK: - Round 5 native stream player"
    if r6_marker not in s:
        raise SystemExit("round6 native player anchor missing")
    s = s[:s.index(r6_marker)] + ROUND6_NATIVE_PLAYER_SWIFT + "\n"
p.write_text(s)

# Downloads: ranged fallback inside TrapTubeDirectDownloader.
p = file("TypeTypeService.swift")
s = p.read_text()
s = rep(s, r'''enum TrapTubeDirectDownloadError: LocalizedError {
    case badStatus(Int)
    case emptyDownload''', r'''enum TrapTubeDirectDownloadError: LocalizedError {
    case badStatus(Int)
    case badStatusForHost(Int, String)
    case emptyDownload''',
        "round6 download error host case")
s = rep(s, r'''        case .badStatus(let code):
            return "The download server returned HTTP \(code)."''', r'''        case .badStatus(let code):
            return "The download server returned HTTP \(code)."
        case .badStatusForHost(let code, let host):
            return "The download server returned HTTP \(code) (host: \(host))."''',
        "round6 download error host text")
ROUND6_DOWNLOAD_FUNC = r'''    func download(from url: URL, userAgent: String?, onProgress: @escaping (Double) -> Void) async throws -> URL {
        // Round 6: two strategies. The plain download task is the
        // fast path. If googlevideo refuses it with HTTP 403, fall
        // back to fetching the file in ranged chunks with the exact
        // header shape AVPlayer uses for these URLs - the minting
        // profile's User-Agent + Referer + a Range on every chunk.
        do {
            return try await downloadWhole(url: url, userAgent: userAgent, onProgress: onProgress)
        } catch TrapTubeDirectDownloadError.badStatus(let code) where code == 403 {
            do {
                return try await downloadInChunks(url: url, userAgent: userAgent, onProgress: onProgress)
            } catch let chunkError as TrapTubeDirectDownloadError {
                if case .badStatus(let chunkCode) = chunkError {
                    throw TrapTubeDirectDownloadError.badStatusForHost(chunkCode, url.host ?? "unknown host")
                }
                throw chunkError
            }
        }
    }

    private func downloadWhole(url: URL, userAgent: String?, onProgress: @escaping (Double) -> Void) async throws -> URL {
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

    /// Ranged fallback: sequential chunks appended to one temp file.
    /// A 200 answer to a ranged request means the server ignored the
    /// Range header and sent the whole file - that body IS the file.
    private func downloadInChunks(url: URL, userAgent: String?, onProgress: @escaping (Double) -> Void) async throws -> URL {
        let chunkSize: Int64 = 8 * 1024 * 1024
        let destination = FileManager.default.temporaryDirectory
            .appendingPathComponent("tt-direct-\(UUID().uuidString)-chunked.bin")
        FileManager.default.createFile(atPath: destination.path, contents: nil)
        let handle = try FileHandle(forWritingTo: destination)
        defer { try? handle.close() }
        var offset: Int64 = 0
        var total: Int64 = -1
        do {
            while total < 0 || offset < total {
                var request = URLRequest(url: url)
                if let ua = userAgent, !ua.isEmpty {
                    request.setValue(ua, forHTTPHeaderField: "User-Agent")
                }
                request.setValue("https://www.youtube.com/", forHTTPHeaderField: "Referer")
                let end = offset + chunkSize - 1
                request.setValue("bytes=\(offset)-\(end)", forHTTPHeaderField: "Range")
                let (data, response) = try await URLSession.shared.data(for: request)
                guard let http = response as? HTTPURLResponse else {
                    throw TrapTubeDirectDownloadError.badStatus(-1)
                }
                if http.statusCode == 200 {
                    if offset == 0 {
                        try handle.write(contentsOf: data)
                        offset = Int64(data.count)
                        total = offset
                        break
                    }
                    throw TrapTubeDirectDownloadError.badStatus(http.statusCode)
                }
                guard http.statusCode == 206 else {
                    throw TrapTubeDirectDownloadError.badStatus(http.statusCode)
                }
                if total < 0, let rangeHeader = http.value(forHTTPHeaderField: "Content-Range"),
                   let slash = rangeHeader.lastIndex(of: "/"),
                   let parsed = Int64(rangeHeader[rangeHeader.index(after: slash)...]) {
                    total = parsed
                }
                if data.isEmpty { break }
                try handle.write(contentsOf: data)
                offset += Int64(data.count)
                if total > 0 { onProgress(min(1, Double(offset) / Double(total))) }
            }
        } catch {
            try? FileManager.default.removeItem(at: destination)
            throw error
        }
        guard offset > 0 else {
            try? FileManager.default.removeItem(at: destination)
            throw TrapTubeDirectDownloadError.emptyDownload
        }
        onProgress(1)
        return destination
    }

'''
s = splice_between(s, "    func download(from url: URL, userAgent: String?, onProgress: @escaping (Double) -> Void) async throws -> URL {",
                   "    func urlSession(_ session: URLSession, downloadTask: URLSessionDownloadTask,",
                   ROUND6_DOWNLOAD_FUNC, "round6 downloader strategies")
# A 416 to a chunk past the end (when the server never sent a
# Content-Range total) means the file is already complete.
s = rep(s, r'''                guard http.statusCode == 206 else {
                    throw TrapTubeDirectDownloadError.badStatus(http.statusCode)
                }''', r'''                guard http.statusCode == 206 else {
                    if http.statusCode == 416, offset > 0 { break }
                    throw TrapTubeDirectDownloadError.badStatus(http.statusCode)
                }''',
        "round6 chunk 416 completion")
p.write_text(s)


# ------------------------------------------------------------------
# Round 7: Musi-style native stream player.
#
# The native stream player becomes the primary way to watch, modeled
# on the user's Musi screen recording (see musi-player-reference.md):
# a persistent session owns the AVPlayer + queue (watch-next "Mix"),
# collapse leaves a mini bar in RootView, and the player's EQ sheet
# is the Musi "Settings" sheet - enable/bypass toggle, 10 vertical
# band sliders mapped onto the real 16-band model, named presets
# that jump the sliders, reset, save-your-own.
#
# Invariants kept: Round 6's crash-proofed composition + lifecycle
# (generation tokens, clamped ranges, PLAYBACK FAILED surfacing),
# the EQ button -> native player routing, downloads behavior.
# Base fix carried here (Round 6 CI #399): the startAt seek used the
# async seek variant without await; every seek in this round uses
# the completionHandler variant.

# (a) TrapTubeTapEQ: a real enable/bypass flag for the render path.
# A 19th shared value slot carries "enabled"; when 0 the tap leaves
# the buffers untouched (true passthrough) while gains stay stored.
p = file("AudioEngineManager.swift")
s = p.read_text()
s = rep(s, r'''        values = .allocate(capacity: 18); values.initialize(repeating: 0, count: 18)
        values[17] = 1''', r'''        values = .allocate(capacity: 19); values.initialize(repeating: 0, count: 19)
        values[17] = 1
        values[18] = UserDefaults.standard.object(forKey: "TrapTube.EQ.Enabled") as? Bool ?? true ? 1 : 0''',
        "round7 tap values capacity")
s = rep(s, r'''        destination.update(from: values, count: 18)''',
        r'''        destination.update(from: values, count: 19)''',
        "round7 tap copy count")
s = rep(s, r'''    /// Render-thread read. Returns false (keep the previous settings) if the lock is busy.
    fileprivate func copyValues(into destination: UnsafeMutablePointer<Float>) -> UInt64? {''',
        r'''    /// Round 7: the player's EQ sheet enable toggle. Persisted;
    /// the render callback reads slot 18 and passes audio through
    /// untouched while it is 0 (true bypass - gains stay stored and
    /// return when re-enabled).
    var isEnabled: Bool {
        UserDefaults.standard.object(forKey: "TrapTube.EQ.Enabled") as? Bool ?? true
    }

    func setEnabled(_ enabled: Bool) {
        UserDefaults.standard.set(enabled, forKey: "TrapTube.EQ.Enabled")
        os_unfair_lock_lock(lock)
        values[18] = enabled ? 1 : 0
        version &+= 1
        os_unfair_lock_unlock(lock)
    }

    /// Render-thread read. Returns false (keep the previous settings) if the lock is busy.
    fileprivate func copyValues(into destination: UnsafeMutablePointer<Float>) -> UInt64? {''',
        "round7 tap enable api")
s = rep(s, r'''        let newSnapshot = UnsafeMutablePointer<Float>.allocate(capacity: 18)
        newSnapshot.initialize(repeating: 0, count: 18)
        newSnapshot[17] = 1''', r'''        let newSnapshot = UnsafeMutablePointer<Float>.allocate(capacity: 19)
        newSnapshot.initialize(repeating: 0, count: 19)
        newSnapshot[17] = 1
        newSnapshot[18] = 1''',
        "round7 tap snapshot capacity")
s = rep(s, r'''            preamp = snapshot[17]
            appliedVersion = version
        }
        var gain = preamp''', r'''            preamp = snapshot[17]
            appliedVersion = version
        }
        // Round 7: EQ disabled from the player sheet - leave the
        // buffers exactly as the source delivered them.
        if snapshot[18] < 0.5 { return }
        var gain = preamp''',
        "round7 tap bypass")
p.write_text(s)

# (b) YouTubeView.swift: watch-next for the queue, favorites in the
# downloads view, host-level covers moved to RootView (done in (c)).
p = file("YouTubeView.swift")
s = p.read_text()
s = rep(s, r'''    private static func playerResponse(videoID: String, profile: ClientProfile) async throws -> [String: Any] {''',
        r'''    /// Round 7: watch-next recommendations - the native player's
    /// queue (the "YouTube Mix" in the reference recording). Uses
    /// the ANDROID profile against the /next endpoint and walks the
    /// response for compactVideoRenderer entries. Best-effort by
    /// design: any failure returns an empty list and the player's
    /// queue stays a single video.
    static func fetchRelated(videoID: String) async -> [TrapTubeQueueItem] {
        let profile = profiles[0]
        var client = profile.client
        if let visitor = await fetchVisitorData() { client["visitorData"] = visitor }
        let body: [String: Any] = ["context": ["client": client], "videoId": videoID,
                                   "racyCheckOk": true, "contentCheckOk": true]
        guard let url = URL(string: "https://www.youtube.com/youtubei/v1/next?key=\(profile.apiKey)&prettyPrint=false"),
              let bodyData = try? JSONSerialization.data(withJSONObject: body) else { return [] }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(profile.userAgent, forHTTPHeaderField: "User-Agent")
        request.httpBody = bodyData
        guard let (data, _) = try? await URLSession.shared.data(for: request),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return [] }
        var results: [TrapTubeQueueItem] = []
        var seen: Set<String> = [videoID]
        collectRelated(json, into: &results, seen: &seen)
        return Array(results.prefix(25))
    }

    private static func collectRelated(_ node: Any, into results: inout [TrapTubeQueueItem], seen: inout Set<String>) {
        if results.count >= 25 { return }
        if let dict = node as? [String: Any] {
            if let renderer = dict["compactVideoRenderer"] as? [String: Any],
               let id = renderer["videoId"] as? String, !id.isEmpty, !seen.contains(id) {
                let title = rendererText(renderer["title"])
                let author = rendererText(renderer["shortBylineText"] ?? renderer["longBylineText"])
                if !title.isEmpty {
                    seen.insert(id)
                    results.append(TrapTubeQueueItem(videoID: id, title: title, channel: author))
                }
            }
            for value in dict.values { collectRelated(value, into: &results, seen: &seen) }
        } else if let list = node as? [Any] {
            for value in list { collectRelated(value, into: &results, seen: &seen) }
        }
    }

    private static func rendererText(_ node: Any?) -> String {
        guard let dict = node as? [String: Any] else { return "" }
        if let simple = dict["simpleText"] as? String { return simple }
        if let runs = dict["runs"] as? [[String: Any]] {
            return runs.compactMap { $0["text"] as? String }.joined()
        }
        return ""
    }

    private static func playerResponse(videoID: String, profile: ClientProfile) async throws -> [String: Any] {''',
        "round7 watch-next fetch")
s = rep(s, r'''    @State private var laterItems: [TrapTubeDownloadLaterItem] = TrapTubeDownloadLaterStore.items''',
        r'''    @State private var laterItems: [TrapTubeDownloadLaterItem] = TrapTubeDownloadLaterStore.items
    @ObservedObject private var favoritesStore = TrapTubeFavoritesStore.shared''',
        "round7 downloads favorites store")
s = rep(s, r'''                                .accessibilityLabel("Remove from Download later")
                            }
                            .padding(12)
                            .background(.white.opacity(0.045), in: RoundedRectangle(cornerRadius: 13))
                        }
                    }
                }

                if !manager.jobs.isEmpty {''',
        r'''                                .accessibilityLabel("Remove from Download later")
                            }
                            .padding(12)
                            .background(.white.opacity(0.045), in: RoundedRectangle(cornerRadius: 13))
                        }
                    }
                }

                if !favoritesStore.items.isEmpty {
                    VStack(alignment: .leading, spacing: 12) {
                        Text("Favorites").font(.headline.bold()).foregroundStyle(.white)
                        ForEach(favoritesStore.items) { entry in
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
                                    Text(entry.channel.isEmpty ? "Saved from the player" : entry.channel)
                                        .font(.caption).foregroundStyle(Color(hex: "A6A4A6")).lineLimit(1)
                                }
                                Spacer(minLength: 4)
                                Button("Play") {
                                    TrapTubeNativePlayCenter.shared.present(videoID: entry.videoID, title: entry.title, contextName: "Favorites")
                                }
                                .font(.caption.bold()).foregroundStyle(Color(hex: "FF7A84"))
                                Button { favoritesStore.remove(videoID: entry.videoID) } label: {
                                    Image(systemName: "trash").foregroundStyle(Color(hex: "A6A4A6"))
                                }
                                .accessibilityLabel("Remove from Favorites")
                            }
                            .padding(12)
                            .background(.white.opacity(0.045), in: RoundedRectangle(cornerRadius: 13))
                        }
                    }
                }

                if !manager.jobs.isEmpty {''',
        "round7 downloads favorites section")
s = rep(s, r'''                if manager.completed.isEmpty && manager.jobs.isEmpty && laterItems.isEmpty {''',
        r'''                if manager.completed.isEmpty && manager.jobs.isEmpty && laterItems.isEmpty && favoritesStore.items.isEmpty {''',
        "round7 downloads empty state")
s = rep(s, """    @ObservedObject private var homeNativePlayCenter = TrapTubeNativePlayCenter.shared
""", "", "round7 home center property")
s = rep(s, """        .fullScreenCover(item: $homeNativePlayCenter.activeRequest) { playRequest in
            TrapTubeNativeStreamPlayer(request: playRequest)
                .preferredColorScheme(.dark)
        }
""", "", "round7 home native cover")
s = rep(s, """    @ObservedObject private var nativePlayCenter = TrapTubeNativePlayCenter.shared
""", "", "round7 account center property")
s = rep(s, """        .fullScreenCover(item: $nativePlayCenter.activeRequest) { playRequest in
            TrapTubeNativeStreamPlayer(request: playRequest)
                .preferredColorScheme(.dark)
        }
""", "", "round7 account native cover")
p.write_text(s)

# (c) RootView.swift: the native player's cover lives here now (one
# presentation host, reachable from every tab), and collapsing the
# player leaves the native mini bar in the bottom inset.
p = file("RootView.swift")
s = p.read_text()
s = rep(s, r'''    @ObservedObject private var webSession = TrapTubePlayerSession.shared''',
        r'''    @ObservedObject private var webSession = TrapTubePlayerSession.shared
    @ObservedObject private var nativePlayCenter = TrapTubeNativePlayCenter.shared
    @ObservedObject private var nativeSession = TrapTubeNativeSession.shared''',
        "round7 root native observers")
s = rep(s, r'''                MiniPlayer { showPlayer = true }
                    .environmentObject(player).environmentObject(theme)''',
        r'''                if nativeSession.hasActiveContent, nativePlayCenter.activeRequest == nil {
                    TrapTubeNativeMiniBar()
                        .environmentObject(theme)
                }
                MiniPlayer { showPlayer = true }
                    .environmentObject(player).environmentObject(theme)''',
        "round7 root native mini bar")
s = rep(s, r'''        .fullScreenCover(isPresented: $showPlayer) {''',
        r'''        .fullScreenCover(item: $nativePlayCenter.activeRequest) { playRequest in
            TrapTubeNativeStreamPlayer(request: playRequest)
                .environmentObject(player).environmentObject(theme)
                .preferredColorScheme(.dark)
        }
        .fullScreenCover(isPresented: $showPlayer) {''',
        "round7 root native cover")
p.write_text(s)

# (d) Replace the Round 6 native player block with the Round 7
# Musi-style player: persistent session + queue, mini bar, EQ sheet.
p = file("YouTubeView.swift")
s = p.read_text()
ROUND7_NATIVE_PLAYER_SWIFT = r'''

// MARK: - Round 7 native stream player (Musi-style) + session
//
// Modeled on the user's Musi screen recording: the native player
// is the primary way to watch. A persistent session owns the
// AVPlayer and the queue, so collapsing the player (chevron) keeps
// playback alive behind the mini bar in RootView. The queue starts
// as the launched video and fills with watch-next recommendations
// (the "YouTube Mix"); playback auto-advances through it. The EQ
// sheet is Musi's "Settings" sheet: enable/bypass toggle, ten
// vertical band sliders mapped exactly onto the 16-band model,
// named presets, reset, save-your-own.
//
// Round 6 invariants kept: composition ranges come from each
// track's OWN loaded timeRange (clamped, guarded, do/catch), the
// generation-token lifecycle, attach-in-own-task, and every failure
// lands in the PLAYBACK FAILED state. All seeks use the
// completionHandler variant (the async variant without await was
// the Round 6 CI #399 build error).

struct TrapTubeQueueItem: Codable, Identifiable, Equatable {
    let videoID: String
    var title: String
    var channel: String
    var id: String { videoID }
}

struct TrapTubeNativePlayRequest: Identifiable {
    let videoID: String
    let title: String
    var startAt: TimeInterval = 0
    var contextName: String = "YouTube"
    var id: String { videoID }
}

/// The single presentation path for the native player. RootView
/// observes this center and presents the player as a full-screen
/// cover; the mod sheet, the stream EQ sheet, the in-player EQ
/// button and the Favorites section all land here.
final class TrapTubeNativePlayCenter: ObservableObject {
    static let shared = TrapTubeNativePlayCenter()
    @Published var activeRequest: TrapTubeNativePlayRequest?
    private var pendingPresent: DispatchWorkItem?
    private init() {}

    /// When the caller is a sheet it dismisses itself first and the
    /// presentation is deferred briefly so the dismissal completes -
    /// a cover presented over a still-dismissing sheet can be
    /// dropped by SwiftUI's presentation machinery.
    func present(videoID: String, title: String, startAt: TimeInterval = 0, contextName: String = "YouTube", afterSheetDismissal: Bool = false) {
        let request = TrapTubeNativePlayRequest(videoID: videoID, title: title, startAt: startAt, contextName: contextName)
        DispatchQueue.main.async {
            self.pendingPresent?.cancel()
            if afterSheetDismissal {
                let work = DispatchWorkItem { [weak self] in self?.activeRequest = request }
                self.pendingPresent = work
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.45, execute: work)
            } else {
                self.activeRequest = request
            }
        }
    }

    /// Mini bar / PiP restore: re-present whatever the persistent
    /// session is playing. begin() no-ops for the already-loaded
    /// video, so playback continues untouched.
    func reopenSession() {
        DispatchQueue.main.async {
            let session = TrapTubeNativeSession.shared
            guard let entry = session.currentEntry else { return }
            let request = TrapTubeNativePlayRequest(videoID: entry.videoID, title: entry.title, contextName: session.contextName)
            self.pendingPresent?.cancel()
            self.activeRequest = request
        }
    }
}

enum TrapTubeNativePlayRouter {
    /// The in-player EQ button's intent: open the page's current
    /// video in the native TrapTube player with the EQ attached.
    /// Falls back to the stream EQ sheet only when no video id is
    /// known for the tapped surface.
    static func openEQ(host: TrapTubeHostTab?, videoID: String?, startAt: TimeInterval) {
        let session = TrapTubePlayerSession.shared
        var resolvedID = (videoID?.isEmpty == false) ? videoID : nil
        if resolvedID == nil, let host, session.watchHost == host {
            resolvedID = session.watchVideoID
        }
        if let host, let resolvedID {
            // The native player takes over the audio; pause the page
            // video so the two never play over each other.
            session.pauseWatchVideo(for: host)
            TrapTubeNativePlayCenter.shared.present(videoID: resolvedID, title: session.watchTitle, startAt: startAt)
        } else {
            TrapTubeWebEQCenter.shared.present(host: host)
        }
    }
}

/// The heart button's store: favorites persist in UserDefaults and
/// surface as a Favorites section in the TrapTube tab, playable in
/// the native player.
final class TrapTubeFavoritesStore: ObservableObject {
    static let shared = TrapTubeFavoritesStore()
    @Published private(set) var items: [TrapTubeQueueItem] = []
    private let defaultsKey = "TrapTube.Favorites"

    private init() {
        if let data = UserDefaults.standard.data(forKey: defaultsKey),
           let decoded = try? JSONDecoder().decode([TrapTubeQueueItem].self, from: data) {
            items = decoded
        }
    }

    func contains(videoID: String) -> Bool { items.contains { $0.videoID == videoID } }

    func toggle(_ item: TrapTubeQueueItem) {
        if contains(videoID: item.videoID) {
            remove(videoID: item.videoID)
        } else {
            items.insert(item, at: 0)
            save()
        }
    }

    func remove(videoID: String) {
        items.removeAll { $0.videoID == videoID }
        save()
    }

    private func save() {
        if let data = try? JSONEncoder().encode(items) {
            UserDefaults.standard.set(data, forKey: defaultsKey)
        }
    }
}

struct TrapTubeEQPreset: Identifiable, Codable, Equatable {
    let name: String
    /// Gains (dB) at the ten anchor frequencies below.
    let anchors: [Float]
    let bass: Float
    var id: String { name }
}

enum TrapTubeEQPresetLib {
    static let anchorFrequencies: [Double] = [32, 64, 125, 250, 500, 1_000, 2_000, 4_000, 8_000, 16_000]
    /// The ten reference bands are exact members of the model's 16
    /// bands, at these indices - the sheet's sliders drive real DSP.
    static let displayIndices = [0, 1, 2, 3, 4, 5, 6, 8, 12, 15]
    static let displayLabels = ["32", "64", "125", "250", "500", "1K", "2K", "4K", "8K", "16K"]

    static let builtins: [TrapTubeEQPreset] = [
        TrapTubeEQPreset(name: "Bando", anchors: [9, 8, 6, 3, 0, -1, 0, 2, 3, 2], bass: 10),
        TrapTubeEQPreset(name: "Default", anchors: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0], bass: 0),
        TrapTubeEQPreset(name: "Bass", anchors: [6, 5, 4, 2, 1, 0, 0, 0, 0, 0], bass: 6),
        TrapTubeEQPreset(name: "Bass++", anchors: [10, 9, 7, 5, 2, 0, 0, 0, 0, 0], bass: 12),
        TrapTubeEQPreset(name: "Acoustic", anchors: [5, 4, 3, 2, 3, 3, 4, 4, 3, 2], bass: 2),
        TrapTubeEQPreset(name: "Classical", anchors: [4, 3, 2, 1, 0, 0, -1, -2, -3, -4], bass: 0),
        TrapTubeEQPreset(name: "Dance", anchors: [6, 5, 3, 1, 0, 0, 2, 3, 4, 3], bass: 6),
        TrapTubeEQPreset(name: "Deep", anchors: [7, 6, 5, 4, 3, 2, 1, 0, -1, -2], bass: 6),
        TrapTubeEQPreset(name: "Electronic", anchors: [5, 4, 3, 1, 0, 1, 2, 3, 4, 3], bass: 4),
        TrapTubeEQPreset(name: "Flat", anchors: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0], bass: 0),
        TrapTubeEQPreset(name: "Hip Hop", anchors: [6, 5, 4, 2, 0, -1, 0, 2, 3, 3], bass: 8),
        TrapTubeEQPreset(name: "Jazz", anchors: [3, 3, 2, 2, 2, 3, 2, 3, 3, 2], bass: 2),
        TrapTubeEQPreset(name: "Loudness", anchors: [5, 4, 3, 1, 0, 0, 2, 4, 5, 5], bass: 4),
        TrapTubeEQPreset(name: "Lounge", anchors: [3, 2, 2, 1, 2, 2, 2, 1, 1, 0], bass: 2),
        TrapTubeEQPreset(name: "Pop", anchors: [1, 1, 2, 3, 3, 2, 1, 0, -1, -1], bass: 0),
        TrapTubeEQPreset(name: "Rock", anchors: [5, 4, 2, 1, 0, -1, 1, 2, 3, 3], bass: 2),
        TrapTubeEQPreset(name: "Spoken Word", anchors: [-2, -1, 0, 2, 4, 5, 5, 4, 2, 0], bass: 0),
        TrapTubeEQPreset(name: "Trap", anchors: [9, 8, 6, 3, 0, -1, 0, 1, 3, 4], bass: 10),
        TrapTubeEQPreset(name: "Drill", anchors: [8, 7, 5, 2, 0, 0, 1, 2, 4, 5], bass: 8),
        TrapTubeEQPreset(name: "Clarity", anchors: [-2, -1, 0, 1, 2, 3, 4, 5, 5, 4], bass: 0)
    ]

    static let flat = TrapTubeEQPreset(name: "Flat", anchors: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0], bass: 0)

    /// Expands a 10-anchor curve onto the model's 16 bands by
    /// log-frequency interpolation. The ten anchors land exactly;
    /// the in-between bands (3k/5k/6k/7k/10k/12k) follow the curve.
    static func expand(_ anchors: [Float]) -> [Float] {
        guard anchors.count == anchorFrequencies.count else { return Array(repeating: 0, count: 16) }
        return AudioEngineManager.frequencies.map { frequency in
            let f = Double(frequency)
            if let exact = anchorFrequencies.firstIndex(of: f) { return anchors[exact] }
            let lower = anchorFrequencies.lastIndex { $0 < f } ?? 0
            let upper = anchorFrequencies.firstIndex { $0 > f } ?? (anchorFrequencies.count - 1)
            if lower == upper { return anchors[lower] }
            let t = (log(f) - log(anchorFrequencies[lower])) / (log(anchorFrequencies[upper]) - log(anchorFrequencies[lower]))
            return Float(Double(anchors[lower]) + (Double(anchors[upper]) - Double(anchors[lower])) * t)
        }
    }

    private static let customsKey = "TrapTube.PlayerEQ.CustomPresets"

    static func customPresets() -> [TrapTubeEQPreset] {
        guard let data = UserDefaults.standard.data(forKey: customsKey),
              let decoded = try? JSONDecoder().decode([TrapTubeEQPreset].self, from: data) else { return [] }
        return decoded
    }

    static func saveCustom(_ preset: TrapTubeEQPreset) {
        var list = customPresets()
        list.removeAll { $0.name == preset.name }
        list.append(preset)
        if let data = try? JSONEncoder().encode(list) {
            UserDefaults.standard.set(data, forKey: customsKey)
        }
    }

    static func deleteCustoms(at offsets: IndexSet) {
        var list = customPresets()
        for index in offsets.sorted(by: >) { list.remove(at: index) }
        if let data = try? JSONEncoder().encode(list) {
            UserDefaults.standard.set(data, forKey: customsKey)
        }
    }
}

/// Owns the AVPictureInPictureController for the player's layer.
final class TrapTubePiPHolder: NSObject, AVPictureInPictureControllerDelegate {
    private var controller: AVPictureInPictureController?
    private weak var attachedLayer: AVPlayerLayer?
    weak var session: TrapTubeNativeSession?

    var isSupported: Bool { AVPictureInPictureController.isPictureInPictureSupported() }

    func attach(layer: AVPlayerLayer) {
        guard isSupported else { return }
        if attachedLayer == layer, controller != nil { return }
        attachedLayer = layer
        guard let created = AVPictureInPictureController(playerLayer: layer) else { return }
        created.delegate = self
        controller = created
    }

    func toggle() {
        guard let controller else { return }
        if controller.isPictureInPictureActive {
            controller.stopPictureInPicture()
        } else {
            controller.startPictureInPicture()
        }
    }

    func pictureInPictureControllerWillStartPictureInPicture(_ controller: AVPictureInPictureController) {
        let activeSession = session
        Task { @MainActor in activeSession?.pipStateChanged(active: true) }
    }

    func pictureInPictureControllerDidStopPictureInPicture(_ controller: AVPictureInPictureController) {
        let activeSession = session
        Task { @MainActor in activeSession?.pipStateChanged(active: false) }
    }

    func pictureInPictureController(_ controller: AVPictureInPictureController,
                                    restoreUserInterfaceForPictureInPictureStopWithCompletionHandler completionHandler: @escaping (Bool) -> Void) {
        TrapTubeNativePlayCenter.shared.reopenSession()
        completionHandler(true)
    }
}

// MARK: - Ghost audio path (Round 7)

/// Ghost path: the AVPlayer plays the video muted while this
/// engine renders the audio-only stream through TrapTube's own
/// graph - player node -> varispeed -> 10-band EQ -> main mixer -
/// so the player's EQ is a real AVAudioUnitEQ that the Musi-style
/// sheet drives directly, with no tap in the chain. Two feeds:
/// STREAMED (an AVAssetReader pump schedules decoded PCM into the
/// node a few seconds ahead) and FILE (the whole audio file,
/// fetched with the Round 6 downloader, scheduled on the same
/// node) for streams the reader cannot run.
@MainActor
final class TrapTubeGhostAudio {
    enum Feed {
        case none, streamed, file
    }

    struct Source {
        let url: URL
        let userAgent: String
    }

    static let bandFrequencies: [Float] = [32, 64, 125, 250, 500, 1_000, 2_000, 4_000, 8_000, 16_000]

    private(set) var feed: Feed = .none
    var isLive: Bool { feed != .none }
    private(set) var streamEnded = false
    private(set) var audioDuration: TimeInterval = 0

    private let engine = AVAudioEngine()
    private let node = AVAudioPlayerNode()
    private let varispeed = AVAudioUnitVarispeed()
    private let eqUnit = AVAudioUnitEQ(numberOfBands: 10)

    private var connected = false
    private var graphFormat: AVAudioFormat?
    private var bandGains: [Float] = Array(repeating: 0, count: 10)
    private var bypassed: Bool
    private var baselineRate: Float = 1
    private var correction: Float = 1
    private var outputLevelValue: Float = 1

    private var source: Source?
    private var desiredPlaying = false

    private var reader: AVAssetReader?
    private var readerOutput: AVAssetReaderTrackOutput?
    private var pumpTask: Task<Void, Never>?
    private var scheduledFrames: AVAudioFramePosition = 0
    private var primeOffset: TimeInterval = 0
    private var lastBufferAt = Date.distantPast
    private var stallReported = false
    var onStreamStalled: (() -> Void)?

    /// The ONE format the streamed feed connects the graph with
    /// and schedules in: the standard format (48 kHz float32
    /// interleaved stereo), the most universally accepted format
    /// for every unit in the chain. Reader buffers are never
    /// trusted to already be in it — AVAssetReaderTrackOutput
    /// delivers its own layout (the non-interleaved request in
    /// the output settings is not reliably honored, and the
    /// emitted format description can carry a channel layout
    /// that makes an otherwise-identical AVAudioFormat unequal),
    /// while AVAudioPlayerNode.scheduleBuffer raises an
    /// uncatchable NSException when a buffer's format differs
    /// from the connection format in ANY detail. So every reader
    /// buffer is converted into exactly this format (see
    /// schedulableBuffer) and re-checked against the graph
    /// format immediately before the schedule call.
    private let streamFormat = AVAudioFormat(standardFormatWithSampleRate: 48_000, channels: 2)
    private var streamConverter: AVAudioConverter?
    private var streamConverterFormat: AVAudioFormat?
    /// Bumped by teardownFeed on every feed replacement; a pump
    /// whose captured generation no longer matches exits before
    /// it can touch the new feed's reader or the node.
    private var feedGeneration = 0

    private var loadedFile: AVAudioFile?
    private var tempFileURL: URL?

    init() {
        bypassed = !TrapTubeTapEQ.shared.isEnabled
        engine.attach(node)
        engine.attach(varispeed)
        engine.attach(eqUnit)
        applyParameters()
    }

    // MARK: Parameters (cached: an engine reset must not lose them)

    private func applyParameters() {
        for (index, frequency) in Self.bandFrequencies.enumerated() {
            let band = eqUnit.bands[index]
            band.filterType = .parametric
            band.frequency = frequency
            band.bandwidth = 1.0
            band.gain = bandGains[index]
            band.bypass = false
        }
        eqUnit.bypass = bypassed
        varispeed.rate = baselineRate * correction
        engine.mainMixerNode.outputVolume = outputLevelValue
    }

    func bandGain(_ index: Int) -> Float { bandGains[index] }

    func setBand(_ index: Int, gain: Float) {
        let clamped = min(max(gain, -12), 12)
        bandGains[index] = clamped
        eqUnit.bands[index].gain = clamped
    }

    func applyCurve(_ gains: [Float]) {
        for index in 0..<10 {
            setBand(index, gain: gains.indices.contains(index) ? gains[index] : 0)
        }
    }

    func setEnabled(_ enabled: Bool) {
        bypassed = !enabled
        eqUnit.bypass = bypassed
    }

    func setBaselineRate(_ rate: Float) {
        baselineRate = rate
        varispeed.rate = baselineRate * correction
    }

    /// Micro-correction from the sync loop: 1 = locked to the
    /// baseline rate; the loop clamps its input to ±3%.
    func setCorrection(_ factor: Float) {
        correction = min(max(factor, 0.97), 1.03)
        varispeed.rate = baselineRate * correction
    }

    func setOutputLevel(_ level: Float) {
        outputLevelValue = min(max(level, 0), 1)
        engine.mainMixerNode.outputVolume = outputLevelValue
    }

    // MARK: Graph

    /// Connects node -> varispeed -> EQ -> mixer in `format`.
    /// engine.connect raises an uncatchable exception on a
    /// format it cannot route, and scheduling into a node whose
    /// connections were never made raises too — so a degenerate
    /// format is refused here and the caller aborts the prime
    /// (degrading to the next feed) instead of proceeding with a
    /// half-built graph.
    @discardableResult
    private func connectGraph(format: AVAudioFormat) -> Bool {
        if connected, graphFormat == format { return true }
        guard format.sampleRate > 0, format.channelCount > 0 else { return false }
        // A format change needs fresh connections; reset() drops
        // them (and node parameters), so re-apply ours after.
        engine.reset()
        engine.connect(node, to: varispeed, format: format)
        engine.connect(varispeed, to: eqUnit, format: format)
        engine.connect(eqUnit, to: engine.mainMixerNode, format: format)
        graphFormat = format
        connected = true
        applyParameters()
        return true
    }

    // MARK: Starting feeds

    /// Tries the streamed feed first, then the file feed. The
    /// position provider is consulted at the moment each feed
    /// actually primes, so a slow download still lands on the
    /// video's current position.
    func start(source: Source, position: @escaping () -> TimeInterval) async -> Feed {
        self.source = source
        teardownFeed(deleteTemp: true)
        if await primeStreamed(source: source, startAt: position()) {
            return .streamed
        }
        if await primeFileRoute(source: source, position: position) {
            return .file
        }
        feed = .none
        return .none
    }

    func switchToFile(position: @escaping () -> TimeInterval) async -> Bool {
        guard let source else { return false }
        teardownFeed(deleteTemp: true)
        return await primeFileRoute(source: source, position: position)
    }

    private func primeStreamed(source: Source, startAt: TimeInterval) async -> Bool {
        let asset = AVURLAsset(url: source.url, options: [
            "AVURLAssetHTTPHeaderFieldsKey": ["User-Agent": source.userAgent, "Referer": "https://www.youtube.com/"]
        ])
        // The graph format is the canonical stream format, NOT
        // a locally rebuilt twin of what we hope the reader
        // emits: the pump converts every emitted buffer into
        // exactly this format before scheduling.
        guard let track = try? await asset.loadTracks(withMediaType: .audio).first,
              let format = streamFormat,
              let newReader = try? AVAssetReader(asset: asset) else { return false }
        let output = AVAssetReaderTrackOutput(track: track, outputSettings: [
            AVFormatIDKey: kAudioFormatLinearPCM,
            AVSampleRateKey: 48_000,
            AVNumberOfChannelsKey: 2,
            AVLinearPCMBitDepthKey: 32,
            AVLinearPCMIsFloatKey: true,
            AVLinearPCMIsNonInterleaved: false
        ])
        output.alwaysCopiesSampleData = false
        guard newReader.canAdd(output) else { return false }
        newReader.add(output)
        if startAt > 0 {
            newReader.timeRange = CMTimeRange(start: CMTime(seconds: startAt, preferredTimescale: 600),
                                              duration: .positiveInfinity)
        }
        // Retire any previous feed first (its pump is cancelled
        // and generation-invalidated) so two pumps can never read
        // one output or schedule into one node concurrently;
        // resync reaches this prime without an outer teardown.
        teardownFeed(deleteTemp: false)
        guard connectGraph(format: format) else { return false }
        node.stop()
        reader = newReader
        readerOutput = output
        primeOffset = startAt
        scheduledFrames = 0
        streamEnded = false
        stallReported = false
        lastBufferAt = Date()
        audioDuration = 0
        guard newReader.startReading() else {
            teardownFeed(deleteTemp: false)
            return false
        }
        feed = .streamed
        startPump()
        if !engine.isRunning { try? engine.start() }
        if desiredPlaying { node.play() }
        return true
    }

    private func primeFileRoute(source: Source, position: () -> TimeInterval) async -> Bool {
        guard let downloaded = try? await TrapTubeDirectDownloader.shared.download(
            from: source.url, userAgent: source.userAgent, onProgress: { _ in }) else { return false }
        // AVAudioFile needs a real audio extension to open the
        // container; the downloader's temp files carry none.
        let local = FileManager.default.temporaryDirectory
            .appendingPathComponent("tt-ghost-\(UUID().uuidString).m4a")
        if (try? FileManager.default.moveItem(at: downloaded, to: local)) == nil {
            guard (try? FileManager.default.copyItem(at: downloaded, to: local)) != nil else { return false }
            try? FileManager.default.removeItem(at: downloaded)
        }
        tempFileURL = local
        return primeFile(localURL: local, startAt: position())
    }

    private func primeFile(localURL: URL, startAt: TimeInterval) -> Bool {
        guard let file = try? AVAudioFile(forReading: localURL) else { return false }
        let format = file.processingFormat
        // A degenerate processing format would poison the
        // frame math below and the graph connection alike.
        guard format.sampleRate > 0, format.channelCount > 0 else { return false }
        // Same retirement as the streamed prime: scheduleSegment
        // must be the only producer on this node.
        teardownFeed(deleteTemp: false)
        // The file's own processing format is the one format
        // scheduleSegment accepts for it — self-consistent by
        // construction.
        guard connectGraph(format: format) else { return false }
        node.stop()
        loadedFile = file
        primeOffset = min(max(startAt, 0), Double(file.length) / format.sampleRate)
        scheduledFrames = file.length
        audioDuration = Double(file.length) / format.sampleRate
        streamEnded = false
        let startFrame = AVAudioFramePosition(primeOffset * format.sampleRate)
        let frames = file.length - startFrame
        guard frames > 0 else { return false }
        node.scheduleSegment(file, startingFrame: startFrame,
                             frameCount: AVAudioFrameCount(frames), at: nil)
        feed = .file
        if !engine.isRunning { try? engine.start() }
        if desiredPlaying { node.play() }
        return true
    }

    // MARK: The reader pump

    private func startPump() {
        pumpTask?.cancel()
        // The pump works on CAPTURED reader/output values and
        // the feed generation at prime time — never on the live
        // properties, which a resync may swap mid-loop. The
        // identity + generation checks make a superseded pump
        // exit before its next read or schedule.
        guard let pumpReader = reader, let pumpOutput = readerOutput else { return }
        let generation = feedGeneration
        pumpTask = Task { [weak self] in
            guard let self else { return }
            while !Task.isCancelled, self.feedGeneration == generation,
                  self.feed == .streamed, self.reader === pumpReader {
                if pumpReader.status == .failed {
                    self.reportStall()
                    return
                }
                if pumpReader.status == .completed {
                    self.streamEnded = true
                    return
                }
                if self.scheduledAhead() > 3.5 {
                    try? await Task.sleep(nanoseconds: 100_000_000)
                    continue
                }
                if let sampleBuffer = pumpOutput.copyNextSampleBuffer() {
                    // Convert into the graph's one format and
                    // re-verify equality immediately before the
                    // schedule call: scheduleBuffer raises an
                    // uncatchable exception on ANY format
                    // mismatch, so a buffer that is not provably
                    // in the connection format is dropped, never
                    // scheduled. Persistent conversion failure
                    // starves the pump, which the branch below
                    // escalates to the file feed.
                    if let pcm = self.schedulableBuffer(from: sampleBuffer),
                       pcm.format == self.graphFormat {
                        self.node.scheduleBuffer(pcm, completionHandler: nil)
                        self.scheduledFrames += AVAudioFramePosition(pcm.frameLength)
                        self.lastBufferAt = Date()
                    }
                    continue
                }
                // Nothing available right now: a live feed that
                // starves for over five seconds while playing is
                // treated as failed so the session can fall back
                // to the file feed.
                if self.desiredPlaying, self.scheduledAhead() < 0.5,
                   Date().timeIntervalSince(self.lastBufferAt) > 5 {
                    self.reportStall()
                    return
                }
                try? await Task.sleep(nanoseconds: 60_000_000)
            }
        }
    }

    private func reportStall() {
        guard !stallReported else { return }
        stallReported = true
        onStreamStalled?()
    }

    private func scheduledAhead() -> TimeInterval {
        guard let format = graphFormat else { return 0 }
        let scheduledEnd = primeOffset + Double(scheduledFrames) / format.sampleRate
        return scheduledEnd - (position() ?? primeOffset)
    }

    /// The reader's samples in the reader's OWN format,
    /// whatever layout the emitted format description actually
    /// carries. Never scheduled directly — this is only the
    /// input to the canonical conversion below.
    private static func rawPCMBuffer(from sampleBuffer: CMSampleBuffer) -> AVAudioPCMBuffer? {
        guard let formatDescription = CMSampleBufferGetFormatDescription(sampleBuffer) else { return nil }
        let format = AVAudioFormat(cmAudioFormatDescription: formatDescription)
        let frameCount = AVAudioFrameCount(CMSampleBufferGetNumSamples(sampleBuffer))
        guard frameCount > 0, format.sampleRate > 0, format.channelCount > 0,
              let buffer = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: frameCount) else { return nil }
        buffer.frameLength = frameCount
        let status = CMSampleBufferCopyPCMDataIntoAudioBufferList(
            sampleBuffer, at: 0, frameCount: Int32(frameCount), into: buffer.mutableAudioBufferList)
        return status == noErr ? buffer : nil
    }

    /// The only buffer the pump may schedule: the raw samples
    /// converted into the graph's canonical stream format.
    /// AVAudioConverter reports failure as a status (it never
    /// raises), so any stream whose layout cannot be converted
    /// yields nil — the chunk is dropped, and if that keeps
    /// happening the pump's starve detection escalates the feed
    /// to FILE, then the session to TAP. Degradation instead of
    /// the format-mismatch exception this replaces.
    private func schedulableBuffer(from sampleBuffer: CMSampleBuffer) -> AVAudioPCMBuffer? {
        guard let target = streamFormat,
              let raw = Self.rawPCMBuffer(from: sampleBuffer) else { return nil }
        if raw.format == target { return raw }
        if streamConverterFormat != raw.format {
            streamConverter = AVAudioConverter(from: raw.format, to: target)
            streamConverterFormat = raw.format
        }
        guard let converter = streamConverter, raw.frameLength > 0 else { return nil }
        let ratio = target.sampleRate / raw.format.sampleRate
        guard ratio.isFinite, ratio > 0 else { return nil }
        let capacity = AVAudioFrameCount((Double(raw.frameLength) * ratio).rounded(.up)) + 32
        guard capacity > 32,
              let converted = AVAudioPCMBuffer(pcmFormat: target, frameCapacity: capacity) else { return nil }
        var supplied = false
        var conversionError: NSError?
        let status = converter.convert(to: converted, error: &conversionError) { _, inputStatus in
            if supplied {
                inputStatus.pointee = .endOfStream
                return nil
            }
            supplied = true
            inputStatus.pointee = .haveData
            return raw
        }
        guard status != .error, converted.frameLength > 0 else { return nil }
        return converted
    }

    // MARK: Position + transport

    /// The audio timeline position: where the stream primed plus
    /// what the node has actually rendered since (the player-node
    /// clock follows real consumption, varispeed included).
    func position() -> TimeInterval? {
        guard feed != .none,
              let nodeTime = node.lastRenderTime,
              let playerTime = node.playerTime(forNodeTime: nodeTime),
              playerTime.sampleRate > 0 else { return nil }
        return primeOffset + Double(playerTime.sampleTime) / playerTime.sampleRate
    }

    func setDesiredPlaying(_ playing: Bool) {
        desiredPlaying = playing
        guard feed != .none else { return }
        if playing {
            if !engine.isRunning { try? engine.start() }
            node.play()
        } else {
            node.pause()
        }
    }

    /// Stall-follow: pauses rendering without changing the
    /// desired state the session asked for.
    func pauseRendering() { node.pause() }

    func resumeRendering() {
        guard desiredPlaying, feed != .none else { return }
        if !engine.isRunning { try? engine.start() }
        node.play()
    }

    /// Hard resync: flush the node and re-prime the same feed at
    /// the video's current position.
    func resync(to position: TimeInterval) async -> Bool {
        guard let source, feed != .none else { return false }
        switch feed {
        case .streamed:
            return await primeStreamed(source: source, startAt: position)
        case .file:
            guard let tempFileURL else { return false }
            return primeFile(localURL: tempFileURL, startAt: position)
        case .none:
            return false
        }
    }

    func teardownFeed(deleteTemp: Bool) {
        // Invalidate any live pump BEFORE cancelling it: Task
        // cancellation is cooperative, so the generation check
        // is what actually stops a mid-loop pump from touching
        // the next feed's reader or node.
        feedGeneration += 1
        pumpTask?.cancel()
        pumpTask = nil
        reader?.cancelReading()
        reader = nil
        readerOutput = nil
        node.stop()
        loadedFile = nil
        feed = .none
        streamEnded = false
        if deleteTemp, let tempFileURL {
            try? FileManager.default.removeItem(at: tempFileURL)
            self.tempFileURL = nil
        }
    }

    func shutdown() {
        teardownFeed(deleteTemp: true)
        engine.stop()
        source = nil
        desiredPlaying = false
    }
}

/// The persistent native playback session: one AVPlayer, one
/// queue, alive across presentations of the player view.
@MainActor
final class TrapTubeNativeSession: ObservableObject {
    static let shared = TrapTubeNativeSession()

    enum Phase {
        case idle
        case resolving
        case playing
        case failed(String)
    }

    enum RepeatMode: Int {
        case off, all, one
    }

    enum AudioPath: String {
        case ghost, tap
    }

    let player = AVPlayer()
    let pipHolder = TrapTubePiPHolder()

    @Published private(set) var phase: Phase = .idle
    @Published private(set) var queue: [TrapTubeQueueItem] = []
    @Published private(set) var queueIndex = 0
    @Published private(set) var contextName = "YouTube"
    @Published private(set) var currentInfo: TrapTubeVideoInfo?
    @Published private(set) var equalizerActive = false
    @Published private(set) var eqAttachFinished = false
    @Published private(set) var isPlaying = false
    @Published private(set) var currentTime: TimeInterval = 0
    @Published private(set) var duration: TimeInterval = 0
    @Published private(set) var rate: Float = 1
    @Published private(set) var volume: Float = 1
    @Published private(set) var isFavorite = false
    @Published var isShuffled = false
    @Published var repeatMode: RepeatMode = .off
    @Published private(set) var crossfadeSeconds: Double = 0
    @Published private(set) var eqEnabled: Bool = true
    @Published private(set) var pipActive = false
    @Published private(set) var audioPath: AudioPath = .ghost
    @Published private(set) var ghostFeed: TrapTubeGhostAudio.Feed = .none
    @Published private(set) var driftMs: Int?
    @Published private(set) var usingFallbackTap = false

    let ghost = TrapTubeGhostAudio()

    private var startTask: Task<Void, Never>?
    private var attachTask: Task<Void, Never>?
    private var relatedTask: Task<Void, Never>?
    private var fadeTask: Task<Void, Never>?
    private var statusObservation: NSKeyValueObservation?
    private var endObserver: NSObjectProtocol?
    private var playerItem: AVPlayerItem?
    private var generation = 0
    private var autoFadeStarted = false
    private var ghostTask: Task<Void, Never>?
    private var syncTask: Task<Void, Never>?
    private var itemUsesGhost = false
    private var lastHardResync = Date.distantPast
    private var outputGain: Float = 1

    private init() {
        let defaults = UserDefaults.standard
        if defaults.object(forKey: "TrapTube.NativePlayer.Volume") != nil {
            volume = min(max(defaults.float(forKey: "TrapTube.NativePlayer.Volume"), 0), 1)
        }
        crossfadeSeconds = defaults.double(forKey: "TrapTube.NativePlayer.Crossfade")
        eqEnabled = TrapTubeTapEQ.shared.isEnabled
        player.volume = volume
        outputGain = volume
        if let savedPath = defaults.string(forKey: "TrapTube.NativePlayer.AudioPath"),
           let path = AudioPath(rawValue: savedPath) {
            audioPath = path
        }
        pipHolder.session = self
        player.addPeriodicTimeObserver(forInterval: CMTime(seconds: 0.25, preferredTimescale: 600), queue: .main) { [weak self] time in
            guard let self else { return }
            Task { @MainActor in self.tick(time: time) }
        }
    }

    var currentEntry: TrapTubeQueueItem? {
        queue.indices.contains(queueIndex) ? queue[queueIndex] : nil
    }

    var hasActiveContent: Bool { !queue.isEmpty }

    var failureMessage: String? {
        if case .failed(let message) = phase { return message }
        return nil
    }

    var isResolving: Bool {
        if case .resolving = phase { return true }
        return false
    }

    /// The honest state line (no badge theater). On the ghost
    /// path it is the live path + drift readout the sync is judged
    /// by; on the tap path it is the attach state; a ghost item
    /// that fell back says so.
    var statusText: String {
        switch phase {
        case .idle: return ""
        case .resolving: return "RESOLVING…"
        case .failed: return "PLAYBACK FAILED"
        case .playing:
            if itemUsesGhost {
                if usingFallbackTap {
                    if !eqAttachFinished { return "TAP (FALLBACK) · EQ ATTACHING…" }
                    if !eqEnabled { return "TAP (FALLBACK) · EQ OFF" }
                    return equalizerActive ? "TAP (FALLBACK)" : "TAP (FALLBACK) · EQ UNAVAILABLE"
                }
                if ghostFeed == .none { return "GHOST STARTING…" }
                var text = ghostFeed == .file ? "GHOST (FILE)" : "GHOST (STREAMED)"
                if !eqEnabled { text += " · EQ OFF" }
                if let driftMs {
                    text += " · drift \(driftMs) ms"
                } else {
                    text += " · SYNCING…"
                }
                return text
            }
            if !eqEnabled { return "EQ OFF — BYPASSED" }
            if !eqAttachFinished { return "EQ ATTACHING…" }
            return equalizerActive ? "TRAPTUBE EQ ACTIVE" : "EQ UNAVAILABLE FOR THIS STREAM"
        }
    }

    /// True when the EQ the user hears is engaged right now -
    /// drives the accent tint on the player's EQ affordances.
    var eqAudiblyActive: Bool {
        guard eqEnabled else { return false }
        if itemUsesGhost, !usingFallbackTap { return ghostFeed != .none }
        return equalizerActive && eqAttachFinished
    }

    /// The user's volume, routed to whichever output is live:
    /// the ghost mixer's gain, or the player's own volume on the
    /// tap path. Ramps and fades all write through here.
    private func applyOutputGain() {
        if itemUsesGhost {
            ghost.setOutputLevel(outputGain)
        } else {
            player.volume = outputGain
        }
    }

    func setAudioPath(_ path: AudioPath) {
        guard path != audioPath else { return }
        audioPath = path
        UserDefaults.standard.set(path.rawValue, forKey: "TrapTube.NativePlayer.AudioPath")
        // On-device A/B: restart the current track at the same
        // position through the newly chosen path.
        if hasActiveContent, case .playing = phase {
            load(index: queueIndex, startAt: currentTime, fadeIn: 0)
        }
    }

    var remainingLabel: String {
        // Until the item's duration is known there is no
        // remaining time to show — a placeholder, not "-0:00".
        guard duration > 0, duration.isFinite else { return "--:--" }
        return "-" + Self.timeLabel(max(0, duration - currentTime))
    }

    static func timeLabel(_ seconds: TimeInterval) -> String {
        guard seconds.isFinite, seconds >= 0 else { return "0:00" }
        let total = Int(seconds.rounded())
        let minutes = total / 60
        let rest = total % 60
        return rest < 10 ? "\(minutes):0\(rest)" : "\(minutes):\(rest)"
    }

    func pipStateChanged(active: Bool) { pipActive = active }

    // MARK: Starting and loading

    func begin(request: TrapTubeNativePlayRequest) {
        if let current = currentEntry, current.videoID == request.videoID, player.currentItem != nil {
            if case .failed = phase {
                load(index: queueIndex, startAt: 0, fadeIn: 0)
            }
            return
        }
        queue = [TrapTubeQueueItem(videoID: request.videoID, title: request.title, channel: "")]
        queueIndex = 0
        contextName = request.contextName
        load(index: 0, startAt: request.startAt, fadeIn: 0)
    }

    func retry() {
        guard !queue.isEmpty else { return }
        load(index: queueIndex, startAt: 0, fadeIn: 0)
    }

    private func load(index: Int, startAt: TimeInterval, fadeIn: TimeInterval) {
        guard queue.indices.contains(index) else { return }
        queueIndex = index
        generation += 1
        let loadGeneration = generation
        startTask?.cancel()
        attachTask?.cancel()
        relatedTask?.cancel()
        fadeTask?.cancel()
        ghostTask?.cancel()
        syncTask?.cancel()
        ghost.onStreamStalled = nil
        statusObservation?.invalidate()
        statusObservation = nil
        removeEndObserver()
        playerItem = nil
        phase = .resolving
        equalizerActive = false
        eqAttachFinished = false
        isPlaying = false
        currentTime = 0
        duration = 0
        autoFadeStarted = false
        itemUsesGhost = audioPath == .ghost
        usingFallbackTap = false
        ghostFeed = .none
        driftMs = nil
        outputGain = volume
        applyOutputGain()

        try? AVAudioSession.sharedInstance().setCategory(.playback, mode: .moviePlayback, options: [.allowAirPlay, .allowBluetoothA2DP])
        try? AVAudioSession.sharedInstance().setActive(true)

        let entry = queue[index]
        startTask = Task { [weak self] in
            guard let self else { return }
            do {
                let info = try await TrapTubeInnerTube.fetchInfo(videoID: entry.videoID)
                guard !Task.isCancelled, self.generation == loadGeneration else { return }
                let item = try await Self.makePlayerItem(info: info)
                guard !Task.isCancelled, self.generation == loadGeneration else { return }
                self.currentInfo = info
                var updatedQueue = self.queue
                if updatedQueue.indices.contains(index) {
                    updatedQueue[index] = TrapTubeQueueItem(
                        videoID: info.videoID,
                        title: info.title.isEmpty ? entry.title : info.title,
                        channel: info.author)
                    self.queue = updatedQueue
                }
                self.isFavorite = TrapTubeFavoritesStore.shared.contains(videoID: entry.videoID)
                self.playerItem = item
                self.statusObservation = item.observe(\.status, options: [.new]) { [weak self] observedItem, _ in
                    guard observedItem.status == .failed else { return }
                    let message = observedItem.error?.localizedDescription ?? "The stream failed to load."
                    Task { @MainActor in self?.failCurrentItem(message: message) }
                }
                self.endObserver = NotificationCenter.default.addObserver(
                    forName: .AVPlayerItemDidPlayToEndTime, object: item, queue: .main) { [weak self] _ in
                    Task { @MainActor in self?.handleItemEnd() }
                }
                // The previous item's ghost feed ends exactly
                // when its video does.
                self.ghost.teardownFeed(deleteTemp: false)
                self.ghostFeed = .none
                self.driftMs = nil
                self.player.replaceCurrentItem(with: item)
                self.phase = .playing
                // Ghost items play video-only; the engine owns
                // the audio. Tap items (and ghost fallbacks)
                // play the stream's own audio.
                self.player.isMuted = self.itemUsesGhost
                if startAt > 5 {
                    // Pick up roughly where the page video left off;
                    // the completionHandler seek variant (the async
                    // variant without await failed CI in Round 6).
                    self.player.seek(to: CMTime(seconds: startAt, preferredTimescale: 600),
                                     toleranceBefore: CMTime(seconds: 2, preferredTimescale: 600),
                                     toleranceAfter: .zero) { _ in }
                }
                self.play()
                if fadeIn > 0 {
                    self.outputGain = 0
                    self.applyOutputGain()
                    self.rampVolume(to: self.volume, duration: fadeIn)
                }
                if self.itemUsesGhost {
                    self.startGhost(info: info, generation: loadGeneration, item: item)
                } else {
                    // The EQ tap attaches alongside playback in its
                    // own task: it never gates playback, and stop()
                    // can cancel it cleanly.
                    self.attachTask = Task { [weak self] in
                        let attached = await TrapTubeTapEQ.shared.attach(to: item)
                        guard let self, self.generation == loadGeneration, self.playerItem === item else { return }
                        self.equalizerActive = attached
                        self.eqAttachFinished = true
                    }
                }
                // A single-video launch grows into the watch-next
                // queue ("YouTube Mix") when YouTube offers one.
                if self.queue.count == 1 {
                    let sourceID = entry.videoID
                    self.relatedTask = Task { [weak self] in
                        let related = await TrapTubeInnerTube.fetchRelated(videoID: sourceID)
                        guard let self, !Task.isCancelled, self.generation == loadGeneration,
                              self.queue.count == 1, self.queue.first?.videoID == sourceID,
                              !related.isEmpty else { return }
                        self.queue = self.queue + related
                        if self.contextName == "YouTube" { self.contextName = "YouTube Mix" }
                    }
                }
            } catch {
                if !Task.isCancelled, self.generation == loadGeneration {
                    self.phase = .failed(error.localizedDescription)
                }
            }
        }
    }

    // MARK: Ghost orchestration

    /// The ghost's audio source for an item: the best AAC
    /// audio-only stream (the same family the composition path
    /// uses), or the muxed file's own audio track when no
    /// adaptive audio exists.
    private static func ghostSource(info: TrapTubeVideoInfo) -> TrapTubeGhostAudio.Source? {
        if let aac = info.audioOnly.filter({ $0.isAACAudio }).max(by: { $0.bitrate < $1.bitrate }),
           let url = URL(string: aac.url) {
            return TrapTubeGhostAudio.Source(
                url: url, userAgent: aac.userAgent.isEmpty ? info.userAgent : aac.userAgent)
        }
        if let muxed = info.muxed.first, let url = URL(string: muxed.url) {
            return TrapTubeGhostAudio.Source(
                url: url, userAgent: muxed.userAgent.isEmpty ? info.userAgent : muxed.userAgent)
        }
        return nil
    }

    private func startGhost(info: TrapTubeVideoInfo, generation loadGeneration: Int, item: AVPlayerItem) {
        ghostTask?.cancel()
        ghost.onStreamStalled = { [weak self] in
            guard let self, self.generation == loadGeneration else { return }
            self.escalateGhostToFile(generation: loadGeneration)
        }
        ghostTask = Task { [weak self] in
            guard let self else { return }
            guard let source = Self.ghostSource(info: info) else {
                self.beginTapFallback(generation: loadGeneration, item: item)
                return
            }
            self.ghost.setBaselineRate(self.rate)
            self.ghost.setEnabled(self.eqEnabled)
            let feed = await self.ghost.start(source: source) { [weak self] in
                self?.player.currentTime().seconds ?? 0
            }
            guard !Task.isCancelled, self.generation == loadGeneration, self.playerItem === item else { return }
            if feed == .none {
                self.beginTapFallback(generation: loadGeneration, item: item)
                return
            }
            self.ghostFeed = feed
            self.equalizerActive = true
            self.eqAttachFinished = true
            self.ghost.setDesiredPlaying(self.isPlaying || self.player.timeControlStatus == .playing)
            self.startSyncLoop(generation: loadGeneration)
        }
    }

    /// A streamed feed that fails or starves escalates to the
    /// file feed at the video's current position.
    private func escalateGhostToFile(generation loadGeneration: Int) {
        guard itemUsesGhost, !usingFallbackTap, ghostFeed == .streamed else { return }
        ghostTask?.cancel()
        ghostTask = Task { [weak self] in
            guard let self else { return }
            let ok = await self.ghost.switchToFile { [weak self] in
                self?.player.currentTime().seconds ?? 0
            }
            guard !Task.isCancelled, self.generation == loadGeneration else { return }
            if ok {
                self.ghostFeed = .file
                self.ghost.setDesiredPlaying(self.isPlaying || self.player.timeControlStatus == .playing)
            } else if let item = self.playerItem {
                self.beginTapFallback(generation: loadGeneration, item: item)
            }
        }
    }

    /// Ghost failed outright on this item: unmute the stream and
    /// run the Round 5/6 tap attach for it instead.
    private func beginTapFallback(generation loadGeneration: Int, item: AVPlayerItem) {
        guard generation == loadGeneration, playerItem === item else { return }
        usingFallbackTap = true
        ghostFeed = .none
        driftMs = nil
        syncTask?.cancel()
        ghost.teardownFeed(deleteTemp: true)
        player.isMuted = false
        outputGain = volume
        applyOutputGain()
        attachTask?.cancel()
        attachTask = Task { [weak self] in
            let attached = await TrapTubeTapEQ.shared.attach(to: item)
            guard let self, self.generation == loadGeneration, self.playerItem === item else { return }
            self.equalizerActive = attached
            self.eqAttachFinished = true
        }
    }

    /// The 5 Hz sync loop. Deadband ±25 ms does nothing; 25-120 ms
    /// of error bends the varispeed rate (proportional, clamped to
    /// ±3%) until the audio is back inside the deadband; beyond
    /// 120 ms - or when the video comes back from a stall - the
    /// feed hard-resyncs at the video's position. While AVPlayer
    /// waits on the network, the ghost node waits with it.
    private func startSyncLoop(generation loadGeneration: Int) {
        syncTask?.cancel()
        lastHardResync = Date.distantPast
        var waitingOnVideo = false
        syncTask = Task { [weak self] in
            while !Task.isCancelled {
                try? await Task.sleep(nanoseconds: 200_000_000)
                guard let self, self.generation == loadGeneration,
                      self.itemUsesGhost, !self.usingFallbackTap,
                      self.ghostFeed != .none, case .playing = self.phase else { continue }
                if self.player.timeControlStatus == .waitingToPlayAtSpecifiedRate {
                    if !waitingOnVideo {
                        waitingOnVideo = true
                        self.ghost.pauseRendering()
                    }
                    continue
                }
                if waitingOnVideo {
                    waitingOnVideo = false
                    self.ghost.resumeRendering()
                    await self.hardResyncGhost()
                    continue
                }
                guard let audioTime = self.ghost.position() else { continue }
                let videoTime = self.player.currentTime().seconds
                guard videoTime.isFinite else { continue }
                let drift = audioTime - videoTime
                self.driftMs = Int((drift * 1000).rounded())
                guard self.isPlaying else { continue }
                let magnitude = abs(drift)
                if magnitude <= 0.025 {
                    self.ghost.setCorrection(1)
                } else if magnitude <= 0.120 {
                    self.ghost.setCorrection(Float(min(max(1 - drift * 0.8, 0.97), 1.03)))
                } else if !self.ghost.streamEnded,
                          Date().timeIntervalSince(self.lastHardResync) > 1.5 {
                    await self.hardResyncGhost()
                }
            }
        }
    }

    private func hardResyncGhost() async {
        lastHardResync = Date()
        ghost.setCorrection(1)
        let target = player.currentTime().seconds
        let ok = await ghost.resync(to: target.isFinite ? target : 0)
        guard itemUsesGhost, !usingFallbackTap else { return }
        if !ok {
            if ghostFeed == .streamed {
                escalateGhostToFile(generation: generation)
            } else if let item = playerItem {
                beginTapFallback(generation: generation, item: item)
            }
        }
    }

    func stop() {
        generation += 1
        startTask?.cancel(); startTask = nil
        attachTask?.cancel(); attachTask = nil
        relatedTask?.cancel(); relatedTask = nil
        fadeTask?.cancel(); fadeTask = nil
        ghostTask?.cancel(); ghostTask = nil
        syncTask?.cancel(); syncTask = nil
        ghost.onStreamStalled = nil
        ghost.shutdown()
        itemUsesGhost = false
        usingFallbackTap = false
        ghostFeed = .none
        driftMs = nil
        statusObservation?.invalidate(); statusObservation = nil
        removeEndObserver()
        playerItem = nil
        player.pause()
        player.isMuted = false
        player.replaceCurrentItem(with: nil)
        queue = []
        queueIndex = 0
        currentInfo = nil
        phase = .idle
        equalizerActive = false
        eqAttachFinished = false
        isPlaying = false
        currentTime = 0
        duration = 0
        outputGain = volume
        player.volume = volume
    }

    private func removeEndObserver() {
        if let endObserver {
            NotificationCenter.default.removeObserver(endObserver)
            self.endObserver = nil
        }
    }

    private func failCurrentItem(message: String) {
        if case .playing = phase {
            phase = .failed(message)
            // A dead video must not leave ghost audio running.
            if itemUsesGhost { ghost.pauseRendering() }
        }
    }

    // MARK: Transport

    func play() {
        fadeTask?.cancel()
        autoFadeStarted = false
        outputGain = volume
        applyOutputGain()
        let wasPlaying = isPlaying
        player.play()
        if rate != 1 { player.rate = rate }
        if itemUsesGhost, !usingFallbackTap, ghostFeed != .none {
            ghost.setDesiredPlaying(true)
            // Resuming is a sync event: re-prime the feed at the
            // video's position rather than trusting the pause gap.
            if !wasPlaying {
                Task { [weak self] in await self?.hardResyncGhost() }
            }
        }
    }

    func pause() {
        player.pause()
        if itemUsesGhost { ghost.setDesiredPlaying(false) }
    }

    func togglePlay() {
        if isPlaying {
            pause()
        } else if case .failed = phase {
            retry()
        } else {
            play()
        }
    }

    func seek(toSeconds seconds: TimeInterval) {
        let clamped = max(0, seconds)
        player.seek(to: CMTime(seconds: clamped, preferredTimescale: 600),
                    toleranceBefore: .zero, toleranceAfter: .zero) { [weak self] finished in
            // A completed seek is a sync event for the ghost feed.
            guard finished, let self, self.itemUsesGhost, !self.usingFallbackTap,
                  self.ghostFeed != .none else { return }
            Task { [weak self] in await self?.hardResyncGhost() }
        }
        currentTime = clamped
        autoFadeStarted = false
        fadeTask?.cancel()
        if isPlaying { outputGain = volume; applyOutputGain() }
    }

    func seek(toFraction fraction: Double) {
        guard duration > 0 else { return }
        seek(toSeconds: min(max(fraction, 0), 1) * duration)
    }

    func setRate(_ newRate: Float) {
        rate = newRate
        player.defaultRate = newRate
        if isPlaying { player.rate = newRate }
        // The varispeed unit takes the same baseline rate (it
        // pitch-shifts with speed, which is expected at non-1x).
        ghost.setBaselineRate(newRate)
    }

    func setVolume(_ newVolume: Float) {
        volume = min(max(newVolume, 0), 1)
        fadeTask?.cancel()
        autoFadeStarted = false
        outputGain = volume
        applyOutputGain()
        UserDefaults.standard.set(volume, forKey: "TrapTube.NativePlayer.Volume")
    }

    func setCrossfade(_ seconds: Double) {
        crossfadeSeconds = min(max(seconds, 0), 12)
        UserDefaults.standard.set(crossfadeSeconds, forKey: "TrapTube.NativePlayer.Crossfade")
    }

    func setEQEnabled(_ enabled: Bool) {
        eqEnabled = enabled
        TrapTubeTapEQ.shared.setEnabled(enabled)
        ghost.setEnabled(enabled)
    }

    func toggleFavorite() {
        guard let entry = currentEntry else { return }
        TrapTubeFavoritesStore.shared.toggle(entry)
        isFavorite = TrapTubeFavoritesStore.shared.contains(videoID: entry.videoID)
    }

    func cycleRepeatMode() {
        repeatMode = RepeatMode(rawValue: (repeatMode.rawValue + 1) % 3) ?? .off
    }

    // MARK: Queue

    func nextIndex(auto: Bool) -> Int? {
        guard !queue.isEmpty else { return nil }
        if isShuffled, queue.count > 1 {
            var candidate = queueIndex
            while candidate == queueIndex { candidate = Int.random(in: queue.indices) }
            return candidate
        }
        if queueIndex + 1 < queue.count { return queueIndex + 1 }
        if repeatMode == .all { return 0 }
        return nil
    }

    var hasNext: Bool { nextIndex(auto: false) != nil }
    var hasPrevious: Bool { queueIndex > 0 || repeatMode == .all }

    func playNext() {
        guard let target = nextIndex(auto: false) else { return }
        transition(to: target)
    }

    func playPrevious() {
        if currentTime > 3 {
            seek(toSeconds: 0)
        } else if queueIndex > 0 {
            transition(to: queueIndex - 1)
        } else if repeatMode == .all, !queue.isEmpty {
            transition(to: queue.count - 1)
        } else {
            seek(toSeconds: 0)
        }
    }

    func playQueueItem(at index: Int) {
        guard index != queueIndex, queue.indices.contains(index) else { return }
        transition(to: index)
    }

    private func transition(to index: Int) {
        let fade = crossfadeSeconds
        if fade > 0, isPlaying {
            rampVolume(to: 0, duration: min(fade, 0.7)) { [weak self] in
                self?.load(index: index, startAt: 0, fadeIn: min(fade, 1.2))
            }
        } else {
            load(index: index, startAt: 0, fadeIn: min(fade, 1.2))
        }
    }

    private func handleItemEnd() {
        isPlaying = false
        if repeatMode == .one {
            let fade = crossfadeSeconds
            if fade > 0 { outputGain = 0; applyOutputGain() }
            player.seek(to: .zero, toleranceBefore: .zero, toleranceAfter: .zero) { [weak self] _ in
                guard let self else { return }
                self.autoFadeStarted = false
                self.player.play()
                if self.rate != 1 { self.player.rate = self.rate }
                if self.itemUsesGhost, !self.usingFallbackTap, self.ghostFeed != .none {
                    self.ghost.setDesiredPlaying(true)
                    Task { [weak self] in await self?.hardResyncGhost() }
                }
                if fade > 0 { self.rampVolume(to: self.volume, duration: min(fade, 1.5)) }
            }
            return
        }
        if let target = nextIndex(auto: true) {
            load(index: target, startAt: 0, fadeIn: min(crossfadeSeconds, 2.0))
        } else {
            outputGain = volume
            applyOutputGain()
            currentTime = duration
        }
    }

    // MARK: Progress + crossfade

    private func tick(time: CMTime) {
        let seconds = time.seconds
        if seconds.isFinite, seconds >= 0 { currentTime = seconds }
        if let itemDuration = player.currentItem?.duration.seconds,
           itemDuration.isFinite, itemDuration > 0 {
            duration = itemDuration
        }
        let playing = player.timeControlStatus == .playing
        if playing != isPlaying { isPlaying = playing }
        if playing, rate != 1, abs(player.rate - rate) > 0.01 { player.rate = rate }
        // Crossfade: begin the fade-out early enough to land
        // exactly on the item's end; the next entry fades in.
        if crossfadeSeconds > 0, !autoFadeStarted, playing, duration > 0,
           case .playing = phase {
            let remaining = duration - currentTime
            if remaining <= crossfadeSeconds, remaining > 0.1,
               repeatMode == .one || nextIndex(auto: true) != nil {
                autoFadeStarted = true
                rampVolume(to: 0, duration: remaining)
            }
        }
    }

    private func rampVolume(to target: Float, duration: TimeInterval, completion: @escaping () -> Void = {}) {
        fadeTask?.cancel()
        guard duration > 0.05 else {
            outputGain = target
            applyOutputGain()
            completion()
            return
        }
        let start = outputGain
        let steps = max(4, Int(duration / 0.05))
        fadeTask = Task { [weak self] in
            for step in 1...steps {
                try? await Task.sleep(nanoseconds: UInt64(duration / Double(steps) * 1_000_000_000))
                guard !Task.isCancelled, let self else { return }
                self.outputGain = start + (target - start) * Float(step) / Float(steps)
                self.applyOutputGain()
            }
            guard !Task.isCancelled else { return }
            completion()
        }
    }

    // MARK: Stream construction (Round 6 crash-proofed)

    /// Muxed MP4 when YouTube offers one; otherwise an AVC + AAC
    /// composition built from the adaptive streams (the same pairing
    /// the download merge uses).
    private static func makePlayerItem(info: TrapTubeVideoInfo) async throws -> AVPlayerItem {
        if let muxed = info.muxed.first, let url = URL(string: muxed.url) {
            let asset = AVURLAsset(url: url, options: headerOptions(userAgent: muxed.userAgent.isEmpty ? info.userAgent : muxed.userAgent))
            return AVPlayerItem(asset: asset)
        }
        guard let video = info.adaptiveVideo.first(where: { $0.isAVCVideo }),
              let audio = info.audioOnly.first(where: { $0.isAACAudio }),
              let videoURL = URL(string: video.url),
              let audioURL = URL(string: audio.url) else {
            throw TrapTubeModError.unplayable("no stream this player can use (it needs a muxed MP4 or an AVC + AAC pair)")
        }
        let videoAsset = AVURLAsset(url: videoURL, options: headerOptions(userAgent: video.userAgent.isEmpty ? info.userAgent : video.userAgent))
        let audioAsset = AVURLAsset(url: audioURL, options: headerOptions(userAgent: audio.userAgent.isEmpty ? info.userAgent : audio.userAgent))
        guard let videoTrack = try await videoAsset.loadTracks(withMediaType: .video).first,
              let audioTrack = try await audioAsset.loadTracks(withMediaType: .audio).first else {
            throw TrapTubeModError.unplayable("the adaptive streams had no usable tracks")
        }
        // Round 6 defensive composition: insert ranges come from
        // each track's OWN loaded timeRange, clamped to the shorter
        // track - never from the assets' reported durations, which
        // can exceed a track's real range and make AVFoundation
        // raise (crash) instead of throwing.
        let videoRange = try await videoTrack.load(.timeRange)
        let audioRange = try await audioTrack.load(.timeRange)
        let target = CMTimeMinimum(videoRange.duration, audioRange.duration)
        guard videoRange.isValid, audioRange.isValid,
              target.isValid, target.isNumeric, target.seconds > 0 else {
            throw TrapTubeModError.unplayable("the adaptive streams reported no usable timeline")
        }
        let composition = AVMutableComposition()
        guard let compositionVideo = composition.addMutableTrack(withMediaType: .video, preferredTrackID: kCMPersistentTrackID_Invalid),
              let compositionAudio = composition.addMutableTrack(withMediaType: .audio, preferredTrackID: kCMPersistentTrackID_Invalid) else {
            throw TrapTubeModError.unplayable("could not build the playback composition")
        }
        do {
            try compositionVideo.insertTimeRange(CMTimeRange(start: videoRange.start, duration: target), of: videoTrack, at: .zero)
            try compositionAudio.insertTimeRange(CMTimeRange(start: audioRange.start, duration: target), of: audioTrack, at: .zero)
        } catch {
            throw TrapTubeModError.unplayable("could not assemble the video and audio streams (\(error.localizedDescription))")
        }
        if let transform = try? await videoTrack.load(.preferredTransform) {
            compositionVideo.preferredTransform = transform
        }
        return AVPlayerItem(asset: composition)
    }

    private static func headerOptions(userAgent: String) -> [String: Any] {
        ["AVURLAssetHTTPHeaderFieldsKey": ["User-Agent": userAgent, "Referer": "https://www.youtube.com/"]]
    }
}

final class TrapTubePlayerContainerView: UIView {
    override class var layerClass: AnyClass { AVPlayerLayer.self }
    var playerLayer: AVPlayerLayer { layer as! AVPlayerLayer }

    override init(frame: CGRect) {
        super.init(frame: frame)
        backgroundColor = .black
        playerLayer.videoGravity = .resizeAspect
    }

    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }
}

struct TrapTubePlayerLayerView: UIViewRepresentable {
    let player: AVPlayer
    let onLayer: (AVPlayerLayer) -> Void

    func makeUIView(context: Context) -> TrapTubePlayerContainerView {
        let view = TrapTubePlayerContainerView()
        view.playerLayer.player = player
        onLayer(view.playerLayer)
        return view
    }

    func updateUIView(_ uiView: TrapTubePlayerContainerView, context: Context) {
        if uiView.playerLayer.player !== player { uiView.playerLayer.player = player }
        onLayer(uiView.playerLayer)
    }
}

/// Fullscreen via AVPlayerViewController on the same AVPlayer -
/// the same surface SwiftUI's VideoPlayer used in Rounds 5/6, so
/// its native chrome (including its own PiP button) is unchanged.
enum TrapTubeFullscreenPresenter {
    static func present(player: AVPlayer) {
        guard let top = topViewController() else { return }
        let controller = AVPlayerViewController()
        controller.player = player
        controller.allowsPictureInPicturePlayback = true
        controller.modalPresentationStyle = .fullScreen
        top.present(controller, animated: true)
    }

    private static func topViewController() -> UIViewController? {
        let scene = UIApplication.shared.connectedScenes
            .compactMap { $0 as? UIWindowScene }
            .first { $0.activationState == .foregroundActive }
        let window = scene?.windows.first { $0.isKeyWindow } ?? scene?.windows.first
        var top = window?.rootViewController
        while let presented = top?.presentedViewController { top = presented }
        return top
    }
}

struct TrapTubeRoutePicker: UIViewRepresentable {
    let tint: Color

    func makeUIView(context: Context) -> AVRoutePickerView {
        let view = AVRoutePickerView()
        view.backgroundColor = .clear
        view.tintColor = .white
        view.activeTintColor = UIColor(tint)
        view.prioritizesVideoDevices = true
        return view
    }

    func updateUIView(_ uiView: AVRoutePickerView, context: Context) {
        uiView.activeTintColor = UIColor(tint)
    }
}

/// The thin seek line from the reference: gray track, accent fill,
/// drag and tap both seek.
struct TrapTubeSeekBar: View {
    let progress: Double
    let tint: Color
    let onSeek: (Double) -> Void
    @State private var dragFraction: Double?

    private var shownFraction: Double { min(max(dragFraction ?? progress, 0), 1) }

    var body: some View {
        GeometryReader { geo in
            let width = max(geo.size.width, 1)
            ZStack(alignment: .leading) {
                Capsule().fill(.white.opacity(0.22)).frame(height: 3)
                Capsule().fill(tint).frame(width: width * CGFloat(shownFraction), height: 3)
                Circle().fill(tint).frame(width: 11, height: 11)
                    .offset(x: width * CGFloat(shownFraction) - 5.5)
            }
            .frame(height: 18)
            .contentShape(Rectangle())
            .gesture(DragGesture(minimumDistance: 0)
                .onChanged { value in
                    dragFraction = min(max(Double(value.location.x / width), 0), 1)
                }
                .onEnded { value in
                    let fraction = min(max(Double(value.location.x / width), 0), 1)
                    dragFraction = nil
                    onSeek(fraction)
                })
        }
        .frame(height: 18)
    }
}

/// Title that scrolls horizontally (marquee) when it overflows,
/// like the reference; static when it fits.
struct TrapTubeMarqueeText: View {
    let text: String
    let font: Font
    let uiFont: UIFont
    @State private var offset: CGFloat = 0

    var body: some View {
        GeometryReader { geo in
            let textWidth = (text as NSString).size(withAttributes: [.font: uiFont]).width
            let overflows = textWidth > geo.size.width + 1
            ZStack(alignment: .leading) {
                HStack(spacing: 48) {
                    Text(text).font(font).foregroundStyle(.white).lineLimit(1)
                        .fixedSize(horizontal: true, vertical: false)
                    if overflows {
                        Text(text).font(font).foregroundStyle(.white).lineLimit(1)
                            .fixedSize(horizontal: true, vertical: false)
                    }
                }
                .offset(x: offset)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .clipped()
            .onAppear { restart(textWidth: textWidth, containerWidth: geo.size.width) }
            .onChange(of: text) { _, _ in restart(textWidth: textWidth, containerWidth: geo.size.width) }
        }
    }

    private func restart(textWidth: CGFloat, containerWidth: CGFloat) {
        offset = 0
        guard textWidth > containerWidth + 1 else { return }
        let distance = textWidth + 48
        withAnimation(.linear(duration: Double(distance) / 42).delay(1.4).repeatForever(autoreverses: false)) {
            offset = -distance
        }
    }
}

struct TrapTubeNativeStreamPlayer: View {
    let request: TrapTubeNativePlayRequest

    @Environment(\.dismiss) private var dismiss
    @EnvironmentObject private var audio: AudioEngineManager
    @EnvironmentObject private var theme: ThemeManager
    @ObservedObject private var session = TrapTubeNativeSession.shared
    @State private var showEqualizer = false
    @State private var showQueue = false
    @State private var showDownload = false

    var body: some View {
        ZStack {
            theme.background.ignoresSafeArea()
            VStack(spacing: 0) {
                header
                videoArea
                seekRow
                titleBlock
                transportRow
                volumeRow
                actionRow
                statusRow
                Spacer(minLength: 0)
            }
        }
        .background(.black)
        .task { session.begin(request: request) }
        .onChange(of: audio.eqGains) { _, _ in TrapTubeTapEQ.shared.update(gains: audio.eqGains, bass: audio.bassBoost, master: audio.masterGain) }
        .onChange(of: audio.bassBoost) { _, _ in TrapTubeTapEQ.shared.update(gains: audio.eqGains, bass: audio.bassBoost, master: audio.masterGain) }
        .onChange(of: audio.masterGain) { _, _ in TrapTubeTapEQ.shared.update(gains: audio.eqGains, bass: audio.bassBoost, master: audio.masterGain) }
        .sheet(isPresented: $showEqualizer) {
            TrapTubePlayerEQSheet()
                .environmentObject(audio).environmentObject(theme)
                .presentationDetents([.large])
                .preferredColorScheme(.dark)
        }
        .sheet(isPresented: $showQueue) {
            TrapTubeQueueView()
                .environmentObject(theme)
                .presentationDetents([.large])
                .preferredColorScheme(.dark)
        }
        .sheet(isPresented: $showDownload) {
            TrapTubeModDownloadSheet(videoID: session.currentEntry?.videoID ?? request.videoID, preloaded: session.currentInfo)
                .presentationDetents([.large])
                .presentationDragIndicator(.visible)
                .preferredColorScheme(.dark)
        }
    }

    private var header: some View {
        HStack(alignment: .center) {
            Button { collapse() } label: {
                Image(systemName: "chevron.down")
                    .font(.system(size: 19, weight: .semibold)).foregroundStyle(.white)
                    .frame(width: 40, height: 40)
            }
            .accessibilityLabel("Collapse player")
            Spacer()
            VStack(spacing: 1) {
                Text("PLAYING FROM")
                    .font(.system(size: 9, weight: .bold)).tracking(1.6)
                    .foregroundStyle(.white.opacity(0.5))
                Text(session.contextName)
                    .font(.system(size: 13, weight: .semibold)).foregroundStyle(.white).lineLimit(1)
            }
            Spacer()
            Button { showQueue = true } label: {
                Image(systemName: "list.bullet")
                    .font(.system(size: 17, weight: .semibold)).foregroundStyle(.white)
                    .frame(width: 40, height: 40)
            }
            .accessibilityLabel("Show queue")
        }
        .padding(.horizontal, 8)
        .padding(.top, 6)
    }

    private func collapse() {
        // Collapsing keeps playback alive in the session (the mini
        // bar takes over) - except for a failed item, which is
        // torn down instead of haunting the bar.
        if session.failureMessage != nil { session.stop() }
        dismiss()
    }

    private var videoArea: some View {
        TrapTubePlayerLayerView(player: session.player) { layer in
            session.pipHolder.attach(layer: layer)
        }
        .aspectRatio(16 / 9, contentMode: .fit)
        .background(.black)
        .overlay(alignment: .topTrailing) {
            if session.pipHolder.isSupported {
                Button {
                    session.pipHolder.toggle()
                } label: {
                    Image(systemName: "pip.enter")
                        .font(.system(size: 14, weight: .semibold)).foregroundStyle(.white)
                        .frame(width: 34, height: 34)
                        .background(.black.opacity(0.55), in: Circle())
                        .overlay(Circle().stroke(.white.opacity(0.18), lineWidth: 1))
                }
                .padding(10)
                .accessibilityLabel("Picture in picture")
            }
        }
        .overlay(alignment: .bottomTrailing) {
            Button {
                TrapTubeFullscreenPresenter.present(player: session.player)
            } label: {
                Image(systemName: "arrow.up.left.and.arrow.down.right")
                    .font(.system(size: 13, weight: .semibold)).foregroundStyle(.white)
                    .frame(width: 34, height: 34)
                    .background(.black.opacity(0.55), in: Circle())
                    .overlay(Circle().stroke(.white.opacity(0.18), lineWidth: 1))
            }
            .padding(10)
            .accessibilityLabel("Fullscreen")
        }
        .overlay {
            if session.isResolving {
                ZStack {
                    Color.black.opacity(0.35)
                    VStack(spacing: 12) {
                        ProgressView().tint(.white)
                        Text("Resolving stream…")
                            .font(.subheadline.weight(.semibold)).foregroundStyle(.white.opacity(0.85))
                    }
                }
            }
        }
        .overlay {
            if let message = session.failureMessage {
                ZStack {
                    Color.black.opacity(0.72)
                    VStack(spacing: 12) {
                        Image(systemName: "exclamationmark.triangle.fill")
                            .font(.title2).foregroundStyle(Color(hex: "FF7A84"))
                        Text(message)
                            .font(.subheadline).foregroundStyle(.white)
                            .multilineTextAlignment(.center)
                            .fixedSize(horizontal: false, vertical: true)
                        HStack(spacing: 10) {
                            Button("Retry") { session.retry() }
                                .font(.subheadline.bold()).foregroundStyle(.white)
                                .padding(.horizontal, 16).padding(.vertical, 9)
                                .background(theme.accent, in: Capsule())
                            Button("Close") { session.stop(); dismiss() }
                                .font(.subheadline.bold()).foregroundStyle(.white)
                                .padding(.horizontal, 16).padding(.vertical, 9)
                                .background(.white.opacity(0.12), in: Capsule())
                        }
                    }
                    .padding(24)
                }
            }
        }
    }

    private var seekRow: some View {
        VStack(spacing: 3) {
            TrapTubeSeekBar(progress: session.duration > 0 ? session.currentTime / session.duration : 0,
                            tint: theme.accent) { fraction in
                session.seek(toFraction: fraction)
            }
            .padding(.horizontal, 16)
            HStack {
                Text(TrapTubeNativeSession.timeLabel(session.currentTime))
                Spacer()
                Text(session.remainingLabel)
            }
            .font(.system(size: 11, weight: .medium).monospacedDigit())
            .foregroundStyle(.white.opacity(0.55))
            .padding(.horizontal, 16)
        }
        .padding(.top, -4)
    }

    private var titleBlock: some View {
        HStack(alignment: .top, spacing: 12) {
            VStack(alignment: .leading, spacing: 4) {
                TrapTubeMarqueeText(text: session.currentEntry?.title ?? request.title,
                                    font: .system(size: 20, weight: .bold),
                                    uiFont: .systemFont(ofSize: 20, weight: .bold))
                    .frame(height: 26)
                Text(session.currentEntry?.channel ?? "")
                    .font(.subheadline).foregroundStyle(.white.opacity(0.55)).lineLimit(1)
            }
            Spacer(minLength: 4)
            Button {
                session.toggleFavorite()
            } label: {
                Image(systemName: session.isFavorite ? "heart.fill" : "heart")
                    .font(.system(size: 21, weight: .semibold))
                    .foregroundStyle(session.isFavorite ? theme.accent : .white.opacity(0.85))
                    .frame(width: 40, height: 40)
            }
            .accessibilityLabel(session.isFavorite ? "Remove from favorites" : "Add to favorites")
        }
        .padding(.horizontal, 20)
        .padding(.top, 14)
    }

    private var transportRow: some View {
        HStack(alignment: .center) {
            Spacer()
            transportButton(systemName: "shuffle", active: session.isShuffled, disabled: session.queue.count < 2) {
                session.isShuffled.toggle()
            }
            Spacer()
            transportButton(systemName: "backward.end.fill", active: false, disabled: false) {
                session.playPrevious()
            }
            Spacer()
            Button {
                session.togglePlay()
            } label: {
                Image(systemName: session.isPlaying ? "pause.fill" : "play.fill")
                    .font(.system(size: 27, weight: .bold))
                    .foregroundStyle(.white)
                    .offset(x: session.isPlaying ? 0 : 2)
                    .frame(width: 66, height: 66)
                    .background(theme.accent, in: Circle())
                    .shadow(color: theme.accent.opacity(0.55), radius: 16, y: 4)
            }
            .accessibilityLabel(session.isPlaying ? "Pause" : "Play")
            Spacer()
            transportButton(systemName: "forward.end.fill", active: false, disabled: !session.hasNext) {
                session.playNext()
            }
            Spacer()
            transportButton(systemName: session.repeatMode == .one ? "repeat.1" : "repeat",
                            active: session.repeatMode != .off, disabled: false) {
                session.cycleRepeatMode()
            }
            Spacer()
        }
        .padding(.horizontal, 26)
        .padding(.top, 18)
    }

    private func transportButton(systemName: String, active: Bool, disabled: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Image(systemName: systemName)
                .font(.system(size: 19, weight: .semibold))
                .foregroundStyle(active ? theme.accent : .white.opacity(0.9))
                .frame(width: 44, height: 44)
        }
        .disabled(disabled)
        .opacity(disabled ? 0.3 : 1)
    }

    private var volumeRow: some View {
        HStack(spacing: 12) {
            Image(systemName: "speaker.fill")
                .font(.system(size: 13)).foregroundStyle(.white.opacity(0.55))
            Slider(value: Binding(get: { Double(session.volume) }, set: { session.setVolume(Float($0)) }), in: 0...1)
                .tint(theme.accent)
            Image(systemName: "speaker.waveform.3.fill")
                .font(.system(size: 15)).foregroundStyle(.white.opacity(0.55))
        }
        .padding(.horizontal, 22)
        .padding(.top, 16)
    }

    private var actionRow: some View {
        HStack {
            Spacer()
            actionButton(systemName: "plus", label: "Download this video") { showDownload = true }
            Spacer()
            actionButton(systemName: "slider.vertical.3", label: "Equalizer",
                         tint: session.eqAudiblyActive ? theme.accent : .white) { showEqualizer = true }
            Spacer()
            TrapTubeRoutePicker(tint: theme.accent)
                .frame(width: 40, height: 40)
            Spacer()
            actionButton(systemName: "list.bullet", label: "Queue") { showQueue = true }
            Spacer()
            ShareLink(item: shareURL) {
                Image(systemName: "square.and.arrow.up")
                    .font(.system(size: 19, weight: .semibold))
                    .foregroundStyle(.white)
                    .frame(width: 40, height: 40)
            }
            .accessibilityLabel("Share")
            Spacer()
        }
        .padding(.horizontal, 18)
        .padding(.top, 14)
    }

    private var shareURL: URL {
        URL(string: "https://www.youtube.com/watch?v=\(session.currentEntry?.videoID ?? request.videoID)")!
    }

    private func actionButton(systemName: String, label: String, tint: Color = .white, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Image(systemName: systemName)
                .font(.system(size: 19, weight: .semibold))
                .foregroundStyle(tint)
                .frame(width: 40, height: 40)
        }
        .accessibilityLabel(label)
    }

    private var statusRow: some View {
        Text(session.statusText)
            .font(.system(size: 10, weight: .bold))
            .tracking(1.2)
            .foregroundStyle(session.eqAudiblyActive ? theme.accent : .white.opacity(0.45))
            .padding(.top, 12)
    }
}

struct TrapTubeQueueView: View {
    @Environment(\.dismiss) private var dismiss
    @EnvironmentObject private var theme: ThemeManager
    @ObservedObject private var session = TrapTubeNativeSession.shared

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Up Next").font(.headline.bold()).foregroundStyle(.white)
                    Text(session.contextName).font(.caption).foregroundStyle(Color(hex: "A6A4A6"))
                }
                Spacer()
                Button { dismiss() } label: {
                    Image(systemName: "xmark").font(.headline.bold()).foregroundStyle(.white)
                        .frame(width: 38, height: 38).background(.white.opacity(0.12), in: Circle())
                }
                .accessibilityLabel("Close queue")
            }
            .padding(18)

            if session.queue.count <= 1 {
                VStack(spacing: 10) {
                    Image(systemName: "list.bullet").font(.system(size: 30)).foregroundStyle(Color(hex: "A6A4A6"))
                    Text("Just this video for now").font(.headline.bold()).foregroundStyle(.white)
                    Text("When YouTube offers a Mix for this video, the queue fills with its recommendations and playback auto-advances through it.")
                        .font(.caption).foregroundStyle(Color(hex: "A6A4A6"))
                        .multilineTextAlignment(.center)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .padding(28)
                Spacer()
            } else {
                ScrollView(showsIndicators: false) {
                    LazyVStack(spacing: 8) {
                        ForEach(Array(session.queue.enumerated()), id: \.element.id) { index, entry in
                            Button {
                                session.playQueueItem(at: index)
                                dismiss()
                            } label: {
                                HStack(spacing: 11) {
                                    AsyncImage(url: URL(string: "https://i.ytimg.com/vi/\(entry.videoID)/hqdefault.jpg")) { image in
                                        image.resizable().scaledToFill()
                                    } placeholder: {
                                        Color.white.opacity(0.07)
                                    }
                                    .frame(width: 84, height: 52)
                                    .clipShape(RoundedRectangle(cornerRadius: 9))
                                    VStack(alignment: .leading, spacing: 3) {
                                        Text(entry.title)
                                            .font(.subheadline.bold()).foregroundStyle(.white).lineLimit(2)
                                        Text(entry.channel)
                                            .font(.caption).foregroundStyle(Color(hex: "A6A4A6")).lineLimit(1)
                                    }
                                    Spacer(minLength: 4)
                                    if index == session.queueIndex {
                                        Image(systemName: "waveform").foregroundStyle(theme.accent)
                                    }
                                }
                                .padding(10)
                                .background(index == session.queueIndex ? theme.accent.opacity(0.13) : .white.opacity(0.045),
                                            in: RoundedRectangle(cornerRadius: 12))
                                .contentShape(Rectangle())
                            }
                            .buttonStyle(.plain)
                        }
                    }
                    .padding(.horizontal, 16)
                    .padding(.bottom, 16)
                }
            }
        }
        .background(Color(hex: "141315").ignoresSafeArea())
    }
}

/// Musi's "Settings" sheet for the native player: crossfade,
/// playback speed, the Enable Equalizer bypass toggle, ten vertical
/// band sliders, and Presets / Reset / Save As….
struct TrapTubePlayerEQSheet: View {
    @Environment(\.dismiss) private var dismiss
    @EnvironmentObject private var audio: AudioEngineManager
    @EnvironmentObject private var theme: ThemeManager
    @ObservedObject private var session = TrapTubeNativeSession.shared
    @AppStorage("TrapTube.PlayerEQ.Preset") private var activePresetName = "Flat"
    @State private var showPresets = false
    @State private var showSavePrompt = false
    @State private var newPresetName = ""
    @State private var customs: [TrapTubeEQPreset] = TrapTubeEQPresetLib.customPresets()

    private let rates: [Float] = [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0]

    var body: some View {
        ZStack {
            Color(hex: "141315").ignoresSafeArea()
            if showPresets {
                presetsPage.transition(.move(edge: .trailing))
            } else {
                settingsPage.transition(.move(edge: .leading))
            }
        }
        .preferredColorScheme(.dark)
        .alert("Save Preset", isPresented: $showSavePrompt) {
            TextField("Preset name", text: $newPresetName)
            Button("Save") { saveCustomPreset() }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("Saves the current slider positions as your own preset.")
        }
    }

    private var settingsPage: some View {
        VStack(spacing: 0) {
            ZStack {
                Text("Settings").font(.headline.bold()).foregroundStyle(.white)
                HStack {
                    Button("Close") { dismiss() }
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(theme.accent)
                    Spacer()
                }
            }
            .padding(.horizontal, 20)
            .padding(.vertical, 14)

            ScrollView(showsIndicators: false) {
                VStack(alignment: .leading, spacing: 20) {
                    VStack(spacing: 9) {
                        HStack {
                            Text("Crossfade").font(.subheadline.weight(.semibold)).foregroundStyle(.white)
                            Spacer()
                            Text(session.crossfadeSeconds <= 0 ? "Off" : "\(Int(session.crossfadeSeconds))s")
                                .font(.subheadline.weight(.semibold)).foregroundStyle(theme.accent)
                        }
                        Slider(value: Binding(get: { session.crossfadeSeconds }, set: { session.setCrossfade($0) }),
                               in: 0...12, step: 1)
                            .tint(theme.accent)
                        Text("Fades the end of a track out and the next queue entry in.")
                            .font(.caption2).foregroundStyle(Color(hex: "A6A4A6"))
                    }

                    VStack(spacing: 9) {
                        HStack {
                            Text("Audio Path").font(.subheadline.weight(.semibold)).foregroundStyle(.white)
                            Spacer()
                            Text(session.usingFallbackTap ? "Tap (fallback)" : (session.audioPath == .ghost ? "Ghost" : "Tap"))
                                .font(.subheadline.weight(.semibold)).foregroundStyle(theme.accent)
                        }
                        Picker("Audio Path", selection: Binding(
                            get: { session.audioPath },
                            set: { session.setAudioPath($0) })) {
                            Text("Ghost").tag(TrapTubeNativeSession.AudioPath.ghost)
                            Text("Tap").tag(TrapTubeNativeSession.AudioPath.tap)
                        }
                        .pickerStyle(.segmented)
                        Text("Ghost (default) renders the audio through TrapTube's own engine and EQ while the video plays muted. Tap is the legacy in-stream processing. Switching restarts the current track at the same position.")
                            .font(.caption2).foregroundStyle(Color(hex: "A6A4A6"))
                            .fixedSize(horizontal: false, vertical: true)
                    }

                    Menu {
                        ForEach(rates, id: \.self) { rate in
                            Button {
                                session.setRate(rate)
                            } label: {
                                if rate == session.rate {
                                    Label(Self.rateText(rate), systemImage: "checkmark")
                                } else {
                                    Text(Self.rateText(rate))
                                }
                            }
                        }
                    } label: {
                        HStack {
                            Text("Playback Speed").font(.subheadline.weight(.semibold)).foregroundStyle(.white)
                            Spacer()
                            Text(Self.rateText(session.rate))
                                .font(.subheadline.weight(.semibold)).foregroundStyle(theme.accent)
                            Image(systemName: "chevron.up.chevron.down")
                                .font(.caption2.bold()).foregroundStyle(Color(hex: "A6A4A6"))
                        }
                        .contentShape(Rectangle())
                    }

                    Rectangle().fill(.white.opacity(0.1)).frame(height: 1)

                    HStack {
                        Text("Enable Equalizer").font(.subheadline.weight(.semibold)).foregroundStyle(.white)
                        Spacer()
                        Toggle("", isOn: Binding(get: { session.eqEnabled }, set: { session.setEQEnabled($0) }))
                            .labelsHidden()
                            .tint(theme.accent)
                    }

                    HStack(alignment: .top, spacing: 0) {
                        ForEach(0..<10, id: \.self) { position in
                            let modelIndex = TrapTubeEQPresetLib.displayIndices[position]
                            TrapTubeVerticalBand(
                                label: TrapTubeEQPresetLib.displayLabels[position],
                                gain: bandGain(at: position, modelIndex: modelIndex),
                                enabled: session.eqEnabled,
                                tint: theme.accent
                            ) { newGain in
                                setBand(position: position, modelIndex: modelIndex, gain: newGain)
                                activePresetName = "Custom"
                            }
                        }
                    }
                    .frame(maxWidth: .infinity)

                    HStack {
                        Button("Presets") { withAnimation(.easeInOut(duration: 0.22)) { showPresets = true } }
                        Spacer()
                        Button("Reset") { apply(TrapTubeEQPresetLib.flat) }
                        Spacer()
                        Button("Save As…") { newPresetName = ""; showSavePrompt = true }
                    }
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(theme.accent)
                    .buttonStyle(.plain)

                    Text("The 10 bands shown are the Musi layout (32 Hz – 16 kHz). On the Ghost path they drive the player's own EQ unit directly; on the Tap path they are exact members of the app's 16-band engine. While the equalizer is off, audio passes through untouched and the sliders keep their positions.")
                        .font(.caption2).foregroundStyle(Color(hex: "A6A4A6"))
                        .fixedSize(horizontal: false, vertical: true)
                }
                .padding(20)
            }
        }
    }

    private var presetsPage: some View {
        VStack(spacing: 0) {
            ZStack {
                Text("Choose Preset").font(.headline.bold()).foregroundStyle(.white)
                HStack {
                    Button {
                        withAnimation(.easeInOut(duration: 0.22)) { showPresets = false }
                    } label: {
                        HStack(spacing: 4) {
                            Image(systemName: "chevron.left").font(.system(size: 13, weight: .bold))
                            Text("Settings").font(.subheadline.weight(.semibold))
                        }
                        .foregroundStyle(theme.accent)
                    }
                    Spacer()
                }
            }
            .padding(.horizontal, 20)
            .padding(.vertical, 14)

            List {
                Section {
                    ForEach(TrapTubeEQPresetLib.builtins) { preset in presetRow(preset) }
                }
                if !customs.isEmpty {
                    Section("Your Presets") {
                        ForEach(customs) { preset in presetRow(preset) }
                            .onDelete { offsets in
                                TrapTubeEQPresetLib.deleteCustoms(at: offsets)
                                customs = TrapTubeEQPresetLib.customPresets()
                            }
                    }
                }
            }
            .listStyle(.plain)
            .scrollContentBackground(.hidden)
        }
    }

    private func presetRow(_ preset: TrapTubeEQPreset) -> some View {
        Button {
            apply(preset)
            withAnimation(.easeInOut(duration: 0.22)) { showPresets = false }
        } label: {
            HStack {
                Text(preset.name).foregroundStyle(.white)
                Spacer()
                if activePresetName == preset.name {
                    Image(systemName: "checkmark")
                        .font(.subheadline.bold()).foregroundStyle(theme.accent)
                }
            }
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .listRowBackground(Color.white.opacity(0.045))
        .listRowSeparatorTint(.white.opacity(0.08))
    }

    /// While the ghost feed is live, the sliders and presets
    /// bind straight to its AVAudioUnitEQ (the 10 anchors ARE the
    /// unit's bands). Otherwise they drive the app's 16-band
    /// engine model, expanded by log-frequency interpolation.
    private var ghostLive: Bool { session.ghostFeed != .none }

    private func bandGain(at position: Int, modelIndex: Int) -> Float {
        ghostLive ? session.ghost.bandGain(position) : audio.eqGains[modelIndex]
    }

    private func setBand(position: Int, modelIndex: Int, gain: Float) {
        if ghostLive {
            session.ghost.setBand(position, gain: gain)
        } else {
            audio.setBand(modelIndex, gain: gain)
        }
    }

    private func apply(_ preset: TrapTubeEQPreset) {
        if ghostLive {
            session.ghost.applyCurve(preset.anchors)
        } else {
            let gains = TrapTubeEQPresetLib.expand(preset.anchors)
            for index in 0..<16 { audio.setBand(index, gain: gains[index]) }
            audio.setBassBoost(preset.bass)
        }
        activePresetName = preset.name
    }

    private func saveCustomPreset() {
        let name = newPresetName.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !name.isEmpty else { return }
        let anchors = ghostLive
            ? (0..<10).map { session.ghost.bandGain($0) }
            : TrapTubeEQPresetLib.displayIndices.map { audio.eqGains[$0] }
        let preset = TrapTubeEQPreset(name: name, anchors: anchors, bass: audio.bassBoost)
        TrapTubeEQPresetLib.saveCustom(preset)
        customs = TrapTubeEQPresetLib.customPresets()
        activePresetName = name
    }

    static func rateText(_ rate: Float) -> String {
        if rate == 1 { return "1x" }
        return String(format: "%gx", Double(rate))
    }
}

private struct TrapTubeVerticalBand: View {
    let label: String
    let gain: Float
    let enabled: Bool
    let tint: Color
    let onChange: (Float) -> Void

    var body: some View {
        VStack(spacing: 7) {
            GeometryReader { geo in
                let height = geo.size.height
                let width = geo.size.width
                let clamped = min(max(gain, -12), 12)
                let fraction = CGFloat((clamped + 12) / 24)
                let knobY = height * (1 - fraction)
                let fillHeight = max(height * fraction, 3)
                ZStack {
                    Capsule().fill(.white.opacity(0.13))
                        .frame(width: 5, height: height)
                        .position(x: width / 2, y: height / 2)
                    Capsule().fill(tint)
                        .frame(width: 5, height: fillHeight)
                        .position(x: width / 2, y: height - fillHeight / 2)
                    Rectangle().fill(.white.opacity(0.4))
                        .frame(width: 12, height: 1)
                        .position(x: width / 2, y: height / 2)
                    Circle().fill(.white)
                        .frame(width: 15, height: 15)
                        .shadow(color: .black.opacity(0.35), radius: 3)
                        .position(x: width / 2, y: knobY)
                }
                .contentShape(Rectangle())
                .gesture(DragGesture(minimumDistance: 0).onChanged { gesture in
                    let f = min(max(1 - gesture.location.y / max(height, 1), 0), 1)
                    onChange(Float(f * 24 - 12))
                })
            }
            .frame(width: 26, height: 168)
            Text(label)
                .font(.system(size: 10, weight: .semibold, design: .rounded))
                .foregroundStyle(.white.opacity(0.85))
        }
        .frame(maxWidth: .infinity)
        .opacity(enabled ? 1 : 0.35)
        .allowsHitTesting(enabled)
        .accessibilityElement()
        .accessibilityLabel("\(label) hertz equalizer band")
        .accessibilityValue("\(Int(gain)) decibels")
    }
}

/// The native mini bar in RootView's bottom inset: shown while
/// the session has content and the full player is collapsed.
struct TrapTubeNativeMiniBar: View {
    @EnvironmentObject private var theme: ThemeManager
    @ObservedObject private var session = TrapTubeNativeSession.shared

    var body: some View {
        if let entry = session.currentEntry {
            HStack(spacing: 10) {
                Button {
                    TrapTubeNativePlayCenter.shared.reopenSession()
                } label: {
                    HStack(spacing: 10) {
                        AsyncImage(url: URL(string: "https://i.ytimg.com/vi/\(entry.videoID)/hqdefault.jpg")) { image in
                            image.resizable().scaledToFill()
                        } placeholder: {
                            Color.white.opacity(0.07)
                        }
                        .frame(width: 54, height: 34)
                        .clipShape(RoundedRectangle(cornerRadius: 7))
                        VStack(alignment: .leading, spacing: 2) {
                            Text(entry.title)
                                .font(.caption.bold()).foregroundStyle(.white).lineLimit(1)
                            Text(miniStatusText(entry: entry))
                                .font(.caption2).foregroundStyle(Color(hex: "A6A4A6")).lineLimit(1)
                        }
                    }
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)

                Spacer(minLength: 4)

                if session.hasNext {
                    Button { session.playNext() } label: {
                        Image(systemName: "forward.end.fill")
                            .font(.system(size: 15, weight: .semibold)).foregroundStyle(.white)
                            .frame(width: 34, height: 34)
                    }
                    .accessibilityLabel("Next")
                }
                Button { session.togglePlay() } label: {
                    Image(systemName: session.isPlaying ? "pause.fill" : "play.fill")
                        .font(.system(size: 16, weight: .bold)).foregroundStyle(.white)
                        .frame(width: 34, height: 34)
                        .background(theme.accent, in: Circle())
                }
                .accessibilityLabel(session.isPlaying ? "Pause" : "Play")
                Button { session.stop() } label: {
                    Image(systemName: "xmark")
                        .font(.system(size: 12, weight: .bold)).foregroundStyle(.white.opacity(0.7))
                        .frame(width: 30, height: 30)
                }
                .accessibilityLabel("Stop playback")
            }
            .padding(.horizontal, 10)
            .padding(.vertical, 5)
        }
    }

    private func miniStatusText(entry: TrapTubeQueueItem) -> String {
        if session.failureMessage != nil { return "Playback failed — tap play to retry" }
        if session.isResolving { return "Resolving…" }
        return entry.channel.isEmpty ? session.contextName : entry.channel
    }
}
'''
if "Round 7 native stream player" not in s:
    r7_marker = "\n// MARK: - Round 6 native stream player"
    if r7_marker not in s:
        raise SystemExit("round7 native player anchor missing")
    s = s[:s.index(r7_marker)] + ROUND7_NATIVE_PLAYER_SWIFT + "\n"
p.write_text(s)


# =====================================================================
# Round 9: STOP GUESSING - crash-trail instrumentation for the
# native player's audio start path, plus the one proven defect on
# the causal path (nil AVAudioConverter cached by format).
#
# Two audit rounds fixed what code reading could prove and the
# device still crashed - per the user, "right after it says eq
# attaching". So this round's primary deliverable is EVIDENCE: a
# persistent breadcrumb trail (TrapTubeCrashTrail) that survives a
# hard crash and names the exact last step on the next launch.
# Round 8 invariants stay untouched: canonical stream format,
# feed generation counter, connectGraph Bool, STREAMED -> FILE ->
# TAP ladder, honest status text.
# =====================================================================

p = file("YouTubeView.swift")
s = p.read_text()

# --- The crash trail type itself, inserted before the ghost section.
s = rep(s, r'''// MARK: - Ghost audio path (Round 7)''',
        r'''// MARK: - Crash trail (Round 9)
//
// Diagnosis-first instrumentation for the native player's audio
// start path. Every stage of session start, resolve, the ghost
// primes, the tap attach sequence and the EQ layer appends one
// short line to a small file in Application Support, and each
// append ends in synchronize() (fsync), so the last line
// survives a hard crash and is read back on the next launch as
// "Last run reached: ..." in the player's status area.
//
// Why a file and not UserDefaults: defaults writes are buffered
// by cfprefsd and flushed on its schedule, so a crash can lose
// the final steps - exactly the ones that matter. A direct file
// write + fsync is durable across a process crash.
//
// The one place that must never do file I/O is the audio tap's
// render callbacks. Those write step codes into preallocated
// slots on TapState instead (see AudioEngineManager.swift), and
// a main-queue flusher turns new codes into trail lines.
enum TrapTubeCrashTrail {
    private static let queue = DispatchQueue(label: "com.traptube.crashtrail")
    private static let startUptime = ProcessInfo.processInfo.systemUptime
    private static var storedPreviousSummary: String?

    /// Runs exactly once, on first touch from ANY entry point,
    /// before that entry point writes: reads the previous run's
    /// trail (the summary the player surfaces) and trims the file.
    private static let boot: Void = TrapTubeCrashTrail.performBoot()

    private static let fileURL: URL? = {
        let manager = FileManager.default
        let base = manager.urls(for: .applicationSupportDirectory, in: .userDomainMask).first
            ?? manager.urls(for: .documentDirectory, in: .userDomainMask).first
        guard let base else { return nil }
        let directory = base.appendingPathComponent("TrapTube", isDirectory: true)
        try? manager.createDirectory(at: directory, withIntermediateDirectories: true)
        return directory.appendingPathComponent("crash-trail.log")
    }()

    static var previousRunSummary: String? {
        _ = boot
        return storedPreviousSummary
    }

    private static func performBoot() {
        guard let fileURL else { return }
        guard let text = try? String(contentsOf: fileURL, encoding: .utf8) else {
            FileManager.default.createFile(atPath: fileURL.path, contents: nil)
            return
        }
        let lines = text.split(separator: "\n").map(String.init)
        storedPreviousSummary = summarize(lines)
        if text.utf8.count > 65_536 {
            let tail = lines.suffix(120).joined(separator: "\n") + "\n"
            try? tail.write(to: fileURL, atomically: true, encoding: .utf8)
        }
    }

    private static func summarize(_ lines: [String]) -> String? {
        let meaningful = lines.filter { !$0.contains("heartbeat") }
        guard let last = meaningful.last else { return nil }
        if last.contains("session stop (clean)") { return nil }
        // A previous run that reached healthy playback after its
        // last load began left no crash residue to surface.
        var sawLoad = false
        var healthyAfterLoad = false
        for line in meaningful {
            if line.contains("load begin") { sawLoad = true; healthyAfterLoad = false }
            if line.contains("run healthy") { healthyAfterLoad = true }
        }
        if sawLoad && healthyAfterLoad { return nil }
        let step = stripTimestamp(last)
        let facts = meaningful.last {
            $0.contains("(track fmt:") || $0.contains("prepare (fmt:") || $0.contains("canonical format")
        }
        if let facts, facts != last { return step + " | " + stripTimestamp(facts) }
        return step
    }

    private static func stripTimestamp(_ line: String) -> String {
        guard let close = line.firstIndex(of: "]") else { return line }
        return String(line[line.index(after: close)...]).trimmingCharacters(in: .whitespaces)
    }

    /// Synchronous append + fsync: when record() returns, the
    /// step is durable even if the very next statement crashes.
    /// Called from the session, the ghost and attach - never
    /// from a render callback.
    static func record(_ step: String) {
        _ = boot
        queue.sync {
            guard let fileURL, let handle = try? FileHandle(forWritingTo: fileURL) else { return }
            let elapsed = ProcessInfo.processInfo.systemUptime - startUptime
            let line = String(format: "[%7.2fs] %@\n", elapsed, step)
            _ = try? handle.seekToEnd()
            if let data = line.data(using: .utf8) { try? handle.write(contentsOf: data) }
            try? handle.synchronize()
            try? handle.close()
        }
    }

    /// Detached liveness markers at +3s/+6s/+10s after a load or
    /// an attach begins: if they keep landing while the UI is
    /// frozen, the process was alive (a hang); if they stop, it
    /// died (a crash).
    static func armHeartbeat() {
        Task.detached {
            let marks: [(delay: UInt64, label: String)] = [
                (3_000_000_000, "+3s"), (3_000_000_000, "+6s"), (4_000_000_000, "+10s")
            ]
            for mark in marks {
                try? await Task.sleep(nanoseconds: mark.delay)
                record("heartbeat \(mark.label)")
            }
        }
    }

    // MARK: Format facts

    static func describeASBD(_ asbd: AudioStreamBasicDescription) -> String {
        let isFloat = (asbd.mFormatFlags & kAudioFormatFlagIsFloat) != 0
        let nonInterleaved = (asbd.mFormatFlags & kAudioFormatFlagIsNonInterleaved) != 0
        return "\(Int(asbd.mSampleRate)) Hz, \(asbd.mChannelsPerFrame) ch, \(isFloat ? "float" : "int")\(asbd.mBitsPerChannel), \(nonInterleaved ? "non-interleaved" : "interleaved")"
    }

    static func describeAudioFormat(_ format: AVAudioFormat) -> String {
        describeASBD(format.streamDescription.pointee)
    }

    /// The reader track's ACTUAL emitted format description -
    /// the fact two audit rounds could only guess at.
    static func describeTrackFormat(_ track: AVAssetTrack) -> String {
        guard let first = track.formatDescriptions.first else { return "unavailable" }
        let desc = first as CMFormatDescription
        guard let asbd = CMAudioFormatDescriptionGetStreamBasicDescription(desc)?.pointee else { return "unavailable" }
        var layoutTag: UInt32 = 0
        var layoutSize = 0
        if let layout = CMAudioFormatDescriptionGetChannelLayout(desc, sizeOut: &layoutSize) {
            layoutTag = layout.pointee.mChannelLayoutTag
        }
        return describeASBD(asbd) + ", layout tag \(layoutTag)"
    }

    static func trackMatchesCanonical(_ track: AVAssetTrack, canonical: AVAudioFormat) -> Bool {
        guard let first = track.formatDescriptions.first else { return false }
        let desc = first as CMFormatDescription
        return AVAudioFormat(cmAudioFormatDescription: desc) == canonical
    }

    static func describeSampleBufferFormat(_ sampleBuffer: CMSampleBuffer) -> String {
        guard let desc = CMSampleBufferGetFormatDescription(sampleBuffer),
              let asbd = CMAudioFormatDescriptionGetStreamBasicDescription(desc)?.pointee else { return "unavailable" }
        return describeASBD(asbd)
    }
}

// MARK: - Ghost audio path (Round 7)''',
        "round9 crash trail type")

# --- Ghost: first-conversion breadcrumb flag.
s = rep(s, r'''    private var streamConverter: AVAudioConverter?
    private var streamConverterFormat: AVAudioFormat?''',
        r'''    private var streamConverter: AVAudioConverter?
    private var streamConverterFormat: AVAudioFormat?
    /// Round 9: the first conversion outcome is breadcrumbed
    /// once per start() (reset there).
    private var trailConversionRecorded = false''',
        "round9 ghost converter flag")

# --- Ghost: applyParameters breadcrumb (only once connected, so
# the init-time call at singleton creation stays silent).
s = rep(s, r'''    private func applyParameters() {
        for (index, frequency) in Self.bandFrequencies.enumerated() {''',
        r'''    private func applyParameters() {
        if connected { TrapTubeCrashTrail.record("ghost applyParameters") }
        for (index, frequency) in Self.bandFrequencies.enumerated() {''',
        "round9 ghost applyParameters crumb")

# --- Ghost: start() breadcrumbs.
s = rep(s, r'''    func start(source: Source, position: @escaping () -> TimeInterval) async -> Feed {
        self.source = source
        teardownFeed(deleteTemp: true)''',
        r'''    func start(source: Source, position: @escaping () -> TimeInterval) async -> Feed {
        TrapTubeCrashTrail.record("ghost start begin")
        trailConversionRecorded = false
        self.source = source
        teardownFeed(deleteTemp: true)''',
        "round9 ghost start begin")
s = rep(s, r'''        feed = .none
        return .none
    }''',
        r'''        TrapTubeCrashTrail.record("ghost start -> none (both feeds failed)")
        feed = .none
        return .none
    }''',
        "round9 ghost start none")

# --- Ghost: primeStreamed breadcrumbs.
s = rep(s, r'''    private func primeStreamed(source: Source, startAt: TimeInterval) async -> Bool {
        let asset = AVURLAsset(url: source.url, options: [''',
        r'''    private func primeStreamed(source: Source, startAt: TimeInterval) async -> Bool {
        TrapTubeCrashTrail.record("ghost prime begin (streamed, startAt \(Int(startAt))s)")
        let asset = AVURLAsset(url: source.url, options: [''',
        "round9 prime streamed begin")
s = rep(s, r'''        guard let track = try? await asset.loadTracks(withMediaType: .audio).first,
              let format = streamFormat,
              let newReader = try? AVAssetReader(asset: asset) else { return false }''',
        r'''        guard let track = try? await asset.loadTracks(withMediaType: .audio).first,
              let format = streamFormat,
              let newReader = try? AVAssetReader(asset: asset) else { return false }
        TrapTubeCrashTrail.record("ghost reader created (track fmt: \(TrapTubeCrashTrail.describeTrackFormat(track)))")
        TrapTubeCrashTrail.record("ghost canonical format (\(TrapTubeCrashTrail.describeAudioFormat(format)); track matches canonical: \(TrapTubeCrashTrail.trackMatchesCanonical(track, canonical: format)))")''',
        "round9 reader created crumb")
s = rep(s, r'''        guard connectGraph(format: format) else { return false }
        node.stop()
        reader = newReader''',
        r'''        let graphOK = connectGraph(format: format)
        TrapTubeCrashTrail.record("ghost graph connect -> \(graphOK)")
        guard graphOK else { return false }
        node.stop()
        reader = newReader''',
        "round9 graph connect crumb")
s = rep(s, r'''        guard newReader.startReading() else {
            teardownFeed(deleteTemp: false)
            return false
        }
        feed = .streamed
        startPump()
        if !engine.isRunning { try? engine.start() }
        if desiredPlaying { node.play() }
        return true''',
        r'''        let reading = newReader.startReading()
        TrapTubeCrashTrail.record("ghost reader startReading -> \(reading)")
        guard reading else {
            teardownFeed(deleteTemp: false)
            return false
        }
        feed = .streamed
        startPump()
        if !engine.isRunning {
            try? engine.start()
            TrapTubeCrashTrail.record("ghost engine start -> \(engine.isRunning ? "running" : "FAILED")")
        }
        if desiredPlaying { node.play(); TrapTubeCrashTrail.record("ghost node play") }
        TrapTubeCrashTrail.record("ghost feed live (streamed)")
        return true''',
        "round9 startReading crumbs")

# --- Ghost: file route breadcrumbs.
s = rep(s, r'''        guard let downloaded = try? await TrapTubeDirectDownloader.shared.download(
            from: source.url, userAgent: source.userAgent, onProgress: { _ in }) else { return false }''',
        r'''        TrapTubeCrashTrail.record("ghost file prime begin (downloading)")
        let downloadedFile = try? await TrapTubeDirectDownloader.shared.download(
            from: source.url, userAgent: source.userAgent, onProgress: { _ in })
        TrapTubeCrashTrail.record("ghost file download -> \(downloadedFile != nil ? "ok" : "FAILED")")
        guard let downloaded = downloadedFile else { return false }''',
        "round9 file download crumbs")
s = rep(s, r'''        // A degenerate processing format would poison the
        // frame math below and the graph connection alike.
        guard format.sampleRate > 0, format.channelCount > 0 else { return false }''',
        r'''        // A degenerate processing format would poison the
        // frame math below and the graph connection alike.
        guard format.sampleRate > 0, format.channelCount > 0 else { return false }
        TrapTubeCrashTrail.record("ghost file opened (fmt: \(TrapTubeCrashTrail.describeAudioFormat(format)), duration \(Int(Double(file.length) / format.sampleRate))s)")''',
        "round9 file opened crumb")
s = rep(s, r'''        node.scheduleSegment(file, startingFrame: startFrame,
                             frameCount: AVAudioFrameCount(frames), at: nil)
        feed = .file
        if !engine.isRunning { try? engine.start() }
        if desiredPlaying { node.play() }
        return true''',
        r'''        node.scheduleSegment(file, startingFrame: startFrame,
                             frameCount: AVAudioFrameCount(frames), at: nil)
        TrapTubeCrashTrail.record("ghost file segment scheduled (\(frames) frames)")
        feed = .file
        if !engine.isRunning {
            try? engine.start()
            TrapTubeCrashTrail.record("ghost engine start -> \(engine.isRunning ? "running" : "FAILED")")
        }
        if desiredPlaying { node.play(); TrapTubeCrashTrail.record("ghost node play") }
        TrapTubeCrashTrail.record("ghost feed live (file)")
        return true''',
        "round9 file segment crumbs")

# --- Ghost: pump firsts.
s = rep(s, r'''        guard let pumpReader = reader, let pumpOutput = readerOutput else { return }
        let generation = feedGeneration
        pumpTask = Task { [weak self] in''',
        r'''        guard let pumpReader = reader, let pumpOutput = readerOutput else { return }
        let generation = feedGeneration
        var trailRawRecorded = false
        var trailScheduleRecorded = false
        pumpTask = Task { [weak self] in''',
        "round9 pump flags")
s = rep(s, r'''                if let sampleBuffer = pumpOutput.copyNextSampleBuffer() {''',
        r'''                if let sampleBuffer = pumpOutput.copyNextSampleBuffer() {
                    if !trailRawRecorded {
                        trailRawRecorded = true
                        TrapTubeCrashTrail.record("ghost first raw buffer (fmt: \(TrapTubeCrashTrail.describeSampleBufferFormat(sampleBuffer)))")
                    }''',
        "round9 first raw buffer crumb")
s = rep(s, r'''                        self.node.scheduleBuffer(pcm, completionHandler: nil)
                        self.scheduledFrames += AVAudioFramePosition(pcm.frameLength)
                        self.lastBufferAt = Date()''',
        r'''                        self.node.scheduleBuffer(pcm, completionHandler: nil)
                        if !trailScheduleRecorded {
                            trailScheduleRecorded = true
                            TrapTubeCrashTrail.record("ghost first scheduleBuffer (\(pcm.frameLength) frames)")
                        }
                        self.scheduledFrames += AVAudioFramePosition(pcm.frameLength)
                        self.lastBufferAt = Date()''',
        "round9 first schedule crumb")

# --- Ghost: conversion breadcrumbs + the proven nil-converter fix.
s = rep(s, r'''        if raw.format == target { return raw }''',
        r'''        if raw.format == target {
            if !trailConversionRecorded {
                trailConversionRecorded = true
                TrapTubeCrashTrail.record("ghost first conversion -> passthrough (raw already canonical)")
            }
            return raw
        }''',
        "round9 conversion passthrough crumb")
s = rep(s, r'''        if streamConverterFormat != raw.format {
            streamConverter = AVAudioConverter(from: raw.format, to: target)
            streamConverterFormat = raw.format
        }
        guard let converter = streamConverter, raw.frameLength > 0 else { return nil }''',
        r'''        if streamConverterFormat != raw.format {
            // Round 9 (proven defect on the crash's causal path):
            // a nil converter used to be cached by format anyway,
            // so one failed AVAudioConverter creation poisoned
            // every later buffer in that format for the ghost's
            // whole lifetime - the streamed feed could only
            // starve and escalate. Cache the format only on
            // success, so a later buffer may retry creation.
            let created = AVAudioConverter(from: raw.format, to: target)
            streamConverter = created
            streamConverterFormat = created != nil ? raw.format : nil
        }
        guard let converter = streamConverter, raw.frameLength > 0 else {
            if !trailConversionRecorded {
                trailConversionRecorded = true
                TrapTubeCrashTrail.record("ghost first conversion -> NIL CONVERTER (from \(TrapTubeCrashTrail.describeAudioFormat(raw.format)))")
            }
            return nil
        }''',
        "round9 converter nil fix")
s = rep(s, r'''        guard status != .error, converted.frameLength > 0 else { return nil }
        return converted''',
        r'''        if !trailConversionRecorded {
            trailConversionRecorded = true
            if status == .error {
                TrapTubeCrashTrail.record("ghost first conversion -> ERROR (status \(status.rawValue))")
            } else if converted.frameLength > 0 {
                TrapTubeCrashTrail.record("ghost first conversion -> ok (\(converted.frameLength) frames)")
            } else {
                TrapTubeCrashTrail.record("ghost first conversion -> empty output (status \(status.rawValue))")
            }
        }
        guard status != .error, converted.frameLength > 0 else { return nil }
        return converted''',
        "round9 conversion outcome crumb")

# --- Ghost: node play via setDesiredPlaying.
s = rep(s, r'''    func setDesiredPlaying(_ playing: Bool) {
        desiredPlaying = playing
        guard feed != .none else { return }
        if playing {
            if !engine.isRunning { try? engine.start() }
            node.play()
        } else {
            node.pause()
        }
    }''',
        r'''    func setDesiredPlaying(_ playing: Bool) {
        desiredPlaying = playing
        guard feed != .none else { return }
        if playing {
            if !engine.isRunning { try? engine.start() }
            node.play()
            TrapTubeCrashTrail.record("ghost node play (setDesiredPlaying)")
        } else {
            node.pause()
        }
    }''',
        "round9 setDesiredPlaying crumb")

# --- Session: last-run residue surface + healthy marker.
s = rep(s, r'''    @Published private(set) var driftMs: Int?
    @Published private(set) var usingFallbackTap = false''',
        r'''    @Published private(set) var driftMs: Int?
    /// Round 9 crash trail: the previous run's last recorded
    /// step (+ format facts), surfaced in the player's status
    /// area until a healthy play in this run clears it.
    @Published private(set) var lastRunReached: String?
    @Published private(set) var usingFallbackTap = false''',
        "round9 session lastRun property")
s = rep(s, r'''    private var lastHardResync = Date.distantPast''',
        r'''    private var lastHardResync = Date.distantPast
    private var trailHealthyRecorded = false''',
        "round9 session healthy flag")
s = rep(s, r'''    var remainingLabel: String {''',
        r'''    /// Round 9: a genuinely healthy play (ghost feed live,
    /// tap attached, or the first drift tick) retires the
    /// previous run's crash residue and marks this run healthy
    /// in the trail.
    private func markRunHealthy() {
        guard !trailHealthyRecorded else { return }
        trailHealthyRecorded = true
        lastRunReached = nil
        TrapTubeCrashTrail.record("run healthy")
    }

    var remainingLabel: String {''',
        "round9 markRunHealthy")

# --- Session: init reads the residue BEFORE this run writes.
s = rep(s, r'''        pipHolder.session = self
        player.addPeriodicTimeObserver(forInterval: CMTime(seconds: 0.25, preferredTimescale: 600), queue: .main) { [weak self] time in''',
        r'''        pipHolder.session = self
        // Round 9: read the previous run's crash residue BEFORE
        // this run's first trail write (the trail's boot read
        // happens on first touch, so the order matters here).
        lastRunReached = TrapTubeCrashTrail.previousRunSummary
        TrapTubeCrashTrail.record("app launch")
        player.addPeriodicTimeObserver(forInterval: CMTime(seconds: 0.25, preferredTimescale: 600), queue: .main) { [weak self] time in''',
        "round9 session init crumb")

# --- Session: setAudioPath / setEQEnabled breadcrumbs.
s = rep(s, r'''    func setAudioPath(_ path: AudioPath) {
        guard path != audioPath else { return }
        audioPath = path''',
        r'''    func setAudioPath(_ path: AudioPath) {
        guard path != audioPath else { return }
        audioPath = path
        TrapTubeCrashTrail.record("audio path set -> \(path.rawValue)")''',
        "round9 audio path crumb")
s = rep(s, r'''    func setEQEnabled(_ enabled: Bool) {
        eqEnabled = enabled
        TrapTubeTapEQ.shared.setEnabled(enabled)''',
        r'''    func setEQEnabled(_ enabled: Bool) {
        eqEnabled = enabled
        TrapTubeCrashTrail.record("eq enable toggled -> \(enabled ? "on" : "off")")
        TrapTubeTapEQ.shared.setEnabled(enabled)''',
        "round9 eq toggle crumb")

# --- Session: load() breadcrumbs + healthy on tap attach.
s = rep(s, r'''        currentTime = 0
        duration = 0
        autoFadeStarted = false
        itemUsesGhost = audioPath == .ghost''',
        r'''        currentTime = 0
        duration = 0
        autoFadeStarted = false
        trailHealthyRecorded = false
        TrapTubeCrashTrail.record("load begin (path: \(audioPath == .ghost ? "ghost" : "tap"))")
        TrapTubeCrashTrail.armHeartbeat()
        itemUsesGhost = audioPath == .ghost''',
        "round9 load begin crumb")
s = rep(s, r'''                let item = try await Self.makePlayerItem(info: info)''',
        r'''                let item = try await Self.makePlayerItem(info: info)
                TrapTubeCrashTrail.record("resolve done (\(info.muxed.isEmpty ? "composition avc+aac" : "muxed mp4"), ua: \(String(info.userAgent.prefix(24))))")''',
        "round9 resolve crumb")
s = rep(s, r'''                    self.attachTask = Task { [weak self] in
                        let attached = await TrapTubeTapEQ.shared.attach(to: item)''',
        r'''                    TrapTubeCrashTrail.record("tap attach begin (path: tap)")
                    self.attachTask = Task { [weak self] in
                        let attached = await TrapTubeTapEQ.shared.attach(to: item)''',
        "round9 tap begin crumb")
s = rep(s, r'''                        self.equalizerActive = attached
                        self.eqAttachFinished = true
                    }
                }
                // A single-video launch grows into the watch-next''',
        r'''                        self.equalizerActive = attached
                        self.eqAttachFinished = true
                        if attached { self.markRunHealthy() }
                    }
                }
                // A single-video launch grows into the watch-next''',
        "round9 tap healthy")

# --- Session: ghost start outcome + fallback breadcrumbs.
s = rep(s, r'''            if feed == .none {
                self.beginTapFallback(generation: loadGeneration, item: item)
                return
            }
            self.ghostFeed = feed
            self.equalizerActive = true
            self.eqAttachFinished = true''',
        r'''            TrapTubeCrashTrail.record("ghost start returned (\(feed == .none ? "none - tap fallback next" : (feed == .file ? "file" : "streamed")))")
            if feed == .none {
                self.beginTapFallback(generation: loadGeneration, item: item)
                return
            }
            self.ghostFeed = feed
            self.equalizerActive = true
            self.eqAttachFinished = true
            self.markRunHealthy()''',
        "round9 ghost outcome crumbs")
s = rep(s, r'''        attachTask?.cancel()
        attachTask = Task { [weak self] in
            let attached = await TrapTubeTapEQ.shared.attach(to: item)
            guard let self, self.generation == loadGeneration, self.playerItem === item else { return }
            self.equalizerActive = attached
            self.eqAttachFinished = true
        }''',
        r'''        attachTask?.cancel()
        TrapTubeCrashTrail.record("tap attach begin (path: ghost-fallback)")
        attachTask = Task { [weak self] in
            let attached = await TrapTubeTapEQ.shared.attach(to: item)
            guard let self, self.generation == loadGeneration, self.playerItem === item else { return }
            self.equalizerActive = attached
            self.eqAttachFinished = true
            if attached { self.markRunHealthy() }
        }''',
        "round9 fallback crumbs")

# --- Session: first drift tick breadcrumb.
s = rep(s, r'''        var waitingOnVideo = false''',
        r'''        var waitingOnVideo = false
        var trailDriftRecorded = false''',
        "round9 drift flag")
s = rep(s, r'''                let drift = audioTime - videoTime
                self.driftMs = Int((drift * 1000).rounded())''',
        r'''                let drift = audioTime - videoTime
                self.driftMs = Int((drift * 1000).rounded())
                if !trailDriftRecorded {
                    trailDriftRecorded = true
                    TrapTubeCrashTrail.record("ghost first drift tick (drift \(self.driftMs ?? 0) ms)")
                    self.markRunHealthy()
                }''',
        "round9 first drift crumb")

# --- Session: clean-stop marker + tick flushes tap breadcrumbs.
s = rep(s, r'''    func stop() {
        generation += 1''',
        r'''    func stop() {
        TrapTubeCrashTrail.record("session stop (clean)")
        generation += 1''',
        "round9 stop crumb")
s = rep(s, r'''    private func tick(time: CMTime) {
        let seconds = time.seconds''',
        r'''    private func tick(time: CMTime) {
        // Round 9: flush any new render-thread tap breadcrumbs.
        TrapTubeTapEQ.shared.drainTapTrail()
        let seconds = time.seconds''',
        "round9 tick drain")

# --- Player view: surface "Last run reached:" under the status.
s = rep(s, r'''    private var statusRow: some View {
        Text(session.statusText)
            .font(.system(size: 10, weight: .bold))
            .tracking(1.2)
            .foregroundStyle(session.eqAudiblyActive ? theme.accent : .white.opacity(0.45))
            .padding(.top, 12)
    }''',
        r'''    private var statusRow: some View {
        VStack(spacing: 3) {
            Text(session.statusText)
                .font(.system(size: 10, weight: .bold))
                .tracking(1.2)
                .foregroundStyle(session.eqAudiblyActive ? theme.accent : .white.opacity(0.45))
            if let lastRun = session.lastRunReached {
                Text("Last run reached: \(lastRun)")
                    .font(.system(size: 9, weight: .medium))
                    .foregroundStyle(.white.opacity(0.4))
                    .multilineTextAlignment(.center)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .padding(.top, 12)
    }''',
        "round9 status last run line")

# --- EQ sheet: opened + preset breadcrumbs.
s = rep(s, r'''        .preferredColorScheme(.dark)
        .alert("Save Preset", isPresented: $showSavePrompt) {''',
        r'''        .preferredColorScheme(.dark)
        .onAppear { TrapTubeCrashTrail.record("eq sheet opened (bind: \(ghostLive ? "ghost" : "tap-model"))") }
        .alert("Save Preset", isPresented: $showSavePrompt) {''',
        "round9 eq sheet crumb")
s = rep(s, r'''    private func apply(_ preset: TrapTubeEQPreset) {
        if ghostLive {''',
        r'''    private func apply(_ preset: TrapTubeEQPreset) {
        TrapTubeCrashTrail.record("eq preset applied (\(preset.name), bind: \(ghostLive ? "ghost" : "tap-model"))")
        if ghostLive {''',
        "round9 preset crumb")
p.write_text(s)

# =====================================================================
# AudioEngineManager.swift: the tap attach sequence at fine
# granularity, and the render-callback breadcrumb slots.
# =====================================================================
p = file("AudioEngineManager.swift")
s = p.read_text()

# --- TrapTubeTapEQ: last-state retention + the trail flusher.
s = rep(s, r'''    private let lock: UnsafeMutablePointer<os_unfair_lock>
    private let values: UnsafeMutablePointer<Float>
    private var version: UInt64 = 1''',
        r'''    private let lock: UnsafeMutablePointer<os_unfair_lock>
    private let values: UnsafeMutablePointer<Float>
    private var version: UInt64 = 1

    /// Round 9: the most recent tap's state, retained so the
    /// crash trail's flusher can drain its render-thread
    /// breadcrumb slots even after the tap is finalized.
    fileprivate private(set) var lastTapState: TapState?
    private var trailDrainedFor: ObjectIdentifier?
    private var trailDrainedCount = 0

    /// Main-queue flusher for the tap's render-thread breadcrumb
    /// slots: turns new step codes into crash-trail lines. Cheap
    /// no-op when nothing new was recorded. The slots are written
    /// by the tap's single render thread (CoreAudio serializes
    /// one tap's callbacks) with plain aligned 32-bit stores,
    /// the count stored last as the commit word; this reader
    /// formats only committed codes. (Format-flag facts: bit 0
    /// of the ASBD flags is kAudioFormatFlagIsFloat, bit 7 is
    /// kAudioFormatFlagIsNonInterleaved.)
    func drainTapTrail() {
        guard let state = lastTapState else { return }
        let identity = ObjectIdentifier(state)
        if trailDrainedFor != identity {
            trailDrainedFor = identity
            trailDrainedCount = 0
        }
        let available = min(Int(state.trailCount), 8)
        guard available > trailDrainedCount else { return }
        for index in trailDrainedCount..<available {
            let code = state.trailCodes[index]
            let a = state.trailValues[index * 4]
            let b = state.trailValues[index * 4 + 1]
            let c = state.trailValues[index * 4 + 2]
            let d = state.trailValues[index * 4 + 3]
            switch code {
            case 1:
                TrapTubeCrashTrail.record("tap callback: initialize")
            case 2:
                let floatWord = (c & 1) != 0 ? "float" : "int"
                let layoutWord = (c & 128) != 0 ? "non-interleaved" : "interleaved"
                TrapTubeCrashTrail.record("tap callback: prepare (fmt: \(a) Hz, \(b) ch, \(floatWord)\(d)-bit, \(layoutWord))")
            case 3:
                TrapTubeCrashTrail.record("tap callback: first frames rendered (\(a) frames)")
            case 4:
                TrapTubeCrashTrail.record("tap callback: unprepare")
            case 5:
                TrapTubeCrashTrail.record("tap callback: finalize")
            default:
                break
            }
        }
        trailDrainedCount = available
    }

    /// Round 9: after an audioMix assignment, drain on a short
    /// fuse so callback breadcrumbs land in the trail promptly
    /// even if nothing else ticks.
    func scheduleTrailDrains() {
        for delay in [0.05, 0.3, 1.0] {
            DispatchQueue.main.asyncAfter(deadline: .now() + delay) { [weak self] in
                self?.drainTapTrail()
            }
        }
    }''',
        "round9 tap trail flusher")

# --- attach(): fine-grained breadcrumbs around the sequence
# the user named ("crashes right after it says eq attaching").
s = rep(s, r'''    func attach(to item: AVPlayerItem) async -> Bool {
        // Round 5: never stack a second tap on an item that already
        // carries one (a re-attach on sheet re-presentation used to
        // orphan the first tap's retained state).
        if let existingParameters = item.audioMix?.inputParameters,
           existingParameters.contains(where: { $0.audioTapProcessor != nil }) {
            return true
        }
        guard let tracks = try? await item.asset.loadTracks(withMediaType: .audio), let track = tracks.first else { return false }
        let state = TapState()''',
        r'''    func attach(to item: AVPlayerItem) async -> Bool {
        TrapTubeCrashTrail.record("tap attach called")
        TrapTubeCrashTrail.armHeartbeat()
        // Round 5: never stack a second tap on an item that already
        // carries one (a re-attach on sheet re-presentation used to
        // orphan the first tap's retained state).
        let existingParameters = item.audioMix?.inputParameters
        TrapTubeCrashTrail.record("tap attach: audioMix read (existing tap: \(existingParameters?.contains(where: { $0.audioTapProcessor != nil }) ?? false))")
        if let existingParameters,
           existingParameters.contains(where: { $0.audioTapProcessor != nil }) {
            TrapTubeCrashTrail.record("tap attach: item already carries a tap")
            return true
        }
        let audioTracks = try? await item.asset.loadTracks(withMediaType: .audio)
        TrapTubeCrashTrail.record("tap attach: tracks loaded (audio track: \(audioTracks?.first != nil))")
        guard let track = audioTracks?.first else { return false }
        let state = TapState()
        lastTapState = state
        trailDrainedFor = nil
        trailDrainedCount = 0''',
        "round9 attach head crumbs")
s = rep(s, r'''        var tap: MTAudioProcessingTap?
        let status = MTAudioProcessingTapCreate(kCFAllocatorDefault, &callbacks, kMTAudioProcessingTapCreationFlag_PostEffects, &tap)
        guard status == noErr, let tap else {''',
        r'''        var tap: MTAudioProcessingTap?
        let status = MTAudioProcessingTapCreate(kCFAllocatorDefault, &callbacks, kMTAudioProcessingTapCreationFlag_PostEffects, &tap)
        TrapTubeCrashTrail.record("tap attach: TapCreate -> \(status == noErr ? "ok" : "OSStatus \(status)")")
        guard status == noErr, let tap else {''',
        "round9 tapcreate crumb")
s = rep(s, r'''        let parameters = AVMutableAudioMixInputParameters(track: track)
        parameters.audioTapProcessor = tap
        let mix = AVMutableAudioMix()
        mix.inputParameters = [parameters]
        item.audioMix = mix
        return true
    }''',
        r'''        let parameters = AVMutableAudioMixInputParameters(track: track)
        parameters.audioTapProcessor = tap
        TrapTubeCrashTrail.record("tap attach: mix params built")
        let mix = AVMutableAudioMix()
        mix.inputParameters = [parameters]
        item.audioMix = mix
        TrapTubeCrashTrail.record("tap attach: audioMix ASSIGNED")
        scheduleTrailDrains()
        TrapTubeCrashTrail.record("tap attach returned (attached: true)")
        return true
    }''',
        "round9 attach assign crumbs")

# --- TapState: preallocated breadcrumb slots. NOT freed by
# release() (prepare calls release() before noting its own
# step); they live and die with the state object.
s = rep(s, r'''    private var appliedVersion: UInt64 = 0
    private var preamp: Float = 1
    private let delayLength = 2 * TrapTubeTapEQ.sectionCount + 2''',
        r'''    private var appliedVersion: UInt64 = 0
    private var preamp: Float = 1
    private let delayLength = 2 * TrapTubeTapEQ.sectionCount + 2

    // Round 9 crash-trail slots (see TrapTubeCrashTrail): the
    // render callbacks note step codes here - plain aligned
    // 32-bit stores from the tap's one render thread, the count
    // stored last as the commit word - and the main-queue
    // flusher on TrapTubeTapEQ turns them into trail lines. No
    // locks, no allocation, no I/O on the render path.
    let trailCodes: UnsafeMutablePointer<Int32>
    let trailValues: UnsafeMutablePointer<Int32>
    var trailCount: Int32 = 0
    private var trailProcessNoted = false

    init() {
        trailCodes = .allocate(capacity: 8)
        trailCodes.initialize(repeating: 0, count: 8)
        trailValues = .allocate(capacity: 32)
        trailValues.initialize(repeating: 0, count: 32)
    }

    /// Render-thread breadcrumb: codes 1 initialize, 2 prepare,
    /// 3 first process, 4 unprepare, 5 finalize. Values carry
    /// per-code facts (prepare: sample rate, channels, format
    /// flags, bits per channel; process: frame count).
    func noteTrail(_ code: Int32, _ a: Int32 = 0, _ b: Int32 = 0, _ c: Int32 = 0, _ d: Int32 = 0) {
        let index = Int(trailCount)
        guard index < 8 else { return }
        trailCodes[index] = code
        trailValues[index * 4] = a
        trailValues[index * 4 + 1] = b
        trailValues[index * 4 + 2] = c
        trailValues[index * 4 + 3] = d
        trailCount = Int32(index + 1)
    }

    func noteProcessIfFirst(frames: Int32) {
        guard !trailProcessNoted else { return }
        trailProcessNoted = true
        noteTrail(3, frames)
    }''',
        "round9 tapstate trail slots")
s = rep(s, r'''    deinit { release() }''',
        r'''    deinit {
        release()
        trailCodes.deallocate()
        trailValues.deallocate()
    }''',
        "round9 tapstate deinit")

# --- The callbacks themselves note their steps.
s = rep(s, r'''private let tapInit: MTAudioProcessingTapInitCallback = { _, clientInfo, storageOut in
    storageOut.pointee = clientInfo
}
private let tapFinalize: MTAudioProcessingTapFinalizeCallback = { tap in
    Unmanaged<TapState>.fromOpaque(MTAudioProcessingTapGetStorage(tap)).release()
}
private let tapPrepare: MTAudioProcessingTapPrepareCallback = { tap, _, format in
    Unmanaged<TapState>.fromOpaque(MTAudioProcessingTapGetStorage(tap)).takeUnretainedValue().prepare(format.pointee)
}
private let tapUnprepare: MTAudioProcessingTapUnprepareCallback = { tap in
    Unmanaged<TapState>.fromOpaque(MTAudioProcessingTapGetStorage(tap)).takeUnretainedValue().release()
}
private let tapProcess: MTAudioProcessingTapProcessCallback = { tap, frames, _, bufferList, framesOut, flagsOut in
    guard MTAudioProcessingTapGetSourceAudio(tap, frames, bufferList, flagsOut, nil, framesOut) == noErr else { return }
    Unmanaged<TapState>.fromOpaque(MTAudioProcessingTapGetStorage(tap)).takeUnretainedValue()
        .process(bufferList, frames: Int(framesOut.pointee))
}''',
        r'''private let tapInit: MTAudioProcessingTapInitCallback = { _, clientInfo, storageOut in
    storageOut.pointee = clientInfo
    if let clientInfo {
        Unmanaged<TapState>.fromOpaque(clientInfo).takeUnretainedValue().noteTrail(1)
    }
}
private let tapFinalize: MTAudioProcessingTapFinalizeCallback = { tap in
    Unmanaged<TapState>.fromOpaque(MTAudioProcessingTapGetStorage(tap)).takeUnretainedValue().noteTrail(5)
    Unmanaged<TapState>.fromOpaque(MTAudioProcessingTapGetStorage(tap)).release()
}
private let tapPrepare: MTAudioProcessingTapPrepareCallback = { tap, _, format in
    let state = Unmanaged<TapState>.fromOpaque(MTAudioProcessingTapGetStorage(tap)).takeUnretainedValue()
    state.prepare(format.pointee)
    state.noteTrail(2, Int32(format.pointee.mSampleRate), Int32(format.pointee.mChannelsPerFrame),
                    Int32(format.pointee.mFormatFlags), Int32(format.pointee.mBitsPerChannel))
}
private let tapUnprepare: MTAudioProcessingTapUnprepareCallback = { tap in
    let state = Unmanaged<TapState>.fromOpaque(MTAudioProcessingTapGetStorage(tap)).takeUnretainedValue()
    state.release()
    state.noteTrail(4)
}
private let tapProcess: MTAudioProcessingTapProcessCallback = { tap, frames, _, bufferList, framesOut, flagsOut in
    guard MTAudioProcessingTapGetSourceAudio(tap, frames, bufferList, flagsOut, nil, framesOut) == noErr else { return }
    let state = Unmanaged<TapState>.fromOpaque(MTAudioProcessingTapGetStorage(tap)).takeUnretainedValue()
    state.noteProcessIfFirst(frames: Int32(framesOut.pointee))
    state.process(bufferList, frames: Int(framesOut.pointee))
}''',
        "round9 tap callback crumbs")

# --- Downloaded-file player: name its attach path + drain after.
s = rep(s, r'''        let playGeneration = generation
        attachTask = Task { [weak self] in''',
        r'''        let playGeneration = generation
        TrapTubeCrashTrail.record("tap attach begin (path: downloaded-player)")
        attachTask = Task { [weak self] in''',
        "round9 downloaded attach crumb")
s = rep(s, r'''            let attached = await TrapTubeTapEQ.shared.attach(to: item)
            guard let self, self.generation == playGeneration, self.currentItem === item else { return }''',
        r'''            let attached = await TrapTubeTapEQ.shared.attach(to: item)
            TrapTubeTapEQ.shared.drainTapTrail()
            guard let self, self.generation == playGeneration, self.currentItem === item else { return }''',
        "round9 downloaded drain")
p.write_text(s)

print("Build II hybrid navigation applied.")

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
                .ignoresSafeArea(edges: .top)
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
        view.isOpaque = false
        view.backgroundColor = .black
        view.scrollView.backgroundColor = .black
        view.scrollView.contentInsetAdjustmentBehavior = .never
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
'''
if "struct YouTubeAccountView: View" not in s:
    s += account
p.write_text(s)
print("Build II hybrid navigation applied.")

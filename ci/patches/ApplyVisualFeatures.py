#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1])
def find(name):
    matches = list(root.rglob(name))
    if not matches:
        raise SystemExit(f"Required Swift source not found: {name}")
    return matches[0]

# Root: branded launch splash and a reusable Liquid Glass modifier.
p = find("RootView.swift")
s = p.read_text()
if "TrapTubeSplashView" not in s:
    s = s.replace('            .padding(.bottom, 4)\n        }\n        .preferredColorScheme(.dark)', '            .padding(.bottom, 4)\n            .trapGlass(radius: 24, accent: theme.accent)\n        }\n        .preferredColorScheme(.dark)')
    s = s.replace('@State private var showPlayer = false',
                  '@State private var showPlayer = false\n    @State private var showSplash = true')
    anchor = '        .preferredColorScheme(.dark)\n        .tint(theme.accent)'
    overlay = '''        .overlay {
            if showSplash {
                TrapTubeSplashView(accent: theme.accent).transition(.opacity).zIndex(10)
            }
        }
        .task {
            try? await Task.sleep(nanoseconds: 1_850_000_000)
            withAnimation(.easeOut(duration: 0.45)) { showSplash = false }
        }
        .preferredColorScheme(.dark)
        .tint(theme.accent)'''
    if anchor not in s: raise SystemExit("RootView splash insertion anchor missing")
    s = s.replace(anchor, overlay, 1)
    s += r'''

private struct TrapTubeSplashView: View {
    let accent: Color
    var body: some View {
        ZStack {
            Color(red: 0.025, green: 0.025, blue: 0.035).ignoresSafeArea()
            RadialGradient(colors: [accent.opacity(0.34), .clear], center: .center, startRadius: 10, endRadius: 280).ignoresSafeArea()
            VStack(spacing: 18) {
                ZStack {
                    Circle().fill(accent.opacity(0.15)).frame(width: 142, height: 142).blur(radius: 18)
                    Image("TrapTubeIcon").resizable().scaledToFit().frame(width: 116, height: 116)
                        .clipShape(RoundedRectangle(cornerRadius: 27, style: .continuous))
                        .overlay(RoundedRectangle(cornerRadius: 27, style: .continuous).stroke(.white.opacity(0.22), lineWidth: 1))
                        .shadow(color: accent.opacity(0.42), radius: 24, y: 8)
                }
                Text("TrapTube").font(.system(size: 38, weight: .black, design: .rounded)).tracking(-1.2).foregroundStyle(.white)
                Text("Hostile Youtube Takeover").font(.system(size: 12, weight: .heavy, design: .rounded)).tracking(2.4).textCase(.uppercase).foregroundStyle(accent)
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("TrapTube. Hostile Youtube Takeover.")
    }
}

private struct TrapGlassSurface: ViewModifier {
    var radius: CGFloat = 22
    var accent: Color = .white
    func body(content: Content) -> some View {
        content.background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: radius, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: radius, style: .continuous)
                .stroke(LinearGradient(colors: [.white.opacity(0.26), accent.opacity(0.12), .white.opacity(0.035)], startPoint: .topLeading, endPoint: .bottomTrailing), lineWidth: 1))
            .shadow(color: .black.opacity(0.22), radius: 18, y: 8)
    }
}

extension View {
    func trapGlass(radius: CGFloat = 22, accent: Color = .white) -> some View {
        modifier(TrapGlassSurface(radius: radius, accent: accent))
    }
}
'''
p.write_text(s)

# Home: glass empty-state surface and luminous CTA.
p = find("HomeView.swift")
s = p.read_text()
s = s.replace('.background(.white.opacity(0.04), in: RoundedRectangle(cornerRadius: 26))',
              '.trapGlass(radius: 26, accent: theme.accent)')
s = s.replace('.background(theme.accent, in: Capsule())',
              '.background(LinearGradient(colors: [theme.accent, theme.accent.opacity(0.72)], startPoint: .topLeading, endPoint: .bottomTrailing), in: Capsule())')
p.write_text(s)

# Settings: every settings card receives the shared glass treatment.
for p in root.rglob("SettingsView.swift"):
    s = p.read_text()
    s = s.replace('''.padding(16).background(.white.opacity(0.055), in: RoundedRectangle(cornerRadius: 20))
        .overlay(RoundedRectangle(cornerRadius: 20).stroke(.white.opacity(0.06), lineWidth: 1))''',
                  '''.padding(16).trapGlass(radius: 20, accent: theme.accent)''')
    p.write_text(s)

# Stem Studio: replace opaque card backgrounds with material surfaces.
p = find("StemStudioView.swift")
s = p.read_text()
s = s.replace('.padding(16).background(.white.opacity(0.055), in: RoundedRectangle(cornerRadius: 20))',
              '.padding(16).trapGlass(radius: 20, accent: theme.accent)')
s = s.replace('.padding(16).background(.white.opacity(0.04), in: RoundedRectangle(cornerRadius: 20))',
              '.padding(16).trapGlass(radius: 20, accent: theme.accent)')
p.write_text(s)

# Player: show live meter under the cover art and add selectable visualizer styles.
p = find("PlayerView.swift")
s = p.read_text()
if "AudioReactiveVisualizer" not in s:
    s = s.replace('@State private var scrubbing = false',
                  '@State private var scrubbing = false\n    @State private var visualizerStyle = VisualizerStyle.spectrum')
    old = '''                        CoverArt(title: track.title, size: 270)
                            .frame(maxWidth: .infinity)
                            .shadow(color: theme.accent.opacity(0.18), radius: 24, y: 8)
                            .padding(.vertical, 4)'''
    new = '''                        VStack(spacing: 12) {
                            CoverArt(title: track.title, size: 220)
                                .frame(maxWidth: .infinity)
                                .shadow(color: theme.accent.opacity(0.18), radius: 24, y: 8)
                            AudioReactiveVisualizer(levels: player.visualizerLevels, waveform: player.visualizerWaveform, style: $visualizerStyle, tint: theme.accent)
                                .frame(height: 112)
                        }
                        .padding(14)
                        .trapGlass(radius: 28, accent: theme.accent)
                        .padding(.vertical, 4)'''
    if old not in s: raise SystemExit("Player cover-art insertion anchor missing")
    s = s.replace(old, new, 1)
    s = s.replace('.frame(maxWidth: .infinity, minHeight: 250)\n                        .padding(20).background(.white.opacity(0.05), in: RoundedRectangle(cornerRadius: 24))',
                  '.frame(maxWidth: .infinity, minHeight: 250)\n                        .padding(20).trapGlass(radius: 24, accent: theme.accent)')
    s = s.replace('.background(.white.opacity(0.08), in: RoundedRectangle(cornerRadius: 16))',
                  '.trapGlass(radius: 16, accent: theme.accent)')
    s += r'''

private enum VisualizerStyle: String, CaseIterable, Identifiable {
    case spectrum = "Spectrum"
    case radial = "Radial"
    case waveform = "Waveform"
    case pulse = "Neon Pulse"
    var id: String { rawValue }
}

private struct AudioReactiveVisualizer: View {
    let levels: [Float]
    let waveform: [Float]
    @Binding var style: VisualizerStyle
    let tint: Color
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        VStack(spacing: 8) {
            HStack {
                Label("LIVE VISUALIZER", systemImage: "waveform.path")
                    .font(.system(size: 9, weight: .black, design: .rounded)).tracking(1.5).foregroundStyle(.white.opacity(0.66))
                Spacer()
                Menu {
                    ForEach(VisualizerStyle.allCases) { item in
                        Button(item.rawValue) { style = item }
                    }
                } label: {
                    HStack(spacing: 5) {
                        Text(style.rawValue).font(.caption2.bold())
                        Image(systemName: "chevron.down").font(.system(size: 8, weight: .black))
                    }
                    .foregroundStyle(.white).padding(.horizontal, 10).padding(.vertical, 6)
                    .background(.ultraThinMaterial, in: Capsule())
                    .overlay(Capsule().stroke(.white.opacity(0.18), lineWidth: 1))
                }
            }
            Canvas { context, size in
                let values = levels.isEmpty ? Array(repeating: Float(0.025), count: 48) : levels
                switch style {
                case .spectrum:
                    let gap: CGFloat = 3
                    let barWidth = max(1, (size.width - gap * CGFloat(values.count - 1)) / CGFloat(values.count))
                    for (index, value) in values.enumerated() {
                        let eased = CGFloat(pow(max(0, value), 0.72))
                        let height = max(3, eased * size.height * 0.92)
                        let rect = CGRect(x: CGFloat(index) * (barWidth + gap), y: size.height - height, width: barWidth, height: height)
                        context.fill(Path(roundedRect: rect, cornerRadius: barWidth / 2),
                            with: .linearGradient(Gradient(colors: [tint.opacity(0.42), tint, .white.opacity(0.88)]),
                            startPoint: CGPoint(x: rect.midX, y: rect.maxY), endPoint: CGPoint(x: rect.midX, y: rect.minY)))
                    }
                case .radial:
                    let center = CGPoint(x: size.width / 2, y: size.height / 2)
                    let base = min(size.width, size.height) * 0.22
                    for (index, value) in values.enumerated() {
                        let angle = CGFloat(index) / CGFloat(values.count) * .pi * 2 - .pi / 2
                        let length = base + CGFloat(value) * min(size.width, size.height) * 0.25
                        let a = CGPoint(x: center.x + cos(angle) * base, y: center.y + sin(angle) * base)
                        let b = CGPoint(x: center.x + cos(angle) * length, y: center.y + sin(angle) * length)
                        var path = Path(); path.move(to: a); path.addLine(to: b)
                        context.stroke(path, with: .color(tint.opacity(0.35 + Double(value) * 0.65)),
                            style: StrokeStyle(lineWidth: 2.2, lineCap: .round))
                    }
                    let ring = Path(ellipseIn: CGRect(x: center.x - base, y: center.y - base, width: base * 2, height: base * 2))
                    context.stroke(ring, with: .color(.white.opacity(0.18)), lineWidth: 1)
                case .waveform:
                    let waveValues = waveform.isEmpty ? values : waveform
                    var path = Path()
                    let mid = size.height / 2
                    path.move(to: CGPoint(x: 0, y: mid))
                    for (index, value) in waveValues.enumerated() {
                        let x = CGFloat(index) / CGFloat(max(1, waveValues.count - 1)) * size.width
                        path.addLine(to: CGPoint(x: x, y: mid - CGFloat(max(-1, min(1, value * 4.5))) * size.height * 0.46))
                    }
                    for (index, value) in waveValues.enumerated().reversed() {
                        let x = CGFloat(index) / CGFloat(max(1, waveValues.count - 1)) * size.width
                        path.addLine(to: CGPoint(x: x, y: mid + CGFloat(max(-1, min(1, value * 4.5))) * size.height * 0.46))
                    }
                    path.closeSubpath()
                    context.fill(path, with: .linearGradient(Gradient(colors: [tint.opacity(0.05), tint.opacity(0.65), tint.opacity(0.08)]),
                        startPoint: CGPoint(x: 0, y: 0), endPoint: CGPoint(x: 0, y: size.height)))
                    var centerLine = Path(); centerLine.move(to: CGPoint(x: 0, y: mid)); centerLine.addLine(to: CGPoint(x: size.width, y: mid))
                    context.stroke(centerLine, with: .color(.white.opacity(0.22)), lineWidth: 1)
                case .pulse:
                    let peak = CGFloat(values.max() ?? 0)
                    let radius = min(size.width, size.height) * (0.18 + peak * 0.2)
                    let rect = CGRect(x: size.width / 2 - radius, y: size.height / 2 - radius, width: radius * 2, height: radius * 2)
                    context.addFilter(.blur(radius: 10 + peak * 12))
                    context.fill(Path(ellipseIn: rect), with: .color(tint.opacity(0.18 + Double(peak) * 0.4)))
                    context.addFilter(.blur(radius: 0))
                    context.stroke(Path(ellipseIn: rect), with: .color(tint.opacity(0.9)), lineWidth: 2 + peak * 2)
                    for ring in 1...3 {
                        let r = radius + CGFloat(ring) * (7 + peak * 8)
                        context.stroke(Path(ellipseIn: CGRect(x: size.width / 2 - r, y: size.height / 2 - r, width: r * 2, height: r * 2)),
                            with: .color(tint.opacity(0.22 / Double(ring))), lineWidth: 1)
                    }
                }
            }
            .animation(reduceMotion ? nil : .easeOut(duration: 0.08), value: levels)
        }
    }
}
'''
p.write_text(s)

# Make the actual YouTube Home page the app's primary Home tab.
# Keep the local audio collection available from the former TrapTube tab.
root_view = find("RootView.swift")
root_source = root_view.read_text()
root_source = root_source.replace("case .home: HomeView()", "case .home: YouTubeView()", 1)
root_source = root_source.replace("case .youtube: YouTubeView()", "case .youtube: HomeView()", 1)
root_view.write_text(root_source)

print("Applied splash, glass surfaces, and audio-reactive visualizer patches.")


# Home feed: replace the external Safari launch with an embedded, persistent
# YouTube Home experience. The existing RootView tab bar is intentionally untouched.
yt_path = find("YouTubeView.swift")
yt_source = yt_path.read_text()
start_marker = "struct YouTubeView: View {"
end_marker = "private struct TypeTypeVideoRow"
if start_marker not in yt_source or end_marker not in yt_source:
    raise SystemExit("YouTube Home replacement anchors missing")
start = yt_source.index(start_marker)
end = yt_source.index(end_marker, start)
replacement = r'''struct YouTubeView: View {
    @EnvironmentObject private var theme: ThemeManager
    @State private var webView: WKWebView?
    @State private var searchText = ""
    @State private var selectedCategory = "All"
    @State private var isLoading = true
    @FocusState private var searchFocused: Bool

    private let homeURL = URL(string: "https://www.youtube.com/feed/recommended")!
    private let categories = ["All", "Louisiana Hip Hop", "Documentaries", "Studio Sessions"]

    var body: some View {
        ZStack {
            Color(red: 0.025, green: 0.025, blue: 0.035).ignoresSafeArea()
            RadialGradient(colors: [Color(hex: "A90012").opacity(0.22), .clear],
                           center: .top, startRadius: 8, endRadius: 430)
                .ignoresSafeArea()

            VStack(spacing: 0) {
                header
                searchBar
                categoryBar

                ZStack(alignment: .top) {
                    YouTubeHomeWebView(
                        url: homeURL,
                        onCreated: { webView = $0 },
                        onLoading: { isLoading = $0 }
                    )
                    .background(Color.black)

                    if isLoading {
                        HStack(spacing: 9) {
                            ProgressView().tint(.white)
                            Text("Loading your YouTube feed…")
                                .font(.caption.weight(.semibold))
                                .foregroundStyle(.white.opacity(0.8))
                        }
                        .padding(.horizontal, 15).padding(.vertical, 11)
                        .background(.ultraThinMaterial, in: Capsule())
                        .overlay(Capsule().stroke(.white.opacity(0.16), lineWidth: 1))
                        .padding(.top, 16)
                        .allowsHitTesting(false)
                    }
                }
            }
        }
        .preferredColorScheme(.dark)
    }

    private var header: some View {
        HStack(spacing: 10) {
            Image(uiImage: UIImage(named: "TrapTubeIcon") ?? UIImage(systemName: "play.rectangle.fill")!)
                .resizable().scaledToFill()
                .frame(width: 34, height: 34)
                .clipShape(RoundedRectangle(cornerRadius: 11, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: 11, style: .continuous)
                    .stroke(.white.opacity(0.24), lineWidth: 1))
                .shadow(color: Color(hex: "F01D2D").opacity(0.34), radius: 10, y: 3)

            VStack(alignment: .leading, spacing: 1) {
                HStack(spacing: 5) {
                    Text("TrapTube").font(.system(size: 18, weight: .black, design: .rounded))
                        .tracking(-0.5).foregroundStyle(.white)
                    Text("HOME").font(.system(size: 8, weight: .black, design: .rounded))
                        .tracking(1).foregroundStyle(Color(hex: "FF6570"))
                        .padding(.horizontal, 6).padding(.vertical, 3)
                        .background(Color(hex: "E50920").opacity(0.18), in: Capsule())
                }
                Text("Your YouTube feed").font(.system(size: 10, weight: .medium))
                    .foregroundStyle(.white.opacity(0.48))
            }

            Spacer(minLength: 4)

            Button {
                load(URL(string: "https://www.youtube.com/signin?next=%2Ffeed%2Frecommended")!)
            } label: {
                Label("Sign in", systemImage: "person.crop.circle")
                    .font(.caption.weight(.bold)).foregroundStyle(.white)
                    .padding(.horizontal, 11).padding(.vertical, 9)
                    .background(.ultraThinMaterial, in: Capsule())
                    .overlay(Capsule().stroke(.white.opacity(0.18), lineWidth: 1))
            }
            .accessibilityLabel("Sign in to YouTube")

            Button { webView?.reload() } label: {
                Image(systemName: "arrow.clockwise")
                    .font(.system(size: 13, weight: .bold)).foregroundStyle(.white.opacity(0.9))
                    .frame(width: 36, height: 36)
                    .background(.ultraThinMaterial, in: Circle())
                    .overlay(Circle().stroke(.white.opacity(0.16), lineWidth: 1))
            }
            .accessibilityLabel("Refresh YouTube feed")
        }
        .padding(.horizontal, 15).padding(.top, 8).padding(.bottom, 11)
        .background(.ultraThinMaterial.opacity(0.72))
        .overlay(alignment: .bottom) { Rectangle().fill(.white.opacity(0.07)).frame(height: 1) }
    }

    private var searchBar: some View {
        HStack(spacing: 10) {
            Image(systemName: "magnifyingglass").foregroundStyle(.white.opacity(0.52))
            TextField("Search videos, audio, creators…", text: $searchText)
                .font(.system(size: 13, weight: .medium))
                .foregroundStyle(.white)
                .tint(Color(hex: "FF3948"))
                .focused($searchFocused)
                .submitLabel(.search)
                .onSubmit { submitSearch() }
                .autocorrectionDisabled()
            if !searchText.isEmpty {
                Button { searchText = "" } label: {
                    Image(systemName: "xmark.circle.fill").foregroundStyle(.white.opacity(0.45))
                }
                .accessibilityLabel("Clear search")
            }
            Button { submitSearch() } label: {
                Image(systemName: "arrow.right")
                    .font(.system(size: 12, weight: .black)).foregroundStyle(.white)
                    .frame(width: 29, height: 29)
                    .background(LinearGradient(colors: [Color(hex: "FF303B"), Color(hex: "A90012")],
                                               startPoint: .topLeading, endPoint: .bottomTrailing),
                                in: RoundedRectangle(cornerRadius: 9, style: .continuous))
            }
            .accessibilityLabel("Search YouTube")
        }
        .padding(.horizontal, 13).padding(.vertical, 10)
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous)
            .stroke(.white.opacity(0.13), lineWidth: 1))
        .shadow(color: .black.opacity(0.2), radius: 12, y: 5)
        .padding(.horizontal, 14).padding(.vertical, 9)
    }

    private var categoryBar: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(categories, id: \.self) { category in
                    let active = selectedCategory == category
                    Button { selectCategory(category) } label: {
                        Text(category)
                            .font(.system(size: 11, weight: active ? .bold : .semibold))
                            .foregroundStyle(active ? .white : .white.opacity(0.72))
                            .padding(.horizontal, 13).padding(.vertical, 8)
                            .background {
                                if active {
                                    LinearGradient(colors: [Color(hex: "FF303B"), Color(hex: "A90012")],
                                                   startPoint: .topLeading, endPoint: .bottomTrailing)
                                } else {
                                    Color.white.opacity(0.055)
                                }
                            }
                            .clipShape(Capsule())
                            .overlay(Capsule().stroke(.white.opacity(active ? 0.24 : 0.12), lineWidth: 1))
                            .shadow(color: active ? Color(hex: "E50920").opacity(0.22) : .clear, radius: 9, y: 3)
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(.horizontal, 14).padding(.vertical, 3)
        }
        .padding(.bottom, 8)
    }

    private func selectCategory(_ category: String) {
        selectedCategory = category
        searchFocused = false
        if category == "All" {
            load(homeURL)
        } else {
            searchText = category
            submitSearch()
        }
    }

    private func submitSearch() {
        let query = searchText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !query.isEmpty,
              var components = URLComponents(string: "https://www.youtube.com/results") else { return }
        components.queryItems = [URLQueryItem(name: "search_query", value: query)]
        if let url = components.url { load(url) }
        searchFocused = false
    }

    private func load(_ url: URL) {
        guard url.host == "www.youtube.com" || url.host == "m.youtube.com" else { return }
        webView?.load(URLRequest(url: url, cachePolicy: .useProtocolCachePolicy, timeoutInterval: 30))
    }
}

private struct YouTubeHomeWebView: UIViewRepresentable {
    let url: URL
    let onCreated: (WKWebView) -> Void
    let onLoading: (Bool) -> Void

    func makeCoordinator() -> Coordinator { Coordinator(onLoading: onLoading) }

    func makeUIView(context: Context) -> WKWebView {
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .default()
        configuration.allowsInlineMediaPlayback = true
        configuration.mediaTypesRequiringUserActionForPlayback = []
        let view = WKWebView(frame: .zero, configuration: configuration)
        view.isOpaque = false
        view.backgroundColor = .black
        view.scrollView.backgroundColor = .black
        view.scrollView.contentInsetAdjustmentBehavior = .never
        view.allowsBackForwardNavigationGestures = true
        view.navigationDelegate = context.coordinator
        context.coordinator.webView = view
        onCreated(view)
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
yt_path.write_text(yt_source[:start] + replacement + yt_source[end:])

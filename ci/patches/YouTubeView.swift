import SwiftUI
import WebKit
import AVFoundation

struct YouTubeView: View {
    @EnvironmentObject private var theme: ThemeManager
    @EnvironmentObject private var library: LibraryStore
    @State private var query = ""
    @State private var filter = "All"
    @State private var feed: [TypeTypeVideo] = []
    @State private var results: [TypeTypeVideo] = []
    @State private var nextPage: String?
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var selectedVideo: TypeTypeVideo?
    @FocusState private var searchFocused: Bool

    private var localResults: [Track] {
        let term = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !term.isEmpty else { return [] }
        return library.tracks.filter { $0.title.localizedCaseInsensitiveContains(term) || $0.artist.localizedCaseInsensitiveContains(term) }
    }

    private var visibleVideos: [TypeTypeVideo] { query.isEmpty ? feed : results }

    var body: some View {
        ScrollView(showsIndicators: false) {
            VStack(alignment: .leading, spacing: 18) {
                BrandHeader().padding(.horizontal, 20)
                VStack(alignment: .leading, spacing: 6) {
                    Text("Discover").font(.largeTitle.bold()).foregroundStyle(.white)
                    Text("Search your music library and browse TypeType videos.")
                        .font(.subheadline).foregroundStyle(Color(hex: "A6A4A6"))
                }.padding(.horizontal, 18)

                HStack(spacing: 10) {
                    Image(systemName: "magnifyingglass").foregroundStyle(Color(hex: "A6A4A6"))
                    TextField("Search your library and videos", text: $query)
                        .focused($searchFocused)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .submitLabel(.search)
                        .foregroundStyle(.white)
                        .onSubmit { Task { await performSearch() } }
                    if !query.isEmpty {
                        Button { query = ""; results = []; searchFocused = false } label: {
                            Image(systemName: "xmark.circle.fill").foregroundStyle(Color(hex: "8D898D"))
                        }
                    }
                    Button { Task { await performSearch() } } label: {
                        Image(systemName: "arrow.right.circle.fill").font(.title2).foregroundStyle(theme.accent)
                    }
                    .accessibilityLabel("Search")
                }
                .padding(.horizontal, 15).padding(.vertical, 13)
                .background(.white.opacity(0.07), in: RoundedRectangle(cornerRadius: 17))
                .overlay(RoundedRectangle(cornerRadius: 17).stroke(.white.opacity(0.08), lineWidth: 1))
                .padding(.horizontal, 16)

                HStack(spacing: 9) {
                    ForEach(["All", "Local", "Videos"], id: \.self) { item in
                        Button { filter = item } label: {
                            Text(item).font(.subheadline.bold()).foregroundStyle(filter == item ? .white : Color(hex: "B5B2B5"))
                                .padding(.horizontal, 17).padding(.vertical, 9)
                                .background(filter == item ? theme.accent : .white.opacity(0.07), in: Capsule())
                        }.buttonStyle(.plain)
                    }
                }.padding(.horizontal, 18)

                if !query.isEmpty && filter != "Videos" {
                    VStack(alignment: .leading, spacing: 10) {
                        SectionHeading(title: "Your music", trailing: "\(localResults.count) tracks")
                        if localResults.isEmpty {
                            Text("No matching imported tracks.").font(.subheadline).foregroundStyle(Color(hex: "898589"))
                        } else {
                            ForEach(localResults) { track in
                                TrackRow(track: track, queue: localResults)
                            }
                        }
                    }.padding(.horizontal, 18)
                }

                if filter != "Local" {
                    VStack(alignment: .leading, spacing: 12) {
                        SectionHeading(title: query.isEmpty ? "Trending on TypeType" : "Video results", trailing: "\(visibleVideos.count) videos")
                        if isLoading && visibleVideos.isEmpty {
                            ProgressView("Loading videos…").tint(theme.accent).foregroundStyle(.white).frame(maxWidth: .infinity).padding(.vertical, 28)
                        } else if visibleVideos.isEmpty {
                            Text(query.isEmpty ? "No videos are available from this instance right now." : "No matching videos found.")
                                .font(.subheadline).foregroundStyle(Color(hex: "898589")).padding(.vertical, 10)
                        } else {
                            ForEach(visibleVideos) { video in
                                Button {
                                    selectedVideo = video
                                } label: { TypeTypeVideoRow(video: video, tint: theme.accent) }
                                    .buttonStyle(.plain)
                            }
                        }
                        if let errorMessage {
                            Label(errorMessage, systemImage: "exclamationmark.triangle.fill")
                                .font(.caption).foregroundStyle(Color(hex: "FF7A84")).fixedSize(horizontal: false, vertical: true)
                        }
                        if !query.isEmpty && !results.isEmpty && nextPage != nil {
                            Button { Task { await loadMore() } } label: {
                                Text(isLoading ? "Loading…" : "Load more videos").font(.subheadline.bold())
                                    .foregroundStyle(.white).frame(maxWidth: .infinity).padding(.vertical, 12)
                                    .background(theme.accent.opacity(0.85), in: Capsule())
                            }.disabled(isLoading)
                        }
                    }.padding(.horizontal, 18)
                }

                Text("Video discovery and playback are provided by your TypeType instance. Local audio stays on this device.")
                    .font(.caption).foregroundStyle(Color(hex: "858185")).padding(.horizontal, 20).padding(.bottom, 20)
            }
            .padding(.top, 7)
        }
        .refreshable { await loadFeed() }
        .task { if feed.isEmpty { await loadFeed() } }
        .sheet(item: $selectedVideo) { video in
            if let url = TypeTypeService().watchURL(for: video) {
                TypeTypeWatchSheet(url: url, title: video.title)
                    .ignoresSafeArea()
                    .preferredColorScheme(.dark)
            } else {
                Text("This video does not have a valid TypeType watch address.")
                    .padding().presentationDetents([.medium])
            }
        }
    }

    private func loadFeed() async {
        guard !isLoading else { return }
        isLoading = true; errorMessage = nil
        defer { isLoading = false }
        do {
            _ = try await TypeTypeService().connect()
            feed = try await TypeTypeService().trending()
        } catch { errorMessage = error.localizedDescription }
    }

    private func performSearch() async {
        let term = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !term.isEmpty else { results = []; return }
        isLoading = true; errorMessage = nil; nextPage = nil
        defer { isLoading = false }
        do {
            _ = try await TypeTypeService().connect()
            let page = try await TypeTypeService().search(query: term)
            results = page.items
            nextPage = page.nextpage
        } catch { results = []; errorMessage = error.localizedDescription }
    }

    private func loadMore() async {
        guard let nextPage, !isLoading else { return }
        isLoading = true; defer { isLoading = false }
        do {
            let page = try await TypeTypeService().search(query: query, nextPage: nextPage)
            results.append(contentsOf: page.items)
            self.nextPage = page.nextpage
        } catch { errorMessage = error.localizedDescription }
    }
}

private struct TypeTypeVideoRow: View {
    let video: TypeTypeVideo
    let tint: Color
    var body: some View {
        HStack(spacing: 12) {
            ZStack(alignment: .bottomTrailing) {
                AsyncImage(url: URL(string: video.thumbnailUrl)) { image in
                    image.resizable().scaledToFill()
                } placeholder: {
                    RoundedRectangle(cornerRadius: 12).fill(.white.opacity(0.07)).overlay(Image(systemName: "play.rectangle").foregroundStyle(.white.opacity(0.35)))
                }
                .frame(width: 132, height: 82).clipShape(RoundedRectangle(cornerRadius: 12))
                Text(video.isLive == true ? "LIVE" : video.displayDuration)
                    .font(.system(size: 10, weight: .bold, design: .rounded)).foregroundStyle(.white)
                    .padding(.horizontal, 6).padding(.vertical, 3)
                    .background(video.isLive == true ? Color.red : Color.black.opacity(0.8), in: Capsule()).padding(5)
            }
            VStack(alignment: .leading, spacing: 5) {
                Text(video.title).font(.subheadline.bold()).foregroundStyle(.white).lineLimit(2).multilineTextAlignment(.leading)
                Text(video.uploaderName).font(.caption).foregroundStyle(Color(hex: "AAA6AA")).lineLimit(1)
                if let views = video.viewCount {
                    Text("\(views.formatted()) views").font(.caption2).foregroundStyle(Color(hex: "858185"))
                }
            }
            Spacer(minLength: 0)
            Image(systemName: "play.circle.fill").font(.title2).foregroundStyle(tint)
        }
        .padding(8)
        .background(.white.opacity(0.045), in: RoundedRectangle(cornerRadius: 16))
    }
}

private struct TypeTypePlayerOption: Identifiable, Equatable {
    let id: String          // stable identifier read from the player (itag/value) when available
    let label: String
    let selected: Bool
}

/// The streaming equalizer has four distinct states; playback failures are reported separately.
private enum StreamEQStatus: Equatable {
    case connecting
    case active
    case unavailable(String, canReload: Bool)
}

private struct TypeTypeWatchSheet: View {
    let url: URL
    let title: String
    @Environment(\.dismiss) private var dismiss
    @EnvironmentObject private var theme: ThemeManager
    @EnvironmentObject private var audio: AudioEngineManager
    @State private var webView: WKWebView?
    @State private var currentTime = 0.0
    @State private var duration = 0.0
    @State private var isPlaying = false
    @State private var scrubbing = false
    @State private var scrubValue = 0.0
    @State private var eqStatus: StreamEQStatus = .connecting
    @State private var eqDisabledForSession = false
    @State private var playbackError: String?
    @State private var menuNotice: String?
    @State private var videoQualities: [TypeTypePlayerOption] = []
    @State private var audioTracks: [TypeTypePlayerOption] = []
    @State private var showEQ = false

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()
            TypeTypeWebView(url: url, gains: audio.eqGains, bass: audio.bassBoost, master: audio.masterGain,
                            eqDisabled: eqDisabledForSession,
                            onCreated: { webView = $0 }, onMessage: receive)
            VStack(spacing: 0) {
                HStack {
                    Button { dismiss() } label: {
                        Image(systemName: "xmark").font(.headline.bold()).foregroundStyle(.white)
                            .frame(width: 38, height: 38).background(.black.opacity(0.7), in: Circle())
                    }
                    .accessibilityLabel("Close player")
                    Text(title).font(.subheadline.bold()).foregroundStyle(.white).lineLimit(1)
                    Spacer()
                }.padding(14).background(LinearGradient(colors: [.black.opacity(0.85), .clear], startPoint: .top, endPoint: .bottom))
                Spacer()
                VStack(spacing: 10) {
                    if let playbackError {
                        Label(playbackError, systemImage: "exclamationmark.triangle.fill")
                            .font(.caption).foregroundStyle(Color(hex: "FF8A8A"))
                            .frame(maxWidth: .infinity, alignment: .leading).fixedSize(horizontal: false, vertical: true)
                    }
                    HStack(spacing: 12) {
                        Button { command("toggle") } label: {
                            Image(systemName: isPlaying ? "pause.fill" : "play.fill")
                                .font(.title3.bold()).foregroundStyle(.white).frame(width: 42, height: 42)
                                .background(theme.accent, in: Circle())
                        }
                        .accessibilityLabel(isPlaying ? "Pause" : "Play")
                        VStack(spacing: 3) {
                            Slider(value: Binding(get: { scrubbing ? scrubValue : (duration > 0 ? min(1, currentTime / duration) : 0) },
                                                  set: { scrubValue = $0; scrubbing = true }),
                                   in: 0...1, onEditingChanged: { editing in
                                if !editing { command("seek", scrubValue * duration); scrubbing = false }
                            }).tint(theme.accent).disabled(duration <= 0)
                            HStack {
                                Text(timeText(scrubbing ? scrubValue * duration : currentTime))
                                Spacer()
                                Text(duration > 0 ? timeText(duration) : "LIVE")
                            }.font(.caption2.monospacedDigit()).foregroundStyle(.white.opacity(0.75))
                        }
                    }
                    HStack(spacing: 8) {
                        Button { showEQ = true } label: {
                            Label("EQ", systemImage: "slider.horizontal.3").font(.subheadline.bold())
                                .foregroundStyle(.white).padding(.horizontal, 12).padding(.vertical, 9)
                                .background(.white.opacity(0.12), in: Capsule())
                        }
                        eqStatusView
                        Spacer(minLength: 0)
                        optionMenu(title: "Quality", icon: "4k.tv", kind: "video", options: videoQualities,
                                   empty: "No selectable video qualities for this stream", single: "Only one quality is available")
                        optionMenu(title: "Audio track", icon: "waveform", kind: "audio", options: audioTracks,
                                   empty: "No alternate audio tracks for this stream", single: "Only one audio track is available")
                    }
                    if let menuNotice {
                        Text(menuNotice).font(.caption2).foregroundStyle(Color(hex: "FFB85C")).frame(maxWidth: .infinity, alignment: .leading)
                    }
                    Text("Choices are read from the active TypeType player; unsupported quality levels are not fabricated.")
                        .font(.caption2).foregroundStyle(.white.opacity(0.55)).frame(maxWidth: .infinity, alignment: .leading)
                }
                .padding(13).background(.black.opacity(0.9), in: RoundedRectangle(cornerRadius: 18))
                .padding(.horizontal, 10).padding(.bottom, 12)
            }
        }
        .sheet(isPresented: $showEQ) {
            EqualizerView().environmentObject(audio).environmentObject(theme).presentationDetents([.large])
        }
        .onAppear {
            // The web player owns audio output while this sheet is open.
            audio.pauseForExternalPlayback()
            try? AVAudioSession.sharedInstance().setCategory(.playback, mode: .moviePlayback)
            try? AVAudioSession.sharedInstance().setActive(true)
        }
    }

    @ViewBuilder private var eqStatusView: some View {
        switch eqStatus {
        case .connecting:
            Text("EQ connecting…").font(.caption2).foregroundStyle(.white.opacity(0.65))
        case .active:
            Label("EQ active", systemImage: "checkmark.circle.fill").font(.caption2).foregroundStyle(Color.green)
        case let .unavailable(reason, canReload):
            VStack(alignment: .leading, spacing: 3) {
                Text("EQ unavailable — original audio").font(.caption2.bold()).foregroundStyle(Color(hex: "FFB85C"))
                Text(reason).font(.caption2).foregroundStyle(.white.opacity(0.65)).lineLimit(3)
                if canReload {
                    Button("Reload without EQ") { eqDisabledForSession = true; eqStatus = .unavailable("Equalizer turned off for this video.", canReload: false) }
                        .font(.caption2.bold()).foregroundStyle(theme.accent)
                }
            }
        }
    }

    private func optionMenu(title: String, icon: String, kind: String, options: [TypeTypePlayerOption], empty: String, single: String) -> some View {
        Menu {
            if options.isEmpty {
                Text(empty)
            } else if options.count == 1, let only = options.first {
                Text("\(single): \(only.label)")
            } else {
                ForEach(options) { option in
                    Button { select(kind: kind, option: option) } label: {
                        if option.selected { Label(option.label, systemImage: "checkmark") } else { Text(option.label) }
                    }
                }
            }
        } label: {
            Label(title, systemImage: icon).font(.caption.bold()).foregroundStyle(.white)
                .padding(.horizontal, 10).padding(.vertical, 9).background(.white.opacity(0.12), in: Capsule())
        }
    }

    private func receive(_ body: [String: Any]) {
        switch body["type"] as? String {
        case "reset":
            // New navigation: drop everything that described the previous page.
            currentTime = 0; duration = 0; isPlaying = false
            videoQualities = []; audioTracks = []; menuNotice = nil; playbackError = nil
            if !eqDisabledForSession { eqStatus = .connecting }
        case "state":
            if let value = body["currentTime"] as? Double, value.isFinite { currentTime = value }
            if let value = body["duration"] as? Double, value.isFinite { duration = value }
            let paused = body["paused"] as? Bool ?? true
            let ended = body["ended"] as? Bool ?? false
            isPlaying = !paused && !ended
            if isPlaying { playbackError = nil }
        case "eqStatus":
            if eqDisabledForSession { return }
            switch body["state"] as? String {
            case "active": eqStatus = .active
            case "unavailable": eqStatus = .unavailable(body["message"] as? String ?? "The equalizer could not be attached to this stream.", canReload: body["canReload"] as? Bool ?? false)
            default: eqStatus = .connecting
            }
        case "videoQualities": videoQualities = options(body["items"])
        case "audioTracks": audioTracks = options(body["items"])
        case "menuNotice": menuNotice = body["message"] as? String
        case "playerError": playbackError = body["message"] as? String   // playback problems never touch EQ status
        default: break
        }
    }

    private func options(_ raw: Any?) -> [TypeTypePlayerOption] {
        guard let rows = raw as? [[String: Any]] else { return [] }
        return rows.compactMap { row in
            guard let id = row["id"] as? String, let label = row["label"] as? String, !label.isEmpty else { return nil }
            return TypeTypePlayerOption(id: id, label: label, selected: row["selected"] as? Bool ?? false)
        }
    }

    private func command(_ name: String, _ value: Double = 0) {
        let safe = value.isFinite ? value : 0
        webView?.evaluateJavaScript("window.__traptubeControl && window.__traptubeControl('\(name)', \(safe));")
    }

    private func select(kind: String, option: TypeTypePlayerOption) {
        menuNotice = nil
        let payload: [String: Any] = ["kind": kind, "id": option.id, "label": option.label]
        guard let data = try? JSONSerialization.data(withJSONObject: payload),
              let json = String(data: data, encoding: .utf8) else { return }
        webView?.evaluateJavaScript("window.__traptubeSelectOption && window.__traptubeSelectOption(\(json));")
    }

    private func timeText(_ value: Double) -> String {
        let seconds = value.isFinite ? max(0, Int(value)) : 0
        return String(format: "%d:%02d", seconds / 60, seconds % 60)
    }
}

/// WKUserContentController retains its handlers strongly; this proxy breaks the retain cycle.
private final class WeakScriptHandler: NSObject, WKScriptMessageHandler {
    weak var target: WKScriptMessageHandler?
    init(_ target: WKScriptMessageHandler) { self.target = target }
    func userContentController(_ controller: WKUserContentController, didReceive message: WKScriptMessage) {
        target?.userContentController(controller, didReceive: message)
    }
}

private struct TypeTypeWebView: UIViewRepresentable {
    let url: URL
    let gains: [Float]
    let bass: Float
    let master: Float
    let eqDisabled: Bool
    let onCreated: (WKWebView) -> Void
    let onMessage: ([String: Any]) -> Void

    func makeCoordinator() -> Coordinator { Coordinator(onMessage: onMessage, gains: gains, bass: bass, master: master) }

    static func installScripts(into content: WKUserContentController, eqDisabled: Bool) {
        content.removeAllUserScripts()
        if eqDisabled {
            content.addUserScript(WKUserScript(source: "window.__traptubeEQDisabled = true;", injectionTime: .atDocumentStart, forMainFrameOnly: true))
        }
        // atDocumentStart so playback listeners exist before TypeType creates its video element.
        content.addUserScript(WKUserScript(source: bootstrap, injectionTime: .atDocumentStart, forMainFrameOnly: true))
    }

    func makeUIView(context: Context) -> WKWebView {
        let content = WKUserContentController()
        content.add(WeakScriptHandler(context.coordinator), name: "trapPlayer")
        Self.installScripts(into: content, eqDisabled: eqDisabled)
        let configuration = WKWebViewConfiguration()
        configuration.userContentController = content
        configuration.allowsInlineMediaPlayback = true
        configuration.mediaTypesRequiringUserActionForPlayback = []
        let view = WKWebView(frame: .zero, configuration: configuration)
        view.isOpaque = false
        view.backgroundColor = .black
        view.scrollView.backgroundColor = .black
        view.navigationDelegate = context.coordinator
        context.coordinator.webView = view
        context.coordinator.requestedURL = url
        context.coordinator.eqDisabled = eqDisabled
        // Avoid mutating SwiftUI state during the view update.
        DispatchQueue.main.async { onCreated(view) }
        view.load(URLRequest(url: url, cachePolicy: .useProtocolCachePolicy, timeoutInterval: 30))
        return view
    }

    func updateUIView(_ uiView: WKWebView, context: Context) {
        let coordinator = context.coordinator
        coordinator.onMessage = onMessage
        coordinator.setEQ(gains: gains, bass: bass, master: master)
        // Only an explicit change of the requested URL or EQ mode loads again. Comparing with
        // uiView.url would fight TypeType's own in-page navigation (autoplay, next video).
        if coordinator.eqDisabled != eqDisabled {
            coordinator.eqDisabled = eqDisabled
            Self.installScripts(into: uiView.configuration.userContentController, eqDisabled: eqDisabled)
            uiView.load(URLRequest(url: coordinator.requestedURL))
        } else if coordinator.requestedURL != url {
            coordinator.requestedURL = url
            uiView.load(URLRequest(url: url))
        }
    }

    static func dismantleUIView(_ uiView: WKWebView, coordinator: Coordinator) {
        uiView.evaluateJavaScript("document.querySelectorAll('video').forEach(function(v){v.pause();});")
        uiView.stopLoading()
        uiView.navigationDelegate = nil
        let content = uiView.configuration.userContentController
        content.removeScriptMessageHandler(forName: "trapPlayer")
        content.removeAllUserScripts()
        uiView.loadHTMLString("", baseURL: nil)
        coordinator.webView = nil
    }

    final class Coordinator: NSObject, WKScriptMessageHandler, WKNavigationDelegate {
        var onMessage: ([String: Any]) -> Void
        weak var webView: WKWebView?
        var requestedURL = URL(string: "about:blank")!
        var eqDisabled = false
        private var gains: [Float]
        private var bass: Float
        private var master: Float
        private var lastApplied = ""

        init(onMessage: @escaping ([String: Any]) -> Void, gains: [Float], bass: Float, master: Float) {
            self.onMessage = onMessage
            self.gains = gains
            self.bass = bass
            self.master = master
        }

        func setEQ(gains: [Float], bass: Float, master: Float) {
            self.gains = gains; self.bass = bass; self.master = master
            applyEQ()
        }

        private func applyEQ(force: Bool = false) {
            guard let webView,
                  let data = try? JSONSerialization.data(withJSONObject: ["gains": gains, "bass": bass, "master": master]),
                  let json = String(data: data, encoding: .utf8) else { return }
            if !force && json == lastApplied { return }
            lastApplied = json
            webView.evaluateJavaScript("window.__traptubeSetEQ && window.__traptubeSetEQ(\(json));")
        }

        func userContentController(_ controller: WKUserContentController, didReceive message: WKScriptMessage) {
            guard let body = message.body as? [String: Any] else { return }
            DispatchQueue.main.async { self.onMessage(body) }
        }

        private func report(_ message: String) {
            DispatchQueue.main.async { self.onMessage(["type": "playerError", "message": message]) }
        }

        func webView(_ webView: WKWebView, didStartProvisionalNavigation navigation: WKNavigation!) {
            DispatchQueue.main.async { self.onMessage(["type": "reset"]) }
        }

        func webView(_ webView: WKWebView, decidePolicyFor navigationResponse: WKNavigationResponse, decisionHandler: @escaping (WKNavigationResponsePolicy) -> Void) {
            if navigationResponse.isForMainFrame, let http = navigationResponse.response as? HTTPURLResponse, http.statusCode >= 400 {
                report("TypeType returned HTTP \(http.statusCode) for this video.")
            }
            decisionHandler(.allow)
        }

        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            applyEQ(force: true)
        }

        func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) { handle(error) }
        func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) { handle(error) }

        private func handle(_ error: Error) {
            let ns = error as NSError
            if ns.domain == NSURLErrorDomain && ns.code == NSURLErrorCancelled { return }
            report("TypeType could not be loaded: \(ns.localizedDescription)")
        }

        func webViewWebContentProcessDidTerminate(_ webView: WKWebView) {
            report("The TypeType player stopped unexpectedly and is being reloaded.")
            webView.reload()
        }
    }

    // Bootstrap injected into the TypeType page. Playback reporting, native controls and menu
    // discovery never depend on the equalizer; the equalizer only ever attaches to a proven-safe
    // element and is verified by measuring the signal that actually leaves the filter graph.
    static let bootstrap = #"""
    (() => {
      if (window.__traptubeInstalled) return;
      window.__traptubeInstalled = true;
      const post = value => { try { window.webkit.messageHandlers.trapPlayer.postMessage(value); } catch (_) {} };
      const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
      const hz = [32,64,125,250,500,1000,2000,3000,4000,5000,6000,7000,8000,10000,12000,16000];
      const eqDisabled = window.__traptubeEQDisabled === true;
      const startedAt = Date.now();
      let settings = {gains:Array(16).fill(0), bass:0, master:1};
      let video = null, playbackCleanup = [], eq = null, starting = false, eqAttempts = 0, retryTimer = null;
      let streamGen = 0, missingReported = false, lastEQ = "";
      const captured = new WeakSet();   // an element may be handed to createMediaElementSource only once

      // ---- Equalizer status (distinct from playback errors) ---------------------------------
      const reportEQ = (state, message, canReload) => {
        const key = state + "|" + (message || "") + "|" + (canReload ? 1 : 0);
        if (key === lastEQ) return;
        lastEQ = key;
        post({type:"eqStatus", state, message:message || null, canReload:!!canReload});
      };

      // ---- Playback reporting (independent of EQ) ---------------------------------------------
      const postState = () => {
        if (!video) return;
        post({type:"state", currentTime:video.currentTime || 0, duration:Number.isFinite(video.duration) ? video.duration : 0,
              paused:video.paused, ended:video.ended});
      };
      const mediaErrorText = error => {
        if (!error) return "unknown error";
        const names = {1:"playback aborted", 2:"network error", 3:"decode error", 4:"stream not supported"};
        return (names[error.code] || "unknown error") + (error.message ? " (" + error.message + ")" : "");
      };

      // ---- Equalizer -------------------------------------------------------------------------------
      const apply = () => {
        if (!eq) return;
        hz.forEach((_, i) => { eq.filters[i].gain.value = Number(settings.gains[i] || 0); });
        eq.shelf.gain.value = Number(settings.bass || 0);
        const peakBoost = Math.max(0, ...settings.gains.map(value => Number(value) || 0)) + Number(settings.bass || 0);
        const headroomDB = -Math.min(18, peakBoost * 0.5);
        const master = Math.max(0, Math.min(2, Number(settings.master ?? 1)));
        eq.gain.gain.value = master * Math.pow(10, headroomDB / 20);
      };
      window.__traptubeSetEQ = value => { settings = Object.assign(settings, value || {}); apply(); };

      const teardownEQ = () => {
        clearTimeout(retryTimer);
        if (!eq) return;
        const old = eq; eq = null;
        clearInterval(old.monitor);
        try { old.source.disconnect(); old.filters.forEach(node => node.disconnect()); old.shelf.disconnect(); old.gain.disconnect(); old.analyser.disconnect(); } catch (_) {}
        try { old.context.close(); } catch (_) {}
      };

      // createMediaElementSource() silences media the browser considers cross-origin without CORS,
      // and it cannot be undone for that element. So only tap elements that are safe to process.
      const tapVerdict = el => {
        const src = el.currentSrc || el.src || "";
        if (el.srcObject || src.startsWith("blob:") || src.startsWith("mediasource:")) return {ok:true};
        if (!src) return {ok:false, wait:true};
        try { if (new URL(src, location.href).origin === location.origin) return {ok:true}; } catch (_) {}
        if (el.crossOrigin === "anonymous" || el.crossOrigin === "use-credentials") return {ok:true};
        return {ok:false, reason:"This stream is served from another origin without CORS permission, so the browser does not allow the equalizer to process it."};
      };

      const startEQ = async () => {
        if (!video || eq || starting) return;
        if (eqDisabled) { reportEQ("unavailable", "The equalizer is turned off for this video.", false); return; }
        const el = video;
        if (captured.has(el)) return;
        const verdict = tapVerdict(el);
        if (!verdict.ok) { verdict.wait ? reportEQ("connecting") : reportEQ("unavailable", verdict.reason, false); return; }
        if (el.paused) { reportEQ("connecting"); return; }   // start once playing so the audio context may run
        const Ctx = window.AudioContext || window.webkitAudioContext;
        if (!Ctx) { reportEQ("unavailable", "Web Audio is not available in this WebKit runtime.", false); return; }
        starting = true;
        reportEQ("connecting");
        let context = null, source = null;
        try {
          context = new Ctx();
          if (context.state !== "running") await Promise.race([context.resume(), sleep(1500)]);
          if (video !== el || !el.isConnected) { context.close(); return; }
          if (context.state !== "running") {
            // Never capture the element with a suspended context: that would mute the stream.
            try { context.close(); } catch (_) {}
            eqAttempts++;
            if (eqAttempts >= 4) reportEQ("unavailable", "The browser kept the audio engine suspended, so the equalizer could not start.", false);
            else retryTimer = setTimeout(startEQ, 1500);
            return;
          }
          source = context.createMediaElementSource(el);
          captured.add(el);
          const filters = hz.map(frequency => {
            const node = context.createBiquadFilter();
            node.type = "peaking"; node.frequency.value = frequency; node.Q.value = 1;
            return node;
          });
          const shelf = context.createBiquadFilter(); shelf.type = "lowshelf"; shelf.frequency.value = 90; shelf.Q.value = 0.7;
          const gain = context.createGain();
          const analyser = context.createAnalyser(); analyser.fftSize = 1024;
          let node = source;
          filters.forEach(filter => { node.connect(filter); node = filter; });
          node.connect(shelf); shelf.connect(gain); gain.connect(context.destination); gain.connect(analyser);
          eq = {context, source, filters, shelf, gain, analyser, monitor:null, silentSince:null, proven:false};
          apply();
          monitorEQ(el);
        } catch (error) {
          // If the element was already captured, give it a direct path so playback is never left silent.
          try { if (source && context) source.connect(context.destination); } catch (_) {}
          reportEQ("unavailable", "Equalizer could not be attached: " + (error && error.message ? error.message : String(error)), false);
        } finally { starting = false; }
      };

      const monitorEQ = el => {
        const samples = new Float32Array(eq.analyser.fftSize);
        eq.monitor = setInterval(() => {
          if (!eq || video !== el) return;
          if (eq.context.state !== "running") {
            eq.context.resume().catch(() => {});
            if (!eq.proven) reportEQ("connecting");
            return;
          }
          eq.analyser.getFloatTimeDomainData(samples);
          let peak = 0;
          for (let i = 0; i < samples.length; i++) { const a = Math.abs(samples[i]); if (a > peak) peak = a; }
          if (peak > 1e-5) { eq.proven = true; eq.silentSince = null; reportEQ("active"); return; }
          const audible = !el.paused && !el.ended && !el.muted && el.volume > 0 && el.readyState >= 3;
          if (!audible) { eq.silentSince = null; return; }
          eq.silentSince = eq.silentSince || Date.now();
          if (!eq.proven && Date.now() - eq.silentSince > 4000) {
            reportEQ("unavailable", "No audio is reaching the equalizer; the browser may be blocking processing of this stream.", true);
          }
        }, 400);
      };

      // ---- Video element lifecycle ---------------------------------------------------------------
      const unbindVideo = () => {
        playbackCleanup.forEach(fn => { try { fn(); } catch (_) {} });
        playbackCleanup = [];
        teardownEQ();
        video = null; starting = false;
      };
      const bindVideo = el => {
        unbindVideo();
        video = el; eqAttempts = 0; streamGen++; missingReported = false; lastEQ = "";
        const on = (name, handler) => { el.addEventListener(name, handler); playbackCleanup.push(() => el.removeEventListener(name, handler)); };
        ["timeupdate","durationchange","play","playing","pause","ended","seeked","waiting","loadedmetadata"].forEach(name => on(name, postState));
        on("error", () => post({type:"playerError", message:"Playback failed: " + mediaErrorText(el.error)}));
        on("loadedmetadata", () => { streamGen++; scanSoon(); startEQ(); });
        on("emptied", () => { streamGen++; post({type:"videoQualities", items:[]}); post({type:"audioTracks", items:[]}); });
        on("play", startEQ);
        on("playing", startEQ);
        reportEQ("connecting");
        postState();
        startEQ();
      };
      const pickVideo = () => {
        const all = Array.from(document.querySelectorAll("video")).filter(item => item.isConnected);
        return all.find(item => item.closest(".vds-player")) || all[0] || null;
      };
      const sync = () => {
        if (video && !video.isConnected) unbindVideo();
        const candidate = pickVideo();
        if (candidate && candidate !== video) bindVideo(candidate);
        if (!candidate && !video && !missingReported && Date.now() - startedAt > 15000) {
          missingReported = true;
          post({type:"playerError", message:"TypeType did not start a video player."});
        }
      };

      // ---- Native control (works with or without EQ) ---------------------------------------------
      const play = () => {
        const result = video.play();
        if (result && result.catch) result.catch(error => post({type:"playerError", message:"Playback could not start: " + (error && error.message ? error.message : error)}));
      };
      window.__traptubeControl = (command, value) => {
        if (!video) { post({type:"playerError", message:"The TypeType player is not ready yet."}); return; }
        if (eq && eq.context.state === "suspended") eq.context.resume().catch(() => {});
        if (command === "toggle") { (video.paused || video.ended) ? play() : video.pause(); }
        else if (command === "play") play();
        else if (command === "pause") video.pause();
        else if (command === "seek" && Number.isFinite(Number(value))) {
          const target = Number(value);
          if (Number.isFinite(video.duration)) video.currentTime = Math.max(0, Math.min(video.duration, target));
          else if (video.seekable && video.seekable.length) video.currentTime = Math.max(video.seekable.start(0), Math.min(video.seekable.end(video.seekable.length - 1), target));
        }
        postState();
      };

      // ---- Quality / audio-track menus (read from the real TypeType menus) -------------------------
      const MENUS = {video:".typetype-quality-menu", audio:".vds-audio-menu"};
      const MESSAGE = {video:"videoQualities", audio:"audioTracks"};
      const clean = text => String(text || "").replace(/\s+/g, " ").trim();
      const labelOf = node => clean(node.innerText || node.textContent);
      const isChecked = node => node.getAttribute("aria-checked") === "true" || node.getAttribute("aria-pressed") === "true" || node.hasAttribute("data-checked");
      const valueOf = node => {
        for (const attr of ["data-itag", "data-value", "data-id", "value"]) { const v = node.getAttribute(attr); if (v) return v; }
        return (typeof node.value === "string" && node.value) ? node.value : null;
      };
      const optionNodes = (root, trigger) => {
        const controlled = trigger.getAttribute("aria-controls");
        const scope = (controlled && document.getElementById(controlled)) || root.querySelector(".vds-menu-items") || root;
        let nodes = Array.from(scope.querySelectorAll("[role=radio],[role=menuitemradio]"));
        if (!nodes.length) nodes = Array.from(scope.querySelectorAll("button")).filter(node => labelOf(node));
        return nodes;
      };
      const describe = nodes => nodes.map((node, index) => {
        const label = labelOf(node), value = valueOf(node);
        return {id: value !== null ? "v:" + value : "i:" + index + ":" + label, label, selected:isChecked(node)};
      }).filter(option => option.label);

      let menuQueue = Promise.resolve();
      const withMenu = (kind, work) => {
        const run = menuQueue.then(async () => {
          const root = document.querySelector(MENUS[kind]);
          const trigger = root && (root.querySelector("[aria-haspopup]") || root.querySelector("button"));
          if (!trigger) return work(null, null, []);
          const wasOpen = trigger.getAttribute("aria-expanded") === "true";
          if (!wasOpen) trigger.click();
          let nodes = [];
          for (let i = 0; i < 20; i++) { nodes = optionNodes(root, trigger); if (nodes.length) break; await sleep(50); }
          try { return await work(root, trigger, nodes); }
          finally { if (!wasOpen && trigger.getAttribute("aria-expanded") === "true") trigger.click(); }
        }).catch(() => {});
        menuQueue = run;
        return run;
      };
      const scanned = {video:-1, audio:-1};
      const scanMenu = kind => withMenu(kind, (root, trigger, nodes) => {
        const items = describe(nodes);
        post({type:MESSAGE[kind], items});
        return items;
      });
      window.__traptubeScanMenus = kind => Object.keys(MENUS).filter(name => !kind || name === kind).forEach(scanMenu);
      let scanTimer = null;
      const scanSoon = () => { clearTimeout(scanTimer); scanTimer = setTimeout(maybeScan, 400); };
      const maybeScan = () => {
        Object.keys(MENUS).forEach(kind => {
          if (!document.querySelector(MENUS[kind]) || scanned[kind] === streamGen) return;
          scanned[kind] = streamGen;
          scanMenu(kind).then(items => { if (!items || !items.length) scanned[kind] = -1; });
        });
      };
      window.__traptubeSelectOption = request => {
        const kind = request && request.kind;
        if (!MENUS[kind]) return;
        withMenu(kind, async (root, trigger, nodes) => {
          const options = describe(nodes);
          // Match on the stable identifier AND the label so an unrelated or re-ordered item is never clicked.
          const index = options.findIndex(option => option.id === request.id && option.label === request.label);
          if (index < 0) {
            post({type:"menuNotice", message:"That option is no longer available for this stream."});
            return;
          }
          nodes[index].click();
          await sleep(250);
        }).then(() => scanMenu(kind));
      };

      new MutationObserver(() => { clearTimeout(window.__traptubeSyncTimer); window.__traptubeSyncTimer = setTimeout(() => { sync(); maybeScan(); }, 150); })
        .observe(document, {childList:true, subtree:true});
      window.addEventListener("pagehide", unbindVideo);
      sync();
      setInterval(() => { sync(); postState(); maybeScan(); }, 1000);
    })();
    """#
}

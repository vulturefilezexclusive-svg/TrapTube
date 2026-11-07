import SwiftUI
import WebKit
import AVKit
import UIKit

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
                    Text("TrapTube").font(.largeTitle.bold()).foregroundStyle(.white)
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

private struct TypeTypePlayerOption: Identifiable {
    let label: String
    let selected: Bool
    var id: String { label }
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
    @State private var eqReady = false
    @State private var eqError: String?
    @State private var videoQualities: [TypeTypePlayerOption] = []
    @State private var audioTracks: [TypeTypePlayerOption] = []
    @State private var showEQ = false
    @State private var showTrapTubeMenu = false

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()
            TypeTypeWebView(url: url, gains: audio.eqGains, bass: audio.bassBoost, master: audio.masterGain,
                            onCreated: { webView = $0 }, onMessage: receive)
            VStack(spacing: 0) {
                HStack {
                    Button { dismiss() } label: {
                        Image(systemName: "xmark").font(.headline.bold()).foregroundStyle(.white)
                            .frame(width: 38, height: 38).background(.black.opacity(0.7), in: Circle())
                    }
                    Text(title).font(.subheadline.bold()).foregroundStyle(.white).lineLimit(1)
                    Spacer(minLength: 4)
                    Button { showTrapTubeMenu = true } label: {
                        Image(uiImage: UIImage(named: "TrapTubeIcon") ?? UIImage(systemName: "app.fill")!).resizable().scaledToFill().frame(width: 38, height: 38)
                            .clipShape(RoundedRectangle(cornerRadius: 11))
                            .overlay(RoundedRectangle(cornerRadius: 11).stroke(.white.opacity(0.25), lineWidth: 1))
                    }.accessibilityLabel("Open TrapTube player menu")
                }.padding(14).background(LinearGradient(colors: [.black.opacity(0.85), .clear], startPoint: .top, endPoint: .bottom))
                Spacer()
                VStack(spacing: 10) {
                    HStack(spacing: 12) {
                        Button { command("toggle") } label: {
                            Image(systemName: isPlaying ? "pause.fill" : "play.fill")
                                .font(.title3.bold()).foregroundStyle(.white).frame(width: 42, height: 42)
                                .background(theme.accent, in: Circle())
                        }
                        VStack(spacing: 3) {
                            Slider(value: Binding(get: { scrubbing ? scrubValue : (duration > 0 ? currentTime / duration : 0) },
                                                  set: { scrubValue = $0; scrubbing = true }),
                                   in: 0...1, onEditingChanged: { editing in
                                if !editing { command("seek", scrubValue * duration); scrubbing = false }
                            }).tint(theme.accent)
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
                        if let eqError {
                            Text(eqError).font(.caption2).foregroundStyle(Color(hex: "FF8A8A")).lineLimit(2)
                        } else if !eqReady {
                            Text("Connecting EQ…").font(.caption2).foregroundStyle(.white.opacity(0.65))
                        }
                        Spacer(minLength: 0)
                        Menu {
                            if videoQualities.isEmpty { Text("No selectable video qualities for this stream") }
                            ForEach(videoQualities) { option in
                                Button { select(kind: "video", label: option.label) } label: {
                                    if option.selected { Label(option.label, systemImage: "checkmark") } else { Text(option.label) }
                                }
                            }
                        } label: {
                            Label("Quality", systemImage: "4k.tv").font(.caption.bold()).foregroundStyle(.white)
                                .padding(.horizontal, 10).padding(.vertical, 9).background(.white.opacity(0.12), in: Capsule())
                        }
                        Menu {
                            if audioTracks.isEmpty { Text("No alternate audio tracks for this stream") }
                            ForEach(audioTracks) { option in
                                Button { select(kind: "audio", label: option.label) } label: {
                                    if option.selected { Label(option.label, systemImage: "checkmark") } else { Text(option.label) }
                                }
                            }
                        } label: {
                            Label("Audio track", systemImage: "waveform").font(.caption.bold()).foregroundStyle(.white)
                                .padding(.horizontal, 10).padding(.vertical, 9).background(.white.opacity(0.12), in: Capsule())
                        }
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
        .sheet(isPresented: $showTrapTubeMenu) {
            TrapTubePlayerMenu(title: title, videoURL: url, onPlayback: {
                showTrapTubeMenu = false
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) { showEQ = true }
            })
            .presentationDetents([.medium, .large])
            .presentationDragIndicator(.visible)
            .presentationCornerRadius(28)
            .preferredColorScheme(.dark)
        }
        .onChange(of: audio.eqGains) { _, _ in applyEQ() }
        .onChange(of: audio.bassBoost) { _, _ in applyEQ() }
        .onChange(of: audio.masterGain) { _, _ in applyEQ() }
    }

    private func receive(_ body: [String: Any]) {
        switch body["type"] as? String {
        case "state":
            if let value = body["currentTime"] as? Double { currentTime = value }
            if let value = body["duration"] as? Double { duration = value }
            if let value = body["paused"] as? Bool { isPlaying = !value }
        case "eqStatus":
            eqReady = body["ready"] as? Bool ?? false
            eqError = body["error"] as? String
        case "videoQualities": videoQualities = options(body["items"])
        case "audioTracks": audioTracks = options(body["items"])
        case "playerError": eqError = body["message"] as? String
        default: break
        }
    }

    private func options(_ raw: Any?) -> [TypeTypePlayerOption] {
        guard let rows = raw as? [[String: Any]] else { return [] }
        return rows.compactMap { row in
            guard let label = row["label"] as? String, !label.isEmpty else { return nil }
            return TypeTypePlayerOption(label: label, selected: row["selected"] as? Bool ?? false)
        }
    }

    private func command(_ name: String, _ value: Double = 0) {
        webView?.evaluateJavaScript("window.__traptubeControl && window.__traptubeControl('\(name)', \(value));")
    }

    private func select(kind: String, label: String) {
        guard let data = try? JSONSerialization.data(withJSONObject: [kind, label]),
              let json = String(data: data, encoding: .utf8) else { return }
        webView?.evaluateJavaScript("window.__traptubeSelectOption && window.__traptubeSelectOption(\(json));")
    }

    private func applyEQ() {
        guard let data = try? JSONSerialization.data(withJSONObject: ["gains": audio.eqGains, "bass": audio.bassBoost, "master": audio.masterGain]),
              let json = String(data: data, encoding: .utf8) else { return }
        webView?.evaluateJavaScript("window.__traptubeSetEQ && window.__traptubeSetEQ(\(json));")
    }

    private func timeText(_ value: Double) -> String {
        let seconds = value.isFinite ? max(0, Int(value)) : 0
        return String(format: "%d:%02d", seconds / 60, seconds % 60)
    }
}

private struct TypeTypeWebView: UIViewRepresentable {
    let url: URL
    let gains: [Float]
    let bass: Float
    let master: Float
    let onCreated: (WKWebView) -> Void
    let onMessage: ([String: Any]) -> Void

    func makeCoordinator() -> Coordinator { Coordinator(onMessage: onMessage, gains: gains, bass: bass, master: master) }

    func makeUIView(context: Context) -> WKWebView {
        let content = WKUserContentController()
        content.add(context.coordinator, name: "trapPlayer")
        content.addUserScript(WKUserScript(source: Self.bootstrap, injectionTime: .atDocumentEnd, forMainFrameOnly: true))
        let configuration = WKWebViewConfiguration()
        configuration.userContentController = content
        let view = WKWebView(frame: .zero, configuration: configuration)
        view.isOpaque = false
        view.backgroundColor = .black
        view.scrollView.backgroundColor = .black
        view.navigationDelegate = context.coordinator
        context.coordinator.webView = view
        onCreated(view)
        view.load(URLRequest(url: url, cachePolicy: .useProtocolCachePolicy, timeoutInterval: 30))
        return view
    }

    func updateUIView(_ uiView: WKWebView, context: Context) {
        context.coordinator.onMessage = onMessage
        context.coordinator.setEQ(gains: gains, bass: bass, master: master)
        if uiView.url != url && !uiView.isLoading { uiView.load(URLRequest(url: url)) }
    }

    final class Coordinator: NSObject, WKScriptMessageHandler, WKNavigationDelegate {
        var onMessage: ([String: Any]) -> Void
        weak var webView: WKWebView?
        private var gains: [Float]
        private var bass: Float
        private var master: Float

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

        private func applyEQ() {
            guard let webView,
                  let data = try? JSONSerialization.data(withJSONObject: ["gains": gains, "bass": bass, "master": master]),
                  let json = String(data: data, encoding: .utf8) else { return }
            webView.evaluateJavaScript("window.__traptubeSetEQ && window.__traptubeSetEQ(\(json));")
        }

        func userContentController(_ controller: WKUserContentController, didReceive message: WKScriptMessage) {
            guard let body = message.body as? [String: Any] else { return }
            DispatchQueue.main.async { self.onMessage(body) }
        }

        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            applyEQ()
            webView.evaluateJavaScript("window.__traptubeScanMenus && window.__traptubeScanMenus();")
        }

        func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
            onMessage(["type": "playerError", "message": "TypeType playback failed: \(error.localizedDescription)"])
        }
    }

    private static let bootstrap = #"""
    (() => {
      const post = value => { try { window.webkit.messageHandlers.trapPlayer.postMessage(value); } catch (_) {} };
      const hz = [32,64,125,250,500,1000,2000,3000,4000,5000,6000,7000,8000,10000,12000,16000];
      let video = null, context = null, filters = [], shelf = null, gain = null, directSource = null;
      let settings = {gains:Array(16).fill(0), bass:0, master:1};
      const bootstrapStartedAt = Date.now();
      let missingVideoReported = false;
      const state = () => {
        if (video) post({type:"state", currentTime:video.currentTime || 0, duration:Number.isFinite(video.duration) ? video.duration : 0, paused:video.paused});
      };
      const apply = () => {
        if (!filters.length || !shelf || !gain) return;
        hz.forEach((_, i) => filters[i].gain.value = Number(settings.gains[i] || 0));
        shelf.gain.value = Number(settings.bass || 0);
        const peakBoost = Math.max(0, ...settings.gains.map(value => Number(value) || 0)) + Number(settings.bass || 0);
        const headroomDB = -Math.min(18, peakBoost * 0.5);
        const master = Math.max(0, Math.min(2, Number(settings.master ?? 1)));
        gain.gain.value = master * Math.pow(10, headroomDB / 20);
      };
      window.__traptubeSetEQ = value => { settings = Object.assign(settings, value || {}); apply(); };
      const attach = () => {
        const candidate = document.querySelector("main .vds-player video") || document.querySelector(".vds-player video") || document.querySelector("video");
        if (!candidate) {
          if (!missingVideoReported && Date.now() - bootstrapStartedAt > 12000) {
            missingVideoReported = true;
            post({type:"eqStatus", ready:false, error:"Streaming EQ unavailable: TypeType has not exposed a playable video element yet."});
          }
          return;
        }
        if (candidate === video) return;
        video = candidate;
        missingVideoReported = false;
        try {
          const AudioContextClass = window.AudioContext || window.webkitAudioContext;
          if (!AudioContextClass) throw new Error("Web Audio is unavailable in this WebKit runtime.");
          context = new AudioContextClass();
          directSource = context.createMediaElementSource(video);
          // Keep the stream audible if filter construction fails; EQ status reports the failure.
          directSource.connect(context.destination);
          filters = hz.map(frequency => {
            const node = context.createBiquadFilter();
            node.type = "peaking"; node.frequency.value = frequency; node.Q.value = 1;
            return node;
          });
          shelf = context.createBiquadFilter(); shelf.type = "lowshelf"; shelf.frequency.value = 90; shelf.Q.value = 0.7;
          gain = context.createGain();
          let node = directSource;
          filters.forEach(filter => { node.connect(filter); node = filter; });
          node.connect(shelf); shelf.connect(gain); gain.connect(context.destination);
          directSource.disconnect(context.destination);
          video.addEventListener("play", () => { if (context.state === "suspended") context.resume(); state(); });
          ["timeupdate","durationchange","play","pause","ended"].forEach(event => video.addEventListener(event, state));
          apply();
          post({type:"eqStatus", ready:true}); state();
        } catch (error) {
          try {
            if (directSource && context) {
              directSource.disconnect();
              filters.forEach(node => node.disconnect());
              if (shelf) shelf.disconnect();
              if (gain) gain.disconnect();
              directSource.connect(context.destination);
            }
          } catch (_) {}
          post({type:"eqStatus", ready:false, error:"Streaming EQ unavailable: " + (error && error.message ? error.message : String(error))});
        }
      };
      window.__traptubeControl = (command, value) => {
        if (!video) return;
        if (command === "toggle") {
          if (video.paused) { if (context && context.state === "suspended") context.resume(); video.play().catch(e => post({type:"playerError",message:e.message})); }
          else video.pause();
        }
        if (command === "play") { if (context && context.state === "suspended") context.resume(); video.play().catch(e => post({type:"playerError",message:e.message})); }
        if (command === "pause") video.pause();
        if (command === "seek" && Number.isFinite(Number(value)) && Number.isFinite(video.duration)) video.currentTime = Math.max(0, Math.min(video.duration, Number(value)));
      };
      const selectors = {video:".typetype-quality-menu", audio:".vds-audio-menu"};
      window.__traptubeScanMenus = (onlyKind) => Object.entries(selectors).filter(([kind]) => !onlyKind || kind === onlyKind).forEach(([kind, selector]) => {
        const trigger = document.querySelector(selector + " button");
        if (!trigger) { post({type:kind === "video" ? "videoQualities" : "audioTracks",items:[]}); return; }
        trigger.click();
        setTimeout(() => {
          const items = Array.from(document.querySelectorAll(".vds-menu-items [role=radio], .vds-menu-items button"))
            .map(node => ({label:(node.innerText || node.textContent || "").trim(),selected:node.getAttribute("aria-checked") === "true" || node.getAttribute("aria-pressed") === "true"}))
            .filter(item => item.label.length);
          trigger.click();
          post({type:kind === "video" ? "videoQualities" : "audioTracks",items});
        }, 220);
      });
      window.__traptubeSelectOption = ([kind,label]) => {
        const trigger = document.querySelector((selectors[kind] || "") + " button");
        if (!trigger) return;
        trigger.click();
        setTimeout(() => {
          const wanted = String(label).trim();
          const option = Array.from(document.querySelectorAll(".vds-menu-items [role=radio], .vds-menu-items button"))
            .find(node => (node.innerText || node.textContent || "").trim() === wanted);
          if (option) option.click(); else trigger.click();
          setTimeout(window.__traptubeScanMenus, 150);
        }, 220);
      };
      let videoMenuScanned = false, audioMenuScanned = false;
      new MutationObserver(() => {
        attach();
        if (!videoMenuScanned && document.querySelector(".typetype-quality-menu")) {
          videoMenuScanned = true;
          setTimeout(() => window.__traptubeScanMenus("video"), 350);
        }
        if (!audioMenuScanned && document.querySelector(".vds-audio-menu")) {
          audioMenuScanned = true;
          setTimeout(() => window.__traptubeScanMenus("audio"), 350);
        }
      }).observe(document.documentElement,{childList:true,subtree:true});
      attach();
      setInterval(() => { attach(); state(); }, 700);
    })();
    """#
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
                        menuInfoText = "Transcript access depends on the captions and transcript data supplied by the connected TypeType instance."
                        showMenuInfo = true
                    }
                    menuRow("Information", detail: "Media and stream information", icon: "info.circle") {
                        menuInfoText = "Playback and stream information are supplied by your connected TypeType service."
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
                        Text("Downloads are processed by the connected TypeType downloader and saved on this device.")
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
                            quality = "best"
                            format = newMode == "audio" ? "m4a" : "mp4"
                        }

                        if mode == "video" || mode == "audio" {
                            Picker(mode == "video" ? "Video quality" : "Audio quality", selection: $quality) {
                                Text("Best available").tag("best")
                                if mode == "video" {
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
                            Text("Video and audio streams are selected by the TypeType downloader, then muxed into the chosen container.")
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

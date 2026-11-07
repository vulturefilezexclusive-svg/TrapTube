import SwiftUI
import WebKit
import AVKit
import UIKit

struct YouTubeView: View {
    @AppStorage("discovery.sourceURL") private var discoverySourceURL = ""
    @State private var selectedWatch: YouTubeWatchItem?
    @State private var latestVideoURL = URL(string: "https://www.youtube.com/")!
    @State private var latestVideoTitle = "YouTube video"
    @State private var showDownloads = false

    private var homeURL: URL {
        let raw = discoverySourceURL.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let url = URL(string: raw), let scheme = url.scheme?.lowercased(),
              ["http", "https"].contains(scheme), url.host != nil else {
            return URL(string: "https://www.youtube.com/")!
        }
        return url
    }

    var body: some View {
        StreamingHomeWebView(url: homeURL) { url in
            latestVideoURL = url
            selectedWatch = YouTubeWatchItem(url: url, title: "YouTube video")
        }
        .ignoresSafeArea(edges: .bottom)
        .overlay(alignment: .topTrailing) {
            Button { showDownloads = true } label: {
                Image(systemName: "arrow.down.circle")
                    .font(.title2.weight(.semibold))
                    .foregroundStyle(.white)
                    .padding(10)
                    .background(.black.opacity(0.72), in: Circle())
            }
            .accessibilityLabel("Open downloads")
            .padding(.top, 8)
            .padding(.trailing, 14)
        }
        .fullScreenCover(item: $selectedWatch) { item in
            YouTubeWatchSheet(url: item.url, downloadURL: item.url, title: item.title)
        }
        .sheet(isPresented: $showDownloads) {
            TrapTubeDownloadsSheet(title: latestVideoTitle, videoURL: latestVideoURL)
                .preferredColorScheme(.dark)
                .presentationDetents([.large])
                .presentationDragIndicator(.visible)
        }
    }
}

private struct YouTubeWatchItem: Identifiable {
    let id = UUID()
    let url: URL
    let title: String
}

private struct StreamingHomeWebView: UIViewRepresentable {
    let url: URL
    let onWatch: (URL) -> Void

    func makeCoordinator() -> Coordinator { Coordinator(onWatch: onWatch) }

    func makeUIView(context: Context) -> WKWebView {
        let content = WKUserContentController()
        content.add(context.coordinator, name: "trapHome")
        let script = """
        document.addEventListener('click', function(event) {
          const anchor = event.target && event.target.closest ? event.target.closest('a[href]') : null;
          if (!anchor) return;
          let target;
          try { target = new URL(anchor.href, location.href); } catch (_) { return; }
          if (target.hostname.endsWith('youtube.com') &&
              (target.pathname === '/watch' || target.pathname.startsWith('/shorts/') ||
               target.pathname.startsWith('/live/'))) {
            event.preventDefault();
            event.stopPropagation();
            window.webkit.messageHandlers.trapHome.postMessage(target.href);
          }
        }, true);
        """
        content.addUserScript(WKUserScript(source: script, injectionTime: .atDocumentEnd, forMainFrameOnly: true))
        let configuration = WKWebViewConfiguration()
        configuration.userContentController = content
        configuration.allowsInlineMediaPlayback = true
        configuration.mediaTypesRequiringUserActionForPlayback = []
        let web = WKWebView(frame: .zero, configuration: configuration)
        web.navigationDelegate = context.coordinator
        web.allowsBackForwardNavigationGestures = true
        web.scrollView.contentInsetAdjustmentBehavior = .never
        context.coordinator.lastLoaded = url
        web.load(URLRequest(url: url, cachePolicy: .useProtocolCachePolicy, timeoutInterval: 30))
        return web
    }

    func updateUIView(_ web: WKWebView, context: Context) {
        context.coordinator.onWatch = onWatch
        if context.coordinator.lastLoaded != url {
            context.coordinator.lastLoaded = url
            web.load(URLRequest(url: url))
        }
    }

    final class Coordinator: NSObject, WKNavigationDelegate, WKScriptMessageHandler {
        var onWatch: (URL) -> Void
        var lastLoaded: URL?
        init(onWatch: @escaping (URL) -> Void) { self.onWatch = onWatch }

        func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
            guard let raw = message.body as? String, let url = URL(string: raw) else { return }
            onWatch(url)
        }

        func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction,
                     decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
            guard let url = navigationAction.request.url,
                  url.host?.lowercased().hasSuffix("youtube.com") == true,
                  url.path == "/watch" || url.path.hasPrefix("/shorts/") || url.path.hasPrefix("/live/"),
                  navigationAction.targetFrame?.isMainFrame != false else {
                decisionHandler(.allow)
                return
            }
            onWatch(url)
            decisionHandler(.cancel)
        }
    }
}

private struct YouTubePlayerOption: Identifiable {
    let label: String
    let selected: Bool
    var id: String { label }
}

private struct YouTubeWatchSheet: View {
    let url: URL
    let downloadURL: URL
    let title: String

    var body: some View {
        YouTubePlainVideoWebView(url: url)
            .background(Color.black.ignoresSafeArea())
            .ignoresSafeArea()
            .preferredColorScheme(.dark)
    }
}

private struct YouTubePlainVideoWebView: UIViewRepresentable {
    let url: URL

    func makeUIView(context: Context) -> WKWebView {
        let configuration = WKWebViewConfiguration()
        configuration.allowsInlineMediaPlayback = true
        configuration.mediaTypesRequiringUserActionForPlayback = []
        let webView = WKWebView(frame: .zero, configuration: configuration)
        webView.backgroundColor = .black
        webView.scrollView.backgroundColor = .black
        webView.isOpaque = false
        webView.allowsBackForwardNavigationGestures = true
        webView.load(URLRequest(url: url, cachePolicy: .useProtocolCachePolicy, timeoutInterval: 30))
        return webView
    }

    func updateUIView(_ webView: WKWebView, context: Context) {}
}

private struct YouTubePlayerWebView: UIViewRepresentable {
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
        configuration.allowsInlineMediaPlayback = true
        configuration.mediaTypesRequiringUserActionForPlayback = []
        let view = WKWebView(frame: .zero, configuration: configuration)
        view.isOpaque = false
        view.backgroundColor = .black
        view.scrollView.backgroundColor = .black
        view.navigationDelegate = context.coordinator
        context.coordinator.webView = view
        context.coordinator.lastLoaded = url
        onCreated(view)
        view.load(URLRequest(url: url, cachePolicy: .useProtocolCachePolicy, timeoutInterval: 30))
        return view
    }

    func updateUIView(_ uiView: WKWebView, context: Context) {
        context.coordinator.onMessage = onMessage
        context.coordinator.setEQ(gains: gains, bass: bass, master: master)
        if context.coordinator.lastLoaded != url {
            context.coordinator.lastLoaded = url
            uiView.load(URLRequest(url: url))
        }
    }

    final class Coordinator: NSObject, WKScriptMessageHandler, WKNavigationDelegate {
        var onMessage: ([String: Any]) -> Void
        var lastLoaded: URL?
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
            onMessage(["type": "playerError", "message": "YouTube playback failed: \(error.localizedDescription)"])
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
        hz.forEach((frequency, i) => {
          filters[i].frequency.setTargetAtTime(frequency, context.currentTime, 0.015);
          filters[i].gain.setTargetAtTime(Number(settings.gains[i] || 0), context.currentTime, 0.015);
          filters[i].Q.setTargetAtTime(1.15, context.currentTime, 0.015);
        });
        shelf.gain.setTargetAtTime(Number(settings.bass || 0), context.currentTime, 0.015);
        const peakBoost = Math.max(0, ...settings.gains.map(value => Number(value) || 0)) + Number(settings.bass || 0);
        const headroomDB = -Math.min(18, peakBoost * 0.5);
        const master = Math.max(0, Math.min(2, Number(settings.master ?? 1)));
        gain.gain.setTargetAtTime(master * Math.pow(10, headroomDB / 20), context.currentTime, 0.015);
      };
      window.__traptubeSetEQ = value => { settings = Object.assign(settings, value || {}); apply(); };
      const mediaGraphs = new WeakMap();
      let activeElement = null, activeSource = null;
      const audioElements = () => Array.from(document.querySelectorAll("video, audio"));
      const chooseMediaElement = () => {
        const elements = audioElements().filter(element => {
          try { return !!(element.currentSrc || element.src) && element.readyState >= 2 && !element.ended; }
          catch (_) { return false; }
        });
        const playing = elements.filter(element => !element.paused && !element.muted && element.volume > 0);
        return playing[0] || elements.find(element => element === activeElement) || elements[0] || null;
      };
      const ensureGraph = element => {
        let graph = mediaGraphs.get(element);
        if (graph) return graph;
        const AudioContextClass = window.AudioContext || window.webkitAudioContext;
        if (!AudioContextClass) throw new Error("Web Audio is unavailable in this WebKit runtime.");
        if (!context) {
          context = new AudioContextClass();
          filters = hz.map(frequency => {
            const node = context.createBiquadFilter();
            node.type = "peaking";
            node.frequency.value = frequency;
            node.Q.value = 1.15;
            node.gain.value = 0;
            return node;
          });
          shelf = context.createBiquadFilter();
          shelf.type = "lowshelf";
          shelf.frequency.value = 90;
          shelf.Q.value = 0.7;
          gain = context.createGain();
          let node = gain;
          node.connect(context.destination);
          shelf.connect(gain);
          filters[filters.length - 1].connect(shelf);
          for (let index = filters.length - 2; index >= 0; index--) filters[index].connect(filters[index + 1]);
          context.addEventListener("statechange", reportAudioState);
        }
        const source = context.createMediaElementSource(element);
        graph = {source};
        mediaGraphs.set(element, graph);
        return graph;
      };
      const reportAudioState = () => {
        const running = !!context && context.state === "running";
        post({
          type:"eqStatus",
          ready:running && !!activeSource,
          error:running && activeSource ? null : "Streaming EQ is waiting for iOS audio activation. Press Play in the player to start processed audio."
        });
      };
      const resumeAudio = () => {
        if (!context || context.state === "running") { reportAudioState(); return; }
        context.resume().then(reportAudioState).catch(error => {
          post({type:"eqStatus",ready:false,error:"Tap Play to activate streaming audio processing: " + error.message});
        });
      };
      const attach = () => {
        const candidate = chooseMediaElement();
        if (!candidate) {
          if (!missingVideoReported && Date.now() - bootstrapStartedAt > 12000) {
            missingVideoReported = true;
            post({type:"eqStatus", ready:false, error:"Streaming EQ unavailable: YouTube has not exposed an active audio/video element yet."});
          }
          return;
        }
        missingVideoReported = false;
        if (candidate !== activeElement) {
          try {
            if (activeSource) activeSource.disconnect();
            const graph = ensureGraph(candidate);
            activeElement = candidate;
            video = candidate;
            activeSource = graph.source;
            activeSource.connect(filters[0]);
            apply();
            resumeAudio();
            state();
          } catch (error) {
            post({type:"eqStatus",ready:false,error:"Streaming EQ unavailable for this media element: " + (error && error.message ? error.message : String(error))});
            // If Web Audio cannot attach, preserve the native media output.
            try {
              if (activeSource) activeSource.disconnect();
              activeSource = null;
              activeElement = null;
            } catch (_) {}
          }
        } else if (context && context.state !== "running" && !candidate.paused) {
          resumeAudio();
        }
      };
      const watchElement = element => {
        if (element.__traptubeEQObserved) return;
        element.__traptubeEQObserved = true;
        ["play","playing","canplay","loadedmetadata","emptied","loadstart","volumechange"].forEach(event => {
          element.addEventListener(event, () => { attach(); state(); }, {passive:true});
        });
      };
      audioElements().forEach(watchElement);
      const observer = new MutationObserver(() => {
        audioElements().forEach(watchElement);
        attach();
      });
      observer.observe(document.documentElement,{childList:true,subtree:true,attributes:true,attributeFilter:["src"]});
      attach();
      setInterval(() => {
        audioElements().forEach(watchElement);
        attach();
        state();
      }, 500);
      window.__traptubeControl = (command, value) => {
        if (!video) return;
        if (command === "toggle") {
          if (video.paused) {
            if (context && context.state !== "running") context.resume().catch(() => {});
            video.play().catch(e => post({type:"playerError",message:e.message}));
          } else video.pause();
        }
        if (command === "play") {
          if (context && context.state !== "running") context.resume().catch(() => {});
          video.play().catch(e => post({type:"playerError",message:e.message}));
        }
        if (command === "pause") video.pause();
        if (command === "seek" && Number.isFinite(Number(value)) && Number.isFinite(video.duration)) video.currentTime = Math.max(0, Math.min(video.duration, Number(value)));
      };
      const youtubeSettings = () => document.querySelector(".ytp-settings-button");
      const menuItems = () => Array.from(document.querySelectorAll(".ytp-panel-menu .ytp-menuitem, .ytp-panel-menu [role=menuitemradio]"));
      const textOf = node => (node.innerText || node.textContent || "").trim().replace(/\s+/g, " ");
      const openQualityMenu = callback => {
        const trigger = youtubeSettings();
        if (!trigger) { callback([]); return; }
        trigger.click();
        setTimeout(() => {
          const quality = menuItems().find(node => /^quality(?:\s|$)/i.test(textOf(node)));
          if (!quality) { trigger.click(); callback([]); return; }
          quality.click();
          setTimeout(() => callback(menuItems().map(node => ({
            label:textOf(node),
            selected:node.getAttribute("aria-checked") === "true" || node.getAttribute("aria-pressed") === "true" ||
              node.classList.contains("ytp-menuitem-selected")
          })).filter(item => /\d{3,4}p|auto/i.test(item.label))), 180);
        }, 180);
      };
      window.__traptubeScanMenus = () => openQualityMenu(items => {
        post({type:"videoQualities",items});
        const trigger = youtubeSettings();
        if (trigger) trigger.click();
        post({type:"audioTracks",items:[]});
      });
      window.__traptubeSelectOption = ([kind,label]) => {
        if (kind !== "video") return;
        openQualityMenu(items => {
          const wanted = String(label).trim();
          const option = menuItems().find(node => textOf(node) === wanted);
          if (option) option.click();
          else { const trigger = youtubeSettings(); if (trigger) trigger.click(); }
          setTimeout(window.__traptubeScanMenus, 180);
        });
      };
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
    @ObservedObject private var manager = TrapTubeDownloadManager.shared

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
                                    ForEach(manager.availableVideoHeights, id: \.self) { height in
                                        Text("\(height)p").tag("\(height)p")
                                    }
                                } else {
                                    ForEach(manager.availableAudioBitrates, id: \.self) { bitrate in
                                        Text("\(max(1, bitrate / 1000)) kbps").tag("\(bitrate)bps")
                                    }
                                }
                            }
                            .pickerStyle(.menu)
                            .tint(Color(hex: "F04452"))

                            if mode == "audio" {
                                Text(quality == "best" ? "The highest exposed audio rendition is selected automatically." : "TrapTube will select the closest exposed audio rendition at or below this bitrate.")
                                    .font(.caption).foregroundStyle(Color(hex: "A6A4A6"))
                            }
                        }

                        Picker("File format", selection: $format) {
                            if mode == "video" {
                                Text("MP4 · iOS compatible").tag("mp4")
                            } else {
                                Text("M4A · AAC").tag("m4a")
                                Text("WAV · PCM").tag("wav")
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
                                    bitrate: mode == "audio" && quality != "best"
                                        ? Int(quality.replacingOccurrences(of: "bps", with: "")) : nil,
                                    height: mode == "video" && quality != "best"
                                        ? Int(quality.replacingOccurrences(of: "p", with: "")) : nil
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
                                        } else if job.status == "paused" || job.status == "failed" {
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
            Task {
                await manager.inspect(videoURL: videoURL, title: title)
                if preferredVideoQuality != "auto" &&
                    !manager.availableVideoHeights.contains(Int(preferredVideoQuality) ?? -1) {
                    quality = "best"
                }
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

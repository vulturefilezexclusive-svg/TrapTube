import SwiftUI
import WebKit

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
                TypeTypeWatchSheet(url: url)
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

private struct TypeTypeWatchSheet: View {
    let url: URL
    @Environment(\.dismiss) private var dismiss
    var body: some View {
        NavigationStack {
            TypeTypeWebView(url: url)
                .background(Color.black)
                .toolbar {
                    ToolbarItem(placement: .topBarLeading) {
                        Button("Close") { dismiss() }.foregroundStyle(.white)
                    }
                }
                .toolbarBackground(.black, for: .navigationBar)
        }
    }
}

private struct TypeTypeWebView: UIViewRepresentable {
    let url: URL
    func makeUIView(context: Context) -> WKWebView {
        let view = WKWebView(frame: .zero)
        view.isOpaque = false
        view.backgroundColor = .black
        view.scrollView.backgroundColor = .black
        view.allowsBackForwardNavigationGestures = true
        view.load(URLRequest(url: url, cachePolicy: .useProtocolCachePolicy, timeoutInterval: 30))
        return view
    }
    func updateUIView(_ uiView: WKWebView, context: Context) {
        if uiView.url != url { uiView.load(URLRequest(url: url)) }
    }
}
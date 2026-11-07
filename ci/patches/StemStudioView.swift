import SwiftUI

struct StemStudioView: View {
    @EnvironmentObject private var library: LibraryStore
    @EnvironmentObject private var theme: ThemeManager
    @EnvironmentObject private var audio: AudioEngineManager
    @StateObject private var stemService = StemSeparationService()
    @State private var selectedTrackID: UUID?

    private var selectedTrack: Track? {
        library.tracks.first(where: { $0.id == selectedTrackID })
    }

    var body: some View {
        ScrollView(showsIndicators: false) {
            VStack(alignment: .leading, spacing: 18) {
                BrandHeader().padding(.horizontal, 20)

                VStack(alignment: .leading, spacing: 7) {
                    Text("Stem Studio").font(.largeTitle.bold()).foregroundStyle(.white)
                    Text("Separate an imported song into four individual audio tracks using HTDemucs on your iPhone.")
                        .font(.subheadline).foregroundStyle(Color(hex: "A6A4A6"))
                }.padding(.horizontal, 18)

                VStack(alignment: .leading, spacing: 13) {
                    Label("Local source", systemImage: "waveform").font(.headline.bold()).foregroundStyle(.white)
                    if library.tracks.isEmpty {
                        Text("Import an audio file in Home or Library to choose it here.")
                            .font(.subheadline).foregroundStyle(Color(hex: "A6A4A6"))
                    } else {
                        Menu {
                            ForEach(library.tracks) { track in
                                Button(track.title) { selectedTrackID = track.id }
                            }
                        } label: {
                            HStack {
                                VStack(alignment: .leading, spacing: 3) {
                                    Text(selectedTrack?.title ?? "Choose a library track")
                                        .font(.subheadline.bold()).foregroundStyle(.white).lineLimit(1)
                                    Text(selectedTrack == nil ? "No track selected" : "Stored on this device")
                                        .font(.caption).foregroundStyle(Color(hex: "A6A4A6"))
                                }
                                Spacer()
                                Image(systemName: "chevron.up.chevron.down").foregroundStyle(theme.accent)
                            }
                            .padding(13).background(.black.opacity(0.28), in: RoundedRectangle(cornerRadius: 13))
                        }
                        .accessibilityLabel("Choose a local audio track")
                    }
                }
                .padding(16).background(.white.opacity(0.055), in: RoundedRectangle(cornerRadius: 20))
                .padding(.horizontal, 16)

                VStack(alignment: .leading, spacing: 12) {
                    Label(stemService.availability.title, systemImage: "cpu")
                        .font(.headline.bold())
                        .foregroundStyle(stemService.availability == .bundled ? Color.green : Color(hex: "FFB85C"))
                    Text(stemService.availability.detail)
                        .font(.subheadline).foregroundStyle(Color(hex: "A6A4A6"))

                    Button {
                        guard let selectedTrack else { return }
                        stemService.separate(track: selectedTrack)
                    } label: {
                        HStack(spacing: 9) {
                            if stemService.isProcessing { ProgressView().tint(.white) }
                            else { Image(systemName: "waveform.badge.mic") }
                            Text(stemService.isProcessing ? stemService.statusMessage : "Separate into 4 stems")
                        }
                        .font(.headline.bold()).foregroundStyle(.white)
                        .frame(maxWidth: .infinity).padding(.vertical, 13)
                        .background(theme.accent, in: Capsule())
                    }
                    .disabled(selectedTrack == nil || stemService.isProcessing || stemService.availability != .bundled)
                    .opacity(selectedTrack == nil || stemService.isProcessing || stemService.availability != .bundled ? 0.5 : 1)

                    if stemService.isProcessing {
                        ProgressView(value: stemService.progress)
                            .tint(theme.accent)
                        Button("Cancel separation") { stemService.cancel() }
                            .font(.caption.bold()).foregroundStyle(Color(hex: "FF7A84"))
                        Text(stemService.statusMessage)
                            .font(.caption).foregroundStyle(Color(hex: "A6A4A6"))
                    }

                    if let error = stemService.errorMessage {
                        Label(error, systemImage: "exclamationmark.triangle.fill")
                            .font(.caption).foregroundStyle(Color(hex: "FF7A84"))
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
                .padding(16).background(.white.opacity(0.055), in: RoundedRectangle(cornerRadius: 20))
                .overlay(RoundedRectangle(cornerRadius: 20).stroke(theme.accent.opacity(0.22), lineWidth: 1))
                .padding(.horizontal, 16)

                VStack(alignment: .leading, spacing: 11) {
                    Text("Separated stems").font(.headline.bold()).foregroundStyle(.white)
                    ForEach(Stem.allCases) { stem in
                        HStack(spacing: 11) {
                            Image(systemName: stem.icon).foregroundStyle(theme.accent).frame(width: 24)
                            Text(stem.rawValue).font(.subheadline.bold()).foregroundStyle(.white)
                            Spacer()
                            if let url = stemService.outputs[stem] {
                                ShareLink(item: url) {
                                    Image(systemName: "square.and.arrow.up")
                                        .foregroundStyle(Color(hex: "B8B4B8"))
                                }
                                Button {
                                    if audio.externalFileURL == url, audio.isPlaying { audio.stop() }
                                    else { audio.playFile(at: url, title: "\(selectedTrack?.title ?? "Stem") – \(stem.rawValue)") }
                                } label: {
                                    Image(systemName: audio.externalFileURL == url && audio.isPlaying ? "stop.circle.fill" : "play.circle.fill")
                                        .font(.title2).foregroundStyle(theme.accent)
                                }
                                .buttonStyle(.plain)
                            } else {
                                Text("Not generated").font(.caption).foregroundStyle(Color(hex: "858185"))
                            }
                        }
                        .padding(.vertical, 6)
                    }
                    Text("The four WAV files are saved locally. Stem previews play through the shared equalizer; you can also share each file.")
                        .font(.caption).foregroundStyle(Color(hex: "A6A4A6")).padding(.top, 3)
                }
                .padding(16).background(.white.opacity(0.04), in: RoundedRectangle(cornerRadius: 20))
                .padding(.horizontal, 16)

                Text("Processing runs on-device using the CPU and GPU (the Neural Engine is not used). It needs substantial free memory, and longer tracks take longer to process. Songs over 3 minutes are blocked.")
                    .font(.caption).foregroundStyle(Color(hex: "858185")).padding(.horizontal, 20)
            }
            .padding(.top, 8).padding(.bottom, 22)
        }
        .onAppear {
            stemService.refresh()
            if selectedTrackID == nil { selectedTrackID = library.tracks.first?.id }
        }
        .onChange(of: library.tracks) { _, tracks in
            if !tracks.contains(where: { $0.id == selectedTrackID }) {
                selectedTrackID = tracks.first?.id
            }
        }
        .onChange(of: selectedTrackID) { _, _ in
            if audio.externalFileURL != nil { audio.stop() }
        }
    }
}

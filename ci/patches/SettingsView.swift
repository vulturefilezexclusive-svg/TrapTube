import SwiftUI

struct SettingsView: View {
    @EnvironmentObject private var player: AudioEngineManager
    @EnvironmentObject private var theme: ThemeManager
    @State private var connectionStatus: String?
    @State private var checkingConnection = false
    @State private var showEqualizer = false
    @StateObject private var stemService = StemSeparationService()

    private let columns = [GridItem(.adaptive(minimum: 76), spacing: 12)]

    var body: some View {
        ScrollView(showsIndicators: false) {
            VStack(alignment: .leading, spacing: 18) {
                BrandHeader().padding(.horizontal, 20)
                Text("Settings").font(.largeTitle.bold()).foregroundStyle(.white).padding(.horizontal, 18)

                settingsCard(title: "Audio", icon: "slider.horizontal.3") {
                    HStack {
                        VStack(alignment: .leading, spacing: 4) {
                            Text("16-band equalizer").font(.headline).foregroundStyle(.white)
                            Text(player.currentPreset).font(.caption).foregroundStyle(Color(hex: "A6A4A6"))
                        }
                        Spacer()
                        Button("Adjust") { showEqualizer = true }.font(.subheadline.bold()).foregroundStyle(theme.accent)
                    }
                    Divider().overlay(.white.opacity(0.1))
                    gainSlider(title: "Bass boost", value: Double(player.bassBoost), range: 0...20, suffix: "dB") { player.setBassBoost(Float($0)) }
                    gainSlider(title: "Master gain", value: Double(player.masterGain * 100), range: 0...200, suffix: "%") { player.setMasterGain(Float($0 / 100)) }
                    if player.clippingWarning {
                        Label("High gain may cause clipping. Reduce gain or EQ boosts if the sound distorts.", systemImage: "exclamationmark.triangle.fill")
                            .font(.caption.weight(.semibold)).foregroundStyle(Color(hex: "FF7A84"))
                            .padding(10).frame(maxWidth: .infinity, alignment: .leading)
                            .background(Color(hex: "5A1019").opacity(0.75), in: RoundedRectangle(cornerRadius: 12))
                    }
                    Text("Local playback always uses the AVAudioEngine EQ path. If the engine cannot decode a track, TrapTube reports an error instead of playing it without equalization.")
                        .font(.caption).foregroundStyle(Color(hex: "A6A4A6"))
                }

                settingsCard(title: "Video discovery", icon: "play.rectangle.fill") {
                    HStack(spacing: 10) {
                        Image(systemName: "server.rack").foregroundStyle(theme.accent)
                        VStack(alignment: .leading, spacing: 3) {
                            Text("watch.typetype.video").font(.subheadline.bold()).foregroundStyle(.white)
                            Text("Native feed and search use the TypeType server.").font(.caption).foregroundStyle(Color(hex: "A6A4A6"))
                        }
                    }
                    Button {
                        checkingConnection = true; connectionStatus = nil
                        Task {
                            defer { checkingConnection = false }
                            do { connectionStatus = try await TypeTypeService().checkHealth() }
                            catch { connectionStatus = error.localizedDescription }
                        }
                    } label: {
                        Label(checkingConnection ? "Checking…" : "Check TypeType connection", systemImage: "network")
                            .font(.subheadline.bold()).foregroundStyle(.white)
                            .frame(maxWidth: .infinity).padding(.vertical, 12)
                            .background(theme.accent, in: Capsule())
                    }
                    .disabled(checkingConnection)
                    if let connectionStatus {
                        Text(connectionStatus).font(.caption).foregroundStyle(connectionStatus.hasPrefix("Connected") ? Color.green : Color(hex: "FF7A84"))
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }

                settingsCard(title: "Streaming quality", icon: "slider.horizontal.3") {
                    Text("Quality choices are loaded from the active TypeType stream. Open a video and use the in-player Quality menu for available video renditions and the Audio menu for available audio tracks. TrapTube does not display fixed quality levels that the stream does not support.")
                        .font(.caption).foregroundStyle(Color(hex: "A6A4A6"))
                }

                settingsCard(title: "Theme colors", icon: "paintpalette.fill") {
                    Text("Choose an accent color. Your selection updates the app immediately.")
                        .font(.caption).foregroundStyle(Color(hex: "A6A4A6"))
                    LazyVGrid(columns: columns, spacing: 14) {
                        ForEach(ThemeManager.accents) { option in
                            Button { theme.selectAccent(option) } label: {
                                VStack(spacing: 7) {
                                    ZStack {
                                        Circle().fill(option.color).frame(width: 42, height: 42)
                                        if theme.accentHex == option.hex {
                                            Image(systemName: "checkmark").font(.headline.bold()).foregroundStyle(option.hex == "F4F4F5" || option.hex == "A6A4A6" ? .black : .white)
                                        }
                                    }
                                    Text(option.name).font(.caption2.weight(.semibold)).foregroundStyle(.white).lineLimit(1)
                                }
                                .frame(maxWidth: .infinity).padding(.vertical, 7)
                                .background(theme.accentHex == option.hex ? .white.opacity(0.10) : .clear, in: RoundedRectangle(cornerRadius: 13))
                                .overlay(RoundedRectangle(cornerRadius: 13).stroke(theme.accentHex == option.hex ? theme.accent : .white.opacity(0.07), lineWidth: 1))
                                .contentShape(Rectangle())
                            }
                            .buttonStyle(.plain)
                            .accessibilityLabel("\(option.name) accent color\(theme.accentHex == option.hex ? ", selected" : "")")
                        }
                    }
                    HStack(spacing: 9) {
                        RoundedRectangle(cornerRadius: 8).fill(theme.accent).frame(width: 28, height: 28)
                        Text("Live preview · \(theme.selectedAccent.name)").font(.subheadline.bold()).foregroundStyle(.white)
                        Spacer()
                        Button("Reset") { theme.reset() }.font(.subheadline.bold()).foregroundStyle(theme.accent)
                    }.padding(.top, 5)
                }

                settingsCard(title: "Local library", icon: "externaldrive.fill") {
                    infoRow("Imported audio", value: "Stored on this device")
                    Divider().overlay(.white.opacity(0.1))
                    infoRow("Supported formats", value: "MP3 · M4A · AAC · WAV · AIFF")
                    Divider().overlay(.white.opacity(0.1))
                    infoRow("Stem separation", value: stemService.availability.title)
                }

                Text("TrapTube · Local music stays on this device. Remote video discovery and playback are provided by TypeType.")
                    .font(.caption).foregroundStyle(Color(hex: "858185")).multilineTextAlignment(.center)
                    .frame(maxWidth: .infinity).padding(.vertical, 6)
            }
            .padding(.top, 7).padding(.bottom, 20)
        }
        .sheet(isPresented: $showEqualizer) { EqualizerView().environmentObject(player).environmentObject(theme).presentationDetents([.large]) }
        .onAppear { stemService.refresh() }
    }

    private func settingsCard<Content: View>(title: String, icon: String, @ViewBuilder content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            Label(title, systemImage: icon).font(.headline.bold()).foregroundStyle(.white)
            content()
        }
        .padding(16).background(.white.opacity(0.055), in: RoundedRectangle(cornerRadius: 20))
        .overlay(RoundedRectangle(cornerRadius: 20).stroke(.white.opacity(0.06), lineWidth: 1))
        .padding(.horizontal, 16)
    }

    private func gainSlider(title: String, value: Double, range: ClosedRange<Double>, suffix: String, onChange: @escaping (Double) -> Void) -> some View {
        VStack(spacing: 6) {
            HStack { Text(title).font(.subheadline.bold()).foregroundStyle(.white); Spacer(); Text("\(Int(value))\(suffix)").font(.subheadline.monospacedDigit()).foregroundStyle(Color(hex: "D2D0D2")) }
            Slider(value: Binding(get: { value }, set: onChange), in: range).tint(theme.accent)
        }
    }

    private func infoRow(_ title: String, value: String) -> some View {
        HStack(alignment: .top) {
            Text(title).font(.subheadline.bold()).foregroundStyle(.white)
            Spacer(minLength: 10)
            Text(value).font(.caption).foregroundStyle(Color(hex: "A6A4A6")).multilineTextAlignment(.trailing).frame(maxWidth: 180, alignment: .trailing)
        }
    }
}
import SwiftUI

struct SettingsView: View {
    @EnvironmentObject private var player: AudioEngineManager
    @EnvironmentObject private var theme: ThemeManager
    @State private var connectionStatus: String?
    @State private var checkingConnection = false
    @State private var showEqualizer = false
    @State private var showCustomization = false
    @StateObject private var stemService = StemSeparationService()
    @AppStorage("settings.quickSetupComplete") private var quickSetupComplete = true
    @AppStorage("settings.backgroundPlayback") private var backgroundPlayback = true
    @AppStorage("settings.autoplay") private var autoplay = false
    @AppStorage("settings.showCaptions") private var showCaptions = true
    @AppStorage("settings.keepScreenAwake") private var keepScreenAwake = false
    @AppStorage("settings.smartCleanup") private var smartCleanup = true
    @AppStorage("settings.shortsAutoplay") private var shortsAutoplay = true
    @AppStorage("settings.reduceMotion") private var reduceMotion = false
    @AppStorage("settings.shareDiagnostics") private var shareDiagnostics = false
    @AppStorage("video.preferredQuality") private var preferredVideoQuality = "auto"
    @AppStorage("discovery.sourceURL") private var discoverySourceURL = ""

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
                    Text("Choose the website TrapTube opens for its home streaming view. Leave this field empty to use the default home page.")
                        .font(.caption).foregroundStyle(Color(hex: "A6A4A6"))
                    HStack(spacing: 9) {
                        Image(systemName: "globe").foregroundStyle(theme.accent)
                        TextField("", text: $discoverySourceURL, prompt: Text("https://example.com").foregroundColor(Color(hex: "777277")))
                            .textInputAutocapitalization(.never)
                            .autocorrectionDisabled()
                            .keyboardType(.URL)
                            .textContentType(.URL)
                            .foregroundStyle(.white)
                            .tint(theme.accent)
                            .accessibilityLabel("Streaming website address")
                        if !discoverySourceURL.isEmpty {
                            Button { discoverySourceURL = "" } label: {
                                Image(systemName: "xmark.circle.fill").foregroundStyle(Color(hex: "A6A4A6"))
                            }.accessibilityLabel("Clear streaming website address")
                        }
                    }
                    .padding(13)
                    .background(.white.opacity(0.06), in: RoundedRectangle(cornerRadius: 12))
                    Text("Enter a website URL. TrapTube will open that site in the home streaming view; playback and downloads depend on what the site makes available.")
                        .font(.caption2).foregroundStyle(Color(hex: "858185"))
                }

                settingsCard(title: "Streaming quality", icon: "slider.horizontal.3") {
                    Text("Choose the preferred video resolution. TrapTube selects it when the active stream offers that rendition; if it is unavailable, the player uses the highest available rendition below your preference.")
                        .font(.caption).foregroundStyle(Color(hex: "A6A4A6"))
                    Picker("Preferred video quality", selection: $preferredVideoQuality) {
                        Text("Auto · Provider default").tag("auto")
                        Text("2160p · 4K").tag("2160")
                        Text("1440p · 2K").tag("1440")
                        Text("1080p · Full HD").tag("1080")
                        Text("720p · HD").tag("720")
                        Text("480p · SD").tag("480")
                        Text("360p").tag("360")
                    }
                    .pickerStyle(.menu)
                    .tint(theme.accent)
                    HStack {
                        Text("Preferred resolution")
                        Spacer()
                        Text(preferredVideoQuality == "auto" ? "Auto" : "\(preferredVideoQuality)p")
                            .fontWeight(.semibold).foregroundStyle(theme.accent)
                    }
                    .font(.subheadline)
                }

                settingsCard(title: "Quick setup", icon: "checkmark.circle") {
                    Text("The important defaults most people set once.").font(.caption).foregroundStyle(Color(hex: "A6A4A6"))
                    settingsToggle("Quick setup complete", detail: "Remember this device initial preferences", value: $quickSetupComplete)
                }

                settingsCard(title: "Downloads", icon: "arrow.down.circle") {
                    infoRow("Storage location", value: "On this device")
                    Divider().overlay(.white.opacity(0.1))
                    infoRow("Media sources", value: "Files you own or are licensed to use")
                    Divider().overlay(.white.opacity(0.1))
                    settingsToggle("Smart library cleanup", detail: "Offer cleanup suggestions for unused imported files", value: $smartCleanup)
                }

                Button {
                    showCustomization = true
                } label: {
                    VStack(alignment: .leading, spacing: 12) {
                        Label("Customize TrapTube", systemImage: "slider.horizontal.3")
                            .font(.headline.bold()).foregroundStyle(.white)
                        Text("Personalize playback, appearance, and interface behavior.")
                            .font(.caption).foregroundStyle(Color(hex: "A6A4A6"))
                        HStack(spacing: 7) {
                            Text("Open customization")
                            Image(systemName: "arrow.up.right")
                        }
                        .font(.caption.weight(.semibold)).foregroundStyle(theme.accent)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(16)
                    .background(.white.opacity(0.055), in: RoundedRectangle(cornerRadius: 20))
                    .overlay(RoundedRectangle(cornerRadius: 20).stroke(.white.opacity(0.10), lineWidth: 1))
                    .contentShape(RoundedRectangle(cornerRadius: 20))
                }
                .buttonStyle(.plain)
                .padding(.horizontal, 16)
                .accessibilityHint("Opens playback, appearance, and interface customization settings")

                settingsCard(title: "App & privacy", icon: "lock.shield") {
                    settingsToggle("Share anonymous diagnostics", detail: "Off by default", value: $shareDiagnostics)
                    Divider().overlay(.white.opacity(0.1))
                    infoRow("Local audio", value: "Processed on this device")
                    Divider().overlay(.white.opacity(0.1))
                    infoRow("Remote video", value: "Handled by your connected provider")
                }

                settingsCard(title: "Local library", icon: "externaldrive.fill") {
                    infoRow("Imported audio", value: "Stored on this device")
                    Divider().overlay(.white.opacity(0.1))
                    infoRow("Supported formats", value: "MP3 · M4A · AAC · WAV · AIFF")
                    Divider().overlay(.white.opacity(0.1))
                    infoRow("Stem separation", value: stemService.availability.title)
                }

                Text("TrapTube · Local music stays on this device. Streaming content is loaded from your selected website.")
                    .font(.caption).foregroundStyle(Color(hex: "858185")).multilineTextAlignment(.center)
                    .frame(maxWidth: .infinity).padding(.vertical, 6)
            }
            .padding(.top, 7).padding(.bottom, 20)
        }
        .sheet(isPresented: $showEqualizer) { EqualizerView().environmentObject(player).environmentObject(theme).presentationDetents([.large]) }

        .sheet(isPresented: $showCustomization) {
            NavigationStack {
                ScrollView(showsIndicators: false) {
                    VStack(alignment: .leading, spacing: 18) {
                        Text("Choose how TrapTube looks and behaves. Changes are saved automatically.")
                            .font(.subheadline).foregroundStyle(Color(hex: "A6A4A6"))
                            .padding(.horizontal, 18)

                        settingsCard(title: "Playback", icon: "play.rectangle") {
                            settingsToggle("Background playback", detail: "Keep supported local audio playing when you leave the player", value: $backgroundPlayback)
                            Divider().overlay(.white.opacity(0.1))
                            settingsToggle("Autoplay next item", detail: "Continue through a local queue", value: $autoplay)
                            Divider().overlay(.white.opacity(0.1))
                            settingsToggle("Show captions when available", detail: "Use captions exposed by the video provider", value: $showCaptions)
                            Divider().overlay(.white.opacity(0.1))
                            settingsToggle("Keep screen awake in player", detail: "Prevent auto-lock while the player is open", value: $keepScreenAwake)
                            Divider().overlay(.white.opacity(0.1))
                            settingsToggle("Autoplay short videos", detail: "Remember this preference for supported short-video feeds", value: $shortsAutoplay)
                        }

                        settingsCard(title: "Interface", icon: "rectangle.stack") {
                            settingsToggle("Reduce motion", detail: "Use simpler transitions throughout TrapTube", value: $reduceMotion)
                        }

                                        settingsCard(title: "Theme colors", icon: "paintpalette.fill") {
                            Text("Pick any accent color with the hue wheel and saturation/value square, or choose a preset below.")
                                .font(.caption).foregroundStyle(Color(hex: "A6A4A6"))
                            TrapTubeHuePicker(initialColor: theme.accent) { color in
                                theme.selectCustomAccent(color)
                            }
                            HStack(spacing: 9) {
                                RoundedRectangle(cornerRadius: 8).fill(theme.accent).frame(width: 28, height: 28)
                                Text("Live preview · \(theme.selectedAccent.name)").font(.subheadline.bold()).foregroundStyle(.white)
                                Spacer()
                                Button("Reset") { theme.reset() }.font(.subheadline.bold()).foregroundStyle(theme.accent)
                            }.padding(.top, 5)
                            Text("Presets").font(.caption.bold()).foregroundStyle(Color(hex: "A6A4A6"))
                            LazyVGrid(columns: columns, spacing: 12) {
                                ForEach(ThemeManager.accents) { option in
                                    Button { theme.selectAccent(option) } label: {
                                        VStack(spacing: 6) {
                                            Circle().fill(option.color).frame(width: 34, height: 34)
                                                .overlay {
                                                    if theme.accentHex == option.hex {
                                                        Image(systemName: "checkmark").font(.caption.bold())
                                                            .foregroundStyle(option.hex == "F4F4F5" || option.hex == "A6A4A6" ? .black : .white)
                                                    }
                                                }
                                            Text(option.name).font(.caption2.weight(.semibold)).foregroundStyle(.white).lineLimit(1)
                                        }
                                        .frame(maxWidth: .infinity).padding(.vertical, 6)
                                    }.buttonStyle(.plain)
                                }
                            }
                        }
                    }
                    .padding(.top, 16).padding(.bottom, 24)
                }
                .background(Color(hex: "080809").ignoresSafeArea())
                .navigationTitle("Customize TrapTube")
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .topBarTrailing) {
                        Button("Done") { showCustomization = false }
                            .fontWeight(.semibold).tint(theme.accent)
                    }
                }
            }
            .preferredColorScheme(.dark)
            .presentationDetents([.large])
            .presentationDragIndicator(.visible)
        }
        .onAppear { stemService.refresh() }
    }

    private func settingsToggle(_ title: String, detail: String, value: Binding<Bool>) -> some View {
        Toggle(isOn: value) {
            VStack(alignment: .leading, spacing: 3) {
                Text(title).font(.subheadline.weight(.semibold)).foregroundStyle(.white)
                Text(detail).font(.caption).foregroundStyle(Color(hex: "A6A4A6"))
            }
        }.tint(theme.accent)
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

private struct TrapTubeHuePicker: View {
    let initialColor: Color
    let onChange: (Color) -> Void
    @State private var hue: Double = 0
    @State private var saturation: Double = 1
    @State private var brightness: Double = 1

    private var selected: Color { Color(hue: hue, saturation: saturation, brightness: brightness) }

    var body: some View {
        VStack(spacing: 14) {
            GeometryReader { proxy in
                let side = min(proxy.size.width, 250)
                ZStack {
                    Circle().stroke(AngularGradient(gradient: Gradient(colors: [
                        .red, .orange, .yellow, .green, .cyan, .blue, .purple, .pink, .red
                    ]), center: .center), style: StrokeStyle(lineWidth: 22, lineCap: .round))
                    Circle().stroke(.white.opacity(0.12), lineWidth: 1).padding(11)
                    Circle().fill(selected).frame(width: 28, height: 28)
                        .overlay(Circle().stroke(.white, lineWidth: 3))
                        .offset(x: 0, y: -(side / 2 - 11))
                        .rotationEffect(.degrees(hue * 360))
                }
                .frame(width: side, height: side)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .contentShape(Circle())
                .gesture(DragGesture(minimumDistance: 0).onChanged { value in
                    let center = CGPoint(x: side / 2, y: side / 2)
                    let dx = value.location.x - center.x
                    let dy = value.location.y - center.y
                    var angle = atan2(dy, dx) / (2 * .pi) + 0.25
                    if angle < 0 { angle += 1 }
                    hue = angle.truncatingRemainder(dividingBy: 1)
                    publish()
                })
            }
            .frame(height: 250)

            GeometryReader { proxy in
                ZStack {
                    RoundedRectangle(cornerRadius: 12).fill(Color(hue: hue, saturation: 1, brightness: 1))
                    RoundedRectangle(cornerRadius: 12).fill(LinearGradient(colors: [.white, .clear], startPoint: .leading, endPoint: .trailing))
                    RoundedRectangle(cornerRadius: 12).fill(LinearGradient(colors: [.clear, .black], startPoint: .top, endPoint: .bottom))
                    Circle().stroke(.white, lineWidth: 2).background(Circle().fill(.clear))
                        .frame(width: 18, height: 18)
                        .position(x: saturation * proxy.size.width,
                                  y: (1 - brightness) * proxy.size.height)
                        .shadow(color: .black.opacity(0.5), radius: 2)
                }
                .clipShape(RoundedRectangle(cornerRadius: 12))
                .contentShape(Rectangle())
                .gesture(DragGesture(minimumDistance: 0).onChanged { value in
                    saturation = min(1, max(0, value.location.x / max(1, proxy.size.width)))
                    brightness = 1 - min(1, max(0, value.location.y / max(1, proxy.size.height)))
                    publish()
                })
            }
            .frame(height: 150)
            HStack {
                Text("Saturation").font(.caption).foregroundStyle(.secondary)
                Spacer()
                Text("\(Int(saturation * 100))%").font(.caption.monospacedDigit()).foregroundStyle(.white)
                Text("Value").font(.caption).foregroundStyle(.secondary).padding(.leading, 12)
                Text("\(Int(brightness * 100))%").font(.caption.monospacedDigit()).foregroundStyle(.white)
            }
        }
        .onAppear {
            let ui = UIColor(initialColor)
            var h: CGFloat = 0, s: CGFloat = 0, v: CGFloat = 0, a: CGFloat = 0
            ui.getHue(&h, saturation: &s, brightness: &v, alpha: &a)
            hue = Double(h); saturation = Double(s); brightness = Double(v)
        }
    }

    private func publish() { onChange(selected) }
}

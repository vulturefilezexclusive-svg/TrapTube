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
                            AudioReactiveVisualizer(levels: player.visualizerLevels, style: $visualizerStyle, tint: theme.accent)
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
                    var path = Path()
                    let mid = size.height / 2
                    path.move(to: CGPoint(x: 0, y: mid))
                    for (index, value) in values.enumerated() {
                        let x = CGFloat(index) / CGFloat(max(1, values.count - 1)) * size.width
                        path.addLine(to: CGPoint(x: x, y: mid - CGFloat(value) * size.height * 0.46))
                    }
                    for (index, value) in values.enumerated().reversed() {
                        let x = CGFloat(index) / CGFloat(max(1, values.count - 1)) * size.width
                        path.addLine(to: CGPoint(x: x, y: mid + CGFloat(value) * size.height * 0.46))
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

print("Applied splash, glass surfaces, and audio-reactive visualizer patches.")

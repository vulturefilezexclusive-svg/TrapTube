import SwiftUI
import UIKit

@MainActor
final class ThemeManager: ObservableObject {
    struct AccentOption: Identifiable, Equatable {
        let name: String
        let hex: String
        var id: String { hex }
        var color: Color { Color(hex: hex) }
    }

    static let accents: [AccentOption] = [
        .init(name: "Trap Red", hex: "E50920"),
        .init(name: "Crimson", hex: "B5122A"),
        .init(name: "Orange", hex: "F07828"),
        .init(name: "Amber", hex: "E5A000"),
        .init(name: "Lime", hex: "9ACD32"),
        .init(name: "Green", hex: "20A66A"),
        .init(name: "Teal", hex: "159A9C"),
        .init(name: "Cyan", hex: "21B8D5"),
        .init(name: "Blue", hex: "3478F6"),
        .init(name: "Indigo", hex: "5652C8"),
        .init(name: "Violet", hex: "8B5CF6"),
        .init(name: "Magenta", hex: "C026D3"),
        .init(name: "Pink", hex: "EC4899"),
        .init(name: "Silver", hex: "A6A4A6"),
        .init(name: "White", hex: "F4F4F5")
    ]

    @Published private(set) var accentHex: String {
        didSet { UserDefaults.standard.set(accentHex, forKey: "theme.accent") }
    }
    @Published private(set) var backgroundHex = "080809"
    @Published private(set) var primaryTextHex = "FFFFFF"
    @Published private(set) var secondaryTextHex = "A6A4A6"

    init() {
        let saved = (UserDefaults.standard.string(forKey: "theme.accent") ?? "E50920").uppercased()
        let isHex = saved.count == 6 && saved.allSatisfy { $0.isHexDigit }
        accentHex = isHex ? saved : "E50920"
    }

    var accent: Color { Color(hex: accentHex) }
    var background: Color { Color(hex: backgroundHex) }
    var primaryText: Color { Color(hex: primaryTextHex) }
    var secondaryText: Color { Color(hex: secondaryTextHex) }
    var selectedAccent: AccentOption {
        Self.accents.first(where: { $0.hex == accentHex }) ??
        AccentOption(name: "Custom", hex: accentHex)
    }

    func selectCustomAccent(_ color: Color) {
        let ui = UIColor(color)
        var red: CGFloat = 0, green: CGFloat = 0, blue: CGFloat = 0, alpha: CGFloat = 1
        ui.getRed(&red, green: &green, blue: &blue, alpha: &alpha)
        accentHex = String(format: "%02X%02X%02X",
            Int((red * 255).rounded()), Int((green * 255).rounded()), Int((blue * 255).rounded()))
    }

    func selectAccent(_ option: AccentOption) { accentHex = option.hex }
    func reset() { accentHex = "E50920" }
}
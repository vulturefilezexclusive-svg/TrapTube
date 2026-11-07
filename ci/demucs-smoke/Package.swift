// swift-tools-version: 6.2
import PackageDescription

let package = Package(
    name: "DemucsSmoke",
    platforms: [.macOS(.v14)],
    dependencies: [
        .package(url: "https://github.com/SplitFireAI/demucs-swift.git", from: "0.1.0")
    ],
    targets: [
        .executableTarget(
            name: "DemucsSmoke",
            dependencies: [.product(name: "Demucs", package: "demucs-swift")]
        )
    ]
)

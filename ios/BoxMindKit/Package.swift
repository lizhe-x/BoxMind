// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "BoxMindKit",
    defaultLocalization: "en",
    platforms: [.iOS(.v18), .macOS(.v15)],
    products: [
        .library(name: "BoxMindKit", targets: ["BoxMindKit"]),
    ],
    targets: [
        .target(
            name: "BoxMindKit",
            swiftSettings: [.enableUpcomingFeature("StrictConcurrency")]
        ),
        .testTarget(name: "BoxMindKitTests", dependencies: ["BoxMindKit"]),
    ]
)

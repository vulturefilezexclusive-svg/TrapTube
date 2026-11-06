# TrapTube iOS

Native SwiftUI iOS application source and an unsigned IPA build workflow.

## Source package
The CI workflow extracts `ci/source.bundle.zip.b64`, which contains the Xcode project and supporting Swift sources. The ZIP preserves the original project layout.

## Build
Use the GitHub Actions workflow **Build iOS unsigned IPA**. It builds with Xcode on a hosted macOS runner, packages `Payload/TrapTube.app` as an unsigned IPA, and uploads the IPA as a workflow artifact.

An unsigned IPA is suitable as input to a sideloading/signing tool such as AltStore; it is not App Store signed. For direct installation, sign it with a valid Apple development identity and provisioning profile.

## Known feature boundaries
- YouTube playback uses the official embedded player; YouTube audio is not routed into the local EQ or stem pipeline.
- Stem separation remains model-gated. A licensed, compatible Core ML Demucs model and inference adapter are required before actual separation can be enabled.

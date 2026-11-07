# HTDemucs FT attribution and third-party notices

TrapTube uses the Demucs Swift package by SplitFireAI, backed by the demucs-rs Metal inference engine.

- Swift package: https://github.com/SplitFireAI/demucs-swift
- Inference engine: https://github.com/SplitFireAI/demucs-rs
- Model: HTDemucs FT (fine-tuned four-stem ensemble)
- Upstream model project: https://github.com/facebookresearch/demucs
- Model cache size: approximately 333 MB
- Runtime: on-device Metal GPU inference; weights are downloaded on first use and cached in the app's Caches directory.
- Package license: Apache-2.0 (see the package's LICENSE and bundled third-party notices).
- Upstream Demucs model/code license: MIT, Meta Platforms, Inc. and affiliates.

HTDemucs FT uses one fine-tuned specialist per stem: drums, bass, other and vocals. The app requests the four-stem fine-tuned model and uses the package's own resampling, STFT/iSTFT, chunk overlap-add, and output reconstruction implementation. TrapTube does not redistribute model weights inside the IPA; the package downloads the model from its published source and verifies/caches it according to its implementation.

The model is an estimate of source components. Some bleed and artifacts are normal; output quality varies by recording and mix. Users are responsible for having the rights to audio they process.

This product is not affiliated with or endorsed by Meta Platforms, Inc. or SplitFireAI.

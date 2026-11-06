# HTDemucs attribution and license

TrapTube integrates the HTDemucs Core ML conversion distributed by the CoreML-Models project.

- Model: HTDemucs_SourceSeparation_F32.mlpackage
- Upstream project: Demucs, https://github.com/facebookresearch/demucs
- Model conversion/sample implementation: https://github.com/john-rocky/CoreML-Models
- License: MIT

HTDemucs is by Simon Rouard, Francisco Massa, and Alexandre Défossez (Meta AI). The upstream Demucs code and pretrained weights are distributed under the MIT License. The Core ML conversion is also listed as MIT by its distributor.

The model is downloaded during the GitHub Actions build from:
https://github.com/john-rocky/CoreML-Models/releases/download/demucs-v1/HTDemucs_SourceSeparation_F32.mlpackage.zip

## Bundled model interface and host-side reconstruction

The compiled model's verified Float16 tensor contract is:

- Input `audio_waveform`: [1, 2, 343980]
- Input `spectral_magnitude`: [1, 4, 2048, 336], with channel planes [left real, left imaginary, right real, right imaginary]
- Output `time_output`: [1, 8, 343980]
- Output `freq_output`: [1, 16, 2048, 336], with four source groups, each containing [left real, left imaginary, right real, right imaginary]

The host reconstruction follows the upstream integration guide: 44.1 kHz stereo, periodic Hann window, 4096-point normalized STFT, 1024-sample hop, reflect padding, inverse STFT of the frequency branch, addition of the time branch, and 25% overlapping segment crossfades.

Source order is **drums, bass, other, vocals**. TrapTube validates the compiled model's names, shapes, and Float16 types at build time and runtime. It also runs an STFT/iSTFT round-trip self-check before processing and rejects non-finite model output before writing WAV files.

Upstream interface reference: https://github.com/john-rocky/CoreML-Models/blob/master/conversion_scripts/HTDemucs_SourceSeparation_README.swift

## MIT License

Copyright (c) Meta Platforms, Inc. and affiliates.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

This project is not affiliated with Meta, Apple, or the CoreML-Models maintainers.

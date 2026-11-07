#!/usr/bin/env python3
"""Independent check of the HTDemucs host-side STFT/iSTFT index math.

Part A re-implements demucs' htdemucs._spec/_ispec (torch.stft/istft semantics: centre=True,
reflect padding, periodic Hann, normalized=True, Nyquist bin dropped/zero-filled, frames 2..2+le)
directly with numpy. Part B mirrors the Swift code in StemSeparationService.swift line by line.
The two must agree, and B must reconstruct the interior exactly. The first/last ~3.5k samples of a segment are
not exactly invertible in demucs itself (frames 0,1 and the last 2 are dropped); this is reported, and is why
the overlap-add triangular weights (which are ~0 at segment edges) matter.
Run:  python3 tests/reference/dsp_reference_check.py
"""
import numpy as np, sys
N, HOP, BINS, SEG = 4096, 1024, 2048, 343980
FR = -(-SEG // HOP); PAD = HOP // 2 * 3
win = 0.5 - 0.5*np.cos(2*np.pi*np.arange(N)/N)          # periodic Hann (torch.hann_window default)

def reflect(x, l, r):
    return np.pad(x, (l, r), mode="reflect")

# ---- Part A: demucs semantics --------------------------------------------------------------
def ref_spec(x):
    le = -(-len(x)//HOP)
    x = reflect(x, PAD, PAD + le*HOP - len(x))
    xc = reflect(x, N//2, N//2)                           # torch.stft(center=True, pad_mode="reflect")
    nfr = 1 + (len(xc)-N)//HOP
    z = np.stack([np.fft.rfft(xc[f*HOP:f*HOP+N]*win)/np.sqrt(N) for f in range(nfr)], axis=1)  # normalized
    z = z[:-1]                                            # drop Nyquist -> 2048 bins
    return z[:, 2:2+le]

def ref_ispec(z, length):
    le = HOP*(-(-length//HOP)) + 2*PAD
    z = np.pad(z, ((0,1),(2,2)))                          # Nyquist bin + 2 frames each side
    nfr = z.shape[1]
    out = np.zeros(HOP*(nfr-1)+N); env = np.zeros_like(out)
    for f in range(nfr):
        fr = np.fft.irfft(z[:, f]*np.sqrt(N), n=N)/1.0    # normalized=True: irfft * sqrt(N) / N ... see note
        out[f*HOP:f*HOP+N] += fr*win; env[f*HOP:f*HOP+N] += win**2
    out = out[N//2:N//2+le] / env[N//2:N//2+le]           # centre trim
    return out[PAD:PAD+length]

# ---- Part B: line-by-line mirror of the Swift implementation -------------------------------
def swift_spec(x):
    padded = reflect(reflect(x, PAD, PAD+FR*HOP-len(x)), N//2, N//2)
    re = np.zeros((BINS, FR)); im = np.zeros((BINS, FR))
    for f in range(FR):
        start = (f+2)*HOP
        spec = np.fft.fft(padded[start:start+N]*win)       # complexComplex forward
        re[:, f] = spec[:BINS].real/np.sqrt(N); im[:, f] = spec[:BINS].imag/np.sqrt(N)
    return re, im

env_len = N + HOP*(FR+3)
envelope = np.zeros(env_len)
for f in range(FR+4): envelope[f*HOP:f*HOP+N] += win*win
origin = N//2 + PAD
inv_env = 1/envelope[origin:origin+SEG]

def swift_ispec(re, im):
    out = np.zeros(SEG)
    for f in range(FR):
        inr = np.zeros(N); ini = np.zeros(N)
        inr[:BINS] = re[:, f]; ini[:BINS] = im[:, f]
        spec = (inr + 1j*ini)
        outr = (np.fft.ifft(spec)*N).real                  # vDSP inverse is unnormalised
        fs = (f+2)*HOP - origin
        lo, hi = max(0, -fs), min(N, SEG-fs)
        if lo < hi:
            k = np.arange(lo, hi)
            out[fs+k] += (2*outr[k] - inr[0])/np.sqrt(N)*win[k]
    return out*inv_env

rng = np.random.default_rng(0)
t = np.arange(SEG)/44100
x = 0.4*np.sin(2*np.pi*55*t)+0.3*np.sin(2*np.pi*1234.5*t)+0.2*np.sin(2*np.pi*9876*t)

zA = ref_spec(x); re, im = swift_spec(x)
fwd = max(np.abs(zA.real-re).max(), np.abs(zA.imag-im).max())
print(f"forward  : Swift-mirror vs demucs-semantics max abs diff = {fwd:.3e}")
rec = swift_ispec(re, im)
err_all = np.abs(rec-x)
bad = np.where(err_all > 1e-4)[0]
head = (bad[bad < SEG//2].max()+1) if (bad < SEG//2).any() else 0
tail = (SEG - bad[bad >= SEG//2].min()) if (bad >= SEG//2).any() else 0
print(f"roundtrip: interior max err = {err_all[8192:-8192].max():.3e}")
print(f"           samples with err>1e-4: first {head} and last {tail} of the segment (inherent to demucs' dropped edge frames)")
print(f"           peak edge err = {err_all.max():.3e}")
refrec = ref_ispec(zA, SEG)
print(f"inverse  : Swift-mirror vs demucs-semantics max abs diff = {np.abs(swift_ispec(re, im)-refrec).max():.3e}")
ok = fwd < 1e-4 and err_all[8192:-8192].max() < 1e-4 and head < 8192 and tail < 8192
print("PASS" if ok else "FAIL"); sys.exit(0 if ok else 1)

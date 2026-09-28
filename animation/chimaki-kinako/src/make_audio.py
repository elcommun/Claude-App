#!/usr/bin/env python3
"""Procedural score + sound design for the 60 s short
   「いつも、となりに。〜ちまきと、きなこ〜」

Outputs (48 kHz / stereo / 16-bit / exactly 60.0 s, peak ~ -3 dBFS):
  audio/bgm.wav  - music only (vocal band dipped ~4 dB under every line)
  audio/sfx.wav  - sound effects only
Everything is synthesized with numpy/scipy (no samples).  Re-run: python3 make_audio.py

Main "friendship" theme (G major, 3/4):
  m1 B4-- A4 G4 | m2 D5-- B4 | m3 C5. B4 A4 | m4 A4---     (G  Em  C  D)
  m5 B4-- A4 G4 | m6 G5-- E5 | m7 D5. C5 A4 B4 | m8 G4--- (G  C   D7 G)
"""
import json
import os
import wave

import numpy as np
from scipy import signal
from scipy.ndimage import minimum_filter1d, uniform_filter1d

SR = 48000
DUR = 60.0
N = int(round(SR * DUR))
PAD = 12 * SR
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCRIPT = json.load(open(os.path.join(ROOT, "script.json"), encoding="utf-8"))
rng = np.random.default_rng(20260928)

# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------
NOTE_IDX = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def midi_of(name):
    letter, rest, acc = name[0], name[1:], 0
    while rest and rest[0] in "b#":
        acc += -1 if rest[0] == "b" else 1
        rest = rest[1:]
    return 12 * (int(rest) + 1) + NOTE_IDX[letter] + acc


def nf(name):
    if isinstance(name, (int, float)):
        return float(name)
    return 440.0 * 2 ** ((midi_of(name) - 69) / 12)


def tarr(n):
    return np.arange(n) / SR


def fade_edges(x, a=0.002, r=0.01):
    n = len(x)
    na = min(n // 2, max(1, int(a * SR)))
    nr = min(n // 2, max(1, int(r * SR)))
    x[:na] *= 0.5 - 0.5 * np.cos(np.pi * np.arange(na) / na)
    x[n - nr:] *= 0.5 + 0.5 * np.cos(np.pi * np.arange(nr) / nr)
    return x


def env_points(pts, n, t0=0.0):
    t = t0 + tarr(n)
    return np.interp(t, [p[0] for p in pts], [p[1] for p in pts])


def pan_gains(p):
    p = np.clip(p, -1, 1)
    a = (p + 1) * np.pi / 4
    return np.cos(a), np.sin(a)


class Bus:
    """stereo dry bus + reverb send"""

    def __init__(self):
        self.L = np.zeros(N + PAD)
        self.R = np.zeros(N + PAD)
        self.sL = np.zeros(N + PAD)
        self.sR = np.zeros(N + PAD)

    def add(self, t, x, pan=0.0, gain=1.0, send=0.25):
        i = int(round(t * SR))
        if i < 0:
            x, i = x[-i:], 0
        n = min(len(x), N + PAD - i)
        if n <= 0:
            return
        x = x[:n] * gain
        if np.ndim(pan) == 0:
            gl, gr = pan_gains(pan)
        else:
            gl, gr = pan_gains(np.asarray(pan)[:n])
        self.L[i:i + n] += x * gl
        self.R[i:i + n] += x * gr
        if send:
            self.sL[i:i + n] += x * gl * send
            self.sR[i:i + n] += x * gr * send

    def add_st(self, t, xl, xr, gain=1.0, send=0.25):
        i = int(round(t * SR))
        n = min(len(xl), N + PAD - i)
        self.L[i:i + n] += xl[:n] * gain
        self.R[i:i + n] += xr[:n] * gain
        if send:
            self.sL[i:i + n] += xl[:n] * gain * send
            self.sR[i:i + n] += xr[:n] * gain * send


def lp(x, fc, order=2):
    return signal.sosfilt(signal.butter(order, min(fc, SR * 0.45), "low", fs=SR, output="sos"), x)


def hp(x, fc, order=2):
    return signal.sosfilt(signal.butter(order, fc, "high", fs=SR, output="sos"), x)


def bp(x, lo, hi, order=2):
    return signal.sosfilt(signal.butter(order, [lo, min(hi, SR * 0.45)], "band", fs=SR, output="sos"), x)


def peq(x, f0, gain_db, q=1.0):
    """RBJ peaking EQ"""
    A = 10 ** (gain_db / 40)
    w = 2 * np.pi * f0 / SR
    al = np.sin(w) / (2 * q)
    b = [1 + al * A, -2 * np.cos(w), 1 - al * A]
    a = [1 + al / A, -2 * np.cos(w), 1 - al / A]
    return signal.lfilter(b, a, x)


def noise(n, r=None):
    return (r or rng).standard_normal(n)


# ----------------------------------------------------------------------------
# reverb (synthesized frequency-dependent IR)
# ----------------------------------------------------------------------------
def make_ir(rt_low, rt_mid, rt_high, length, predelay=0.02, seed=1, er=True):
    r = np.random.default_rng(seed)
    n = int(length * SR)
    t = tarr(n)
    irs = []
    for _ in range(2):
        nz = r.standard_normal(n)
        ir = (lp(nz, 600) * np.exp(-6.9078 * t / rt_low) + bp(nz, 600, 4000) * np.exp(-6.9078 * t / rt_mid)
              + hp(nz, 4000) * np.exp(-6.9078 * t / rt_high) * 0.6)
        ir *= 1 - np.exp(-t / 0.012)
        if er:
            for _ in range(12):
                d = r.uniform(0.004, 0.06)
                ir[int(d * SR)] += r.uniform(-1, 1) * 2.5 * np.exp(-d / 0.05)
        ir = np.concatenate([np.zeros(int(predelay * SR)), ir])
        ir = fade_edges(ir, 0.0001, 0.2)
        irs.append(ir / np.sqrt(np.sum(ir ** 2)))
    return irs


def apply_reverb(bus, ir):
    wl = signal.fftconvolve(bus.sL, ir[0])[: N + PAD]
    wr = signal.fftconvolve(bus.sR, ir[1])[: N + PAD]
    return wl, wr


# ----------------------------------------------------------------------------
# instruments
# ----------------------------------------------------------------------------
def additive(f, partials, length, attack=0.003, vel=1.0, phase_rand=True):
    n = int(length * SR)
    t = tarr(n)
    out = np.zeros(n)
    for ratio, amp, t60 in partials:
        fr = f * ratio
        if fr > 18500 or amp == 0:
            continue
        ph = rng.uniform(0, 2 * np.pi) if phase_rand else 0.0
        out += amp * np.exp(-6.9078 * t / t60) * np.sin(2 * np.pi * fr * t + ph)
    na = max(2, int(attack * SR))
    out[:na] *= 0.5 - 0.5 * np.cos(np.pi * np.arange(na) / na)
    return fade_edges(out * vel, attack, 0.02)


def piano(f, dur, vel=0.5):
    """Acoustic grand model.
    - stretched (inharmonic) partials f_k = k f sqrt(1 + B k^2), B rising toward the treble
    - 1/2/3 strings per note with sub-cent mistuning -> beating & two-stage (prompt/after-sound) decay
    - hammer: velocity-dependent spectral tilt + strike-position comb (x0 ~ 1/8) + felt/noise knock
    - key-bed / soundboard thump, damper release (+ tiny felt noise); top octave has no damper
    """
    m = 69 + 12 * np.log2(f / 440)
    B = float(np.clip(6e-5 * 2 ** ((m - 48) / 13), 3e-5, 4e-3))
    T0 = float(np.clip(15.0 * (130.8 / f) ** 0.62, 1.2, 24.0))
    undamped = m >= 89
    ring = T0 if undamped else min(dur + 0.6, T0 * 1.05)
    n = int(ring * SR)
    t = tarr(n)
    out = np.zeros(n)
    ns = 1 if m < 34 else (2 if m < 46 else 3)
    detc = [0.0] if ns == 1 else ([-0.45, 0.45] if ns == 2 else [-0.7, 0.05, 0.6])
    detc = [d * rng.uniform(0.6, 1.4) for d in detc]
    nmax = int(min(36, 12000 / f))
    tilt = 1.05 + 0.9 * (1 - vel)
    fch = 1500 + 6500 * vel ** 1.4
    x0 = 1 / 8 + rng.uniform(-0.006, 0.006)
    for k in range(1, nmax + 1):
        fk = k * f * np.sqrt(1 + B * k * k)
        if fk > 17000:
            break
        a = k ** -tilt * (0.12 + abs(np.sin(np.pi * k * x0))) / (1 + (fk / fch) ** 2)
        Tk = T0 / (1 + 0.85 * (fk / 900) ** 1.25)
        pf = 0.55 + 0.25 * min(1, fk / 3000)
        env = pf * np.exp(-6.9078 * t / (Tk * 0.16)) + (1 - pf) * np.exp(-6.9078 * t / Tk)
        ph = rng.uniform(0, 2 * np.pi)
        s = np.zeros(n)
        for c in detc:
            s += np.sin(2 * np.pi * fk * 2 ** (c * (1 + 0.15 * k) / 1200) * t + ph)
        out += a * env * s / len(detc)
    # hammer attack: ~1.5 ms rise
    na = int(0.0015 * SR)
    out[:na] *= np.linspace(0, 1, na) ** 1.5
    # damper
    if not undamped and dur < ring:
        io = int(dur * SR)
        tr = t[io:] - dur
        rel = 0.16 + 0.25 * (261.6 / f) ** 0.5
        lo = lp(out[io:], 900)
        out[io:] = lo * np.exp(-6.9078 * tr / rel) + (out[io:] - lo) * np.exp(-6.9078 * tr / (rel * 0.45))
        k = int(0.03 * SR)
        if io + k < n:
            out[io:io + k] += lp(noise(k), 500) * np.hanning(k) * 0.004 * vel
    # hammer felt knock + key/soundboard thump
    k = int(0.03 * SR)
    kn = bp(noise(k), 150, min(6000, 1200 + 2 * f)) * np.exp(-np.arange(k) / (0.0035 * SR))
    out[:k] += kn * 0.05 * vel ** 1.3
    th = np.sin(2 * np.pi * rng.uniform(85, 110) * t[:k]) * np.exp(-t[:k] / 0.012)
    out[:k] += th * 0.03 * vel
    return fade_edges(out * vel * 0.55, 0.0005, 0.03)


def music_box(f, vel=1.0):
    T = float(np.clip(3.4 * (523.0 / f) ** 0.5, 1.2, 5.0))
    parts = [(1.0, 1.0, T), (1.0 + 0.8 / f, 0.35, T * 0.9), (2.0, 0.07, T * 0.5), (3.01, 0.2, T * 0.33),
             (5.43, 0.08, T * 0.18), (8.21, 0.035, T * 0.1), (11.9, 0.015, T * 0.06)]
    x = additive(f, parts, min(T * 1.1, 6.0), attack=0.0015, vel=vel)
    k = int(0.004 * SR)
    x[:k] += hp(noise(k), 3000) * np.hanning(k) * 0.03 * vel     # comb-tooth pluck
    return x


def celesta(f, vel=1.0):
    T = float(np.clip(2.6 * (523.0 / f) ** 0.4, 1.0, 4.0))
    parts = [(1.0, 1.0, T), (1.0015, 0.3, T), (2.0, 0.3, T * 0.55), (3.0, 0.07, T * 0.35),
             (4.02, 0.05, T * 0.25), (7.1, 0.03, 0.12)]
    x = additive(f, parts, min(T * 1.1, 5.0), attack=0.004, vel=vel)
    k = int(0.01 * SR)
    x[:k] += lp(noise(k), 1500) * np.hanning(k) * 0.03 * vel     # felt hammer
    return x


def glock(f, vel=1.0):
    """glockenspiel bar: free-free bar modes 1 : 2.76 : 5.40 : 8.93, hard mallet click"""
    T = float(np.clip(3.8 * (1568 / f) ** 0.5, 1.6, 5.5))
    parts = [(1.0, 1.0, T), (1.0006, 0.25, T * 0.9), (2.76, 0.32, T * 0.3), (5.40, 0.16, T * 0.12),
             (8.93, 0.07, T * 0.05)]
    x = additive(f, parts, min(T, 5.5), attack=0.0008, vel=vel)
    k = int(0.003 * SR)
    x[:k] += hp(noise(k), 4000) * np.hanning(k) * 0.08 * vel
    return x


def pluck(f, vel=1.0, T=2.5, bright=1.0, length=None):
    parts = []
    nmax = int(min(30, 12000 / f))
    for k in range(1, nmax + 1):
        parts.append((k * (1 + 0.0002 * k * k), (1.0 / k ** 1.6) * bright ** (k - 1) * (0.3 + abs(np.sin(np.pi * k * 0.23))),
                      T / (1 + 0.45 * (k - 1))))
    return additive(f, parts, length or min(T * 1.1, 6.0), attack=0.003, vel=vel)


def harp(f, vel=1.0):
    return pluck(f, vel, T=float(np.clip(3.5 * (262 / f) ** 0.35, 1.2, 5)), bright=0.8)


def pizz(f, vel=1.0):
    return lp(pluck(f, vel, T=0.5, bright=0.7, length=0.6), 2200)


def polyblep_saw(freq_inst, phase0=0.0):
    dt = freq_inst / SR
    ph = (phase0 + np.cumsum(dt)) % 1.0
    y = 2 * ph - 1
    m = ph < dt
    x = ph[m] / dt[m]
    y[m] -= x + x - x * x - 1
    m = ph > 1 - dt
    x = (ph[m] - 1) / dt[m]
    y[m] -= x * x + x + x + 1
    return y


def string_body(x, bright=1.0):
    """violin-family body colouring (wood resonances, soft top end)"""
    x = peq(x, 280, 3.0, 1.2)
    x = peq(x, 1050, -2.0, 1.5)
    x = peq(x, 2600, 2.5 * bright, 1.4)
    return x


def strings(notes, t0, t1, amp_pts, cut0=2000, cut1=None, voices=5, detune=10.0, width=0.8,
            attack=0.5, release=0.9, vib=0.0035):
    """sustained ensemble chord. returns stereo (L, R) starting at t0"""
    cut1 = cut1 or cut0
    length = t1 - t0 + release
    n = int(length * SR)
    t = tarr(n)
    L = np.zeros(n)
    R = np.zeros(n)
    for ni, name in enumerate(notes):
        f = nf(name)
        for v in range(voices):
            cents = detune * ((v - (voices - 1) / 2) / max(1, (voices - 1) / 2)) + rng.uniform(-2, 2)
            fv = f * 2 ** (cents / 1200)
            vdepth = vib * np.clip(t / 1.2, 0, 1)
            drift = 1 + 0.001 * np.sin(2 * np.pi * rng.uniform(0.1, 0.3) * t + rng.uniform(0, 6))
            finst = fv * (1 + vdepth * np.sin(2 * np.pi * rng.uniform(4.6, 5.8) * t + rng.uniform(0, 6))) * drift
            s = polyblep_saw(finst, rng.uniform())
            p = width * ((v / max(1, voices - 1)) * 2 - 1) * (0.7 + 0.3 * (ni % 2))
            gl, gr = pan_gains(p)
            L += s * gl
            R += s * gr
    norm = 1.0 / (len(notes) * voices) ** 0.5

    def filt(x):
        a = lp(x, cut0, 2)
        if cut1 != cut0:
            b = lp(x, cut1, 2)
            w = np.clip(t / max(1e-3, t1 - t0), 0, 1)
            a = a * (1 - w) + b * w
        return string_body(hp(a, 50, 2)) * norm
    L, R = filt(L), filt(R)
    env = env_points(amp_pts, n, t0)
    na = int(attack * SR)
    env[:na] *= 0.5 - 0.5 * np.cos(np.pi * np.arange(na) / na)
    ir = int((t1 - t0) * SR)
    nr = n - ir
    env[ir:] *= 0.5 + 0.5 * np.cos(np.pi * np.arange(nr) / nr)
    return L * env, R * env


def string_line(events, amp_pts, voices=6, detune=8.0, cut=3400, port=0.09, vib=0.0055, width=0.6,
                release=0.8, rebow=0.25):
    """legato bowed melody for a section. events: [(abs_t, note, dur)]. returns (t0, L, R)"""
    t0 = events[0][0]
    t1 = max(e[0] + e[2] for e in events)
    n = int((t1 - t0 + release) * SR)
    t = tarr(n)
    lf = np.zeros(n)
    onset = np.zeros(n)
    for (ts, name, d) in events:
        i = int((ts - t0) * SR)
        lf[i:] = np.log2(nf(name))
        onset[i:] = ts - t0
    lf = uniform_filter1d(lf, max(3, int(port * SR)), mode="nearest")
    since = t - onset
    art = 1 - rebow * np.exp(-since / 0.05) * (1 - np.exp(-since / 0.008))    # small re-bow dip on note change
    L = np.zeros(n)
    R = np.zeros(n)
    for v in range(voices):
        cents = detune * ((v - (voices - 1) / 2) / max(1, (voices - 1) / 2)) + rng.uniform(-2.5, 2.5)
        vr = rng.uniform(5.0, 6.0)
        vd = vib * np.clip((since - 0.25) / 0.5, 0, 1) * rng.uniform(0.7, 1.2)
        finst = 2 ** lf * 2 ** (cents / 1200) * (1 + vd * np.sin(2 * np.pi * vr * t + rng.uniform(0, 6)))
        s = polyblep_saw(finst, rng.uniform())
        p = width * ((v / max(1, voices - 1)) * 2 - 1)
        gl, gr = pan_gains(p)
        L += s * gl
        R += s * gr
    bow = hp(noise(n), 2500) * 0.05
    L, R = L + bow, R + bow[::-1]
    norm = 1.0 / voices ** 0.5
    L = string_body(hp(lp(L, cut, 2), 70)) * norm
    R = string_body(hp(lp(R, cut, 2), 70)) * norm
    env = env_points(amp_pts, n, t0) * art
    ir = int((t1 - t0) * SR)
    nr = n - ir
    env[ir:] *= 0.5 + 0.5 * np.cos(np.pi * np.arange(nr) / nr)
    na = int(0.12 * SR)
    env[:na] *= 0.5 - 0.5 * np.cos(np.pi * np.arange(na) / na)
    return t0, L * env, R * env


def timpani(f, vel=1.0, T=2.2):
    n = int(T * 1.1 * SR)
    t = tarr(n)
    bend = 1 + 0.04 * np.exp(-t / 0.03)
    out = np.zeros(n)
    for ratio, a, tt in [(1.0, 1.0, T), (1.5, 0.45, T * 0.6), (1.99, 0.3, T * 0.45), (2.44, 0.18, T * 0.3)]:
        out += a * np.exp(-6.9078 * t / tt) * np.sin(2 * np.pi * np.cumsum(f * ratio * bend) / SR)
    k = int(0.05 * SR)
    out[:k] += lp(noise(k), 400) * np.exp(-np.arange(k) / (0.012 * SR)) * 0.4
    return fade_edges(out * vel, 0.002, 0.05)


def cymbal_swell(length, vel=1.0):
    """soft-mallet suspended cymbal roll: swells to the end, then short natural tail"""
    tail = 2.5
    n = int((length + tail) * SR)
    t = tarr(n)
    x = bp(noise(n), 2500, 13000, 2) * 0.5
    for _ in range(40):
        x += 0.04 * np.sin(2 * np.pi * rng.uniform(2800, 9500) * t + rng.uniform(0, 6))
    env = np.where(t < length, (t / length) ** 2.2, np.exp(-6.9078 * (t - length) / tail))
    return fade_edges(x * env * vel, 0.05, 0.1)


# ----------------------------------------------------------------------------
# time-varying filtered noise
# ----------------------------------------------------------------------------
def shaped_noise(length, fc_fn, bw_oct_fn, seed=None, amp_fn=None):
    r = np.random.default_rng(seed) if seed is not None else rng
    n = int(length * SR)
    x = r.standard_normal(n + 2048)
    f, tt, Z = signal.stft(x, fs=SR, nperseg=1024, noverlap=768)
    fc = np.maximum(fc_fn(tt), 20)
    bw = bw_oct_fn(tt)
    lf = np.log2(np.maximum(f, 1.0))[:, None]
    mask = np.exp(-0.5 * ((lf - np.log2(fc)[None, :]) / bw[None, :]) ** 2)
    _, y = signal.istft(Z * mask, fs=SR, nperseg=1024, noverlap=768)
    y = y[:n]
    y /= (np.sqrt(np.mean(y ** 2)) + 1e-12)
    if amp_fn is not None:
        y *= amp_fn(tarr(n))
    return fade_edges(y, 0.005, 0.02)


def const(v):
    return lambda tt: np.full_like(tt, v, dtype=float)


def smooth_random(n, rate_hz, r=None, lo=0.0, hi=1.0):
    """slowly varying random curve (cubic-ish via interpolation of random points)"""
    r = r or rng
    k = max(4, int(n / SR * rate_hz) + 3)
    pts = r.uniform(lo, hi, k)
    x = np.interp(np.arange(n), np.linspace(0, n, k), pts)
    return uniform_filter1d(x, max(3, int(SR / rate_hz / 2)), mode="nearest")


# ============================================================================
#                                   MUSIC
# ============================================================================
THEME = {
    1: [("B4", 2), ("A4", .5), ("G4", .5)],
    2: [("D5", 2), ("B4", 1)],
    3: [("C5", 1.5), ("B4", .5), ("A4", 1)],
    4: [("A4", 3)],
    5: [("B4", 2), ("A4", .5), ("G4", .5)],
    6: [("G5", 2), ("E5", 1)],
    7: [("D5", 1.5), ("C5", .5), ("A4", .5), ("B4", .5)],
    8: [("G4", 3)],
}
# broken-chord figures (6 eighths per 3/4 bar)
ARP = {
    "G": ["G2", "D3", "G3", "B3", "D4", "B3"],
    "Em": ["E2", "B2", "E3", "G3", "B3", "G3"],
    "C": ["C3", "G3", "C4", "E4", "G4", "E4"],
    "Cmaj7": ["C3", "G3", "B3", "E4", "G4", "E4"],
    "D": ["D3", "A3", "D4", "F#4", "A4", "F#4"],
    "Dsus": ["D3", "A3", "D4", "G4", "A4", "G4"],
    "D7": ["D3", "A3", "C4", "F#4", "A4", "F#4"],
    "Am": ["A2", "E3", "A3", "C4", "E4", "C4"],
    "B7": ["B2", "F#3", "A3", "D#4", "F#4", "D#4"],
}
PADS = {
    "G": ["G2", "D3", "B3", "G4"], "Em": ["E2", "B2", "G3", "E4"], "C": ["C3", "G3", "E4", "G4"],
    "D": ["D3", "A3", "F#4", "A4"], "D7": ["D3", "A3", "C4", "F#4"], "Am": ["A2", "E3", "C4", "E4"],
    "B7": ["B2", "F#3", "A3", "D#4"], "Cmaj7": ["C3", "G3", "B3", "E4"], "Dsus": ["D3", "A3", "G4", "A4"],
}


def shift_oct(name, o):
    letters = name.rstrip("0123456789-")
    return f"{letters}{int(name[len(letters):]) + o}"


def compose_bgm():
    P = Bus()     # piano (gets soundboard + sympathetic resonance)
    B = Bus()     # everything else
    hum = lambda s=0.007: float(rng.uniform(-s, s))

    def melody(bus, inst, bar_notes, t0, beat, vel, pan=0.0, send=0.35, octave=0, piano_hold=None):
        tt = t0
        out = []
        for name, beats in bar_notes:
            nm = shift_oct(name, octave)
            d = beats * beat
            if inst is piano:
                x = piano(nf(nm), piano_hold or d * 1.05, vel * rng.uniform(0.95, 1.05))
            else:
                x = inst(nf(nm), vel * rng.uniform(0.93, 1.05))
            bus.add(tt + hum(), x, pan=pan, send=send)
            out.append((tt, nm, d))
            tt += d
        return out

    def arps(chord, t0, beat, vel, pattern=range(6), hold=None, pan=-0.15, octave=0, lift=1.0):
        """pedalled broken chord; notes ring to end of the bar (sustain pedal)"""
        bar = 3 * beat
        for j in pattern:
            nm = shift_oct(ARP[chord][j], octave)
            tt = t0 + j * beat / 2
            v = vel * (1.12 if j == 0 else 0.82 + 0.1 * (j == 3)) * rng.uniform(0.92, 1.05) * lift
            P.add(tt + hum(0.01), piano(nf(nm), hold or (t0 + bar - tt + 0.15), v), pan=pan + 0.08 * (j - 2.5) / 2.5,
                  send=0.3)

    def pad(chord, t0, t1, pts, cut=1600, gain=1.0, oct_=0, send=0.5, **kw):
        L, R = strings([shift_oct(x, oct_) for x in PADS[chord]], t0, t1, pts, cut0=cut, **kw)
        B.add_st(t0, L, R, gain=gain, send=send)

    # ================================================================ S1 0-9
    # warm afternoon, G major 3/4 ~84 bpm. Theme first half on piano, doubled softly by glockenspiel.
    beat = 0.716
    bar = 3 * beat
    t = 0.15
    chords = ["G", "Em", "C", "D"]
    for i, ch in enumerate(chords):
        tb = t + i * bar
        arps(ch, tb, beat, 0.30 if i else 0.34)
        mel = melody(P, piano, THEME[i + 1], tb, beat, 0.40, pan=0.12)
        melody(B, glock, THEME[i + 1], tb + 0.004, beat, 0.085, pan=0.3, send=0.45, octave=1)
        pad(ch, tb, tb + bar + 0.3, [(tb, 0.10), (tb + bar, 0.11)], cut=1300, gain=0.9)
    # m4 held D: little glock echo of the motif (B A G -> A) before the dream
    for k, nm in enumerate(["F#6", "A6"]):
        B.add(t + 3 * bar + 1.4 + 0.36 * k, glock(nf(nm), 0.05), pan=0.45, send=0.6)

    # ================================================================ S2 9-25 flashback
    # 9.0 harp glissando into E minor + shimmer; music-box theme in E minor (G F# E | B G | A G F#)
    for k, nm in enumerate(["E4", "F#4", "G4", "A4", "B4", "C5", "D5", "E5", "F#5", "G5", "A5", "B5", "C6", "D6", "E6"]):
        B.add(9.02 + 0.055 * k + 0.004 * k * k, harp(nf(nm), 0.10 + 0.03 * np.sin(np.pi * k / 14)),
              pan=-0.5 + k / 14, send=0.6)
    P.add(9.9, piano(nf("E2"), 3.0, 0.28), pan=-0.2, send=0.4)
    P.add(9.92, piano(nf("B2"), 3.0, 0.22), pan=-0.1, send=0.4)
    pad("Em", 9.3, 13.1, [(9.3, 0.0), (10.5, 0.13), (13.1, 0.13)], cut=900, gain=1.0, oct_=0, send=0.55)
    fbeat = 0.8
    fbar = 3 * fbeat                                   # 10.6 / 13.0 / 15.4 -> 17.8
    minor_theme = [[("G4", 2), ("F#4", .5), ("E4", .5)],
                   [("B4", 2), ("G4", 1)],
                   [("A4", 1.5), ("G4", .5), ("F#4", 1)]]
    minor_ch = ["Em", "Cmaj7", "Am"]
    for i in range(3):
        tb = 10.6 + i * fbar
        melody(B, music_box, minor_theme[i], tb, fbeat, 0.16, pan=0.2, send=0.55, octave=1)
        # sparse music-box "comb" accompaniment: root + fifth + tenth, lonely
        acc = ARP[minor_ch[i]]
        for j, bt in enumerate([0, 1, 2]):
            B.add(tb + bt * fbeat + 0.02 + hum(), music_box(nf(shift_oct(acc[[0, 2, 3][j]], 1)), 0.08),
                  pan=-0.25, send=0.55)
        if i >= 1:
            pad(minor_ch[i], tb, tb + fbar + 0.2, [(tb, 0.12), (tb + fbar, 0.13)], cut=900, send=0.55)
    # B7 on the last beat (15.4 + 1.6 = 17.0) : longing dominant, then resolve to G major at 17.8
    pad("B7", 17.0, 17.85, [(17.0, 0.13), (17.8, 0.16)], cut=1000, attack=0.25, release=0.25, send=0.55)
    B.add(17.0, music_box(nf("D#5"), 0.07), pan=-0.25, send=0.55)
    P.add(15.4, piano(nf("A2"), 1.6, 0.22), pan=-0.2, send=0.4)
    P.add(17.0, piano(nf("B1"), 0.8, 0.22), pan=-0.2, send=0.4)
    # ---- 17.8 G major resolution: the same melody now in major (B A G), lullaby 3/4
    lbeat = 0.8
    lbar = 3 * lbeat
    lull = [(17.8, "G", THEME[1]), (20.2, "C", [("E5", 2), ("D5", 1)]), (22.6, "D", [("D5", 1.5), ("C5", .5), ("A4", 1)])]
    for tb, ch, mel_ in lull:
        melody(B, music_box, mel_, tb, lbeat, 0.17, pan=0.18, send=0.55, octave=1)
        melody(B, celesta, mel_, tb + 0.006, lbeat, 0.07, pan=-0.1, send=0.55, octave=0)
        arps(ch, tb, lbeat, 0.21, pattern=[0, 1, 2, 3, 4, 5], pan=-0.1)
        pad(ch, tb, tb + lbar + 0.1, [(tb, 0.16), (tb + lbar, 0.14)], cut=1500, send=0.55)
    B.add(17.8, glock(nf("G6"), 0.07), pan=0.4, send=0.7)          # the "light" of comfort
    B.add(17.8, harp(nf("G2"), 0.25), pan=-0.3, send=0.4)
    for k, nm in enumerate(["D6", "G6", "B6"]):
        B.add(24.1 + 0.18 * k, celesta(nf(nm), 0.035), pan=0.3, send=0.7)   # dream dissolves

    # ================================================================ S3 25-37 storm (E minor, restrained)
    # deceptive: D -> Em.  low strings drone, sparse low piano, theme fragment in minor, cut to near silence at 34.0
    L, R = strings(["E1", "E2", "B2"], 25.0, 28.4, [(25.0, 0.0), (25.8, 0.30), (27.0, 0.36), (28.4, 0.30)],
                   cut0=500, cut1=700, voices=6, detune=12, attack=0.6, release=0.6)
    B.add_st(25.0, L, R, send=0.45)
    L, R = strings(["C2", "C3", "G2", "E3"], 28.3, 30.9, [(28.3, 0.28), (30.9, 0.30)],
                   cut0=600, voices=6, detune=12, attack=0.5, release=0.6)
    B.add_st(28.3, L, R, send=0.45)
    L, R = strings(["A1", "A2", "E3", "C4"], 30.8, 32.4, [(30.8, 0.28), (32.4, 0.32)],
                   cut0=650, voices=6, detune=12, attack=0.5, release=0.5)
    B.add_st(30.8, L, R, send=0.45)
    L, R = strings(["B1", "B2", "F#3", "A3", "D#4"], 32.3, 34.0, [(32.3, 0.30), (33.9, 0.55), (34.0, 0.55)],
                   cut0=700, cut1=1300, voices=6, detune=14, attack=0.4, release=0.08, vib=0.006)
    B.add_st(32.3, L, R, send=0.35)
    # high violin harmonic, trembling (very soft)
    t0h, L, R = string_line([(26.2, "B5", 3.2), (29.4, "C6", 2.2), (31.6, "B5", 2.35)],
                            [(26.2, 0.0), (27.5, 0.035), (33.5, 0.045), (33.95, 0.05)], voices=4, cut=4500, vib=0.008,
                            release=0.08)
    B.add_st(t0h, L, R, send=0.6)
    # piano: sparse low octaves + minor theme fragment (one octave down)
    P.add(25.05, piano(nf("E1"), 3.0, 0.34), pan=-0.3, send=0.35)
    P.add(25.07, piano(nf("E2"), 3.0, 0.30), pan=-0.3, send=0.35)
    for tt, nm, d in [(25.9, "G3", 1.3), (27.3, "F#3", 0.45), (27.75, "E3", 1.2)]:
        P.add(tt, piano(nf(nm), d, 0.30), pan=0.05, send=0.4)
    P.add(28.35, piano(nf("C2"), 2.4, 0.28), pan=-0.3, send=0.35)
    for tt, nm, d in [(29.1, "B3", 1.4), (30.5, "G3", 0.9)]:
        P.add(tt, piano(nf(nm), d, 0.26), pan=0.05, send=0.4)
    P.add(30.85, piano(nf("A1"), 1.6, 0.28), pan=-0.3, send=0.35)
    for tt, nm, d in [(31.3, "A3", 0.6), (31.9, "G3", 0.25), (32.15, "F#3", 0.5)]:
        P.add(tt, piano(nf(nm), d, 0.26), pan=0.05, send=0.4)
    # trembling heartbeat: soft low pizz + timpani on B, 32.4-33.9
    for tt in [32.4, 32.72, 33.2, 33.5, 33.75]:
        B.add(tt, pizz(nf("B1"), 0.30), pan=-0.1, send=0.3)
        B.add(tt, timpani(nf("B1"), 0.10, T=1.0), pan=0.0, send=0.3)
    # 34.0: everything drops out under the thunder; near-silence, then a faint held E/B (numb)
    L, R = strings(["E3", "B3"], 35.0, 36.7, [(35.0, 0.0), (36.0, 0.035), (36.7, 0.04)], cut0=900, voices=4,
                   attack=0.8, release=0.5, vib=0.002)
    B.add_st(35.0, L, R, send=0.6)

    # ================================================================ S4 37-48 build -> tearful peak
    bb = 0.667                       # beat; bar = 2.0 s
    # 36.6 C: theme head as a hopeful question on piano ; 38.6 Dsus->D ; 40.6 theme returns (strings + piano)
    arps("Cmaj7", 36.6, bb, 0.24, pan=-0.1)
    melody(P, piano, [("B4", 2), ("A4", .5), ("G4", .5)], 36.6, bb, 0.30, pan=0.1)
    arps("Dsus", 38.6, bb, 0.27, pattern=[0, 1, 2, 3], pan=-0.1)
    arps("D", 38.6 + 2 * bb, bb, 0.29, pattern=[4, 5], pan=-0.1)
    melody(P, piano, [("A4", 2), ("F#4", .5), ("A4", .5)], 38.6, bb, 0.32, pan=0.1)
    pad("Cmaj7", 36.6, 38.7, [(36.6, 0.0), (38.6, 0.16)], cut=1500, attack=1.2)
    pad("Dsus", 38.6, 39.95, [(38.6, 0.18), (39.9, 0.22)], cut=1700)
    pad("D", 39.9, 40.7, [(39.9, 0.22), (40.6, 0.28)], cut=1800, attack=0.2)
    # climax harmony: G | Em | C (octave leap) | Dsus -> D  => 48.0 G
    clim = [(40.6, "G", THEME[1]), (42.6, "Em", THEME[2]), (44.6, "C", THEME[6])]
    for tb, ch, mel_ in clim:
        lift = 1.0 + 0.25 * (tb - 40.6) / 4
        arps(ch, tb, bb, 0.33 * lift, pan=-0.12)
        melody(P, piano, mel_, tb, bb, 0.36 * lift, pan=0.15, octave=1, send=0.4)
    # 46.6 Dsus4 -> D with rit. : D5 . C5 A4 (melody), everything leans into 48.0
    P.add(46.6, piano(nf("D6"), 0.9, 0.44), pan=0.15, send=0.4)
    P.add(47.45, piano(nf("C6"), 0.32, 0.38), pan=0.15, send=0.4)
    P.add(47.75, piano(nf("A5"), 0.3, 0.36), pan=0.15, send=0.4)
    for j, nm in enumerate(["D2", "A2", "D3", "G3", "A3"]):
        P.add(46.6 + 0.05 * j, piano(nf(nm), 0.75 - 0.05 * j, 0.36), pan=-0.15, send=0.35)
    for j, nm in enumerate(["D3", "A3", "F#4"]):
        P.add(47.3 + 0.08 * j, piano(nf(nm), 0.7 - 0.08 * j, 0.33), pan=-0.1, send=0.35)
    # violins: the theme (octave doubled), swelling 40.6 -> peak 44.6-47.8
    vio = [(40.6, "B4", 1.333), (41.933, "A4", 0.333), (42.267, "G4", 0.333), (42.6, "D5", 1.333),
           (43.933, "B4", 0.667), (44.6, "G5", 1.333), (45.933, "E5", 0.667), (46.6, "D5", 0.85),
           (47.45, "C5", 0.3), (47.75, "A4", 0.3)]
    vamp = [(40.6, 0.30), (42.6, 0.36), (44.4, 0.42), (44.7, 0.52), (46.6, 0.54), (47.4, 0.5), (48.05, 0.42)]
    t0v, L, R = string_line(vio, vamp, voices=7, cut=3800, vib=0.0065, release=0.5)
    B.add_st(t0v, L, R, send=0.5)
    t0v, L, R = string_line([(e[0], shift_oct(e[1], 1), e[2]) for e in vio],
                            [(p[0], p[1] * 0.45) for p in vamp], voices=6, cut=5200, vib=0.006, release=0.5)
    B.add_st(t0v, L, R, send=0.55)
    # cellos: descending bass line G F# E D C B A D -> G
    cel = [(40.6, "G3", 1.3), (41.9, "F#3", 0.7), (42.6, "E3", 1.3), (43.9, "D3", 0.7), (44.6, "C3", 1.3),
           (45.9, "B2", 0.7), (46.6, "A2", 0.7), (47.3, "D3", 0.75)]
    t0c, L, R = string_line(cel, [(40.6, 0.30), (44.6, 0.40), (47.8, 0.42), (48.05, 0.35)], voices=6, cut=2200,
                            vib=0.004, width=0.4, release=0.5)
    B.add_st(t0c, L, R, send=0.45)
    # inner pads
    pad("G", 40.6, 42.65, [(40.6, 0.20), (42.6, 0.22)], cut=1900)
    pad("Em", 42.6, 44.65, [(42.6, 0.22), (44.6, 0.25)], cut=2000)
    pad("C", 44.6, 46.65, [(44.6, 0.30), (46.6, 0.30)], cut=2300)
    pad("Dsus", 46.6, 47.35, [(46.6, 0.30), (47.3, 0.30)], cut=2300, attack=0.2)
    pad("D", 47.3, 48.05, [(47.3, 0.30), (48.0, 0.32)], cut=2400, attack=0.15, release=0.4)
    # contrabass
    L, R = strings(["G1"], 40.6, 42.6, [(40.6, 0.25), (42.6, 0.25)], cut0=400, voices=4, release=0.3)
    B.add_st(40.6, L, R, send=0.3)
    L, R = strings(["E1"], 42.6, 44.6, [(42.6, 0.25), (44.6, 0.27)], cut0=400, voices=4, release=0.3)
    B.add_st(42.6, L, R, send=0.3)
    L, R = strings(["C2"], 44.6, 46.6, [(44.6, 0.30), (46.6, 0.30)], cut0=450, voices=4, release=0.3)
    B.add_st(44.6, L, R, send=0.3)
    L, R = strings(["D2"], 46.6, 48.0, [(46.6, 0.30), (48.0, 0.30)], cut0=450, voices=4, release=0.3)
    B.add_st(46.6, L, R, send=0.3)
    # soft cymbal swell + timpani into the leap (44.6) and into the dawn (48.0)
    B.add(42.9, cymbal_swell(1.7, 0.035), pan=0.2, send=0.5)
    B.add(44.6, timpani(nf("C2"), 0.22, T=2.4), pan=-0.1, send=0.4)
    B.add(46.4, cymbal_swell(1.6, 0.04), pan=-0.2, send=0.5)
    for k, nm in enumerate(["D4", "E4", "F#4", "G4", "A4", "B4", "D5", "E5", "F#5", "G5", "A5", "B5", "D6"]):
        B.add(47.35 + 0.05 * k, harp(nf(nm), 0.07 + 0.005 * k), pan=-0.6 + 0.1 * k, send=0.6)

    # ================================================================ S5a 48-55 bright morning resolution
    rb = 0.714
    rbar = 3 * rb
    res = [(48.0, "G", 1), (48.0 + rbar, "Em", 2), (48.0 + 2 * rbar, "C", 3), (48.0 + 3 * rbar, "D", 4)]
    B.add(48.0, timpani(nf("G2"), 0.12, T=2.5), pan=0.0, send=0.4)
    B.add(48.0, harp(nf("G2"), 0.35), pan=-0.3, send=0.4)
    for tb, ch, m in res:
        last = m == 4
        arps(ch, tb, rb, 0.30, pan=-0.12, pattern=[0, 1, 2, 3] if last else range(6),
             hold=0.95 if last else None)
        melody(P, piano, THEME[m], tb, rb, 0.30, pan=0.12, octave=1, send=0.45,
               piano_hold=0.95 if last else None)
        melody(B, glock, THEME[m], tb + 0.003, rb, 0.07, pan=0.35, send=0.5, octave=1)
        # harp arps (8ths, high)
        for j in range(6 if not last else 2):
            nm = shift_oct(ARP[ch][(j + 2) % 6], 1)
            B.add(tb + j * rb / 2 + 0.01, harp(nf(nm), 0.07), pan=0.45 - 0.1 * j, send=0.5)
        te = tb + rbar if not last else 55.0
        pad(ch, tb, te + 0.05, [(tb, 0.24), (te, 0.22 if not last else 0.12)], cut=2400, send=0.5,
            release=0.9 if not last else 0.35)
    # warm violin counter-line (above the voice range) 48-54.4
    t0v, L, R = string_line([(48.0, "D6", 2.14), (50.14, "B5", 2.14), (52.28, "C6", 1.43), (53.71, "E6", 0.72),
                             (54.43, "D6", 0.55)],
                            [(48.0, 0.10), (50.0, 0.12), (54.4, 0.09), (54.98, 0.0)], voices=6, cut=5500, release=0.3)
    B.add_st(t0v, L, R, send=0.55)
    L, R = strings(["G1", "G2"], 48.0, 50.14, [(48.0, 0.24), (50.1, 0.22)], cut0=500, voices=4, release=0.3)
    B.add_st(48.0, L, R, send=0.3)
    L, R = strings(["E1", "E2"], 50.14, 52.28, [(50.14, 0.22), (52.28, 0.22)], cut0=500, voices=4, release=0.3)
    B.add_st(50.14, L, R, send=0.3)
    L, R = strings(["C2", "C3"], 52.28, 54.43, [(52.28, 0.22), (54.43, 0.22)], cut0=500, voices=4, release=0.3)
    B.add_st(52.28, L, R, send=0.3)

    # ================================================================ S5b 55-60 solo piano coda (after the shutter)
    coda = [(55.35, "B4", 0.72, 0.30), (56.07, "A4", 0.26, 0.26), (56.33, "G4", 0.36, 0.25),
            (56.72, "E5", 0.72, 0.29), (57.44, "D5", 0.46, 0.26),
            (57.92, "C5", 0.40, 0.25), (58.34, "A4", 0.40, 0.23)]
    for tt, nm, d, v in coda:
        P.add(tt, piano(nf(nm), d + 0.12, v), pan=0.1, send=0.45)
    for tt, nm, d, v in [(55.33, "G2", 1.35, 0.24), (55.6, "D3", 1.1, 0.18), (55.85, "B3", 0.85, 0.16),
                         (56.70, "C3", 1.2, 0.22), (56.95, "G3", 0.95, 0.17), (57.2, "E4", 0.7, 0.15),
                         (57.90, "D3", 0.8, 0.21), (58.1, "A3", 0.6, 0.16), (58.3, "C4", 0.4, 0.15)]:
        P.add(tt, piano(nf(nm), d, v), pan=-0.12, send=0.45)
    # final chord: rolled G add9, pedal held, rings and fades to silence by 60.0
    for j, (nm, v) in enumerate([("G1", 0.22), ("G2", 0.22), ("D3", 0.19), ("B3", 0.18), ("D4", 0.17),
                                 ("A4", 0.15), ("G4", 0.24)]):
        P.add(58.78 + 0.045 * j, piano(nf(nm), 3.0, v), pan=-0.3 + 0.1 * j, send=0.5)
    return P, B


def sympathetic(x):
    """undamped-string resonance (sustain pedal down): high-Q resonators on the G-major strings."""
    out = np.zeros_like(x)
    names = ["G1", "D2", "G2", "B2", "D3", "E3", "G3", "A3", "B3", "C4", "D4", "E4", "F#4", "G4", "A4", "B4",
             "D5", "E5", "G5"]
    for nm in names:
        f = nf(nm)
        for h, g in [(1, 1.0), (2, 0.5)]:
            fh = f * h * np.sqrt(1 + 1e-4 * h * h)
            T60 = float(np.clip(6.0 * (130 / fh) ** 0.5, 0.8, 8.0))
            bw = 6.9078 / (np.pi * T60)
            b, a = signal.iirpeak(fh, fh / bw, fs=SR)
            out += g * signal.lfilter(b, a, x)
    return out / len(names) ** 0.5


def soundboard(x):
    """short woody body IR convolution (spruce board + case)"""
    r = np.random.default_rng(77)
    n = int(0.09 * SR)
    t = tarr(n)
    ir = r.standard_normal(n) * np.exp(-t / 0.018)
    ir = peq(peq(lp(hp(ir, 70), 3500), 180, 5, 1.5), 520, 3, 2)
    ir[0] += 6.0
    return signal.fftconvolve(x, ir / np.sqrt(np.sum(ir ** 2)))[: len(x)]


# ============================================================================
#                                   SFX
# ============================================================================
def poisson_train(n, rate_fn, amp_lo, amp_hi, r):
    """impulse train with time-varying rate (events per second)"""
    t = tarr(n)
    rate = rate_fn(t) if callable(rate_fn) else np.full(n, rate_fn)
    p = rate / SR
    hits = r.uniform(size=n) < p
    x = np.zeros(n)
    k = int(hits.sum())
    x[hits] = r.uniform(amp_lo, amp_hi, k) ** 2 * r.choice([-1, 1], k)
    return x


def drop_kernel(f, T, r):
    n = int(max(0.02, T * 4) * SR)
    t = tarr(n)
    x = np.sin(2 * np.pi * f * (1 + 0.25 * t / T) * t) * np.exp(-t / T)
    x[:int(0.0006 * SR)] += r.standard_normal(int(0.0006 * SR)) * 0.6
    return fade_edges(x, 0.0002, 0.003)


def rain(length, rate_fn, amp_fn, heavy=0.0, muffle=None, seed=0):
    """rain: broadband hiss bed + individual droplet impulses (several pitched kernels) + splats.
    returns stereo (L, R)"""
    out = []
    n = int(length * SR)
    t = tarr(n)
    for ch in range(2):
        r = np.random.default_rng(seed * 10 + ch)
        bed = hp(lp(r.standard_normal(n), 7000 + 5000 * heavy), 350) * (0.7 + 0.3 * smooth_random(n, 0.7, r))
        bed = peq(bed, 5000, 3, 0.8)
        drops = np.zeros(n)
        for kf, kt, kr in [(2600, 0.0018, 0.35), (3900, 0.0012, 0.35), (5600, 0.0009, 0.3), (1500, 0.0035, 0.12)]:
            tr = poisson_train(n, lambda tt: rate_fn(tt) * kr, 0.2, 1.0, r)
            drops += signal.fftconvolve(tr, drop_kernel(kf * r.uniform(0.9, 1.1), kt, r))[:n]
        # heavier splats on the window / sill
        tr = poisson_train(n, lambda tt: rate_fn(tt) * 0.03, 0.3, 1.0, r)
        splat_k = bp(r.standard_normal(int(0.03 * SR)), 500, 3000) * np.exp(-tarr(int(0.03 * SR)) / 0.006)
        drops += signal.fftconvolve(tr, splat_k)[:n] * 0.8
        x = bed * (0.20 + 0.25 * heavy) + drops * 0.55
        if muffle:
            x = lp(x, muffle, 2)
            x = lp(x, muffle * 1.4, 2)
        out.append(x * amp_fn(t))
    return fade_edges(out[0], 0.2, 0.3), fade_edges(out[1], 0.2, 0.3)


def wind(length, amp_fn, seed=0):
    """storm wind: moving band-pass noise with gusts + faint whistling through the window frame"""
    res = []
    for ch in range(2):
        r = np.random.default_rng(900 + seed * 7 + ch)
        n = int(length * SR)
        g = smooth_random(n, 0.45, r, 0.2, 1.0) ** 1.6
        gcol = g[::256]
        gt = tarr(n)[::256]
        body = shaped_noise(length, lambda tt: 260 + 650 * np.interp(tt, gt, gcol), const(0.9), seed=1000 + seed + ch)
        whis = shaped_noise(length, lambda tt: 820 + 380 * np.interp(tt, gt, gcol), const(0.05), seed=1100 + seed + ch)
        rumble = lp(r.standard_normal(n), 120) * 3
        x = body * (0.4 + 0.9 * g) + whis * 0.12 * np.clip(g - 0.45, 0, 1) * 2 + rumble * 0.25 * g
        res.append(x * amp_fn(tarr(n)))
    return res


def thunder(big, seed):
    """lightning crack (tearing discharge) + rolling rumble. returns stereo (L, R)"""
    length = 9.0 if big else 7.0
    n = int(length * SR)
    t = tarr(n)
    out = []
    for ch in range(2):
        r = np.random.default_rng(seed * 10 + ch)
        # ---- crack: dense cluster of sharp broadband clicks tearing over ~120-250 ms
        crack = np.zeros(n)
        span = 0.25 if big else 0.16
        nc = 60 if big else 30
        for i in range(nc):
            tc = span * (r.uniform() ** 1.8)
            a = np.exp(-tc / (span * 0.5)) * r.uniform(0.3, 1.0)
            k = int(r.uniform(0.001, 0.006) * SR)
            idx = int(tc * SR)
            crack[idx:idx + k] += r.standard_normal(k) * np.exp(-np.arange(k) / (k / 4)) * a
        crack = hp(crack, 350 if big else 600)
        if not big:
            crack = lp(crack, 3500)
        crack += hp(r.standard_normal(n), 800) * np.exp(-t / (0.06 if big else 0.04)) * (0.35 if big else 0.15)
        # ---- boom (big only): sub-pressure hit
        boom = np.zeros(n)
        if big:
            f = 48 * (1 + 0.5 * np.exp(-t / 0.15))
            boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.9) * (1 - np.exp(-t / 0.01))
            boom += lp(r.standard_normal(n), 90, 4) * 6 * np.exp(-t / 1.2)
        # ---- rolling rumble: sequence of rolls with decaying strengths
        roll_env = np.zeros(n)
        tc = 0.1 if big else 0.35
        amp = 1.0
        while tc < length - 1.0:
            w = r.uniform(0.25, 0.7)
            x = np.clip((t - tc) / w, 0, None)
            roll_env += amp * r.uniform(0.5, 1.0) * x * np.exp(1 - x)
            tc += r.uniform(0.25, 0.8)
            amp *= r.uniform(0.72, 0.9)
        low = lp(r.standard_normal(n), 160 if big else 120, 4) * 5
        mid = bp(r.standard_normal(n), 120, 700) * (0.5 + 0.5 * np.abs(uniform_filter1d(r.standard_normal(n), 480)) * 20)
        rumble = (low + mid * (0.6 if big else 0.35)) * roll_env
        rumble *= np.exp(-t / (3.2 if big else 2.4))
        x = crack * (1.0 if big else 0.45) + boom * 0.9 + rumble * (0.55 if big else 0.30)
        out.append(fade_edges(x, 0.0005, 1.0))
    return out


def fabric(length, amp_pts, seed, lo=600, hi=7000, grain=250):
    """cloth rustle/swish: band noise with crinkly micro-grains"""
    r = np.random.default_rng(seed)
    n = int(length * SR)
    t = tarr(n)
    base = bp(r.standard_normal(n), lo, hi)
    gr = poisson_train(n, grain, 0.1, 1.0, r)
    gk = hp(r.standard_normal(int(0.004 * SR)), 2000) * np.hanning(int(0.004 * SR))
    crinkle = signal.fftconvolve(gr, gk)[:n]
    wob = 0.6 + 0.4 * smooth_random(n, 8, r)
    x = (base * 0.7 + crinkle * 0.8) * wob
    x += lp(r.standard_normal(n), 500) * 0.8 * wob       # body of the whoosh
    return fade_edges(x * np.interp(t, [p[0] for p in amp_pts], [p[1] for p in amp_pts]), 0.02, 0.05)


def flump(vel, seed, size=1.0):
    """blanket landing: soft low thud + air puff"""
    r = np.random.default_rng(seed)
    n = int(0.6 * SR)
    t = tarr(n)
    thud = lp(r.standard_normal(n), 220 * size, 4) * 4 * np.exp(-t / 0.07) * (1 - np.exp(-t / 0.004))
    thud += np.sin(2 * np.pi * 70 / size * t) * np.exp(-t / 0.06) * 0.5
    puff = bp(r.standard_normal(n), 300, 2500) * np.exp(-t / 0.12) * (1 - np.exp(-t / 0.01)) * 0.35
    return fade_edges((thud + puff) * vel, 0.001, 0.05)


def paw(vel, seed, claws=True):
    """small dog landing: padded thump + tiny claw ticks"""
    r = np.random.default_rng(seed)
    n = int(0.25 * SR)
    t = tarr(n)
    x = lp(r.standard_normal(n), 260, 4) * 5 * np.exp(-t / 0.03) * (1 - np.exp(-t / 0.002))
    x += np.sin(2 * np.pi * 115 * t) * np.exp(-t / 0.04) * 0.6
    if claws:
        for k in range(r.integers(2, 4)):
            tc = int(r.uniform(0.005, 0.06) * SR)
            kk = int(0.0015 * SR)
            x[tc:tc + kk] += hp(r.standard_normal(kk), 3000) * np.hanning(kk) * 0.5
    return fade_edges(x * vel, 0.0005, 0.03)


def chirp_fm(f0, f1, dur, fm_rate=0.0, fm_depth=0.0, h2=0.12):
    n = int(dur * SR)
    t = tarr(n)
    fr = f0 * (f1 / f0) ** (t / dur) * (1 + fm_depth * np.sin(2 * np.pi * fm_rate * t))
    ph = 2 * np.pi * np.cumsum(fr) / SR
    x = (np.sin(ph) + h2 * np.sin(2 * ph)) * np.sin(np.pi * t / dur) ** 1.5
    return fade_edges(x, 0.001, 0.002)


def sparrow(r):
    """'chirp-chirp' cluster"""
    notes = []
    tt = 0.0
    for _ in range(r.integers(2, 5)):
        f0 = r.uniform(3300, 4300)
        notes.append((tt, chirp_fm(f0, f0 * r.uniform(1.15, 1.45), r.uniform(0.045, 0.075), 60, 0.04)))
        tt += r.uniform(0.09, 0.16)
    return notes


def warbler(r, base=4200):
    """fast trill phrase + descending tail"""
    notes = []
    tt = 0.0
    for i in range(r.integers(6, 10)):
        f = base * (1 + 0.08 * np.sin(i * 1.3))
        notes.append((tt, chirp_fm(f * 1.25, f, 0.04, 90, 0.05)))
        tt += 0.055
    notes.append((tt + 0.02, chirp_fm(base * 1.4, base * 0.75, 0.22, 35, 0.03)))
    return notes


def drip(f0, r):
    """water drop into a puddle/gutter: bubble resonance with upward glide"""
    n = int(0.12 * SR)
    t = tarr(n)
    fr = f0 * (1 + 0.6 * (1 - np.exp(-t / 0.02)))
    x = np.sin(2 * np.pi * np.cumsum(fr) / SR) * np.exp(-t / 0.025) * (1 - np.exp(-t / 0.001))
    k = int(0.001 * SR)
    x[:k] += r.standard_normal(k) * 0.3
    return fade_edges(x, 0.0003, 0.01)


def clock_tick(tock, r):
    n = int(0.08 * SR)
    t = tarr(n)
    f = 2300 if tock else 2700
    x = (np.sin(2 * np.pi * f * t) * np.exp(-t / 0.004) + 0.6 * np.sin(2 * np.pi * f * 1.62 * t) * np.exp(-t / 0.0025)
         + 0.3 * np.sin(2 * np.pi * 900 * t) * np.exp(-t / 0.008))
    k = int(0.001 * SR)
    x[:k] += r.standard_normal(k) * 0.5
    return fade_edges(x, 0.0002, 0.005)


def shimmer(length, peak_at, reverse, seed, notes=("G5", "B5", "D6", "E6", "G6", "B6", "D7")):
    """magical shimmer: chime cluster played backwards (swelling) + airy noise"""
    r = np.random.default_rng(seed)
    n = int(length * SR)
    x = np.zeros(n)
    for k, nm in enumerate(notes):
        f = nf(nm)
        T = r.uniform(0.9, 1.6)
        c = additive(f, [(1, 1, T), (2.0, 0.3, T * 0.5), (2.76, 0.2, T * 0.4), (5.4, 0.08, T * 0.2)], T, vel=1.0)
        if reverse:
            c = c[::-1]
            st = int(peak_at * SR) - len(c) + int(r.uniform(-0.05, 0.05) * SR)
        else:
            st = int((peak_at + 0.06 * k) * SR)
        st = max(0, st)
        m = min(len(c), n - st)
        x[st:st + m] += c[:m] * r.uniform(0.5, 1.0)
    air = shaped_noise(length, lambda tt: 4000 + 3000 * np.clip(tt / length, 0, 1), const(0.6), seed=seed + 1)
    tt = tarr(n)
    aenv = np.interp(tt, [0, peak_at, length], [0, 1, 0]) ** 2 if reverse else np.interp(tt, [0, peak_at, length], [0.0, 1, 0])
    return fade_edges(x * 0.5 + air * 0.25 * aenv, 0.05, 0.1)


def shutter():
    """two-part mechanical shutter 'ka-sha': release/mirror click, curtain run, closing click + wind spring"""
    r = np.random.default_rng(5500)
    n = int(0.35 * SR)
    t = tarr(n)
    x = np.zeros(n)

    def click(at, freqs, amp, dec):
        i = int(at * SR)
        m = n - i
        tt = t[:m]
        c = sum(a * np.sin(2 * np.pi * f * tt + r.uniform(0, 6)) * np.exp(-tt / (dec * d)) for f, a, d in freqs)
        k = int(0.0012 * SR)
        c[:k] += r.standard_normal(k) * 1.2
        c += hp(r.standard_normal(m), 1500) * np.exp(-tt / 0.003) * 0.6
        c += lp(r.standard_normal(m), 400) * np.exp(-tt / 0.01) * 1.2   # body thunk
        x[i:] += c * amp

    click(0.0, [(2150, 1.0, 1.0), (3700, 0.7, 0.7), (5200, 0.5, 0.5), (820, 0.4, 1.4)], 1.0, 0.012)
    # curtain travel: short metallic swish between the clicks
    i0, i1 = int(0.006 * SR), int(0.062 * SR)
    sw = bp(r.standard_normal(i1 - i0), 2500, 9000) * np.hanning(i1 - i0) * 0.25
    x[i0:i1] += sw
    click(0.066, [(1850, 1.0, 1.0), (3300, 0.8, 0.7), (6100, 0.4, 0.4), (700, 0.5, 1.4)], 1.25, 0.016)
    # advance spring 'shh' tail (the "ッ")
    i2 = int(0.07 * SR)
    m = n - i2
    x[i2:] += bp(r.standard_normal(m), 1800, 7000) * np.exp(-t[:m] / 0.035) * 0.35
    return fade_edges(x, 0.0002, 0.05)


def flash_whine(length=1.4):
    """flash capacitor recharge: faint rising whine"""
    n = int(length * SR)
    t = tarr(n)
    f = 3200 + 3800 * (1 - np.exp(-t / 0.5))
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.interp(t, [0, 0.1, length * 0.7, length], [0, 1, 0.6, 0])
    return fade_edges(x, 0.01, 0.1)


def polaroid(length=1.2):
    """instant-camera eject: geared motor whirr + film sliding out + paper flick"""
    r = np.random.default_rng(6600)
    n = int(length * SR)
    t = tarr(n)
    run = 1.0
    spd = np.interp(t, [0, 0.08, run - 0.1, run, length], [0.3, 1.0, 1.0, 0.25, 0.0])
    f_motor = 95 * spd
    ph = np.cumsum(f_motor) / SR
    motor = polyblep_saw(f_motor + 1e-3, 0.0) * 0.4
    gear = (np.sin(2 * np.pi * ph * 7) > 0.85).astype(float)          # gear teeth ~ 665 Hz buzz
    gear = bp(gear - gear.mean(), 300, 4000) * 0.9
    film = bp(r.standard_normal(n), 1800, 7500) * 0.35 * smooth_random(n, 20, r, 0.6, 1.0)
    mot_env = np.interp(t, [0, 0.03, run - 0.05, run + 0.03, length], [0, 1, 1, 0, 0])
    x = (bp(motor, 150, 2500) + gear) * mot_env + film * np.interp(t, [0, 0.12, run - 0.1, run + 0.02, length], [0, 1, 1, 0, 0])
    # paper flick when the print leaves the slot
    i = int((run + 0.02) * SR)
    k = int(0.05 * SR)
    x[i:i + k] += hp(r.standard_normal(k), 1500) * np.exp(-np.arange(k) / (0.008 * SR)) * 0.9
    x[i:i + k] += lp(r.standard_normal(k), 600) * np.exp(-np.arange(k) / (0.01 * SR)) * 0.6
    return fade_edges(x, 0.005, 0.05)


def compose_sfx():
    S = Bus()      # close foley / room (room IR)
    O = Bus()      # outdoor / weather (big, diffuse IR)
    r = np.random.default_rng(4242)

    # ---- 0-9 afternoon room tone: soft air, clock tick, distant birds (through the window)
    rt = lp(r.standard_normal(int(9.6 * SR)), 700) * 0.06
    S.add(0.0, fade_edges(rt, 0.3, 1.0), pan=0.0, send=0.1)
    for i, tt in enumerate(np.arange(0.35, 9.2, 1.0)):
        g = 0.08 * (1.0 if tt < 8.4 else np.interp(tt, [8.4, 9.2], [1, 0.3]))
        S.add(tt + r.uniform(-0.004, 0.004), clock_tick(i % 2 == 1, r) * g, pan=0.55, send=0.3)
    for bt in [0.6, 2.3, 3.9, 6.2, 7.8]:
        for dt, c in sparrow(r):
            O.add(bt + dt, lp(c, 3000) * 0.07, pan=-0.6 + r.uniform(-0.1, 0.2), send=0.4)
    for bt in [1.6, 5.2]:
        for dt, c in warbler(r, 3600):
            O.add(bt + dt, lp(c, 2800) * 0.04, pan=0.7, send=0.5)

    # ---- 9.0-10.5 dreamy transition (reverse shimmer swelling to 9.9, then drifts)
    x = shimmer(2.2, 1.0, True, 31, notes=("E5", "G5", "B5", "D6", "E6", "G6", "B6"))
    O.add(8.9, x * 0.10, pan=0.0, send=0.6)
    x = shimmer(1.8, 0.0, False, 33, notes=("B6", "G6", "E6"))
    O.add(9.9, x * 0.05, pan=0.3, send=0.7)

    # ---- 10-24 flashback rain (muffled, gentle, on the window)
    L, R = rain(14.4, const(55.0), lambda tt: np.interp(tt, [0, 1.2, 12.8, 14.4], [0, 1, 1, 0]), heavy=0.0,
                muffle=1900, seed=11)
    O.add_st(9.9, L * 0.65, R * 0.65, send=0.3)
    # 14.8-16.2 blanket slides off the sofa (swish), soft flump at 16.2 ; paw at 16.6
    S.add(14.8, fabric(1.45, [(0, 0), (0.15, 0.4), (0.9, 1.0), (1.3, 0.7), (1.45, 0)], 51) * 0.13, pan=0.25, send=0.3)
    S.add(16.2, flump(0.25, 52), pan=0.1, send=0.25)
    S.add(16.2, fabric(0.45, [(0, 0.8), (0.4, 0)], 53, 400, 4000, 120) * 0.06, pan=0.1, send=0.25)
    S.add(16.6, paw(0.17, 54), pan=-0.15, send=0.25)
    S.add(16.72, paw(0.10, 55, claws=False), pan=-0.1, send=0.25)
    # ---- 23.5-25.5 reverse shimmer back to present (peak 25.0)
    x = shimmer(2.0, 1.5, True, 41, notes=("G5", "B5", "D6", "G6", "A6", "B6", "D7"))
    O.add(23.5, x * 0.11, pan=0.0, send=0.6)

    # ---- 25-48 storm: heavy rain + wind, calming from 44, gone by ~49
    def storm_amp(tt):
        a = 25.0 + tt
        return np.interp(a, [25.0, 25.5, 26.0, 44.0, 46.5, 48.0, 49.5], [0, 0.7, 1.0, 1.0, 0.55, 0.25, 0.0])

    L, R = rain(24.6, lambda tt: np.interp(25.0 + tt, [25, 26, 44, 48, 49.6], [250, 420, 420, 120, 40]), storm_amp,
                heavy=1.0, seed=21)
    O.add_st(25.0, L * 0.30, R * 0.30, send=0.25)
    wl, wr = wind(24.6, lambda tt: storm_amp(tt) * np.interp(25.0 + tt, [25, 26, 44, 48], [0.8, 1.0, 1.0, 0.4]), seed=3)
    O.add_st(25.0, wl * 0.07, wr * 0.07, send=0.3)
    # 27.0 medium lightning + rolling thunder ; 34.0 very close crack + big boom
    L, R = thunder(False, 71)
    O.add_st(27.0, L * 0.28, R * 0.26, send=0.35)
    L, R = thunder(True, 72)
    O.add_st(34.0, L * 0.50, R * 0.52, send=0.3)
    # rain gust burst after the big one
    x = shaped_noise(3.0, lambda tt: 700 + 300 * tt, const(1.0), seed=73,
                     amp_fn=lambda tt: np.interp(tt, [0, 0.4, 3.0], [0, 1, 0]) * 0.04)
    O.add(34.3, x, pan=-0.3, send=0.3)

    # ---- 38.0-40.2 kinako drags the blanket, hops at 38.6 / 39.6, flump 40.2
    tugs = lambda tt: 0.55 + 0.45 * np.clip(np.sin(2 * np.pi * 2.6 * tt), 0, 1) ** 2
    drag = fabric(2.2, [(0, 0), (0.15, 0.8), (2.0, 0.8), (2.2, 0)], 61, 300, 5000, 180)
    drag *= tugs(tarr(len(drag)))
    S.add(38.0, drag * 0.07, pan=np.linspace(-0.4, 0.2, len(drag)), send=0.3)
    for ht, sd in [(38.6, 62), (39.6, 63)]:
        S.add(ht - 0.05, fabric(0.12, [(0, 0), (0.05, 1), (0.12, 0)], sd + 10, 800, 6000, 400) * 0.06, pan=0.0, send=0.25)
        S.add(ht, paw(0.15, sd), pan=0.05, send=0.3)
        S.add(ht + 0.09, paw(0.08, sd + 20, claws=True), pan=0.08, send=0.3)
        # sofa cushion creak/squish
        n = int(0.25 * SR)
        tt = tarr(n)
        sq = bp(r.standard_normal(n), 150, 900) * np.exp(-tt / 0.06) * (1 - np.exp(-tt / 0.01))
        S.add(ht + 0.02, fade_edges(sq * 0.05), pan=0.05, send=0.3)
    S.add(40.05, fabric(0.2, [(0, 0), (0.1, 1), (0.2, 0.3)], 64, 500, 6000, 300) * 0.08, pan=0.2, send=0.3)
    S.add(40.2, flump(0.22, 65, size=1.1), pan=0.2, send=0.3)

    # ---- 48-60 morning: birds, dripping water, soft air
    amb = shaped_noise(12.0, const(900), const(1.2), seed=81, amp_fn=lambda tt: np.interp(tt, [0, 1.5, 12], [0, 1, 1]) * 0.025)
    O.add(48.0, amb, pan=0.0, send=0.2)
    bt = 48.3
    while bt < 59.3:
        side = float(r.choice([-0.65, -0.4, 0.5, 0.7]))
        dist = r.uniform(0.5, 1.0)
        for dt, c in sparrow(r):
            O.add(bt + dt, c * 0.10 * dist, pan=side, send=0.35 + 0.2 * (1 - dist))
        bt += r.uniform(0.8, 1.7)
    for bt, base in [(49.2, 4200), (52.1, 3800), (55.8, 4400), (58.1, 4000)]:
        for dt, c in warbler(r, base):
            O.add(bt + dt, c * 0.05, pan=0.75, send=0.55)
    # distant dove-ish coo (soft low FM)
    for bt in [50.6, 54.0, 57.3]:
        for k, (f0, f1, d) in enumerate([(620, 560, 0.35), (660, 520, 0.55)]):
            O.add(bt + k * 0.45, lp(chirp_fm(f0, f1, d, 6, 0.01, 0.3), 1500) * 0.035, pan=-0.75, send=0.6)
    # drips: eaves / gutter
    dt_ = 48.2
    while dt_ < 59.5:
        f0 = r.uniform(900, 1700) if r.uniform() < 0.7 else r.uniform(1800, 2600)
        S.add(dt_, drip(f0, r) * 0.16 * r.uniform(0.6, 1.0), pan=float(r.uniform(-0.5, 0.6)), send=0.45)
        dt_ += r.uniform(0.45, 1.3)

    # ---- 55.0 camera shutter + soft flash ; 55.4-56.6 polaroid eject
    S.add(55.0, shutter() * 0.16, pan=0.05, send=0.2)
    S.add(55.08, flash_whine() * 0.008, pan=0.1, send=0.2)
    S.add(55.4, polaroid(1.2) * 0.12, pan=0.12, send=0.25)
    return S, O


# ============================================================================
#                              MIX / MASTER / QA
# ============================================================================
def master(L, R, fade_out=(59.1, 60.0)):
    L = L[:N].copy()
    R = R[:N].copy()
    L, R = hp(L, 20, 2), hp(R, 20, 2)
    t = tarr(N)
    fo = np.ones(N)
    a, b = fade_out
    m = t >= a
    fo[m] = 0.5 + 0.5 * np.cos(np.pi * np.clip((t[m] - a) / (b - a), 0, 1))
    L *= fo
    R *= fo
    L -= np.mean(L)
    R -= np.mean(R)
    k = int(0.02 * SR)
    L[-k:] *= np.linspace(1, 0, k)
    R[-k:] *= np.linspace(1, 0, k)
    k = int(0.005 * SR)
    L[:k] *= np.linspace(0, 1, k)
    R[:k] *= np.linspace(0, 1, k)
    return L, R


def soft_limit(L, R, thresh=0.8, ratio=2.0):
    pk = np.maximum(np.abs(L), np.abs(R))
    win = int(0.005 * SR)
    pk = signal.convolve(pk, np.ones(win) / win, mode="same")
    over = np.maximum(pk / thresh, 1.0)
    g = 1.0 / over ** (1 - 1 / ratio)
    g = minimum_filter1d(g, int(0.04 * SR))
    sos = signal.butter(1, 8, "low", fs=SR, output="sos")
    g = signal.sosfiltfilt(sos, g)
    return L * g, R * g


def duck_vocal_band(L, R, lines, depth_db=-4.0):
    """dynamic EQ: attenuate 300-3000 Hz in the music during dialogue (zero-phase split)."""
    sos = signal.butter(2, [300, 3000], "band", fs=SR, output="sos")
    mL, mR = signal.sosfiltfilt(sos, L), signal.sosfiltfilt(sos, R)
    t = tarr(len(L))
    g = np.zeros(len(L))
    for ln in lines:
        a, b = ln["t"] - 0.15, ln["slot_end"] + 0.1
        g = np.maximum(g, np.interp(t, [a - 0.25, a, b, b + 0.35], [0, 1, 1, 0]))
    cut = 1 - 10 ** (depth_db / 20)
    return L - g * cut * mL, R - g * cut * mR


def normalize(L, R, target_db=-3.0):
    pk = max(np.max(np.abs(L)), np.max(np.abs(R)))
    g = 10 ** (target_db / 20) / pk
    return L * g, R * g


def write_wav(path, L, R):
    x = np.stack([L, R], axis=1)
    x = np.clip(np.round(x * 32767), -32768, 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(x.tobytes())


def db(x):
    return 20 * np.log10(max(x, 1e-9))


def analyze(name, L, R):
    print(f"\n== {name} ==")
    print(f"samples={len(L)} ({len(L)/SR:.3f}s)  peak={db(max(np.abs(L).max(), np.abs(R).max())):.2f} dBFS  "
          f"DC L={np.mean(L):+.2e} R={np.mean(R):+.2e}  clipped={int(np.sum(np.abs(L) >= 0.9999) + np.sum(np.abs(R) >= 0.9999))}")
    m = 0.5 * (L + R)
    rows = []
    for s in range(60):
        seg = m[s * SR:(s + 1) * SR]
        rows.append(f"{s:2d}:{db(np.sqrt(np.mean(seg ** 2))):6.1f}")
    print("RMS per second (dBFS):")
    for i in range(0, 60, 10):
        print("  " + "  ".join(rows[i:i + 10]))
    hf = hp(m, 10000, 4)
    fr = int(0.002 * SR)
    e = np.sqrt(np.mean(hf[: len(hf) // fr * fr].reshape(-1, fr) ** 2, axis=1))
    med = signal.medfilt(e, 51)
    sus = np.where((e > 12 * (med + 1e-6)) & (e > 10 ** (-60 / 20)))[0]
    print(f"HF-spike frames (possible clicks): {len(sus)}" + (f" at {np.round(sus[:15] * fr / SR, 3).tolist()}" if len(sus) else ""))
    d = np.abs(np.diff(m))
    print(f"max sample-to-sample jump = {d.max():.4f}   tail: last 50 ms max = {db(np.abs(m[-int(0.05*SR):]).max()):.1f} dBFS")


def main():
    print("composing music ...")
    P, B = compose_bgm()
    # piano: soundboard colouring + sympathetic string resonance, then the hall
    pm = 0.5 * (P.L + P.R)
    sym = sympathetic(pm) * 0.10
    P.L = soundboard(P.L) + sym
    P.R = soundboard(P.R) + sym
    ir_hall = make_ir(2.6, 2.2, 1.3, 4.0, predelay=0.022, seed=3)
    ir_room = make_ir(1.2, 1.0, 0.6, 1.8, predelay=0.012, seed=4)
    pl, pr = apply_reverb(P, ir_room)
    wl, wr = apply_reverb(B, ir_hall)
    ph_l, ph_r = apply_reverb(P, ir_hall)
    L = P.L + 0.35 * pl + 0.35 * ph_l + B.L + 0.55 * wl
    R = P.R + 0.35 * pr + 0.35 * ph_r + B.R + 0.55 * wr
    L, R = duck_vocal_band(L, R, SCRIPT["lines"], -4.0)
    L, R = master(L, R, fade_out=(59.0, 60.0))
    L, R = normalize(L, R, -1.0)
    L, R = soft_limit(L, R, 0.55)
    L, R = normalize(L, R, -3.0)
    write_wav(os.path.join(HERE, "bgm.wav"), L, R)
    bgm = (L, R)
    analyze("bgm.wav", L, R)

    print("\ndesigning sfx ...")
    S, O = compose_sfx()
    ir_room = make_ir(0.7, 0.55, 0.35, 1.2, predelay=0.006, seed=5)
    ir_out = make_ir(2.4, 1.9, 1.0, 3.5, predelay=0.03, seed=6, er=False)
    sl, sr = apply_reverb(S, ir_room)
    ol, orr = apply_reverb(O, ir_out)
    L = S.L + 0.5 * sl + O.L + 0.5 * ol
    R = S.R + 0.5 * sr + O.R + 0.5 * orr
    L, R = master(L, R, fade_out=(59.3, 60.0))
    L, R = normalize(L, R, -1.0)
    L, R = soft_limit(L, R, 0.35, ratio=3.0)
    L, R = normalize(L, R, -3.0)
    write_wav(os.path.join(HERE, "sfx.wav"), L, R)
    analyze("sfx.wav", L, R)

    mixL = 0.6 * bgm[0] + 0.8 * L
    mixR = 0.6 * bgm[1] + 0.8 * R
    analyze("preview mix 0.6*bgm + 0.8*sfx (no voice)", mixL, mixR)


if __name__ == "__main__":
    main()

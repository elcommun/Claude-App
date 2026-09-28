#!/usr/bin/env python3
"""Procedural score + sound design for the 60 s short "ほしのおとしもの".

Outputs (48 kHz / stereo / 16-bit / exactly 60.0 s):
  audio/bgm.wav  - music only
  audio/sfx.wav  - sound effects only
Everything is synthesized with numpy/scipy (no samples).  Re-run: python3 make_audio.py
"""
import json
import os
import wave

import numpy as np
from scipy import signal

SR = 48000
DUR = 60.0
N = int(round(SR * DUR))
PAD = 12 * SR                      # scratch room for tails past 60 s (cut later)
HERE = os.path.dirname(os.path.abspath(__file__))
ANIM = os.path.dirname(HERE)
SCRIPT = json.load(open(os.path.join(ANIM, "script.json"), encoding="utf-8"))
rng = np.random.default_rng(20260928)

# ----------------------------------------------------------------------------
# basic helpers
# ----------------------------------------------------------------------------
NOTE_IDX = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def nf(name):
    """'Bb4' -> Hz"""
    if isinstance(name, (int, float)):
        return float(name)
    letter = name[0]
    rest = name[1:]
    acc = 0
    while rest and rest[0] in "b#":
        acc += -1 if rest[0] == "b" else 1
        rest = rest[1:]
    midi = 12 * (int(rest) + 1) + NOTE_IDX[letter] + acc
    return 440.0 * 2 ** ((midi - 69) / 12)


def tarr(n):
    return np.arange(n) / SR


def fade_edges(x, a=0.002, r=0.01):
    """raised-cosine fade in/out so nothing starts/stops with a step."""
    n = len(x)
    na = min(n // 2, max(1, int(a * SR)))
    nr = min(n // 2, max(1, int(r * SR)))
    x[:na] *= 0.5 - 0.5 * np.cos(np.pi * np.arange(na) / na)
    x[n - nr:] *= 0.5 + 0.5 * np.cos(np.pi * np.arange(nr) / nr)
    return x


def env_points(pts, n, t0=0.0):
    """piecewise-linear envelope from [(abs_time, value), ...] sampled for n samples from t0"""
    t = t0 + tarr(n)
    ts = [p[0] for p in pts]
    vs = [p[1] for p in pts]
    return np.interp(t, ts, vs)


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
            x = x[-i:]
            i = 0
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
    sos = signal.butter(order, min(fc, SR * 0.45), "low", fs=SR, output="sos")
    return signal.sosfilt(sos, x)


def hp(x, fc, order=2):
    sos = signal.butter(order, fc, "high", fs=SR, output="sos")
    return signal.sosfilt(sos, x)


def bp(x, lo, hi, order=2):
    sos = signal.butter(order, [lo, min(hi, SR * 0.45)], "band", fs=SR, output="sos")
    return signal.sosfilt(sos, x)


# ----------------------------------------------------------------------------
# reverb: convolution with a synthesized, frequency-dependent decaying noise IR
# ----------------------------------------------------------------------------
def make_ir(rt_low, rt_mid, rt_high, length, predelay=0.02, seed=1, er=True):
    r = np.random.default_rng(seed)
    n = int(length * SR)
    t = tarr(n)
    irs = []
    for ch in range(2):
        noise = r.standard_normal(n)
        lo = lp(noise, 600, 2) * np.exp(-6.9078 * t / rt_low)
        mid = bp(noise, 600, 4000, 2) * np.exp(-6.9078 * t / rt_mid)
        hi = hp(noise, 4000, 2) * np.exp(-6.9078 * t / rt_high) * 0.6
        ir = lo + mid + hi
        # soft onset (diffusion build-up)
        ir *= 1 - np.exp(-t / 0.012)
        if er:  # a few early reflections
            for _ in range(10):
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
# instruments (all return mono float arrays)
# ----------------------------------------------------------------------------
def additive(f, partials, length, attack=0.003, vel=1.0, off=None, rel=0.15, phase_rand=True):
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
    if off is not None and off < length:
        io = int(off * SR)
        out[io:] *= np.exp(-6.9078 * (t[io:] - off) / rel)
    return fade_edges(out * vel, attack, 0.02)


def music_box(f, vel=1.0, length=None):
    T = float(np.clip(3.2 * (523.0 / f) ** 0.5, 1.2, 5.0))
    parts = [(1.0, 1.0, T), (1.0 + 0.9 / f, 0.35, T * 0.9),   # slow beating shimmer
             (2.0, 0.08, T * 0.5), (3.01, 0.22, T * 0.33),
             (5.43, 0.09, T * 0.18), (8.21, 0.04, T * 0.1), (11.9, 0.02, T * 0.06)]
    x = additive(f, parts, length or min(T * 1.1, 6.0), attack=0.0015, vel=vel)
    # tiny comb "pluck" tick
    k = int(0.004 * SR)
    tick = hp(rng.standard_normal(k), 3000) * np.hanning(k) * 0.025 * vel
    x[:k] += tick
    return x


def celesta(f, vel=1.0, length=None):
    T = float(np.clip(2.6 * (523.0 / f) ** 0.4, 1.0, 4.0))
    parts = [(1.0, 1.0, T), (1.0015, 0.3, T), (2.0, 0.3, T * 0.55), (3.0, 0.07, T * 0.35),
             (4.02, 0.05, T * 0.25), (7.1, 0.03, 0.12)]
    return additive(f, parts, length or min(T * 1.1, 5.0), attack=0.004, vel=vel)


def chime(f, vel=1.0, T=4.5, length=None):
    parts = [(0.5, 0.22, T * 1.2), (1.0, 1.0, T), (1.002, 0.4, T), (2.0, 0.45, T * 0.7),
             (2.76, 0.25, T * 0.5), (4.07, 0.16, T * 0.33), (5.43, 0.1, T * 0.22),
             (6.8, 0.06, T * 0.16)]
    return additive(f, parts, length or T * 1.1, attack=0.002, vel=vel)


def glass(f, vel=1.0, T=0.6):
    parts = [(1.0, 1.0, T), (2.32, 0.5, T * 0.6), (4.25, 0.25, T * 0.4), (6.63, 0.12, T * 0.25)]
    return additive(f, parts, T * 1.2, attack=0.0025, vel=vel)


def marimba(f, vel=1.0, T=0.6):
    parts = [(1.0, 1.0, T), (3.93, 0.3, T * 0.25), (9.2, 0.08, T * 0.08)]
    x = additive(f, parts, T * 1.1, attack=0.003, vel=vel)
    k = int(0.008 * SR)
    x[:k] += lp(rng.standard_normal(k), 1800) * np.hanning(k) * 0.04 * vel
    return x


def piano(f, dur, vel=0.6):
    """additive piano: stretched partials, two detuned strings, 2-stage decay, damper."""
    B = 0.00035
    T0 = float(np.clip(9.0 * (261.6 / f) ** 0.6, 1.5, 16.0))
    length = min(dur + 0.6, T0)
    n = int(length * SR)
    t = tarr(n)
    out = np.zeros(n)
    nmax = int(min(24, 16000 / f))
    tilt = 1.3 + 1.2 * (1 - vel)
    for k in range(1, nmax + 1):
        fk = k * f * np.sqrt(1 + B * k * k)
        a = (1.0 / k ** tilt) * (0.25 + abs(np.sin(np.pi * k * 0.12)))
        Tk = T0 / (1 + 0.22 * (k - 1) * (f / 200) ** 0.4)
        env = 0.55 * np.exp(-6.9078 * t / (Tk * 0.22)) + 0.45 * np.exp(-6.9078 * t / Tk)
        det = fk * 0.0004
        ph = rng.uniform(0, 2 * np.pi)
        out += a * env * (np.sin(2 * np.pi * (fk - det) * t + ph) + np.sin(2 * np.pi * (fk + det) * t + ph * 1.3))
    na = int(0.002 * SR)
    out[:na] *= np.linspace(0, 1, na)
    if dur < length:
        io = int(dur * SR)
        out[io:] *= np.exp(-6.9078 * (t[io:] - dur) / 0.35)
    k = int(0.012 * SR)
    out[:k] += lp(rng.standard_normal(k), 1200) * np.hanning(k) * 0.06 * vel
    return fade_edges(out * vel * 0.5, 0.002, 0.03)


def pluck(f, vel=1.0, T=2.5, bright=1.0, length=None):
    """harp / pizzicato: harmonic series with frequency-dependent damping"""
    parts = []
    nmax = int(min(30, 12000 / f))
    for k in range(1, nmax + 1):
        parts.append((k * (1 + 0.0002 * k * k), (1.0 / k ** 1.6) * bright ** (k - 1) * (0.3 + abs(np.sin(np.pi * k * 0.23))),
                      T / (1 + 0.45 * (k - 1))))
    return additive(f, parts, length or min(T * 1.1, 6.0), attack=0.003, vel=vel)


def harp(f, vel=1.0):
    return pluck(f, vel, T=float(np.clip(3.5 * (262 / f) ** 0.35, 1.2, 5)), bright=0.8)


def pizz(f, vel=1.0):
    return lp(pluck(f, vel, T=0.45, bright=0.7, length=0.5), 2500)


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


def strings(notes, t0, t1, amp_pts, cut0=2000, cut1=None, voices=5, detune=10.0, width=0.8,
            attack=0.4, release=0.8, vib=0.0035, tone="string"):
    """sustained ensemble. amp_pts: [(abs_time, amp)], cutoff crossfades cut0->cut1.
    returns stereo (L, R) starting at t0."""
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
            vr = rng.uniform(4.6, 5.8)
            vdepth = vib * np.clip(t / 1.2, 0, 1)
            drift = 1 + 0.0012 * np.sin(2 * np.pi * rng.uniform(0.1, 0.3) * t + rng.uniform(0, 6))
            finst = fv * (1 + vdepth * np.sin(2 * np.pi * vr * t + rng.uniform(0, 6))) * drift
            s = polyblep_saw(finst, rng.uniform())
            if tone == "horn":
                s = np.tanh(1.5 * s)
            p = width * ((v / max(1, voices - 1)) * 2 - 1) * (0.6 + 0.4 * ((ni % 2) * 2 - 1) * 0.5)
            gl, gr = pan_gains(p)
            L += s * gl
            R += s * gr
    norm = 1.0 / (len(notes) * voices) ** 0.5
    L *= norm
    R *= norm
    def filt(x):
        a = lp(x, cut0, 2)
        if cut1 != cut0:
            b = lp(x, cut1, 2)
            w = np.clip(t / max(1e-3, t1 - t0), 0, 1)
            a = a * (1 - w) + b * w
        return hp(a, 55, 2)
    L, R = filt(L), filt(R)
    env = env_points(amp_pts, n, t0) * pad_gain(t0)
    # attack / release shaping
    na = int(attack * SR)
    env[:na] *= 0.5 - 0.5 * np.cos(np.pi * np.arange(na) / na)
    ir = int((t1 - t0) * SR)
    nr = n - ir
    env[ir:] *= 0.5 + 0.5 * np.cos(np.pi * np.arange(nr) / nr)
    return L * env, R * env


def pad_gain(t0):
    """quiet-section string beds are lifted so the score doesn't vanish outside the climax"""
    return 3.6 if (t0 < 33.0 or t0 >= 50.0) else 1.0


def timpani(f, vel=1.0, T=2.2):
    n = int(T * 1.1 * SR)
    t = tarr(n)
    bend = 1 + 0.04 * np.exp(-t / 0.03)
    out = np.zeros(n)
    for ratio, a, tt in [(1.0, 1.0, T), (1.5, 0.45, T * 0.6), (1.99, 0.3, T * 0.45), (2.44, 0.18, T * 0.3), (2.9, 0.1, T * 0.2)]:
        ph = 2 * np.pi * np.cumsum(f * ratio * bend) / SR
        out += a * np.exp(-6.9078 * t / tt) * np.sin(ph)
    k = int(0.05 * SR)
    out[:k] += lp(rng.standard_normal(k), 400) * np.exp(-np.arange(k) / (0.012 * SR)) * 0.5
    return fade_edges(out * vel, 0.002, 0.05)


def cymbal(length, vel=1.0, T=3.0, swell=None):
    n = int(length * SR)
    t = tarr(n)
    x = bp(rng.standard_normal(n), 2500, 14000, 2) * 0.5
    for _ in range(40):
        fr = rng.uniform(2800, 9500)
        x += 0.05 * np.sin(2 * np.pi * fr * t + rng.uniform(0, 6)) * np.exp(-t / rng.uniform(0.5, 3))
    if swell is None:
        env = np.exp(-6.9078 * t / T)
        env[: int(0.003 * SR)] *= np.linspace(0, 1, int(0.003 * SR))
    else:
        env = swell
    return fade_edges(x * env * vel, 0.003, 0.05)


# ----------------------------------------------------------------------------
# time-varying filtered noise (STFT mask)
# ----------------------------------------------------------------------------
def shaped_noise(length, fc_fn, bw_oct_fn, seed=None, amp_fn=None):
    """noise with a gaussian (in octaves) spectral band whose centre/width move in time."""
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


# ============================================================================
#                                   MUSIC
# ============================================================================
def compose_bgm():
    B = Bus()
    hum = lambda s=0.006: rng.uniform(-s, s)   # humanized timing

    # ---------------------------------------------------------------- 0 - 9 s
    # Quiet wonder. F major, 3/4, 80 bpm (beat 0.75, bar 2.25). Main motif on music box.
    # MOTIF (bars):  C5 A5-- | G5 F5 E5 | F5 D6 C6 | A5---   over  F | C | Bb | F
    beat = 0.75
    m0 = 0.75
    motif = [("C5", 0, 1), ("A5", 1, 2), ("G5", 3, 1), ("F5", 4, 1), ("E5", 5, 1),
             ("F5", 6, 1), ("D6", 7, 1), ("C6", 8, 1), ("A5", 9, 3)]
    for nm, b, _ in motif:
        B.add(m0 + b * beat + hum(), music_box(nf(nm), 0.55), pan=0.15, send=0.45)
    # accompaniment: music-box broken chords in 8ths, low register
    acc = {0: ["F3", "C4", "A4", "C4", "F4", "C4"], 1: ["C3", "G3", "E4", "G3", "C4", "G3"],
           2: ["Bb2", "F3", "D4", "F3", "Bb3", "F3"], 3: ["F3", "C4", "A4", "C4", "F4", "A4"]}
    for bar in range(4):
        for i, nm in enumerate(acc[bar]):
            tt = m0 + bar * 3 * beat + i * beat / 2
            if tt >= 8.45:
                continue
            B.add(tt + hum(0.004), music_box(nf(nm), 0.22 if i else 0.3), pan=-0.35 + 0.1 * (i % 3), send=0.4)
    # a faint high twinkle on the pickup
    B.add(0.25, celesta(nf("F6"), 0.10), pan=0.5, send=0.7)
    # soft string bed (very quiet, dark)
    L, R = strings(["F2", "C3", "A3"], 0.0, 3.0, [(0, 0), (1.5, 0.05), (3, 0.05)], cut0=700, attack=1.5, release=0.6)
    B.add_st(0.0, L, R, send=0.4)
    L, R = strings(["C3", "G3", "E4"], 3.0, 5.25, [(3, 0.05), (5.25, 0.05)], cut0=750, attack=0.6, release=0.6)
    B.add_st(3.0, L, R, send=0.4)
    L, R = strings(["Bb2", "F3", "D4"], 5.25, 7.5, [(5.25, 0.05), (7.5, 0.06)], cut0=800, attack=0.6, release=0.6)
    B.add_st(5.25, L, R, send=0.4)
    # bar 4 swells with the approaching shooting star, cut under the impact flash
    L, R = strings(["F2", "C3", "A3", "F4"], 7.5, 8.5, [(7.5, 0.06), (8.45, 0.11), (8.5, 0.11)], cut0=900, cut1=1800,
                   attack=0.5, release=0.12)
    B.add_st(7.5, L, R, send=0.4)

    # --------------------------------------------------------------- 9 - 22 s
    # Tender / sad. D minor, 3/4, 75 bpm (beat 0.8, bar 2.4). Motif in minor on celesta,
    # soft low piano, dark strings.
    beat = 0.8
    s0 = 9.6
    minor = [("A4", 0), ("F5", 1), ("E5", 3), ("D5", 4), ("C#5", 5), ("D5", 6), ("Bb5", 7), ("A5", 8), ("F5", 9),
             ("D5", 12), ("C5", 13), ("Bb4", 14)]
    for nm, b in minor:
        B.add(s0 + b * beat + hum(0.01), celesta(nf(nm), 0.28), pan=0.2, send=0.5)
    # piano: bass on 1, soft chord on 2 (and 3)
    pchords = [(9.6, "D2", ["A3", "D4", "F4"]), (12.0, "A1", ["A3", "C#4", "E4"]), (14.4, "G2", ["G3", "Bb3", "D4"]),
               (16.8, "D2", ["A3", "D4", "F4"]), (19.2, "Bb1", ["F3", "Bb3", "D4"])]
    for t0, bass, ch in pchords:
        B.add(t0 + hum(), piano(nf(bass), 2.3, 0.36), pan=-0.2, send=0.35)
        for j, nm in enumerate(ch):
            B.add(t0 + beat + 0.03 * j + hum(), piano(nf(nm), 1.5, 0.22), pan=-0.1 + 0.1 * j, send=0.35)
    # 20.4 Gm, 21.2 C7 -> 22 F
    B.add(20.4, piano(nf("G2"), 0.8, 0.4), pan=-0.2, send=0.35)
    for j, nm in enumerate(["G3", "Bb3", "D4"]):
        B.add(20.4 + 0.03 * j, piano(nf(nm), 0.7, 0.2), pan=-0.1, send=0.35)
    B.add(21.2, piano(nf("C2"), 0.75, 0.42), pan=-0.2, send=0.35)
    for j, nm in enumerate(["E3", "Bb3", "C4"]):
        B.add(21.2 + 0.03 * j, piano(nf(nm), 0.7, 0.22), pan=-0.1, send=0.35)
    B.add(21.6, celesta(nf("E5"), 0.2), pan=0.2, send=0.5)
    B.add(21.8, celesta(nf("G5"), 0.22), pan=0.2, send=0.5)
    # dark strings under it
    for t0, t1, ch in [(9.0, 12.0, ["D3", "A3", "F4"]), (12.0, 14.4, ["C#3", "A3", "E4"]),
                       (14.4, 16.8, ["D3", "Bb3", "G4"]), (16.8, 19.2, ["D3", "A3", "F4"]),
                       (19.2, 21.2, ["D3", "Bb3", "F4"]), (21.2, 22.0, ["C3", "Bb3", "E4"])]:
        a = 0.055 if t0 > 9.1 else 0.0
        L, R = strings(ch, t0, t1, [(t0, a), (t0 + 0.8, 0.055), (t1, 0.055)], cut0=650,
                       attack=1.2 if t0 < 9.1 else 0.5, release=0.5)
        B.add_st(t0, L, R, send=0.45)

    # --------------------------------------------------------------- 22 - 26 s
    # Playful, bouncy staccato, F major, 120 bpm (beat 0.5)
    for i, nm in enumerate(["F2", "C3"]):
        B.add(22.0 + i * 0.5, pizz(nf(nm), 0.9), pan=-0.3, send=0.15)
    for i in range(2):
        for j, nm in enumerate(["A3", "C4", "F4"]):
            B.add(22.25 + i * 0.5 + 0.005 * j, pizz(nf(nm), 0.45), pan=0.1 * j, send=0.15)
    for tt, nm in [(22.0, "C5"), (22.25, "F5"), (22.5, "A5"), (22.625, "G5"), (22.75, "F5")]:
        B.add(tt, marimba(nf(nm), 0.5), pan=0.3, send=0.2)
    # rocket take-off: ascending 16ths 23.0-24.5, bass pumping 8ths
    up = ["F4", "G4", "A4", "Bb4", "C5", "D5", "E5", "F5", "G5", "A5", "Bb5", "C6"]
    for i, nm in enumerate(up):
        B.add(23.0 + i * 0.125, marimba(nf(nm), 0.35 + 0.3 * i / 11), pan=-0.3 + 0.6 * i / 11, send=0.2)
    for i in range(6):
        B.add(23.0 + i * 0.25, pizz(nf(["F2", "C3", "F2", "C3", "G2", "C3"][i]), 0.75), pan=-0.3, send=0.15)
        B.add(23.125 + i * 0.25, pizz(nf(["A3", "A3", "Bb3", "Bb3", "Bb3", "E4"][i]), 0.35), pan=0.2, send=0.15)
    L, R = strings(["C4", "E4", "G4", "C5"], 23.0, 24.5, [(23, 0.02), (24.45, 0.08)], cut0=1200, cut1=2500,
                   attack=0.3, release=0.15, vib=0.006)
    B.add_st(23.0, L, R, send=0.3)
    # sputter: stuttering repeated note, dropping pitch
    for tt, nm, v in [(24.5, "C6", 0.55), (24.62, "B5", 0.45), (24.8, "Bb5", 0.42), (24.88, "A5", 0.3),
                      (25.05, "Ab5", 0.25), (25.14, "G5", 0.18)]:
        B.add(tt, marimba(nf(nm), v), pan=0.3, send=0.2)
    # falling: descending chromatic run 25.2-26.0
    for i in range(12):
        f = nf("G5") * 2 ** (-i / 12)
        B.add(25.2 + i * 0.0667, pizz(f * 0.5, 0.35), pan=0.3 - 0.05 * i, send=0.2)
        B.add(25.2 + i * 0.0667, marimba(f, 0.18), pan=0.3 - 0.05 * i, send=0.2)

    # --------------------------------------------------------------- 26 - 33 s
    # bonk -> deflated, sparse (Dm); hope builds from 30.0
    B.add(26.0, pizz(nf("D2"), 1.0), pan=0, send=0.2)
    B.add(26.02, pizz(nf("A2"), 0.6), pan=0, send=0.2)
    for tt, nm in [(26.6, "A5"), (28.1, "F5"), (29.5, "D5")]:
        B.add(tt, celesta(nf(nm), 0.2), pan=0.35, send=0.6)
    L, R = strings(["D3", "A3", "F4"], 26.3, 30.0, [(26.3, 0), (27.5, 0.045), (30.0, 0.045)], cut0=550,
                   attack=1.2, release=0.6)
    B.add_st(26.3, L, R, send=0.45)
    # hope: Bb(add9) -> Gm7 -> C -> F(33.6)
    for t0, t1, ch, a0, a1, c0, c1 in [(30.0, 31.2, ["Bb2", "F3", "D4", "C5"], 0.045, 0.06, 700, 1000),
                                       (31.2, 32.4, ["G2", "F3", "Bb3", "D4"], 0.06, 0.08, 1000, 1400),
                                       (32.4, 33.6, ["C3", "G3", "Bb3", "E4"], 0.08, 0.13, 1400, 2200)]:
        L, R = strings(ch, t0, t1, [(t0, a0), (t1, a1)], cut0=c0, cut1=c1, attack=0.35, release=0.4)
        B.add_st(t0, L, R, send=0.45)
    for t0, notes in [(30.0, ["Bb1", "F2", "D3", "F3"]), (31.2, ["G1", "D2", "Bb2", "D3"]), (32.4, ["C2", "G2", "E3", "G3"])]:
        for j, nm in enumerate(notes):
            B.add(t0 + j * 0.2, piano(nf(nm), 1.2, 0.3 + 0.03 * j), pan=-0.25, send=0.35)
    # motif returns, hopeful (major), on celesta - bar 2 in 8ths leading into 33.6
    for tt, nm in [(30.0, "C5"), (30.8, "A5"), (32.4, "G5"), (32.8, "F5"), (33.2, "E5")]:
        B.add(tt + hum(), celesta(nf(nm), 0.3), pan=0.25, send=0.5)

    # --------------------------------------------------------------- 33.6 - 48 s
    # Triumphant crescendo. 3/4, beat 0.8 s = antenna pulse period; bars land exactly on 48.0.
    beat = 0.8
    chords = [  # (t0, t1, bass, chord voicing)
        (33.6, 36.0, "F2", ["F3", "C4", "A4", "F5"]),
        (36.0, 37.2, "Bb1", ["F3", "Bb3", "D4", "F4"]),
        (37.2, 38.4, "C2", ["G3", "C4", "E4", "G4"]),
        (38.4, 40.8, "F2", ["F3", "C4", "A4", "C5"]),
        (40.8, 43.2, "E2", ["G3", "C4", "E4", "G4"]),
        (43.2, 44.8, "Bb1", ["F3", "Bb3", "D4", "F4"]),
        (44.8, 45.6, "Bb1", ["F3", "Bb3", "Db4", "F4"]),
        (45.6, 47.2, "C2", ["G3", "Bb3", "D4", "F4"]),
        (47.2, 48.0, "C2", ["G3", "Bb3", "E4", "G4"]),
    ]
    def cres(t):  # overall intensity 0..1 across the climax
        return float(np.interp(t, [33.0, 38.4, 43.2, 46.0, 48.0], [0.35, 0.55, 0.72, 0.9, 1.0]))
    for t0, t1, bass, ch in chords:
        a0, a1 = cres(t0), cres(t1)
        L, R = strings(ch, t0, t1, [(t0, 0.13 * a0), (t1, 0.13 * a1)], cut0=1200 + 3500 * a0, cut1=1200 + 3500 * a1,
                       attack=0.12 if t0 > 33.7 else 0.25, release=0.25, voices=6, width=0.9)
        B.add_st(t0, L, R, send=0.4)
        # celli/basses: octave-doubled bass line
        L, R = strings([bass, nf(bass) * 2], t0, t1, [(t0, 0.12 * a0), (t1, 0.12 * a1)], cut0=500 + 700 * a0,
                       cut1=500 + 700 * a1, attack=0.1, release=0.25, voices=4, width=0.3)
        B.add_st(t0, L, R, send=0.3)
    # lead-in swell 33.0-33.6
    L, R = strings(["C3", "E3", "G3", "C4"], 33.0, 33.6, [(33.0, 0.05), (33.6, 0.1)], cut0=1500, cut1=2500,
                   attack=0.3, release=0.15)
    B.add_st(33.0, L, R, send=0.4)
    # MELODY (violins + horns an octave below + bells an octave above from 43.2)
    mel = [("C5", 38.4, 39.2), ("A5", 39.2, 40.8), ("G5", 40.8, 41.6), ("F5", 41.6, 42.4), ("E5", 42.4, 43.2),
           ("F5", 43.2, 44.0), ("D6", 44.0, 44.8), ("C6", 44.8, 45.6), ("G5", 45.6, 46.4), ("A5", 46.4, 47.2),
           ("Bb5", 47.2, 48.0)]
    for nm, t0, t1 in mel:
        a = cres(t0)
        L, R = strings([nm], t0, t1 + 0.05, [(t0, 0.16 * a), (t1, 0.17 * a)], cut0=2500 + 3000 * a,
                       attack=0.06, release=0.18, voices=5, detune=8, width=0.4, vib=0.005)
        B.add_st(t0, L, R, send=0.45)
        f = nf(nm) / 2
        L, R = strings([f], t0, t1 + 0.05, [(t0, 0.12 * a), (t1, 0.13 * a)], cut0=900 + 1500 * a,
                       attack=0.08, release=0.2, voices=3, detune=5, width=0.3, tone="horn", vib=0.003)
        B.add_st(t0, L, R, send=0.4)
        B.add(t0, celesta(nf(nm) * 2, 0.22 * a), pan=0.3, send=0.5)
    # rising arpeggios (harp): 8ths -> triplets -> 16ths -> 32nds; accelerate like the climb
    arp_tones = {
        33.6: ["F3", "A3", "C4", "F4", "A4", "C5", "F5", "C5", "A4", "F4", "C4", "A3"],
        36.0: ["Bb2", "D3", "F3", "Bb3", "D4", "F4"], 37.2: ["C3", "E3", "G3", "C4", "E4", "G4"],
        38.4: ["F3", "A3", "C4", "F4", "A4", "C5", "F5", "A5"], 40.8: ["E3", "G3", "C4", "E4", "G4", "C5", "E5", "G5"],
        43.2: ["Bb2", "D3", "F3", "Bb3", "D4", "F4", "Bb4", "D5"], 44.8: ["Bb2", "Db3", "F3", "Bb3", "Db4", "F4", "Bb4", "Db5"],
        45.6: ["C3", "G3", "Bb3", "D4", "F4", "G4", "Bb4", "D5", "F5", "G5", "Bb5", "D6"],
        47.2: ["C4", "E4", "G4", "Bb4", "C5", "E5", "G5", "Bb5", "C6", "E6"],
    }
    seg_starts = sorted(arp_tones)
    seg_ends = seg_starts[1:] + [48.0]
    for s, e in zip(seg_starts, seg_ends):
        step = 0.4 if s < 38.4 else (0.8 / 3 if s < 43.2 else (0.2 if s < 45.6 else 0.1))
        tones = arp_tones[s]
        k = 0
        tt = s
        while tt < e - 1e-6:
            nm = tones[k % len(tones)]
            v = 0.25 + 0.35 * cres(tt)
            B.add(tt + hum(0.003), harp(nf(nm), v), pan=-0.5 + 0.9 * ((k % len(tones)) / len(tones)), send=0.45)
            k += 1
            tt += step
    # antenna-pulse bells on every beat 33.6-38.4 (music side: soft celesta octaves)
    for i in range(7):
        tt = 33.6 + i * 0.8
        B.add(tt, celesta(nf(["C6", "F6", "A6", "C7", "D6", "G6", "C7"][i]), 0.14), pan=0.5, send=0.7)
    # timpani: downbeats from 38.4, roll 45.6 -> 48.0, big hit at 48.0
    for tt, nm, v in [(38.4, "F2", 0.5), (40.8, "C2", 0.55), (42.4, "C2", 0.35), (43.2, "F2", 0.65), (44.8, "F2", 0.55)]:
        B.add(tt, timpani(nf(nm), v), pan=-0.1, send=0.3)
    tt = 45.6
    while tt < 47.95:
        v = 0.12 + 0.55 * ((tt - 45.6) / 2.4) ** 1.5
        B.add(tt + hum(0.004), timpani(nf("C2"), v * rng.uniform(0.8, 1.0), T=0.9), pan=-0.1, send=0.3)
        tt += 0.075
    # suspended cymbal swell into the lock + crash
    sw_len = 2.0
    nsw = int(sw_len * SR)
    swell = (np.linspace(0, 1, nsw) ** 2.5) * (1 + 0.25 * np.sin(2 * np.pi * 14 * tarr(nsw)))
    B.add(46.0, cymbal(sw_len, 0.22, swell=swell), pan=0.2, send=0.3)

    # --------------------------------------------------------------- 48 - 55 s
    # Resolution: big F major at the lock, then warm and quiet under dialogue; bells.
    B.add(48.0, timpani(nf("F2"), 0.9, T=3.0), pan=-0.1, send=0.35)
    B.add(48.0, cymbal(4.0, 0.3, T=3.5), pan=0.25, send=0.35)
    L, R = strings(["F2", "C3", "F3", "A3", "C4", "F4", "A4", "C5", "F5"], 48.0, 50.4,
                   [(48.0, 0.22), (48.6, 0.18), (49.6, 0.17), (50.4, 0.16)], cut0=5000, cut1=1600,
                   attack=0.03, release=0.5, voices=5, width=1.0)
    B.add_st(48.0, L, R, send=0.45)
    L, R = strings(["A5"], 48.0, 49.2, [(48.0, 0.2), (48.6, 0.1), (49.2, 0.06)], cut0=5000, cut1=2500,
                   attack=0.03, release=0.8, voices=5, detune=8, width=0.4, vib=0.005)
    B.add_st(48.0, L, R, send=0.5)
    L, R = strings(["F1", "F2"], 48.0, 50.4, [(48.0, 0.2), (49.0, 0.16), (50.4, 0.15)], cut0=800,
                   attack=0.03, release=0.5, voices=4, width=0.3)
    B.add_st(48.0, L, R, send=0.35)
    for j, nm in enumerate(["F4", "A4", "C5", "F5", "A5", "C6"]):
        B.add(48.0 + 0.012 * j, chime(nf(nm), 0.18, T=4.0), pan=-0.4 + 0.16 * j, send=0.55)
    # harp gliss upward while the constellation lines draw (48.0-50.2)
    gl = ["F4", "G4", "A4", "C5", "D5", "F5", "G5", "A5", "C6", "D6", "F6", "G6", "A6", "C7"]
    for i, nm in enumerate(gl):
        B.add(48.05 + i * (2.1 / len(gl)), harp(nf(nm), 0.22 - 0.008 * i), pan=-0.5 + i / len(gl), send=0.6)
    for t0, t1, ch, bass in [(50.4, 52.8, ["F3", "A3", "C4", "E4"], "D2"), (52.8, 54.2, ["F3", "A3", "D4", "E4"], "Bb1")]:
        L, R = strings(ch, t0, t1, [(t0, 0.06), (t1, 0.06)], cut0=1400, attack=0.6, release=0.6, width=0.9)
        B.add_st(t0, L, R, send=0.45)
        L, R = strings([bass, nf(bass) * 2], t0, t1, [(t0, 0.07), (t1, 0.07)], cut0=600, attack=0.6, release=0.6,
                       voices=4, width=0.3)
        B.add_st(t0, L, R, send=0.35)
    # bells: slow, high echoes of the motif ending (G F E -> F)
    for tt, nm in [(50.4, "D6"), (51.2, "C6"), (52.0, "A5"), (52.8, "G5"), (53.6, "A5")]:
        B.add(tt, chime(nf(nm), 0.14, T=3.0), pan=0.4, send=0.6)
    for tt, nm in [(50.8, "F6"), (52.4, "C7"), (53.2, "A6")]:
        B.add(tt, music_box(nf(nm), 0.18), pan=-0.4, send=0.7)
    # whiteout 54.2-55.0: C9sus swell + shimmering celesta tremolo -> dawn
    L, R = strings(["C3", "G3", "Bb3", "D4", "F4", "G4", "D5"], 54.2, 55.0, [(54.2, 0.05), (54.95, 0.16), (55.0, 0.16)],
                   cut0=1500, cut1=4500, attack=0.3, release=0.25, width=1.0)
    B.add_st(54.2, L, R, send=0.6)
    tt = 54.2
    trem = ["G5", "C6", "D6", "F6", "G6", "C7"]
    k = 0
    while tt < 55.0:
        B.add(tt, celesta(nf(trem[k % 6]), 0.06 + 0.12 * (tt - 54.2) / 0.8), pan=((k % 2) * 2 - 1) * 0.5, send=0.7)
        k += 1
        tt += 0.066

    # --------------------------------------------------------------- 55 - 60 s
    # Dawn: warm pad + main motif on the music box, final chord fading to silence.
    L, R = strings(["F2", "C3", "A3", "F4"], 55.0, 59.3, [(55.0, 0.07), (56.0, 0.05), (58.3, 0.045), (59.3, 0.02)],
                   cut0=900, cut1=600, attack=0.15, release=0.7)
    B.add_st(55.0, L, R, send=0.5)
    for tt, nm, v in [(55.4, "C5", 0.5), (55.85, "A5", 0.55), (57.0, "G5", 0.45), (57.4, "F5", 0.42), (57.8, "E5", 0.4)]:
        B.add(tt, music_box(nf(nm), v), pan=0.15, send=0.5)
    # final chord (rolled): F3 C4 A4 F5 + sparkle
    for j, nm in enumerate(["F3", "C4", "A4", "F5"]):
        B.add(58.3 + 0.05 * j, music_box(nf(nm), 0.45 if nm == "F5" else 0.28), pan=-0.3 + 0.2 * j, send=0.55)
    B.add(58.55, music_box(nf("C7"), 0.12), pan=0.5, send=0.7)
    return B


# ============================================================================
#                                SOUND EFFECTS
# ============================================================================
def compose_sfx():
    S = Bus()      # small-room send
    Lg = Bus()     # big hall send (magic)

    # ---- night ambience 0-9: crickets + gentle wind
    amb_env = lambda tt: np.interp(tt, [0, 1.2, 8.4, 9.0], [0, 1, 1, 0])
    for ci, (fc, pan, amp, per) in enumerate([(4400, -0.6, 0.05, 0.62), (4750, 0.45, 0.035, 0.81), (4150, 0.85, 0.02, 0.55)]):
        tt = rng.uniform(0, 0.4)
        while tt < 8.9:
            n = int(0.11 * SR)
            t = tarr(n)
            g = np.zeros(n)
            for p in range(4):
                s = p * 0.026
                w = np.clip((t - s) / 0.016, 0, 1)
                g += np.where((t >= s) & (t < s + 0.016), np.sin(np.pi * w), 0)
            x = g * (np.sin(2 * np.pi * fc * t) + 0.15 * np.sin(2 * np.pi * 2 * fc * t))
            S.add(tt, fade_edges(x) * amp * amb_env(tt), pan=pan, send=0.3)
            tt += per * rng.uniform(0.85, 1.2)
    # distant cricket bed
    n = int(9.0 * SR)
    bed = bp(rng.standard_normal(n), 4000, 5200) * (0.5 + 0.5 * np.sin(2 * np.pi * 38 * tarr(n)))
    bed = bed / np.sqrt(np.mean(bed ** 2)) * 0.004 * amb_env(tarr(n))
    S.add(0.0, fade_edges(bed), pan=0.0, send=0.5)
    # wind: slow gusts, stereo decorrelated
    for seed, pan in [(11, -0.7), (12, 0.7)]:
        gust = lambda tt, s=seed: 0.012 * (0.6 + 0.4 * np.sin(2 * np.pi * 0.13 * tt + s) * np.sin(2 * np.pi * 0.07 * tt + 2 * s)) * amb_env(tt)
        w = shaped_noise(9.0, lambda tt, s=seed: 450 + 200 * np.sin(2 * np.pi * 0.11 * tt + s), const(0.9), seed=seed, amp_fn=gust)
        S.add(0.0, w, pan=pan, send=0.2)

    # ---- shooting star 4.5-8.5: rising sparkly whoosh, getting louder, travelling L->centre
    d = 4.0
    grow = lambda tt: (np.clip(tt / d, 0, 1) ** 2.2) * np.interp(tt, [0, 3.93, 4.0], [1, 1, 0.3])
    wh = shaped_noise(d, lambda tt: 700 * (9.0 ** np.clip(tt / d, 0, 1)), const(0.55), seed=21, amp_fn=lambda tt: 0.09 * grow(tt))
    panmove = np.interp(tarr(len(wh)), [0, d], [-0.75, 0.05])
    Lg.add(4.5, wh, pan=panmove, send=0.35)
    # tonal shimmer gliding up
    n = int(d * SR)
    t = tarr(n)
    fg = 900 * 2 ** (1.3 * t / d)
    ph = 2 * np.pi * np.cumsum(fg) / SR
    tone = (np.sin(ph) + 0.5 * np.sin(1.5 * ph) + 0.3 * np.sin(2.01 * ph)) * (0.6 + 0.4 * np.sin(2 * np.pi * 9 * t))
    Lg.add(4.5, fade_edges(tone * 0.02 * grow(t)), pan=np.interp(t, [0, d], [-0.75, 0.05]), send=0.5)
    # sparkles: density & level increase
    tt = 4.5
    while tt < 8.45:
        x = (tt - 4.5) / d
        Lg.add(tt, glass(rng.uniform(3000, 9000), 0.02 + 0.08 * x ** 1.5, T=rng.uniform(0.12, 0.35)),
               pan=float(np.clip(-0.75 + 0.8 * x + rng.normal(0, 0.2), -1, 1)), send=0.5)
        tt += 1.0 / (6 + 40 * x ** 1.5) * rng.uniform(0.5, 1.5)

    # ---- impact 8.5: soft magical boom + glass chime scatter
    n = int(3.0 * SR)
    t = tarr(n)
    fb = 34 + 60 * np.exp(-t / 0.12)
    boom = np.sin(2 * np.pi * np.cumsum(fb) / SR) * np.exp(-6.9 * t / 2.2)
    boom += 0.5 * lp(rng.standard_normal(n), 180) * np.exp(-t / 0.25) * 3
    boom += 0.25 * bp(rng.standard_normal(n), 200, 900) * np.exp(-t / 0.12) * 3
    Lg.add(8.5, fade_edges(boom, 0.004, 0.2) * 0.55, pan=0.0, send=0.35)
    tt = 8.5
    k = 0
    while tt < 10.6:
        x = (tt - 8.5) / 2.1
        Lg.add(tt, glass(rng.uniform(2200, 7500), 0.12 * (1 - x) ** 1.5 + 0.01, T=rng.uniform(0.3, 1.0)),
               pan=float(rng.uniform(-0.9, 0.9)), send=0.7)
        tt += 0.012 + 0.2 * x ** 2 * rng.uniform(0.5, 1.5)
        k += 1
    tail = shaped_noise(2.5, const(8000), const(0.6), seed=31, amp_fn=lambda tt: 0.03 * np.exp(-tt / 0.6))
    Lg.add(8.5, tail, pan=0.1, send=0.6)

    # ---- star glow hum 9.5-22: faint shimmering pad (D / A, fits D minor)
    d = 12.5
    n = int(d * SR)
    t = tarr(n)
    genv = np.interp(t, [0, 1.8, d - 1.8, d], [0, 1, 1, 0])
    for f, a, pan in [(587.3, 1.0, -0.4), (880.0, 0.7, 0.4), (1174.7, 0.45, -0.1), (1760.0, 0.25, 0.2)]:
        x = np.zeros(n)
        for det in (-0.6, 0.0, 0.7):
            x += np.sin(2 * np.pi * (f + det) * t + rng.uniform(0, 6))
        x *= 0.6 + 0.4 * np.sin(2 * np.pi * rng.uniform(0.2, 0.5) * t + rng.uniform(0, 6))
        Lg.add(9.5, fade_edges(x * a * 0.0045 * genv), pan=pan, send=0.6)
    sh = shaped_noise(d, const(8500), const(0.4), seed=41,
                      amp_fn=lambda tt: 0.005 * np.interp(tt, [0, 1.8, d - 1.8, d], [0, 1, 1, 0]) * (0.5 + 0.5 * np.sin(2 * np.pi * 0.4 * tt)))
    Lg.add(9.5, sh, pan=0.0, send=0.6)
    tt = 10.0
    while tt < 21.0:
        Lg.add(tt, glass(rng.uniform(4000, 8000), 0.01, T=0.3), pan=float(rng.uniform(-0.6, 0.6)), send=0.7)
        tt += rng.uniform(0.6, 1.4)

    # ---- rocket jet 23.0-25.2 (steady -> sputter -> fizzle), falling 25.2-26.0
    d = 2.2
    def jet_amp(tt):
        a = np.interp(tt, [0, 0.08, 1.5, 2.2], [0, 1, 1, 0.6])
        flutter = 0.75 + 0.25 * np.sin(2 * np.pi * 31 * tt) * np.sin(2 * np.pi * 7.3 * tt)
        gate = np.ones_like(tt)
        m = tt > 1.5   # sputtering: irregular on/off gating
        pops = [1.5, 1.62, 1.71, 1.86, 1.93, 2.05, 2.15]
        g2 = np.zeros_like(tt)
        for i, p in enumerate(pops):
            w = 0.06 - 0.004 * i
            g2 += np.exp(-0.5 * ((tt - p - w / 2) / (w / 2.5)) ** 2) * (1 - 0.1 * i)
        gate[m] = np.clip(g2[m], 0, 1)
        return 0.12 * a * flutter * gate
    jet = shaped_noise(d, lambda tt: 1000 + 400 * np.clip(tt / 1.5, 0, 1), const(1.1), seed=51, amp_fn=jet_amp)
    jet += 0.5 * shaped_noise(d, const(250), const(0.8), seed=52, amp_fn=jet_amp)
    S.add(23.0, jet, pan=0.0, send=0.2)
    # cute thruster whine
    n = int(d * SR)
    t = tarr(n)
    fw = np.interp(t, [0, 1.5, 2.2], [420, 900, 300]) * (1 + 0.02 * np.sin(2 * np.pi * 12 * t))
    wh = np.sin(2 * np.pi * np.cumsum(fw) / SR)
    wh = (wh + 0.3 * np.sign(wh) * np.abs(wh) ** 3) * jet_amp(t) / 0.12 * 0.035
    S.add(23.0, fade_edges(wh), pan=0.0, send=0.2)
    # little pops during sputter + fizzle hiss
    for p in [24.5, 24.62, 24.71, 24.86, 24.93, 25.05, 25.15]:
        k = int(0.03 * SR)
        pop = lp(rng.standard_normal(k), 1500) * np.exp(-np.arange(k) / (0.005 * SR))
        S.add(p, fade_edges(pop, 0.0005, 0.005) * 0.12, pan=float(rng.uniform(-0.2, 0.2)), send=0.2)
    fz = shaped_noise(0.5, const(6000), const(0.7), seed=53, amp_fn=lambda tt: 0.03 * np.exp(-tt / 0.12))
    S.add(25.15, fz, pan=0.0, send=0.2)
    # slide-whistle fall
    n = int(0.8 * SR)
    t = tarr(n)
    ff = 1400 * (350 / 1400) ** (t / 0.8) * (1 + 0.015 * np.sin(2 * np.pi * 6.5 * t))
    sw = np.sin(2 * np.pi * np.cumsum(ff) / SR) * np.interp(t, [0, 0.05, 0.75, 0.8], [0, 1, 1, 0.3])
    S.add(25.2, fade_edges(sw * 0.05, 0.01, 0.01), pan=np.linspace(0.3, 0.0, n), send=0.25)
    S.add(25.2, shaped_noise(0.8, lambda tt: 1500 - 1000 * tt, const(0.8), seed=54,
                             amp_fn=lambda tt: 0.02 * np.interp(tt, [0, 0.4, 0.8], [0.2, 0.7, 1])), pan=0.1, send=0.2)

    # ---- bonk 26.0: wood knock + boing ; dizzy twinkles
    n = int(0.35 * SR)
    t = tarr(n)
    knock = np.zeros(n)
    for f, a, T in [(720, 1.0, 0.05), (1850, 0.5, 0.03), (3100, 0.2, 0.02)]:
        knock += a * np.sin(2 * np.pi * f * t) * np.exp(-6.9 * t / T)
    fk = 300 * (1 + 0.6 * np.exp(-t / 0.02))
    knock += 1.2 * np.sin(2 * np.pi * np.cumsum(fk) / SR) * np.exp(-6.9 * t / 0.22)
    S.add(26.0, fade_edges(knock, 0.0008, 0.02) * 0.16, pan=0.0, send=0.25)
    n = int(1.0 * SR)
    t = tarr(n)
    fbg = 210 * (1 + 0.3 * np.exp(-t / 0.35) * np.sin(2 * np.pi * 10 * t)) * (1 + 0.1 * t)
    phb = 2 * np.pi * np.cumsum(fbg) / SR
    boing = (np.sin(phb) + 0.35 * np.sin(2 * phb) + 0.15 * np.sin(3 * phb)) * np.exp(-6.9 * t / 0.9)
    S.add(26.03, fade_edges(boing, 0.004, 0.05) * 0.08, pan=0.0, send=0.25)
    for i in range(7):
        tt = 26.4 + i * 0.32
        ang = 2 * np.pi * i / 3.5
        Lg.add(tt, glass([2637, 3136, 3520][i % 3], 0.035 * (1 - i / 9), T=0.35), pan=0.6 * np.sin(ang), send=0.35)

    # ---- magic rising 33.4-46.5
    # antenna light pulses every 0.8 s, 33.6-38.4
    for i in range(7):
        tt = 33.6 + i * 0.8
        n = int(0.9 * SR)
        t = tarr(n)
        pw = (np.sin(2 * np.pi * 1046.5 * t) + 0.5 * np.sin(2 * np.pi * 1568 * t + 1)) * np.exp(-6.9 * t / 0.7) * (1 + 0.2 * np.sin(2 * np.pi * 6 * t))
        wom = np.sin(2 * np.pi * 174.6 * t) * np.interp(t, [0, 0.04, 0.4, 0.9], [0, 1, 0.2, 0])
        Lg.add(tt, fade_edges(pw * 0.035 + wom * 0.05, 0.002, 0.05), pan=0.0, send=0.5)
    # window lights detach one by one (34.4-39.2), each: bell ping + 1.5 s airy flight
    pent = ["F5", "G5", "A5", "C6", "D6", "F6", "G6", "A6", "C7", "D7"]
    nlights = 13
    for i in range(nlights):
        tt = 34.4 + i * (4.8 / (nlights - 1))
        nm = pent[min(len(pent) - 1, int(i * 0.7) + rng.integers(0, 3))]
        p = float(rng.uniform(-0.85, 0.85))
        Lg.add(tt, chime(nf(nm), 0.05, T=1.4), pan=p, send=0.55)
        fl = shaped_noise(1.5, lambda x: 2500 * 2.5 ** (x / 1.5), const(0.5), seed=100 + i,
                          amp_fn=lambda x: 0.012 * np.sin(np.pi * np.clip(x / 1.5, 0, 1)) ** 2)
        Lg.add(tt, fl, pan=np.linspace(p, p * 0.3, len(fl)), send=0.5)
    # ascending shimmer 40-46.5 (accelerating, crescendo)
    d = 6.5
    sh_amp = lambda x: 0.05 * (np.clip(x / 6.0, 0, 1) ** 1.8) * np.interp(x, [0, 6.0, 6.5], [1, 1, 0]) + 0.004 * np.interp(x, [0, 0.8, 6.5], [0, 1, 1])
    for seed, pan in [(61, -0.6), (62, 0.6)]:
        Lg.add(40.0, shaped_noise(d, lambda x: 1500 * 6 ** ((x / d) ** 1.6), const(0.45), seed=seed, amp_fn=sh_amp), pan=pan, send=0.5)
    n = int(d * SR)
    t = tarr(n)
    for j, base in enumerate([nf("F5"), nf("A5"), nf("C6"), nf("F6")]):
        fr = base * 2 ** (1.2 * (t / d) ** 1.6)
        trem = 0.5 + 0.5 * np.sin(2 * np.pi * np.cumsum(10 + 16 * t / d) / SR + j)
        x = np.sin(2 * np.pi * np.cumsum(fr) / SR) * trem * sh_amp(t) * 0.25
        Lg.add(40.0, fade_edges(x, 0.2, 0.3), pan=(-0.6, -0.2, 0.2, 0.6)[j], send=0.6)
    tt = 40.0
    while tt < 46.3:
        x = (tt - 40.0) / 6.3
        nm = pent[min(len(pent) - 1, int(x * 7) + rng.integers(0, 3))]
        Lg.add(tt, chime(nf(nm), 0.015 + 0.03 * x, T=0.9), pan=float(rng.uniform(-0.9, 0.9)), send=0.55)
        tt += 1.0 / (3 + 12 * x ** 1.5) * rng.uniform(0.6, 1.4)

    # ---- constellation lock 48.0: big warm chime chord + sparkle tail (lines draw 48.0-50.2)
    for j, nm in enumerate(["F3", "C4", "F4", "A4", "C5", "F5", "A5", "C6"]):
        Lg.add(48.0 + 0.008 * j, chime(nf(nm), 0.1 if j > 1 else 0.13, T=5.5), pan=-0.6 + 0.17 * j, send=0.55)
    n = int(2.5 * SR)
    t = tarr(n)
    whoomp = np.sin(2 * np.pi * 87.3 * t) * np.interp(t, [0, 0.03, 0.4, 2.5], [0, 1, 0.4, 0])
    Lg.add(48.0, fade_edges(whoomp * 0.12), pan=0.0, send=0.3)
    tt = 48.02
    while tt < 50.2:
        x = (tt - 48.0) / 2.2
        nm = pent[min(len(pent) - 1, int(x * 8) + rng.integers(0, 2))]
        Lg.add(tt, glass(nf(nm) * 2, 0.03 * (1 - 0.5 * x), T=0.5), pan=float(-0.7 + 1.4 * x + rng.normal(0, 0.1)), send=0.6)
        tt += rng.uniform(0.05, 0.13)
    Lg.add(48.0, shaped_noise(3.5, const(9000), const(0.5), seed=71, amp_fn=lambda x: 0.02 * np.interp(x, [0, 0.05, 2.2, 3.5], [0, 1, 0.6, 0])),
           pan=0.0, send=0.6)
    # whiteout airy swell 54.2-55.2
    Lg.add(54.2, shaped_noise(1.2, lambda x: 3000 + 5000 * x, const(0.9), seed=81,
                              amp_fn=lambda x: 0.03 * np.interp(x, [0, 0.8, 1.2], [0, 1, 0]) ** 2), pan=0.0, send=0.6)

    # ---- dawn 55-60: birds chirp softly (+ light breeze)
    def chirp(f0, f1, dur, warble=0.0):
        n = int(dur * SR)
        t = tarr(n)
        fr = f0 * (f1 / f0) ** (t / dur) * (1 + warble * np.sin(2 * np.pi * 45 * t))
        x = np.sin(2 * np.pi * np.cumsum(fr) / SR) * np.sin(np.pi * t / dur) ** 2
        return x
    birdA = [(55.35, 0.0), (56.1, 0.0), (57.55, 0.0), (58.4, 0.0)]
    for bt, _ in birdA:
        for k in range(rng.integers(3, 6)):
            f0 = rng.uniform(3200, 3800)
            S.add(bt + k * 0.085, chirp(f0, f0 * rng.uniform(1.2, 1.4), 0.06, 0.03) * 0.03, pan=-0.55, send=0.35)
    for bt in [55.8, 56.9, 58.0, 59.0]:
        S.add(bt, chirp(4200, 2900, 0.16, 0.01) * 0.02, pan=0.6, send=0.5)
        S.add(bt + 0.2, chirp(4300, 3000, 0.12, 0.01) * 0.016, pan=0.6, send=0.5)
    br = shaped_noise(5.0, const(700), const(1.0), seed=91, amp_fn=lambda x: 0.006 * np.interp(x, [0, 1.0, 4.0, 5.0], [0, 1, 1, 0]))
    S.add(55.0, br, pan=0.0, send=0.2)
    # wink 57.0: tiny twinkle
    Lg.add(57.0, glass(nf("C7"), 0.06, T=0.5), pan=0.25, send=0.6)
    Lg.add(57.06, glass(nf("G7"), 0.045, T=0.45), pan=0.3, send=0.6)
    Lg.add(57.12, glass(nf("C8"), 0.02, T=0.3), pan=0.35, send=0.6)
    return S, Lg


# ============================================================================
#                              MIX / MASTER / QA
# ============================================================================
def master(L, R, fade_out=(59.1, 60.0)):
    L = L[:N].copy()
    R = R[:N].copy()
    L, R = hp(L, 20, 2), hp(R, 20, 2)            # remove DC / subsonics
    t = tarr(N)
    fo = np.ones(N)
    a, b = fade_out
    m = t >= a
    fo[m] = 0.5 + 0.5 * np.cos(np.pi * np.clip((t[m] - b + (b - a)) / (b - a), 0, 1))
    fo[-int(0.005 * SR):] = 0.0
    L *= fo
    R *= fo
    L -= np.mean(L)
    R -= np.mean(R)
    fo2 = np.ones(N)
    fo2[-int(0.02 * SR):] = np.linspace(1, 0, int(0.02 * SR))
    L *= fo2
    R *= fo2
    return L, R


def soft_limit(L, R, thresh=0.8):
    """gentle peak control (smooth gain computer) - keeps the climax from dominating normalisation."""
    pk = np.maximum(np.abs(L), np.abs(R))
    win = int(0.005 * SR)
    pk = signal.convolve(pk, np.ones(win) / win, mode="same")
    over = np.maximum(pk / thresh, 1.0)
    g = 1.0 / over ** 0.5                       # 2:1 above threshold
    # smooth (attack ~5ms, release ~120ms) via one-pole on reversed/forward min
    from scipy.ndimage import minimum_filter1d
    g = minimum_filter1d(g, int(0.04 * SR))
    sos = signal.butter(1, 8, "low", fs=SR, output="sos")
    g = signal.sosfiltfilt(sos, g)
    return L * g, R * g


def duck_vocal_band(L, R, lines, depth_db=-5.0):
    """dynamic EQ: attenuate 300-3000 Hz in the music during dialogue (zero-phase split)."""
    sos = signal.butter(2, [300, 3000], "band", fs=SR, output="sos")
    mL, mR = signal.sosfiltfilt(sos, L), signal.sosfiltfilt(sos, R)
    t = tarr(len(L))
    g = np.zeros(len(L))
    for ln in lines:
        a, b = ln["t"] - 0.15, ln["slot_end"] + 0.1
        g = np.maximum(g, np.interp(t, [a - 0.2, a, b, b + 0.3], [0, 1, 1, 0]))
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
    print("RMS per second (dBFS):")
    rows = []
    for s in range(60):
        seg = m[s * SR:(s + 1) * SR]
        rows.append(f"{s:2d}:{db(np.sqrt(np.mean(seg ** 2))):6.1f}")
    for i in range(0, 60, 10):
        print("  " + "  ".join(rows[i:i + 10]))
    # click detector: HF energy in 2 ms frames vs local median; also raw sample jumps
    hf = hp(m, 10000, 4)
    fr = int(0.002 * SR)
    e = np.sqrt(np.mean(hf[: len(hf) // fr * fr].reshape(-1, fr) ** 2, axis=1))
    med = signal.medfilt(e, 51)
    sus = np.where((e > 12 * (med + 1e-6)) & (e > 10 ** (-60 / 20)))[0]
    print(f"HF-spike frames (possible clicks): {len(sus)}" + (f" at {np.round(sus[:15] * fr / SR, 3).tolist()}" if len(sus) else ""))
    print(f"tail: last 50 ms max = {db(np.abs(m[-int(0.05*SR):]).max()):.1f} dBFS")


def main():
    print("composing music ...")
    B = compose_bgm()
    ir_big = make_ir(3.2, 2.7, 1.6, 4.5, predelay=0.025, seed=3)
    wl, wr = apply_reverb(B, ir_big)
    L = B.L + 0.55 * wl
    R = B.R + 0.55 * wr
    L, R = duck_vocal_band(L, R, SCRIPT["lines"], -4.5)
    L, R = master(L, R)
    L, R = normalize(L, R, -1.0)
    L, R = soft_limit(L, R, 0.6)
    L, R = normalize(L, R, -3.0)
    write_wav(os.path.join(HERE, "bgm.wav"), L, R)
    bgm = (L, R)
    analyze("bgm.wav", L, R)

    print("\ndesigning sfx ...")
    S, Lg = compose_sfx()
    ir_room = make_ir(1.0, 0.8, 0.5, 1.5, predelay=0.01, seed=5)
    ir_hall = make_ir(3.0, 2.6, 1.5, 4.0, predelay=0.02, seed=6)
    sl, sr = apply_reverb(S, ir_room)
    gl_, gr_ = apply_reverb(Lg, ir_hall)
    L = S.L + 0.5 * sl + Lg.L + 0.6 * gl_
    R = S.R + 0.5 * sr + Lg.R + 0.6 * gr_
    L, R = master(L, R)
    L, R = normalize(L, R, -1.0)
    L, R = soft_limit(L, R, 0.55)
    L, R = normalize(L, R, -3.0)
    write_wav(os.path.join(HERE, "sfx.wav"), L, R)
    analyze("sfx.wav", L, R)

    mixL = 0.5 * bgm[0] + 0.8 * L
    mixR = 0.5 * bgm[1] + 0.8 * R
    analyze("preview mix 0.5*bgm + 0.8*sfx (no voice, no ducking)", mixL, mixR)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Analisis simple de musica con numpy: tempo, pulsos, tonalidad y energia.

Uso: audio_analysis.py <archivo> [--json out.json] [--start s --dur s]
"""
import json
import subprocess
import sys

import numpy as np

SR = 22050
NOTES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
KS_MAJ = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
KS_MIN = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


def load(path, sr=SR, start=None, dur=None):
    cmd = ["ffmpeg", "-v", "error"]
    if start is not None:
        cmd += ["-ss", str(start)]
    if dur is not None:
        cmd += ["-t", str(dur)]
    cmd += ["-i", path, "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def stft_mag(y, n_fft=2048, hop=512):
    win = np.hanning(n_fft).astype(np.float32)
    n = 1 + (len(y) - n_fft) // hop
    if n <= 0:
        return np.zeros((n_fft // 2 + 1, 1)), hop
    idx = np.arange(n_fft)[None, :] + hop * np.arange(n)[:, None]
    frames = y[idx] * win
    return np.abs(np.fft.rfft(frames, axis=1)).T, hop


def onset_env(y):
    S, hop = stft_mag(y, 2048, 512)
    L = np.log1p(10 * S)
    flux = np.maximum(0, np.diff(L, axis=1)).sum(axis=0)
    flux = np.concatenate([[0], flux])
    flux = flux - np.convolve(flux, np.ones(16) / 16, mode="same")
    flux = np.maximum(flux, 0)
    if flux.max() > 0:
        flux /= flux.max()
    return flux, SR / hop


def tempo(env, fps, lo=60, hi=180):
    ac = np.correlate(env, env, mode="full")[len(env) - 1:]
    lags = np.arange(len(ac))
    bpm = 60 * fps / np.maximum(lags, 1)
    mask = (bpm >= lo) & (bpm <= hi)
    # ponderacion suave alrededor de 100 bpm
    w = np.exp(-0.5 * (np.log2(np.maximum(bpm, 1) / 100.0) / 0.9) ** 2)
    score = ac * w
    score[~mask] = 0
    lag = int(np.argmax(score))
    return 60 * fps / lag, lag


def beats(env, fps, bpm, tightness=100):
    period = 60 * fps / bpm
    n = len(env)
    score = env.copy()
    back = np.zeros(n, dtype=int) - 1
    for i in range(n):
        lo = int(i - 2 * period)
        hi = int(i - period / 2)
        if hi <= 0:
            continue
        lo = max(lo, 0)
        cand = np.arange(lo, hi)
        pen = -tightness * (np.log((i - cand) / period)) ** 2
        tot = score[cand] + pen
        j = int(np.argmax(tot))
        score[i] = env[i] + tot[j]
        back[i] = cand[j]
    # terminar en el maximo de los ultimos periodos
    tail = int(max(1, period))
    i = int(np.argmax(score[-tail:])) + n - tail
    out = []
    while i >= 0:
        out.append(i)
        i = back[i]
    return np.array(out[::-1]) / fps


def key(y):
    S, hop = stft_mag(y, 8192, 4096)
    freqs = np.fft.rfftfreq(8192, 1 / SR)
    chroma = np.zeros(12)
    valid = (freqs > 55) & (freqs < 2000)
    midi = 69 + 12 * np.log2(freqs[valid] / 440.0)
    pc = np.round(midi).astype(int) % 12
    energy = (S[valid] ** 2).sum(axis=1)
    for p, e in zip(pc, energy):
        chroma[p] += e
    chroma /= chroma.sum() + 1e-9
    best = None
    for k in range(12):
        for mode, prof in (("mayor", KS_MAJ), ("menor", KS_MIN)):
            r = np.corrcoef(chroma, np.roll(prof, k))[0, 1]
            if best is None or r > best[0]:
                best = (r, NOTES[k], mode)
    return best, chroma


def energy_profile(y, step=1.0):
    n = int(step * SR)
    return [float(20 * np.log10(np.sqrt(np.mean(y[i:i + n] ** 2)) + 1e-9)) for i in range(0, len(y) - n, n)]


def analyze(path, start=None, dur=None):
    y = load(path, start=start, dur=dur)
    env, fps = onset_env(y)
    bpm, _ = tempo(env, fps)
    bt = beats(env, fps, bpm)
    (r, k, mode), chroma = key(y)
    S, _ = stft_mag(y, 2048, 1024)
    freqs = np.fft.rfftfreq(2048, 1 / SR)
    centroid = float((S * freqs[:, None]).sum() / (S.sum() + 1e-9))
    return {
        "file": path, "dur": len(y) / SR, "bpm": round(float(bpm), 1), "key": f"{k} {mode}", "key_r": round(float(r), 2),
        "centroid_hz": round(centroid), "beats": [round(float(b), 3) for b in bt],
        "energy_db_per_s": [round(e, 1) for e in energy_profile(y)],
    }


if __name__ == "__main__":
    a = sys.argv[1:]
    start = float(a[a.index("--start") + 1]) if "--start" in a else None
    dur = float(a[a.index("--dur") + 1]) if "--dur" in a else None
    res = analyze(a[0], start, dur)
    if "--json" in a:
        json.dump(res, open(a[a.index("--json") + 1], "w"))
    print(f"{res['file'].split('/')[-1]}: {res['dur']:.1f}s  {res['bpm']} bpm  {res['key']} (r={res['key_r']})  brillo={res['centroid_hz']}Hz")
    e = res["energy_db_per_s"]
    print("energia/s:", " ".join(f"{x:.0f}" for x in e))

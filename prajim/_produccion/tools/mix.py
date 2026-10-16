#!/usr/bin/env python3
"""Mezcla musica + efectos desde una pauta JSON y normaliza a -14 LUFS / -1 dBTP.

Pauta (audio.json):
{
  "duration": 30.0,
  "music": {"file": "...mp3", "offset": 0.0, "at": 0.0, "gain_db": 0, "fade_in": 0.3, "fade_out": 1.5,
            "automation": [[t, db], ...]},           # automatizacion de volumen (dB) en tiempo de la linea
  "sfx": [{"file": "...wav", "t": 1.0, "gain_db": -6, "pitch": 0, "trim": [0, 1.5], "fade_out": 0.2,
           "pan": 0.0, "rate": 1.0}],
  "target_lufs": -14, "tp": -1.0
}
Salida: <out>_full.wav y <out>_sfx.wav (48 kHz, estereo)
"""
import json
import os
import re
import subprocess
import sys

import numpy as np

SR = 48000


def decode(path, filt=None):
    cmd = ["ffmpeg", "-v", "error", "-i", path]
    if filt:
        cmd += ["-af", filt]
    cmd += ["-ac", "2", "-ar", str(SR), "-f", "f32le", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).copy()


def db(x):
    return 10 ** (x / 20.0)


def interp_auto(n, automation, base_db=0.0):
    t = np.arange(n) / SR
    if not automation:
        return np.full(n, db(base_db), dtype=np.float32)
    ts = np.array([a[0] for a in automation], dtype=np.float64)
    vs = np.array([a[1] for a in automation], dtype=np.float64)
    return db(base_db + np.interp(t, ts, vs)).astype(np.float32)


def fade(x, fin, fout):
    n = len(x)
    if fin and fin > 0:
        k = min(n, int(fin * SR))
        x[:k] *= np.linspace(0, 1, k, dtype=np.float32)[:, None]
    if fout and fout > 0:
        k = min(n, int(fout * SR))
        # curva de coseno para un cierre musical suave
        c = (0.5 * (1 + np.cos(np.linspace(0, np.pi, k)))).astype(np.float32)
        x[n - k:] *= c[:, None]
    return x


def place(bus, clip, t):
    i = int(round(t * SR))
    if i >= len(bus):
        return
    if i < 0:
        clip = clip[-i:]
        i = 0
    k = min(len(clip), len(bus) - i)
    bus[i:i + k] += clip[:k]


def build(spec, base_dir):
    dur = spec["duration"]
    n = int(round(dur * SR))
    music = np.zeros((n, 2), np.float32)
    sfx = np.zeros((n, 2), np.float32)
    for m in ([spec["music"]] if isinstance(spec.get("music"), dict) else spec.get("music", [])):
        f = os.path.join(base_dir, m["file"]) if not m["file"].startswith("/") else m["file"]
        filt = []
        if m.get("offset"):
            filt.append(f"atrim=start={m['offset']},asetpts=PTS-STARTPTS")
        y = decode(f, ",".join(filt) if filt else None)
        at = m.get("at", 0.0)
        length = int(round((m.get("length", dur - at)) * SR))
        y = y[:length]
        if len(y) < length:
            y = np.vstack([y, np.zeros((length - len(y), 2), np.float32)])
        y = fade(y, m.get("fade_in", 0.0), m.get("fade_out", 1.0))
        tmp = np.zeros_like(music)
        place(tmp, y, at)
        g = interp_auto(n, m.get("automation"), m.get("gain_db", 0.0))
        music += tmp * g[:, None]
    for s in spec.get("sfx", []):
        f = os.path.join(base_dir, s["file"]) if not s["file"].startswith("/") else s["file"]
        filt = []
        if s.get("trim"):
            a, b = s["trim"]
            filt.append(f"atrim=start={a}:end={b},asetpts=PTS-STARTPTS")
        if s.get("pitch"):
            # afinacion tipo sampler (cambia la duracion, como un instrumento real)
            r = 2 ** (s["pitch"] / 12.0)
            filt.append(f"asetrate={int(SR * r)},aresample={SR}")
        if s.get("rate") and s["rate"] != 1.0:
            filt.append(f"atempo={s['rate']}")
        if s.get("reverse"):
            filt.append("areverse")
        if s.get("lowpass"):
            filt.append(f"lowpass=f={s['lowpass']}")
        if s.get("highpass"):
            filt.append(f"highpass=f={s['highpass']}")
        y = decode(f, ",".join(filt) if filt else None)
        y = fade(y, s.get("fade_in", 0.0), s.get("fade_out", 0.0))
        pan = s.get("pan", 0.0)
        if pan:
            y[:, 0] *= np.sqrt(0.5 * (1 - pan)) * np.sqrt(2)
            y[:, 1] *= np.sqrt(0.5 * (1 + pan)) * np.sqrt(2)
        y *= db(s.get("gain_db", 0.0))
        place(sfx, y, s["t"])
    return music, sfx


def write_wav(path, x):
    x = np.clip(x, -1.0, 1.0)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-",
                    "-c:a", "pcm_s24le", path], input=x.astype(np.float32).tobytes(), check=True)


def measure(path):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    summ = r[r.rfind("Summary:"):]
    I = float(re.search(r"I:\s+(-?[\d.]+|-inf) LUFS", summ).group(1))
    tp = re.search(r"Peak:\s+(-?[\d.]+|-inf) dBFS", summ)
    return I, float(tp.group(1)) if tp else -99.0


def limit(inp, out, ceiling_db):
    lim = db(ceiling_db)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", inp, "-af",
                    f"aresample=192000,alimiter=limit={lim:.4f}:attack=0.5:release=40:level=disabled,aresample={SR}",
                    "-c:a", "pcm_s24le", out], check=True)


def master(full, sfx, out_prefix, target=-14.0, tp_max=-1.0):
    tmp = out_prefix + "_tmp.wav"
    write_wav(tmp, full / 4.0)  # margen para medir sin recortar
    I, _ = measure(tmp)
    gain_db = target - I - 20 * np.log10(4.0)
    ceiling = tp_max - 0.6
    for _ in range(5):
        g = db(gain_db)
        pre = out_prefix + "_pre.wav"
        # pre-limitado en flotante: se escribe a 32 bits para no recortar antes del limitador
        x = full * g
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-",
                        "-c:a", "pcm_f32le", pre], input=x.astype(np.float32).tobytes(), check=True)
        limit(pre, out_prefix + "_full.wav", ceiling)
        I2, tp = measure(out_prefix + "_full.wav")
        ok_I = abs(I2 - target) <= 0.3
        ok_tp = tp <= tp_max
        if ok_I and ok_tp:
            break
        if not ok_tp:
            ceiling -= (tp - tp_max) + 0.1
        if not ok_I:
            gain_db += (target - I2)
    # version solo efectos: misma ganancia y limitador que la mezcla completa
    pre = out_prefix + "_pre.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-",
                    "-c:a", "pcm_f32le", pre], input=(sfx * db(gain_db)).astype(np.float32).tobytes(), check=True)
    limit(pre, out_prefix + "_sfx.wav", ceiling)
    for f in (tmp, pre):
        if os.path.exists(f):
            os.remove(f)
    I3, tp3 = measure(out_prefix + "_full.wav")
    Is, tps = measure(out_prefix + "_sfx.wav")
    return {"full_LUFS": I3, "full_TP": tp3, "sfx_LUFS": Is, "sfx_TP": tps, "gain_db": gain_db}


if __name__ == "__main__":
    spec_path, out_prefix = sys.argv[1], sys.argv[2]
    spec = json.load(open(spec_path))
    music, sfx = build(spec, os.path.dirname(os.path.abspath(spec_path)))
    res = master(music + sfx, sfx, out_prefix, spec.get("target_lufs", -14.0), spec.get("tp", -1.0))
    print(json.dumps(res))

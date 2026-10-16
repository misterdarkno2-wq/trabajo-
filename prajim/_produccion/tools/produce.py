#!/usr/bin/env python3
"""Produce un reel completo: cuadros (Playwright) -> mezcla de audio -> videos -> control de calidad.

Uso: produce.py <carpeta_reel> [--workers 4] [--skip-frames] [--only-audio] [--qc-only] [--frames a:b]
La carpeta del reel contiene index.html, audio.json y reel.json.
"""
import json
import math
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))           # .../prajim
SP = "/tmp/claude-0/-home-user-trabajo-/e45aeb62-b827-5979-8a06-dcd1bae0709b/scratchpad"
ENGINE = os.path.join(HERE, "..", "engine", "render_worker.js")
ENV = dict(os.environ, NODE_PATH="/opt/node22/lib/node_modules", PLAYWRIGHT_BROWSERS_PATH="/opt/pw-browsers")


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, **kw)


def render_frames(reel_dir, cfg, workers, frames_dir, rng=None):
    fps = cfg.get("fps", 30)
    total = int(round(cfg["duration"] * fps))
    a, b = rng if rng else (0, total)
    os.makedirs(frames_dir, exist_ok=True)
    chunk = math.ceil((b - a) / workers)
    procs = []
    t0 = time.time()
    for w in range(workers):
        s, e = a + w * chunk, min(b, a + (w + 1) * chunk)
        if s >= e:
            continue
        log = open(os.path.join(frames_dir, f"_w{w}.log"), "w")
        procs.append(subprocess.Popen(["node", ENGINE, os.path.join(reel_dir, "index.html"), frames_dir, str(fps), str(s), str(e)],
                                      stdout=log, stderr=subprocess.STDOUT, env=ENV))
    codes = [p.wait() for p in procs]
    if any(codes):
        for w in range(workers):
            print(open(os.path.join(frames_dir, f"_w{w}.log")).read()[-2000:])
        raise SystemExit("Fallo el render de cuadros")
    missing = [i for i in range(total) if not os.path.exists(os.path.join(frames_dir, f"f_{i:05d}.jpg"))]
    print(f"cuadros: {total} en {time.time() - t0:.0f}s; faltan {len(missing)}")
    return total


def vfilter(cfg):
    f = []
    if cfg.get("grain", 0):
        f.append(f"noise=c0s={cfg['grain']}:c0f=t")
    if cfg.get("vignette", 0):
        f.append(f"vignette=a={cfg['vignette']}")
    f.append("scale=in_color_matrix=bt601:in_range=full:out_color_matrix=bt709:out_range=tv,format=yuv420p")
    return ",".join(f)


COLOR = ["-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv"]


def encode(cfg, frames_dir, audio_full, audio_sfx):
    name = cfg["name"]
    fps = cfg.get("fps", 30)
    dur = cfg["duration"]
    out_v = os.path.join(ROOT, "videos", f"{name}.mp4")
    out_s = os.path.join(ROOT, "para_enviar", f"{name}_para_enviar.mp4")
    out_e = os.path.join(ROOT, "solo_efectos", f"{name}_solo_efectos.mp4")
    for d in (out_v, out_s, out_e):
        os.makedirs(os.path.dirname(d), exist_ok=True)
    inp = ["-framerate", str(fps), "-i", os.path.join(frames_dir, "f_%05d.jpg")]
    vf = vfilter(cfg)
    # 1) maxima calidad
    run(["ffmpeg", "-v", "error", "-y", *inp, "-i", audio_full, "-map", "0:v", "-map", "1:a", "-vf", vf,
         "-c:v", "libx264", "-profile:v", "high", "-preset", "slow", "-crf", str(cfg.get("crf", 17)),
         "-maxrate", "20M", "-bufsize", "40M", "-g", str(fps * 2), "-r", str(fps), *COLOR,
         "-c:a", "aac", "-b:a", "320k", "-ar", "48000", "-t", str(dur), "-movflags", "+faststart", out_v])
    # 2) para enviar (<30 MB) a 2 pasadas
    kbps = int(min(7500, (27.0 * 8 * 1024 * 1024 / dur - 192000) / 1000))
    log = os.path.join(frames_dir, "_2pass")
    common = ["-vf", vf, "-c:v", "libx264", "-profile:v", "high", "-preset", "slow", "-b:v", f"{kbps}k",
              "-maxrate", f"{int(kbps * 1.4)}k", "-bufsize", f"{int(kbps * 2)}k", "-g", str(fps * 2), "-r", str(fps), *COLOR,
              "-passlogfile", log]
    run(["ffmpeg", "-v", "error", "-y", *inp, *common, "-pass", "1", "-an", "-t", str(dur), "-f", "mp4", "/dev/null"])
    run(["ffmpeg", "-v", "error", "-y", *inp, "-i", audio_full, "-map", "0:v", "-map", "1:a", *common, "-pass", "2",
         "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", str(dur), "-movflags", "+faststart", out_s])
    # 3) solo efectos: mismo video de "para enviar" con el audio de efectos
    run(["ffmpeg", "-v", "error", "-y", "-i", out_s, "-i", audio_sfx, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
         "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", str(dur), "-movflags", "+faststart", out_e])
    return out_v, out_s, out_e


def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration,size,bit_rate", "-of", "json", path],
                       capture_output=True, text=True).stdout
    f = json.loads(r)["format"]
    return float(f["duration"]), int(f["size"]) / 1e6


def loudness(path):
    sys.path.insert(0, HERE)
    import mix
    return mix.measure(path)


def qc_sheet(cfg, frames_dir, out):
    from PIL import Image, ImageDraw
    fps = cfg.get("fps", 30)
    total = int(round(cfg["duration"] * fps))
    step = cfg.get("qc_step", 1.0)
    times = [round(x * step, 3) for x in range(int(cfg["duration"] / step) + 1)]
    sw, sh = 216, 384
    cols = 8
    tiles = []
    for t in times:
        i = min(total - 1, int(round(t * fps)))
        p = os.path.join(frames_dir, f"f_{i:05d}.jpg")
        if not os.path.exists(p):
            continue
        im = Image.open(p).convert("RGB").resize((sw, sh), Image.LANCZOS)
        d = ImageDraw.Draw(im)
        top, bot, side = 0.14 * sh, (1 - 0.35) * sh, 0.06 * sw
        d.rectangle([side, top, sw - side, bot], outline=(255, 40, 40), width=1)
        d.rectangle([0, sh * 0.125, sw - 1, sh * 0.875], outline=(40, 160, 255), width=1)  # recorte 3:4 del perfil
        d.text((4, sh - 14), f"{t:.1f}s", fill=(255, 255, 0))
        tiles.append(im)
    rows = math.ceil(len(tiles) / cols)
    W = Image.new("RGB", (cols * (sw + 4), rows * (sh + 4)), (30, 30, 30))
    for k, im in enumerate(tiles):
        W.paste(im, ((k % cols) * (sw + 4), (k // cols) * (sh + 4)))
    W.save(out, quality=88)
    return out


def main():
    a = sys.argv[1:]
    reel_dir = os.path.abspath(a[0])
    cfg = json.load(open(os.path.join(reel_dir, "reel.json")))
    workers = int(a[a.index("--workers") + 1]) if "--workers" in a else 4
    frames_dir = os.path.join(SP, "frames", cfg["name"])
    audio_dir = os.path.join(SP, "audio")
    os.makedirs(audio_dir, exist_ok=True)
    rng = None
    if "--frames" in a:
        x, y = a[a.index("--frames") + 1].split(":")
        rng = (int(x), int(y))
    if "--clean" in a and os.path.isdir(frames_dir):
        shutil.rmtree(frames_dir)
    if "--skip-frames" not in a and "--only-audio" not in a and "--qc-only" not in a:
        render_frames(reel_dir, cfg, workers, frames_dir, rng)
        if rng:
            return
    if "--qc-only" in a:
        print(qc_sheet(cfg, frames_dir, os.path.join(SP, "qc", f"{cfg['name']}_hoja.jpg")))
        return
    pref = os.path.join(audio_dir, cfg["name"])
    res = subprocess.run([sys.executable, os.path.join(HERE, "mix.py"), os.path.join(reel_dir, "audio.json"), pref],
                         capture_output=True, text=True)
    if res.returncode:
        print(res.stderr)
        raise SystemExit("Fallo la mezcla")
    print("mezcla:", res.stdout.strip())
    if "--only-audio" in a:
        return
    out_v, out_s, out_e = encode(cfg, frames_dir, pref + "_full.wav", pref + "_sfx.wav")
    os.makedirs(os.path.join(SP, "qc"), exist_ok=True)
    sheet = qc_sheet(cfg, frames_dir, os.path.join(SP, "qc", f"{cfg['name']}_hoja.jpg"))
    rep = {"hoja": sheet}
    for k, p in (("videos", out_v), ("para_enviar", out_s), ("solo_efectos", out_e)):
        d, mb = probe(p)
        I, tp = loudness(p)
        rep[k] = {"archivo": p, "duracion_s": round(d, 2), "MB": round(mb, 1), "LUFS": I, "TP_dBTP": tp}
    json.dump(rep, open(os.path.join(SP, "qc", f"{cfg['name']}_qc.json"), "w"), indent=1, ensure_ascii=False)
    print(json.dumps(rep, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()

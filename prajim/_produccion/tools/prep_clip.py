#!/usr/bin/env python3
"""Extrae una toma a JPG cuadro por cuadro en 1080x1920 / 30 fps con recorte 9:16 y etalonaje comun.

Uso: prep_clip.py <src.mp4> <outdir> --start S --dur D [--cx 0.5] [--cy 0.5] [--zoom 1.0]
                  [--speed 1.0] [--reverse] [--grade noche|calido|pastel|neutro|nocheazul] [--hflip]
"""
import argparse
import json
import os
import shutil
import subprocess

GRADES = {
    # etalonaje de marca: sombras ciruela, luces doradas suaves
    "calido": "eq=contrast=1.05:saturation=1.04:gamma=1.0,"
              "colorbalance=rs=0.03:gs=-0.02:bs=0.04:rm=0.01:gm=-0.01:bm=0.0:rh=0.04:gh=0.02:bh=-0.03,"
              "curves=all='0/0.025 0.5/0.51 1/0.975'",
    "pastel": "eq=contrast=0.96:saturation=0.92:gamma=1.06:brightness=0.02,"
              "colorbalance=rs=0.03:gs=0.0:bs=0.03:rh=0.03:gh=0.02:bh=-0.01,"
              "curves=all='0/0.06 0.5/0.55 1/0.98'",
    "noche": "eq=contrast=1.1:saturation=0.86:gamma=0.94:brightness=-0.03,"
             "colorbalance=rs=0.05:gs=-0.04:bs=0.08:rm=0.03:gm=-0.03:bm=0.04:rh=0.06:gh=0.02:bh=-0.06,"
             "curves=all='0/0.012 0.3/0.24 0.7/0.68 1/0.94'",
    # noche americana: dia convertido en noche azul-ciruela
    "nocheazul": "eq=contrast=1.12:saturation=0.45:gamma=0.62:brightness=-0.10,"
                 "colorbalance=rs=0.02:gs=-0.03:bs=0.12:rm=0.04:gm=-0.04:bm=0.10:rh=0.02:gh=0.0:bh=0.06,"
                 "curves=all='0/0.01 0.4/0.18 0.8/0.52 1/0.7'",
    "neutro": "null",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--start", type=float, default=0)
    ap.add_argument("--dur", type=float, required=True)
    ap.add_argument("--cx", type=float, default=0.5)
    ap.add_argument("--cy", type=float, default=0.5)
    ap.add_argument("--zoom", type=float, default=1.0)
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--reverse", action="store_true")
    ap.add_argument("--hflip", action="store_true")
    ap.add_argument("--grade", default="calido")
    ap.add_argument("--extra", default="")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--q", type=int, default=3)
    a = ap.parse_args()

    info = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                      "stream=width,height", "-of", "json", a.src], capture_output=True, text=True).stdout)
    W, H = info["streams"][0]["width"], info["streams"][0]["height"]
    # recorte 9:16 mas grande posible, con zoom y centro (cx, cy)
    if W / H > 9 / 16:
        ch = H / a.zoom
        cw = ch * 9 / 16
    else:
        cw = W / a.zoom
        ch = cw * 16 / 9
    cw, ch = int(cw) // 2 * 2, int(ch) // 2 * 2
    x = int(min(max(0, a.cx * W - cw / 2), W - cw))
    y = int(min(max(0, a.cy * H - ch / 2), H - ch))
    src_dur = a.dur * a.speed
    vf = [f"trim=duration={src_dur + 0.25}", "setpts=PTS-STARTPTS"]
    if a.reverse:
        vf.append("reverse")
    if a.speed != 1.0:
        vf.append(f"setpts=PTS/{a.speed}")
    vf.append(f"framerate=fps={a.fps}:interp_start=15:interp_end=240:scene=100")
    vf.append(f"crop={cw}:{ch}:{x}:{y}")
    if a.hflip:
        vf.append("hflip")
    vf.append("scale=1080:1920:flags=lanczos")
    vf.append(GRADES[a.grade])
    if a.extra:
        vf.append(a.extra)
    if os.path.isdir(a.out):
        shutil.rmtree(a.out)
    os.makedirs(a.out)
    n = int(round(a.dur * a.fps))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(a.start), "-i", a.src, "-vf", ",".join(vf), "-frames:v", str(n), "-q:v", str(a.q),
                    "-start_number", "0", os.path.join(a.out, "%05d.jpg")], check=True)
    got = len([f for f in os.listdir(a.out) if f.endswith(".jpg")])
    json.dump({"src": a.src, "frames": got, "fps": a.fps, "crop": [cw, ch, x, y], "grade": a.grade},
              open(os.path.join(a.out, "_info.json"), "w"))
    print(f"{os.path.basename(a.out)}: {got} cuadros, recorte {cw}x{ch}+{x}+{y} de {W}x{H}")


if __name__ == "__main__":
    main()

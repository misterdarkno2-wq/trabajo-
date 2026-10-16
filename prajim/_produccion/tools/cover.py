#!/usr/bin/env python3
"""Genera la portada (1080x1920) de un reel desde su cover.html y una vista previa del recorte 3:4 del perfil.

Uso: cover.py <carpeta_reel>
"""
import json
import os
import subprocess
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
SP = "/tmp/claude-0/-home-user-trabajo-/e45aeb62-b827-5979-8a06-dcd1bae0709b/scratchpad"
ENV = dict(os.environ, NODE_PATH="/opt/node22/lib/node_modules", PLAYWRIGHT_BROWSERS_PATH="/opt/pw-browsers")

reel = os.path.abspath(sys.argv[1])
cfg = json.load(open(os.path.join(reel, "reel.json")))
os.makedirs(os.path.join(ROOT, "portadas"), exist_ok=True)
out = os.path.join(ROOT, "portadas", f"{cfg['name']}_portada.jpg")
tmp = os.path.join(SP, "snap", f"cover_{cfg['name']}_%t.jpg")
subprocess.run(["node", os.path.join(HERE, "..", "tests", "snap.js"), os.path.join(reel, "cover.html"), "0", tmp], check=True, env=ENV)
im = Image.open(tmp.replace("%t", "0")).convert("RGB")
im.save(out, quality=95)
# vista previa: recorte central 1080x1440 (perfil) y 1080x1080
prev = im.copy()
d = ImageDraw.Draw(prev)
d.rectangle([0, 240, 1079, 1680], outline=(40, 160, 255), width=6)
d.rectangle([0, 420, 1079, 1500], outline=(255, 200, 40), width=4)
prev.resize((540, 960)).save(os.path.join(SP, "qc", f"{cfg['name']}_portada_check.jpg"), quality=85)
print(out)

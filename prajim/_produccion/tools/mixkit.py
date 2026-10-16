#!/usr/bin/env python3
"""Herramientas para buscar, verificar licencia y descargar material de Mixkit.

Uso:
  mixkit.py search <tag> [--vertical] [--pages N]   -> lista id | titulo | descripcion
  mixkit.py sheet <out.jpg> <id> [<id> ...]          -> hoja de miniaturas para elegir
  mixkit.py info <id>                                 -> licencia, resolucion, duracion
  mixkit.py get <id> <outdir>                         -> descarga 1080p (o la mayor) si es Free License
  mixkit.py music <category-url-or-tag> [--pages N]   -> lista canciones (JSON-LD)
  mixkit.py sfx <id> <outdir>                         -> descarga efecto .wav
"""
import html
import io
import json
import os
import re
import subprocess
import sys
import urllib.request

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
CACHE = os.environ.get("MIXKIT_CACHE", "/tmp/claude-0/-home-user-trabajo-/e45aeb62-b827-5979-8a06-dcd1bae0709b/scratchpad/stock/pages")
os.makedirs(CACHE, exist_ok=True)


def fetch(url, binary=False):
    key = re.sub(r"[^a-zA-Z0-9]+", "_", url)[-180:]
    path = os.path.join(CACHE, key)
    if os.path.exists(path) and not binary:
        return open(path, encoding="utf-8").read()
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    if binary:
        return data
    txt = data.decode("utf-8", "replace")
    open(path, "w", encoding="utf-8").write(txt)
    return txt


def parse_cards(t):
    out = []
    for m in re.finditer(r'data-item-grid--video-player-item-id-value="(\d+)"(.*?)class="item-grid-video-player__overlay-link"', t, re.S):
        vid, body = m.group(1), m.group(2)
        thumb = re.search(r'<img src="([^"]+)"', body)
        title = re.search(r'overlay-video-title">\s*(.*?)\s*<', body, re.S)
        desc = re.search(r'overlay-video-description">\s*(.*?)\s*<', body, re.S)
        hrefs = re.findall(r'href="(/free-stock-video/[^"]+)"', body)
        href = hrefs[-1] if hrefs else None
        out.append({
            "id": vid,
            "title": html.unescape(title.group(1)) if title else "",
            "desc": html.unescape(desc.group(1)) if desc else "",
            "thumb": thumb.group(1) if thumb else "",
            "href": href or "",
        })
    return out


def search(tag, vertical=False, pages=1):
    res = []
    for p in range(1, pages + 1):
        q = []
        if vertical:
            q.append("orientation=vertical")
        if p > 1:
            q.append(f"page={p}")
        url = f"https://mixkit.co/free-stock-video/{tag}/" + ("?" + "&".join(q) if q else "")
        try:
            t = fetch(url)
        except Exception as e:  # noqa
            print("ERR", url, e, file=sys.stderr)
            break
        cards = parse_cards(t)
        if not cards:
            break
        res += cards
    seen, uniq = set(), []
    for c in res:
        if c["id"] not in seen:
            seen.add(c["id"])
            uniq.append(c)
    return uniq


def item_page(vid):
    # La URL de un clip necesita el slug; se resuelve por la pagina de descarga o por cache de busquedas.
    idx = os.path.join(CACHE, "_index.json")
    index = json.load(open(idx)) if os.path.exists(idx) else {}
    href = index.get(str(vid))
    if not href:
        raise SystemExit(f"No conozco el slug del clip {vid}; busca primero.")
    return fetch("https://mixkit.co" + href), href


def remember(cards):
    idx = os.path.join(CACHE, "_index.json")
    index = json.load(open(idx)) if os.path.exists(idx) else {}
    for c in cards:
        if c.get("href"):
            index[c["id"]] = c["href"]
            index["thumb_" + c["id"]] = c["thumb"]
            index["title_" + c["id"]] = c["title"]
    json.dump(index, open(idx, "w"))


def info(vid):
    t, href = item_page(vid)
    lic = "?"
    m = re.search(r'data-license="(video\w+)"', t)
    if m:
        lic = m.group(1)
    else:
        if re.search(r"Restricted License", t):
            lic = "videoRestricted"
        elif re.search(r"Free License", t):
            lic = "videoFree"
    title = re.search(r"<title>(.*?)</title>", t, re.S)
    res = sorted(set(re.findall(r"(\d{3,4})x(\d{3,4})", t)))
    return {"id": vid, "license": lic, "page": "https://mixkit.co" + href,
            "title": html.unescape(title.group(1)).strip() if title else "", "dims": res[:6]}


def download(vid, outdir, quality="1080p"):
    inf = info(vid)
    if inf["license"] != "videoFree":
        raise SystemExit(f"Clip {vid} NO es Free License ({inf['license']}); no se descarga.")
    mp4 = None
    if quality == "best":
        for q in ("2160", "1080"):
            u = f"https://assets.mixkit.co/videos/{vid}/{vid}-{q}.mp4"
            try:
                urllib.request.urlopen(urllib.request.Request(u, method="HEAD", headers={"User-Agent": UA}), timeout=30)
                mp4 = u
                break
            except Exception:
                pass
        quality = "1080p"
    if not mp4:
        url = f"https://mixkit.co/free-stock-video/download/{vid}/?context=sidebar&type={quality}"
        t = fetch(url)
        m = re.search(r'data-download--modal-url-value="([^"]+)"', t)
        if not m:
            raise SystemExit("No encontre la URL de descarga para " + vid)
        mp4 = html.unescape(m.group(1))
    os.makedirs(outdir, exist_ok=True)
    out = os.path.join(outdir, f"{vid}.mp4")
    if not os.path.exists(out):
        part = out + ".part"
        for _ in range(6):
            r = subprocess.run(["curl", "-sS", "-L", "-C", "-", "--retry", "5", "--retry-delay", "2", "-A", UA, "-o", part, mp4])
            if r.returncode == 0:
                break
        os.replace(part, out)
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                            "stream=width,height,r_frame_rate:format=duration", "-of", "csv=p=0", out],
                           capture_output=True, text=True).stdout.strip().replace("\n", " ")
    print(f"{vid}\t{inf['license']}\t{probe}\t{inf['page']}")
    with open(os.path.join(outdir, "_creditos.tsv"), "a") as f:
        f.write(f"{vid}\t{inf['title']}\t{inf['license']}\t{inf['page']}\n")
    return out


def sheet(out, ids):
    from PIL import Image, ImageDraw
    idx = json.load(open(os.path.join(CACHE, "_index.json")))
    ims = []
    for vid in ids:
        u = idx.get("thumb_" + vid)
        if not u:
            continue
        try:
            im = Image.open(io.BytesIO(fetch(u, binary=True))).convert("RGB")
        except Exception:
            continue
        im.thumbnail((320, 320))
        canvas = Image.new("RGB", (330, 360), "white")
        canvas.paste(im, ((330 - im.width) // 2, 5))
        d = ImageDraw.Draw(canvas)
        d.text((6, 330), f"{vid} {idx.get('title_' + vid, '')[:40]}", fill="black")
        ims.append(canvas)
    cols = 5
    rows = (len(ims) + cols - 1) // cols
    W = Image.new("RGB", (cols * 330, max(1, rows) * 360), "white")
    for i, im in enumerate(ims):
        W.paste(im, ((i % cols) * 330, (i // cols) * 360))
    W.save(out, quality=85)
    print(out)


def music(tag, pages=1):
    res = []
    for p in range(1, pages + 1):
        url = tag if tag.startswith("http") else f"https://mixkit.co/free-stock-music/{tag}/"
        if p > 1:
            url += ("&" if "?" in url else "?") + f"page={p}"
        try:
            t = fetch(url)
        except Exception:
            break
        found = 0
        for blk in re.findall(r'<script type="application/ld\+json">(.*?)</script>', t, re.S):
            try:
                j = json.loads(blk)
            except Exception:
                continue
            for g in j.get("@graph", []):
                if g.get("@type") == "ItemList":
                    for e in g.get("itemListElement", []):
                        if e.get("@type") == "MusicRecording":
                            res.append(e)
                            found += 1
        if not found:
            break
    return res


def sfx(sid, outdir):
    os.makedirs(outdir, exist_ok=True)
    out = os.path.join(outdir, f"{sid}.wav")
    if not os.path.exists(out):
        data = fetch(f"https://assets.mixkit.co/active_storage/sfx/{sid}/{sid}.wav", binary=True)
        open(out, "wb").write(data)
    return out


if __name__ == "__main__":
    a = sys.argv[1:]
    cmd = a[0]
    if cmd == "search":
        pages = int(a[a.index("--pages") + 1]) if "--pages" in a else 1
        cards = search(a[1], "--vertical" in a, pages)
        remember(cards)
        for c in cards:
            print(f"{c['id']}\t{c['title']}\t{c['desc'][:110]}")
    elif cmd == "sheet":
        sheet(a[1], a[2:])
    elif cmd == "info":
        print(json.dumps(info(a[1]), ensure_ascii=False))
    elif cmd == "get":
        download(a[1], a[2], a[3] if len(a) > 3 else "best")
    elif cmd == "music":
        pages = int(a[a.index("--pages") + 1]) if "--pages" in a else 1
        for it in music(a[1], pages):
            mid = it["url"].split("/")[-2]
            print(f"{mid}\t{it['name']}\t{it.get('byArtist','')}\t{it.get('genre','')}\t{it.get('duration','')}\t{it.get('copyrightNotice','')}")
    elif cmd == "sfx":
        print(sfx(a[1], a[2]))


def sfx_search(tag, pages=1):
    res = []
    for p in range(1, pages + 1):
        url = f"https://mixkit.co/free-sound-effects/{tag}/" + (f"?page={p}" if p > 1 else "")
        try:
            t = fetch(url)
        except Exception:
            break
        cards = re.findall(r'data-audio-player-item-id-value="(\d+)".*?item-grid-sound-player__title[^>]*>\s*(.*?)\s*<.*?(\d+:\d+)', t, re.S)
        if not cards:
            ids = re.findall(r'data-audio-player-item-id-value="(\d+)"', t)
            titles = [html.unescape(x.strip()) for x in re.findall(r'class="item-grid-card__title"[^>]*>\s*(.*?)\s*<', t, re.S)]
            cards = [(i, titles[k] if k < len(titles) else "", "") for k, i in enumerate(ids)]
        if not cards:
            break
        res += cards
    return res


if __name__ == "__main__" and sys.argv[1] == "sfxsearch":
    for tag in sys.argv[2:]:
        for sid, title, dur in sfx_search(tag):
            print(f"{tag}\t{sid}\t{html.unescape(title)}\t{dur}")

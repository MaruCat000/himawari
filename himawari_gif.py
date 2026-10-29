#!/usr/bin/env python3
"""ひまわり(気象庁の公開タイル画像)から直近の画像を集めて、
台風などの雲の動きをアニメーションGIFにするスクリプト。

使い方:
    pip install pillow
    python himawari_gif.py                # 赤外画像、直近6時間
    python himawari_gif.py --band color   # 自然色(昼間のみきれいに見える)
    python himawari_gif.py --frames 72    # 直近12時間

出典: 気象庁ホームページ(ひまわり画像)
"""
import argparse
import io
import json
import math
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta

from PIL import Image, ImageDraw

BASE = "https://www.jma.go.jp/bosai/himawari/data/satimg"
TILE = 256
BANDS = {
    "ir": ("B13", "TBB"),      # 赤外(夜も見える。雲が白いほど雲頂が高い)
    "color": ("REP", "ETC"),   # 自然色(昼間のみ)
}


def fetch(url, retries=2):
    req = urllib.request.Request(url, headers={"User-Agent": "himawari-gif-sample/1.0"})
    for i in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(1)
        except urllib.error.URLError:
            time.sleep(1)
    return None


def lonlat_to_tile(lon, lat, z):
    n = 2 ** z
    x = (lon + 180.0) / 360.0 * n
    y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    return int(x), int(y)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--band", choices=BANDS, default="ir")
    ap.add_argument("--frames", type=int, default=36, help="10分間隔のコマ数")
    ap.add_argument("--zoom", type=int, default=5)
    ap.add_argument("--lon", type=float, nargs=2, default=[120, 150], metavar=("W", "E"))
    ap.add_argument("--lat", type=float, nargs=2, default=[45, 15], metavar=("N", "S"))
    ap.add_argument("--out", default="typhoon.gif")
    args = ap.parse_args()

    band, prod = BANDS[args.band]
    x0, y0 = lonlat_to_tile(args.lon[0], args.lat[0], args.zoom)
    x1, y1 = lonlat_to_tile(args.lon[1], args.lat[1], args.zoom)

    times = json.loads(fetch(f"{BASE}/targetTimes_fd.json") or b"[]")
    if not times:
        raise SystemExit("時刻リストを取得できませんでした(ネットワークを確認してください)")
    times = sorted(times, key=lambda t: t["validtime"])[-args.frames:]

    frames = []
    for t in times:
        b, v = t["basetime"], t["validtime"]
        w, h = (x1 - x0 + 1) * TILE, (y1 - y0 + 1) * TILE
        canvas = Image.new("RGB", (w, h), (40, 40, 40))
        for ix, x in enumerate(range(x0, x1 + 1)):
            for iy, y in enumerate(range(y0, y1 + 1)):
                data = fetch(f"{BASE}/{b}/fd/{v}/{band}/{prod}/{args.zoom}/{x}/{y}.jpg")
                if data:
                    canvas.paste(Image.open(io.BytesIO(data)).convert("RGB"), (ix * TILE, iy * TILE))
        jst = datetime.strptime(v, "%Y%m%d%H%M%S") + timedelta(hours=9)
        d = ImageDraw.Draw(canvas)
        d.rectangle((0, 0, 250, 22), fill=(0, 0, 0))
        d.text((6, 5), jst.strftime("%Y-%m-%d %H:%M JST") + "  Himawari / JMA", fill=(255, 255, 255))
        frames.append(canvas)
        print("OK", v)

    frames[0].save(args.out, save_all=True, append_images=frames[1:], duration=150, loop=0, optimize=True)
    print("saved:", args.out, f"({len(frames)} frames)")


if __name__ == "__main__":
    main()

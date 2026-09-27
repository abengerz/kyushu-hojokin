# -*- coding: utf-8 -*-
"""japan.geojson から九州・沖縄8県の簡略地図（SVGパス）を作り data/kyushu_map.json に保存する。
   生成物はリポジトリにコミットするので、通常のビルドではこのスクリプトは不要。"""
import json, math, os, urllib.request, sys

SRC = "https://raw.githubusercontent.com/dataofjapan/land/master/japan.geojson"
ROOT = os.path.dirname(os.path.abspath(__file__))
CACHE = os.environ.get("JAPAN_GEOJSON", os.path.join(ROOT, ".cache_japan.geojson"))
PREFS = [("fukuoka","福岡県"),("saga","佐賀県"),("nagasaki","長崎県"),("kumamoto","熊本県"),
         ("oita","大分県"),("miyazaki","宮崎県"),("kagoshima","鹿児島県"),("okinawa","沖縄県")]

# 鹿児島の南西諸島・沖縄の先島は本体から遠いので、主要域だけを切り出す
CLIP = {"鹿児島県": (128.0, 130.9, 30.2, 32.4),   # lon_min, lon_max, lat_min, lat_max
        "沖縄県":   (127.2, 128.5, 26.0, 26.95)}  # 沖縄本島まわり

def load():
    if not os.path.exists(CACHE):
        print("downloading japan.geojson ...", file=sys.stderr)
        urllib.request.urlretrieve(SRC, CACHE)
    return json.load(open(CACHE, encoding="utf-8"))

def rings(geom):
    t, c = geom["type"], geom["coordinates"]
    return [p[0] for p in c] if t == "MultiPolygon" else [c[0]]

def area(r):
    s = 0.0
    for i in range(len(r)-1):
        s += r[i][0]*r[i+1][1] - r[i+1][0]*r[i][1]
    return abs(s)/2

def rdp(pts, eps):
    if len(pts) < 3: return pts
    if pts[0] == pts[-1]:            # 閉リングは始点==終点で距離が常に0になり潰れる
        i = max(range(1, len(pts)-1),
                key=lambda k: (pts[k][0]-pts[0][0])**2 + (pts[k][1]-pts[0][1])**2)
        a = rdp(pts[:i+1], eps); b = rdp(pts[i:], eps)
        return a[:-1] + b
    x0,y0 = pts[0]; x1,y1 = pts[-1]
    dx,dy = x1-x0, y1-y0
    n = math.hypot(dx,dy) or 1e-12
    imax, dmax = 0, 0.0
    for i in range(1, len(pts)-1):
        px,py = pts[i]
        d = abs(dy*px - dx*py + x1*y0 - y1*x0) / n
        if d > dmax: imax, dmax = i, d
    if dmax > eps:
        return rdp(pts[:imax+1], eps)[:-1] + rdp(pts[imax:], eps)
    return [pts[0], pts[-1]]

def clip_ok(ring, box):
    if not box: return True
    lo1,lo2,la1,la2 = box
    cx = sum(p[0] for p in ring)/len(ring); cy = sum(p[1] for p in ring)/len(ring)
    return lo1 <= cx <= lo2 and la1 <= cy <= la2

def collect(feat, name):
    box = CLIP.get(name)
    rs = [r for r in rings(feat["geometry"]) if clip_ok(r, box)]
    if not rs: rs = rings(feat["geometry"])
    rs.sort(key=area, reverse=True)
    biggest = area(rs[0])
    keep = [r for r in rs if area(r) >= biggest*0.004][:28]
    return keep

def project(lon, lat, lat0):
    return lon*math.cos(math.radians(lat0)), -lat

def to_path(polys, sx, sy, ox, oy, nd=1):
    out = []
    for r in polys:
        pts = [(round((x-ox)*sx, nd), round((y-oy)*sy, nd)) for x, y in r]
        ded = [pts[0]]
        for p in pts[1:]:
            if p != ded[-1]: ded.append(p)
        if len(ded) < 3: continue
        out.append("M" + " L".join(f"{x} {y}" for x, y in ded) + "Z")
    return "".join(out)

def main():
    gj = load()
    by = {f["properties"]["nam_ja"]: f for f in gj["features"]}
    raw = {}
    for slug, name in PREFS:
        polys = collect(by[name], name)
        lat0 = 32.5 if name != "沖縄県" else 26.4
        eps = 0.004 if name != "沖縄県" else 0.003
        simp = []
        for r in polys:
            p = [project(x, y, lat0) for x, y in r]
            p = rdp(p, eps)
            if len(p) >= 4: simp.append(p)
        raw[slug] = simp

    out = {"main": {}, "okinawa": {}, "thumbs": {}, "labels": {}}

    # --- 本土7県を共通座標系に ---
    main_slugs = [s for s, n in PREFS if s != "okinawa"]
    pts = [p for s in main_slugs for r in raw[s] for p in r]
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    W, H = 300.0, 380.0
    sc = min(W/(max(xs)-min(xs)), H/(max(ys)-min(ys)))
    ox, oy = min(xs), min(ys)
    padx = (W-(max(xs)-min(xs))*sc)/2
    for s in main_slugs:
        out["main"][s] = to_path(raw[s], sc, sc, ox-padx/sc, oy)
        pts_s = [p for r in raw[s] for p in r]
        # ラベルは最大ポリゴンの重心（面積重心に近い代表点）
        big = max(raw[s], key=area)
        cx = sum(p[0] for p in big)/len(big); cy = sum(p[1] for p in big)/len(big)
        out["labels"][s] = [round((cx-(ox-padx/sc))*sc, 1), round((cy-oy)*sc, 1)]
    out["main"]["viewBox"] = f"0 0 {W:.0f} {H:.0f}"

    # --- 沖縄は別枠 ---
    pts = [p for r in raw["okinawa"] for p in r]
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    w, h = 130.0, 96.0
    sc2 = min(w/(max(xs)-min(xs)), h/(max(ys)-min(ys)))
    padx = (w-(max(xs)-min(xs))*sc2)/2; pady = (h-(max(ys)-min(ys))*sc2)/2
    out["okinawa"]["path"] = to_path(raw["okinawa"], sc2, sc2, min(xs)-padx/sc2, min(ys)-pady/sc2)
    out["okinawa"]["viewBox"] = f"0 0 {w:.0f} {h:.0f}"

    # --- 県ごとのサムネイル（100x100 に正規化） ---
    for s, n in PREFS:
        pts = [p for r in raw[s] for p in r]
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        sc3 = min(88/(max(xs)-min(xs)), 88/(max(ys)-min(ys)))
        px = (100-(max(xs)-min(xs))*sc3)/2; py = (100-(max(ys)-min(ys))*sc3)/2
        out["thumbs"][s] = to_path(raw[s], sc3, sc3, min(xs)-px/sc3, min(ys)-py/sc3)

    fp = os.path.join(ROOT, "data", "kyushu_map.json")
    json.dump(out, open(fp, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("wrote", fp, os.path.getsize(fp), "bytes")
    for s, n in PREFS:
        print(f"  {n}: {len(raw[s])} polygons, {sum(len(r) for r in raw[s])} points")

if __name__ == "__main__":
    main()

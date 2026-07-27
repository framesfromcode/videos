# -*- coding: utf-8 -*-
"""
montage.py — the exact script that rendered the opening montage of
"I Make YouTube Videos With No Editor, No AI Video Tools, and $0"
(FramesFromCode, episode 01).

Four scenes + a 2x2 replay grid, drawn frame by frame with numpy + Pillow and
piped straight into FFmpeg. No editor. No AI image/video tools. No stock
assets. Everything you see — the terrain, the sea, the aurora, the smoke, the
light — is computed below.

Requirements: Python 3.10+, `pip install numpy pillow`, and ffmpeg on PATH.
Run:          python montage.py            -> montage.mp4 (1920x1080, 30 fps)
Try:          python montage.py --proxy    -> fast 640x360 draft

Scene durations are locked to the episode's narration (audio-first workflow:
the voice is measured first, the pictures are born fitting). Change SCENES,
CITIES, WORDS, or any color below — the code adapts. That's the point.

License: MIT for this script. Fonts in ./fonts are SIL OFL 1.1 (license files
included). Have fun, break it, make it yours.
"""

from __future__ import annotations

import argparse
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ----------------------------------------------------------------- constants
HERE = Path(__file__).resolve().parent
FPS = 30
DESIGN_W, DESIGN_H = 1920, 1080          # all coordinates are designed at 1080p

# FramesFromCode palette — one source of truth, shared by every scene.
BG = (13, 17, 23)        # editor-dark canvas
INK = (230, 237, 243)    # near-white text
GREEN = (63, 185, 80)    # "it runs"
CYAN = (88, 166, 255)    # technical accent
AMBER = (210, 153, 34)   # warning / cost

# Scene layout, seconds. Locked to episode-01 narration windows.
SCENES = [
    ("map", 4.62),
    ("chart", 1.95),
    ("type", 2.74),
    ("smoke", 3.95),
    ("grid", 7.78),
]
BADGE_AT = 1.15          # seconds into "grid": the $0 badge pops ("zero dollars")

# The night map: a fictional coast. Rename or move the cities — it all redraws.
CITIES = [("NORDVIK", 330, 800), ("HAVRE", 610, 640), ("CALDERA", 890, 520),
          ("VELUNA", 1180, 430), ("ORSK", 1450, 330), ("MERIDIAN", 1700, 235)]
COAST = [(-80, 1040), (140, 880), (300, 900), (470, 740), (620, 700),
         (780, 560), (950, 585), (1120, 470), (1310, 420), (1470, 300),
         (1650, 300), (1810, 170), (2000, 120)]

WORDS = ["ON", "THE", "BEAT", "EXACTLY"]


def font(name: str, px: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(HERE / "fonts" / name), max(8, int(px)))


# ------------------------------------------------------------------- easing
def clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


def ease_out_cubic(t: float) -> float:
    t = clamp01(t)
    return 1 - (1 - t) ** 3


def ease_io(t: float) -> float:
    t = clamp01(t)
    return 4 * t ** 3 if t < 0.5 else 1 - ((-2 * t + 2) ** 3) / 2


def ease_out_back(t: float, k: float = 1.70158) -> float:
    t = clamp01(t)
    return 1 + (k + 1) * ((t - 1) ** 3) + k * ((t - 1) ** 2)


def seg(t: float, t0: float, t1: float) -> float:
    """Normalize absolute t into [0,1] across [t0,t1]."""
    return clamp01((t - t0) / (t1 - t0)) if t1 > t0 else 1.0


# ------------------------------------------------------- procedural texture
def _vnoise(h: int, w: int, cell: int, rng: np.random.Generator) -> np.ndarray:
    """Bilinear value noise, one octave."""
    gh, gw = h // cell + 2, w // cell + 2
    g = rng.uniform(0, 1, (gh, gw))
    ys = np.linspace(0, gh - 1.001, h)
    xs = np.linspace(0, gw - 1.001, w)
    y0, x0 = ys.astype(int), xs.astype(int)
    fy, fx = (ys - y0)[:, None], (xs - x0)[None, :]
    fy, fx = fy * fy * (3 - 2 * fy), fx * fx * (3 - 2 * fx)   # smoothstep
    a = g[y0][:, x0]
    b = g[y0][:, x0 + 1]
    c = g[y0 + 1][:, x0]
    d = g[y0 + 1][:, x0 + 1]
    return a * (1 - fy) * (1 - fx) + b * (1 - fy) * fx + c * fy * (1 - fx) + d * fy * fx


def fbm(h: int, w: int, seed: int, octaves: int = 5, base_cell: int = 320) -> np.ndarray:
    """Fractal noise in [0,1] — terrain, sea, clouds all come from this."""
    rng = np.random.default_rng(seed)
    acc = np.zeros((h, w))
    amp, tot = 1.0, 0.0
    cell = base_cell
    for _ in range(octaves):
        acc += amp * _vnoise(h, w, max(2, cell), rng)
        tot += amp
        amp *= 0.5
        cell //= 2
    return acc / tot


def glow_layer(mask: Image.Image, radius: float, color: tuple,
               strength: float = 1.0) -> np.ndarray:
    """Blurred mask -> float RGB glow array (additive)."""
    g = np.asarray(mask.filter(ImageFilter.GaussianBlur(radius)),
                   dtype=np.float32) / 255.0 * strength
    return g[..., None] * np.array(color, dtype=np.float32)


def to_img(arr: np.ndarray) -> Image.Image:
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")


_VIGNETTE: dict[tuple, np.ndarray] = {}


def vignette(size: tuple, power: float = 0.55) -> np.ndarray:
    if size not in _VIGNETTE:
        w, h = size
        yy, xx = np.mgrid[0:h, 0:w]
        r = np.sqrt(((xx / w - 0.5) * 2.1) ** 2 + ((yy / h - 0.5) * 2.1) ** 2)
        _VIGNETTE[size] = (1 - np.clip(r - 0.55, 0, 1) * power)[..., None]
    return _VIGNETTE[size]


_GRAIN: dict[tuple, list[np.ndarray]] = {}


def grain(size: tuple, fi: int, amount: float = 5.0) -> np.ndarray:
    """4-frame looping film grain."""
    if size not in _GRAIN:
        rng = np.random.default_rng(99)
        _GRAIN[size] = [rng.standard_normal((size[1], size[0], 1)) * amount
                        for _ in range(4)]
    return _GRAIN[size][fi % 4]


def catmull_rom(pts: list, samples: int = 24) -> list:
    if len(pts) < 3:
        return pts
    ext = [pts[0]] + pts + [pts[-1]]
    out = []
    for i in range(len(ext) - 3):
        p0, p1, p2, p3 = ext[i], ext[i + 1], ext[i + 2], ext[i + 3]
        for j in range(samples):
            t = j / samples
            t2, t3 = t * t, t * t * t
            out.append((
                0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t
                       + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                       + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3),
                0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t
                       + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                       + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3),
            ))
    out.append(pts[-1])
    return out


def polyline_progress(pts: list, p: float) -> list:
    if p >= 1.0 or len(pts) < 2:
        return pts
    segs = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    target, acc, out = p * sum(segs), 0.0, [pts[0]]
    for i, L in enumerate(segs):
        if acc + L >= target:
            f = (target - acc) / L if L else 0.0
            a, b = pts[i], pts[i + 1]
            out.append((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f))
            return out
        out.append(pts[i + 1])
        acc += L
    return out


# ================================================== scene 1: THE NIGHT MAP
# A dark cartographic painting: shaded terrain, deep sea, a glowing coast,
# and a route that draws itself from beacon to beacon.
_MAP_CACHE: dict[tuple, dict] = {}
_OVERSCAN = 1.12                       # headroom for the slow camera push


def _map_static(size: tuple) -> dict:
    if size in _MAP_CACHE:
        return _MAP_CACHE[size]
    w, h = size
    bw, bh = int(w * _OVERSCAN), int(h * _OVERSCAN)
    sx, sy = bw / DESIGN_W, bh / DESIGN_H
    # --- land mask from the coast polygon (everything above-right is land)
    coast = catmull_rom([(x * sx, y * sy) for x, y in COAST], 18)
    land_poly = coast + [(bw + 80, -80), (-80, -80)] if False else \
        coast + [(bw + 120, bh + 120), (bw + 120, -120), (-120, -120)]
    mask_im = Image.new("L", (bw, bh), 0)
    ImageDraw.Draw(mask_im).polygon(land_poly, fill=255)
    land = np.asarray(mask_im.filter(ImageFilter.GaussianBlur(3)),
                      dtype=np.float32) / 255.0
    # --- terrain: fbm elevation + hillshade lit from the north-west
    elev = fbm(bh, bw, seed=7, octaves=6, base_cell=int(360 * sx))
    gy, gx = np.gradient(elev)
    shade = np.clip(0.62 + (gx * -1.2 + gy * -0.8) * 26.0, 0.2, 1.2)
    lo = np.array((22, 32, 29), np.float32)
    hi = np.array((66, 82, 66), np.float32)
    land_rgb = (lo + (hi - lo) * (elev ** 1.1)[..., None]) * shade[..., None]
    ridge = np.clip(elev - 0.72, 0, 1) * 3.0
    land_rgb += ridge[..., None] * np.array((26, 22, 12), np.float32)   # amber ridgelights
    # --- sea: deep navy, brighter toward the coast, faint current bands
    sea_n = fbm(bh, bw, seed=11, octaves=4, base_cell=int(300 * sx))
    depth = np.clip(1.0 - land, 0, 1)
    coast_prox = np.asarray(mask_im.filter(ImageFilter.GaussianBlur(int(60 * sx))),
                            dtype=np.float32) / 255.0
    sea_lo = np.array((7, 12, 22), np.float32)
    sea_hi = np.array((16, 30, 48), np.float32)
    sea_rgb = sea_lo + (sea_hi - sea_lo) * (0.35 + 0.65 * coast_prox)[..., None]
    sea_rgb += (sea_n[..., None] - 0.5) * np.array((6, 9, 12), np.float32)
    base = sea_rgb * (1 - land[..., None]) + land_rgb * land[..., None]
    # --- coastline glow (cold cyan rim — "the map is lit")
    edge_im = Image.new("L", (bw, bh), 0)
    ImageDraw.Draw(edge_im).line(coast, fill=255, width=max(2, int(3 * sx)))
    base += glow_layer(edge_im, 14 * sx, (30, 80, 110), 0.9)
    base += glow_layer(edge_im, 3 * sx, (120, 200, 235), 0.55)
    # --- shallow shelf: bright turquoise hugging the coast (satellite look)
    shelf = np.clip(coast_prox - land, 0, 1) ** 1.6
    base += shelf[..., None] * np.array((14, 42, 48), np.float32)
    # --- two shimmer phases for living water
    shim = []
    for seed in (21, 22):
        s_ = fbm(bh, bw, seed=seed, octaves=3, base_cell=int(140 * sx))
        shim.append(((np.clip(s_ - 0.62, 0, 1) * 2.2)[..., None]
                     * np.array((10, 18, 26), np.float32)) * depth[..., None])
    # --- night-satellite city lights: a warm core + sprawl along the roads
    rngc = np.random.default_rng(41)
    roads_im = Image.new("L", (bw, bh), 0)
    rdd = ImageDraw.Draw(roads_im)
    ctr = [(x * sx, y * sy) for _, x, y in CITIES]
    for a, b in zip(ctr, ctr[1:]):
        rdd.line([a, b], fill=110, width=max(1, int(2 * sx)))
    lights_im = Image.new("L", (bw, bh), 0)
    ldd = ImageDraw.Draw(lights_im)
    for ci, (cx0, cy0) in enumerate(ctr):
        n_pts = 150 + int(rngc.integers(0, 80))
        pts = rngc.normal(0, 26 * sx, (n_pts, 2)) + (cx0, cy0)
        for px_, py_ in pts:
            r = rngc.uniform(0.7, 2.0) * sx
            ldd.ellipse([px_ - r, py_ - r, px_ + r, py_ + r],
                        fill=int(rngc.uniform(90, 220)))
        nxt = ctr[ci + 1] if ci + 1 < len(ctr) else None
        if nxt:                                   # sprawl strings toward the road
            for f_ in rngc.uniform(0.05, 0.5, 40):
                jx = cx0 + (nxt[0] - cx0) * f_ + rngc.normal(0, 7 * sx)
                jy = cy0 + (nxt[1] - cy0) * f_ + rngc.normal(0, 7 * sx)
                r = rngc.uniform(0.6, 1.4) * sx
                ldd.ellipse([jx - r, jy - r, jx + r, jy + r],
                            fill=int(rngc.uniform(60, 150)))
    base += glow_layer(roads_im, 2.5 * sx, (60, 48, 26), 0.5)
    base += glow_layer(lights_im, 6 * sx, (120, 84, 30), 0.9)
    base += glow_layer(lights_im, 1.2 * sx, (255, 214, 140), 0.85)
    # --- drifting cloud deck with soft ground shadows (sells "satellite")
    cl = fbm(bh, bw, seed=55, octaves=4, base_cell=int(420 * sx))
    cloud = np.clip(cl - 0.60, 0, 1) * 2.6
    # --- cartographic dressing: compass rose + graticule arcs, very faint
    dress = Image.new("L", (bw, bh), 0)
    dd = ImageDraw.Draw(dress)
    cx, cy, r0 = bw * 0.115, bh * 0.82, 72 * sx
    for rr in (r0, r0 * 0.62):
        dd.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=90,
                   width=max(1, int(2 * sx)))
    for k in range(8):
        a = k * math.pi / 4
        r1 = r0 * (1.28 if k % 2 == 0 else 1.05)
        dd.line([(cx, cy), (cx + math.cos(a) * r1, cy + math.sin(a) * r1)],
                fill=110, width=max(1, int(2 * sx)))
    for k in range(1, 4):                      # graticule: long faint arcs
        dd.arc([-bw * 0.6 + k * bw * 0.34, -bh * 0.8, bw * 1.2 + k * bw * 0.2,
                bh * 1.6], 220, 340, fill=36, width=max(1, int(2 * sx)))
    base += (np.asarray(dress, np.float32) / 255.0)[..., None] \
        * np.array((70, 84, 96), np.float32) * 0.5
    route = catmull_rom([(x * sx, y * sy) for _, x, y in CITIES], 26)
    _MAP_CACHE[size] = {"base": base, "shim": shim, "route": route,
                        "cloud": cloud, "bw": bw, "bh": bh, "sx": sx, "sy": sy}
    return _MAP_CACHE[size]


def scene_map(t: float, dur: float, size: tuple) -> Image.Image:
    w, h = size
    st = _map_static(size)
    bw, bh, sx, sy = st["bw"], st["bh"], st["sx"], st["sy"]
    fade = ease_out_cubic(seg(t, 0.0, 0.9))
    ph = t * 1.1
    arr = st["base"] + st["shim"][0] * (0.5 + 0.5 * math.sin(ph)) \
        + st["shim"][1] * (0.5 + 0.5 * math.cos(ph * 0.8))
    # cloud deck drifts east; its shadow crawls on the ground below
    dx = int(t * 26 * sx)
    cloud = np.roll(st["cloud"], dx, axis=1)
    shadow = np.roll(cloud, (int(16 * sx), int(20 * sx)), axis=(1, 0))
    arr = arr * (1 - shadow[..., None] * 0.35)
    arr += cloud[..., None] * np.array((88, 96, 110), np.float32)
    # --- route: glowing comet drawing itself
    p = ease_out_cubic(seg(t, 0.5, dur - 0.55))
    rpts = polyline_progress(st["route"], p)
    lay = Image.new("L", (bw, bh), 0)
    dl = ImageDraw.Draw(lay)
    if len(rpts) > 1:
        dl.line(rpts, fill=200, width=max(2, int(4 * sx)))
        tail = polyline_progress(st["route"], p)[-max(2, len(rpts) // 6):]
        dl.line(tail, fill=255, width=max(3, int(7 * sx)))
    arr = arr + glow_layer(lay, 10 * sx, (40, 110, 160), 1.0) \
        + glow_layer(lay, 2.5 * sx, (150, 220, 255), 0.9)
    img = to_img(arr * fade)
    d = ImageDraw.Draw(img)
    if len(rpts) > 1 and 0 < p < 1:
        hx, hy = rpts[-1]
        rr = (6 + 2 * math.sin(t * 9)) * sx
        d.ellipse([hx - rr, hy - rr, hx + rr, hy + rr], fill=(220, 245, 255))
    # --- city beacons pop one by one with ping rings + labels
    lab_f = font("IBMPlexMono-Bold.ttf", 30 * sx)
    n_c = len(CITIES)
    for i, (name, x, y) in enumerate(CITIES):
        t_pop = 0.55 + i * (dur - 1.7) / n_c
        tp = seg(t, t_pop, t_pop + 0.5)
        if tp <= 0:
            continue
        x, y = x * sx, y * sy
        r = 9 * sx * ease_out_back(tp, 2.2)
        for rr, a in ((r * 3.2, 26), (r * 2.0, 60), (r, 255)):
            col = (int(GREEN[0] * a / 255 + arr[0, 0, 0] * 0),
                   int(GREEN[1] * a / 255), int(GREEN[2] * a / 255))
            d.ellipse([x - rr, y - rr, x + rr, y + rr],
                      fill=col if a == 255 else None,
                      outline=None if a == 255 else col,
                      width=max(1, int(2 * sx)))
        ring = seg(t, t_pop, t_pop + 0.9)
        if 0 < ring < 1:
            rr = r + 46 * sx * ease_out_cubic(ring)
            a = int(150 * (1 - ring))
            d.ellipse([x - rr, y - rr, x + rr, y + rr],
                      outline=(a // 3, a, a // 2), width=max(1, int(2 * sx)))
        if tp > 0.55:
            a2 = seg(tp, 0.55, 1.0)
            tw = d.textlength(name, font=lab_f)
            lx, ly = x + 20 * sx, y - 48 * sy
            if x + 20 * sx + tw > bw * 0.86:   # camera crop eats the right edge
                lx = x - tw - 20 * sx
            pad = 8 * sx
            tint = Image.new("RGBA", img.size, (0, 0, 0, 0))
            td = ImageDraw.Draw(tint)
            td.rectangle([lx - pad, ly - pad * 0.6, lx + tw + pad,
                          ly + 34 * sx + pad * 0.6],
                         fill=(5, 8, 12, int(150 * a2)))
            img.paste(Image.alpha_composite(img.convert("RGBA"), tint)
                      .convert("RGB"), (0, 0))
            d = ImageDraw.Draw(img)
            d.line([(x + 8 * sx, y - 8 * sy), (lx, ly + 30 * sx)],
                   fill=(70, 100, 110), width=max(1, int(2 * sx)))
            c = tuple(int(v * a2) for v in INK)
            d.text((lx, ly), name, font=lab_f, fill=c)
    # --- slow camera push-in, vignette, grain
    z = 1.0 + 0.09 * ease_io(seg(t, 0, dur))
    cw, ch = int(w / z), int(h / z)
    ox = int((bw - cw) * (0.30 + 0.35 * seg(t, 0, dur)))
    oy = int((bh - ch) * (0.62 - 0.30 * seg(t, 0, dur)))
    img = img.crop((ox, oy, ox + cw, oy + ch)).resize((w, h), Image.LANCZOS)
    out = np.asarray(img, np.float32) * vignette((w, h)) + grain((w, h), int(t * FPS))
    return to_img(out)


# ============================================= scene 2: THE LIVING CHART
# "A chart that moves like it's alive" — an aurora ridge breathing over a
# night valley, sparks rising off the data line. Still a chart. Also a sky.
_CHART_CACHE: dict[tuple, dict] = {}


def _chart_static(size: tuple) -> dict:
    if size not in _CHART_CACHE:
        w, h = size
        yy = np.linspace(0, 1, h)[:, None]
        sky = (np.array((6, 9, 18), np.float32) * (1 - yy)
               + np.array((13, 17, 23), np.float32) * yy)[None, ...] \
            if False else \
            np.array((6, 9, 18), np.float32)[None, None, :] * (1 - yy[..., None]) \
            + np.array((16, 20, 30), np.float32)[None, None, :] * yy[..., None]
        sky = np.broadcast_to(sky.squeeze(1) if sky.ndim == 4 else sky,
                              (h, w, 3)).copy()
        rng = np.random.default_rng(5)
        stars = np.zeros((h, w, 1), np.float32)
        n = max(30, w * h // 18000)
        xs = rng.integers(0, w, n)
        ys_ = rng.integers(0, int(h * 0.55), n)
        stars[ys_, xs, 0] = rng.uniform(60, 160, n)
        _CHART_CACHE[size] = {"sky": sky, "stars": stars,
                              "tw": rng.uniform(0, 6.28, n),
                              "sx": xs, "sy": ys_}
    return _CHART_CACHE[size]


def _ridge(xn: np.ndarray, t: float, k: int) -> np.ndarray:
    """Gentle breathing trend line: few slow waves + a rise to the right."""
    return (0.09 * np.sin(xn * (1.5 + 0.4 * k) + t * (0.8 + 0.25 * k) + k * 2.1)
            + 0.05 * np.sin(xn * (3.1 - 0.5 * k) - t * 0.6 + k)
            + 0.022 * np.sin(xn * 5.3 + t * 1.4 + k * 3.7)
            - 0.11 * (xn / (2 * math.pi)))          # the chart trends UP


def scene_chart(t: float, dur: float, size: tuple) -> Image.Image:
    w, h = size
    st = _chart_static(size)
    arr = st["sky"].copy()
    # twinkling stars
    tw = (0.55 + 0.45 * np.sin(t * 2.2 + st["tw"])).astype(np.float32)
    arr[st["sy"], st["sx"]] += (st["stars"][st["sy"], st["sx"], 0]
                                * tw)[:, None] * np.array((0.8, 0.9, 1.0),
                                                          np.float32)
    xn = np.linspace(0, 1, w) * 2 * math.pi
    reveal = ease_out_cubic(seg(t, 0.05, dur * 0.55))
    layers = [(0.50, (14, 44, 52), 0.55, 0),
              (0.60, (16, 66, 62), 0.75, 1),
              (0.70, (20, 92, 66), 1.0, 2)]
    yy = np.linspace(0, 1, h)[:, None]
    for base, col, alpha, k in layers:
        ridge = base + _ridge(xn, t, k) * (0.7 + 0.3 * math.sin(t * 1.1 + k))
        m = (yy > ridge[None, :]).astype(np.float32)[..., None] \
            if False else (yy > ridge[None, :])[..., None].astype(np.float32)
        fade_d = np.clip((yy - ridge[None, :]) * 3.2, 0, 1)[..., None]
        arr += m * (1 - fade_d * 0.7) * np.array(col, np.float32) * alpha * reveal
    # the data line = top of front ridge, drawn with glow, revealed L->R
    ridge_f = 0.70 + _ridge(xn, t, 2) * (0.7 + 0.3 * math.sin(t * 1.1 + 2))
    lay = Image.new("L", size, 0)
    dl = ImageDraw.Draw(lay)
    n_show = max(2, int(w * ease_out_cubic(seg(t, 0.05, dur * 0.5))))
    pts = [(i, ridge_f[i] * h) for i in range(0, n_show, 3)]
    if len(pts) > 1:
        dl.line(pts, fill=255, width=max(2, int(w * 0.0035)))
    arr += glow_layer(lay, w * 0.008, (60, 190, 120), 1.1)
    arr += glow_layer(lay, w * 0.002, (180, 255, 210), 0.8)
    # sparks rising off the line
    rng = np.random.default_rng(17)
    n_sp = 42
    px = rng.uniform(0.03, 0.97, n_sp)
    ph_ = rng.uniform(0, 1, n_sp)
    img = to_img(arr)
    d = ImageDraw.Draw(img)
    for i in range(n_sp):
        life = (ph_[i] + t * 0.30) % 1.0
        x = px[i] * w + math.sin(t * 1.3 + i) * w * 0.004
        xi = int(np.clip(x, 0, w - 1))
        y = ridge_f[xi] * h - life * h * 0.22
        a = (1 - life) * min(1.0, seg(t, 0.4, 1.2))
        r = w * 0.0016 * (1 + (1 - life))
        c = (int(140 * a), int(235 * a), int(170 * a))
        d.ellipse([x - r, y - r, x + r, y + r], fill=c)
    # live endpoint pulse
    if n_show >= w - 4:
        ex, ey = w * 0.985, ridge_f[int(w * 0.985)] * h
        rr = w * 0.006 * (1 + 0.25 * math.sin(t * 6))
        d.ellipse([ex - rr, ey - rr, ex + rr, ey + rr], fill=(210, 255, 225))
    # thin baseline so it still reads as a chart
    d.line([(w * 0.03, h * 0.93), (w * 0.97, h * 0.93)], fill=(46, 56, 66),
           width=max(1, int(w * 0.0015)))
    out = np.asarray(img, np.float32) * vignette(size) + grain(size, int(t * FPS))
    return to_img(out)


# ============================================ scene 3: TYPE ON THE BEAT
def scene_type(t: float, dur: float, size: tuple) -> Image.Image:
    w, h = size
    slot = dur / len(WORDS)
    hit_i = min(len(WORDS) - 1, int(t / slot))
    t_hit = hit_i * slot
    since = t - t_hit
    # background: radial beat-pulse
    pulse = math.exp(-since * 5.0)
    yy, xx = np.mgrid[0:h, 0:w]
    r2 = ((xx / w - 0.5) ** 2 + (yy / h - 0.5) ** 2) * 4
    arr = np.array(BG, np.float32)[None, None, :] \
        + (np.exp(-r2 * 2.2)[..., None] * np.array((10, 26, 16), np.float32)
           * (0.5 + 1.6 * pulse))
    # camera shake decaying after each hit (deterministic)
    shk = 14 * pulse
    ox = shk * math.sin(since * 60 + hit_i * 9)
    oy = shk * 0.6 * math.sin(since * 74 + hit_i * 5)
    img = to_img(arr)
    d = ImageDraw.Draw(img)
    # stacked past words, dim
    f_small = font("ArchivoBlack-Regular.ttf", 60 * w / DESIGN_W)
    for i in range(hit_i):
        d.text((w * 0.06 + ox * 0.2, h * 0.09 + i * 74 * w / DESIGN_W + oy * 0.2),
               WORDS[i], font=f_small, fill=(64, 76, 90))
    # the hit word: bloom + core + shockwave + sparks
    word = WORDS[hit_i]
    tp = seg(since, 0, 0.26)
    px = int(232 * w / DESIGN_W * (0.82 + 0.18 * ease_out_back(tp, 2.4)))
    f_big = font("ArchivoBlack-Regular.ttf", px)
    tw = d.textlength(word, font=f_big)
    cx, cy = (w - tw) / 2 + ox, h * 0.5 - px * 0.62 + oy
    lay = Image.new("L", size, 0)
    ImageDraw.Draw(lay).text((cx, cy), word, font=f_big, fill=255)
    col = GREEN if hit_i % 2 else (200, 225, 245)
    out = np.asarray(img, np.float32)
    out += glow_layer(lay, w * 0.014, col, 0.85 * (0.6 + pulse))
    out += glow_layer(lay, w * 0.003, (255, 255, 255), 0.35 * (0.4 + pulse))
    img = to_img(out)
    d = ImageDraw.Draw(img)
    d.text((cx, cy), word, font=f_big, fill=INK if hit_i % 2 == 0 else
           (225, 245, 230))
    ring = seg(since, 0, 0.5)
    if 0 < ring < 1:
        rr = (0.10 + 0.42 * ease_out_cubic(ring)) * w
        a = int(140 * (1 - ring))
        d.ellipse([w / 2 - rr + ox, h / 2 - rr * 9 / 16 + oy,
                   w / 2 + rr + ox, h / 2 + rr * 9 / 16 + oy],
                  outline=(a // 3, a, a // 2),
                  width=max(1, int(w * 0.004 * (1 - ring) + 1)))
    # impact sparks
    if since < 0.5:
        rng = np.random.default_rng(hit_i + 40)
        for k in range(14):
            ang = rng.uniform(0, 6.28)
            spd = rng.uniform(0.12, 0.34) * w
            x = w / 2 + math.cos(ang) * spd * since * 2.2
            y = h / 2 + math.sin(ang) * spd * since * 2.2 * 0.6
            a = 1 - since * 2
            if a > 0:
                r = w * 0.0022 * a
                d.ellipse([x - r, y - r, x + r, y + r],
                          fill=(int(180 * a), int(240 * a), int(200 * a)))
    out = np.asarray(img, np.float32) * vignette(size) + grain(size, int(t * FPS))
    return to_img(out)


# ================================================ scene 4: SMOKE & MOON
_SMOKE_CACHE: dict[tuple, dict] = {}
_SPRITES: dict[int, np.ndarray] = {}


def _puff(r: int) -> np.ndarray:
    if r not in _SPRITES:
        c = int(r * 1.5)
        sp = Image.new("L", (c * 2, c * 2), 0)
        dd = ImageDraw.Draw(sp)
        for rr, a in ((r, 34), (int(r * 0.7), 52), (int(r * 0.42), 74)):
            dd.ellipse([c - rr, c - rr, c + rr, c + rr], fill=a)
        _SPRITES[r] = np.asarray(sp.filter(ImageFilter.GaussianBlur(r * 0.55)),
                                 np.float32)
    return _SPRITES[r]


def _smoke_static(size: tuple) -> dict:
    """A READABLE night vignette (poster values, not murk): starry navy sky,
    two crisp mountain lines, a lake with a moon glitter path, and a big
    foreground hill carrying the cabin."""
    if size not in _SMOKE_CACHE:
        w, h = size
        yy = np.linspace(0, 1, h)[:, None, None]
        sky = np.array((14, 19, 40), np.float32) * (1 - yy) \
            + np.array((28, 35, 62), np.float32) * yy
        sky = np.broadcast_to(sky, (h, w, 3)).copy()
        rng = np.random.default_rng(3)
        n = max(50, w * h // 11000)
        xs = rng.integers(0, w, n)
        ys_ = rng.integers(0, int(h * 0.55), n)
        mag = rng.uniform(60, 170, n).astype(np.float32)
        ph = rng.uniform(0, 6.28, n).astype(np.float32)
        WATER_Y = 0.80                       # lake takes the bottom fifth
        ridges = []
        for k, (base, col) in enumerate([(0.62, (22, 28, 54)),
                                         (0.72, (13, 17, 36))]):
            prof = fbm(1, w * 2, seed=30 + k, octaves=4,
                       base_cell=max(4, w // 4))[0]
            ridges.append({"base": base, "col": np.array(col, np.float32),
                           "prof": prof, "speed": 4 + k * 7})
        # foreground hill, rising to the left — the cabin's stage
        xs_h = np.arange(w)
        hillp = fbm(1, w * 2, seed=44, octaves=3, base_cell=max(4, w // 3))[0]
        hill_y = (0.86 - 0.16 * np.exp(-((xs_h / w - 0.20) ** 2) / 0.045)
                  + (hillp[:w] - 0.5) * 0.02) * h
        _SMOKE_CACHE[size] = {"sky": sky, "sx": xs, "sy": ys_, "mag": mag,
                              "ph": ph, "ridges": ridges, "hill": hill_y,
                              "water_y": WATER_Y}
    return _SMOKE_CACHE[size]


def scene_smoke(t: float, dur: float, size: tuple) -> Image.Image:
    w, h = size
    st = _smoke_static(size)
    arr = st["sky"].copy()
    tw = (0.5 + 0.5 * np.sin(t * 1.8 + st["ph"])).astype(np.float32)
    arr[st["sy"], st["sx"]] += (st["mag"] * tw)[:, None] \
        * np.array((0.8, 0.88, 1.0), np.float32)
    out = arr
    # big warm moon + bloom
    mx, my = w * 0.74, h * 0.20
    mr = w * 0.045
    disc = Image.new("L", size, 0)
    ImageDraw.Draw(disc).ellipse([mx - mr, my - mr, mx + mr, my + mr], fill=255)
    out += glow_layer(disc, mr * 2.2, (74, 78, 96), 1.0)
    out += np.asarray(disc.filter(ImageFilter.GaussianBlur(2)),
                      np.float32)[..., None] / 255.0 \
        * np.array((246, 240, 222), np.float32)
    # two crisp mountain lines (poster values — readable at a glance)
    yy = np.arange(h)[:, None]
    for rd in st["ridges"]:
        off = int(t * rd["speed"]) % w
        ys = (rd["base"] + (rd["prof"][off:off + w] - 0.5) * 0.12) * h
        m = (yy >= ys[None, :]).astype(np.float32)
        out = out * (1 - m[..., None]) + rd["col"][None, None, :] * m[..., None]
    # the lake: dark water + moon glitter path
    wy = int(st["water_y"] * h)
    water = np.zeros((h, w), np.float32)
    water[wy:] = 1.0
    out = out * (1 - water[..., None]) \
        + np.array((10, 14, 32), np.float32)[None, None, :] * water[..., None]
    img = to_img(out)
    d = ImageDraw.Draw(img)
    rng_g = np.random.default_rng(6)
    gx = rng_g.normal(mx, w * 0.035, 90)
    gp = rng_g.uniform(0, 6.28, 90)
    gyy = rng_g.uniform(wy + h * 0.01, h - 2, 90)
    for i in range(90):
        a = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(t * 2.6 + gp[i]))
        ww = w * 0.006 * (0.5 + a)
        d.line([(gx[i] - ww, gyy[i]), (gx[i] + ww, gyy[i])],
               fill=(int(196 * a), int(190 * a), int(160 * a)),
               width=max(1, int(h * 0.003)))
    d.line([(0, wy), (w, wy)], fill=(34, 42, 70), width=max(1, int(h * 0.002)))
    # foreground hill
    hill = st["hill"]
    d.polygon([(0, h)] + [(x, hill[x]) for x in range(0, w, 3)] + [(w, h)],
              fill=(6, 8, 18))
    # THE CABIN — big, foreground, warm light spilling out
    cbx = w * 0.20
    cby = hill[int(cbx)]
    cw_, chh = w * 0.15, h * 0.15
    bx0, by0 = cbx - cw_ / 2, cby - chh
    d.polygon([(bx0 - cw_ * 0.14, by0), (cbx, by0 - chh * 0.72),
               (bx0 + cw_ * 1.14, by0)], fill=(10, 11, 20))
    d.rectangle([bx0, by0, bx0 + cw_, cby + chh * 0.10], fill=(8, 9, 17))
    d.rectangle([bx0 + cw_ * 0.66, by0 - chh * 0.98,
                 bx0 + cw_ * 0.80, by0 - chh * 0.30], fill=(10, 11, 20))
    wa = 0.82 + 0.18 * math.sin(t * 3.1)          # hearth flicker
    win = Image.new("L", size, 0)
    wd_ = ImageDraw.Draw(win)
    wx0, wy0 = bx0 + cw_ * 0.14, by0 + chh * 0.24
    wwid, whei = cw_ * 0.26, chh * 0.44
    wd_.rectangle([wx0, wy0, wx0 + wwid, wy0 + whei], fill=int(230 * wa))
    wd_.rectangle([wx0 + cw_ * 0.42, wy0, wx0 + cw_ * 0.42 + wwid * 0.6,
                   wy0 + whei], fill=int(150 * wa))
    # light pooling on the snowless ground under the window
    wd_.ellipse([wx0 - cw_ * 0.10, cby - chh * 0.06,
                 wx0 + wwid + cw_ * 0.28, cby + chh * 0.22], fill=int(70 * wa))
    out = np.asarray(img, np.float32)
    out += glow_layer(win, w * 0.012, (150, 92, 28), 1.0)
    out += np.asarray(win, np.float32)[..., None] / 255.0 \
        * np.array((244, 196, 118), np.float32)
    img = to_img(out)
    d = ImageDraw.Draw(img)
    # window cross-bars for shape clarity
    d.line([(wx0 + wwid / 2, wy0), (wx0 + wwid / 2, wy0 + whei)],
           fill=(30, 22, 16), width=max(1, int(w * 0.003)))
    d.line([(wx0, wy0 + whei / 2), (wx0 + wwid, wy0 + whei / 2)],
           fill=(30, 22, 16), width=max(1, int(w * 0.003)))
    # THE SMOKE — one clear plume, born at the chimney, drifting past the moon
    out = np.asarray(img, np.float32)
    chx, chy = bx0 + cw_ * 0.73, by0 - chh * 0.98
    acc = np.zeros((h, w), np.float32)
    n_p = 26
    for i in range(n_p):
        life = (i / n_p + t * 0.115) % 1.0
        drift = life * life * 0.9 + life * 0.25
        pxx = chx + drift * w * 0.62 \
            + math.sin(life * 7 + t * 0.8 + i * 0.4) * w * 0.014 * (0.3 + life)
        pyy = chy - life * h * 0.34 + math.sin(life * 4 + t) * h * 0.012
        r = max(4, int((10 + life * 74) * w / DESIGN_W))
        sp = _puff(r)
        c = sp.shape[0] // 2
        x0, y0 = int(pxx - c), int(pyy - c)
        sx0, sy0 = max(0, -x0), max(0, -y0)
        dx0, dy0 = max(0, x0), max(0, y0)
        dx1, dy1 = min(w, x0 + 2 * c), min(h, y0 + 2 * c)
        if dx1 > dx0 and dy1 > dy0:
            acc[dy0:dy1, dx0:dx1] += sp[sy0:sy0 + dy1 - dy0,
                                        sx0:sx0 + dx1 - dx0] \
                * (1.35 - life * 0.75)
    alpha = np.clip(acc * 2.0, 0, 200)[..., None] / 255.0
    out = out * (1 - alpha) + np.array((176, 184, 202), np.float32) * alpha
    # a couple of thin moonlit fog bands between the mountain lines
    fog = Image.new("L", size, 0)
    fd = ImageDraw.Draw(fog)
    for k, fy in enumerate((0.66, 0.755)):
        yy_ = fy * h + math.sin(t * 0.5 + k * 2) * h * 0.004
        fd.ellipse([w * (0.05 + 0.1 * k) - w * 0.3, yy_ - h * 0.016,
                    w * (0.75 - 0.05 * k) + w * 0.3, yy_ + h * 0.016],
                   fill=46)
    out += glow_layer(fog, w * 0.012, (120, 130, 155), 0.9)
    img = to_img(out)
    d = ImageDraw.Draw(img)
    # fireflies near the cabin — bigger, warmer
    for i in range(9):
        fx = cbx + w * (0.10 + 0.24 * math.sin(t * 0.5 + i * 2.2)) \
            + i * w * 0.035
        fy = hill[int(np.clip(fx, 0, w - 1))] - h * (0.03 + 0.05 * (0.5 + 0.5 * math.sin(t * 0.9 + i * 1.9)))
        a = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(t * 2.3 + i * 2.7))
        r = w * 0.0034 * (0.6 + 0.4 * a)
        d.ellipse([fx - r, fy - r, fx + r, fy + r],
                  fill=(int(226 * a), int(196 * a), int(90 * a)))
    out = np.asarray(img, np.float32) * vignette(size) + grain(size, int(t * FPS))
    return to_img(out)


# ================================================== scene 5: replay grid
def scene_grid(t: float, dur: float, size: tuple) -> Image.Image:
    w, h = size
    img = Image.new("RGB", size, BG)
    half = (w // 2 - round(w * 0.003), h // 2 - round(w * 0.003))
    subs = [
        scene_map(t % 4.6, 4.6, half),
        scene_chart(t % 3.2, 3.2, half),
        scene_type(t % 2.74, 2.74, half),
        scene_smoke(t, dur, half),
    ]
    pos = [(0, 0), (w - half[0], 0), (0, h - half[1]), (w - half[0], h - half[1])]
    for sub, p in zip(subs, pos):
        img.paste(sub, p)
    tp = ease_out_back(seg(t, BADGE_AT, BADGE_AT + 0.35), 1.9)
    if tp > 0:
        d = ImageDraw.Draw(img)
        s = w / DESIGN_W
        bw_, bh_ = 300 * s * tp, 132 * s * tp
        cx, cy = w / 2, h / 2
        d.rounded_rectangle([cx - bw_ / 2, cy - bh_ / 2, cx + bw_ / 2, cy + bh_ / 2],
                            radius=bh_ * 0.24, fill=GREEN)
        f = font("ArchivoBlack-Regular.ttf", 88 * s * tp)
        tw = d.textlength("$0", font=f)
        d.text((cx - tw / 2, cy - 62 * s * tp), "$0", font=f, fill=BG)
    return img


SCENE_FN = {"map": scene_map, "chart": scene_chart, "type": scene_type,
            "smoke": scene_smoke, "grid": scene_grid}


# ------------------------------------------------------------------- render
def render(out: Path, size: tuple, crf: int, preset: str) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    total = sum(d for _, d in SCENES)
    n_frames = round(total * FPS)
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
           "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{size[0]}x{size[1]}", "-r", str(FPS), "-i", "-",
           "-c:v", "libx264", "-crf", str(crf), "-preset", preset,
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t_edges, acc = [], 0.0
    for name, d in SCENES:
        t_edges.append((name, acc, acc + d))
        acc += d
    for fi in range(n_frames):
        t = fi / FPS
        for name, t0, t1 in t_edges:
            if t0 <= t < t1 or (name == SCENES[-1][0] and t >= t1):
                frame = SCENE_FN[name](t - t0, t1 - t0, size)
                break
        proc.stdin.write(frame.tobytes())
        if fi % 120 == 0:
            print(f"  frame {fi}/{n_frames} ({t:5.1f}s / {total:.1f}s)", flush=True)
    proc.stdin.close()
    proc.wait()
    if proc.returncode:
        sys.exit(f"ffmpeg failed with code {proc.returncode}")
    print(f"done -> {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--proxy", action="store_true", help="fast 640x360 draft")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    if a.proxy:
        render(Path(a.out or HERE / "montage-proxy.mp4"), (640, 360), 28, "veryfast")
    else:
        render(Path(a.out or HERE / "montage.mp4"), (1920, 1080), 23, "slow")

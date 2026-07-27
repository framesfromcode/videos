# -*- coding: utf-8 -*-
"""
first_film.py — your first FILM, rendered by your own computer.

FramesFromCode starter kit. One locked visual style (the night-poster
letterbox look), your story, and a free offline narrator. Every frame is
computed with numpy + Pillow and piped straight into FFmpeg. No editor.
No camera. No AI video tools. No stock assets. Total cost: zero dollars.

The whole movie lives in story.py: scenes (what's drawn) + lines (what the
voice says + designed pauses). The film is audio-first — each line is
synthesized, measured, and every scene lasts exactly as long as its words.

Run:   python first_film.py --proxy     -> fast small draft (~1 minute)
       python first_film.py             -> my-first-film.mp4 (1920x1080)
       python first_film.py --voice af_heart      -> same film, other voice
       python first_film.py --samples   -> one spoken sample per preset voice

Requirements: Python 3.10+, `pip install numpy pillow kokoro-onnx`,
ffmpeg on PATH, and the voice files (run `python get_tts.py` once).

License: MIT for this script. Fonts in ./fonts are SIL OFL 1.1 (licenses
included). The voice model is Apache-2.0 (Kokoro-82M).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import story

HERE = Path(__file__).resolve().parent
WORK = HERE / "work"
FPS = 30
DESIGN_W, DESIGN_H = 1920, 1080
FILM_RATIO = 2.35                     # the letterbox film frame
SR = 24000
SPEED = 1.0
LEAD_S = 2.2                          # title card before the first line
CARD_S = 3.6                          # end card
MAX_WORDS = 160                       # short films breathe

PRESET_VOICES = ["bm_george", "af_heart", "af_bella", "am_puck"]
SAMPLE_LINE = ("On the edge of the night, a small boat waited for the wind. "
               "This is what your films could sound like.")

# the locked palette, per mood
PALETTES = {
    "night": {
        "sky_top": (9, 13, 30), "sky_bot": (26, 33, 58),
        "moon": (246, 240, 222), "moon_glow": (74, 78, 96),
        "mountain": [(24, 30, 56), (15, 19, 40), (9, 12, 26)],
        "water": (8, 12, 28), "water_lit": (18, 26, 48),
        "glitter": (206, 198, 164),
        "ground": (6, 8, 18),
        "cloud": (60, 68, 92),
    },
    "dawn": {
        "sky_top": (36, 30, 56), "sky_bot": (168, 96, 64),
        "moon": (250, 214, 160), "moon_glow": (120, 74, 48),
        "mountain": [(52, 36, 58), (34, 24, 46), (20, 15, 32)],
        "water": (30, 22, 38), "water_lit": (78, 44, 44),
        "glitter": (240, 176, 120),
        "ground": (14, 10, 22),
        "cloud": (140, 92, 84),
    },
}
INK = (230, 237, 243)
GREEN = (63, 185, 80)
AMBER = (210, 153, 34)
PAPER = (226, 228, 224)               # the paper boat reads bright
_OVERSCAN = 1.08


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


def seg(t: float, t0: float, t1: float) -> float:
    return clamp01((t - t0) / (t1 - t0)) if t1 > t0 else 1.0


# ------------------------------------------------------- procedural texture
def _vnoise(h: int, w: int, cell: int, rng: np.random.Generator) -> np.ndarray:
    gh, gw = h // cell + 2, w // cell + 2
    g = rng.uniform(0, 1, (gh, gw))
    ys = np.linspace(0, gh - 1.001, h)
    xs = np.linspace(0, gw - 1.001, w)
    y0, x0 = ys.astype(int), xs.astype(int)
    fy, fx = (ys - y0)[:, None], (xs - x0)[None, :]
    fy, fx = fy * fy * (3 - 2 * fy), fx * fx * (3 - 2 * fx)
    a = g[y0][:, x0]
    b = g[y0][:, x0 + 1]
    c = g[y0 + 1][:, x0]
    d = g[y0 + 1][:, x0 + 1]
    return a * (1 - fy) * (1 - fx) + b * (1 - fy) * fx \
        + c * fy * (1 - fx) + d * fy * fx


def fbm(h: int, w: int, seed: int, octaves: int = 5,
        base_cell: int = 320) -> np.ndarray:
    rng = np.random.default_rng(seed)
    acc = np.zeros((h, w))
    amp, tot, cell = 1.0, 0.0, base_cell
    for _ in range(octaves):
        acc += amp * _vnoise(h, w, max(2, cell), rng)
        tot += amp
        amp *= 0.5
        cell //= 2
    return acc / tot


def glow_layer(mask: Image.Image, radius: float, color: tuple,
               strength: float = 1.0) -> np.ndarray:
    g = np.asarray(mask.filter(ImageFilter.GaussianBlur(radius)),
                   dtype=np.float32) / 255.0 * strength
    return g[..., None] * np.array(color, dtype=np.float32)


def to_img(arr: np.ndarray) -> Image.Image:
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")


_VIGNETTE: dict[tuple, np.ndarray] = {}


def vignette(size: tuple, power: float = 0.5) -> np.ndarray:
    if size not in _VIGNETTE:
        w, h = size
        yy, xx = np.mgrid[0:h, 0:w]
        r = np.sqrt(((xx / w - 0.5) * 2.1) ** 2 + ((yy / h - 0.5) * 2.1) ** 2)
        _VIGNETTE[size] = (1 - np.clip(r - 0.55, 0, 1) * power)[..., None]
    return _VIGNETTE[size]


_GRAIN: dict[tuple, list[np.ndarray]] = {}


def grain(size: tuple, fi: int, amount: float = 4.5) -> np.ndarray:
    if size not in _GRAIN:
        rng = np.random.default_rng(99)
        _GRAIN[size] = [rng.standard_normal((size[1], size[0], 1)) * amount
                        for _ in range(4)]
    return _GRAIN[size][fi % 4]


# =============================================== the locked style: elements
_SCENE_CACHE: dict[tuple, dict] = {}


def _norm_art(art: dict) -> dict:
    """Fill defaults so drawing code never guesses."""
    a = dict(art)
    a.setdefault("palette", "night")
    if a.get("moon") is True:
        a["moon"] = {}
    if "moon" in a and a["moon"] is not None:
        m = {"x": 0.74, "y": 0.20, "r": 0.045}
        m.update(a["moon"] or {})
        a["moon"] = m
    a.setdefault("stars", 1.0)
    a.setdefault("clouds", 0.0)
    mt = a.get("mountains", 0)
    if isinstance(mt, int):
        mt = [{"base": b} for b in ((0.52, 0.62, 0.70)[:mt] if mt else ())]
    a["mountains"] = mt
    if a.get("water"):
        wtr = {"y": 0.60, "glitter": False}
        wtr.update(a["water"] if isinstance(a["water"], dict) else {})
        a["water"] = wtr
    if a.get("hill"):
        h = {"x": 0.25, "h": 0.14}
        h.update(a["hill"] if isinstance(a["hill"], dict) else {})
        a["hill"] = h
    if a.get("cabin"):
        c = {"x": 0.22, "scale": 1.0, "smoke": False}
        c.update(a["cabin"] if isinstance(a["cabin"], dict) else {})
        a["cabin"] = c
    if a.get("boat"):
        b = {"x": 0.4, "scale": 1.0, "drift": 0.02, "kind": "paper",
             "sail_text": None}
        b.update(a["boat"] if isinstance(a["boat"], dict) else {})
        a["boat"] = b
    if a.get("figure"):
        f = {"x": 0.3, "scale": 1.0}
        f.update(a["figure"] if isinstance(a["figure"], dict) else {})
        a["figure"] = f
    a.setdefault("fireflies", 0)
    a.setdefault("push", False)
    return a


def _scene_static(idx: int, art: dict, size: tuple) -> dict:
    key = (idx, size)
    if key in _SCENE_CACHE:
        return _SCENE_CACHE[key]
    w, h = size
    P = PALETTES[art["palette"]]
    yy = np.linspace(0, 1, h)[:, None, None]
    sky = np.array(P["sky_top"], np.float32) * (1 - yy) \
        + np.array(P["sky_bot"], np.float32) * yy
    sky = np.broadcast_to(sky, (h, w, 3)).copy()
    rng = np.random.default_rng(300 + idx)
    n = int(max(40, w * h // 12000) * art["stars"])
    st = {
        "P": P,
        "sky": sky,
        "star_x": rng.integers(0, w, n),
        "star_y": rng.integers(0, int(h * 0.72), n),
        "star_m": rng.uniform(50, 165, n).astype(np.float32),
        "star_p": rng.uniform(0, 6.28, n).astype(np.float32),
    }
    # mountain profiles (fbm ridge per layer, farthest first)
    profs = []
    for k, m in enumerate(art["mountains"]):
        prof = fbm(1, w * 2, seed=700 + idx * 7 + k, octaves=4,
                   base_cell=max(4, w // (3 + k)))[0]
        col = P["mountain"][min(k, len(P["mountain"]) - 1)]
        profs.append({"base": m.get("base", 0.55 + 0.09 * k),
                      "prof": prof, "col": np.array(col, np.float32),
                      "amp": m.get("amp", 0.10)})
    st["mountains"] = profs
    if art.get("hill"):
        xs = np.arange(w)
        hp = fbm(1, w * 2, seed=900 + idx, octaves=3,
                 base_cell=max(4, w // 3))[0]
        st["hill"] = (0.94 - art["hill"]["h"] * 1.6
                      * np.exp(-((xs / w - art["hill"]["x"]) ** 2) / 0.05)
                      + (hp[:w] - 0.5) * 0.02) * h
    if art["clouds"] > 0:
        cl = fbm(h, w, seed=520 + idx, octaves=4, base_cell=max(8, w // 4))
        st["cloud"] = np.clip(cl - (0.72 - art["clouds"] * 0.22), 0, 1) * 2.2
    _SCENE_CACHE[key] = st
    return st


def _draw_boat(d: ImageDraw.ImageDraw, img_w: int, img_h: int, x: float,
               y: float, scale: float, t: float,
               sail_text: str | None = None) -> None:
    """A little paper boat: bright hull + triangular sail, gentle bob."""
    s = img_w * 0.030 * scale
    bob = math.sin(t * 1.6) * s * 0.10
    tilt = math.sin(t * 1.1 + 1.3) * 0.06
    cx, cy = x * img_w, y + bob
    hull = [(cx - s, cy), (cx + s, cy),
            (cx + s * 0.62, cy + s * 0.42), (cx - s * 0.62, cy + s * 0.42)]
    sail = [(cx - s * 0.66, cy - s * 0.06), (cx + s * 0.66, cy - s * 0.06),
            (cx + s * 0.02, cy - s * 1.05)]

    def rot(pts):
        return [(cx + (px - cx) - (py - cy) * tilt,
                 cy + (py - cy) + (px - cx) * tilt) for px, py in pts]
    d.polygon(rot(hull), fill=PAPER)
    d.polygon(rot(sail), fill=(206, 210, 212))
    d.line(rot([(cx - s, cy), (cx + s, cy)]), fill=(150, 152, 150), width=1)
    # reflection
    refl = [(px, 2 * (cy + s * 0.42) - py) for px, py in rot(sail)]
    d.polygon(refl, fill=(52, 58, 66))
    # handwriting on the sail — the reveal shot (readable when scale >= 1.4)
    if sail_text and scale >= 1.4:
        f_s = font("IBMPlexMono-Bold.ttf", s * 0.16)
        words = sail_text.split()
        rows = [" ".join(words[:len(words) // 2 or 1]),
                " ".join(words[len(words) // 2 or 1:])]
        for r_i, row in enumerate(rows):
            if not row:
                continue
            tw_ = d.textlength(row, font=f_s)
            d.text((cx - s * 0.12 - tw_ / 2,
                    cy - s * (0.62 - r_i * 0.20)), row, font=f_s,
                   fill=(96, 98, 104))


def _draw_figure(d: ImageDraw.ImageDraw, w: int, x: float, base_y: float,
                 scale: float, t: float, on_ground: bool) -> None:
    """A quiet standing silhouette, slight breath, on a small dark bank."""
    hgt = w * 0.052 * scale
    cx = x * w
    if not on_ground:                      # give them a shore to stand on
        d.ellipse([cx - hgt * 1.5, base_y - hgt * 0.10,
                   cx + hgt * 1.5, base_y + hgt * 0.55], fill=(5, 6, 12))
    br = 1 + 0.008 * math.sin(t * 1.2)
    top = base_y - hgt * br
    d.ellipse([cx - hgt * 0.13, top, cx + hgt * 0.13, top + hgt * 0.26],
              fill=(4, 5, 10))
    d.polygon([(cx - hgt * 0.20, base_y), (cx - hgt * 0.13, top + hgt * 0.24),
               (cx + hgt * 0.13, top + hgt * 0.24), (cx + hgt * 0.20, base_y)],
              fill=(4, 5, 10))


def draw_scene(idx: int, art: dict, t: float, dur: float,
               size: tuple) -> Image.Image:
    """One frame of one scene, at overscan size (camera crops later)."""
    w, h = size
    st = _scene_static(idx, art, size)
    P = st["P"]
    arr = st["sky"].copy()
    # stars
    tw = (0.5 + 0.5 * np.sin(t * 1.7 + st["star_p"])).astype(np.float32)
    arr[st["star_y"], st["star_x"]] += (st["star_m"] * tw)[:, None] \
        * np.array((1.05, 1.15, 1.3), np.float32)
    # moon + glow
    if art.get("moon"):
        m = art["moon"]
        mx, my, mr = m["x"] * w, m["y"] * h, m["r"] * w
        disc = Image.new("L", size, 0)
        ImageDraw.Draw(disc).ellipse([mx - mr, my - mr, mx + mr, my + mr],
                                     fill=255)
        arr += glow_layer(disc, mr * 2.1, P["moon_glow"], 1.0)
        arr += np.asarray(disc.filter(ImageFilter.GaussianBlur(2)),
                          np.float32)[..., None] / 255.0 \
            * np.array(P["moon"], np.float32)
    # clouds drift
    if art["clouds"] > 0:
        cl = np.roll(st["cloud"], int(t * w * 0.008), axis=1)
        arr = arr * (1 - cl[..., None] * 0.25)
        arr += cl[..., None] * np.array(P["cloud"], np.float32) * 0.9
    # mountains, far to near, slow parallax
    yy = np.arange(h)[:, None]
    for k, rd in enumerate(st["mountains"]):
        off = int(t * (2 + k * 4)) % w
        ys = (rd["base"] + (rd["prof"][off:off + w] - 0.5) * rd["amp"]) * h
        mmask = (yy >= ys[None, :]).astype(np.float32)[..., None]
        arr = arr * (1 - mmask) + rd["col"][None, None, :] * mmask
    # water: opaque night gradient, brighter toward the bottom (closer)
    wy = None
    if art.get("water"):
        wy = int(art["water"]["y"] * h)
        shade = np.linspace(0, 1, h - wy)[:, None, None]
        arr[wy:] = np.array(P["water"], np.float32)[None, None, :] \
            * (1 - shade * 0.25) + np.array(P["water_lit"], np.float32) \
            * shade * 0.35
        # faint sky reflection just under the water line
        band = min(h - wy, max(8, (h - wy) // 4))
        arr[wy:wy + band] += arr[max(0, wy - band):wy][::-1] * 0.08
    img = to_img(arr)
    d = ImageDraw.Draw(img)
    if wy is not None:
        d.line([(0, wy), (w, wy)], fill=tuple(
            int(v) for v in np.array(P["water_lit"]) * 1.4), width=max(1, h // 400))
        # moon glitter road on the water
        if art["water"].get("glitter") and art.get("moon"):
            m = art["moon"]
            rng_g = np.random.default_rng(60 + idx)
            gx = rng_g.normal(m["x"] * w, w * 0.045, 150)
            gp = rng_g.uniform(0, 6.28, 150)
            gyy = rng_g.uniform(wy + h * 0.012, h - 2, 150)
            for i in range(150):
                a = 0.3 + 0.7 * (0.5 + 0.5 * math.sin(t * 2.4 + gp[i]))
                spread = 1 + (gyy[i] - wy) / max(1, h - wy) * 1.6
                ww = w * 0.005 * (0.5 + a) * spread
                col = tuple(int(v * a) for v in P["glitter"])
                d.line([(gx[i] - ww, gyy[i]), (gx[i] + ww, gyy[i])],
                       fill=col, width=max(1, int(h * 0.004)))
    # foreground hill + cabin + fireflies live on it
    ground_y = None
    if art.get("hill"):
        hill = st["hill"]
        d.polygon([(0, h)] + [(x, hill[x]) for x in range(0, w, 3)]
                  + [(w, h)], fill=P["ground"])
        ground_y = hill
    if art.get("cabin"):
        c = art["cabin"]
        cbx = c["x"] * w
        base = (ground_y[int(np.clip(cbx, 0, w - 1))] if ground_y is not None
                else (wy if wy is not None else h * 0.8))
        cw_, chh = w * 0.11 * c["scale"], h * 0.16 * c["scale"]
        bx0, by0 = cbx - cw_ / 2, base - chh
        d.polygon([(bx0 - cw_ * 0.14, by0), (cbx, by0 - chh * 0.62),
                   (bx0 + cw_ * 1.14, by0)], fill=(8, 9, 16))
        d.rectangle([bx0, by0, bx0 + cw_, base + chh * 0.06], fill=(6, 7, 14))
        wa = 0.82 + 0.18 * math.sin(t * 3.1)
        win = Image.new("L", size, 0)
        wd_ = ImageDraw.Draw(win)
        wx0, wy0 = bx0 + cw_ * 0.20, by0 + chh * 0.28
        wd_.rectangle([wx0, wy0, wx0 + cw_ * 0.24, wy0 + chh * 0.36],
                      fill=int(230 * wa))
        out2 = np.asarray(img, np.float32)
        out2 += glow_layer(win, w * 0.012, (150, 92, 28), 1.0)
        out2 += np.asarray(win, np.float32)[..., None] / 255.0 \
            * np.array((244, 196, 118), np.float32)
        img = to_img(out2)
        d = ImageDraw.Draw(img)
        if c["smoke"]:
            chx, chy = bx0 + cw_ * 0.78, by0 - chh * 0.55
            for i in range(20):
                life = (i / 20 + t * 0.09) % 1.0
                px_ = chx + life * w * 0.055 \
                    + math.sin(life * 6 + t) * w * 0.007 * (0.4 + life)
                py_ = chy - life * h * 0.22
                r = (2.5 + life * 26) * w / DESIGN_W
                a = int(40 * (1 - life * 0.8))
                d.ellipse([px_ - r, py_ - r, px_ + r, py_ + r],
                          fill=(120 + a, 126 + a, 140 + a))
    # the boat sails on the water line region
    if art.get("boat") and wy is not None:
        b = art["boat"]
        bx = (b["x"] + b["drift"] * t) % 1.04
        by = wy + (h - wy) * 0.28
        _draw_boat(d, w, h, bx, by, b["scale"], t, b["sail_text"])
    # a figure stands at the water's edge (or on the hill)
    if art.get("figure"):
        f = art["figure"]
        fx = f["x"]
        on_ground = ground_y is not None
        base = (ground_y[int(fx * w)] if on_ground
                else (wy + (h - wy) * 0.10 if wy is not None else h * 0.85))
        _draw_figure(d, w, fx, base, f["scale"], t, on_ground)
    # fireflies
    if art["fireflies"]:
        rng_f = np.random.default_rng(40 + idx)
        fx0 = rng_f.uniform(0.06, 0.94, art["fireflies"])
        fy0 = rng_f.uniform(0.55, 0.9, art["fireflies"])
        fp = rng_f.uniform(0, 6.28, art["fireflies"])
        for i in range(art["fireflies"]):
            a = 0.3 + 0.7 * (0.5 + 0.5 * math.sin(t * 2.1 + fp[i]))
            fx_ = (fx0[i] + 0.01 * math.sin(t * 0.6 + fp[i])) * w
            fy_ = (fy0[i] + 0.008 * math.cos(t * 0.8 + fp[i])) * h
            r = w * 0.0028 * (0.6 + 0.4 * a)
            d.ellipse([fx_ - r, fy_ - r, fx_ + r, fy_ + r],
                      fill=(int(226 * a), int(196 * a), int(90 * a)))
    return img


# ============================================================= film frame
def film_frame(seg_name: str, idx: int, art: dict | None, t: float,
               dur: float, size: tuple) -> Image.Image:
    """Compose the letterboxed 16:9 frame: title/scene/end + camera."""
    w, h = size
    fh = int(w / FILM_RATIO)                      # film area height
    bar = (h - fh) // 2
    canvas = Image.new("RGB", size, (0, 0, 0))
    s = w / DESIGN_W
    if seg_name == "scene":
        bw, bh = int(w * _OVERSCAN), int(fh * _OVERSCAN)
        img = draw_scene(idx, art, t, dur, (bw, bh))
        z = 1.0 + (0.06 * ease_io(seg(t, 0, dur)) if art["push"] else 0.0)
        cw, ch = int(w / z), int(fh / z)
        ox = (bw - cw) * (0.5 + 0.06 * math.sin(t * 0.14 + idx))
        oy = (bh - ch) * (0.5 + 0.05 * math.cos(t * 0.11 + idx * 2))
        img = img.crop((int(ox), int(oy), int(ox) + cw, int(oy) + ch)) \
                 .resize((w, fh), Image.LANCZOS)
        out = np.asarray(img, np.float32) * vignette((w, fh)) \
            + grain((w, fh), int(t * FPS))
        # fade in/out at scene edges
        fade = min(ease_out_cubic(seg(t, 0, 0.5)),
                   ease_out_cubic(seg(dur - t, 0, 0.5)) * 0.4 + 0.6)
        canvas.paste(to_img(out * fade), (0, bar))
        return canvas
    d = ImageDraw.Draw(canvas)
    if seg_name == "title":
        a = min(ease_out_cubic(seg(t, 0.3, 1.2)),
                ease_out_cubic(seg(dur - t, 0.0, 0.6)))
        f_t = font("ArchivoBlack-Regular.ttf", 110 * s)
        tw = d.textlength(story.TITLE, font=f_t)
        while tw > w * 0.86 and f_t.size > 40:
            f_t = font("ArchivoBlack-Regular.ttf", f_t.size * 0.92)
            tw = d.textlength(story.TITLE, font=f_t)
        d.text(((w - tw) / 2, h * 0.42), story.TITLE, font=f_t,
               fill=tuple(int(v * a) for v in INK))
        f_s = font("IBMPlexMono-Regular.ttf", 34 * s)
        sub = "a short film, rendered by code on this machine"
        sw = d.textlength(sub, font=f_s)
        d.text(((w - sw) / 2, h * 0.42 + f_t.size * 1.6), sub, font=f_s,
               fill=tuple(int(v * a * 0.6) for v in INK))
    elif seg_name == "end":
        a = ease_out_cubic(seg(t, 0.2, 1.0))
        f_t = font("ArchivoBlack-Regular.ttf", 96 * s)
        tw = d.textlength(story.TITLE, font=f_t)
        while tw > w * 0.86 and f_t.size > 40:
            f_t = font("ArchivoBlack-Regular.ttf", f_t.size * 0.92)
            tw = d.textlength(story.TITLE, font=f_t)
        d.text(((w - tw) / 2, h * 0.36), story.TITLE, font=f_t,
               fill=tuple(int(v * a) for v in INK))
        a2 = ease_out_cubic(seg(t, 0.9, 1.6))
        f_c = font("IBMPlexMono-Bold.ttf", 36 * s)
        items = [("no editor", INK), ("·", (90, 100, 110)),
                 ("no camera", INK), ("·", (90, 100, 110)), ("$0", AMBER)]
        widths = [d.textlength(txt, font=f_c) for txt, _ in items]
        gaps = 24 * s
        x = (w - sum(widths) - gaps * (len(items) - 1)) / 2
        for (txt, col), tw_ in zip(items, widths):
            d.text((x, h * 0.58), txt, font=f_c,
                   fill=tuple(int(v * a2) for v in col))
            x += tw_ + gaps
        f_m = font("IBMPlexMono-Regular.ttf", 30 * s)
        sub = "my first film, rendered from a text file"
        sw = d.textlength(sub, font=f_m)
        a3 = ease_out_cubic(seg(t, 1.5, 2.2))
        d.text(((w - sw) / 2, h * 0.70), sub, font=f_m,
               fill=tuple(int(v * a3 * 0.65) for v in INK))
        if a3 >= 1 and int(t * 2.2) % 2 == 0:
            cx2 = (w + sw) / 2 + 12 * s
            d.rectangle([cx2, h * 0.70, cx2 + 18 * s, h * 0.70 + 34 * s],
                        fill=GREEN)
    return canvas


# ================================================================ narration
def find_models() -> Path:
    for cand in (os.environ.get("FFC_TTS_DIR"), HERE / "tts-models"):
        if cand and (Path(cand) / "kokoro-v1.0.onnx").exists() \
                and (Path(cand) / "voices-v1.0.bin").exists():
            return Path(cand)
    sys.exit("TTS model files not found.\n"
             "Run once:  python get_tts.py   (downloads ~340 MB, free)")


def peak_clamp(x: np.ndarray, cap_dbfs: float = -1.0) -> np.ndarray:
    cap = 10 ** (cap_dbfs / 20)
    peak = np.abs(x).max()
    return x * (cap / peak) if peak > cap else x


def trim_silence(x: np.ndarray, sr: int, thresh_dbfs: float = -45.0,
                 pad_s: float = 0.08) -> np.ndarray:
    """Cut Kokoro's own lead/tail silence so film pauses are exactly ours."""
    win = max(1, sr // 100)
    n = len(x) // win
    rms = np.sqrt(np.mean(x[: n * win].reshape(n, win) ** 2, axis=1))
    loud = np.nonzero(20 * np.log10(np.maximum(rms, 1e-9)) > thresh_dbfs)[0]
    if not len(loud):
        return x
    a = max(0, loud[0] * win - int(pad_s * sr))
    b = min(len(x), (loud[-1] + 1) * win + int(pad_s * sr))
    return x[a:b]


def write_wav(path: Path, x: np.ndarray, sr: int) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())


def read_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as w:
        sr = w.getframerate()
        x = np.frombuffer(w.readframes(w.getnframes()),
                          dtype=np.int16).astype(np.float64) / 32767
    return x, sr


def synth_film(voice: str) -> tuple[np.ndarray, int, list[dict]]:
    """Line-by-line synthesis with designed pauses. Cached in ./work."""
    WORK.mkdir(exist_ok=True)
    all_lines = [(ln, gap, si) for si, sc in enumerate(story.SCENES)
                 for ln, gap in sc["lines"]]
    key_src = "|".join(f"{ln}~{gap}" for ln, gap, _ in all_lines) \
        + f"|{voice}|{SPEED}|{LEAD_S}"
    key = hashlib.sha256(key_src.encode()).hexdigest()[:16]
    cache, meta = WORK / "film-voice.wav", WORK / "film-voice.json"
    if cache.exists() and meta.exists():
        try:
            md = json.loads(meta.read_text(encoding="utf-8"))
            if md.get("key") == key:
                x, sr = read_wav(cache)
                print(f"[voice] cached narration {len(x) / sr:.1f}s ({voice})")
                return x, sr, md["lines"]
        except (json.JSONDecodeError, OSError, wave.Error):
            pass
    models = find_models()
    print("[voice] loading Kokoro (first time takes ~10s)...")
    from kokoro_onnx import Kokoro
    k = Kokoro(str(models / "kokoro-v1.0.onnx"),
               str(models / "voices-v1.0.bin"))
    sr = SR
    parts, lines_meta = [np.zeros(int(LEAD_S * SR))], []
    t = LEAD_S
    for ln, gap, si in all_lines:
        x, sr = k.create(ln, voice=voice, speed=SPEED, lang="en-us")
        clip = trim_silence(np.asarray(x, dtype=np.float64), sr)
        dur = len(clip) / sr
        lines_meta.append({"scene": si, "text": ln, "t0": round(t, 3),
                           "t1": round(t + dur, 3), "gap": gap})
        parts += [clip, np.zeros(int(gap * sr))]
        t += dur + gap
        print(f"  scene {si + 1}: {dur:5.1f}s + {gap:.1f}s pause  "
              f"\"{ln[:44]}{'…' if len(ln) > 44 else ''}\"")
    x = peak_clamp(np.concatenate(parts))
    write_wav(cache, x, sr)
    meta.write_text(json.dumps({"key": key, "voice": voice,
                                "lines": lines_meta}), encoding="utf-8")
    print(f"[voice] narration {len(x) / sr:.1f}s ({voice})")
    return x, sr, lines_meta


def make_samples() -> None:
    models = find_models()
    from kokoro_onnx import Kokoro
    k = Kokoro(str(models / "kokoro-v1.0.onnx"),
               str(models / "voices-v1.0.bin"))
    out_dir = WORK / "voice-samples"
    out_dir.mkdir(parents=True, exist_ok=True)
    for v in PRESET_VOICES:
        x, sr = k.create(SAMPLE_LINE, voice=v, speed=SPEED, lang="en-us")
        write_wav(out_dir / f"{v}.wav",
                  peak_clamp(np.asarray(x, dtype=np.float64)), sr)
        print(f"  {v}.wav  {len(x) / sr:.1f}s")
    print(f"[done] samples -> {out_dir}  (double-click each to listen)")


# ==================================================================== render
def render(out: Path, size: tuple, crf: int, preset: str, audio: Path,
           timeline: list, total: float, arts: list) -> None:
    n_frames = round(total * FPS)
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
           "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{size[0]}x{size[1]}", "-r", str(FPS), "-i", "-",
           "-i", str(audio),
           "-c:v", "libx264", "-crf", str(crf), "-preset", preset,
           "-pix_fmt", "yuv420p", "-movflags", "+faststart",
           "-c:a", "aac", "-b:a", "192k", "-shortest", str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for fi in range(n_frames):
        t = fi / FPS
        chosen = timeline[-1]
        for entry in timeline:
            if entry[2] <= t < entry[3]:
                chosen = entry
                break
        name, idx, t0, t1 = chosen
        art = arts[idx] if name == "scene" else None
        frame = film_frame(name, idx, art, t - t0, t1 - t0, size)
        proc.stdin.write(frame.tobytes())
        if fi % 150 == 0:
            print(f"  frame {fi}/{n_frames} ({t:5.1f}s / {total:.1f}s)",
                  flush=True)
    proc.stdin.close()
    proc.wait()
    if proc.returncode:
        sys.exit(f"ffmpeg failed with code {proc.returncode}")
    print(f"done -> {out}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--proxy", action="store_true", help="fast 640x360 draft")
    ap.add_argument("--voice", default=None,
                    help=f"override voice ({', '.join(PRESET_VOICES)})")
    ap.add_argument("--samples", action="store_true",
                    help="one spoken sample per preset voice, then exit")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    if a.samples:
        make_samples()
        return
    voice = a.voice or story.VOICE

    # guards: story shape + length
    n_words = sum(len(ln.split()) for sc in story.SCENES
                  for ln, _ in sc["lines"])
    if n_words > MAX_WORDS:
        sys.exit(f"story.py has {n_words} narration words — keep your film "
                 f"under {MAX_WORDS}. Short films breathe. Trim and re-run.")
    arts = [_norm_art(sc.get("art", {})) for sc in story.SCENES]

    # 1. the voice is the ruler
    x, sr, lines = synth_film(voice)

    # 2. scene windows from the measured lines (cut inside the pause
    #    BEFORE each scene's first line — the cut lands just ahead of speech)
    starts = []
    for si in range(len(story.SCENES)):
        first = next(l for l in lines if l["scene"] == si)
        prev = [l for l in lines if l["t1"] <= first["t0"]]
        if prev:
            p = prev[-1]
            starts.append(p["t1"] + (first["t0"] - p["t1"]) * 0.55)
        else:
            starts.append(first["t0"] - LEAD_S * 0.35)
    last = lines[-1]
    speech_end = last["t1"] + last["gap"]
    timeline = [("title", 0, 0.0, starts[0])]
    for si in range(len(story.SCENES)):
        t1 = starts[si + 1] if si + 1 < len(starts) else speech_end
        timeline.append(("scene", si, starts[si], t1))
    total = speech_end + CARD_S
    timeline.append(("end", 0, speech_end, total))
    print(f"[fit] {len(story.SCENES)} scenes, narration "
          f"{last['t1'] - LEAD_S:.1f}s -> film {total:.1f}s (audio-first)")

    # 3. full-length audio (voice already includes lead + pauses)
    track = np.zeros(round(total * sr))
    track[:len(x)] = x
    audio = WORK / "film-track.wav"
    write_wav(audio, track, sr)

    # 4. frames -> ffmpeg
    if a.proxy:
        render(Path(a.out or HERE / "my-first-film-proxy.mp4"),
               (640, 360), 28, "veryfast", audio, timeline, total, arts)
    else:
        render(Path(a.out or HERE / "my-first-film.mp4"),
               (1920, 1080), 23, "slow", audio, timeline, total, arts)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()

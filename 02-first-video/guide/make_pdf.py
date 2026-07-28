# -*- coding: utf-8 -*-
"""
make_pdf.py — builds the starter-kit guide PDF, rendered 100% by code
(Pillow only), in the FramesFromCode brand. Output:
guide/FramesFromCode-First-Video.pdf (4 pages, A4 @ 150 dpi).

Run: python guide/make_pdf.py   (from the 02-first-video folder, or anywhere)
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
FONTS = HERE.parent / "fonts"
W, H = 1240, 1754                       # A4 at 150 dpi
M = 110                                 # page margin

# FramesFromCode palette (brand/palette.py)
BG = (13, 17, 23)
PANEL = (26, 30, 36)
LINE = (43, 48, 54)
INK = (230, 237, 243)
DIM = (154, 163, 173)
GREEN = (63, 185, 80)
CYAN = (88, 166, 255)
AMBER = (210, 153, 34)
RED = (248, 81, 73)


def F(name: str, px: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), px)


ARCHIVO = "ArchivoBlack-Regular.ttf"
MONO = "IBMPlexMono-Regular.ttf"
MONO_B = "IBMPlexMono-Bold.ttf"


def new_page() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), BG)
    return img, ImageDraw.Draw(img)


def wrap(d: ImageDraw.ImageDraw, text: str, fnt, max_w: float) -> list[str]:
    words = []
    for word in text.split():             # hard-split tokens wider than a line
        while d.textlength(word, font=fnt) > max_w:
            k = len(word)
            while k > 1 and d.textlength(word[:k], font=fnt) > max_w:
                k -= 1
            words.append(word[:k])
            word = word[k:]
        words.append(word)
    out, cur = [], ""
    for word in words:
        cand = (cur + " " + word).strip()
        if d.textlength(cand, font=fnt) <= max_w:
            cur = cand
        else:
            if cur:
                out.append(cur)
            cur = word
    if cur:
        out.append(cur)
    return out


def para(d, x, y, text, fnt, fill, max_w, lh=1.5) -> float:
    for ln in wrap(d, text, fnt, max_w):
        d.text((x, y), ln, font=fnt, fill=fill)
        y += fnt.size * lh
    return y


def footer(d, page_no: int) -> None:
    f = F(MONO, 26)
    d.line([(M, H - 118), (W - M, H - 118)], fill=LINE, width=2)
    d.text((M, H - 96), "FramesFromCode — starter kit", font=f, fill=DIM)
    tag = f"{page_no} / 4"
    d.text((W - M - d.textlength(tag, font=f), H - 96), tag, font=f, fill=DIM)


def cursor_block(d, x, y, h_px, col=GREEN) -> None:
    d.rectangle([x, y, x + h_px * 0.55, y + h_px], fill=col)


def terminal_panel(d, x0, y0, x1, lines, px=30) -> float:
    """Draw a terminal-style panel with mono lines [(text, color), ...]."""
    f = F(MONO, px)
    pad = 34
    lh = px * 1.62
    wrapped = [(ln, col) for text, col in lines
               for ln in (wrap(d, text, f, x1 - x0 - pad * 2) or [""])]
    y1 = y0 + 66 + lh * len(wrapped) + pad
    d.rounded_rectangle([x0, y0, x1, y1], radius=16, fill=PANEL, outline=LINE,
                        width=2)
    for i, c in enumerate((RED, AMBER, GREEN)):        # window dots
        d.ellipse([x0 + 26 + i * 34, y0 + 22, x0 + 46 + i * 34, y0 + 42],
                  fill=c)
    y = y0 + 66
    for ln, col in wrapped:
        d.text((x0 + pad, y), ln, font=f, fill=col)
        y += lh
    return y1


# ================================================================ page 1
def page_cover() -> Image.Image:
    img, d = new_page()
    # wordmark
    f_mark = F(MONO_B, 40)
    d.text((M, M), "frames", font=f_mark, fill=INK)
    w1 = d.textlength("frames", font=f_mark)
    d.text((M + w1, M), "from", font=f_mark, fill=DIM)
    w2 = d.textlength("from", font=f_mark)
    d.text((M + w1 + w2, M), "code", font=f_mark, fill=GREEN)
    cursor_block(d, M + w1 + w2 + d.textlength("code", font=f_mark) + 14,
                 M + 6, 40)
    # title
    y = 270
    for ln, col in [("RENDER", INK), ("YOUR FIRST", INK), ("FILM", GREEN)]:
        f_t = F(ARCHIVO, 128)
        d.text((M, y), ln, font=f_t, fill=col)
        y += 146
    y += 26
    f_s = F(MONO, 34)
    y = para(d, M, y, "Your computer draws a short film, frame by frame — "
                      "moonlit water, a drifting paper boat — and narrates "
                      "YOUR story with a free offline voice.", f_s, DIM,
             W - 2 * M, 1.6)
    y += 20
    f_b = F(MONO_B, 36)
    items = [("no editor", INK), ("·", DIM), ("no camera", INK), ("·", DIM),
             ("no AI video tools", INK), ("·", DIM), ("$0", AMBER)]
    x = M
    for txt, col in items:
        d.text((x, y), txt, font=f_b, fill=col)
        x += d.textlength(txt, font=f_b) + 18
    # THE caveat — page one, impossible to miss
    y0 = y + 60
    f_h = F(MONO_B, 34)
    f_p = F(MONO, 32)
    d.text((M + 40, y0 + 36), "BEFORE YOU START — the one honest caveat",
           font=f_h, fill=AMBER)
    yy = y0 + 110
    yy = para(d, M + 40, yy,
              "This kit is driven by Claude Code, which needs a PAID Claude "
              "account (claude.com). That is the only non-free thing here — "
              "every tool the kit installs is free and open-source.",
              f_p, INK, W - 2 * M - 80, 1.55)
    yy += 12
    yy = para(d, M + 40, yy,
              "No Claude account? You can still run everything by hand — "
              "page 3.", f_p, DIM, W - 2 * M - 80, 1.55)
    d.rounded_rectangle([M, y0, W - M, yy + 34], radius=16, outline=AMBER,
                        width=3)
    # expectation note — a starter slice, not the full studio
    yb = yy + 54
    d.text((M, yb), "A STARTER SLICE — not the full studio",
           font=f_h, fill=GREEN)
    yb += 46
    para(d, M, yb,
         "For experiencing the workflow, learning step by step. The "
         "channel's films use the full system (page 4), so your renders "
         "will look simpler — that's by design.",
         F(MONO, 30), DIM, W - 2 * M, 1.45)
    footer(d, 1)
    return img


# ================================================================ page 2
def page_steps() -> Image.Image:
    img, d = new_page()
    f_h1 = F(ARCHIVO, 64)
    d.text((M, M), "THREE STEPS", font=f_h1, fill=INK)
    f_n = F(ARCHIVO, 46)
    f_h = F(MONO_B, 36)
    f_p = F(MONO, 32)

    y = M + 140
    # step 1
    d.text((M, y), "1", font=f_n, fill=GREEN)
    d.text((M + 70, y + 4), "Install Claude Code Desktop", font=f_h, fill=INK)
    y += 70
    y = para(d, M + 70, y,
             "Download it at claude.com/claude-code and sign in with your "
             "Claude account. Windows or macOS.", f_p, DIM, W - M - 180, 1.55)
    y += 40
    # step 2
    d.text((M, y), "2", font=f_n, fill=GREEN)
    d.text((M + 70, y + 4), "Paste this one command", font=f_h, fill=INK)
    y += 78
    y = terminal_panel(d, M + 70, y, W - M, [
        ("Clone or download the GitHub repository "
         "framesfromcode/videos to my home directory, then read "
         "02-first-video/SKILL.md inside it and follow it "
         "exactly.", INK),
    ], px=29)
    y += 26
    y = para(d, M + 70, y,
             "Claude Code checks your machine, installs the free tools "
             "(Python, FFmpeg, a ~340 MB offline voice model), and renders "
             "the sample film: \"The Paper Boat\", 55 seconds, drawn and "
             "narrated entirely by your computer.", f_p, DIM,
             W - M - 180, 1.55)
    y += 40
    # step 3
    d.text((M, y), "3", font=f_n, fill=GREEN)
    d.text((M + 70, y + 4), "Then tell it YOUR story", font=f_h, fill=INK)
    y += 70
    y = para(d, M + 70, y,
             "A memory. A bedtime story for your kid. Something you wish "
             "existed. Claude rewrites the screenplay file and your machine "
             "renders it. If your story needs a night train or a city "
             "skyline, Claude draws the new element too. Or ask smaller:",
             f_p, DIM, W - M - 180, 1.42)
    y += 12
    for q in ['"Draw a night train for my father\'s story."',
              '"Let me hear the other narrator voices."',
              '"End at dawn instead."']:
        d.text((M + 70, y), "-", font=f_p, fill=GREEN)
        y = para(d, M + 110, y, q, f_p, INK, W - M - 220, 1.45)
        y += 6
    footer(d, 2)
    return img


# ================================================================ page 3
def page_under_the_hood() -> Image.Image:
    img, d = new_page()
    f_h1 = F(ARCHIVO, 64)
    f_h = F(MONO_B, 36)
    f_p = F(MONO, 32)
    d.text((M, M), "WHAT'S ACTUALLY HAPPENING", font=F(ARCHIVO, 56), fill=INK)
    y = M + 120
    y = para(d, M, y,
             "No editor ever opens. Your whole movie lives in one screenplay "
             "file (story.py): scenes, narration, designed pauses. Each line "
             "is spoken by Kokoro-82M, a free offline text-to-speech model, "
             "measured, and every scene lasts exactly as long as its words — "
             "the same audio-first idea the whole channel runs on. Then a "
             "Python script computes every pixel with numpy + Pillow and "
             "pipes the frames into FFmpeg. Deterministic: the same story "
             "and voice always render the same film, frame for frame.",
             f_p, DIM, W - 2 * M, 1.42)
    y += 30
    d.text((M, y), "Prefer to do it by hand? No Claude needed:", font=f_h,
           fill=INK)
    y += 70
    y = terminal_panel(d, M, y, W - M, [
        ("pip install numpy pillow kokoro-onnx", GREEN),
        ("python get_tts.py            # one-time voice download", INK),
        ("python first_film.py --proxy     # fast draft", INK),
        ("python first_film.py             # full 1080p", INK),
    ], px=30)
    y += 42
    d.text((M, y), "If something goes wrong", font=f_h, fill=INK)
    y += 64
    for sym, fix in [
        ("python is not recognized",
         "reinstall Python with 'Add to PATH' ticked, reopen the terminal"),
        ("No module named kokoro_onnx",
         "pip install kokoro-onnx (same Python that runs the script)"),
        ("ffmpeg is not recognized",
         "restart the terminal after installing FFmpeg"),
    ]:
        d.text((M, y), "x", font=F(MONO_B, 32), fill=RED)
        y = para(d, M + 46, y, sym, F(MONO_B, 31), INK, W - 2 * M - 60, 1.32)
        y = para(d, M + 46, y, fix, f_p, DIM, W - 2 * M - 60, 1.38)
        y += 12
    footer(d, 3)
    return img


# ================================================================ page 4
def page_full_system() -> Image.Image:
    img, d = new_page()
    d.text((M, M), "THIS KIT IS A SLICE", font=F(ARCHIVO, 56), fill=INK)
    d.text((M, M + 78), "OF SOMETHING BIGGER", font=F(ARCHIVO, 56), fill=GREEN)
    f_p = F(MONO, 29)
    f_h = F(MONO_B, 33)
    y = M + 168
    y = para(d, M, y,
             "With this kit you can make as many films as you want — and "
             "grow its night world with anything your story needs. The "
             "pipeline behind the channel's episodes adds the craft that "
             "makes a film feel directed:",
             f_p, DIM, W - 2 * M, 1.4)
    y += 16
    for name, desc in [
        ("the directing hand", "cameras that breathe and tremble, staging, "
                               "micro-events — the film holds your viewer"),
        ("a style library", "proven visual languages — no two films look "
                            "alike"),
        ("music born from code", "a score that knows your story and lands "
                                 "on your biggest line"),
        ("an audience compass", "topics from measured search demand, "
                                "titles tested on live autocomplete — "
                                "films people were already looking for"),
        ("mastering & QC", "broadcast loudness, frame checks — sounds "
                           "like TV"),
    ]:
        d.text((M, y), ">", font=f_h, fill=GREEN)
        d.text((M + 44, y), name, font=f_h, fill=INK)
        y += 44
        y = para(d, M + 44, y, desc, f_p, DIM, W - 2 * M - 88, 1.34)
        y += 4
    y += 12
    y = para(d, M, y,
             "Film is only the first lane — the same pipeline renders "
             "explainers, data stories, science visuals: quieter niches, "
             "lower barriers. More starter kits are on the way.",
             f_p, DIM, W - 2 * M, 1.34)
    y += 12
    y = para(d, M, y,
             "All of it is taught free in the episodes. For everyone "
             "else: a packaged, ready-to-run version is in the works — "
             "everything above, working for you one pasted sentence at "
             "a time. It saves you the research hours, nothing more: "
             "every lesson was paid for in failed renders, and its proof "
             "is the film that brought you here. Grabbed this kit on "
             "Payhip? You're already on the list. No income promises — "
             "tools, not dreams.", f_p, INK, W - 2 * M, 1.34)
    y += 14
    # channel plate — single line
    d.rounded_rectangle([M, y, W - M, y + 96], radius=16, fill=PANEL,
                        outline=LINE, width=2)
    f_mark = F(MONO_B, 40)
    xx = M + 50
    d.text((xx, y + 26), "frames", font=f_mark, fill=INK)
    xx += d.textlength("frames", font=f_mark)
    d.text((xx, y + 26), "from", font=f_mark, fill=DIM)
    xx += d.textlength("from", font=f_mark)
    d.text((xx, y + 26), "code", font=f_mark, fill=GREEN)
    xx += d.textlength("code", font=f_mark) + 40
    d.text((xx, y + 30), "youtube.com/@framesfromcode", font=F(MONO_B, 34),
           fill=CYAN)
    footer(d, 4)
    return img


def main() -> None:
    pages = [page_cover(), page_steps(), page_under_the_hood(),
             page_full_system()]
    out = HERE / "FramesFromCode-First-Film.pdf"
    pages[0].save(out, save_all=True, append_images=pages[1:],
                  resolution=150.0)
    print(f"done -> {out} ({out.stat().st_size / 1e6:.2f} MB)")
    # QC sheet: all pages side by side, small
    thumbs = [p.resize((W // 3, H // 3)) for p in pages]
    sheet = Image.new("RGB", (W // 3 * 4, H // 3), BG)
    for i, tmb in enumerate(thumbs):
        sheet.paste(tmb, (i * W // 3, 0))
    sheet.save(HERE / "qc-pages.png")
    print("QC sheet -> qc-pages.png")


if __name__ == "__main__":
    main()

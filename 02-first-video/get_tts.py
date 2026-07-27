# -*- coding: utf-8 -*-
"""
get_tts.py — download the free offline voice (Kokoro-82M, Apache-2.0).

Two files, ~340 MB total, fetched from the kokoro-onnx GitHub release
(no account, no API key) into ./tts-models/. Run once:

    python get_tts.py

Safe to re-run: files already present with the right size are skipped.
If a download dies mid-way, just run it again.
"""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEST = HERE / "tts-models"
BASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"

# (filename, exact size in bytes — verified 2026-07-27)
FILES = [
    ("kokoro-v1.0.onnx", 325_532_387),   # the speech model
    ("voices-v1.0.bin", 28_214_398),     # the voice pack (54 voices)
]


def fetch(name: str, want: int) -> None:
    out = DEST / name
    if out.exists() and out.stat().st_size == want:
        print(f"  {name:20s} already here — skipped")
        return
    tmp = out.with_suffix(out.suffix + ".part")
    url = f"{BASE}/{name}"
    print(f"  {name:20s} downloading {want / 1e6:.0f} MB ...")
    req = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
    with urllib.request.urlopen(req) as r, open(tmp, "wb") as f:
        done = 0
        while chunk := r.read(1 << 20):
            f.write(chunk)
            done += len(chunk)
            pct = done * 100 // want
            print(f"\r     {pct:3d}%  ({done / 1e6:6.0f} / {want / 1e6:.0f} MB)",
                  end="", flush=True)
    print()
    got = tmp.stat().st_size
    if got != want:
        tmp.unlink(missing_ok=True)
        sys.exit(f"  {name}: got {got} bytes, expected {want} — "
                 "connection dropped? Run get_tts.py again.")
    tmp.replace(out)
    print(f"  {name:20s} OK")


def main() -> None:
    DEST.mkdir(exist_ok=True)
    print(f"[get_tts] -> {DEST}")
    for name, want in FILES:
        fetch(name, want)
    print("[done] voice installed. Next:  python first_video.py --proxy")


if __name__ == "__main__":
    main()

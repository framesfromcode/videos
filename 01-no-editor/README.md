# Episode 01 free pack — the opening montage, ready to render

This folder contains **the exact script that rendered the opening montage** of
"I Make YouTube Videos With No Editor, No AI Video Tools, and $0" — plus a
guide written for someone who has never opened a terminal.

Two commands:

```
git clone https://github.com/framesfromcode/videos
python videos/01-no-editor/montage.py
```

That's it. `montage.mp4` appears next to the script — the same montage you
watched, rendered on your machine.

- Never used a terminal? **Start with [GUIDE.md](GUIDE.md).** It assumes zero
  background: installing Python and FFmpeg, running the script, changing
  colors and text, and what to do when something looks wrong.
- Want a fast draft first? `python montage.py --proxy` renders a small preview
  in under a minute.

No editor. No AI image or video tools. No stock assets. No email wall.
The voice in the episode is a free offline text-to-speech model — not part of
this script, but the same $0 idea.

License: MIT for the code. Fonts are SIL Open Font License 1.1 (files included
in `fonts/`).

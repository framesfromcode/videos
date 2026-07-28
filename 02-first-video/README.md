# Your first film, rendered by your own computer

This is the FramesFromCode **starter kit**: your computer draws a real short
film frame by frame — moonlit water, drifting paper boat, a window burning
warm on a dark shore — and narrates it with a free offline voice. The sample
film is "The Paper Boat" (55 seconds). Then you change the story, and it
becomes **your** film. No editor. No camera. No AI video generators. No
stock assets. **$0.**

## The one command

You don't need to know how to code. Install
[Claude Code Desktop](https://claude.com/claude-code) (it needs a paid Claude
account — that's the one thing here that isn't free), open it, and paste:

```
Clone or download the GitHub repository framesfromcode/videos to my home
directory, then read 02-first-video/SKILL.md inside it and follow it exactly.
```

That's it. Claude Code will check your machine, install the free tools it
needs (Python, FFmpeg, one offline text-to-speech model), render the sample
film — and then ask for YOUR story. Tell it a memory, a bedtime story,
anything: it rewrites the screenplay file and your machine renders your
film. And if your story needs something the night world can't draw yet —
a train, a skyline, falling snow — Claude draws the new element too.

## Doing it by hand instead

Comfortable with a terminal? You don't need Claude Code at all:

```
pip install numpy pillow kokoro-onnx
python get_tts.py                      # one-time, ~340 MB free voice model
python first_film.py --proxy           # fast draft
python first_film.py                   # full 1080p
```

The whole movie lives in `story.py` — scenes, narration, pauses. Edit it
with the element list in `STYLE.md` and re-render.

## What's in the box

| File | What it is |
|---|---|
| `SKILL.md` | The instruction set Claude Code follows — the actual "skill" |
| `first_film.py` | The film engine: night-poster world, deterministic, extendable |
| `story.py` | The screenplay — scenes + narration. This is YOUR file |
| `STYLE.md` | Every knob of the world + craft rules + how to extend it |
| `get_tts.py` | One-time download of the free voice (Kokoro-82M, Apache-2.0) |
| `VOICES.md` | The four preset narrator voices and how to audition them |
| `fonts/` | SIL OFL 1.1 fonts (licenses included) |

This kit is a **starter slice** of the full pipeline the
[FramesFromCode](https://youtube.com/@framesfromcode) channel builds in
public — made for experiencing the workflow and learning it step by step.
The channel's films use the full system, so your renders will look
simpler; that's the slice working as designed, not you failing. The
episodes show the layers this kit leaves out: the film-directing layer
(emotional cameras, staging, micro-events), the proven style library,
code-generated music, mastering, and the audience-research side.

License: MIT for the code · fonts SIL OFL 1.1 · voice model Apache-2.0.
No email wall. Have fun, break it, make it yours.

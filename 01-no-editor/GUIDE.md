# The complete beginner guide — from nothing to your first rendered scene

Written for someone who has **never opened a terminal**. Every step is spelled
out. Nothing here costs money.

## 1. What you're about to do

You'll install two free tools (Python and FFmpeg), download this folder, and
run one command. Your computer will then *draw* a 21-second video, frame by
frame — the same opening montage from the episode. No editor opens. Nothing to
drag or trim. The code decides every pixel.

## 2. Install Python (free)

**Windows**
1. Go to https://www.python.org/downloads/ and click the big yellow button.
2. Run the installer. **IMPORTANT: tick the checkbox "Add python.exe to PATH"**
   on the first screen (bottom of the window) before clicking Install.
3. Done. To check: press the Windows key, type `cmd`, press Enter — a black
   window opens (that's the terminal — you just opened one). Type:
   `python --version` and press Enter. You should see something like
   `Python 3.12.x`.

**macOS**
1. Open the Terminal app (Cmd+Space, type "Terminal", Enter).
2. Type `python3 --version`. If macOS offers to install developer tools,
   accept — that's Python. Otherwise install from python.org as above.
   (On macOS, write `python3` wherever this guide says `python`.)

## 3. Install FFmpeg (free)

FFmpeg is the tool that packs rendered frames into an .mp4 file.

**Windows**
1. Go to https://www.gyan.dev/ffmpeg/builds/ and download
   "ffmpeg-release-essentials.zip".
2. Unzip it somewhere permanent, e.g. `C:\ffmpeg`.
3. Add it to PATH: press Windows key, type "environment variables", open it →
   "Environment Variables…" → under "User variables" select `Path` → Edit →
   New → paste `C:\ffmpeg\bin` → OK everywhere.
4. Close and reopen your terminal, then check: `ffmpeg -version`.

**macOS**
1. In Terminal: install Homebrew if you don't have it (instructions at
   https://brew.sh — one paste-and-run command), then: `brew install ffmpeg`.

## 4. Get this folder

If you know git: `git clone https://github.com/framesfromcode/videos`.
If not: on the GitHub page, click the green **Code** button → **Download ZIP**,
then unzip it somewhere you can find, e.g. your Desktop.

## 5. Install the two Python libraries

In your terminal:

```
pip install numpy pillow
```

(macOS: `pip3 install numpy pillow`.)

## 6. Render

In the terminal, move into the folder and run the script:

```
cd Desktop/videos/01-no-editor
python montage.py --proxy
```

`cd` means "change directory" — adjust the path to wherever you unzipped.
`--proxy` renders a small fast draft (about a minute). When it finishes,
`montage-proxy.mp4` is sitting next to the script. Double-click it.

For the full-quality 1080p version (a few minutes):

```
python montage.py
```

**You just made a video with no editor.** That's the whole trick from the
episode, in your hands.

## 7. Make it yours

Open `montage.py` in any text editor (Notepad works). Everything interesting
is near the top:

- **Colors** — the `BG / INK / GREEN / CYAN / AMBER` lines. Each is a
  red-green-blue triple, 0–255. Try `GREEN = (255, 120, 60)` and re-render.
- **Cities and the map** — the `CITIES` list: names and x/y positions
  (the frame is 1920 wide, 1080 tall). Rename them, move them, add one.
- **The words that slam on the beat** — the `WORDS` list in scene 3.
- **Scene lengths** — the `SCENES` list at the top: `("map", 4.62)` means the
  map scene lasts 4.62 seconds. Change any number; everything adapts. In the
  episode these numbers are locked to the narration — that's the audio-first
  workflow: measure the voice, then draw pictures that are *born fitting*.
- **The smoke, the chart data, the rain** — all just numbers in the scene
  functions. Change them, re-render, see what happens. You cannot break
  anything: delete the folder and unzip again if you make a mess.

Re-render with `--proxy` after each change — fast feedback is the whole game.

## 8. When something looks wrong

| Symptom | Likely cause & fix |
|---|---|
| `python` is not recognized | PATH checkbox missed on install. Re-run the Python installer → "Modify" → tick "Add to PATH". Then reopen the terminal. |
| `No module named numpy` | Run `pip install numpy pillow` (step 5). If pip is missing, reinstall Python. |
| `ffmpeg failed` or `ffmpeg` not recognized | FFmpeg not on PATH (step 3). Reopen the terminal after editing PATH. |
| Video renders but is black / weird colors | You probably edited a color to an invalid value. Colors are `(0–255, 0–255, 0–255)`. |
| Text overlaps or runs off screen | You made a font size or a label much bigger — reduce the number you changed. |
| It's slow | Normal: the full render draws 631 frames one by one. Use `--proxy` while experimenting. |
| Fonts error | Keep the `fonts/` folder next to `montage.py` — the script loads them from there. |

## 9. What's next

Next episode: a first render from a completely blank folder — one scene,
explained line by line. Same rule as always: result first, then the full
recipe, free.

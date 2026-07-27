# The locked style: "night poster" — every knob

Your film is drawn in ONE visual style: a quiet, poster-flat night world in
a 2.35:1 letterbox film frame. You don't pick a style — you pick what's in
the frame. Everything below goes in a scene's `"art"` dict in `story.py`.

All elements are optional. Coordinates are fractions of the frame
(x: 0 = left, 1 = right · y: 0 = top, 1 = bottom).

| Element | Example | What it does |
|---|---|---|
| `palette` | `"night"` (default) or `"dawn"` | The whole scene's mood: deep blue night, or warm first light |
| `moon` | `{"x":0.74,"y":0.20,"r":0.045}` | Moon with glow. Bigger `r` + lower `y` = the classic big-moon shot |
| `stars` | `1.3` | Star density multiplier (default 1.0) |
| `clouds` | `0.35` | Drifting cloud cover, 0–1 |
| `mountains` | `2` or `[{"base":0.55},{"base":0.68}]` | Ridge layers, far to near; `base` = height of the ridge line |
| `water` | `{"y":0.60,"glitter":True}` | Water from `y` down. `glitter` draws the moon's road on it (needs a moon) |
| `hill` | `{"x":0.24,"h":0.15}` | Foreground hill — gives the cabin and figure ground to stand on |
| `cabin` | `{"x":0.22,"scale":1.0,"smoke":True}` | Small house, one warm lit window; optional chimney smoke |
| `boat` | `{"x":0.44,"scale":1.1,"drift":0.02,"sail_text":"..."}` | The paper boat. `drift` = movement per second; `sail_text` shows writing on the sail when `scale >= 1.4` |
| `figure` | `{"x":0.30,"scale":1.0}` | A standing silhouette — on the hill if there is one, else on a small bank by the water |
| `fireflies` | `6` | Warm drifting sparks |
| `push` | `True` | Slow camera push-in. Use ONCE, on your most important shot |

## The craft rules that make it feel like a film

1. **Audio first.** Each scene lasts exactly as long as its lines + pauses.
   Long pause (2.5–3.5s) after the biggest line — let it land.
2. **5–9 scenes, under ~150 narration words.** Short films breathe.
3. **One push.** If everything pushes in, nothing does.
4. **Big things read, small things decorate.** One clear subject per scene
   (a boat, a window, a figure) — the rest is atmosphere.
5. **End on a change.** The `dawn` palette exists so your last scene can
   feel different from your first.

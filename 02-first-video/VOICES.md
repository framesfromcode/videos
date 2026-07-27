# The narrator voices

Four free offline voices ship preset in this kit (all from Kokoro-82M —
the model `get_tts.py` installs; 54 voices are actually inside it):

| Preset | Character |
|---|---|
| `bm_george` | calm British male — the default storyteller |
| `af_heart` | warm US female |
| `af_bella` | bright US female |
| `am_puck` | light US male |

**Audition them:** `python first_film.py --samples` renders one spoken line
per preset into `work/voice-samples/` — double-click each to listen.

**Switch:** change `VOICE = "bm_george"` in `story.py` (or render once with
`--voice af_heart`), then re-render.

Speed stays at `1.0`; each line is synthesized separately and joined with
the pauses designed in your screenplay — that's what gives the narration
its film pacing. The full FramesFromCode pipeline runs a proper blind
listening test across all 54 voices to pick a channel voice — one of the
layers this starter kit keeps simple on purpose.

# -*- coding: utf-8 -*-
# story.py — YOUR film. This file is the whole movie: what the voice says,
# and what's on screen. Change it, re-render, watch your own story.
#
#   python first_film.py --proxy     -> fast draft
#   python first_film.py             -> full 1080p film
#
# HOW IT WORKS
# - The film is a list of SCENES. Each scene = "art" (what's drawn) +
#   "lines" (what the voice says while that scene is on screen).
# - A line is ("sentence", pause_after_in_seconds). Pauses are part of the
#   filmmaking: a long pause after a big moment lets it land.
# - The film is audio-first: each scene lasts exactly as long as its lines.
# - "art" uses the locked night-poster style. Available elements (all
#   optional): palette ("night" or "dawn"), moon, stars, clouds, mountains,
#   water, hill, cabin, boat, figure, fireflies, push (slow camera push-in
#   for your most important shot). See STYLE.md for every knob.
#
# Keep the whole story under ~150 words. Short films breathe.

TITLE = "The Paper Boat"
VOICE = "bm_george"   # presets: bm_george, af_heart, af_bella, am_puck

SCENES = [
    # 1 — the lakeside house, late
    {
        "art": {
            "moon": {"x": 0.80, "y": 0.18, "r": 0.035},
            "mountains": 2,
            "water": {"y": 0.64},
            "hill": {"x": 0.24, "h": 0.15},
            "cabin": {"x": 0.22, "smoke": True},
            "fireflies": 6,
        },
        "lines": [
            ("When the house went quiet, the boy slipped down to the "
             "water with a boat folded from yesterday's newspaper.", 1.6),
        ],
    },
    # 2 — the launch
    {
        "art": {
            "moon": {"x": 0.76, "y": 0.20, "r": 0.04},
            "mountains": 1,
            "water": {"y": 0.56},
            "figure": {"x": 0.30, "scale": 1.0},
            "boat": {"x": 0.44, "scale": 1.1, "drift": 0.010},
        },
        "lines": [
            ("He set it down, and gave it the gentlest push.", 1.8),
        ],
    },
    # 3 — open water
    {
        "art": {
            "moon": {"x": 0.70, "y": 0.16, "r": 0.035},
            "clouds": 0.35,
            "mountains": 2,
            "water": {"y": 0.50},
            "boat": {"x": 0.30, "scale": 0.9, "drift": 0.045},
        },
        "lines": [
            ("The wind took it from there.", 2.0),
        ],
    },
    # 4 — past the mountains
    {
        "art": {
            "mountains": 3,
            "water": {"y": 0.70},
            "boat": {"x": 0.46, "scale": 0.6, "drift": 0.025},
            "cabin": {"x": 0.84, "scale": 0.55},
            "stars": 1.3,
        },
        "lines": [
            ("Past the sleeping mountains, past the last lit window "
             "on the shore.", 1.8),
        ],
    },
    # 5 — THE shot: crossing the moon's road (that's why it gets the push)
    {
        "art": {
            "moon": {"x": 0.60, "y": 0.28, "r": 0.062},
            "water": {"y": 0.52, "glitter": True},
            "boat": {"x": 0.30, "scale": 1.0, "drift": 0.050},
            "push": True,
        },
        "lines": [
            ("And straight through the moon's silver road.", 2.6),
        ],
    },
    # 6 — the message
    {
        "art": {
            "moon": {"x": 0.78, "y": 0.16, "r": 0.035},
            "water": {"y": 0.52},
            "boat": {"x": 0.50, "scale": 1.7, "drift": 0.006,
                     "sail_text": "come home soon, Grandpa"},
            "fireflies": 3,
        },
        "lines": [
            ("It sailed all night, carrying four small words on its "
             "sail:", 1.2),
            ("Come home soon, Grandpa.", 2.8),
        ],
    },
    # 7 — the far shore, first light
    {
        "art": {
            "palette": "dawn",
            "mountains": 1,
            "water": {"y": 0.60},
            "boat": {"x": 0.42, "scale": 0.9, "drift": 0.0},
            "figure": {"x": 0.30, "scale": 1.05},
        },
        "lines": [
            ("On the far shore, an old man found it at first light.", 1.5),
            ("He read it twice, folded it into his coat, and started "
             "walking home.", 2.2),
        ],
    },
]

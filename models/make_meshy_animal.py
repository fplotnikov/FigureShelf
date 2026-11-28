"""
Figure Shelf - turn a Meshy auto-rigged animal into an app-ready figure with OUR moves
(Blender 5.x, headless).  "Meshy look, our own moves."

Usage:
  blender -b --factory-startup --python make_meshy_animal.py -- kitty [--no-render]

Input   models/meshy_<name>/<name>_rigged.glb   (Meshy rig task output, T-pose, cm armature)
Output  models/<name>.usdz, models/<name>_clips.json (clip ranges + accessory fit),
        models/<name>_skins/<name>_skin_<skin>.png (one 1024px base colour per app skin),
        models/<name>.blend, previews/<name>_*.png

Steps
  1. Convert Meshy's centimetre armature to metres, add a ground "root" bone (for hops and
     squash), and add ear (2 bones each) and tail (3 bones) chains, weighted by region.
  2. Bake toy-style clips like make_bunny.py into one 30 fps timeline with the Bunny's
     frame layout: idle 1-60, dance 61-180, jump 181-252, run 253-372, wave 373-444.
     Every clip starts and ends in the same relaxed pose, so clips loop and blend.
  3. Recolour the painted texture once per app skin (main fur and belly regions are found
     from colours sampled on the model; eyes, nose, inner ears keep their colours).
  4. Measure where hats, glasses and bow ties go and write it into the clips JSON.
  5. Export Y-up, facing +Z, no lights, ARKit-valid (material "Skin").
Per-animal regions live in ANIMALS below (metres, Blender axes: X = animal's left,
-Y = front, Z = up).  Probe a new model and add an entry.
"""
import bpy, bmesh, itertools, json, math, os, sys, subprocess
import numpy as np
from mathutils import Vector, Matrix, Euler, Quaternion

HERE = os.path.dirname(os.path.abspath(__file__))
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
NAME = ARGS[0] if ARGS and not ARGS[0].startswith("--") else "kitty"
DO_RENDER = "--no-render" not in ARGS
SRC = os.path.join(HERE, "meshy_" + NAME)
FPS = 30
TEX_SIZE = 1024

def box(x, y, z):
    return dict(x=x, y=y, z=z)

ANIMALS = {
    "kitty": dict(
        ears=dict(L=box((0.02, 0.07), (-0.035, 0.035), (0.165, 0.25)),
                  R=box((-0.07, -0.02), (-0.035, 0.035), (0.165, 0.25)),
                  base_z=0.174),
        # the tail rises out of the back (narrow column) and curls along the floor to the left
        tail=dict(region=[box((-0.02, 0.07), (0.02, 0.08), (-0.01, 0.03)),
                          box((-0.007, 0.007), (0.024, 0.045), (0.025, 0.042))], root_min_z=0.033),
        ear_amp=1.0, tail_amp=1.0,
    ),
    "bear": dict(   # small round ears, little stub tail
        ears=dict(L=box((0.028, 0.075), (-0.03, 0.03), (0.176, 0.25)),
                  R=box((-0.075, -0.028), (-0.03, 0.03), (0.176, 0.25)), base_z=0.181),
        tail=dict(region=box((-0.019, 0.019), (0.027, 0.07), (0.032, 0.078)), root="min_y"),
        ear_amp=0.45, tail_amp=0.6,
    ),
    "penguin": dict(ears=None, tail=None, arm_down=68),   # flippers are the arms
    "frog": dict(ears=None, tail=None),                    # eyes on top, no ears or tail
    "fox": dict(    # pointed ears (head sits slightly to -x), big tail curving to the left
        ears=dict(L=box((0.004, 0.07), (-0.04, 0.03), (0.168, 0.25)),
                  R=box((-0.075, -0.016), (-0.04, 0.03), (0.168, 0.25)), base_z=0.174),
        tail=dict(region=box((-0.012, 0.1), (0.03, 0.1), (-0.01, 0.105)), root="min_y"),
        ear_amp=0.75, tail_amp=0.8,
    ),
    "bunny": dict(  # two long upright ears, cotton tail to the left
        ears=dict(L=box((0.002, 0.045), (-0.03, 0.02), (0.146, 0.25)),
                  R=box((-0.045, -0.002), (-0.03, 0.02), (0.146, 0.25)), base_z=0.149),
        tail=dict(region=box((-0.004, 0.045), (0.028, 0.07), (0.02, 0.062)), root="min_y"),
        ear_amp=1.2, tail_amp=0.5,
    ),
}
# Fedir's robots (Meshy model + Meshy auto-rig, our moves). Each changes into a vehicle when it
# runs (models/make_vehicle.py makes <name>_vehicle.usdz; the app does the change and the travel).
ROBOTS = ("supercar", "jet", "motorcycle", "truck", "helicopter", "rally", "seaplane",
          "snowmobile", "excavator", "speedboat",
          # second set (Nov 2026)
          "locomotive", "submarine", "tractor", "citybus", "forklift", "cablecar", "lunarrover", "airship")
ROBOT_HEIGHT = 0.25   # animatronics use 0.24 (set below)
# Fedir's animatronics: same path as the robots (Meshy model + auto-rig), no vehicle, and every
# move is "servo" style: hold a pose, snap to the next with a tiny overshoot and settle.
ANIMATRONICS = ("raccoon", "moth", "crocodile", "ram", "pelican", "armadillo", "lynx",
                "frogsinger", "vulture", "anteater",
                # second set (Nov 2026); the ostrich uses our own creature rig (see CREATURES)
                "showelephant", "pangolin", "lobster", "chameleon", "walrus", "showkangaroo", "sloth")
IS_ANIMATRONIC = NAME in ANIMATRONICS
# More animals (Meshy design + model + auto-rig, our usual animal moves) and the two-legged
# dinosaurs and Pteranodon (same, with dinosaur touches). Four-legged dinosaurs use the
# creature path (our own quadruped rig, CREATURES below).
ANIMALS2 = ("lion", "zebra", "ostrich", "horse", "tiger", "beaver", "raccoonkid", "elephant",
            "hippo", "rhino", "mouse", "turtle",
            # third batch (Nov 2026): same path
            "shark", "mole", "bee", "parrot", "koala", "panda",
            # fourth batch (Nov 22, 2026): same path
            "deer", "redpanda", "moose", "kangaroo", "giraffe", "capybara")
DINO_BIPEDS = ()   # dinosaurs now use our own creature rig (CREATURES, auto=True)
IS_ANIMAL2 = NAME in ANIMALS2
IS_DINO = NAME in DINO_BIPEDS
CFG = ANIMALS.get(NAME) or (dict(ears=None, tail=None, robot=True)
                            if (NAME in ROBOTS or IS_ANIMATRONIC or IS_ANIMAL2 or IS_DINO) else {})
IS_ROBOT = NAME in ROBOTS or IS_ANIMATRONIC or IS_ANIMAL2 or IS_DINO   # shared: toy size, hue skins, thumbnail
if IS_ANIMATRONIC:
    ROBOT_HEIGHT = 0.24
if IS_ANIMAL2:
    ROBOT_HEIGHT = 0.2      # like the first six animals
if IS_DINO:
    ROBOT_HEIGHT = 0.2

# app skins (Model.swift Skin.colors); "natural" keeps the painted texture
SKINS = {
    "sunny": (0xFFD45C, 0xFFF4C7), "ocean": (0x5DA9E9, 0xD6ECFF), "mint": (0x7FD8BE, 0xE8FFF7),
    "berry": (0xC86FC9, 0xFBE3FB), "galaxy": (0x3D3A8C, 0xB9B2FF), "snow": (0xF7F7F7, 0xDDE3EA),
}

TAU = math.tau

def ss(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a))) if b != a else float(x >= a)
    return t * t * (3 - 2 * t)

def smooth_(x):
    x = min(1.0, max(0.0, x)); return x * x * (3 - 2 * x)

def env(t, r):
    return ss(0, r, t) * ss(1, 1 - r, t)

def in_box(p, b):
    return b["x"][0] <= p.x <= b["x"][1] and b["y"][0] <= p.y <= b["y"][1] and b["z"][0] <= p.z <= b["z"][1]

# ==========================================================================
# CREATURES (Fedir's imaginary creatures): Meshy static model + OUR OWN rig
#
#   blender -b --factory-startup --python make_meshy_animal.py -- mosskip [--no-render]
#
# Input   models/creatures/<name>/<name>_static.glb  (Meshy image-to-3D, no Meshy rig)
# Output  models/<name>.usdz, <name>_clips.json, <name>_skins/*.jpg, <name>_thumb.png,
#         previews/<name>_*.png, previews/<name>_rigcheck.png
#
# The rig is built here, not by Meshy:
#   * the model is turned so its body runs along -Y ("aligned frame"), scaled to SIZE on its
#     longest side, feet on the floor;
#   * spine (Hips, Spine, Chest, neck, Head) and chains (ears, tails, wings, arms) come from
#     points measured on probe renders (probe_creature.py) in that aligned frame;
#   * legs are found automatically: below the belly line every leg is its own connected
#     piece of the mesh, so each piece becomes a 2-bone leg (3 bones for tentacles);
#   * skin weights: Blender bone heat on a seam-welded copy, copied back to the real mesh;
#   * one shared set of moves per body kind (quad / otter / biped / bat / squid) with the
#     animals' clip layout: idle 1-60, dance 61-180, jump 181-252, run 253-372, wave 373-444;
#   * finally everything is turned back by -yaw so the figure stands like Fedir's picture.
# Colors: "natural" is the Meshy texture as is; other skins rotate the hue of the whole
# texture (neutral greys, whites and black eyes barely change), Night darkens, Snow fades.
# ==========================================================================
def V(*a):
    return Vector(a)

CREATURES = {
    # kind, yaw (deg) that aligns the body to -Y, size (m, longest side after aligning)
    "mosskip": dict(kind="quad", yaw=18, size=0.22,
        eyes=(-0.022, -0.065, 0.112), eye_dx=0.014, face=-15,   # eye midpoint (aligned frame), half spacing, face turn (deg, picture frame)
        spine=[(-0.01, 0.05, 0.075), (-0.02, -0.03, 0.075), (-0.022, -0.045, 0.088),
               (-0.022, -0.055, 0.097), (-0.022, -0.085, 0.112)],
        chains={"ear_L": ("Head", [(0.008, -0.05, 0.123), (0.04, 0.01, 0.155), (0.07, 0.07, 0.175)]),
                "ear_R": ("Head", [(-0.034, -0.052, 0.123), (-0.04, -0.015, 0.17), (-0.0425, 0.025, 0.2175)]),
                "tail": ("Hips", [(0.0, 0.05, 0.088), (0.018, 0.06, 0.112), (0.025, 0.066, 0.135)]),
                # mid-leap: two paws are off the floor, so the legs are placed by hand (snapped)
                "leg_FR": ("Chest", [(-0.03, -0.035, 0.06), (-0.04, -0.06, 0.045), (-0.042, -0.08, 0.035)]),
                "leg_FL": ("Chest", [(-0.012, -0.028, 0.06), (-0.03, -0.03, 0.035), (-0.05, -0.032, 0.012)]),
                "leg_BL": ("Hips", [(0.0, 0.03, 0.062), (-0.015, 0.04, 0.03), (-0.025, 0.045, 0.008)]),
                "leg_BR": ("Hips", [(0.012, 0.05, 0.062), (0.008, 0.07, 0.04), (0.005, 0.09, 0.022)])},
        legs=None),
    "glassfin": dict(kind="otter", yaw=45, size=0.22, tail_amp=0.35, tail_lift=0.0,   # stands on its tail fin
        eyes=(0.015, -0.035, 0.16), eye_dx=0.013, face=25,   # eye midpoint (aligned frame), half spacing, face turn (deg, picture frame)
        spine=[(0.0, 0.07, 0.11), (0.0, -0.02, 0.108), (0.0, -0.035, 0.138),
               (0.0, -0.045, 0.155), (0.0, -0.078, 0.162)],
        chains={"tail": ("Hips", [(0.04, 0.08, 0.11), (0.085, 0.1, 0.075), (0.09, 0.08, 0.04),
                                   (0.075, 0.03, 0.022), (0.065, -0.035, 0.03)]),
                "leg_FL": ("Chest", [(0.02, -0.025, 0.118), (0.02, -0.045, 0.098), (0.022, -0.06, 0.08)]),
                "leg_FR": ("Chest", [(-0.03, -0.025, 0.122), (-0.05, -0.045, 0.1), (-0.06, -0.058, 0.09)])},
        legs=None),
    "cindermole": dict(kind="biped", yaw=0, size=0.22,
        eyes=(0.0, -0.075, 0.14), eye_dx=0.016, face=0,   # eye midpoint (aligned frame), half spacing, face turn (deg, picture frame)
        spine=[(0.0, 0.02, 0.05), (0.0, -0.03, 0.105), (0.0, -0.05, 0.12),
               (0.0, -0.06, 0.128), (0.0, -0.1, 0.146)],
        chains={"arm_L": ("Chest", [(0.045, -0.035, 0.1), (0.06, -0.07, 0.075), (0.055, -0.1, 0.04)]),
                "arm_R": ("Chest", [(-0.045, -0.035, 0.1), (-0.06, -0.07, 0.075), (-0.055, -0.1, 0.04)]),
                "tail": ("Hips", [(0.0, 0.05, 0.035), (0.0, 0.08, 0.035), (0.0, 0.11, 0.04)]),
                "leg_BL": ("Hips", [(0.035, 0.0, 0.045), (0.05, -0.01, 0.022), (0.062, -0.02, 0.006)]),
                "leg_BR": ("Hips", [(-0.035, 0.0, 0.045), (-0.05, -0.01, 0.022), (-0.062, -0.02, 0.006)])},
        legs=None),
    "cloudlope": dict(kind="quad", yaw=45, size=0.22,
        eyes=(0.02, -0.03, 0.148), eye_dx=0.014, face=20,   # eye midpoint (aligned frame), half spacing, face turn (deg, picture frame)
        spine=[(0.0, 0.065, 0.085), (0.0, -0.03, 0.095), (0.0, -0.035, 0.115),
               (0.0, -0.03, 0.13), (0.03, -0.03, 0.145)],
        chains={"ear_L": ("Head", [(0.0, -0.035, 0.13), (0.0, -0.065, 0.11), (-0.01, -0.085, 0.07)]),
                "ear_R": ("Head", [(0.01, -0.015, 0.13), (0.03, 0.035, 0.125), (0.04, 0.08, 0.1)]),
                "tail": ("Hips", [(0.0, 0.07, 0.085), (0.0, 0.09, 0.075), (0.0, 0.105, 0.065)]),
                "leg_FL": ("Chest", [(0.009, -0.025, 0.062), (0.009, -0.025, 0.03), (0.009, -0.025, 0.006)]),
                "leg_FR": ("Chest", [(-0.022, -0.027, 0.062), (-0.023, -0.027, 0.03), (-0.024, -0.0275, 0.006)]),
                "leg_BL": ("Hips", [(0.02, 0.05, 0.062), (0.02, 0.05, 0.03), (0.02, 0.051, 0.006)]),
                "leg_BR": ("Hips", [(-0.022, 0.047, 0.062), (-0.022, 0.047, 0.03), (-0.0225, 0.0475, 0.006)])},
        legs=None),
    "thimblebat": dict(kind="bat", yaw=0, size=0.22,
        eyes=(0.005, -0.028, 0.093), eye_dx=0.017, face=0,   # eye midpoint (aligned frame), half spacing, face turn (deg, picture frame)
        spine=[(0.005, 0.005, 0.035), (0.005, 0.0, 0.07), (0.005, -0.005, 0.08),
               (0.005, -0.01, 0.086), (0.005, -0.03, 0.11)],
        chains={"wing_L": ("Chest", [(0.025, 0.01, 0.075), (0.065, 0.01, 0.09), (0.105, 0.01, 0.075)]),
                "wing_R": ("Chest", [(-0.02, 0.01, 0.075), (-0.06, 0.01, 0.09), (-0.1, 0.01, 0.075)]),
                "ear_L": ("Head", [(0.02, -0.005, 0.12), (0.03, 0.0, 0.14), (0.035, 0.0, 0.157)]),
                "ear_R": ("Head", [(-0.015, -0.005, 0.12), (-0.028, 0.0, 0.135), (-0.035, 0.0, 0.142)]),
                "leg_BL": ("Hips", [(0.02, 0.0, 0.035), (0.022, 0.0, 0.018), (0.0225, -0.005, 0.004)]),
                "leg_BR": ("Hips", [(-0.025, 0.0, 0.035), (-0.027, 0.0, 0.018), (-0.0275, -0.005, 0.004)])},
        legs=None),
    "pebblenewt": dict(kind="quad", yaw=10, size=0.23,
        eyes=(-0.012, -0.09, 0.045), eye_dx=0.013, face=-5,   # eye midpoint (aligned frame), half spacing, face turn (deg, picture frame)
        spine=[(0.015, 0.02, 0.045), (-0.008, -0.05, 0.045), (-0.012, -0.07, 0.044),
               (-0.015, -0.08, 0.043), (-0.015, -0.108, 0.036)],
        chains={"tail": ("Hips", [(0.02, 0.03, 0.05), (0.035, 0.06, 0.065), (0.03, 0.09, 0.09),
                                   (0.02, 0.095, 0.12), (-0.03, 0.07, 0.13)]),
                "leg_FL": ("Chest", [(0.012, -0.06, 0.03), (0.022, -0.07, 0.015), (0.027, -0.075, 0.004)]),
                "leg_FR": ("Chest", [(-0.02, -0.055, 0.03), (-0.04, -0.06, 0.015), (-0.05, -0.067, 0.004)]),
                "leg_BL": ("Hips", [(0.025, 0.01, 0.03), (0.04, 0.012, 0.015), (0.05, 0.0125, 0.004)]),
                "leg_BR": ("Hips", [(-0.01, 0.03, 0.03), (-0.022, 0.033, 0.015), (-0.03, 0.035, 0.004)])},
        legs=None),
    "bloomusk": dict(kind="quad", yaw=47, size=0.23,
        eyes=(0.035, -0.07, 0.1), eye_dx=0.015, face=-10,   # eye midpoint (aligned frame), half spacing, face turn (deg, picture frame)
        spine=[(-0.01, 0.06, 0.09), (0.0, -0.02, 0.095), (0.02, -0.05, 0.105),
               (0.03, -0.06, 0.105), (0.04, -0.09, 0.095)],
        chains={"tail": ("Hips", [(0.0, 0.08, 0.085), (0.0, 0.09, 0.06), (0.0, 0.095, 0.03)]),
                "leg_FL": ("Chest", [(0.02, -0.0425, 0.05), (0.02, -0.0425, 0.025), (0.02, -0.0425, 0.005)]),
                "leg_FR": ("Chest", [(-0.03, -0.05, 0.05), (-0.03, -0.05, 0.025), (-0.03, -0.05, 0.005)]),
                "leg_BL": ("Hips", [(0.019, 0.0525, 0.05), (0.019, 0.0525, 0.025), (0.019, 0.0525, 0.005)]),
                "leg_BR": ("Hips", [(-0.0275, 0.0425, 0.05), (-0.0275, 0.0425, 0.025), (-0.0275, 0.0425, 0.005)])},
        legs=None),
    "velvetide": dict(kind="squid", yaw=0, size=0.22,
        eyes=(0.0, -0.075, 0.133), eye_dx=0.016, face=15,   # eye midpoint (aligned frame), half spacing, face turn (deg, picture frame)
        spine=[(0.0, 0.08, 0.09), (0.0, -0.02, 0.1), (0.0, -0.045, 0.12),
               (0.0, -0.055, 0.125), (0.0, -0.09, 0.14)],
        chains={"ear_L": ("Head", [(0.02, -0.05, 0.135), (0.04, -0.05, 0.155), (0.055, -0.05, 0.165)]),
                "ear_R": ("Head", [(-0.0225, -0.05, 0.135), (-0.04, -0.05, 0.152), (-0.05, -0.05, 0.16)]),
                "tent_L1": ("Chest", [(0.03, -0.06, 0.06), (0.042, -0.06, 0.035), (0.05, -0.06, 0.012), (0.0475, -0.0575, 0.006)]),
                "tent_L2": ("Hips", [(0.03, -0.015, 0.06), (0.048, -0.015, 0.035), (0.058, -0.015, 0.012), (0.06, -0.015, 0.006)]),
                "tent_L3": ("Hips", [(0.03, 0.03, 0.06), (0.045, 0.03, 0.035), (0.055, 0.032, 0.012), (0.0575, 0.0325, 0.006)]),
                "tent_R1": ("Chest", [(-0.03, -0.06, 0.06), (-0.042, -0.06, 0.035), (-0.05, -0.06, 0.012), (-0.05, -0.06, 0.006)]),
                "tent_R2": ("Hips", [(-0.03, -0.015, 0.06), (-0.05, -0.015, 0.035), (-0.06, -0.015, 0.012), (-0.0675, -0.015, 0.006)]),
                "tent_R3": ("Hips", [(-0.03, 0.03, 0.06), (-0.045, 0.03, 0.035), (-0.052, 0.03, 0.012), (-0.055, 0.03, 0.006)])},
        legs=None),
    "lanternquill": dict(kind="quad", yaw=0, size=0.22,
        eyes=(0.0, -0.065, 0.12), eye_dx=0.017, face=0,   # eye midpoint (aligned frame), half spacing, face turn (deg, picture frame)
        spine=[(0.0, 0.05, 0.08), (0.0, -0.02, 0.09), (0.0, -0.04, 0.11),
               (0.0, -0.06, 0.122), (0.0, -0.107, 0.125)],
        chains={"leg_FL": ("Chest", [(0.035, -0.045, 0.05), (0.045, -0.047, 0.025), (0.05, -0.0475, 0.005)]),
                "leg_FR": ("Chest", [(-0.035, -0.045, 0.05), (-0.043, -0.047, 0.025), (-0.0475, -0.0475, 0.005)]),
                "leg_BL": ("Hips", [(0.035, 0.045, 0.05), (0.043, 0.045, 0.025), (0.0475, 0.045, 0.005)]),
                "leg_BR": ("Hips", [(-0.035, 0.045, 0.05), (-0.042, 0.045, 0.025), (-0.045, 0.045, 0.005)])},
        legs=None),
    "dunewisp": dict(kind="quad", yaw=-70, size=0.22,
        eyes=(-0.015, -0.065, 0.1), eye_dx=0.013, face=20,   # eye midpoint (aligned frame), half spacing, face turn (deg, picture frame)
        spine=[(0.0, 0.015, 0.075), (0.0, -0.035, 0.075), (0.0, -0.045, 0.09),
               (-0.01, -0.06, 0.105), (-0.01, -0.075, 0.1)],
        chains={"ear_L": ("Head", [(0.0, -0.05, 0.125), (0.0, -0.04, 0.15), (0.0, -0.035, 0.175)]),
                "ear_R": ("Head", [(-0.01, -0.06, 0.125), (-0.02, -0.08, 0.15), (-0.02, -0.09, 0.175)]),
                "tail": ("Hips", [(0.0, 0.02, 0.08), (0.0, 0.05, 0.11), (0.0, 0.07, 0.15), (0.0, 0.09, 0.17)]),
                "tailB": ("Hips", [(-0.01, 0.02, 0.075), (-0.04, 0.03, 0.07), (-0.06, 0.03, 0.05)]),
                "tailC": ("Hips", [(0.01, 0.02, 0.08), (0.04, 0.04, 0.1), (0.07, 0.045, 0.11)]),
                "leg_FL": ("Chest", [(0.008, -0.05, 0.07), (0.01, -0.06, 0.035), (0.01, -0.0675, 0.005)]),
                "leg_FR": ("Chest", [(-0.008, -0.05, 0.07), (-0.008, -0.068, 0.055), (-0.01, -0.08, 0.037)]),
                "leg_BL": ("Hips", [(0.015, 0.0, 0.07), (0.022, -0.008, 0.035), (0.0275, -0.016, 0.005)]),
                "leg_BR": ("Hips", [(0.0, 0.02, 0.07), (-0.005, 0.028, 0.035), (-0.0085, 0.0325, 0.005)])},
        legs=None),
}


# realistic dinosaurs (models/creatures/<name>/<name>_static.glb, already head toward -Y):
# the skeleton is found from the mesh (auto=True); fractions are of the body length
def _dino(kind, head, neck, eye=0.7, arms=False, long_neck=False, size=0.44, show=-68):
    return dict(kind=kind, yaw=0, size=size, auto=True, dino=True, head_frac=head, neck_frac=neck,
                eye_frac=eye, arms=arms, long_neck=long_neck, show_yaw=show, tail_amp=1.0, legs=None)
CREATURES.update({
    "trex": _dino("biped", 0.17, 0.05, 0.62, arms=True),
    "allosaurus": _dino("biped", 0.15, 0.06, 0.62, arms=True),
    "velociraptor": _dino("biped", 0.11, 0.09, 0.6, arms=True),
    "spinosaurus": _dino("biped", 0.21, 0.07, 0.72, arms=True),
    "pachycephalosaurus": _dino("biped", 0.11, 0.06, 0.55, arms=True),
    "triceratops": _dino("quad", 0.30, 0.02, 0.35),
    "stegosaurus": _dino("quad", 0.09, 0.08, 0.6),
    "brachiosaurus": _dino("quad", 0.08, 0.0, 0.6, long_neck=True, size=0.36),
    "ankylosaurus": _dino("quad", 0.12, 0.04, 0.6),
    "parasaurolophus": _dino("quad", 0.13, 0.07, 0.55),
    "diplodocus": _dino("quad", 0.05, 0.0, 0.6, long_neck=True, size=0.48),
    "pteranodon": _dino("ptero", 0.0, 0.0, 0.6, size=0.56, show=-25),
    # Nov 28, 2026 batch (models/new10dino)
    "styracosaurus": _dino("quad", 0.28, 0.02, 0.38),
    "iguanodon": _dino("quad", 0.12, 0.08, 0.55),
    "carnotaurus": _dino("biped", 0.13, 0.06, 0.6, arms=True),
    "therizinosaurus": dict(_dino("biped", 0.08, 0.12, 0.55, arms=True), arm_wave=0.5),
    "gallimimus": _dino("biped", 0.07, 0.13, 0.55, arms=True),
    "dilophosaurus": _dino("biped", 0.12, 0.07, 0.6, arms=True),
    # Nov 28, 2026 (models/new2dino)
    "kentrosaurus": _dino("quad", 0.09, 0.08, 0.8),
    "microraptor": _dino("biped", 0.10, 0.07, 0.75, arms=True),
})


# Fedir's second set of creatures (Nov 22, 2026). Points are in the aligned frame (head toward -Y),
# read from models/creatures/probe/<name>_views.png. legs=dict(top, count) finds the legs
# automatically (each leg is its own piece of mesh below z=top).
CREATURES.update({
    "pleatbill": dict(kind="biped", yaw=0, size=0.22, tail_amp=0.5,   # wading bird, S neck, fan beak
        eyes=(0.0, -0.0425, 0.185), eye_dx=0.01, face=0,
        spine=[(0.0, 0.06, 0.125), (0.0, 0.02, 0.13), (0.0, -0.01, 0.135),
               (0.0, -0.03, 0.18), (0.0, -0.105, 0.155)],
        chains={"tail": ("Hips", [(0.0, 0.08, 0.13), (0.0, 0.095, 0.12), (0.0, 0.11, 0.1)])},
        legs=dict(top=0.105, count=2)),
    "coilusk": dict(kind="quad", yaw=38, size=0.22, tail_amp=0.3,     # snail on four sucker legs, swirl shell
        eyes=(0.012, -0.08, 0.137), eye_dx=0.02, face=0,
        spine=[(0.0, 0.03, 0.06), (0.0, -0.04, 0.06), (0.0, -0.06, 0.085),
               (0.005, -0.075, 0.105), (0.01, -0.095, 0.12)],
        chains={"tail": ("Hips", [(0.0, 0.03, 0.09), (0.0, 0.04, 0.14), (0.0, 0.03, 0.19)]),   # the shell sways a little
                # the four sucker legs join under the belly, so they are placed by hand (bottom view)
                "leg_FL": ("Chest", [(0.025, -0.04, 0.05), (0.04, -0.05, 0.025), (0.05, -0.055, 0.005)]),
                "leg_FR": ("Chest", [(-0.025, -0.04, 0.05), (-0.045, -0.05, 0.025), (-0.0575, -0.055, 0.005)]),
                "leg_BL": ("Hips", [(0.025, 0.05, 0.05), (0.04, 0.06, 0.025), (0.055, 0.0675, 0.005)]),
                "leg_BR": ("Hips", [(-0.025, 0.05, 0.05), (-0.035, 0.06, 0.025), (-0.045, 0.07, 0.005)])},
        legs=None),
    "siftrunk": dict(kind="quad", yaw=36, size=0.27,                   # low, scaly, long trunk, leaf tail
        eyes=(0.0000, -0.0798, 0.0282), eye_dx=0.0147, face=0,
        spine=[(0.0000, 0.0491, 0.0552), (0.0000, -0.0368, 0.0552), (0.0000, -0.0552, 0.0491),
               (0.0000, -0.0736, 0.0430), (0.0000, -0.0982, 0.0344)],
        chains={"tail": ("Hips", [(0.0000, 0.0736, 0.0614), (0.0000, 0.1043, 0.0614), (0.0000, 0.1350, 0.0552)]),
                "tailTrunk": ("Head", [(0.0000, -0.0920, 0.0270), (0.0000, -0.1105, 0.0147), (0.0000, -0.1289, 0.0074)])},
        legs=dict(top=0.0270, count=4)),
    "spindlecrab": dict(kind="quad", yaw=0, size=0.22,                 # shell hat, one big claw, six legs
        eyes=(-0.025, -0.045, 0.12), eye_dx=0.025, face=0,
        spine=[(0.0, 0.02, 0.11), (0.0, -0.01, 0.11), (0.0, -0.02, 0.12),
               (-0.01, -0.03, 0.15), (-0.015, -0.02, 0.21)],
        chains={"arm_L": ("Chest", [(0.02, -0.02, 0.11), (0.05, -0.04, 0.12), (0.08, -0.06, 0.15)]),
                "arm_R": ("Chest", [(-0.02, -0.02, 0.11), (-0.06, -0.04, 0.11), (-0.095, -0.06, 0.115)])},
        legs=dict(top=0.045, count=6)),
    "ripplemantis": dict(kind="quad", yaw=0, size=0.22,                # mantis with a leaf cape and fan arms
        eyes=(0.0, -0.025, 0.175), eye_dx=0.012, face=0,
        spine=[(0.0, 0.04, 0.08), (0.0, -0.01, 0.1), (0.0, -0.02, 0.15),
               (0.0, -0.025, 0.17), (0.0, -0.035, 0.19)],
        chains={"arm_L": ("Chest", [(0.02, -0.03, 0.14), (0.04, -0.06, 0.15), (0.05, -0.08, 0.15)]),
                "arm_R": ("Chest", [(-0.01, -0.03, 0.12), (-0.015, -0.06, 0.1), (-0.015, -0.08, 0.09)]),
                "ear_L": ("Head", [(0.01, -0.025, 0.19), (0.04, -0.02, 0.21), (0.08, -0.015, 0.21)]),
                "ear_R": ("Head", [(-0.01, -0.025, 0.19), (-0.04, -0.02, 0.21), (-0.08, -0.015, 0.21)])},
        legs=dict(top=0.045, count=6)),
    "tuftwhale": dict(kind="bat", yaw=0, size=0.22,                    # floats; big fins flap like wings
        eyes=(-0.005, -0.09, 0.09), eye_dx=0.02, face=0,
        spine=[(0.0, 0.03, 0.075), (0.0, -0.03, 0.075), (0.0, -0.06, 0.075),
               (0.0, -0.075, 0.075), (0.0, -0.1, 0.075)],
        chains={"wing_L": ("Chest", [(0.03, -0.03, 0.08), (0.07, -0.025, 0.09), (0.105, -0.02, 0.1)]),
                "wing_R": ("Chest", [(-0.03, -0.03, 0.08), (-0.07, -0.025, 0.09), (-0.105, -0.02, 0.1)]),
                "leg_BL": ("Hips", [(0.025, -0.02, 0.05), (0.04, -0.02, 0.025), (0.055, -0.02, 0.005)]),
                "leg_BR": ("Hips", [(-0.025, -0.02, 0.05), (-0.04, -0.02, 0.025), (-0.055, -0.02, 0.005)]),
                "tail": ("Hips", [(0.0, 0.05, 0.08), (0.0, 0.08, 0.095), (0.0, 0.1, 0.115)])},
        legs=None),
    "knotcko": dict(kind="biped", yaw=0, size=0.22, tail_amp=0.3,     # dancing gecko, knotted tail
        eyes=(0.0325, -0.045, 0.1725), eye_dx=0.018, face=0,
        spine=[(0.01, 0.0, 0.075), (0.02, -0.01, 0.13), (0.025, -0.02, 0.15),
               (0.03, -0.03, 0.165), (0.035, -0.07, 0.17)],
        chains={"arm_L": ("Chest", [(0.04, -0.02, 0.13), (0.06, -0.02, 0.135), (0.08, -0.02, 0.14)]),
                "arm_R": ("Chest", [(0.0, -0.02, 0.125), (-0.03, -0.03, 0.12), (-0.06, -0.03, 0.12)]),
                "leg_BL": ("Hips", [(0.03, 0.0, 0.07), (0.06, -0.03, 0.075), (0.085, -0.05, 0.08)]),
                "leg_BR": ("Hips", [(0.0, 0.0, 0.065), (0.0, -0.01, 0.03), (0.0, -0.03, 0.005)]),
                "tail": ("Hips", [(-0.01, 0.02, 0.06), (-0.04, 0.04, 0.05), (-0.07, 0.04, 0.06), (-0.095, 0.03, 0.07)])},
        legs=None),
    # the animatronic ostrich on roller skates: Meshy would not rig her (thin legs), so she gets
    # our own two-legged rig like Pleatbill; the app keeps her with the animatronics
    "skateostrich": dict(kind="biped", yaw=0, size=0.22, tail_amp=0.5,
        eyes=(0.0, -0.0425, 0.195), eye_dx=0.0075, face=0,
        spine=[(0.0, 0.02, 0.13), (0.0, -0.02, 0.15), (0.0, -0.035, 0.175),
               (0.0, -0.04, 0.2), (0.0, -0.075, 0.19)],
        chains={"arm_L": ("Chest", [(0.03, 0.0, 0.14), (0.06, 0.0, 0.14), (0.09, 0.0, 0.14)]),
                "arm_R": ("Chest", [(-0.03, 0.0, 0.14), (-0.06, 0.0, 0.14), (-0.09, 0.0, 0.14)]),
                "tail": ("Hips", [(0.0, 0.04, 0.14), (0.0, 0.06, 0.15), (0.0, 0.075, 0.16)])},
        legs=dict(top=0.1, count=2)),
    "cupspinner": dict(kind="quad", yaw=0, size=0.22,                  # fluffy spider carrying a cup, eight legs
        eyes=(-0.01, -0.0925, 0.065), eye_dx=0.015, face=0,
        spine=[(0.0, 0.03, 0.06), (0.0, -0.04, 0.06), (0.0, -0.06, 0.06),
               (0.0, -0.075, 0.06), (0.0, -0.1, 0.055)],
        chains={},
        legs=dict(top=0.04, count=8)),
})

# sea reptiles and Megalodon (Nov 28, 2026): they swim, so no feet. The skeleton runs along the
# body centre line (spine, neck, tail) with two-bone flippers found as the parts that stick out
# sideways. hip/chest are fractions of the length from the snout.
def _sea(head, neck, hip, chest, fins=2, eye=0.6, neck_segs=1, size=0.40, show=-68, lift=0.03):
    return dict(kind="swim", yaw=0, size=size, auto=True, dino=True, sea=True, head_frac=head,
                neck_frac=neck, hip_frac=hip, chest_frac=chest, fins=fins, eye_frac=eye,
                neck_segs=neck_segs, show_yaw=show, lift=lift, tail_amp=1.0, legs=None)
CREATURES.update({
    "mosasaurus": _sea(0.14, 0.05, 0.50, 0.30, eye=0.8),
    "elasmosaurus": _sea(0.04, 0.36, 0.72, 0.50, neck_segs=3, eye=0.7),
    "ichthyosaurus": _sea(0.20, 0.04, 0.55, 0.36, eye=0.85),
    "megalodon": _sea(0.20, 0.06, 0.58, 0.34, fins=1, eye=0.45),
})


def derive_swim_skeleton(C, co):
    """Spine, neck, tail and flippers for a swimmer lying along Y (head at -Y)."""
    y0, y1 = co[:, 1].min(), co[:, 1].max(); L = y1 - y0
    # centre line: robust middle of each slice, smoothed along the body
    ys = np.linspace(y0 + 0.01 * L, y1 - 0.01 * L, 48)
    cxs, czs, hws = [], [], []
    for y in ys:
        P = co[np.abs(co[:, 1] - y) < 0.006 * L / 0.4 + 0.002]
        if len(P) < 6:
            P = co[np.abs(co[:, 1] - y) < 0.012]
        cx_ = float(np.median(P[:, 0]))
        ax = np.abs(P[:, 0] - cx_)
        core = P[ax < np.percentile(ax, 60) + 1e-4]
        # top from just off the midline (skips a thin dorsal fin), bottom from the midline (skips
        # the flippers, which hang out at the sides); vertex density varies too much for medians
        thin = min(0.006, max(0.002, 0.15 * np.percentile(ax, 90)))
        offm, onm = P[ax > thin], P[ax <= thin]
        top_ = offm[:, 2].max() if len(offm) > 3 else P[:, 2].max()
        bot_ = onm[:, 2].min() if len(onm) > 3 else P[:, 2].min()
        zc = 0.5 * (top_ + bot_)
        ztop = core[:, 2].max()
        up = P[P[:, 2] > zc + 0.25 * (ztop - zc)]
        hw = float(np.percentile(np.abs(up[:, 0] - cx_), 92)) if len(up) > 3 else 0.01
        cxs.append(cx_); czs.append(zc); hws.append(hw)
    def smooth(a, k=2):
        a = np.array(a, float)
        med = np.array([np.median(a[max(0, i - k):i + k + 1]) for i in range(len(a))])
        return np.array([med[max(0, i - 1):i + 2].mean() for i in range(len(a))])
    cxs, czs, hws = smooth(cxs), smooth(czs, 3), smooth(hws)
    cx = lambda y: float(np.interp(y, ys, cxs))
    cz = lambda y: float(np.interp(y, ys, czs))
    hw = lambda y: float(np.interp(y, ys, hws))
    tipP = co[co[:, 1] < y0 + 0.006]
    tip = (float(tipP[:, 0].mean()), float(y0 + 0.002), float(tipP[:, 2].mean()))
    hl = C["head_frac"] * L
    head_y = y0 + hl; neck_y = head_y + C["neck_frac"] * L
    chest_y = y0 + C["chest_frac"] * L; hips_y = y0 + C["hip_frac"] * L
    P3 = lambda y: (cx(y), float(y), cz(y))
    C["spine"] = [P3(hips_y), P3(chest_y), P3(neck_y), P3(head_y), tip]
    n = C.get("neck_segs", 1)
    C["neck_mid"] = [P3(neck_y + (head_y - neck_y) * k / n) for k in range(1, n)]
    chains = {"tail": ("Hips", [P3(y) for y in np.linspace(hips_y + 0.01 * L, y1 - 0.004, 7)])}
    # flippers: what sticks out sideways past the body, grouped into connected patches
    out_idx = [i for i, p in enumerate(co) if abs(p[0] - cx(p[1])) > 1.25 * hw(p[1]) + 0.004
               and y0 + 0.6 * hl < p[1] < y1 - 0.08 * L]
    out = co[out_idx]
    cell = 0.006; keys = {}
    for i, p in enumerate(out):
        keys.setdefault((int(p[0] // cell), int(p[1] // cell), int(p[2] // cell)), []).append(i)
    seen = set(); comps = []
    for k0 in keys:
        if k0 in seen: continue
        stack = [k0]; seen.add(k0); mem = []
        while stack:
            k = stack.pop(); mem += keys[k]
            for d in itertools.product((-1, 0, 1), repeat=3):
                nb = (k[0] + d[0], k[1] + d[1], k[2] + d[2])
                if nb in keys and nb not in seen:
                    seen.add(nb); stack.append(nb)
        comps.append(out[mem])
    for side, sname in ((1, "L"), (-1, "R")):
        mine = [m for m in comps if len(m) > 25 and np.median(m[:, 0] - [cx(y) for y in m[:, 1]]) * side > 0]
        mine.sort(key=len, reverse=True)
        mine = sorted(mine[:C["fins"]], key=lambda m: m[:, 1].mean())
        for k, m in enumerate(mine):
            lat = side * (m[:, 0] - np.array([cx(y) for y in m[:, 1]]))
            base = m[lat < np.percentile(lat, 15)]
            by = float(base[:, 1].mean())
            root = np.array([cx(by) + side * 0.7 * hw(by), by, float(base[:, 2].mean())])
            d = np.linalg.norm(m - root, axis=1)
            tip_ = m[d > 0.85 * d.max()].mean(0)
            mid = m[(d > 0.42 * d.max()) & (d < 0.58 * d.max())]
            mid = mid.mean(0) if len(mid) > 3 else 0.5 * (root + tip_)
            nm = "fin_%s%s" % ("F" if k == 0 else "B", sname)
            chains[nm] = ("Chest" if k == 0 else "Hips", [tuple(root), tuple(mid), tuple(tip_)])
    C["chains"] = chains
    ey = y0 + C["eye_frac"] * hl
    E = co[(np.abs(co[:, 1] - ey) < 0.003) & (np.abs(co[:, 2] - cz(ey)) < max(hl, 0.015))]
    zt, zb = E[:, 2].max(), E[:, 2].min()
    C["eyes"] = (cx(ey), float(ey), float(zb + 0.62 * (zt - zb)))
    C["eye_dx"] = float(max(0.004, 0.85 * np.percentile(np.abs(E[:, 0] - cx(ey)), 90)))
    C["face"] = 0
    print("SWIM spine", [tuple(np.round(p, 3)) for p in C["spine"]], "neck_mid", len(C["neck_mid"]))
    print("SWIM chains", {k: [tuple(np.round(p, 3)) for p in v[1]] for k, v in chains.items()})
    print("SWIM eyes", np.round(C["eyes"], 3), round(C["eye_dx"], 4), "flipper patches", len(comps))


def derive_dino_skeleton(C, co):
    """Fill C's spine, chains and eyes from a dinosaur mesh lying along Y (head at -Y, feet on z=0)."""
    kind = C["kind"]
    if kind == "swim":
        return derive_swim_skeleton(C, co)
    y0, y1 = co[:, 1].min(), co[:, 1].max(); L = y1 - y0
    def sl(y, w=0.004, m=None):
        k = np.abs(co[:, 1] - y) < w
        return co[k & m] if m is not None else co[k]
    def spine_z(y):
        P = sl(y)
        if len(P) < 4:
            P = sl(y, 0.01)
        zt, zb = P[:, 2].max(), P[:, 2].min()
        return float(P[P[:, 2] > zt - 0.6 * (zt - zb), 2].mean())
    def cx(y):
        P = sl(y); return float(P[:, 0].mean()) if len(P) else 0.0
    # ---- feet: connected low patches
    want = 4 if kind == "quad" else 2
    if kind == "ptero":      # gliding: the lowest bits are the hanging feet
        zl = np.percentile(co[:, 2], 1.5)
        low = co[co[:, 2] < zl + 0.004]
    else:
        low = co[co[:, 2] < 0.007]
    cell = 0.005
    keys = {}
    for i, p in enumerate(low):
        keys.setdefault((int(p[0] // cell), int(p[1] // cell)), []).append(i)
    seen = set(); comps = []
    for k0 in keys:
        if k0 in seen: continue
        stack = [k0]; seen.add(k0); mem = []
        while stack:
            k = stack.pop(); mem += keys[k]
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    n = (k[0] + dx, k[1] + dy)
                    if n in keys and n not in seen:
                        seen.add(n); stack.append(n)
        comps.append(np.array(mem))
    # a patch that spans both sides is two feet standing close together: split it
    split = []
    for m in comps:
        xs = low[m, 0] - np.median(co[:, 0])
        if len(m) > 20 and xs.min() < -0.004 and xs.max() > 0.004:
            split += [m[xs < 0], m[xs >= 0]]
        else:
            split.append(m)
    comps = split
    comps.sort(key=len, reverse=True)
    feet = [low[m].mean(0) for m in comps[:want]]
    print("DINO feet", [tuple(np.round(f, 3)) for f in feet], "of", len(comps))
    if kind == "quad":
        feet.sort(key=lambda f: f[1])
        front, back = feet[:2], feet[2:]
    else:
        front, back = [], feet
    hips_y = float(np.mean([f[1] for f in back])) + 0.006 * L / 0.3
    hl = C["head_frac"] * L
    tip_y = y0 + 0.004
    tipP = co[co[:, 1] < y0 + 0.008]
    tip = np.array([tipP[:, 0].mean(), y0 + 0.002, tipP[:, 2].mean()])
    if kind == "ptero":
        hl = 0.25 * (y1 - y0)
    head_y = y0 + hl
    HP = co[(np.abs(co[:, 1] - head_y) < 0.005) & (np.abs(co[:, 2] - tip[2]) < max(0.6 * hl, 0.012))]
    head_z = float(HP[:, 2].mean()) if len(HP) > 3 else tip[2]
    if kind == "quad":
        chest_y = float(np.mean([f[1] for f in front])) - 0.004
    elif kind == "ptero":
        chest_y = y0 + 0.45 * (y1 - y0)
        hips_y = y0 + 0.62 * (y1 - y0)
    else:
        neck_y_ = head_y + C["neck_frac"] * L
        chest_y = neck_y_ + 0.45 * (hips_y - neck_y_)
    if C.get("long_neck"):
        neck_y = chest_y - 0.035 * L
        neck_z = spine_z(chest_y) + 0.01
    elif kind == "ptero":
        neck_y = y0 + 0.35 * (y1 - y0); neck_z = spine_z(neck_y)
    else:
        neck_y = head_y + C["neck_frac"] * L if C["neck_frac"] > 0 else head_y + 0.02 * L
        neck_z = spine_z(neck_y)
    hips = (cx(hips_y), hips_y, spine_z(hips_y))
    chest = (cx(chest_y), chest_y, spine_z(chest_y))
    C["spine"] = [hips, chest, (cx(neck_y), neck_y, neck_z), (float(tip[0]) * 0.5, head_y, head_z), tuple(tip)]
    chains = {}
    # ---- tail: hips -> tail tip along the slice centres
    if kind != "ptero":
        ys = np.linspace(hips_y + 0.012, y1 - 0.004, 6)
        chains["tail"] = ("Hips", [(cx(y), float(y), spine_z(y)) for y in ys])
    # ---- legs
    def leg_chain(f, top_y, parent):
        side = 1 if f[0] > hips[0] else -1
        tz = spine_z(top_y) - 0.004
        top = np.array([f[0] * 0.6 + 0.4 * side * 0.006, top_y, tz])
        foot = np.array([f[0], f[1], max(f[2], 0.004)])
        mz = 0.5 * (tz + foot[2]); my = 0.5 * (top_y + foot[1])
        K = co[(np.abs(co[:, 2] - mz) < 0.004) & (np.sign(co[:, 0] - hips[0]) == side)
               & (np.abs(co[:, 1] - my) < 0.025) & (np.abs(co[:, 0] - f[0]) < 0.02)]
        knee = K.mean(0) if len(K) > 5 else 0.5 * (top + foot)
        return (parent, [tuple(top), tuple(knee), tuple(foot)]), side
    for f in back:
        ch, side = leg_chain(f, hips_y, "Hips")
        chains["leg_B" + ("L" if side > 0 else "R")] = ch
    for f in front:
        ch, side = leg_chain(f, chest_y, "Chest")
        chains["leg_F" + ("L" if side > 0 else "R")] = ch
    # ---- small theropod arms: what hangs below the chest, ahead of the hips
    if C.get("arms"):
        zc = spine_z(chest_y)
        for side, nm in ((1, "arm_L"), (-1, "arm_R")):
            A = co[(co[:, 1] > chest_y - 0.03) & (co[:, 1] < chest_y + 0.006)
                   & (co[:, 2] < zc - 0.008) & (co[:, 2] > 0.35 * zc) & ((co[:, 0] - hips[0]) * side > 0.002)]
            # keep away from the legs
            for lg in [c for c in chains if c.startswith("leg_")]:
                lt = np.array(chains[lg][1][0])
                A = A[np.linalg.norm(A[:, :2] - lt[:2], axis=1) > 0.02] if len(A) else A
            if len(A) < 8:
                print("DINO no arm found", nm); continue
            tipA = A[np.argmin(A[:, 2])]
            root = np.array([hips[0] + side * 0.006, chest_y, zc - 0.006])
            mid = 0.5 * (root + tipA)
            chains[nm] = ("Chest", [tuple(root), tuple(mid), tuple(tipA)])
    # ---- pterosaur wings: out along x
    if kind == "ptero":
        xm = co[:, 0].max()
        for side, nm in ((1, "wing_L"), (-1, "wing_R")):
            pts = []
            for fx in (0.08, 0.35, 0.65, 0.95):
                x = side * fx * xm
                P = co[np.abs(co[:, 0] - x) < 0.006]
                pts.append((x, float(P[:, 1].mean()), float(P[:, 2].mean())))
            chains[nm] = ("Chest", pts)
    C["chains"] = chains
    # ---- eyes
    ey = y0 + C["eye_frac"] * hl if kind != "ptero" else y0 + 0.6 * hl
    E = co[(np.abs(co[:, 1] - ey) < 0.003) & (np.abs(co[:, 2] - head_z) < max(hl, 0.015))]
    zt, zb = E[:, 2].max(), E[:, 2].min()
    C["eyes"] = (float(E[:, 0].mean()), float(ey), float(zb + 0.68 * (zt - zb)))
    C["eye_dx"] = float(max(0.004, 0.8 * np.percentile(np.abs(E[:, 0] - E[:, 0].mean()), 90)))
    C["face"] = 0
    print("DINO spine", [tuple(np.round(p, 3)) for p in C["spine"]])
    print("DINO chains", {k: [tuple(np.round(p, 3)) for p in v[1]] for k, v in chains.items()})
    print("DINO eyes", np.round(C["eyes"], 3), round(C["eye_dx"], 4))


def build_creature(name):
    C = CREATURES[name]
    src = os.path.join(HERE, "creatures", name)
    kind = C["kind"]
    TAU_ = math.tau

    # ---------------------------------------------------------------- import + align
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    bpy.ops.import_scene.gltf(filepath=os.path.join(src, name + "_static.glb"))
    meshes = [o for o in scene.objects if o.type == 'MESH']
    bpy.ops.object.select_all(action='DESELECT')
    for o in meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    body = bpy.context.view_layer.objects.active
    bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
    for o in list(scene.objects):
        if o != body:
            bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    me = body.data
    co = np.array([v.co[:] for v in me.vertices])
    Ra = np.array(Matrix.Rotation(math.radians(C["yaw"]), 3, 'Z'))
    co = co @ Ra.T
    lo, hi = co.min(0), co.max(0)
    S = C["size"] / (hi - lo).max()
    co = (co - [(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]]) * S
    if C.get("sea"):
        # swimmers float: lift the rest pose itself, so the accessory fit (measured at rest) and
        # the app's rest pins already sit at the floating height
        co[:, 2] += C.get("lift", 0.03)
    me.vertices.foreach_set("co", co.ravel())
    me.update()
    body.name = me.name = name
    mat = me.materials[0]
    mat.name = "Skin"
    for extra in me.materials[1:]:
        print("WARNING extra material", extra.name)
    if C.get("auto"):
        derive_dino_skeleton(C, co)
    nV = len(co)
    tri_count = sum(len(p.vertices) - 2 for p in me.polygons)
    print("CREATURE %s verts %d tris %d scale %.5f" % (name, nV, tri_count, S))

    # seam-welded connectivity (glTF splits vertices along UV seams)
    keys = {}
    weld = np.empty(nV, dtype=np.int64)
    for i, p in enumerate(np.round(co / 1e-5).astype(np.int64)):
        weld[i] = keys.setdefault(tuple(p), len(keys))
    nW = len(keys)
    wco = np.zeros((nW, 3))
    wco[weld] = co
    adj = [set() for _ in range(nW)]
    for e in me.edges:
        a, b = weld[e.vertices[0]], weld[e.vertices[1]]
        if a != b:
            adj[a].add(b); adj[b].add(a)

    # ---------------------------------------------------------------- legs
    sp = [V(*p) for p in C["spine"]]
    hips_p, chest_p, neck_p, head_p, tip_p = sp
    y_mid = (hips_p.y + chest_p.y) / 2
    legs = []      # (name, [points])
    if C.get("legs"):
        L = C["legs"]
        top = L["top"]
        inslab = wco[:, 2] < top
        comp = -np.ones(nW, dtype=np.int64)
        comps = []
        for s in np.nonzero(inslab)[0]:
            if comp[s] >= 0:
                continue
            cid = len(comps); stack = [s]; comp[s] = cid; members = []
            while stack:
                x = stack.pop(); members.append(x)
                for y in adj[x]:
                    if comp[y] < 0 and inslab[y]:
                        comp[y] = cid; stack.append(y)
            comps.append(np.array(members))
        # a leg reaches up to the belly line and has some size
        cand = []
        for m in comps:
            z = wco[m, 2]
            print("  piece verts %d z %.3f..%.3f centre %s" % (len(m), z.min(), z.max(), tuple(np.round(wco[m].mean(0), 3))))
            if len(m) < 40 or z.max() < top - 0.004 or z.min() > top - 0.012:
                continue
            cand.append(m)
        cand.sort(key=len, reverse=True)
        want = L.get("count", 8 if L.get("tentacle") else 4)
        cand = cand[:want]
        for m in cand:
            P = wco[m]
            T = P[P[:, 2] > top - 0.006].mean(0)
            d = np.linalg.norm(P - T, axis=1)
            dm = d.max()
            F = P[d > 0.85 * dm].mean(0)
            if L.get("tentacle"):
                K1 = P[(d > 0.28 * dm) & (d < 0.38 * dm)].mean(0)
                K2 = P[(d > 0.6 * dm) & (d < 0.7 * dm)].mean(0)
                pts = [V(T[0], T[1], top + 0.012), V(*K1), V(*K2), V(*F)]
            else:
                K = P[(d > 0.45 * dm) & (d < 0.55 * dm)].mean(0)
                pts = [V(T[0], T[1], top + 0.012), V(*K), V(*F)]
            legs.append(pts)
            print("LEG verts %d top %s foot %s" % (len(m), tuple(np.round(T, 3)), tuple(np.round(F, 3))))
        print("LEG pieces below z=%.3f: %d, used %d" % (top, len(comps), len(legs)))
    # name legs: F/B by y against the body middle, L/R by x against the spine
    named_legs = {}
    def lr(grp, k):
        if len(grp) == 1:
            return "L" if grp[0][0].x > hips_p.x else "R"
        return "L" if k == 0 else ("R" if k == len(grp) - 1 else "M%d" % k)
    if kind in ("biped", "bat"):
        grp = sorted(legs, key=lambda p: -p[0].x)
        for k, pts in enumerate(grp):
            named_legs["leg_B" + lr(grp, k)] = ("Hips", pts)
    elif legs:
        front = sorted([p for p in legs if p[0].y < y_mid], key=lambda p: -p[0].x)
        back = sorted([p for p in legs if p[0].y >= y_mid], key=lambda p: -p[0].x)
        for grp, tag, parent in ((front, "F", "Chest"), (back, "B", "Hips")):
            for k, pts in enumerate(grp):
                nm = ("tent_%s%d" % (tag, k + 1)) if kind == "squid" else ("leg_%s%s" % (tag, lr(grp, k)))
                named_legs[nm] = (parent, pts)
    chains = dict(C.get("chains", {}))
    for nm, (par, pts) in named_legs.items():
        chains[nm] = (par, [tuple(p) for p in pts])
    # hand-placed limb joints: pull knees and feet into the middle of the limb
    for nm, (par, pts) in list(chains.items()):
        if nm.startswith(("leg_", "arm_", "tent_")) and nm not in named_legs:
            new_pts = [pts[0]]
            for p in pts[1:]:
                d = np.linalg.norm(wco - np.array(p), axis=1)
                near = d < 0.009
                q = wco[near].mean(0) if near.sum() > 5 else np.array(p)
                new_pts.append(tuple(q))
                print("SNAP %s %s -> %s" % (nm, tuple(np.round(p, 3)), tuple(np.round(q, 3))))
            chains[nm] = (par, new_pts)
    print("CHAINS", sorted(chains))

    # ---------------------------------------------------------------- armature
    arm = bpy.data.armatures.new(name + "_rig")
    rig = bpy.data.objects.new(name + "_rig", arm)
    scene.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm.edit_bones
    def bone(nm, h, t, parent=None, deform=True, connect=False):
        b = eb.new(nm); b.head = h; b.tail = t
        if (b.tail - b.head).length < 1e-4:
            b.tail = b.head + Vector((0, 0, 0.005))
        if parent:
            b.parent = eb[parent]; b.use_connect = connect
        b.use_deform = deform
        return b
    bone("root", V(0, 0, 0), V(0, 0, 0.03), deform=False)
    mid = (hips_p + chest_p) / 2
    bone("Hips", hips_p, mid, "root")
    bone("Spine", mid, chest_p, "Hips", connect=True)
    bone("Chest", chest_p, neck_p, "Spine", connect=True)
    # long necks (Elasmosaurus) get extra segments: neck, neck2, neck3 ...
    npts = [neck_p] + [V(*q) for q in C.get("neck_mid", [])] + [head_p]
    neck_names = ["neck"] + ["neck%d" % (k + 2) for k in range(len(npts) - 2)]
    prev_b = "Chest"
    for k, nm in enumerate(neck_names):
        bone(nm, npts[k], npts[k + 1], prev_b, connect=True); prev_b = nm
    bone("Head", head_p, tip_p, prev_b, connect=True)
    chain_len = {}
    for nm, (par, pts) in chains.items():
        pts = [V(*p) for p in pts]
        chain_len[nm] = len(pts) - 1
        for k in range(len(pts) - 1):
            bone("%s_%d" % (nm, k + 1), pts[k], pts[k + 1], par if k == 0 else "%s_%d" % (nm, k), connect=k > 0)
    bpy.ops.object.mode_set(mode='OBJECT')

    # ---------------------------------------------------------------- weights (bone heat on a welded copy)
    wm = bpy.data.meshes.new(name + "_weld")
    wedges = set()
    for e in me.edges:
        a, b = int(weld[e.vertices[0]]), int(weld[e.vertices[1]])
        if a != b:
            wedges.add((min(a, b), max(a, b)))
    wfaces = []
    for p in me.polygons:
        f = [int(weld[v]) for v in p.vertices]
        if len(set(f)) == len(f):
            wfaces.append(f)
    # bone heat fails on tiny models: weigh a 100x copy of mesh and skeleton
    wm.from_pydata((wco * 100).tolist(), [], wfaces)
    wm.update()
    wob = bpy.data.objects.new(name + "_weld", wm)
    scene.collection.objects.link(wob)
    big = rig.copy(); big.data = rig.data.copy(); scene.collection.objects.link(big)
    bpy.ops.object.select_all(action='DESELECT')
    big.scale = (100, 100, 100); big.select_set(True); bpy.context.view_layer.objects.active = big
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    wob.select_set(True)
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    deform = [b.name for b in arm.bones if b.use_deform]
    W = np.zeros((nW, len(deform)))
    gidx = {g.index: g.name for g in wob.vertex_groups}
    col = {n: i for i, n in enumerate(deform)}
    for v in wm.vertices:
        for g in v.groups:
            n = gidx[g.group]
            if n in col:
                W[v.index, col[n]] = g.weight
    # fill vertices bone heat missed (loose bits) from their nearest bones
    heads = np.array([arm.bones[n].head_local[:] for n in deform])
    tails = np.array([arm.bones[n].tail_local[:] for n in deform])
    def seg_dist(P):
        ab = tails - heads
        t = np.clip(((P[:, None, :] - heads[None]) * ab[None]).sum(2) / (ab ** 2).sum(1)[None], 0, 1)
        return np.linalg.norm(P[:, None, :] - (heads[None] + t[..., None] * ab[None]), axis=2)
    miss = W.sum(1) < 1e-3
    print("BONE HEAT missed %d of %d welded verts" % (miss.sum(), nW))
    if miss.any():
        D = seg_dist(wco[miss])
        w = 1.0 / np.maximum(D, 1e-3) ** 4
        w[w < w.max(1, keepdims=True) * 0.05] = 0
        W[miss] = w
    # a few smoothing passes over the welded mesh, then keep the 4 biggest
    for _ in range(2):
        W2 = W.copy()
        for i in range(nW):
            if adj[i]:
                W2[i] = 0.5 * W[i] + 0.5 * W[list(adj[i])].mean(0)
        W = W2
    order = np.argsort(-W, axis=1)
    W[np.arange(nW)[:, None], order[:, 4:]] = 0
    W /= np.maximum(W.sum(1, keepdims=True), 1e-9)
    bpy.data.objects.remove(wob, do_unlink=True)
    bigdata = big.data; bpy.data.objects.remove(big, do_unlink=True); bpy.data.armatures.remove(bigdata)
    for n in deform:
        body.vertex_groups.new(name=n)
    Wv = W[weld]
    for j, n in enumerate(deform):
        g = body.vertex_groups[n]
        nz = np.nonzero(Wv[:, j] > 1e-4)[0]
        for i in nz:
            g.add([int(i)], float(Wv[i, j]), 'REPLACE')
    body.parent = rig
    mod = body.modifiers.new("Armature", 'ARMATURE'); mod.object = rig

    # ---------------------------------------------------------------- clips
    rest3 = {b.name: b.matrix_local.to_3x3() for b in arm.bones}
    BONES = set(rest3)
    def q_seq(bn, steps):
        R = Matrix.Identity(3)
        for axis, deg in steps:
            if deg:
                R = Matrix.Rotation(math.radians(deg), 3, axis) @ R
        M = rest3[bn]
        return (M.inverted() @ R @ M).to_quaternion()

    class Pz:
        def __init__(self):
            self.rot = {}; self.root_loc = Vector(); self.squash = 1.0
        def r(self, bn, *steps):
            if bn in BONES:
                self.rot.setdefault(bn, []).extend(steps)
            return self

    EA, TA = C.get("ear_amp", 1.0), C.get("tail_amp", 1.0)
    tails_ = [n for n in chains if n.startswith("tail")]
    legnames = [n for n in chains if n.startswith("leg_")]
    tents = sorted(n for n in chains if n.startswith("tent_"))
    def chainw(p, nm, axis, amp, ph, lag=0.7, grow=0.5):
        n = chain_len.get(nm, 0)
        for k in range(1, n + 1):
            p.r("%s_%d" % (nm, k), (axis, amp * (1 - grow + grow * k / n) * math.sin(ph - lag * k)))
    def chain_const(p, nm, axis, deg):
        n = chain_len.get(nm, 0)
        for k in range(1, n + 1):
            p.r("%s_%d" % (nm, k), (axis, deg / n))
    def ears(p, amp, ph, fwd=0.0):
        for s, nm in ((1, "ear_L"), (-1, "ear_R")):
            chainw(p, nm, "Y", s * amp * EA, ph, 0.9)
            chain_const(p, nm, "X", fwd * EA)
    def tail(p, amp, ph, lift=0.0):
        for k, nm in enumerate(tails_):
            chainw(p, nm, "Z", amp * TA, ph - 0.8 * k, 0.8)
            chain_const(p, nm, "X", lift * TA * C.get("tail_lift", 1.0))
    def leg(p, nm, swing, knee=0.0):
        if nm in chains:
            front = "_F" in nm
            p.r(nm + "_1", ("X", swing))
            p.r(nm + "_2", ("X", knee if front else -knee))
    def wings(p, up, ph=0.0, amp=0.0, only=None):
        for s, nm in ((1, "wing_L"), (-1, "wing_R")):
            if only and nm != only:
                continue
            a = up + amp * math.sin(ph)
            p.r(nm + "_1", ("Y", -s * a))
            p.r(nm + "_2", ("Y", -s * 0.5 * a))
    def tentacles(p, amp, ph, lag=1.1):
        for k, nm in enumerate(tents):
            chainw(p, nm, "X", amp, ph + 1.3 * k, lag, 0.3)
            chainw(p, nm, "Y", 0.6 * amp * (1 if "_L" in nm else -1), ph + 0.7 * k + 1.0, lag, 0.3)

    def idle(t):
        s = math.sin(TAU_ * t)
        p = Pz(); p.squash = 1 + 0.015 * s
        p.r("Chest", ("X", 1.5 * s)).r("Head", ("X", -2 * s), ("Y", 3 * s))
        ears(p, 6, TAU_ * t)
        tail(p, 9, TAU_ * t)
        wings(p, 4 * s)
        tentacles(p, 7, TAU_ * t)
        p.r("arm_L_1", ("X", 3 * s)).r("arm_R_1", ("X", 3 * s))
        return p

    def dance(t):
        e = env(t, 0.1)
        sway = math.sin(2 * TAU_ * t)
        beat = abs(math.sin(4 * TAU_ * t))
        sq = (1 - beat) ** 3
        p = Pz()
        p.root_loc = Vector((0, 0, 0.008 * beat * e))
        p.squash = 1 - 0.06 * sq * e
        p.r("Hips", ("Y", 7 * sway * e)).r("Chest", ("Y", -5 * sway * e))
        p.r("Head", ("Y", -9 * math.sin(2 * TAU_ * t - 0.5) * e), ("Z", 7 * sway * e))
        ears(p, 16 * e, 2 * TAU_ * t - 0.9, -6 * beat * e)
        tail(p, 30 * e, 2 * TAU_ * t - 0.6, 8 * e)
        # little paw taps on the beat, alternating
        tapL, tapR = max(0, sway), max(0, -sway)
        leg(p, "leg_FL", -22 * tapL * e, 30 * tapL * e); leg(p, "leg_FR", -22 * tapR * e, 30 * tapR * e)
        leg(p, "leg_BL", -8 * tapR * e); leg(p, "leg_BR", -8 * tapL * e)
        if kind == "biped":
            up = 15 * math.sin(4 * TAU_ * t)
            p.r("arm_L_1", ("Y", -(70 + up) * e), ("X", -20 * e)).r("arm_R_1", ("Y", (70 - up) * e), ("X", -20 * e))
            p.r("arm_L_2", ("Y", -20 * e)).r("arm_R_2", ("Y", 20 * e))
            leg(p, "leg_BL", -14 * tapL * e); leg(p, "leg_BR", -14 * tapR * e)
        wings(p, 10 * e, 4 * TAU_ * t, 28 * e)
        tentacles(p, 14 * e, 4 * TAU_ * t)
        return p

    def jump(t):
        u = (t * 3) % 1.0
        lift = crouch = air = 0.0
        sz = 1.0
        if u < 0.22:
            c = math.sin(math.pi * u / 0.22); sz = 1 - 0.12 * c; crouch = c
        elif u < 0.72:
            q = (u - 0.22) / 0.5
            lift = 0.035 * 4 * q * (1 - q); sz = 1 + 0.06 * math.sin(math.pi * q); air = math.sin(math.pi * q)
        else:
            q = (u - 0.72) / 0.28
            k = math.sin(math.pi * q ** 0.6); sz = 1 - 0.15 * k; crouch = 0.6 * k
        p = Pz(); p.root_loc = Vector((0, 0, lift)); p.squash = sz
        p.r("Chest", ("X", 6 * crouch)).r("Head", ("X", -5 * crouch + 5 * air))
        for nm in legnames:
            if "_F" in nm:
                leg(p, nm, -28 * air + 8 * crouch, 35 * air)
            else:
                leg(p, nm, 25 * air if kind not in ("biped", "bat") else -15 * air, 30 * air)
        ears(p, 0, 0, 16 * crouch - 14 * air)
        tail(p, 0, 0, 30 * air - 8 * crouch)
        wings(p, -15 * crouch + 25 * air, 0)
        p.r("arm_L_1", ("Y", -50 * air)).r("arm_R_1", ("Y", 50 * air))
        tentacles(p, 0, 0)
        for nm in tents:
            chain_const(p, nm, "X", (-20 if nm.endswith("1") else 20) * air)
        return p

    def run(t):
        e = env(t, 0.08)
        ph = 10 * TAU_ * t
        w = math.sin(ph); b = abs(math.sin(ph))
        p = Pz(); p.root_loc = Vector((0, 0, 0.005 * b * e)); p.squash = 1 - 0.025 * (1 - b) * e
        p.r("Chest", ("X", 4 * w * e)).r("Head", ("X", -5 * e + 3 * math.sin(2 * ph) * e))
        # trot: diagonal pairs swing together
        knee = lambda x: 35 * max(0, x) * e
        if kind in ("biped", "bat"):
            leg(p, "leg_BL", 30 * w * e, knee(w)); leg(p, "leg_BR", -30 * w * e, knee(-w))
        else:
            leg(p, "leg_FL", -28 * w * e, knee(w)); leg(p, "leg_BR", -24 * w * e, knee(-w))
            leg(p, "leg_FR", 28 * w * e, knee(-w)); leg(p, "leg_BL", 24 * w * e, knee(w))
        p.r("arm_L_1", ("X", -35 * w * e)).r("arm_R_1", ("X", 35 * w * e))
        ears(p, 6 * e, 2 * ph, -16 * e)
        tail(p, 12 * e, ph - 0.8, 18 * e)
        wings(p, 8 * e, 2 * ph, 14 * e)
        tentacles(p, 18 * e, ph, 1.4)
        return p

    def wave(t):
        e = env(t, 0.22); inner = env(t, 0.32)
        wv = math.sin(TAU_ * 3 * (t - 0.25) / 0.5) * inner if 0.25 < t < 0.75 else 0.0
        p = Pz()
        p.r("Head", ("Y", -8 * e), ("X", -4 * e))
        tail(p, 18 * e, TAU_ * 2 * t, 6 * e)
        ears(p, 5 * e, TAU_ * 2 * t)
        if kind == "biped":
            p.r("arm_R_1", ("Y", 125 * e), ("X", -25 * e)).r("arm_R_2", ("Y", (25 + 30 * wv) * e))
            p.r("Chest", ("Y", 4 * e))
        elif kind == "bat":
            wings(p, 0, 0)
            p.r("wing_R_1", ("Y", (35 + 18 * wv) * e)).r("wing_R_2", ("Y", (20 + 25 * wv) * e))
            p.r("Chest", ("Y", 4 * e))
        elif kind == "squid":
            if "tent_R1" in chains:
                nm = "tent_R1"
                n = chain_len[nm]
                for k in range(1, n + 1):
                    p.r("%s_%d" % (nm, k), ("X", -(55 if k == 1 else 25) * e), ("Y", 20 * wv * e * k / n))
            tentacles(p, 4 * e, TAU_ * t)
        else:
            nm = "leg_FR" if "leg_FR" in chains else ("leg_FL" if "leg_FL" in chains else None)
            if nm:
                p.r(nm + "_1", ("X", -55 * e), ("Y", 10 * wv * e))
                p.r(nm + "_2", ("X", (40 + 25 * wv) * e))
                p.r("Hips", ("Y", (4 if nm.endswith("R") else -4) * e))
                p.r("Chest", ("Y", (6 if nm.endswith("R") else -6) * e), ("X", -5 * e))
        return p

    if C.get("dino"):
        # Realistic dinosaurs: slow, heavy and calm. No squash, small bounces, weight shifts.
        ptero = kind == "ptero"
        arms = [n for n in ("arm_L", "arm_R") if n in chains]
        def neckhead(p, pitch=0.0, yaw=0.0):
            p.r("neck", ("X", 0.4 * pitch), ("Z", 0.5 * yaw)).r("Head", ("X", 0.6 * pitch), ("Z", 0.5 * yaw))
        def dtail(p, amp, ph, lift=0.0):
            chainw(p, "tail", "Z", amp, ph, 0.55, 0.7)
            chain_const(p, "tail", "X", lift)
        def idle(t):
            s_ = math.sin(TAU_ * t)
            p = Pz()
            p.r("Chest", ("X", 1.2 * s_)).r("Spine", ("X", -0.6 * s_))
            neckhead(p, -2 * s_, 5 * math.sin(TAU_ * t + 0.6))
            dtail(p, 5, TAU_ * t)
            for nm in arms:
                p.r(nm + "_1", ("X", 4 * s_))
            if ptero:
                wings(p, 3 * s_)
            return p
        def dance(t):
            e = env(t, 0.08)
            p = Pz()
            if ptero:
                fl = math.sin(TAU_ * 4 * t)
                p.root_loc = Vector((0, 0, 0.012 * (0.5 + 0.5 * fl) * e))
                wings(p, 8 * e, TAU_ * 4 * t, 38 * e)
                neckhead(p, -6 * fl * e, 10 * math.sin(TAU_ * 2 * t) * e)
                return p
            # four slow stomps, left, right, left, right; the body leans onto the standing side
            u = (t * 4) % 1.0; k = int(t * 4) % 2
            side = 1 if k == 0 else -1
            lift = math.sin(math.pi * min(1, u / 0.5)) if u < 0.5 else 0.0
            hit = math.exp(-((u - 0.52) / 0.07) ** 2)
            settle = 0.5 * math.exp(-((u - 0.52) / 0.18) ** 2)
            p.root_loc = Vector((0, 0, (0.004 * lift - 0.004 * hit) * e))
            p.r("Hips", ("Y", -5 * side * lift * e), ("X", 2 * hit * e)).r("Chest", ("Y", 3 * side * lift * e))
            neckhead(p, (5 * hit - 3 * lift) * e, 9 * math.sin(TAU_ * 2 * t) * e)
            dtail(p, 20 * e, TAU_ * 2 * t, (4 * settle) * e)
            if kind == "quad":
                fr, bk = ("leg_FL", "leg_BR") if side > 0 else ("leg_FR", "leg_BL")
                leg(p, fr, -26 * lift * e, 38 * lift * e); leg(p, bk, -8 * lift * e, 10 * lift * e)
            else:
                nm = "leg_BL" if side > 0 else "leg_BR"
                p.r(nm + "_1", ("X", -30 * lift * e)).r(nm + "_2", ("X", 45 * lift * e))
                for a in arms:
                    p.r(a + "_1", ("X", -12 * lift * e))
            return p
        def jump(t):
            lift = crouch = air = 0.0
            if t < 0.32:
                crouch = math.sin(math.pi * t / 0.32)
            elif t < 0.62:
                q = (t - 0.32) / 0.3
                lift = 0.016 * 4 * q * (1 - q); air = math.sin(math.pi * q)
                if ptero: lift *= 3
            else:
                q = (t - 0.62) / 0.38
                crouch = math.exp(-5 * q) * math.cos(9 * q) * 0.9    # heavy landing that settles
            p = Pz(); p.root_loc = Vector((0, 0, lift - 0.006 * max(0, crouch)))
            p.r("Hips", ("X", 5 * crouch)).r("Chest", ("X", 3 * crouch))
            neckhead(p, 6 * crouch - 8 * air)
            dtail(p, 0, 0, 14 * air - 6 * crouch)
            for nm in legnames:
                k_ = 22 * max(0, crouch) + 25 * air
                if "_F" in nm:
                    leg(p, nm, -15 * air + 6 * crouch, k_)
                else:
                    p.r(nm + "_1", ("X", -18 * air - 10 * max(0, crouch))).r(nm + "_2", ("X", k_))
            if ptero:
                wings(p, 20 * air - 10 * crouch, TAU_ * 3 * t, 35 * air)
            for a in arms:
                p.r(a + "_1", ("X", -20 * air))
            return p
        def run(t):
            e = env(t, 0.08)
            p = Pz()
            if ptero:
                # takes off, glides high round the loop (the app moves it), lands
                up = smooth_(t / 0.28) * (1 - smooth_((t - 0.78) / 0.22))
                beat = 1.0 if (t < 0.32 or t > 0.82) else 0.25
                p.root_loc = Vector((0, 0, 0.07 * up + 0.004 * math.sin(TAU_ * 2 * t) * up))
                wings(p, 6 * up, TAU_ * 5 * t, 34 * beat * e)
                p.r("Hips", ("Y", 14 * math.sin(math.pi * min(1, max(0, (t - 0.3) / 0.5))) * up))
                neckhead(p, -6 * up, 0)
                for nm in legnames:
                    p.r(nm + "_1", ("X", 35 * up))
                return p
            ph = (7 if kind != "quad" else 6) * TAU_ * t
            w = math.sin(ph); b = abs(math.sin(ph))
            p.root_loc = Vector((0, 0, 0.003 * b * e))
            if kind == "quad":
                p.r("Chest", ("X", 2 * w * e)).r("Hips", ("Y", 3 * w * e))
                neckhead(p, (3 * math.sin(2 * ph) - 2) * e, 4 * w * e)
                knee = lambda x: 28 * max(0, x) * e
                leg(p, "leg_FL", -20 * w * e, knee(w)); leg(p, "leg_BR", -18 * w * e, knee(-w))
                leg(p, "leg_FR", 20 * w * e, knee(-w)); leg(p, "leg_BL", 18 * w * e, knee(w))
                dtail(p, 8 * e, ph * 0.5, 4 * e)
            else:
                p.r("Hips", ("X", 12 * e), ("Y", 3 * w * e))
                neckhead(p, -10 * e + 2 * math.sin(2 * ph) * e, 3 * w * e)
                p.r("leg_BL_1", ("X", (-12 + 30 * w) * e)).r("leg_BL_2", ("X", 40 * max(0, -w) * e))
                p.r("leg_BR_1", ("X", (-12 - 30 * w) * e)).r("leg_BR_2", ("X", 40 * max(0, w) * e))
                dtail(p, 6 * e, ph * 0.5, -8 * e)
                for a in arms:
                    p.r(a + "_1", ("X", -10 * e))
            return p
        def wave(t):
            e = env(t, 0.22); inner = env(t, 0.32)
            wv = math.sin(TAU_ * 3 * (t - 0.25) / 0.5) * inner if 0.25 < t < 0.75 else 0.0
            p = Pz()
            neckhead(p, -5 * e, 14 * e)       # looks round at you
            dtail(p, 8 * e, TAU_ * 2 * t)
            if ptero:
                p.r("wing_R_1", ("Y", (30 + 20 * wv) * e)).r("wing_R_2", ("Y", (15 + 25 * wv) * e))
            elif "arm_R" in chains:          # a tiny arm wave
                aw = C.get("arm_wave", 1.0)  # long arms (Therizinosaurus) lift less
                p.r("arm_R_1", ("X", -70 * aw * e), ("Z", -15 * e)).r("arm_R_2", ("X", (-25 + 30 * wv) * aw * e))
                p.r("Chest", ("Y", 3 * e))
            elif "leg_FR" in chains:         # lifts a front foot
                p.r("leg_FR_1", ("X", -40 * e), ("Y", 6 * wv * e)).r("leg_FR_2", ("X", (40 + 25 * wv) * e))
                p.r("Hips", ("Y", 3 * e)).r("Chest", ("Y", 5 * e))
            return p
    if C.get("sea"):
        # Swimmers float a little above the ground. Calm moves: a floating sway, a body wave,
        # a breach leap, a swim loop and a flipper (or tail) flick. "root" turns the whole body
        # round its middle; root_loc keeps that middle in place and adds the float height.
        LIFT = C.get("lift", 0.03)
        cen = (hips_p + chest_p) / 2
        fins = sorted(n for n in chains if n.startswith("fin_"))
        shark = name == "megalodon"
        def bodyturn(p, pitch=0.0, roll=0.0, yaw=0.0, dz=0.0):
            R = Matrix.Identity(3); steps = []
            for axis, deg in (("Y", roll), ("X", pitch), ("Z", yaw)):
                if deg:
                    R = Matrix.Rotation(math.radians(deg), 3, axis) @ R; steps.append((axis, deg))
            if steps:
                p.r("root", *steps)
            p.root_loc = cen - R @ cen + Vector((0, 0, dz))   # the rest pose is already lifted by LIFT
        def neckhead(p, pitch=0.0, yaw=0.0):
            n = len(neck_names)
            for nm in neck_names:
                p.r(nm, ("X", 0.5 * pitch / n), ("Z", 0.6 * yaw / n))
            p.r("Head", ("X", 0.5 * pitch), ("Z", 0.4 * yaw))
        def wavebody(p, amp, ph, lag=0.7):
            # a travelling side-to-side wave from the chest down the tail; the head stays steadier
            p.r("Chest", ("Z", 0.25 * amp * math.sin(ph)))
            p.r("Spine", ("Z", 0.35 * amp * math.sin(ph - lag)))
            p.r("Hips", ("Z", 0.3 * amp * math.sin(ph - 2 * lag)))
            chainw(p, "tail", "Z", amp, ph - 3 * lag, lag, 0.6)
            n = len(neck_names)
            for nm in neck_names:
                p.r(nm, ("Z", -0.3 * amp * math.sin(ph + lag) / n))
        def flap(p, nm, up, sweep=0.0, bend=0.0):
            s = 1 if nm.endswith("L") else -1
            p.r(nm + "_1", ("Y", -s * up), ("Z", s * sweep))
            p.r(nm + "_2", ("Y", -s * (0.5 * up + bend)))
        def paddle(p, amp, ph, sweep_amp=0.0):
            for nm in fins:
                k = 0.0 if "_F" in nm else math.pi   # front and back flippers take turns
                flap(p, nm, amp * math.sin(ph + k), sweep_amp * math.cos(ph + k), 0.4 * amp * math.sin(ph + k - 0.8))
        def idle(t):
            s_ = math.sin(TAU_ * t)
            p = Pz()
            bodyturn(p, pitch=1.5 * s_, roll=2.0 * math.sin(TAU_ * t + 1.2), dz=0.004 * s_)
            wavebody(p, 7, TAU_ * t)
            paddle(p, 7, TAU_ * t)
            neckhead(p, -2 * s_, 4 * math.sin(TAU_ * t + 0.6))
            return p
        def dance(t):
            e = env(t, 0.08)
            p = Pz()
            beat = abs(math.sin(4 * TAU_ * t))
            bodyturn(p, pitch=4 * math.sin(2 * TAU_ * t) * e, roll=9 * math.sin(2 * TAU_ * t + 0.5) * e,
                 yaw=8 * math.sin(TAU_ * t) * e, dz=(0.006 * beat + 0.008 * math.sin(2 * TAU_ * t)) * e)
            wavebody(p, 16 * e, 4 * TAU_ * t, 0.8)
            paddle(p, 22 * e, 4 * TAU_ * t, 10 * e)
            neckhead(p, 5 * math.sin(4 * TAU_ * t) * e, 10 * math.sin(2 * TAU_ * t) * e)
            return p
        def jump(t):
            p = Pz()
            dz = pitch = 0.0; kick = 0.0; tuck = 0.0
            # (nose up is a negative X turn: the head lies toward -Y)
            if t < 0.25:                       # dips and gathers speed
                q = t / 0.25
                dz = -0.01 * math.sin(math.pi * q); pitch = 6 * math.sin(math.pi * q); kick = q
            elif t < 0.75:                     # leaps out in an arc: nose up, over the top, nose down
                q = (t - 0.25) / 0.5
                dz = 0.11 * 4 * q * (1 - q) + 0.03 * smooth_(q)
                pitch = -28 * math.cos(math.pi * q) * smooth_(min(1.0, q / 0.18))
                kick = 1 - q; tuck = math.sin(math.pi * q)
            else:                              # dives back in, bobs and settles
                q = (t - 0.75) / 0.25
                dz = 0.03 * (1 - smooth_(q)) - 0.008 * math.sin(math.pi * q) * (1 - q)
                pitch = 28 * math.exp(-3 * q) * math.cos(5 * q) * (1 - q)
            bodyturn(p, pitch=pitch, dz=dz)
            wavebody(p, 18 * kick + 6, TAU_ * 5 * t, 0.7)
            for nm in fins:
                flap(p, nm, 10 * tuck, 35 * tuck)
            neckhead(p, -6 * tuck)
            return p
        def run(t):
            e = env(t, 0.08)
            ph = 8 * TAU_ * t
            p = Pz()
            bodyturn(p, pitch=2 * math.sin(ph * 0.5) * e, roll=(-6 + 3 * math.sin(ph * 0.25)) * e,
                 dz=0.005 * math.sin(ph * 0.5) * e)
            wavebody(p, 14 * e, ph, 0.75)
            paddle(p, 20 * e, ph, 12 * e)
            neckhead(p, -3 * e, 3 * math.sin(ph) * e)
            return p
        def wave(t):
            e = env(t, 0.22); inner = env(t, 0.32)
            wv = math.sin(TAU_ * 3 * (t - 0.25) / 0.5) * inner if 0.25 < t < 0.75 else 0.0
            p = Pz()
            bodyturn(p, roll=-8 * e, dz=0.004 * e)
            neckhead(p, -4 * e, 12 * e)        # looks round at you
            if shark:                         # a friendly tail flick
                chainw(p, "tail", "Z", 22 * inner, TAU_ * 3 * t, 0.6, 0.7)
            else:
                wavebody(p, 6 * e, TAU_ * 2 * t)
            if "fin_FR" in chains:
                flap(p, "fin_FR", (30 + 15 * wv) * e, -10 * e, 18 * wv * e)
            if "fin_FL" in chains:
                flap(p, "fin_FL", 6 * e)
            return p
    CL = [("idle", 1, 60, idle), ("dance", 61, 180, dance), ("jump", 181, 252, jump),
          ("run", 253, 372, run), ("wave", 373, 444, wave)]
    for pb in rig.pose.bones:
        pb.rotation_mode = 'QUATERNION'
    rig.animation_data_create()
    act = bpy.data.actions.new(name + "_anim")
    rig.animation_data.action = act
    prev = {}
    for cn, a, b, fn in CL:
        for f in range(a, b + 1):
            p = fn((f - a) / (b - a))
            for pb in rig.pose.bones:
                q = q_seq(pb.name, p.rot.get(pb.name, []))
                if pb.name in prev:
                    q.make_compatible(prev[pb.name])
                prev[pb.name] = q
                pb.rotation_quaternion = q
                if pb.name == "root":
                    M = rest3["root"]
                    pb.location = M.inverted() @ p.root_loc
                    sxy = 1 / math.sqrt(p.squash)
                    Sm = M.inverted() @ Matrix.Diagonal((sxy, sxy, p.squash)) @ M
                    pb.scale = (Sm[0][0], Sm[1][1], Sm[2][2])
                else:
                    pb.location = (0, 0, 0); pb.scale = (1, 1, 1)
                for prop in ("rotation_quaternion", "location", "scale"):
                    pb.keyframe_insert(prop, frame=f)
    scene.render.fps = FPS
    scene.frame_start, scene.frame_end = 1, CL[-1][2]

    # ---------------------------------------------------------------- turn back like the picture
    body_yaw = -C["yaw"] + C.get("show_yaw", 0)
    if C.get("auto"):
        C["face"] = body_yaw
    scene.frame_set(1)
    body.parent = None
    rig.rotation_euler = (0, 0, math.radians(body_yaw))
    bpy.ops.object.select_all(action='DESELECT')
    rig.select_set(True); bpy.context.view_layer.objects.active = rig
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    Rb = Matrix.Rotation(math.radians(body_yaw), 3, 'Z')
    me.transform(Rb.to_4x4()); me.update()
    body.parent = rig
    body.matrix_parent_inverse = Matrix.Identity(4)
    body.matrix_world = Matrix.Identity(4)
    co = np.array([v.co[:] for v in me.vertices])
    # root location keys were in root-bone space; root is vertical so they stay valid

    # ---------------------------------------------------------------- accessory fit (final frame)
    def bw(gname):
        g = body.vertex_groups.get(gname)
        out = np.zeros(nV)
        if g:
            for v in me.vertices:
                for gg in v.groups:
                    if gg.group == g.index:
                        out[v.index] = gg.weight
        return out
    hw = bw("Head")
    head_idx = np.nonzero(hw > 0.6)[0]
    hP = co[head_idx]
    H0 = np.array(arm.bones["Head"].head_local); H1 = np.array(arm.bones["Head"].tail_local)
    fdir = np.array([H1[0] - H0[0], H1[1] - H0[1], 0.0])
    fdir /= max(np.linalg.norm(fdir), 1e-6)
    side = np.array([-fdir[1], fdir[0], 0.0])        # left of the face
    hc = hP.mean(0)
    # eyes: darkest texels on the front third of the head
    tex_node = next(n for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE')
    img = tex_node.image
    IW, IH = img.size
    TEXa = np.array(img.pixels[:], dtype=np.float32).reshape(IH, IW, 4)[..., :3]
    uvl = me.uv_layers.active.data
    vuv = np.zeros((nV, 2))
    for poly in me.polygons:
        for li in poly.loop_indices:
            vuv[me.loops[li].vertex_index] = uvl[li].uv[:]
    vcol = TEXa[np.clip((vuv[:, 1] * IH).astype(int), 0, IH - 1), np.clip((vuv[:, 0] * IW).astype(int), 0, IW - 1)]
    # face direction and eyes were measured on the probe views (dark-texel guesses picked up
    # open mouths and dark fur)
    phi = math.radians(C["face"])
    fdir = np.array([math.sin(phi), -math.cos(phi), 0.0])
    side = np.array([-fdir[1], fdir[0], 0.0])
    ecen = np.array(Rb @ Vector(C["eyes"]))
    eye_z = float(ecen[2]); eye_x = float(C["eye_dx"])
    F = ecen + fdir * 0.013
    face_yaw = phi
    hc = ecen - fdir * 0.022          # middle of the head, a bit behind the eyes (hats)
    dark = []
    fwd_amt = (hP - hc) @ fdir
    # hat sits on the top of the head (ear chains and horns may poke through: that's fine)
    excl = sum(bw(n) for n in [g.name for g in body.vertex_groups if g.name.startswith("ear_")]) if any(
        g.name.startswith("ear_") for g in body.vertex_groups) else np.zeros(nV)
    core = head_idx[(excl[head_idx] < 0.3) & (np.linalg.norm(co[head_idx, :2] - hc[:2], axis=1) < 0.02)]
    top = float(co[core, 2].max()) if len(core) else float(hP[:, 2].max())
    hx = float(np.percentile(np.abs((hP - hc) @ side), 90))
    nb = arm.bones["neck"]
    N0 = np.array(nb.head_local)
    nw = bw("neck") + bw("Chest") * 0.0
    ring = np.nonzero((np.abs(co[:, 2] - N0[2]) < 0.006) & (np.linalg.norm(co[:, :2] - N0[:2], axis=1) < 0.06))[0]
    rr = np.linalg.norm(co[ring, :2] - N0[:2], axis=1) if len(ring) else np.array([0.02])
    neck_r = float(min(max(np.percentile(rr, 75), 0.012), 0.05))
    bow = N0 + fdir * (neck_r + 0.002)
    fl_dir = (0.55 * side + np.array([0, 0, 0.7]) + 0.3 * fdir); fl_dir /= np.linalg.norm(fl_dir)
    fl = hP[np.argmax((hP - hc) @ fl_dir)]
    FIT = dict(top=round(top - 0.004, 4), eyeY=round(eye_z, 4), eyeX=round(eye_x, 4), faceZ=round(-F[1], 4),
               neckY=round(float(N0[2]), 4), neckZ=round(float(-bow[1]), 4), neckRadius=round(neck_r + 0.002, 4),
               flower=[round(float(fl[0]), 4), round(float(fl[2]), 4), round(float(-fl[1]), 4)],
               hatScale=round(min(1.2, max(0.6, hx / 0.03)), 3),
               headX=round(float(hc[0]), 4), headZ=round(float(-hc[1]), 4),
               faceX=round(float(F[0]), 4), faceYaw=round(face_yaw, 4),
               neckX=round(float(bow[0]), 4), neckCX=round(float(N0[0]), 4), neckCZ=round(float(-N0[1]), 4))
    if C.get("dino"):
        # necks lie forward: put neck things round the middle of the neck, tilted along it
        nb_ = arm.bones["neck"]
        A0, A1 = np.array(nb_.head_local), np.array(nb_.tail_local)
        Nc = A0 + 0.45 * (A1 - A0); d = (A1 - A0) / max(np.linalg.norm(A1 - A0), 1e-6)
        rel = co - Nc
        along = rel @ d
        radial = np.linalg.norm(rel - along[:, None] * d[None], axis=1)
        band = (np.abs(along) < 0.003) & (radial < 0.05)
        nr = float(np.percentile(radial[band], 80)) if band.sum() > 8 else 0.02
        nr = 0.011 if kind == "ptero" else min(nr, 0.035)   # wings are not neck
        fwd = float(d @ fdir); up = float(d[2])
        FIT.update(neckY=round(float(Nc[2]), 4), neckCX=round(float(Nc[0]), 4), neckCZ=round(float(-Nc[1]), 4),
                   neckX=round(float(Nc[0]), 4), neckZ=round(float(-Nc[1]), 4), neckRadius=round(nr + 0.002, 4),
                   neckPitch=round(math.atan2(fwd, up), 4))
    print("FIT", FIT, "dark", len(dark))

    # ---------------------------------------------------------------- skins (hue shifts)
    def dilate(arr, it=10):
        arr = arr.copy(); empty = arr.sum(2) < 0.004
        for _ in range(it):
            acc = np.zeros_like(arr); cnt = np.zeros(arr.shape[:2], np.float32)
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nb_ = np.roll(np.roll(arr, dy, 0), dx, 1); ne = np.roll(np.roll(empty, dy, 0), dx, 1)
                acc += nb_ * (~ne)[..., None]; cnt += (~ne)
            fill = empty & (cnt > 0)
            arr[fill] = acc[fill] / cnt[fill][:, None]; empty = empty & ~fill
        return arr
    def resize(a, size):
        im = bpy.data.images.new("tmp", a.shape[1], a.shape[0], alpha=True)
        im.pixels.foreach_set(np.concatenate([a, np.ones(a.shape[:2] + (1,), np.float32)], 2).ravel())
        im.scale(size, size)
        out = np.array(im.pixels[:], np.float32).reshape(size, size, 4)[..., :3]
        bpy.data.images.remove(im); return out
    def save(a, path_png, jpg=True):
        im = bpy.data.images.new("out", a.shape[1], a.shape[0], alpha=False)
        im.pixels.foreach_set(np.concatenate([np.clip(a, 0, 1), np.ones(a.shape[:2] + (1,), np.float32)], 2).ravel())
        im.filepath_raw = path_png; im.file_format = 'PNG'; im.save(); bpy.data.images.remove(im)
        if jpg:
            out = path_png[:-4] + ".jpg"
            subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "78", path_png, "--out", out],
                           check=True, capture_output=True)
            os.remove(path_png)
            return out
        return path_png
    def rgb2hsv(a):
        r, g, b = a[..., 0], a[..., 1], a[..., 2]
        mx = a.max(-1); mn = a.min(-1); d = mx - mn
        h = np.zeros_like(mx)
        m = d > 1e-6
        rm = m & (mx == r); gm = m & (mx == g) & ~rm; bm = m & ~rm & ~gm
        h[rm] = ((g - b)[rm] / d[rm]) % 6; h[gm] = (b - r)[gm] / d[gm] + 2; h[bm] = (r - g)[bm] / d[bm] + 4
        return h / 6, np.where(mx > 1e-6, d / np.maximum(mx, 1e-6), 0), mx
    def hsv2rgb(h, s, v):
        i = np.floor(h * 6) % 6; f = h * 6 - np.floor(h * 6)
        p_ = v * (1 - s); q_ = v * (1 - f * s); t_ = v * (1 - (1 - f) * s)
        out = np.zeros(h.shape + (3,), np.float32)
        for k, (R_, G_, B_) in enumerate(((v, t_, p_), (q_, v, p_), (p_, v, t_), (p_, q_, v), (t_, p_, v), (v, p_, q_))):
            m = i == k
            out[m] = np.stack([R_[m], G_[m], B_[m]], -1)
        return out
    if C.get("dino"):
        # Meshy leaves a few unpainted (pure white) patches where the picture could not see:
        # fill them from the colours around them
        TEXa = TEXa.copy()
        hole = (TEXa.min(2) > 0.9) & ((TEXa.max(2) - TEXa.min(2)) < 0.05)
        print("DINO white texels filled", int(hole.sum()))
        TEXa[hole] = 0
        small = resize(dilate(TEXa, 60), TEX_SIZE)
    else:
        small = resize(dilate(TEXa), TEX_SIZE)
    Hh, Ss, Vv = rgb2hsv(small)
    used = small.sum(2) > 0.01
    wgt = (Ss * Vv * used).ravel()
    ang = Hh.ravel() * TAU_
    dom = (math.atan2((np.sin(ang) * wgt).sum(), (np.cos(ang) * wgt).sum()) / TAU_) % 1.0
    satw = np.clip((Ss - 0.08) / 0.2, 0, 1)        # neutral greys / whites / dark eyes stay put
    sk_dir = os.path.join(HERE, name + "_skins"); os.makedirs(sk_dir, exist_ok=True)
    for f_ in os.listdir(sk_dir):
        os.remove(os.path.join(sk_dir, f_))
    nat_path = save(small, os.path.join(sk_dir, "%s_skin_natural.png" % name))
    targets = {"sunny": 48 / 360, "ocean": 208 / 360, "mint": 158 / 360, "berry": 300 / 360, "galaxy": 248 / 360}
    if C.get("dino"):   # realistic animals: only gentle, natural-looking variations
        satw = np.clip((Ss - 0.03) / 0.12, 0, 1)
        nat_t = {"sunny": (40, 0.45), "ocean": (205, 0.35), "mint": (105, 0.5), "berry": (12, 0.5)}
    for sk in ("sunny", "ocean", "mint", "berry", "galaxy", "snow"):
        if C.get("dino"):
            if sk == "snow":
                s2 = Ss * (1 - 0.6 * satw); v2 = Vv + (1 - Vv) * 0.3 * satw; h2 = Hh
            elif sk == "galaxy":
                s2 = Ss * 0.9; v2 = Vv * (1 - 0.35 * satw); h2 = Hh
            else:
                tdeg, amt = nat_t[sk]
                dh = (tdeg / 360 - Hh + 0.5) % 1.0 - 0.5
                h2 = (Hh + dh * amt * satw) % 1.0
                s2 = np.clip(Ss * (0.75 if sk == "ocean" else 1.08), 0, 1); v2 = Vv.copy()
                if sk == "sunny":
                    v2 = Vv + (1 - Vv) * 0.12 * satw
            save(hsv2rgb(h2, s2, v2), os.path.join(sk_dir, "%s_skin_%s.png" % (name, sk)))
            continue
        if sk == "snow":
            s2 = Ss * (1 - 0.82 * satw); v2 = Vv + (1 - Vv) * 0.45 * satw; h2 = Hh
        else:
            delta = (targets[sk] - dom + 0.5) % 1.0 - 0.5
            h2 = (Hh + delta) % 1.0
            if abs(delta) < 40 / 360:
                # already close to this colour: pull every coloured texel onto the target hue
                dh = (targets[sk] - h2 + 0.5) % 1.0 - 0.5
                h2 = (h2 + dh * satw) % 1.0
            s2 = Ss.copy(); v2 = Vv.copy()
            if sk == "sunny":
                v2 = Vv + (1 - Vv) * 0.15 * satw
            if sk == "galaxy":
                v2 = Vv * (1 - 0.42 * satw); s2 = np.clip(Ss * 1.1, 0, 1)
        save(hsv2rgb(h2, s2, v2), os.path.join(sk_dir, "%s_skin_%s.png" % (name, sk)))
    main_rgb = small[used & (satw > 0.5)].mean(0) if (used & (satw > 0.5)).any() else small[used].mean(0)
    print("SKINS dominant hue %.0f deg, main color #%02X%02X%02X" % ((dom * 360,) + tuple(int(c * 255) for c in main_rgb)))
    nat = bpy.data.images.load(nat_path); nat.name = name + "_natural"
    tex_node.image = nat
    # Meshy n1 materials can carry metallic/roughness from glTF: keep a soft toy look
    bsdf = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if bsdf:
        for inp, val in (("Metallic", 0.0), ("Roughness", 0.75)):
            for l in list(bsdf.inputs[inp].links):
                mat.node_tree.links.remove(l)
            bsdf.inputs[inp].default_value = val
        for inp in ("Normal",):
            for l in list(bsdf.inputs[inp].links):
                mat.node_tree.links.remove(l)

    # ---------------------------------------------------------------- JSON, blend, USDZ
    with open(os.path.join(HERE, name + "_clips.json"), "w") as fh:
        json.dump({"fps": FPS, "frameStart": 1, "frameEnd": CL[-1][2],
                   "clips": [{"name": n, "start": a, "end": b, "startTime": round((a - 1) / FPS, 4),
                              "endTime": round((b - 1) / FPS, 4), "loop": n in ("idle", "dance", "run")}
                             for n, a, b, _ in CL],
                   "fit": FIT, "skins": ["natural", "sunny", "ocean", "mint", "berry", "galaxy", "snow"],
                   "bodyYaw": round(math.radians(body_yaw), 4),
                   "mainColor": "%02X%02X%02X" % tuple(int(c * 255) for c in main_rgb),
                   **({"dinosaur": True} if C.get("dino") else {})}, fh, indent=2)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, name + ".blend"))
    usdz = os.path.join(HERE, name + ".usdz")
    bpy.ops.wm.usd_export(
        filepath=usdz, export_animation=True, export_armatures=True, only_deform_bones=False,
        export_materials=True, generate_preview_surface=True, export_uvmaps=True, export_normals=True,
        export_lights=False, export_cameras=False, convert_orientation=True,
        export_global_forward_selection='NEGATIVE_Z', export_global_up_selection='Y',
        export_subdivision='IGNORE', convert_world_material=False, root_prim_path="/" + name.capitalize())
    print("TRIANGLES", tri_count)
    print("EXPORTED", usdz)

    # ---------------------------------------------------------------- previews, rig check, thumbnail
    prev_dir = os.path.join(HERE, "previews"); os.makedirs(prev_dir, exist_ok=True)
    scene.render.engine = 'BLENDER_EEVEE'
    scene.view_settings.view_transform = 'AgX'
    world = bpy.data.worlds.new("W"); scene.world = world; world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.70, 0.78, 0.90, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.35
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", 'SUN'))
    sun.data.energy = 2.2; sun.data.angle = math.radians(12)
    sun.rotation_euler = Euler((math.radians(50), 0, math.radians(-30)))
    scene.collection.objects.link(sun)
    tgt = bpy.data.objects.new("Target", None); tgt.location = (0, 0, 0.09)
    scene.collection.objects.link(tgt)
    fill = bpy.data.objects.new("Fill", bpy.data.lights.new("Fill", 'AREA'))
    fill.data.energy = 1.5; fill.data.size = 0.6; fill.location = (0.5, -0.5, 0.4)
    fill.constraints.new('TRACK_TO').target = tgt
    scene.collection.objects.link(fill)
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam")); cam.data.lens = 85
    scene.collection.objects.link(cam); scene.camera = cam
    cam.constraints.new('TRACK_TO').target = tgt
    cam.location = Vector((-0.40, -0.88, 0.28)).normalized() * 0.85

    def sheet(files, cols, path, size):
        rows = math.ceil(len(files) / cols)
        Sh = np.ones((size * rows, size * cols, 4), dtype=np.float32)
        for i, pth in enumerate(files):
            im = bpy.data.images.load(pth)
            px = np.array(im.pixels[:], dtype=np.float32).reshape(im.size[1], im.size[0], 4)
            r_, c_ = divmod(i, cols); rr = rows - 1 - r_
            Sh[rr * size:(rr + 1) * size, c_ * size:(c_ + 1) * size] = px
        out = bpy.data.images.new("sheet", size * cols, size * rows, alpha=True)
        out.pixels.foreach_set(Sh.ravel()); out.filepath_raw = path; out.file_format = 'PNG'; out.save()

    # thumbnail for the chooser: transparent, 3/4 front view, framed on the figure
    scene.render.film_transparent = True
    scene.render.resolution_x = scene.render.resolution_y = 256
    scene.frame_set(1)
    bb = co.min(0), co.max(0)
    ctr = Vector(((bb[0][0] + bb[1][0]) / 2, (bb[0][1] + bb[1][1]) / 2, (bb[0][2] + bb[1][2]) / 2))
    rad = float(np.linalg.norm(co - np.array(ctr), axis=1).max())
    tgt.location = ctr
    cam.data.lens = 85
    dist = rad / math.tan(cam.data.angle / 2) * 0.92
    cam.location = ctr + Vector((-0.35, -0.9, 0.3)).normalized() * dist
    p_thumb = os.path.join(HERE, name + "_thumb.png")
    scene.render.filepath = p_thumb; bpy.ops.render.render(write_still=True)
    # crop to the figure (alpha), square, small margin, so it fills the chooser tile
    im = bpy.data.images.load(p_thumb)
    A = np.array(im.pixels[:], np.float32).reshape(im.size[1], im.size[0], 4)
    ys, xs = np.nonzero(A[..., 3] > 0.05)
    half = int(max(ys.max() - ys.min(), xs.max() - xs.min()) * 0.54) + 2
    cy, cx = (ys.max() + ys.min()) // 2, (xs.max() + xs.min()) // 2
    out = np.zeros((2 * half, 2 * half, 4), np.float32)
    y0, x0 = cy - half, cx - half
    sy0, sx0 = max(0, y0), max(0, x0)
    sy1, sx1 = min(A.shape[0], y0 + 2 * half), min(A.shape[1], x0 + 2 * half)
    out[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0] = A[sy0:sy1, sx0:sx1]
    ti = bpy.data.images.new("thumb", 2 * half, 2 * half, alpha=True)
    ti.pixels.foreach_set(out.ravel()); ti.scale(192, 192)
    ti.filepath_raw = p_thumb; ti.file_format = 'PNG'; ti.save()
    scene.render.film_transparent = False

    if DO_RENDER:
        bpy.ops.mesh.primitive_plane_add(size=30)
        fm = bpy.data.materials.new("Floor"); fm.use_nodes = True
        fm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.86, 0.88, 0.9, 1)
        bpy.context.object.data.materials.append(fm)
        tgt.location = (0, 0, 0.09)
        cam.location = Vector((-0.40, -0.88, 0.28)).normalized() * 0.85
        scene.render.resolution_x = scene.render.resolution_y = 600
        shots = [("front", 1), ("idle", 30), ("dance", 106), ("jump", 216), ("run", 304), ("wave", 405)]
        files = []
        for label, f in shots:
            scene.frame_set(f)
            pth = os.path.join(prev_dir, "%s_%s.png" % (name, label))
            scene.render.filepath = pth; bpy.ops.render.render(write_still=True); files.append(pth)
        sheet(files, 3, os.path.join(prev_dir, name + "_sheet.png"), 600)
        scene.render.resolution_x = scene.render.resolution_y = 360
        scene.frame_set(30)
        sk_files = []
        for sk in ["natural", "sunny", "ocean", "mint", "berry", "galaxy", "snow"]:
            im = bpy.data.images.load(os.path.join(sk_dir, "%s_skin_%s.jpg" % (name, sk)))
            tex_node.image = im
            pth = os.path.join(prev_dir, "%s_skin_%s.png" % (name, sk))
            scene.render.filepath = pth; bpy.ops.render.render(write_still=True); sk_files.append(pth)
        tex_node.image = nat
        sheet(sk_files, 4, os.path.join(prev_dir, name + "_skins.png"), 360)
        # rig check: orthographic side view (body's left side) with bones, then side views of
        # a few key poses (jump in the air, run stride, wave, dance sway)
        from bpy_extras.object_utils import world_to_camera_view
        scene.render.resolution_x = scene.render.resolution_y = 500
        for c_ in list(cam.constraints):
            cam.constraints.remove(c_)
        cam.data.type = 'ORTHO'; cam.data.ortho_scale = 0.3
        lat = Rb @ Vector((1, 0, 0))
        cam.location = Vector((0, 0, 0.11)) + lat * 1.0
        cam.rotation_euler = (math.radians(90), 0, math.radians(90 + body_yaw))
        rc_files = []
        for label, f in (("rig", 1), ("jump", 216), ("run", 256), ("wave", 408), ("dance", 76)):
            scene.frame_set(f)
            pth = os.path.join(prev_dir, "%s_side_%s.png" % (name, label))
            scene.render.filepath = pth; bpy.ops.render.render(write_still=True)
            if label == "rig":
                im = bpy.data.images.load(pth); Nn = 500
                px = np.array(im.pixels[:], np.float32).reshape(Nn, Nn, 4)
                def dot(pw, clr, r=2):
                    c3 = world_to_camera_view(scene, cam, pw)
                    x, y = int(c3.x * Nn), int(c3.y * Nn)
                    px[max(0, y - r):y + r + 1, max(0, x - r):x + r + 1] = clr
                for b_ in arm.bones:
                    if not b_.use_deform:
                        continue
                    h, tl = rig.matrix_world @ b_.head_local, rig.matrix_world @ b_.tail_local
                    clr = (1, 0, 0, 1) if b_.name.startswith(("leg", "tent", "arm")) else (
                        (0, 0.6, 0, 1) if b_.name.startswith(("ear", "wing")) else ((0, 0, 1, 1) if b_.name.startswith("tail") else (1, 0, 1, 1)))
                    for s_ in np.linspace(0, 1, 40):
                        dot(h.lerp(tl, s_), clr, 1)
                    dot(h, (1, 1, 0, 1), 3)
                im.pixels.foreach_set(px.ravel()); im.filepath_raw = pth; im.save()
            rc_files.append(pth)
        sheet(rc_files, 5, os.path.join(prev_dir, name + "_rigcheck.png"), 500)
        print("PREVIEWS", prev_dir)


if NAME in CREATURES:
    import subprocess
    build_creature(NAME)
    sys.exit(0)


# --------------------------------------------------------------------------
# 1. import and normalise
# --------------------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
bpy.ops.import_scene.gltf(filepath=os.path.join(SRC, NAME + "_rigged.glb"))
rig = next(o for o in scene.objects if o.type == 'ARMATURE')
body = next(o for o in scene.objects if o.type == 'MESH' and o.parent == rig and o.data.materials)
for o in list(scene.objects):
    if o not in (rig, body):
        bpy.data.objects.remove(o, do_unlink=True)
for pb in rig.pose.bones:
    pb.custom_shape = None
if rig.animation_data:
    rig.animation_data.action = None
for a in list(bpy.data.actions):
    bpy.data.actions.remove(a)
if IS_ROBOT:   # Meshy rigs robots 1.7 m tall: make them toy size, feet on the floor
    bpy.context.view_layer.update()
    zs = [(body.matrix_world @ v.co).z for v in body.data.vertices]
    k = ROBOT_HEIGHT / (max(zs) - min(zs))
    rig.scale = rig.scale * k
    bpy.context.view_layer.update()
    wv = [body.matrix_world @ v.co for v in body.data.vertices]
    rig.location.z -= min(p.z for p in wv)
    rig.location.x -= (min(p.x for p in wv) + max(p.x for p in wv)) / 2
    rig.location.y -= (min(p.y for p in wv) + max(p.y for p in wv)) / 2

bpy.ops.object.select_all(action='DESELECT')
body.select_set(True); bpy.context.view_layer.objects.active = body
bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
bpy.ops.object.select_all(action='DESELECT')
rig.select_set(True); bpy.context.view_layer.objects.active = rig
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
body.parent = rig
body.matrix_parent_inverse = Matrix.Identity(4)
arm_mod = next(m for m in body.modifiers if m.type == 'ARMATURE')
arm_mod.object = rig
mat = body.data.materials[0]
mat.name = "Skin"
body.name = body.data.name = NAME

me = body.data
co = [v.co.copy() for v in me.vertices]
height = max(p.z for p in co) - min(p.z for p in co)
tri_count = sum(len(p.vertices) - 2 for p in me.polygons)
print("REST height %.4f m, triangles %d, verts %d" % (height, tri_count, len(co)))

# --------------------------------------------------------------------------
# texture helpers (sample colours on the model)
# --------------------------------------------------------------------------
tex_node = next(n for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE')
src_img = tex_node.image
W, H = src_img.size
TEX = np.array(src_img.pixels[:], dtype=np.float32).reshape(H, W, 4)[..., :3]
uv = me.uv_layers.active.data
vert_uv = {}
for poly in me.polygons:
    for li in poly.loop_indices:
        vert_uv.setdefault(me.loops[li].vertex_index, uv[li].uv.copy())

def vcolor(i):
    u, v = vert_uv[i]
    x = min(W - 1, max(0, int(u * W))); y = min(H - 1, max(0, int(v * H)))
    return TEX[y, x]

def median_color(idx):
    return np.median(np.array([vcolor(i) for i in idx]), axis=0)

# --------------------------------------------------------------------------
# skeleton additions: root, ears, tail
# --------------------------------------------------------------------------
vg = {g.name: g for g in body.vertex_groups}

def group(name):
    if name not in vg:
        vg[name] = body.vertex_groups.new(name=name)
    return vg[name]

def set_weights(i, weights):
    for g in body.vertex_groups:
        g.remove([i])
    tot = sum(weights.values()) or 1
    for n, w in weights.items():
        if w > 1e-4:
            group(n).add([i], w / tot, 'REPLACE')

def centroid(idx):
    return sum((co[i] for i in idx), Vector()) / max(1, len(idx))

new_bones = []   # (name, head, tail, parent)

ear_regions = {}
if CFG.get("ears"):
    for side in "LR":
        b = CFG["ears"][side]
        idx = [i for i, p in enumerate(co) if in_box(p, b)]
        zb = CFG["ears"]["base_z"]
        zt = max(co[i].z for i in idx)
        base = centroid([i for i in idx if co[i].z < zb + 0.15 * (zt - zb)])
        mid = centroid([i for i in idx if abs(co[i].z - (zb + 0.5 * (zt - zb))) < 0.08 * (zt - zb)])
        tip = centroid([i for i in idx if co[i].z > zt - 0.08 * (zt - zb)])
        base.z = zb
        new_bones += [("ear_" + side, base, mid, "Head"), ("ear_%s_tip" % side, mid, tip, "ear_" + side)]
        ear_regions[side] = (idx, zb, zt)
        print("EAR", side, len(idx), "verts, base", tuple(round(x, 3) for x in base), "tip", tuple(round(x, 3) for x in tip))

tail_idx = []
if CFG.get("tail"):
    t = CFG["tail"]
    regions = t["region"] if isinstance(t["region"], list) else [t["region"]]
    tail_idx = [i for i, p in enumerate(co) if any(in_box(p, r) for r in regions)]
    if t.get("root") == "min_y":       # the part touching the body is the frontmost
        y0 = min(co[i].y for i in tail_idx)
        root_pts = [i for i in tail_idx if co[i].y < y0 + 0.004]
    else:
        root_pts = [i for i in tail_idx if co[i].z >= t["root_min_z"]] or tail_idx[:1]
    B = centroid(root_pts)
    far = max(tail_idx, key=lambda i: (co[i] - B).length)
    L = (co[far] - B).length
    tail_s = {i: min(1.0, (co[i] - B).length / L) for i in tail_idx}
    pts = [B] + [centroid([i for i in tail_idx if abs(tail_s[i] - s) < 0.07]) for s in (0.33, 0.66)] + [co[far]]
    for k in range(3):
        new_bones.append(("tail_%d" % (k + 1), pts[k], pts[k + 1], "Hips" if k == 0 else "tail_%d" % k))
    print("TAIL", len(tail_idx), "verts, from", tuple(round(x, 3) for x in B), "to", tuple(round(x, 3) for x in co[far]))

bpy.ops.object.select_all(action='DESELECT')
rig.select_set(True); bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode='EDIT')
eb = rig.data.edit_bones
root = eb.new("root"); root.head = (0, 0, 0); root.tail = (0, 0, 0.03); root.use_deform = False
eb["Hips"].parent = root
for n, h, t_, parent in new_bones:
    b = eb.new(n); b.head = h; b.tail = t_; b.parent = eb[parent]; b.use_deform = True
    b.use_connect = n.endswith("_tip") or (n.startswith("tail_") and n != "tail_1")
bpy.ops.object.mode_set(mode='OBJECT')

for side, (idx, zb, zt) in ear_regions.items():
    for i in idx:
        s = (co[i].z - zb) / (zt - zb)
        head_w = 1 - ss(-0.15, 0.12, s)
        k = ss(0.4, 0.72, s)
        set_weights(i, {"Head": head_w, "ear_" + side: (1 - head_w) * (1 - k), "ear_%s_tip" % side: (1 - head_w) * k})
for i in tail_idx:
    s = tail_s[i]
    hips_w = 1 - ss(0.0, 0.14, s)
    f = min(2.999, s * 3)
    k = int(f); fr = ss(0.25, 0.75, f - k)
    w = {"Hips": hips_w}
    if k < 2:
        w["tail_%d" % (k + 1)] = (1 - hips_w) * (1 - fr)
        w["tail_%d" % (k + 2)] = (1 - hips_w) * fr
    else:
        w["tail_3"] = 1 - hips_w     # the last bone takes the whole tip
    set_weights(i, w)

unweighted = [v.index for v in me.vertices if not any(g.weight > 1e-4 for g in v.groups)]
print("UNWEIGHTED verts", len(unweighted))

# --------------------------------------------------------------------------
# accessory fit (app space: x right, y up, z toward viewer = -Blender y)
# --------------------------------------------------------------------------
head_g = vg["Head"].index
def wt(i, gi):
    for g in me.vertices[i].groups:
        if g.group == gi:
            return g.weight
    return 0.0
ear_set = set(i for idx, _, _ in ear_regions.values() for i in idx)
head_idx = [i for i in range(len(co)) if wt(i, head_g) > 0.6 and i not in ear_set]
if IS_ROBOT and not IS_ANIMAL2:   # small armoured heads: everything mostly moved by the Head bone, above the neck joint
    hb = rig.data.bones["Head"]
    # the head is what sits above the neck joint near the middle (door wings and shoulder
    # armour stick up at the sides, so keep to a narrow column)
    nz = hb.head_local.z
    hx0, hy0 = hb.head_local.x, hb.head_local.y
    head_idx = [i for i in range(len(co)) if co[i].z > nz - 0.003 and abs(co[i].x - hx0) < 0.022
                and abs(co[i].y - hy0) < 0.03]
hz0 = min(co[i].z for i in head_idx); hz1 = max(co[i].z for i in head_idx)
print("HEAD verts", len(head_idx), "z %.3f..%.3f" % (hz0, hz1))
hx = max(abs(co[i].x) for i in head_idx)
dark = [i for i in head_idx if co[i].y < 0 and vcolor(i).max() < 0.12]
eye_z = float(np.mean([co[i].z for i in dark])) if dark else hz0 + 0.55 * (hz1 - hz0)
eye_x = float(np.mean([abs(co[i].x) for i in dark])) if dark else 0.35 * hx
if IS_ROBOT and not IS_ANIMAL2 and not any(abs(co[i].z - eye_z) < 0.01 for i in head_idx):
    eye_z = hz0 + 0.58 * (hz1 - hz0)   # dark pixels away from the head column: use proportions
face_front = max((-co[i].y for i in head_idx if abs(co[i].z - eye_z) < 0.01),
                 default=max(-co[i].y for i in head_idx))
neck_z = hz0 + 0.04 * (hz1 - hz0)
ring = [i for i in range(len(co)) if abs(co[i].z - neck_z) < 0.004 and abs(co[i].x) < 0.6 * hx]
neck_front = max(-co[i].y for i in ring)
neck_r = float(np.percentile([math.hypot(co[i].x, co[i].y) for i in ring], 90))
_hcx = sum(co[i].x for i in head_idx) / len(head_idx)
top_mid = max((co[i].z for i in head_idx if abs(co[i].x - _hcx) < 0.25 * hx), default=hz1)
hc = Vector((0, 0, (hz0 + hz1) / 2))
dirv = Vector((0.55, -0.45, 0.70)).normalized()
fl = max(head_idx, key=lambda i: (co[i] - hc).normalized().dot(dirv))
FIT = dict(top=round(top_mid - 0.007, 4), eyeY=round(eye_z, 4), eyeX=round(eye_x, 4),
           faceZ=round(face_front + 0.003, 4), neckY=round(neck_z, 4), neckZ=round(neck_front + 0.002, 4),
           neckRadius=round(neck_r + 0.002, 4),
           flower=[round(co[fl].x, 4), round(co[fl].z, 4), round(-co[fl].y, 4)],
           hatScale=round(min(1.2, max(0.6, hx / 0.05)), 3))
if IS_ROBOT and not IS_ANIMAL2:   # glowing robot eyes are not dark: use the head's proportions instead
    FIT["eyeY"] = round(hz0 + 0.58 * (hz1 - hz0), 4)
    FIT["eyeX"] = round(max(0.008, 0.3 * hx), 4)
    band = [i for i in head_idx if abs(co[i].z - FIT["eyeY"]) < 0.006]
    FIT["faceZ"] = round(max(-co[i].y for i in band) + 0.003, 4) if band else FIT["faceZ"]
print("FIT", FIT, "dark verts", len(dark))

# --------------------------------------------------------------------------
# 2. clips
# --------------------------------------------------------------------------
rest3 = {b.name: b.matrix_local.to_3x3() for b in rig.data.bones}
BONES = set(rest3)

def q_seq(bone, *steps):
    """Rotations about armature axes applied in order, e.g. ('Y', 62), ('X', -20)."""
    R = Matrix.Identity(3)
    for axis, deg in steps:
        if deg:
            R = Matrix.Rotation(math.radians(deg), 3, axis) @ R
    M = rest3[bone]
    return (M.inverted() @ R @ M).to_quaternion()

ARM_DOWN = CFG.get("arm_down", 62)
if IS_ROBOT:
    # robots already stand with their arms down: only lower them to about 70 degrees
    d = rig.data.bones["LeftArm"].tail_local - rig.data.bones["LeftArm"].head_local
    down = math.degrees(math.atan2(-d.z, max(1e-6, math.hypot(d.x, d.y))))
    ARM_DOWN = max(0.0, 70.0 - down)
    if NAME == "helicopter":   # Meshy's arm bones point along the rotor arm: leave the arms as built
        ARM_DOWN = 0.0
ARM_DOWN_L = ARM_DOWN_R = ARM_DOWN
if IS_ANIMATRONIC or IS_ANIMAL2 or IS_DINO:
    # performers often hold one arm out and one down: settle each arm on its own
    def _down(b):
        d = rig.data.bones[b].tail_local - rig.data.bones[b].head_local
        return math.degrees(math.atan2(-d.z, max(1e-6, math.hypot(d.x, d.y))))
    ARM_DOWN_L = max(0.0, 70.0 - _down("LeftArm"))
    ARM_DOWN_R = max(0.0, 70.0 - _down("RightArm"))
    print("ANIMATRONIC arms L %.0f R %.0f" % (ARM_DOWN_L, ARM_DOWN_R))
    print("ROBOT arm rest %.0f deg below level -> ARM_DOWN %.0f" % (down, ARM_DOWN))
ONE = Vector((1, 1, 1))

class P:
    def __init__(self):
        self.rot = {}          # bone -> list of (axis, deg) applied in order
        self.root_loc = Vector()
        self.squash = 1.0      # root scale z (volume kept)
    def r(self, bone, *steps):
        if bone in BONES:
            self.rot.setdefault(bone, []).extend(steps)
        return self

def relaxed():
    p = P()
    p.r("LeftArm", ("Y", ARM_DOWN_L)).r("RightArm", ("Y", -ARM_DOWN_R))
    return p

EA, TA = CFG.get("ear_amp", 1.0), CFG.get("tail_amp", 1.0)

def ears(p, side_deg, fwd_deg, tip_side, tip_fwd):
    # +Y rotation leans the top toward the animal's left (+X); +X leans it forward
    p.r("ear_L", ("X", fwd_deg * EA), ("Y", side_deg * EA)).r("ear_R", ("X", fwd_deg * EA), ("Y", side_deg * EA))
    p.r("ear_L_tip", ("X", tip_fwd * EA), ("Y", tip_side * EA)).r("ear_R_tip", ("X", tip_fwd * EA), ("Y", tip_side * EA))

def tail(p, swish, lift=0.0):
    for k, f in ((1, 0.6), (2, 1.0), (3, 1.3)):
        p.r("tail_%d" % k, ("Z", swish * f * TA), ("X", lift * f * TA))  # +lift raises the tail

def idle(t):
    s = math.sin(TAU * t)
    lag = math.sin(math.pi * t) ** 2 * math.sin(TAU * t - 0.9)
    p = relaxed()
    p.squash = 1 + 0.02 * s
    p.r("Spine01", ("X", 2 * s)).r("Head", ("X", -1.5 * s), ("Y", 2.5 * s))
    p.r("LeftArm", ("X", 3 * s)).r("RightArm", ("X", 3 * s))
    ears(p, 4 * s, 0, 7 * lag, -3 * lag)
    tail(p, 10 * s, 3 * lag)
    return p

def dance(t):
    e = env(t, 0.1)
    sway = math.sin(2 * TAU * t)
    beat = abs(math.sin(4 * TAU * t))
    sq = (1 - beat) ** 3
    p = P()
    p.root_loc = Vector((0, 0, 0.008 * beat * e))
    p.squash = 1 - 0.07 * sq * e
    p.r("Hips", ("Y", 10 * sway * e)).r("Spine01", ("Y", -5 * sway * e))
    p.r("Head", ("Y", -9 * math.sin(2 * TAU * t - 0.5) * e), ("Z", 6 * sway * e))
    up = 20 * math.sin(4 * TAU * t)
    p.r("LeftArm", ("Y", ARM_DOWN - (ARM_DOWN + 55 + up) * e), ("X", -10 * e))
    p.r("RightArm", ("Y", -ARM_DOWN + (ARM_DOWN + 55 - up) * e), ("X", -10 * e))
    p.r("LeftForeArm", ("Y", -25 * e)).r("RightForeArm", ("Y", 25 * e))
    p.r("LeftUpLeg", ("X", -14 * max(0, sway) * e)).r("RightUpLeg", ("X", -14 * max(0, -sway) * e))
    p.r("LeftLeg", ("X", 20 * max(0, sway) * e)).r("RightLeg", ("X", 20 * max(0, -sway) * e))
    ears(p, 14 * math.sin(2 * TAU * t - 0.9) * e, 8 * math.sin(4 * TAU * t) * e,
         24 * math.sin(2 * TAU * t - 1.7) * e, -10 * beat * e)
    tail(p, 35 * math.sin(2 * TAU * t - 0.6) * e, 10 * e)
    return p

def jump(t):
    u = (t * 3) % 1.0
    lift = crouch = air = ear = 0.0
    sz = 1.0
    if u < 0.22:
        c = math.sin(math.pi * u / 0.22)
        sz = 1 - 0.14 * c; crouch = c; ear = 0.3 * c
    elif u < 0.72:
        q = (u - 0.22) / 0.5
        lift = 0.045 * 4 * q * (1 - q)
        sz = 1 + 0.07 * math.sin(math.pi * q)
        air = math.sin(math.pi * q)
        ear = -math.sin(math.pi * min(1, q * 1.4))
    else:
        q = (u - 0.72) / 0.28
        k = math.sin(math.pi * q ** 0.6)
        sz = 1 - 0.18 * k; ear = 0.9 * k; crouch = 0.6 * k
    p = relaxed()
    p.root_loc = Vector((0, 0, lift)); p.squash = sz
    p.r("Spine01", ("X", 8 * crouch)).r("Head", ("X", -5 * crouch + 4 * air))
    p.r("LeftArm", ("Y", -55 * air), ("X", 15 * crouch)).r("RightArm", ("Y", 55 * air), ("X", 15 * crouch))
    p.r("LeftUpLeg", ("X", -25 * air)).r("RightUpLeg", ("X", -25 * air))
    p.r("LeftLeg", ("X", 35 * air)).r("RightLeg", ("X", 35 * air))
    ears(p, 0, 18 * ear, 0, 30 * ear)
    tail(p, 0, 55 * air - 10 * crouch)
    return p

def run(t):
    e = env(t, 0.08)
    ph = 10 * TAU * t
    w = math.sin(ph)
    b = abs(math.sin(ph))
    p = relaxed()
    p.root_loc = Vector((0, 0, 0.006 * b * e)); p.squash = 1 - 0.03 * (1 - b) * e
    p.r("Hips", ("Z", 6 * w * e)).r("Spine01", ("X", 10 * e), ("Z", -4 * w * e))
    p.r("Head", ("X", -7 * e), ("Y", 2.5 * w * e))
    p.r("LeftUpLeg", ("X", 38 * w * e)).r("RightUpLeg", ("X", -38 * w * e))
    p.r("LeftLeg", ("X", 30 * max(0, w) * e)).r("RightLeg", ("X", 30 * max(0, -w) * e))
    p.r("LeftArm", ("Y", -18 * e), ("X", -45 * w * e)).r("RightArm", ("Y", 18 * e), ("X", 45 * w * e))
    p.r("LeftForeArm", ("Z", 35 * e)).r("RightForeArm", ("Z", -35 * e))
    ears(p, 0, -22 * e + 5 * math.sin(2 * ph - 1) * e, 0, -22 * e + 10 * math.sin(2 * ph - 1.8) * e)
    tail(p, 15 * math.sin(ph - 0.8) * e, 20 * e)
    return p

def wave(t):
    e = env(t, 0.22)
    inner = env(t, 0.32)
    wv = math.sin(TAU * 3 * (t - 0.25) / 0.5) * inner if 0.25 < t < 0.75 else 0.0
    p = relaxed()
    p.r("RightArm", ("Y", (ARM_DOWN + 30) * e), ("Z", 28 * e))
    p.r("RightForeArm", ("Y", (35 + 25 * wv) * e))
    p.r("Spine01", ("Y", 3 * e)).r("Head", ("Y", -8 * e)).r("LeftArm", ("Y", 4 * e))
    ears(p, -5 * e, 0, (-6 + 6 * wv) * e, 0)
    tail(p, 20 * math.sin(TAU * 2 * t) * e, 5 * e)
    return p

# robots: calm mechanical idle, a stiff "robot dance" of held poses, and a big wave
def robot_idle(t):
    s = math.sin(TAU * t)
    p = relaxed()
    p.squash = 1 + 0.008 * s
    p.r("Spine01", ("X", 1.2 * s)).r("Head", ("Z", 9 * math.sin(TAU * t + 0.6)))
    p.r("LeftArm", ("X", 2 * s)).r("RightArm", ("X", 2 * s))
    return p

ROBOT_STEPS = [  # (left arm up, right arm up, left forearm, right forearm, head turn, lean, knee dip)
    (60, 0, 90, 0, 15, 3, 1), (60, 60, 90, 90, 0, 0, 0), (60, 60, -50, -50, -15, -3, 1), (60, 60, 90, 90, 0, 0, 0),
    (0, 60, 0, 90, -15, -3, 1), (60, 60, 90, 90, 0, 0, 0), (100, 100, 40, 40, 0, 0, 1), (60, 60, 90, 90, 0, 0, 0),
    (30, 90, 0, 60, 20, 4, 1), (90, 30, 60, 0, -20, -4, 1), (30, 90, 0, 60, 20, 4, 1), (90, 30, 60, 0, -20, -4, 1),
    (60, 60, 90, 90, 0, 0, 0), (120, 120, 30, 30, 0, 0, 1), (60, 60, 90, 90, 0, 0, 0), (0, 0, 0, 0, 0, 0, 0)]

def robot_dance(t):
    n = len(ROBOT_STEPS)
    f = min(n - 1e-6, t * n)
    k = int(f); u = f - k
    a = ROBOT_STEPS[k - 1] if k > 0 else (0, 0, 0, 0, 0, 0, 0)
    b = ROBOT_STEPS[k]
    m = ss(0.0, 0.3, u)                      # snap quickly to the new pose, then hold it
    v = [x + (y - x) * m for x, y in zip(a, b)]
    p = relaxed()
    p.r("LeftArm", ("Y", -v[0])).r("RightArm", ("Y", v[1]))
    p.r("LeftForeArm", ("Y", -v[2])).r("RightForeArm", ("Y", v[3]))
    p.r("Head", ("Z", v[4])).r("Spine01", ("Y", v[5]))
    dip = v[6] * math.sin(math.pi * min(1, u / 0.6)) if b[6] else 0.0
    p.root_loc = Vector((0, 0, -0.004 * dip)); p.squash = 1 - 0.03 * dip
    p.r("LeftUpLeg", ("X", -10 * dip)).r("RightUpLeg", ("X", -10 * dip))
    p.r("LeftLeg", ("X", 18 * dip)).r("RightLeg", ("X", 18 * dip))
    return p

def robot_wave(t):
    e = env(t, 0.22); inner = env(t, 0.32)
    wv = math.sin(TAU * 3 * (t - 0.25) / 0.5) * inner if 0.25 < t < 0.75 else 0.0
    p = relaxed()
    p.r("RightArm", ("Y", 150 * e)).r("RightForeArm", ("Y", (20 + 25 * wv) * e))
    p.r("Head", ("Z", -10 * e), ("Y", -6 * e)).r("Spine01", ("Y", 3 * e))
    return p

if NAME in ROBOTS:
    idle, dance, wave = robot_idle, robot_dance, robot_wave
if IS_DINO and NAME != "pteranodon":
    _run0, _jump0 = run, jump
    def run(t):        # two-legged dinos run leaning forward
        p = _run0(t); e = env(t, 0.08)
        p.r("Spine01", ("X", 18 * e)).r("Head", ("X", -14 * e))
        return p
    def jump(t):       # a heavier hop: deeper squash on landing
        p = _jump0(t); p.squash = 1 - (1 - p.squash) * 1.3
        return p

def servo(fn, steps_per_clip):
    """Animatronic timing: the clip only moves in steps. Inside each step the time snaps
    forward in ~0.12 s with a small overshoot and settle, then holds still."""
    def stepped(t):
        n = steps_per_clip
        f = min(n - 1e-6, t * n)
        k = int(f); u = f - k
        snap = ss(0.0, 0.32, u)
        settle = 0.12 * math.sin(math.pi * min(1, max(0, (u - 0.18) / 0.3))) * (1 - ss(0.3, 0.6, u))
        return fn(min(1.0, (k + snap + settle) / n))
    return stepped

def anim_idle(t):
    # look left, look right, small torso pivot: one joint at a time
    p = relaxed()
    turn = 18 * math.sin(TAU * t)
    p.r("Head", ("Z", turn), ("Y", 6 * math.sin(2 * TAU * t)))
    p.r("Spine01", ("Z", 4 * math.sin(TAU * t + 1.2)))
    return p

def anim_dance(t):
    # showtime routine: arm raises in steps, head bobs and tilts, torso pivots side to side
    beat = math.sin(4 * TAU * t)
    side = math.sin(2 * TAU * t)
    p = relaxed()
    p.r("Spine01", ("Z", 8 * side)).r("Head", ("X", -5 * max(0, beat)), ("Y", 6 * side))
    p.r("LeftArm", ("Y", -(50 + 30 * max(0, side))), ("X", -20))
    p.r("RightArm", ("Y", 50 + 30 * max(0, -side)), ("X", -20))
    p.r("LeftForeArm", ("Y", -60 * max(0, beat))).r("RightForeArm", ("Y", 60 * max(0, -beat)))
    p.r("LeftUpLeg", ("X", -10 * max(0, side))).r("RightUpLeg", ("X", -10 * max(0, -side)))
    return p

def anim_wave(t):
    e = env(t, 0.2); inner = env(t, 0.32)
    wv = math.sin(TAU * 3 * (t - 0.25) / 0.5) * inner if 0.25 < t < 0.75 else 0.0
    p = relaxed()
    p.r("RightArm", ("Y", 140 * e)).r("RightForeArm", ("Y", (25 + 30 * wv) * e))
    p.r("Head", ("Y", -12 * e))
    return p

def anim_jump(t):
    # locked knees: the hop comes from the root only, arms snap up in the air
    u = (t * 3) % 1.0
    air = math.sin(math.pi * (u - 0.2) / 0.55) if 0.2 < u < 0.75 else 0.0
    p = relaxed()
    p.root_loc = Vector((0, 0, 0.03 * air))
    p.r("LeftArm", ("Y", -60 * air)).r("RightArm", ("Y", 60 * air)).r("Head", ("X", 6 * air))
    return p

def anim_run(t):
    # stiff march in place
    e = env(t, 0.08)
    w = math.sin(10 * TAU * t)
    p = relaxed()
    p.r("LeftUpLeg", ("X", 30 * w * e)).r("RightUpLeg", ("X", -30 * w * e))
    p.r("LeftArm", ("X", -35 * w * e)).r("RightArm", ("X", 35 * w * e))
    p.r("Head", ("Z", 4 * w * e))
    return p

if IS_ANIMATRONIC:
    idle = servo(anim_idle, 6)      # 2 s: a look every third of a second
    dance = servo(anim_dance, 32)   # 4 s: 8 snaps per second, on the beat
    jump = servo(anim_jump, 18)
    run = servo(anim_run, 40)
    wave = servo(anim_wave, 14)

CLIPS = [("idle", 1, 60, idle), ("dance", 61, 180, dance), ("jump", 181, 252, jump),
         ("run", 253, 372, run), ("wave", 373, 444, wave)]

for pb in rig.pose.bones:
    pb.rotation_mode = 'QUATERNION'
rig.animation_data_create()
action = bpy.data.actions.new(NAME + "_anim")
rig.animation_data.action = action
prev = {}
for name, a, b, fn in CLIPS:
    for f in range(a, b + 1):
        p = fn((f - a) / (b - a))
        for pb in rig.pose.bones:
            q = q_seq(pb.name, *p.rot.get(pb.name, []))
            if pb.name in prev:
                q.make_compatible(prev[pb.name])
            prev[pb.name] = q
            pb.rotation_quaternion = q
            if pb.name == "root":
                M = rest3["root"]
                pb.location = M.inverted() @ p.root_loc
                sxy = 1 / math.sqrt(p.squash)
                Sm = M.inverted() @ Matrix.Diagonal((sxy, sxy, p.squash)) @ M
                pb.scale = (Sm[0][0], Sm[1][1], Sm[2][2])
            else:
                pb.location = (0, 0, 0); pb.scale = ONE
            for prop in ("rotation_quaternion", "location", "scale"):
                pb.keyframe_insert(prop, frame=f)

scene.render.fps = FPS
scene.frame_start, scene.frame_end = 1, CLIPS[-1][2]
scene.frame_set(1)

# --------------------------------------------------------------------------
# 3. skin textures
# --------------------------------------------------------------------------
def hexrgb(h):
    return np.array([(h >> 16) & 255, (h >> 8) & 255, h & 255], dtype=np.float32) / 255

def resize(img_arr, size):
    im = bpy.data.images.new("tmp", img_arr.shape[1], img_arr.shape[0], alpha=True)
    rgba = np.concatenate([img_arr, np.ones(img_arr.shape[:2] + (1,), np.float32)], axis=2)
    im.pixels.foreach_set(rgba.ravel()); im.scale(size, size)
    out = np.array(im.pixels[:], dtype=np.float32).reshape(size, size, 4)[..., :3]
    bpy.data.images.remove(im)
    return out

def ycc(rgb):
    y = rgb @ np.array([0.299, 0.587, 0.114], np.float32)
    cb = (rgb[..., 2] - y) * 0.564; cr = (rgb[..., 0] - y) * 0.713
    return y, cb, cr

# reference colours sampled on the model: back of the head = main fur, tummy = belly
back_head = [i for i in head_idx if co[i].y > 0.6 * max(co[j].y for j in head_idx)]
body_z = 0.35 * height
tummy = [i for i in range(len(co)) if abs(co[i].z - body_z) < 0.01 and abs(co[i].x) < 0.008 and co[i].y < 0]
tummy = sorted(tummy, key=lambda i: co[i].y)[:20]
MAIN_REF = median_color(back_head) if back_head else np.array([0.5, 0.5, 0.5])
BELLY_REF = median_color(tummy) if tummy else MAIN_REF * 1.2
print("REF main", MAIN_REF.round(3), "belly", BELLY_REF.round(3))

def dilate(arr, iterations=8):
    """Grow UV islands into the empty (black) background so downscaling and mipmaps
    don't pull dark seams into the fur."""
    arr = arr.copy()
    empty = arr.sum(axis=2) < 0.004
    for _ in range(iterations):
        acc = np.zeros_like(arr); cnt = np.zeros(arr.shape[:2], np.float32)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nb = np.roll(np.roll(arr, dy, 0), dx, 1); ne = np.roll(np.roll(empty, dy, 0), dx, 1)
            acc += nb * (~ne)[..., None]; cnt += (~ne)
        fill = empty & (cnt > 0)
        arr[fill] = acc[fill] / cnt[fill][:, None]
        empty = empty & ~fill
    return arr

small = resize(dilate(TEX), TEX_SIZE)
if IS_ANIMATRONIC:
    # Fedir: the worn, dark theme-park paint read too dark on a phone: lift the shadows gently
    small = np.clip(np.clip(small, 0, 1) ** 0.6 * 1.07, 0, 1)
Y, CB, CR = ycc(small)

def weight_for(ref, sigma_c, ylo, yhi):
    ry, rcb, rcr = ycc(ref[None, None, :])
    dc = np.sqrt((CB - rcb) ** 2 + (CR - rcr) ** 2)
    ratio = Y / max(float(ry), 1e-3)
    wy = np.clip((ratio - ylo) / 0.08, 0, 1) * np.clip((yhi - ratio) / 0.08, 0, 1)
    return np.exp(-(dc / sigma_c) ** 2) * wy, ratio

# when main and belly are both pale (bunny), split them by brightness halfway
ym, yb = float(ycc(MAIN_REF[None, None, :])[0]), float(ycc(BELLY_REF[None, None, :])[0])
main_hi, belly_lo = 1.35, 0.75
if yb > ym:
    main_hi = min(main_hi, (yb / ym + 1) / 2)
    belly_lo = max(belly_lo, (1 + ym / yb) / 2)
w_main, r_main = weight_for(MAIN_REF, 0.06, 0.45, main_hi)
w_belly, r_belly = weight_for(BELLY_REF, 0.035, belly_lo, 1.15)
w_belly = w_belly * (1 - w_main)
skin_dir = os.path.join(HERE, NAME + "_skins")
os.makedirs(skin_dir, exist_ok=True)

def save_png(arr, path):
    im = bpy.data.images.new("out", arr.shape[1], arr.shape[0], alpha=True)
    rgba = np.concatenate([np.clip(arr, 0, 1), np.ones(arr.shape[:2] + (1,), np.float32)], axis=2)
    im.pixels.foreach_set(rgba.ravel())
    im.filepath_raw = path; im.file_format = 'PNG'; im.save()
    bpy.data.images.remove(im)

def _hsv(a):
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    mx = a.max(-1); mn = a.min(-1); d = mx - mn
    h = np.zeros_like(mx); msk = d > 1e-6
    rm = msk & (mx == r); gm = msk & (mx == g) & ~rm; bm = msk & ~rm & ~gm
    h[rm] = ((g - b)[rm] / d[rm]) % 6; h[gm] = (b - r)[gm] / d[gm] + 2; h[bm] = (r - g)[bm] / d[bm] + 4
    return h / 6, np.where(mx > 1e-6, d / np.maximum(mx, 1e-6), 0), mx

def _rgb(h, s_, v):
    i = np.floor(h * 6) % 6; f = h * 6 - np.floor(h * 6)
    p_ = v * (1 - s_); q_ = v * (1 - f * s_); t_ = v * (1 - (1 - f) * s_)
    out = np.zeros(h.shape + (3,), np.float32)
    for k, (R_, G_, B_) in enumerate(((v, t_, p_), (q_, v, p_), (p_, v, t_), (p_, q_, v), (t_, p_, v), (v, p_, q_))):
        msk = i == k; out[msk] = np.stack([R_[msk], G_[msk], B_[msk]], -1)
    return out

if IS_ROBOT:
    # like the creatures: rotate the hue of the whole paint job (greys and metal stay grey)
    for f_ in os.listdir(skin_dir):
        os.remove(os.path.join(skin_dir, f_))
    Hh, Ss, Vv = _hsv(small)
    used = small.sum(2) > 0.01
    wgt = (Ss * Vv * used).ravel(); ang = Hh.ravel() * TAU
    dom = (math.atan2((np.sin(ang) * wgt).sum(), (np.cos(ang) * wgt).sum()) / TAU) % 1.0
    satw = np.clip((Ss - 0.08) / 0.2, 0, 1)
    targets = {"sunny": 48 / 360, "ocean": 208 / 360, "mint": 158 / 360, "berry": 300 / 360, "galaxy": 248 / 360}
    outs = {"natural": small}
    for sk in ("sunny", "ocean", "mint", "berry", "galaxy", "snow"):
        if sk == "snow":
            outs[sk] = _rgb(Hh, Ss * (1 - 0.82 * satw), Vv + (1 - Vv) * 0.45 * satw)
            continue
        delta = (targets[sk] - dom + 0.5) % 1.0 - 0.5
        h2 = (Hh + delta) % 1.0
        if abs(delta) < 40 / 360:
            dh = (targets[sk] - h2 + 0.5) % 1.0 - 0.5
            h2 = (h2 + dh * satw) % 1.0
        s2, v2 = Ss.copy(), Vv.copy()
        if sk == "sunny": v2 = Vv + (1 - Vv) * 0.15 * satw
        if sk == "galaxy": v2 = Vv * (1 - 0.42 * satw); s2 = np.clip(Ss * 1.1, 0, 1)
        outs[sk] = _rgb(h2, s2, v2)
    for sk, arr in outs.items():
        png = os.path.join(skin_dir, "%s_skin_%s.png" % (NAME, sk))
        save_png(arr, png)
        subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "78", png, "--out", png[:-4] + ".jpg"],
                       check=True, capture_output=True)
        os.remove(png)
    MAIN_HEX = "%02X%02X%02X" % tuple(int(c * 255) for c in (small[used & (satw > 0.5)].mean(0) if (used & (satw > 0.5)).any() else small[used].mean(0)))
    print("ROBOT SKINS dominant hue %.0f, main #%s" % (dom * 360, MAIN_HEX))
    SKINS = {k: None for k in ("sunny", "ocean", "mint", "berry", "galaxy", "snow")}
else:
  save_png(small, os.path.join(skin_dir, "%s_skin_natural.png" % NAME))
  for skin, (mh, bh) in SKINS.items():
    main_c, belly_c = hexrgb(mh), hexrgb(bh)
    # light skins: darker stripes stay visible because the ratio keeps the shading
    new_main = main_c[None, None, :] * np.clip(r_main, 0, 1.4)[..., None]
    new_belly = belly_c[None, None, :] * np.clip(r_belly, 0, 1.2)[..., None]
    out = small * (1 - w_main - w_belly)[..., None] + new_main * w_main[..., None] + new_belly * w_belly[..., None]
    save_png(out, os.path.join(skin_dir, "%s_skin_%s.png" % (NAME, skin)))
print("SKINS", skin_dir)

# the USDZ carries the natural texture at 1024 px
nat = bpy.data.images.load(os.path.join(skin_dir, "%s_skin_natural.%s" % (NAME, "jpg" if IS_ROBOT else "png")))
nat.name = NAME + "_natural"
tex_node.image = nat

# --------------------------------------------------------------------------
# 4/5. clips JSON, blend, USDZ
# --------------------------------------------------------------------------
with open(os.path.join(HERE, NAME + "_clips.json"), "w") as fh:
    json.dump({"fps": FPS, "frameStart": 1, "frameEnd": CLIPS[-1][2],
               "clips": [{"name": n, "start": a, "end": b,
                          "startTime": round((a - 1) / FPS, 4), "endTime": round((b - 1) / FPS, 4),
                          "loop": n in ("idle", "dance", "run")}
                         for n, a, b, _ in CLIPS],
               "fit": FIT, "skins": ["natural"] + list(SKINS),
               **({"bodyYaw": 0.0, "mainColor": MAIN_HEX, "robot": True,
                   "vehicle": dict(file=NAME + "_vehicle",
                                   **json.load(open(os.path.join(HERE, NAME + "_vehicle.json"))))}
                  if NAME in ROBOTS else {}),
               **({"bodyYaw": 0.0, "mainColor": MAIN_HEX, "animatronic": True} if IS_ANIMATRONIC else {}),
               **({"bodyYaw": 0.0, "mainColor": MAIN_HEX} if (IS_ANIMAL2 or IS_DINO) else {}),
               **({"dinosaur": True} if IS_DINO else {})},
              fh, indent=2)

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, NAME + ".blend"))
usdz = os.path.join(HERE, NAME + ".usdz")
bpy.ops.wm.usd_export(
    filepath=usdz, export_animation=True, export_armatures=True, only_deform_bones=False,
    export_materials=True, generate_preview_surface=True, export_uvmaps=True, export_normals=True,
    export_lights=False, export_cameras=False, convert_orientation=True,
    export_global_forward_selection='NEGATIVE_Z', export_global_up_selection='Y',
    export_subdivision='IGNORE', convert_world_material=False, root_prim_path="/" + NAME.capitalize(),
)
print("TRIANGLES", tri_count)
print("EXPORTED", usdz)

if IS_ROBOT:   # chooser thumbnail: transparent, 3/4 front, cropped to the figure
    sc_ = bpy.context.scene
    sc_.render.engine = 'BLENDER_EEVEE'; sc_.view_settings.view_transform = 'AgX'
    sc_.render.film_transparent = True; sc_.render.resolution_x = sc_.render.resolution_y = 256
    w_ = bpy.data.worlds.new("TW"); sc_.world = w_; w_.use_nodes = True
    w_.node_tree.nodes["Background"].inputs[0].default_value = (0.70, 0.78, 0.90, 1)
    w_.node_tree.nodes["Background"].inputs[1].default_value = 0.6
    sun_ = bpy.data.objects.new("TSun", bpy.data.lights.new("TSun", 'SUN')); sun_.data.energy = 2.5
    sun_.rotation_euler = Euler((math.radians(50), 0, math.radians(-30))); sc_.collection.objects.link(sun_)
    cam_ = bpy.data.objects.new("TCam", bpy.data.cameras.new("TCam")); cam_.data.lens = 85
    sc_.collection.objects.link(cam_); sc_.camera = cam_
    sc_.frame_set(1)
    ctr = Vector((0, 0, ROBOT_HEIGHT / 2))
    cam_.location = ctr + Vector((-0.35, -0.9, 0.25)).normalized() * 1.1
    cam_.rotation_euler = (ctr - cam_.location).to_track_quat('-Z', 'Y').to_euler()
    p_thumb = os.path.join(HERE, NAME + "_thumb.png")
    sc_.render.filepath = p_thumb; bpy.ops.render.render(write_still=True)
    im_ = bpy.data.images.load(p_thumb)
    A = np.array(im_.pixels[:], np.float32).reshape(im_.size[1], im_.size[0], 4)
    ys, xs = np.nonzero(A[..., 3] > 0.05)
    half = int(max(ys.max() - ys.min(), xs.max() - xs.min()) * 0.54) + 2
    cy, cx = (ys.max() + ys.min()) // 2, (xs.max() + xs.min()) // 2
    out_ = np.zeros((2 * half, 2 * half, 4), np.float32)
    y0, x0 = cy - half, cx - half
    sy0, sx0 = max(0, y0), max(0, x0); sy1, sx1 = min(A.shape[0], y0 + 2 * half), min(A.shape[1], x0 + 2 * half)
    out_[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0] = A[sy0:sy1, sx0:sx1]
    ti = bpy.data.images.new("thumb", 2 * half, 2 * half, alpha=True); ti.pixels.foreach_set(out_.ravel()); ti.scale(192, 192)
    ti.filepath_raw = p_thumb; ti.file_format = 'PNG'; ti.save()
    sc_.render.film_transparent = False
    for o_ in (sun_, cam_): bpy.data.objects.remove(o_, do_unlink=True)

# --------------------------------------------------------------------------
# previews: clip frames + one frame per skin
# --------------------------------------------------------------------------
if DO_RENDER:
    prev_dir = os.path.join(HERE, "previews")
    os.makedirs(prev_dir, exist_ok=True)
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = scene.render.resolution_y = 800
    scene.view_settings.view_transform = 'AgX'
    world = bpy.data.worlds.new("W"); scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.70, 0.78, 0.90, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.35
    bpy.ops.mesh.primitive_plane_add(size=30)
    fm = bpy.data.materials.new("Floor"); fm.use_nodes = True
    fm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.86, 0.88, 0.9, 1)
    bpy.context.object.data.materials.append(fm)
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", 'SUN'))
    sun.data.energy = 2.2; sun.data.angle = math.radians(12)
    sun.rotation_euler = Euler((math.radians(50), 0, math.radians(-30)))
    scene.collection.objects.link(sun)
    tgt = bpy.data.objects.new("Target", None); tgt.location = (0, 0, 0.11)
    scene.collection.objects.link(tgt)
    fill = bpy.data.objects.new("Fill", bpy.data.lights.new("Fill", 'AREA'))
    fill.data.energy = 1.5; fill.data.size = 0.6; fill.location = (0.5, -0.5, 0.4)
    fill.constraints.new('TRACK_TO').target = tgt
    scene.collection.objects.link(fill)
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam")); cam.data.lens = 85
    scene.collection.objects.link(cam); scene.camera = cam
    cam.constraints.new('TRACK_TO').target = tgt
    cam.location = Vector((-0.40, -0.88, 0.28)).normalized() * 0.85

    def sheet(files, cols, path, size):
        rows = math.ceil(len(files) / cols)
        S = np.ones((size * rows, size * cols, 4), dtype=np.float32)
        for i, p in enumerate(files):
            img = bpy.data.images.load(p)
            px = np.array(img.pixels[:], dtype=np.float32).reshape(img.size[1], img.size[0], 4)
            r, c = divmod(i, cols)
            rr = rows - 1 - r
            S[rr * size:(rr + 1) * size, c * size:(c + 1) * size] = px
        out = bpy.data.images.new("sheet", size * cols, size * rows, alpha=True)
        out.pixels.foreach_set(S.ravel())
        out.filepath_raw = path; out.file_format = 'PNG'; out.save()

    shots = [("front", 1), ("idle", 30), ("dance", 106), ("jump", 216), ("run", 304), ("wave", 405)]
    files = []
    for label, f in shots:
        scene.frame_set(f)
        p = os.path.join(prev_dir, "%s_%s.png" % (NAME, label))
        scene.render.filepath = p
        bpy.ops.render.render(write_still=True)
        files.append(p)
    sheet(files, 3, os.path.join(prev_dir, NAME + "_sheet.png"), 800)

    scene.render.resolution_x = scene.render.resolution_y = 400
    scene.frame_set(30)
    sk_files = []
    for skin in ["natural"] + list(SKINS):
        img = bpy.data.images.load(os.path.join(skin_dir, "%s_skin_%s.%s" % (NAME, skin, "jpg" if IS_ROBOT else "png")))
        tex_node.image = img
        p = os.path.join(prev_dir, "%s_skin_%s.png" % (NAME, skin))
        scene.render.filepath = p
        bpy.ops.render.render(write_still=True)
        sk_files.append(p)
    tex_node.image = nat
    sheet(sk_files, 4, os.path.join(prev_dir, NAME + "_skins.png"), 400)
    print("PREVIEWS", prev_dir)

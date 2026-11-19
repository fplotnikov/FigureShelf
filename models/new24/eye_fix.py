"""Hand-read eye positions for the 12 new animals (front ortho probe renders, rest pose).
Run after make_meshy_animal.py and before measure_nose.py:  python3 new24/eye_fix.py"""
import json, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EYES = {  # name: (eyeY, eyeX, faceX)
    "lion": (0.133, 0.0247, 0.0), "zebra": (0.1367, 0.019, 0.002), "ostrich": (0.167, 0.010, 0.009),
    "horse": (0.133, 0.026, 0.0), "tiger": (0.1467, 0.029, 0.0), "beaver": (0.150, 0.026, 0.0),
    "raccoonkid": (0.128, 0.027, -0.0157), "elephant": (0.145, 0.028, 0.0), "hippo": (0.169, 0.0155, 0.0),
    "rhino": (0.137, 0.0317, 0.0), "mouse": (0.130, 0.029, -0.0047), "turtle": (0.1517, 0.020, 0.0),
}
for n, (y, x, fx) in EYES.items():
    p = os.path.join(HERE, n + "_clips.json"); d = json.load(open(p))
    d["fit"].update(eyeY=y, eyeX=x)
    if fx: d["fit"]["faceX"] = fx
    json.dump(d, open(p, "w"), indent=2); print(n, d["fit"]["eyeY"], d["fit"]["eyeX"])

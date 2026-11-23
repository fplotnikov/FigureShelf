"""Hand-set fit values for the six third-batch animals (read from new6/probe_fit.py and
checked in the app). Run after make_meshy_animal.py + measure_nose.py:  python3 new6/fit_fix.py
Writes models/<name>_clips.json and the copy in FigureShelf.swiftpm/Resources."""
import json, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = {
    # round one-piece bodies: the bow tie goes just under the smile / beak, not at eye height
    "shark": dict(top=0.155, neckY=0.088, neckZ=0.131, neckCZ=0.075, neckRadius=0.066),   # long body: ring round the front half
    "parrot": dict(faceZ=0.118, neckY=0.112, neckZ=0.113, neckCZ=0.05, neckRadius=0.066),
    # the bow tie sat on the snout: put it in the dip under the chin
    "mole": dict(neckY=0.117, neckZ=0.061, neckRadius=0.06),
    # the dark nose was read as the eyes: real eyes are wider apart and a bit higher
    "koala": dict(eyeX=0.025, eyeY=0.140),
}
for n, vals in FIX.items():
    for p in (os.path.join(HERE, n + "_clips.json"),
              os.path.join(HERE, "..", "FigureShelf.swiftpm", "Resources", n + "_clips.json")):
        d = json.load(open(p)); d["fit"].update(vals); json.dump(d, open(p, "w"), indent=2)
    print(n, vals)

"""Hand-set fit values for Fedir's second set of creatures (checked in the app). Run after
make_meshy_animal.py for them:  python3 models/creatures2/fit_fix.py"""
import json, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = {
    # the hat sat inside the head: the top of the head is higher up on this round whale
    "tuftwhale": dict(top=0.118, headZ=0.06, hatScale=0.8),
    # the bow tie sat beside the glasses: put it on the white chest under the face
    "spindlecrab": dict(neckY=0.088, neckZ=0.06, neckRadius=0.035, neckX=-0.02, neckCX=-0.02),
    # the bow tie floated over the back: this low creature's neck is just above its knees
    "siftrunk": dict(neckY=0.021, neckRadius=0.025, neckX=-0.046, neckCX=-0.046, top=0.058),
}
for n, vals in FIX.items():
    for p in (os.path.join(HERE, n + "_clips.json"),
              os.path.join(HERE, "..", "FigureShelf.swiftpm", "Resources", n + "_clips.json")):
        d = json.load(open(p)); d["fit"].update(vals); json.dump(d, open(p, "w"), indent=2)
    print(n, vals)

"""Hand-set fit values for Fedir's second set of animatronics (checked in the app). Run after
make_meshy_animal.py for them:  python3 models/animatronics2/fit_fix.py"""
import json, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = {
    # the bow tie sat on the mouth: the neck is the narrow part just above the shoulders
    "chameleon": dict(neckY=0.17, neckZ=0.04, neckRadius=0.03),
    "showkangaroo": dict(neckY=0.168, neckZ=0.03, neckRadius=0.025),
    # the bow tie sat on the shoulder: centre it on the chest just under the head
    "showelephant": dict(neckY=0.158, neckZ=0.068, neckRadius=0.05, neckX=0.0, neckCX=0.0),
    # head bent forward: the bow tie sat on the snout and the glasses inside the head
    "pangolin": dict(neckY=0.17, neckZ=0.088, neckRadius=0.045, eyeY=0.215, eyeX=0.018, faceZ=0.095, faceX=0.016),
}
for n, vals in FIX.items():
    for p in (os.path.join(HERE, n + "_clips.json"),
              os.path.join(HERE, "..", "FigureShelf.swiftpm", "Resources", n + "_clips.json")):
        d = json.load(open(p)); d["fit"].update(vals); json.dump(d, open(p, "w"), indent=2)
    print(n, vals)

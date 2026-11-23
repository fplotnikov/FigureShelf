"""Hand-set fit values for the fourth-batch animals (eye centres from new6b/find_eyes.py, face
depth from new6/probe_fit.py, checked in the app). Run after make_meshy_animal.py and
measure_nose.py:  python3 new6b/fit_fix.py
Glasses sit on the face at eye height (faceZ = front of the face there), not out at the snout
tip, otherwise they slide sideways when the figure is seen from an angle."""
import json, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = {
    "deer": dict(eyeX=0.023, eyeY=0.128, faceZ=0.043),
    "redpanda": dict(eyeX=0.019, eyeY=0.140, faceZ=0.074,
                     neckY=0.097, neckZ=0.071, neckRadius=0.056),   # scarf under the chin, not round the muzzle
    # dark eyes on dark fur were missed: eyes sit above the big snout; bow tie under the chin
    "moose": dict(eyeX=0.019, eyeY=0.133, faceZ=0.034, neckY=0.082, neckZ=0.03,
                  noseY=0.108, noseZ=0.036),
    "kangaroo": dict(eyeX=0.019, eyeY=0.131, faceZ=0.064, top=0.174),   # hats sat down between the ears
    "giraffe": dict(eyeX=0.020, eyeY=0.154, faceZ=0.037),
    "capybara": dict(eyeX=0.028, eyeY=0.157, faceZ=0.045),
}
for n, vals in FIX.items():
    for p in (os.path.join(HERE, n + "_clips.json"),
              os.path.join(HERE, "..", "FigureShelf.swiftpm", "Resources", n + "_clips.json")):
        d = json.load(open(p)); d["fit"].update(vals); json.dump(d, open(p, "w"), indent=2)
    print(n, vals)

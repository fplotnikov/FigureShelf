"""Find the eye centres of a finished figure from its colour texture and position map:
the darkest texels on the front of the head, split into left and right.
    blender -b --factory-startup --python new6b/find_eyes.py -- moose [lumMax]"""
import bpy, sys, os, json
import numpy as np
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
a = sys.argv[sys.argv.index("--") + 1:]
name = a[0]; lum_max = float(a[1]) if len(a) > 1 else 0.09
def load(p):
    im = bpy.data.images.load(p); im.colorspace_settings.name = 'Non-Color'
    w, h = im.size; px = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)
    return px[:, :, :3]
d = json.load(open(os.path.join(HERE, name + "_clips.json")))
box = np.array(d["posBox"]); fit = d["fit"]
pos = load(os.path.join(HERE, name + "_pos.png"))
skin = load(os.path.join(HERE, name + "_skins", name + "_skin_natural.jpg"))
if skin.shape != pos.shape:   # resample skin to the position map's size (nearest)
    ys = (np.arange(pos.shape[0]) * skin.shape[0] / pos.shape[0]).astype(int)
    xs = (np.arange(pos.shape[1]) * skin.shape[1] / pos.shape[1]).astype(int)
    skin = skin[ys][:, xs]
valid = pos.sum(2) > 0.01
p = box[:3] + pos * (box[3:] - box[:3])
lum = skin @ np.array([0.299, 0.587, 0.114])
sel = valid & (lum < lum_max) & (p[:, :, 1] > (float(a[2]) if len(a) > 2 else fit["neckY"] + 0.01)) & (p[:, :, 2] > 0)
pts = p[sel]
print("dark front-head texels", len(pts))
for side, m in (("L", pts[:, 0] > 0.004), ("R", pts[:, 0] < -0.004)):
    q = pts[m]
    if len(q): print("EYE", name, side, "x %.4f y %.4f z %.4f n %d" % (q[:, 0].mean(), q[:, 1].mean(), q[:, 2].mean(), len(q)))
c = pts[np.abs(pts[:, 0]) <= 0.004]
if len(c): print("CENTRE dark (nose?) y %.4f z %.4f n %d" % (c[:, 1].mean(), c[:, 2].mean(), len(c)))
print("FIT", fit)

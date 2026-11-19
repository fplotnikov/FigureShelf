"""Measure where the nose tip is on a finished figure and add it to its clips JSON fit
(noseX, noseY, noseZ, app space: x right, y up, z toward the viewer). Used for the red nose
and the moustache.  blender -b --factory-startup --python measure_nose.py -- kitty
Reads models/<name>.blend (rest pose) and the eye point already in the JSON; writes
models/<name>_clips.json and FigureShelf.swiftpm/Resources/<name>_clips.json."""
import bpy, sys, os, json, math
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
name = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.open_mainfile(filepath=os.path.join(HERE, name + ".blend"))
ob = next(o for o in bpy.data.objects if o.type == 'MESH' and o.vertex_groups.get("Head"))
me = ob.data
M = ob.matrix_world
co = np.array([(M @ v.co)[:] for v in me.vertices])
app = np.stack([co[:, 0], co[:, 2], -co[:, 1]], 1)          # Blender -> app axes
gi = ob.vertex_groups["Head"].index
hw = np.zeros(len(co))
for v in me.vertices:
    for g in v.groups:
        if g.group == gi:
            hw[v.index] = g.weight
path = os.path.join(HERE, name + "_clips.json")
data = json.load(open(path))
fit = data["fit"]
yaw = fit.get("faceYaw", 0.0)
f = np.array([math.sin(yaw), 0, math.cos(yaw)])               # face direction
side = np.array([math.cos(yaw), 0, -math.sin(yaw)])
E = np.array([fit.get("faceX", 0.0), fit["eyeY"], fit["faceZ"]])
rel = app - E
cand = (hw > 0.4) & (rel[:, 1] < -0.002) & (rel[:, 1] > -0.04) & (np.abs(rel @ side) < 0.01)
idx = np.nonzero(cand)[0]
fwd = rel[idx] @ f
tip = idx[fwd > fwd.max() - 0.0015]                            # the front-most bit, averaged
N = app[tip].mean(0)
fit.update(noseX=round(float(N[0]), 4), noseY=round(float(N[1]), 4), noseZ=round(float(N[2]), 4))
print("NOSE", name, fit["noseX"], fit["noseY"], fit["noseZ"], "below eyes %.3f, ahead %.3f" % (E[1] - N[1], float((N - E) @ f)))
for p in (path, os.path.join(HERE, "..", "FigureShelf.swiftpm", "Resources", name + "_clips.json")):
    json.dump(data, open(p, "w"), indent=2)

"""Print the surface profile of a finished figure (app axes: x right, y up, z toward viewer)
to set its hat/glasses/neck fit by hand.  blender -b --python new6/probe_fit.py -- shark"""
import bpy, sys, os, json
import numpy as np
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
name = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.open_mainfile(filepath=os.path.join(HERE, name + ".blend"))
ob = next(o for o in bpy.data.objects if o.type == 'MESH' and o.vertex_groups.get("Head"))
M = ob.matrix_world
co = np.array([(M @ v.co)[:] for v in ob.data.vertices])
app = np.stack([co[:, 0], co[:, 2], -co[:, 1]], 1)
fit = json.load(open(os.path.join(HERE, name + "_clips.json")))["fit"]
print("FIT", name, fit)
print("height %.3f" % app[:, 1].max())
for y in np.arange(0.06, app[:, 1].max(), 0.01):
    band = app[np.abs(app[:, 1] - y) < 0.004]
    mid = band[np.abs(band[:, 0]) < 0.006]
    fz = mid[:, 2].max() if len(mid) else float('nan')
    print("y %.3f  frontZ(x=0) %.4f  halfwidth %.4f  backZ %.4f" % (y, fz, np.abs(band[:, 0]).max() if len(band) else 0, band[:, 2].min() if len(band) else 0))
ey, ex = fit["eyeY"], fit["eyeX"]
for sx in (-1, 1):
    s = app[(np.abs(app[:, 1] - ey) < 0.005) & (np.abs(app[:, 0] - sx * ex) < 0.005)]
    print("eye surface x=%+.3f z=%.4f" % (sx * ex, s[:, 2].max() if len(s) else float('nan')))

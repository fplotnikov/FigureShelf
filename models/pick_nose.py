"""Set a figure's nose point by picking it on a close-up render (same camera as the check
render: 300x300, looking at the old nose point from the face side).
blender -b --factory-startup --python pick_nose.py -- <name> <px> <py>   (pixels from top-left)
Casts a ray from that pixel onto the model and writes noseX/Y/Z into both clips JSON files."""
import bpy, sys, os, json, math
from mathutils import Vector
HERE = os.path.dirname(os.path.abspath(__file__))
a = sys.argv[sys.argv.index("--") + 1:]
name, px, py = a[0], float(a[1]), float(a[2])
bpy.ops.wm.open_mainfile(filepath=os.path.join(HERE, name + ".blend"))
sc = bpy.context.scene; sc.frame_set(1)
path = os.path.join(HERE, name + "_clips.json"); data = json.load(open(path)); fit = data["fit"]
N = Vector((fit["noseX"], -fit["noseZ"], fit["noseY"]))
yaw = fit.get("faceYaw", 0.0); f = Vector((math.sin(yaw), -math.cos(yaw), 0)); side = Vector((f.y, -f.x, 0))
cam = bpy.data.objects.new("C", bpy.data.cameras.new("C")); sc.collection.objects.link(cam)
cam.data.lens = 50; sc.render.resolution_x = sc.render.resolution_y = 300
cam.location = N + (f * 0.9 + side * 0.35 + Vector((0, 0, 0.25))).normalized() * 0.16
cam.rotation_euler = (N - cam.location).to_track_quat('-Z', 'Y').to_euler()
bpy.context.view_layer.update()
frame = cam.data.view_frame(scene=sc)              # local corners: tr, br, bl, tl
tr, br, bl, tl = [cam.matrix_world @ c for c in frame]
u, v = px / 300, py / 300
target = tl + (tr - tl) * u + (bl - tl) * v
d = (target - cam.location).normalized()
hit, loc, *_ = sc.ray_cast(bpy.context.evaluated_depsgraph_get(), cam.location, d)
assert hit, "no hit"
fit.update(noseX=round(loc.x, 4), noseY=round(loc.z, 4), noseZ=round(-loc.y, 4))
print("PICKED", name, fit["noseX"], fit["noseY"], fit["noseZ"])
for p in (path, os.path.join(HERE, "..", "FigureShelf.swiftpm", "Resources", name + "_clips.json")):
    json.dump(data, open(p, "w"), indent=2)

"""Probe a Meshy creature: normalise (longest side SIZE, feet on floor, centred), print stats,
render front / left-side / top orthographic views with a 2 cm grid (darker lines every 10 cm,
origin lines red).  blender -b --factory-startup --python probe_creature.py -- name [yaw_deg] [size]"""
import bpy, sys, os, math
import numpy as np
from mathutils import Vector, Euler, Matrix
HERE = os.path.dirname(os.path.abspath(__file__))
A = sys.argv[sys.argv.index("--") + 1:]
NAME = A[0]; YAW = float(A[1]) if len(A) > 1 else 0.0; SIZE = float(A[2]) if len(A) > 2 else 0.22
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
bpy.ops.import_scene.gltf(filepath=os.path.join(HERE, NAME, NAME + "_static.glb"))
meshes = [o for o in sc.objects if o.type == 'MESH']
print("MESH OBJECTS", len(meshes), [o.name for o in meshes])
for o in meshes:
    o.select_set(True)
bpy.context.view_layer.objects.active = meshes[0]
if len(meshes) > 1:
    bpy.ops.object.join()
ob = bpy.context.view_layer.objects.active
bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
me = ob.data
co = np.array([v.co[:] for v in me.vertices])
R = np.array(Matrix.Rotation(math.radians(YAW), 3, 'Z'))
co = co @ R.T
lo, hi = co.min(0), co.max(0)
s = SIZE / (hi - lo).max()
co = (co - [(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]]) * s
me.vertices.foreach_set("co", co.ravel()); me.update()
lo, hi = co.min(0), co.max(0)
import bmesh
bm = bmesh.new(); bm.from_mesh(me)
islands = 0; seen = set()
for v in bm.verts:
    if v.index in seen: continue
    islands += 1; stack = [v]
    while stack:
        x = stack.pop()
        if x.index in seen: continue
        seen.add(x.index); stack += [e.other_vert(x) for e in x.link_edges]
print("STATS verts %d tris %d islands %d scale %.5f" % (len(co), sum(len(p.vertices) - 2 for p in me.polygons), islands, s))
print("BBOX x %.3f..%.3f  y %.3f..%.3f  z %.3f..%.3f" % (lo[0], hi[0], lo[1], hi[1], lo[2], hi[2]))
# render
sc.render.engine = 'BLENDER_EEVEE'
sc.render.resolution_x = sc.render.resolution_y = 600
sc.view_settings.view_transform = 'Standard'
w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (1, 1, 1, 1)
w.node_tree.nodes["Background"].inputs[1].default_value = 1.0
mat = me.materials[0]
for n in mat.node_tree.nodes:
    if n.type == 'BSDF_PRINCIPLED':
        tex = n.inputs["Base Color"].links[0].from_node if n.inputs["Base Color"].links else None
        if tex:
            em = mat.node_tree.nodes.new("ShaderNodeEmission")
            mat.node_tree.links.new(tex.outputs[0], em.inputs[0])
            out = next(x for x in mat.node_tree.nodes if x.type == 'OUTPUT_MATERIAL')
            mat.node_tree.links.new(em.outputs[0], out.inputs[0])
cam = bpy.data.objects.new("C", bpy.data.cameras.new("C")); sc.collection.objects.link(cam); sc.camera = cam
cam.data.type = 'ORTHO'; OS = 0.30; cam.data.ortho_scale = OS
outd = os.path.join(HERE, "probe"); files = []
views = {"front": ((0, -1, 0.12), (math.radians(90), 0, 0), (0, 0.12)),        # x right, z up
         "left": ((1, 0, 0.12), (math.radians(90), 0, math.radians(90)), (0, 0.12)),  # -y right... see note
         "top": ((0, 0, 1), (0, 0, 0), (0, 0)),
         "bottom": ((0, 0, -1), (math.radians(180), 0, 0), (0, 0))}
for name, (loc, rot, c) in views.items():
    cam.location = loc; cam.rotation_euler = rot
    p = os.path.join(outd, "%s_%s.png" % (NAME, name)); sc.render.filepath = p
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(p); N = 600
    px = np.array(img.pixels[:], np.float32).reshape(N, N, 4)
    # pixel (row from bottom r, col c) -> world: u = (col/N - .5)*OS + cu ; v = (r/N - .5)*OS + cv
    cu, cv = c
    for k in range(-15, 16):
        val = k * 0.02
        col = int(round(((val - cu) / OS + 0.5) * N)); row = int(round(((val - cv) / OS + 0.5) * N))
        clr = (1, 0, 0, 1) if k == 0 else ((0.2, 0.2, 0.9, 1) if k % 5 == 0 else (0.6, 0.6, 0.6, 1))
        a = 0.9 if k % 5 == 0 else 0.35
        if 0 <= col < N: px[:, col] = px[:, col] * (1 - a) + np.array(clr) * a
        if 0 <= row < N: px[row, :] = px[row, :] * (1 - a) + np.array(clr) * a
    img.pixels.foreach_set(px.ravel()); img.filepath_raw = p; img.save()
    files.append(px)
S = np.concatenate(files, axis=1)
im = bpy.data.images.new("s", S.shape[1], S.shape[0], alpha=True); im.pixels.foreach_set(S.ravel())
im.filepath_raw = os.path.join(outd, NAME + "_views.png"); im.file_format = 'PNG'; im.save()

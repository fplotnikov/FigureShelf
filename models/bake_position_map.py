"""Bake a "position map" for one finished figure: every texel of its painted texture gets the
3D point on the body it belongs to (rest pose), so the app can draw patterns (dots, stripes,
checks, stars, hearts) that wrap round the body in 3D instead of breaking at texture seams.

    blender -b --factory-startup --python models/bake_position_map.py -- bunny [size]

Reads   models/<name>.blend
Writes  models/<name>_pos.png  (RGB = position inside the figure's box, 0..1 per axis, app axes:
                                R = x (right), G = y (up), B = z (toward the viewer))
        and adds "posBox": [minX, minY, minZ, maxX, maxY, maxZ] (metres, app axes) to
        models/<name>_clips.json (and the app copy in FigureShelf.swiftpm/Resources).
Texels outside the UV islands stay black (the app leaves them alone).
"""
import bpy, sys, os, json

HERE = os.path.dirname(os.path.abspath(__file__))
ARGS = sys.argv[sys.argv.index("--") + 1:]
NAME = ARGS[0]
SIZE = int(ARGS[1]) if len(ARGS) > 1 else 1024

bpy.ops.wm.open_mainfile(filepath=os.path.join(HERE, NAME + ".blend"))
for arm in [o for o in bpy.data.objects if o.type == 'ARMATURE']:
    arm.data.pose_position = 'REST'
bpy.context.view_layer.update()

# The painted mesh: the one with a "Skin" material.
mesh_obj = None
for o in bpy.data.objects:
    if o.type == 'MESH' and any(s.material and s.material.name.startswith("Skin") for s in o.material_slots):
        mesh_obj = o
        break
assert mesh_obj, "no mesh with a Skin material"

# Bounding box of the deformed (rest pose) mesh, in Blender world axes.
dg = bpy.context.evaluated_depsgraph_get()
ev = mesh_obj.evaluated_get(dg)
me = ev.to_mesh()
M = mesh_obj.matrix_world
pts = [M @ v.co for v in me.vertices]
ev.to_mesh_clear()
bmin = [min(p[i] for p in pts) for i in range(3)]
bmax = [max(p[i] for p in pts) for i in range(3)]
size = [max(1e-6, bmax[i] - bmin[i]) for i in range(3)]

# A bake-only material: emission colour = position mapped to 0..1 (app axes).
img = bpy.data.images.new("posmap", SIZE, SIZE, alpha=False, float_buffer=True)
mat = bpy.data.materials.new("PosBake")
mat.use_nodes = True
nt = mat.node_tree
for n in list(nt.nodes):
    nt.nodes.remove(n)
geo = nt.nodes.new("ShaderNodeNewGeometry")
sep = nt.nodes.new("ShaderNodeSeparateXYZ")
comb = nt.nodes.new("ShaderNodeCombineXYZ")
nt.links.new(geo.outputs["Position"], sep.inputs[0])


def norm(output, lo, span):
    a = nt.nodes.new("ShaderNodeMath"); a.operation = 'SUBTRACT'; a.inputs[1].default_value = lo
    nt.links.new(output, a.inputs[0])
    b = nt.nodes.new("ShaderNodeMath"); b.operation = 'DIVIDE'; b.inputs[1].default_value = span
    nt.links.new(a.outputs[0], b.inputs[0])
    return b.outputs[0]


# app x = blender x, app y = blender z, app z = -blender y
nt.links.new(norm(sep.outputs["X"], bmin[0], size[0]), comb.inputs["X"])
nt.links.new(norm(sep.outputs["Z"], bmin[2], size[2]), comb.inputs["Y"])
negy = nt.nodes.new("ShaderNodeMath"); negy.operation = 'MULTIPLY'; negy.inputs[1].default_value = -1
nt.links.new(sep.outputs["Y"], negy.inputs[0])
nt.links.new(norm(negy.outputs[0], -bmax[1], size[1]), comb.inputs["Z"])
emit = nt.nodes.new("ShaderNodeEmission")
nt.links.new(comb.outputs[0], emit.inputs["Color"])
out = nt.nodes.new("ShaderNodeOutputMaterial")
nt.links.new(emit.outputs[0], out.inputs["Surface"])
tex = nt.nodes.new("ShaderNodeTexImage")
tex.image = img
nt.nodes.active = tex
for s in mesh_obj.material_slots:
    s.material = mat

scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = 1
scene.cycles.device = 'CPU'
scene.render.bake.margin = 6
scene.view_settings.view_transform = 'Standard'
bpy.ops.object.select_all(action='DESELECT')
mesh_obj.select_set(True)
bpy.context.view_layer.objects.active = mesh_obj
bpy.ops.object.bake(type='EMIT')

px = list(img.pixels[:])
nz = sum(1 for i in range(0, len(px), 4) if px[i] + px[i + 1] + px[i + 2] > 0.001)
print("BAKED non-black texels:", nz, "of", len(px) // 4, "sample", px[len(px) // 2:len(px) // 2 + 4])
out_png = os.path.join(HERE, NAME + "_pos.png")
# Saving the float bake image directly writes black: copy the values into a plain 8-bit,
# non-colour image (no colour transform, so 0..1 stays 0..1) and save that.
out_img = bpy.data.images.new("posout", SIZE, SIZE, alpha=False, float_buffer=False)
out_img.colorspace_settings.name = 'Non-Color'
out_img.pixels.foreach_set(px)
out_img.filepath_raw = out_png
out_img.file_format = 'PNG'
out_img.save()

box = [round(bmin[0], 4), round(bmin[2], 4), round(-bmax[1], 4),
       round(bmax[0], 4), round(bmax[2], 4), round(-bmin[1], 4)]
for p in (os.path.join(HERE, NAME + "_clips.json"),
          os.path.join(HERE, "..", "FigureShelf.swiftpm", "Resources", NAME + "_clips.json")):
    if os.path.exists(p):
        d = json.load(open(p)); d["posBox"] = box; json.dump(d, open(p, "w"), indent=2)
print("POSMAP", NAME, out_png, "box", box)

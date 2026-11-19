"""Inspect a Meshy GLB and render previews with the same camera/light as make_bunny.py.
Usage: blender -b --factory-startup --python inspect_render.py -- <in.glb> <out.png> [frame|mid]
The figure is scaled to 0.20 m tall for the preview only (files are not changed)."""
import bpy, sys, math
from mathutils import Vector, Euler

args = sys.argv[sys.argv.index("--") + 1:]
src, out = args[0], args[1]
frame_arg = args[2] if len(args) > 2 else None

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
bpy.ops.import_scene.gltf(filepath=src)

all_meshes = [o for o in scene.objects if o.type == 'MESH']
for o in all_meshes:
    print("INFO mesh", o.name, "verts", len(o.data.vertices), "parent", o.parent.name if o.parent else None,
          "dims", tuple(round(d, 3) for d in o.dimensions), "mats", len(o.data.materials))
# Meshy rigs include an unskinned helper sphere with no material: leave it out
helpers = [o for o in all_meshes if len(o.data.materials) == 0]
for o in helpers:
    o.hide_render = True
meshes = [o for o in all_meshes if o not in helpers]
arms = [o for o in scene.objects if o.type == 'ARMATURE']
deps = bpy.context.evaluated_depsgraph_get()
tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in meshes)
print("INFO meshes", [o.name for o in meshes], "tris", tris)
for o in meshes:
    print("INFO mats", o.name, [m.name for m in o.data.materials],
          [n.image.name + " %dx%d" % tuple(n.image.size) for m in o.data.materials if m and m.use_nodes
           for n in m.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image])
for a in arms:
    print("INFO armature", a.name, "bones", len(a.data.bones), [b.name for b in a.data.bones][:40])
print("INFO actions", [(ac.name, tuple(ac.frame_range)) for ac in bpy.data.actions])

def bounds():
    lo = Vector((1e9,) * 3); hi = Vector((-1e9,) * 3)
    for o in meshes:
        ev = o.evaluated_get(bpy.context.evaluated_depsgraph_get())
        for v in ev.to_mesh().vertices:
            w = ev.matrix_world @ v.co
            lo = Vector(map(min, lo, w)); hi = Vector(map(max, hi, w))
        ev.to_mesh_clear()
    return lo, hi

if bpy.data.actions:
    ac = bpy.data.actions[0]
    f0, f1 = ac.frame_range
    scene.frame_start, scene.frame_end = int(f0), int(f1)
    f = int((f0 + f1) / 2) if frame_arg == "mid" else int(frame_arg or f0)
    scene.frame_set(f)
    print("INFO frame", f, "range", f0, f1, "fps", scene.render.fps)

lo, hi = bounds()
print("INFO bounds (Blender Z-up, m)", tuple(round(x, 4) for x in lo), tuple(round(x, 4) for x in hi),
      "height", round(hi.z - lo.z, 4))

# normalise for the preview: 0.20 m tall, feet on the floor, centred
roots = [o for o in scene.objects if o.parent is None]
s = 0.20 / (hi.z - lo.z)
pivot = bpy.data.objects.new("Pivot", None); scene.collection.objects.link(pivot)
for r in roots:
    r.parent = pivot
pivot.scale = (s, s, s)
pivot.location = (-(lo.x + hi.x) / 2 * s, -(lo.y + hi.y) / 2 * s, -lo.z * s)

scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = scene.render.resolution_y = 800
scene.view_settings.view_transform = 'AgX'
world = bpy.data.worlds.new("W"); scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.70, 0.78, 0.90, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.35
bpy.ops.mesh.primitive_plane_add(size=30)
fm = bpy.data.materials.new("Floor"); fm.use_nodes = True
fm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.86, 0.88, 0.9, 1)
bpy.context.object.data.materials.append(fm)
sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", 'SUN'))
sun.data.energy = 2.2; sun.data.angle = math.radians(12)
sun.rotation_euler = Euler((math.radians(50), 0, math.radians(-30)))
scene.collection.objects.link(sun)
tgt = bpy.data.objects.new("Target", None); tgt.location = (0, 0, 0.11)
scene.collection.objects.link(tgt)
fill = bpy.data.objects.new("Fill", bpy.data.lights.new("Fill", 'AREA'))
fill.data.energy = 1.5; fill.data.size = 0.6; fill.location = (0.5, -0.5, 0.4)
fill.constraints.new('TRACK_TO').target = tgt
scene.collection.objects.link(fill)
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam")); cam.data.lens = 85
scene.collection.objects.link(cam); scene.camera = cam
cam.constraints.new('TRACK_TO').target = tgt
cam.location = Vector((-0.40, -0.88, 0.28)).normalized() * 0.85
scene.render.filepath = out
bpy.ops.render.render(write_still=True)
print("INFO wrote", out)

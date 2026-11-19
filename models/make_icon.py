"""Figure Shelf app icon options, rendered from the app's own models (1024 x 1024, opaque, no text).
blender -b --factory-startup --python make_icon.py -- a|b|c   ->  ../icon/option-<x>.png
  a: wooden shelf with Bunny, Kitty and Mosskip close up on a peach background
  b: Kitty on the round wooden turntable, little sparkles and soft AR corner brackets
  c: Kitty's face filling the frame on a bright solid colour"""
import bpy, os, sys, math
from mathutils import Vector, Euler
HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "..", "FigureShelf.swiftpm", "Resources")
opt = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE'
sc.render.resolution_x = sc.render.resolution_y = 1024
sc.view_settings.view_transform = 'Standard'
sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_mode = 'RGB'

def mat(name, rgb, rough=0.6, emit=False):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1); b.inputs["Roughness"].default_value = rough
    if emit:
        b.inputs["Emission Color"].default_value = (*rgb, 1); b.inputs["Emission Strength"].default_value = 1.0
    return m

def figure(name, x=0.0, y=0.0, yaw=0.0, scale=1.0):
    before = set(bpy.data.objects)
    bpy.ops.wm.usd_import(filepath=os.path.join(RES, name + ".usdz"))
    new = [o for o in bpy.data.objects if o not in before]
    roots = [o for o in new if o.parent is None]
    holder = bpy.data.objects.new(name + "_holder", None); sc.collection.objects.link(holder)
    for r in roots: r.parent = holder
    holder.location = (x, y, 0); holder.rotation_euler = (0, 0, math.radians(yaw)); holder.scale = (scale,) * 3
    return holder

def background(rgb):
    w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (*rgb, 1)
    w.node_tree.nodes["Background"].inputs[1].default_value = 1.0

def lights():
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", 'SUN'))
    sun.data.energy = 3.0; sun.data.angle = math.radians(25)
    sun.rotation_euler = Euler((math.radians(40), 0, math.radians(-30))); sc.collection.objects.link(sun)
    fill = bpy.data.objects.new("Fill", bpy.data.lights.new("Fill", 'AREA'))
    fill.data.energy = 8; fill.data.size = 1.5; fill.location = (0.4, -0.7, 0.5)
    fill.rotation_euler = (Vector((0, 0, 0.1)) - fill.location).to_track_quat('-Z', 'Y').to_euler()
    sc.collection.objects.link(fill)

def camera(target, direction, dist, lens=70):
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam")); cam.data.lens = lens
    sc.collection.objects.link(cam); sc.camera = cam
    cam.location = Vector(target) + Vector(direction).normalized() * dist
    cam.rotation_euler = (Vector(target) - cam.location).to_track_quat('-Z', 'Y').to_euler()

wood = mat("Wood", (0.45, 0.24, 0.10), 0.75)
lights()
if opt == "a":
    background((0.99, 0.80, 0.66))
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -0.012)); board = bpy.context.object
    board.scale = (0.40, 0.14, 0.024)
    bev = board.modifiers.new("Bevel", 'BEVEL'); bev.width = 0.01; bev.segments = 4
    board.data.materials.append(wood)
    figure("bunny", x=-0.12, yaw=-15); figure("kitty", x=0.0); figure("mosskip", x=0.13, yaw=20, scale=0.85)
    camera((0, 0, 0.09), (0, -1, 0.22), 0.74, lens=60)
elif opt == "b":
    background((0.80, 0.90, 1.0))
    bpy.ops.mesh.primitive_cylinder_add(radius=0.11, depth=0.02, location=(0, 0, -0.01), vertices=96)
    bpy.context.object.data.materials.append(wood); bpy.ops.object.shade_smooth()
    figure("kitty", yaw=-10)
    white = mat("Bracket", (1, 1, 1), emit=True); gold = mat("Spark", (1.0, 0.85, 0.3), emit=True)
    # soft AR corner brackets behind the figure
    for sx in (-1, 1):
        for sz in (0, 1):
            cx, cz = sx * 0.15, 0.02 + sz * 0.2
            for dx, dz, w, h in ((sx * -0.02, 0, 0.045, 0.008), (0, (-1 if sz else 1) * 0.02, 0.008, 0.045)):
                bpy.ops.mesh.primitive_cube_add(size=1, location=(cx + dx, 0.08, cz + dz))
                o = bpy.context.object; o.scale = (w, 0.004, h); o.data.materials.append(white)
    for (x, z, s) in ((0.1, 0.2, 0.012), (-0.11, 0.17, 0.009), (0.12, 0.07, 0.007)):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(x, -0.02, z))   # little diamond sparkle
        o = bpy.context.object; o.scale = (s, 0.002, s); o.rotation_euler = (0, math.radians(45), 0)
        o.data.materials.append(gold)
    camera((0, 0, 0.1), (-0.2, -1, 0.25), 0.62, lens=60)
else:
    background((0.60, 0.80, 1.0))
    figure("kitty", yaw=-8)
    camera((0, 0, 0.15), (-0.15, -1, 0.1), 0.25, lens=60)
out = os.path.join(HERE, "..", "icon", "option-%s.png" % opt)
os.makedirs(os.path.dirname(out), exist_ok=True)
sc.render.filepath = out; sc.frame_set(1)
bpy.ops.render.render(write_still=True)
print("ICON", out)

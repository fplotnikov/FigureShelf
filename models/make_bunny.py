"""
Figure Shelf - procedural toy Bunny generator (Blender 5.x, headless).

Usage:
  blender -b --factory-startup --python make_bunny.py            # build + export + previews
  blender -b --factory-startup --python make_bunny.py -- --no-render

Outputs (next to this script):
  bunny.usdz, bunny_clips.json, bunny.blend, previews/*.png

Conventions
  * Modelled in Blender Z-up, character faces -Y (Blender "front").
  * Exported with convert_orientation -> USD Y-up, character faces +Z (toward a
    RealityKit camera at the default position).
  * All shape coordinates below are in "design units" (total height ~2.45) and
    multiplied by S so the figure is TARGET_HEIGHT metres tall.
  * Poses are authored as rotations about *armature* axes (X right, Y back,
    Z up) and converted to bone-local rotations, so the numbers are intuitive:
      +X rot: top of an upward bone leans forward (toward viewer)
      +Y rot: top of an upward bone leans to +X (character's left)
  To make another animal: change PARTS / BONES / CLIPS, keep the pipeline.
"""
import bpy, bmesh, json, math, os, sys
from mathutils import Vector, Matrix, Euler, Quaternion

HERE = os.path.dirname(os.path.abspath(__file__))
NAME = "bunny"
TARGET_HEIGHT = 0.20          # metres
DESIGN_HEIGHT = 2.45
S = TARGET_HEIGHT / DESIGN_HEIGHT
FPS = 30
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
DO_RENDER = "--no-render" not in ARGS

# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))

def ss(a, b, x):
    t = clamp((x - a) / (b - a))
    return t * t * (3 - 2 * t)

def env(t, r):
    """0 at both ends, 1 in the middle, smooth ramps of width r."""
    return ss(0, r, t) * ss(1, 1 - r, t)

def V(x, y, z):
    return Vector((x, y, z)) * S

# --------------------------------------------------------------------------
# scene reset
# --------------------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.fps = FPS
scene.unit_settings.system = 'METRIC'

# --------------------------------------------------------------------------
# materials
# --------------------------------------------------------------------------
def make_mat(name, rgb, rough, spec=0.5, coat=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    if "Specular IOR Level" in b.inputs:
        b.inputs["Specular IOR Level"].default_value = spec
    if coat and "Coat Weight" in b.inputs:
        b.inputs["Coat Weight"].default_value = coat
    m.diffuse_color = (*rgb, 1)
    return m

MATS = {
    "Main":   make_mat("Main",   (0.80, 0.58, 0.42), 0.55),
    "Belly":  make_mat("Belly",  (0.97, 0.92, 0.82), 0.6),
    "Accent": make_mat("Accent", (0.96, 0.52, 0.62), 0.5),
    "Eyes":   make_mat("Eyes",   (0.015, 0.015, 0.025), 0.06, spec=1.0, coat=1.0),
}
MAT_ORDER = ["Main", "Belly", "Accent", "Eyes"]

# --------------------------------------------------------------------------
# skeleton (design units). name: (head, tail, parent, deform)
# --------------------------------------------------------------------------
BONES = {
    "root":      ((0, 0, 0),        (0, 0, 0.25),     None,    False),
    "hips":      ((0, 0, 0.30),     (0, 0, 0.62),     "root",  True),
    "spine":     ((0, 0, 0.62),     (0, 0, 0.95),     "hips",  True),
    "head":      ((0, 0, 0.95),     (0, 0, 1.75),     "spine", True),
    "ear_L":     ((0.16, 0.02, 1.72), (0.20, 0.02, 2.07), "head", True),
    "ear_L_tip": ((0.20, 0.02, 2.07), (0.24, 0.02, 2.44), "ear_L", True),
    "ear_R":     ((-0.16, 0.02, 1.72), (-0.20, 0.02, 2.07), "head", True),
    "ear_R_tip": ((-0.20, 0.02, 2.07), (-0.24, 0.02, 2.44), "ear_R", True),
    "arm_L":     ((0.34, -0.02, 0.84), (0.49, -0.07, 0.48), "spine", True),
    "arm_R":     ((-0.34, -0.02, 0.84), (-0.49, -0.07, 0.48), "spine", True),
    "leg_L":     ((0.20, 0, 0.42),   (0.22, -0.04, 0.04), "hips", True),
    "leg_R":     ((-0.20, 0, 0.42),  (-0.22, -0.04, 0.04), "hips", True),
}

# --------------------------------------------------------------------------
# weight functions: return {bone: weight} for a design-space point p
# --------------------------------------------------------------------------
def seg_t(p, a, b):
    a, b = Vector(a), Vector(b)
    d = b - a
    return clamp((p - a).dot(d) / d.length_squared, -1, 2)

def w_body(p):
    k = ss(0.45, 0.85, p.z)
    return {"hips": 1 - k, "spine": k}

def w_const(bone):
    return lambda p: {bone: 1.0}

def w_ear(side):
    base, mid = BONES["ear_" + side][0], BONES["ear_" + side][1]
    tip = BONES["ear_%s_tip" % side][1]
    def f(p):
        t = seg_t(p, base, tip)
        h = 1 - ss(-0.05, 0.12, t)          # blend into the head at the root
        k = ss(0.38, 0.72, t)               # second bone takes the top half
        return {"head": h, "ear_" + side: (1 - h) * (1 - k),
                "ear_%s_tip" % side: (1 - h) * k}
    return f

def w_limb(bone, parent, r=0.18):
    a, b = BONES[bone][0], BONES[bone][1]
    def f(p):
        t = seg_t(p, a, b)
        k = ss(-0.05, r, t)
        return {parent: 1 - k, bone: k}
    return f

# --------------------------------------------------------------------------
# parts: ellipsoids. (name, material, center, radii(x,y,z), long-axis dir or None,
#         segments, rings, weight fn)
# --------------------------------------------------------------------------
def ear_geo(side, inner=False):
    sx = 1 if side == "L" else -1
    a = Vector((0.16 * sx, 0.02, 1.70)); b = Vector((0.24 * sx, 0.02, 2.46))
    d = b - a
    c = a + d * (0.52 if inner else 0.5)
    if inner:
        c += Vector((0, -0.045, 0))
        return c, (0.072, 0.03, d.length * 0.36), d
    return c, (0.125, 0.06, d.length * 0.5), d

def arm_geo(side):
    sx = 1 if side == "L" else -1
    a = Vector((0.33 * sx, -0.02, 0.86)); b = Vector((0.50 * sx, -0.08, 0.46))
    d = b - a
    return a + d * 0.5, (0.105, 0.105, d.length * 0.62), d

PARTS = []
def part(*a):
    PARTS.append(a)

part("body",   "Main",  (0, 0, 0.58),       (0.42, 0.38, 0.46), None, 40, 24, w_body)
part("belly",  "Belly", (0, -0.25, 0.54),   (0.30, 0.15, 0.32), None, 32, 18, w_body)
part("tail",   "Belly", (0, 0.38, 0.34),    (0.13, 0.12, 0.13), None, 20, 12, w_const("hips"))
part("head",   "Main",  (0, 0, 1.36),       (0.56, 0.50, 0.48), None, 48, 28, w_const("head"))
part("cheek_L","Belly", (0.085, -0.43, 1.21), (0.11, 0.08, 0.09), None, 20, 12, w_const("head"))
part("cheek_R","Belly", (-0.085, -0.43, 1.21), (0.11, 0.08, 0.09), None, 20, 12, w_const("head"))
part("nose",   "Accent",(0, -0.505, 1.285), (0.055, 0.035, 0.038), None, 16, 10, w_const("head"))
part("eye_L",  "Eyes",  (0.21, -0.43, 1.42), (0.075, 0.05, 0.095), None, 20, 12, w_const("head"))
part("eye_R",  "Eyes",  (-0.21, -0.43, 1.42), (0.075, 0.05, 0.095), None, 20, 12, w_const("head"))
for s in "LR":
    sx = 1 if s == "L" else -1
    c, r, d = ear_geo(s);        part("ear_" + s,   "Main",   tuple(c), r, d, 20, 28, w_ear(s))
    c, r, d = ear_geo(s, True);  part("inear_" + s, "Accent", tuple(c), r, d, 14, 22, w_ear(s))
    c, r, d = arm_geo(s);        part("arm_" + s,   "Main",   tuple(c), r, d, 20, 16, w_limb("arm_" + s, "spine"))
    part("leg_" + s,  "Main", (0.20 * sx, -0.02, 0.22), (0.14, 0.14, 0.17), None, 20, 12,
         w_limb("leg_" + s, "hips", 0.3))
    part("foot_" + s, "Main", (0.22 * sx, -0.10, 0.08), (0.15, 0.23, 0.08), None, 24, 14,
         w_const("leg_" + s))
    part("pad_" + s, "Belly", (0.22 * sx, -0.30, 0.075), (0.09, 0.03, 0.055), None, 14, 10,
         w_const("leg_" + s))

# --------------------------------------------------------------------------
# build mesh
# --------------------------------------------------------------------------
deform_bones = [n for n, b in BONES.items() if b[3]]
mesh = bpy.data.meshes.new(NAME)
obj = bpy.data.objects.new(NAME, mesh)
scene.collection.objects.link(obj)
for mname in MAT_ORDER:
    mesh.materials.append(MATS[mname])
groups = {n: obj.vertex_groups.new(name=n) for n in deform_bones}

bm = bmesh.new()
weights = []  # per vertex dict
for (pname, mname, center, radii, axis, segs, rings, wfn) in PARTS:
    tmp = bmesh.new()
    bmesh.ops.create_uvsphere(tmp, u_segments=segs, v_segments=rings, radius=1.0)
    rot = Matrix.Identity(3)
    if axis is not None:
        rot = Vector((0, 0, 1)).rotation_difference(Vector(axis).normalized()).to_matrix()
    m = Matrix.Translation(Vector(center)) @ rot.to_4x4() @ Matrix.Diagonal((*radii, 1))
    bmesh.ops.transform(tmp, matrix=m, verts=tmp.verts)
    vmap = {}
    for v in tmp.verts:
        nv = bm.verts.new(v.co * S)
        vmap[v] = nv
        weights.append(wfn(v.co))
    mi = MAT_ORDER.index(mname)
    for f in tmp.faces:
        nf = bm.faces.new([vmap[v] for v in f.verts])
        nf.material_index = mi
        nf.smooth = True
    tmp.free()
bm.to_mesh(mesh)
bm.free()
for i, wd in enumerate(weights):
    tot = sum(wd.values())
    for bn, w in wd.items():
        if w > 1e-4:
            groups[bn].add([i], w / tot, 'REPLACE')

# --------------------------------------------------------------------------
# armature
# --------------------------------------------------------------------------
arm_data = bpy.data.armatures.new(NAME + "_rig")
rig = bpy.data.objects.new(NAME + "_rig", arm_data)
scene.collection.objects.link(rig)
bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode='EDIT')
for n, (h, t, parent, deform) in BONES.items():
    eb = arm_data.edit_bones.new(n)
    eb.head, eb.tail = V(*h), V(*t)
    eb.roll = 0
    eb.use_deform = deform
for n, (h, t, parent, deform) in BONES.items():
    if parent:
        eb = arm_data.edit_bones[n]
        eb.parent = arm_data.edit_bones[parent]
        eb.use_connect = (Vector(arm_data.edit_bones[parent].tail) - Vector(eb.head)).length < 1e-6
bpy.ops.object.mode_set(mode='OBJECT')

obj.parent = rig
mod = obj.modifiers.new("Armature", 'ARMATURE')
mod.object = rig

tri_count = sum(len(p.vertices) - 2 for p in mesh.polygons)

# --------------------------------------------------------------------------
# animation clips. Each fn(t in [0,1]) -> {bone: dict(rot=(x,y,z) deg, loc=(x,y,z) design units,
#                                            scl=(sxy, sz))}. Must return rest at t=0 and t=1.
# --------------------------------------------------------------------------
TAU = math.tau

def idle(t):
    s = math.sin(TAU * t)
    lag = math.sin(math.pi * t) ** 2 * math.sin(TAU * t - 0.9)
    return {
        "root":  dict(scl=(1 - 0.008 * s, 1 + 0.022 * s)),
        "spine": dict(rot=(2.0 * s, 0, 0)),
        "head":  dict(rot=(-1.5 * s, 2.5 * s, 0)),
        "ear_L": dict(rot=(0, 4 * s, 0)), "ear_R": dict(rot=(0, 4 * s, 0)),
        "ear_L_tip": dict(rot=(-3 * lag, 7 * lag, 0)), "ear_R_tip": dict(rot=(-3 * lag, 7 * lag, 0)),
        "arm_L": dict(rot=(3 * s, -2 * s, 0)), "arm_R": dict(rot=(3 * s, 2 * s, 0)),
    }

def dance(t):
    e = env(t, 0.1)
    sway = math.sin(2 * TAU * t)            # 2 side-to-side sways
    beat = abs(math.sin(4 * TAU * t))       # 8 bounces
    sq = (1 - beat) ** 3
    return {
        "root":  dict(loc=(0, 0, 0.10 * beat * e), scl=(1 + 0.04 * sq * e, 1 - 0.08 * sq * e)),
        "hips":  dict(rot=(0, 10 * sway * e, 0)),
        "spine": dict(rot=(0, -5 * sway * e, 0)),
        "head":  dict(rot=(0, -9 * math.sin(2 * TAU * t - 0.5) * e, 6 * sway * e)),
        "arm_L": dict(rot=(-10 * e, -(115 + 20 * math.sin(4 * TAU * t)) * e, 0)),
        "arm_R": dict(rot=(-10 * e, (115 + 20 * math.sin(4 * TAU * t + math.pi)) * e, 0)),
        "ear_L": dict(rot=(8 * math.sin(4 * TAU * t) * e, 14 * math.sin(2 * TAU * t - 0.9) * e + 6 * e, 0)),
        "ear_R": dict(rot=(8 * math.sin(4 * TAU * t) * e, 14 * math.sin(2 * TAU * t - 0.9) * e - 6 * e, 0)),
        "ear_L_tip": dict(rot=(-10 * beat * e, 24 * math.sin(2 * TAU * t - 1.7) * e, 0)),
        "ear_R_tip": dict(rot=(-10 * beat * e, 24 * math.sin(2 * TAU * t - 1.7) * e, 0)),
        "leg_L": dict(rot=(-14 * max(0, sway) * e, -6 * max(0, sway) * e, 0)),
        "leg_R": dict(rot=(-14 * max(0, -sway) * e, 6 * max(0, -sway) * e, 0)),
    }

def jump(t):
    u = (t * 3) % 1.0
    h = sz = 1.0
    out = {}
    lift = ear = arms = tuck = crouch = 0.0
    if u < 0.22:                       # anticipation crouch
        c = math.sin(math.pi * u / 0.22)
        sz = 1 - 0.16 * c; crouch = c; ear = 0.3 * c
    elif u < 0.72:                     # airborne
        p = (u - 0.22) / 0.5
        lift = 0.55 * 4 * p * (1 - p)
        sz = 1 + 0.08 * math.sin(math.pi * p)
        arms = math.sin(math.pi * p)
        tuck = math.sin(math.pi * p)
        ear = -math.sin(math.pi * min(1, p * 1.4))   # ears trail down on the way up
    else:                              # landing squash
        q = (u - 0.72) / 0.28
        k = math.sin(math.pi * q ** 0.6)
        sz = 1 - 0.20 * k; ear = 0.9 * k; crouch = 0.6 * k
    sxy = 1 / math.sqrt(sz)
    return {
        "root":  dict(loc=(0, 0, lift), scl=(sxy, sz)),
        "spine": dict(rot=(8 * crouch, 0, 0)),
        "head":  dict(rot=(-5 * crouch + 4 * tuck, 0, 0)),
        "arm_L": dict(rot=(18 * crouch, -55 * arms, 0)),
        "arm_R": dict(rot=(18 * crouch, 55 * arms, 0)),
        "leg_L": dict(rot=(-22 * tuck, 0, 0)), "leg_R": dict(rot=(-22 * tuck, 0, 0)),
        "ear_L": dict(rot=(18 * ear, 6 * abs(ear), 0)), "ear_R": dict(rot=(18 * ear, -6 * abs(ear), 0)),
        "ear_L_tip": dict(rot=(30 * ear, 0, 0)), "ear_R_tip": dict(rot=(30 * ear, 0, 0)),
    }

def run(t):
    e = env(t, 0.08)
    ph = 10 * TAU * t                   # 10 strides in 4 s
    w = math.sin(ph)
    b = abs(math.sin(ph))
    flop = math.sin(2 * ph - 1.0)
    return {
        "root":  dict(loc=(0, 0, 0.07 * b * e), scl=(1, 1 - 0.03 * (1 - b) * e)),
        "hips":  dict(rot=(0, 0, 6 * w * e)),
        "spine": dict(rot=(10 * e, 0, -4 * w * e)),
        "head":  dict(rot=(-7 * e, 2.5 * w * e, 0)),
        "leg_L": dict(rot=(38 * w * e, 0, 0)), "leg_R": dict(rot=(-38 * w * e, 0, 0)),
        "arm_L": dict(rot=(-45 * w * e, -25 * e, 0)), "arm_R": dict(rot=(45 * w * e, 25 * e, 0)),
        "ear_L": dict(rot=(-22 * e + 5 * flop * e, 8 * e, 0)),
        "ear_R": dict(rot=(-22 * e + 5 * flop * e, -8 * e, 0)),
        "ear_L_tip": dict(rot=(-22 * e + 10 * math.sin(2 * ph - 1.8) * e, 0, 0)),
        "ear_R_tip": dict(rot=(-22 * e + 10 * math.sin(2 * ph - 1.8) * e, 0, 0)),
    }

def wave(t):
    e = env(t, 0.22)
    inner = env(t, 0.32)
    wv = math.sin(TAU * 3 * (t - 0.25) / 0.5) * inner if 0.25 < t < 0.75 else 0.0
    return {
        "arm_R": dict(rot=(-15 * e, 100 * e + 16 * wv, 0)),
        "spine": dict(rot=(0, 4 * e, 0)),
        "head":  dict(rot=(0, -9 * e, 0)),
        "ear_L": dict(rot=(0, -4 * e, 0)), "ear_R": dict(rot=(0, -6 * e, 0)),
        "ear_L_tip": dict(rot=(0, -6 * e + 6 * wv, 0)), "ear_R_tip": dict(rot=(0, -8 * e + 6 * wv, 0)),
        "arm_L": dict(rot=(0, -4 * e, 0)),
    }

CLIPS = [("idle", 1, 60, idle), ("dance", 61, 180, dance), ("jump", 181, 252, jump),
         ("run", 253, 372, run), ("wave", 373, 444, wave)]

# --------------------------------------------------------------------------
# bake clips into one action
# --------------------------------------------------------------------------
rest3 = {b.name: b.matrix_local.to_3x3() for b in arm_data.bones}
for pb in rig.pose.bones:
    pb.rotation_mode = 'QUATERNION'
rig.animation_data_create()
action = bpy.data.actions.new(NAME + "_anim")
rig.animation_data.action = action
prev_q = {}

def apply_pose(pose):
    for pb in rig.pose.bones:
        d = pose.get(pb.name, {})
        M = rest3[pb.name]
        Mi = M.inverted()
        r = d.get("rot", (0, 0, 0))
        R = Euler([math.radians(a) for a in r], 'XYZ').to_matrix()
        q = (Mi @ R @ M).to_quaternion()
        if pb.name in prev_q:
            q.make_compatible(prev_q[pb.name])
        prev_q[pb.name] = q
        pb.rotation_quaternion = q
        loc = Vector(d.get("loc", (0, 0, 0))) * S
        pb.location = Mi @ loc
        sxy, sz = d.get("scl", (1, 1))
        # scale expressed in armature axes -> bone local (only used on root, which points +Z)
        Sm = Mi @ Matrix.Diagonal((sxy, sxy, sz)) @ M
        pb.scale = (Sm[0][0], Sm[1][1], Sm[2][2])

for name, a, b, fn in CLIPS:
    for f in range(a, b + 1):
        t = (f - a) / (b - a)
        apply_pose(fn(t))
        for pb in rig.pose.bones:
            pb.keyframe_insert("rotation_quaternion", frame=f)
            pb.keyframe_insert("location", frame=f)
            pb.keyframe_insert("scale", frame=f)

scene.frame_start, scene.frame_end = 1, CLIPS[-1][2]
scene.frame_set(1)

with open(os.path.join(HERE, NAME + "_clips.json"), "w") as fh:
    json.dump({"fps": FPS, "frameStart": 1, "frameEnd": CLIPS[-1][2],
               "clips": [{"name": n, "start": a, "end": b,
                          "startTime": round((a - 1) / FPS, 4), "endTime": round((b - 1) / FPS, 4),
                          "loop": n in ("idle", "dance", "run")}
                         for n, a, b, _ in CLIPS]}, fh, indent=2)

# --------------------------------------------------------------------------
# split into one skinned mesh per material, named after the material, so the
# app can find "Main" / "Belly" entities by name after RealityKit loads the USDZ
# --------------------------------------------------------------------------
bpy.ops.object.select_all(action='DESELECT')
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.separate(type='MATERIAL')
bpy.ops.object.mode_set(mode='OBJECT')
for o in [o for o in scene.objects if o.type == 'MESH' and o.parent == rig]:
    used = {p.material_index for p in o.data.polygons}
    mat = o.data.materials[used.pop()]
    o.data.materials.clear()
    o.data.materials.append(mat)
    o.name = o.data.name = mat.name

# --------------------------------------------------------------------------
# export
# --------------------------------------------------------------------------
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, NAME + ".blend"))
usdz = os.path.join(HERE, NAME + ".usdz")
bpy.ops.wm.usd_export(
    filepath=usdz, export_animation=True, export_armatures=True, only_deform_bones=False,
    export_materials=True, generate_preview_surface=True, export_uvmaps=True, export_normals=True,
    export_lights=False, export_cameras=False, convert_orientation=True,
    export_global_forward_selection='NEGATIVE_Z', export_global_up_selection='Y',
    export_subdivision='IGNORE', convert_world_material=False, root_prim_path="/" + NAME.capitalize(),
)
print("TRIANGLES", tri_count)
print("EXPORTED", usdz)

# --------------------------------------------------------------------------
# previews (scene-only objects added after export)
# --------------------------------------------------------------------------
if DO_RENDER:
    prev_dir = os.path.join(HERE, "previews")
    os.makedirs(prev_dir, exist_ok=True)
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = scene.render.resolution_y = 800
    scene.render.image_settings.file_format = 'PNG'
    scene.view_settings.view_transform = 'AgX' if 'AgX' in [v.identifier for v in
        type(scene.view_settings).bl_rna.properties['view_transform'].enum_items] else 'Standard'
    world = bpy.data.worlds.new("W"); scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.70, 0.78, 0.90, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.35

    bpy.ops.mesh.primitive_plane_add(size=30)
    floor = bpy.context.object
    fm = make_mat("Floor", (0.86, 0.88, 0.9), 0.8); floor.data.materials.append(fm)

    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", 'SUN'))
    sun.data.energy = 2.2; sun.data.angle = math.radians(12)
    sun.rotation_euler = Euler((math.radians(50), 0, math.radians(-30)))
    scene.collection.objects.link(sun)
    fill = bpy.data.objects.new("Fill", bpy.data.lights.new("Fill", 'AREA'))
    fill.data.energy = 1.5; fill.data.size = 0.6
    fill.location = (0.5, -0.5, 0.4)
    scene.collection.objects.link(fill)
    tgt = bpy.data.objects.new("Target", None); tgt.location = (0, 0, 0.11)
    scene.collection.objects.link(tgt)
    for L in (fill,):
        c = L.constraints.new('TRACK_TO'); c.target = tgt

    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    cam.data.lens = 85
    scene.collection.objects.link(cam); scene.camera = cam
    c = cam.constraints.new('TRACK_TO'); c.target = tgt
    d = Vector((-0.40, -0.88, 0.28)).normalized() * 0.85
    cam.location = d

    shots = [("front", 1), ("idle", 30), ("dance", 106), ("jump", 216), ("run", 304), ("wave", 405)]
    files = []
    for label, f in shots:
        scene.frame_set(f)
        p = os.path.join(prev_dir, "%s_%s.png" % (NAME, label))
        scene.render.filepath = p
        bpy.ops.render.render(write_still=True)
        files.append(p)

    # contact sheet 3 x 2
    import numpy as np
    W = H = 800
    sheet = np.ones((H * 2, W * 3, 4), dtype=np.float32)
    for i, p in enumerate(files):
        img = bpy.data.images.load(p)
        px = np.array(img.pixels[:], dtype=np.float32).reshape(img.size[1], img.size[0], 4)
        r, c = divmod(i, 3)
        rr = 1 - r   # image rows are bottom-up
        sheet[rr * H:(rr + 1) * H, c * W:(c + 1) * W] = px
    out = bpy.data.images.new("sheet", W * 3, H * 2, alpha=True)
    out.pixels.foreach_set(sheet.ravel())
    out.filepath_raw = os.path.join(prev_dir, NAME + "_sheet.png")
    out.file_format = 'PNG'
    out.save()
    print("PREVIEWS", prev_dir)

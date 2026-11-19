"""
Figure Shelf - convert a Meshy auto-rigged animal into an app-ready USDZ (Blender 5.x, headless).

Usage:
  blender -b --factory-startup --python convert_meshy.py -- kitty
  blender -b --factory-startup --python convert_meshy.py -- kitty --no-render

Reads   models/meshy_<name>/<name>_dance_jump.glb  (rig + Meshy dance & jump clips)
        models/meshy_<name>/<name>_running.glb     (Meshy's free run clip, same skeleton)
Writes  models/<name>.usdz, models/<name>_clips.json, models/<name>.blend, previews/<name>_*.png

What it does
  * Fixes Meshy's centimetre armature (object scale 0.01) so the figure is in metres.
  * Resamples every clip to 30 fps into ONE timeline with the same frame ranges as the
    Bunny: idle 1-60, dance 61-180, jump 181-252, run 253-372, wave 373-444.
  * idle and wave are made here (Meshy has no gentle idle; wave keys the right arm).
  * Each clip starts and ends in the idle pose (0.2 s cross-fades), and net root travel
    is removed, so clips loop and blend like the Bunny's.
  * Exports Y-up, facing +Z, no lights, ARKit-valid. The textured material is named
    "Skin" (not Main/Belly) so the app's flat recolouring leaves it alone.
Works for any Meshy biped rig (standard bone names: Hips, Spine, Head, LeftArm, ...).
"""
import bpy, json, math, os, sys
from mathutils import Vector, Matrix, Euler, Quaternion

HERE = os.path.dirname(os.path.abspath(__file__))
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
NAME = ARGS[0] if ARGS and not ARGS[0].startswith("--") else "kitty"
DO_RENDER = "--no-render" not in ARGS
SRC = os.path.join(HERE, "meshy_" + NAME)
FPS = 30
FADE = 0.2            # seconds of cross-fade to the idle pose at each clip end

# name, start, end (output frames), source
#   ("idle",) / ("wave",) / ("hop",)    made procedurally
#   (glb, action-substring, mode, arg)  mode: "trim" seconds | "fit" whole clip | "cycle" n loops
CLIPS = [
    ("idle", 1, 60, ("idle",)),
    ("dance", 61, 180, (f"{NAME}_dance_jump.glb", "Danc", "trim", 0.0)),
    # Meshy's human "Jump with Arms Open" bends so far forward that a big-headed chibi
    # looks like it tumbles, so the jump is a Bunny-style hop made here. To use a Meshy
    # jump instead: (f"{NAME}_dance_jump.glb", "Jump", "fit", None)
    ("jump", 181, 252, ("hop",)),
    ("run", 253, 372, (f"{NAME}_running.glb", "running", "cycle", 6)),
    ("wave", 373, 444, ("wave",)),
]

TAU = math.tau

def ss(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)

def env(t, r):
    return ss(0, r, t) * ss(1, 1 - r, t)

# --------------------------------------------------------------------------
# import
# --------------------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

def import_glb(path):
    before = set(bpy.data.objects)
    acts_before = set(bpy.data.actions)
    bpy.ops.import_scene.gltf(filepath=path)
    objs = [o for o in bpy.data.objects if o not in before]
    acts = [a for a in bpy.data.actions if a not in acts_before]
    arm = next(o for o in objs if o.type == 'ARMATURE')
    return arm, objs, acts

SRC_FPS = None
sources = {}   # glb file -> (armature, objects, actions)
for clip in CLIPS:
    src = clip[3]
    if len(src) > 1 and src[0] not in sources:
        sources[src[0]] = import_glb(os.path.join(SRC, src[0]))
        SRC_FPS = SRC_FPS or scene.render.fps   # glTF importer sets the scene fps (24)

main_file = CLIPS[1][3][0]
rig, main_objs, _ = sources[main_file]
mesh_objs = [o for o in main_objs if o.type == 'MESH' and o.data.materials]
UNIT = rig.scale.x            # Meshy armatures are in cm with object scale 0.01
print("SOURCE fps", SRC_FPS, "armature scale", UNIT)

def set_action(arm, action):
    arm.animation_data.action = action
    if getattr(action, "slots", None):
        arm.animation_data.action_slot = action.slots[0]

def sample(arm, action, src_frame):
    """Pose (loc, quat, scale) per bone, in bone-local basis, with loc in metres."""
    set_action(arm, action)
    scene.frame_set(int(math.floor(src_frame)), subframe=src_frame - math.floor(src_frame))
    out = {}
    for pb in arm.pose.bones:
        loc, q, s = pb.matrix_basis.decompose()
        out[pb.name] = (loc * UNIT, q, s)
    return out

# --------------------------------------------------------------------------
# sample every Meshy clip at the output frames (before touching transforms)
# --------------------------------------------------------------------------
sampled = {}
for name, a, b, src in CLIPS:
    if len(src) == 1:
        continue
    glb, key, mode, arg = src
    arm, _, acts = sources[glb]
    action = next(x for x in acts if key.lower() in x.name.lower())
    f0, f1 = action.frame_range
    frames = []
    n = b - a
    for i in range(n + 1):
        t = i / n
        if mode == "trim":                       # first (b-a)/FPS seconds of the clip
            sf = f0 + (arg or 0) * SRC_FPS + t * (n / FPS) * SRC_FPS
        elif mode == "fit":                      # whole clip squeezed/stretched into the slot
            sf = f0 + t * (f1 - f0)
        else:                                    # loop the cycle arg times
            sf = f0 + ((t * arg) % 1.0) * (f1 - f0) if t < 1 else f1
        frames.append(sample(arm, action, min(sf, f1)))
    # remove net travel of the hips (Meshy's jump moves forward ~15 cm)
    d0, d1 = frames[0]["Hips"][0], frames[-1]["Hips"][0]
    for i, fr in enumerate(frames):
        loc, q, s = fr["Hips"]
        fr["Hips"] = (loc - (d1 - d0) * (i / n), q, s)
    sampled[name] = frames
    print("SAMPLED", name, "from", action.name, (f0, f1), mode, arg)

# --------------------------------------------------------------------------
# keep only the main rig + mesh, convert to metres
# --------------------------------------------------------------------------
keep = {rig, *mesh_objs}
for o in list(bpy.data.objects):
    if o not in keep:
        bpy.data.objects.remove(o, do_unlink=True)
for pb in rig.pose.bones:
    pb.custom_shape = None
rig.animation_data.action = None
for pb in rig.pose.bones:
    pb.matrix_basis = Matrix.Identity(4)

bpy.ops.object.select_all(action='DESELECT')
for o in mesh_objs:
    o.select_set(True)
bpy.context.view_layer.objects.active = mesh_objs[0]
bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
bpy.ops.object.select_all(action='DESELECT')
rig.select_set(True)
bpy.context.view_layer.objects.active = rig
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
for o in mesh_objs:
    o.parent = rig
    o.matrix_parent_inverse = Matrix.Identity(4)
    for m in o.modifiers:
        if m.type == 'ARMATURE':
            m.object = rig
for o in mesh_objs:
    for i, m in enumerate(o.data.materials):
        if m and m.name.startswith("Material"):
            m.name = "Skin" if i == 0 else "Skin%d" % i

# height check (rest pose)
zs = [(o.matrix_world @ v.co).z for o in mesh_objs for v in o.data.vertices]
tri_count = sum(len(p.vertices) - 2 for o in mesh_objs for p in o.data.polygons)
print("REST height %.4f m, triangles %d" % (max(zs) - min(zs), tri_count))

# --------------------------------------------------------------------------
# procedural poses (armature axes: X right, Y back, Z up; character faces -Y)
# --------------------------------------------------------------------------
rest3 = {b.name: b.matrix_local.to_3x3() for b in rig.data.bones}

def q_arm(bone, rx=0.0, ry=0.0, rz=0.0):
    """Rotation about armature axes (degrees) as a bone-local quaternion."""
    M = rest3[bone]
    R = Euler((math.radians(rx), math.radians(ry), math.radians(rz)), 'XYZ').to_matrix()
    return (M.inverted() @ R @ M).to_quaternion()

IDENT = (Vector(), Quaternion(), Vector((1, 1, 1)))
ARM_DOWN = 62    # Meshy rigs come in T-pose; this lowers the arms to the sides

def loc_arm(bone, v):
    """Translation in armature axes (metres) as a bone-local location."""
    return rest3[bone].inverted() @ Vector(v)

def base_pose(extra=None, hips_offset=None):
    p = {pb.name: IDENT for pb in rig.pose.bones}
    p["LeftArm"] = (Vector(), q_arm("LeftArm", ry=ARM_DOWN), Vector((1, 1, 1)))
    p["RightArm"] = (Vector(), q_arm("RightArm", ry=-ARM_DOWN), Vector((1, 1, 1)))
    for k, rot in (extra or {}).items():
        p[k] = (Vector(), q_arm(k, *rot), Vector((1, 1, 1)))
    if hips_offset:
        _, q, s = p["Hips"]
        p["Hips"] = (loc_arm("Hips", hips_offset), q, s)
    return p

IDLE = base_pose()

def idle_pose(t):
    s = math.sin(TAU * t)
    return base_pose({
        "Spine": (1.8 * s, 0, 0),
        "Head": (-1.5 * s, 2.5 * s, 0),
        "LeftArm": (3 * s, ARM_DOWN - 2 * s, 0),
        "RightArm": (3 * s, -ARM_DOWN + 2 * s, 0),
    })

def wave_pose(t):
    e = env(t, 0.22)
    inner = env(t, 0.32)
    wv = math.sin(TAU * 3 * (t - 0.25) / 0.5) * inner if 0.25 < t < 0.75 else 0.0
    return base_pose({
        # raise the right arm out to the side (~30 deg above horizontal), bring it forward,
        # and wave the forearm so the paw stays clear of the big head
        "RightArm": (0, -ARM_DOWN + (ARM_DOWN + 30) * e, 28 * e),
        "RightForeArm": (0, (35 + 25 * wv) * e, 0),
        "Spine": (0, 3 * e, 0),
        "Head": (0, -8 * e, 0),
        "LeftArm": (0, ARM_DOWN + 4 * e, 0),
    })

def hop_pose(t):
    """Three hops like the Bunny's: crouch, airborne with arms up and knees tucked, land."""
    u = (t * 3) % 1.0
    lift = crouch = air = 0.0
    if u < 0.22:
        crouch = math.sin(math.pi * u / 0.22)
    elif u < 0.72:
        p = (u - 0.22) / 0.5
        lift = 0.045 * 4 * p * (1 - p)
        air = math.sin(math.pi * p)
    else:
        crouch = 0.8 * math.sin(math.pi * ((u - 0.72) / 0.28) ** 0.6)
    return base_pose({
        "Spine": (6 * crouch, 0, 0),
        "Head": (-4 * crouch + 3 * air, 0, 0),
        "LeftArm": (0, ARM_DOWN - 75 * air, 0),
        "RightArm": (0, -ARM_DOWN + 75 * air, 0),
        "LeftUpLeg": (-22 * air - 18 * crouch, 0, 0),
        "RightUpLeg": (-22 * air - 18 * crouch, 0, 0),
        "LeftLeg": (30 * air + 30 * crouch, 0, 0),
        "RightLeg": (30 * air + 30 * crouch, 0, 0),
    }, hips_offset=(0, 0, lift - 0.006 * crouch))

def blend(pa, pb_, w):
    out = {}
    for k in pa:
        la, qa, sa = pa[k]
        lb, qb, sb = pb_.get(k, IDENT)
        out[k] = (la.lerp(lb, w), qa.slerp(qb, w), sa.lerp(sb, w))
    return out

# --------------------------------------------------------------------------
# bake one action
# --------------------------------------------------------------------------
for pb in rig.pose.bones:
    pb.rotation_mode = 'QUATERNION'
rig.animation_data_create()
action = bpy.data.actions.new(NAME + "_anim")
rig.animation_data.action = action
prev = {}

def key(pose, f):
    for pb in rig.pose.bones:
        loc, q, s = pose.get(pb.name, IDENT)
        q = q.copy()
        if pb.name in prev:
            q.make_compatible(prev[pb.name])
        prev[pb.name] = q
        pb.location, pb.rotation_quaternion, pb.scale = loc, q, s
        pb.keyframe_insert("location", frame=f)
        pb.keyframe_insert("rotation_quaternion", frame=f)
        pb.keyframe_insert("scale", frame=f)

for name, a, b, src in CLIPS:
    n = b - a
    for i in range(n + 1):
        t = i / n
        if src[0] == "idle":
            pose = idle_pose(t)
        elif src[0] == "wave":
            pose = wave_pose(t)
        elif src[0] == "hop":
            pose = hop_pose(t)
        else:
            dur = n / FPS
            w = env(t, FADE / dur)                 # 0 at the ends -> idle pose
            pose = blend(IDLE, sampled[name][i], w)
        key(pose, a + i)

scene.render.fps = FPS
scene.frame_start, scene.frame_end = 1, CLIPS[-1][2]
scene.frame_set(1)

with open(os.path.join(HERE, NAME + "_clips.json"), "w") as fh:
    json.dump({"fps": FPS, "frameStart": 1, "frameEnd": CLIPS[-1][2],
               "clips": [{"name": n, "start": a, "end": b,
                          "startTime": round((a - 1) / FPS, 4), "endTime": round((b - 1) / FPS, 4),
                          "loop": n in ("idle", "dance", "run")}
                         for n, a, b, _ in CLIPS]}, fh, indent=2)

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
# previews (same camera and light as make_bunny.py)
# --------------------------------------------------------------------------
if DO_RENDER:
    prev_dir = os.path.join(HERE, "previews")
    os.makedirs(prev_dir, exist_ok=True)
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

    shots = [("front", 1), ("idle", 30), ("dance", 106), ("jump", 216), ("run", 304), ("wave", 405)]
    files = []
    for label, f in shots:
        scene.frame_set(f)
        p = os.path.join(prev_dir, "%s_%s.png" % (NAME, label))
        scene.render.filepath = p
        bpy.ops.render.render(write_still=True)
        files.append(p)

    import numpy as np
    W = H = 800
    sheet = np.ones((H * 2, W * 3, 4), dtype=np.float32)
    for i, p in enumerate(files):
        img = bpy.data.images.load(p)
        px = np.array(img.pixels[:], dtype=np.float32).reshape(img.size[1], img.size[0], 4)
        r, c = divmod(i, 3)
        rr = 1 - r
        sheet[rr * H:(rr + 1) * H, c * W:(c + 1) * W] = px
    out = bpy.data.images.new("sheet", W * 3, H * 2, alpha=True)
    out.pixels.foreach_set(sheet.ravel())
    out.filepath_raw = os.path.join(prev_dir, NAME + "_sheet.png")
    out.file_format = 'PNG'
    out.save()
    print("PREVIEWS", prev_dir)

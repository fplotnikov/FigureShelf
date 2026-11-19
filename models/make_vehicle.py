"""Figure Shelf: turn a Meshy vehicle model (made from the robot's own colours) into the
static model a robot changes into when it runs.
  blender -b --factory-startup --python make_vehicle.py -- supercar
Input  models/robots/vehicles/<name>_vehicle.glb  (nose along -X as Meshy made them)
Output models/<name>_vehicle.usdz (nose toward +z in the app, wheels on y = 0, about LENGTH m
       long, 1024 px JPEG texture, material "Skin") and models/<name>_vehicle.json
       (kind, size, rotor height for the helicopter)."""
import bpy, sys, os, json, math, subprocess
import numpy as np
from mathutils import Matrix
HERE = os.path.dirname(os.path.abspath(__file__))
name = sys.argv[sys.argv.index("--") + 1]
KINDS = {  # how it travels, and its length in metres
    "supercar": ("car", 0.22), "rally": ("car", 0.22), "truck": ("truck", 0.24),
    "motorcycle": ("bike", 0.21), "snowmobile": ("snow", 0.21), "excavator": ("digger", 0.23),
    "jet": ("jet", 0.26), "seaplane": ("plane", 0.26), "helicopter": ("heli", 0.26),
    "speedboat": ("boat", 0.24),
}
kind, length = KINDS[name]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=os.path.join(HERE, "robots", "vehicles", name + "_vehicle.glb"))
meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
bpy.ops.object.select_all(action='DESELECT')
for o in meshes: o.select_set(True)
bpy.context.view_layer.objects.active = meshes[0]
if len(meshes) > 1: bpy.ops.object.join()
ob = bpy.context.view_layer.objects.active
bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
for o in list(bpy.context.scene.objects):
    if o != ob: bpy.data.objects.remove(o, do_unlink=True)
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
me = ob.data
co = np.array([v.co[:] for v in me.vertices])
R = np.array(Matrix.Rotation(math.radians(90), 3, 'Z'))     # nose -X -> -Y (Blender front)
co = co @ R.T
lo, hi = co.min(0), co.max(0)
s = length / (hi[1] - lo[1])
co = (co - [(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]]) * s
me.vertices.foreach_set("co", co.ravel()); me.update()
ob.name = me.name = name + "_vehicle"
mat = me.materials[0]; mat.name = "Skin"
for m in me.materials[1:]: print("WARNING extra material", m.name)
# 1024 px JPEG texture
tex = next(n for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE')
img = tex.image; img.scale(1024, 1024)
png = os.path.join(HERE, name + "_vehicle_tex.png"); jpg = png[:-4] + ".jpg"
img.filepath_raw = png; img.file_format = 'PNG'; img.save()
subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "78", png, "--out", jpg], check=True, capture_output=True)
os.remove(png)
tex.image = bpy.data.images.load(jpg)
bsdf = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
if bsdf:
    for inp, val in (("Metallic", 0.0), ("Roughness", 0.6)):
        for l in list(bsdf.inputs[inp].links): mat.node_tree.links.remove(l)
        bsdf.inputs[inp].default_value = val
    for l in list(bsdf.inputs["Normal"].links): mat.node_tree.links.remove(l)
lo, hi = co.min(0), co.max(0)
info = dict(kind=kind, length=round(float(hi[1] - lo[1]), 4), width=round(float(hi[0] - lo[0]), 4),
            height=round(float(hi[2]), 4), rotorY=round(float(hi[2]), 4) if kind == "heli" else None)
json.dump(info, open(os.path.join(HERE, name + "_vehicle.json"), "w"), indent=2)
bpy.ops.wm.usd_export(filepath=os.path.join(HERE, name + "_vehicle.usdz"), export_materials=True,
    generate_preview_surface=True, export_uvmaps=True, export_normals=True, export_lights=False,
    export_cameras=False, convert_orientation=True, export_global_forward_selection='NEGATIVE_Z',
    export_global_up_selection='Y', root_prim_path="/" + name.capitalize() + "Vehicle")
os.remove(jpg)
print("VEHICLE", name, info, "tris", sum(len(p.vertices) - 2 for p in me.polygons))

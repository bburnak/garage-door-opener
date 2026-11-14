"""
Parametric 3D-printable case for the ESP32-C3 garage door controller.

Holds, side by side in one box:
  * LiftMaster 893LM 3-button remote (relay contacts are wired across a button)
  * ESP32-C3 Mini (USB-C power cable is the only external connection)
  * 1-channel relay module

How to use: Blender > Scripting workspace > Open this file > Run Script.
Two objects are created, laid out flat for printing:
  GarageCase_Base  (print as-is)
  GarageCase_Lid   (print as-is, lip facing up; flip it over when assembling)

Set EXPORT_DIR to also write STL files.

IMPORTANT: every dimension below is an estimate. Measure your actual remote,
ESP32-C3 board and relay module with calipers and edit the numbers first.
Units are millimetres (scene unit scale is set to 0.001).
"""
import bpy
import os

# ----------------------------------------------------------------------------
# Component dimensions (mm) - MEASURE AND EDIT THESE
# ----------------------------------------------------------------------------
REMOTE_L, REMOTE_W, REMOTE_T = 95.0, 48.0, 18.0   # 893LM remote (length, width, thickness)
ESP_L, ESP_W = 34.5, 25.8                         # ESP32-C3 Mini PCB (USB-C end is the short edge)
RELAY_L, RELAY_W, RELAY_H = 34.0, 26.0, 19.0      # relay board incl. relay height

# ----------------------------------------------------------------------------
# Case parameters (mm)
# ----------------------------------------------------------------------------
WALL = 2.4            # outer wall thickness
FLOOR = 2.4           # floor thickness
LID_T = 2.4           # lid plate thickness
CLEAR = 0.5           # gap around each component pocket
RIB_T = 1.2           # thickness of the little walls that locate each part
RIB_H = 5.0           # height of those walls
END_MARGIN = 8.0      # space at left/right ends (holds the screw posts)
Y_PAD = 1.0           # extra room front/back
COMP_GAP = 4.0        # gap between remote and electronics column
HEADROOM = 3.0        # air above the tallest component

POST_D = 6.5          # screw post diameter
PILOT_D = 2.2         # pilot hole for M2.5 self-tapping screws
LID_HOLE_D = 2.8      # clearance hole in lid
CBORE_D = 5.4         # screw head recess in lid
CBORE_DEPTH = 1.2

USB_W, USB_H = 14.0, 8.0   # cutout for USB-C cable plug in the right end wall
LIP_T = 1.2                # lid locating lip thickness
LIP_H = 2.5                # lid locating lip height
LIP_CLEAR = 0.3

EXPORT_DIR = None     # e.g. r"C:\Users\baris\Desktop"  (None = don't export)

# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def _finish(obj, name):
    obj.name = name
    obj.data.name = name
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return obj


def box(name, x0, y0, z0, x1, y1, z1):
    bpy.ops.mesh.primitive_cube_add(
        size=1, location=((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))
    obj = bpy.context.active_object
    obj.scale = (x1 - x0, y1 - y0, z1 - z0)
    return _finish(obj, name)


def cyl(name, x, y, z0, z1, d, verts=48):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=verts, radius=d / 2, depth=z1 - z0, location=(x, y, (z0 + z1) / 2))
    return _finish(bpy.context.active_object, name)


def boolean(target, tool, op):
    mod = target.modifiers.new("bool", 'BOOLEAN')
    mod.operation = op
    mod.object = tool
    mod.solver = 'EXACT'
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = target
    target.select_set(True)
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(tool, do_unlink=True)


def add(target, tool):
    boolean(target, tool, 'UNION')


def cut(target, tool):
    boolean(target, tool, 'DIFFERENCE')


def frame(base, name, x0, y0, x1, y1, z0, z1):
    """Low locating walls around the pocket x0..x1, y0..y1 (pocket stays empty)."""
    t = RIB_T
    for i, r in enumerate((
        (x0 - t, y0 - t, x1 + t, y0),        # front
        (x0 - t, y1, x1 + t, y1 + t),        # back
        (x0 - t, y0, x0, y1),                # left
        (x1, y0, x1 + t, y1),                # right
    )):
        add(base, box(f"{name}_rib{i}", r[0], r[1], z0, r[2], r[3], z1))


# ----------------------------------------------------------------------------
# Layout (coordinates inside the case, origin at the outer corner)
# ----------------------------------------------------------------------------
bpy.context.scene.unit_settings.system = 'METRIC'
bpy.context.scene.unit_settings.scale_length = 0.001
bpy.context.scene.unit_settings.length_unit = 'MILLIMETERS'

rem_w, rem_h = REMOTE_L + 2 * CLEAR, REMOTE_W + 2 * CLEAR
esp_w, esp_h = ESP_L + 2 * CLEAR, ESP_W + 2 * CLEAR
rel_w, rel_h = RELAY_L + 2 * CLEAR, RELAY_W + 2 * CLEAR

col_w = max(esp_w, rel_w)
stack_h = esp_h + rel_h + 3 * RIB_T
inner_x = END_MARGIN + RIB_T + rem_w + RIB_T + COMP_GAP + RIB_T + col_w + RIB_T + END_MARGIN
inner_y = max(rem_h + 2 * RIB_T, stack_h) + 2 * Y_PAD
inner_z = max(REMOTE_T, RELAY_H) + HEADROOM

OX, OY, OZ = inner_x + 2 * WALL, inner_y + 2 * WALL, FLOOR + inner_z
ix, iy, iz = WALL, WALL, FLOOR   # inner origin

# Remote pocket (left, centred in Y)
rem_x0 = ix + END_MARGIN + RIB_T
rem_y0 = iy + (inner_y - rem_h) / 2
# Electronics column (right): ESP at the back (high Y), relay in front
col_x0 = rem_x0 + rem_w + RIB_T + COMP_GAP + RIB_T
col_x1 = col_x0 + col_w
stack_y0 = iy + (inner_y - stack_h) / 2
rel_y0 = stack_y0 + RIB_T
esp_y0 = rel_y0 + rel_h + RIB_T
# ESP sits flush against the right side of its column so USB-C faces the wall
esp_x0 = col_x1 - esp_w
rel_x0 = col_x0

# ----------------------------------------------------------------------------
# Base
# ----------------------------------------------------------------------------
base = box("GarageCase_Base", 0, 0, 0, OX, OY, OZ)
cut(base, box("cavity", ix, iy, iz, ix + inner_x, iy + inner_y, OZ + 1))

frame(base, "remote", rem_x0, rem_y0, rem_x0 + rem_w, rem_y0 + rem_h, iz - 0.5, iz + RIB_H)
frame(base, "relay", rel_x0, rel_y0, rel_x0 + rel_w, rel_y0 + rel_h, iz - 0.5, iz + RIB_H)
frame(base, "esp", esp_x0, esp_y0, esp_x0 + esp_w, esp_y0 + esp_h, iz - 0.5, iz + RIB_H)

# Screw posts in the four corners
post_pts = [
    (ix + POST_D / 2, iy + POST_D / 2),
    (ix + inner_x - POST_D / 2, iy + POST_D / 2),
    (ix + POST_D / 2, iy + inner_y - POST_D / 2),
    (ix + inner_x - POST_D / 2, iy + inner_y - POST_D / 2),
]
for i, (px, py) in enumerate(post_pts):
    add(base, cyl(f"post{i}", px, py, iz - 0.5, OZ, POST_D))
for i, (px, py) in enumerate(post_pts):
    cut(base, cyl(f"pilot{i}", px, py, OZ - 10, OZ + 1, PILOT_D, 24))

# USB-C cable opening in the right end wall, centred on the ESP board
esp_cy = esp_y0 + esp_h / 2
cut(base, box("usb", OX - WALL - 1, esp_cy - USB_W / 2, iz,
              OX + 1, esp_cy + USB_W / 2, iz + USB_H))

# ----------------------------------------------------------------------------
# Lid (modelled flat, lip facing up, placed beside the base for printing)
# ----------------------------------------------------------------------------
lid_y = -(OY + 10)
lid = box("GarageCase_Lid", 0, lid_y, 0, OX, lid_y + OY, LID_T)

# Locating lip: ring that drops just inside the walls
lx0, ly0 = WALL + LIP_CLEAR, lid_y + WALL + LIP_CLEAR
lx1, ly1 = OX - WALL - LIP_CLEAR, lid_y + OY - WALL - LIP_CLEAR
ring = box("lip_outer", lx0, ly0, LID_T - 0.5, lx1, ly1, LID_T + LIP_H)
cut(ring, box("lip_inner", lx0 + LIP_T, ly0 + LIP_T, LID_T - 1,
              lx1 - LIP_T, ly1 - LIP_T, LID_T + LIP_H + 1))
# make room for the screw posts
for i, (px, py) in enumerate(post_pts):
    cut(ring, cyl(f"lipnotch{i}", px, lid_y + py, 0, LID_T + LIP_H + 1,
                  POST_D + 2 * LIP_CLEAR + 0.4))
add(lid, ring)

# Screw holes with recessed heads (head recess on the outer face = bottom of the
# lid as printed, so it ends up on top once the lid is flipped onto the case).
for i, (px, py) in enumerate(post_pts):
    cut(lid, cyl(f"hole{i}", px, lid_y + py, -1, LID_T + 1, LID_HOLE_D, 24))
    cut(lid, cyl(f"cbore{i}", px, lid_y + py, -1, CBORE_DEPTH, CBORE_D, 32))

# ----------------------------------------------------------------------------
# Optional STL export
# ----------------------------------------------------------------------------
if EXPORT_DIR:
    os.makedirs(EXPORT_DIR, exist_ok=True)
    for obj in (base, lid):
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        path = os.path.join(EXPORT_DIR, obj.name + ".stl")
        if hasattr(bpy.ops.wm, "stl_export"):          # Blender 4.x
            bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True)
        else:                                          # Blender 3.x
            bpy.ops.export_mesh.stl(filepath=path, use_selection=True)
        print("Exported", path)

print(f"Case outer size: {OX:.1f} x {OY:.1f} x {OZ:.1f} mm")

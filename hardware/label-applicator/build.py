"""Parametric model of a hand-cranked wrap-around label applicator for jars.

The jar screws into its own lid, which is held in a rotating cup (the same
idea as the square-and-lid hand jig, but fixed to a base). A flat table sits
tangent to the underside of the jar; the label lies on it adhesive side up
against a fence, and a spring-loaded roller presses it onto the jar while the
crank is turned.

Axes: X = jar axis (0 at the closed face of the lid), Y = label feed
direction (label travels from +Y towards the nip at Y=0), Z = up (0 = top of
the base plate).

Usage:
    python build.py                       # default jar (85 x 115, lid 88 x 30)
    python build.py --name B --jar-d 70 --jar-len 100 --lid-d 73 --lid-h 25
"""
import argparse
import itertools
import json
import math
import os

import cadquery as cq

ap = argparse.ArgumentParser()
ap.add_argument("--name", default="A", help="label for this jar size")
ap.add_argument("--jar-d", type=float, default=85.0, help="jar body diameter")
ap.add_argument("--jar-len", type=float, default=115.0, help="jar length incl. lid")
ap.add_argument("--lid-d", type=float, default=88.0, help="lid outer diameter")
ap.add_argument("--lid-h", type=float, default=30.0, help="lid height")
ap.add_argument("--fence-x", type=float, default=40.0, help="label side edge position")
ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "out"))
A = ap.parse_args()

# ---- fixed machine dimensions (shared by every jar size) -------------------
AX_H = 100.0        # spindle axis height above the base plate
BASE_T = 8.0
ROLLER_D = 24.0
ROLLER_X1 = 114.0
TABLE_T = 4.0
BEARING_D, BEARING_W = 22.0, 7.0   # 608 bearing
FIT = 0.2                          # print clearance

# ---- derived from the jar --------------------------------------------------
jar_r = A.jar_d / 2
TT = AX_H - jar_r                  # table top = tangent to jar underside
ROLLER_Z = TT - ROLLER_D / 2
ROLLER_X0 = A.lid_h + 3
ARM1_X0 = ROLLER_X0 - 6

assert 45 <= TT <= 73, "jar diameter outside the table's height adjustment (54-110 mm)"
assert A.jar_len <= 125, "jar too long for this base"


def box(x0, x1, y0, y1, z0, z1):
    return cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, y0, z0))


def cyl_x(d, x0, x1, y=0.0, z=AX_H):
    return cq.Workplane("YZ").workplane(offset=x0).center(y, z).circle(d / 2).extrude(x1 - x0)


def cyl_z(d, z0, z1, x, y):
    return cq.Workplane("XY").workplane(offset=z0).center(x, y).circle(d / 2).extrude(z1 - z0)


def hex_x(af, x0, x1, y=0.0, z=AX_H):
    return cq.Workplane("YZ").workplane(offset=x0).center(y, z).polygon(6, af / math.cos(math.pi / 6)).extrude(x1 - x0)


PIVOT_Y, PIVOT_Z = -40.0, 30.0
FOOT_HOLES = [(-48, -34), (-48, 34), (-7, -34), (-7, 34)]


def make_base():
    b = box(-55, 130, -50, 150, -BASE_T, 0).edges("|Z").fillet(6)
    # uprights that carry the height-adjustable table
    for x0 in (6, 122):
        b = b.union(box(x0, x0 + 6, 80, 120, 0, 48))
    b = b.cut(cyl_x(4.4, 0, 135, y=100, z=35))
    # lugs for the roller arm pivot
    for x0 in (ARM1_X0 - 5.5, 120.5):
        b = b.union(box(x0, x0 + 5, PIVOT_Y - 6, PIVOT_Y + 6, 0, PIVOT_Z + 8))
    b = b.cut(cyl_x(5.2, ARM1_X0 - 10, 130, y=PIVOT_Y, z=PIVOT_Z))
    # spring peg + headstock screw holes
    b = b.union(cyl_z(8, 0, 6, (ARM1_X0 + 120) / 2, -21))
    for x, y in FOOT_HOLES:
        b = b.cut(cyl_z(4.4, -BASE_T - 1, 1, x, y))
    return b


def make_headstock():
    h = box(-41, -11, -30, 30, 0, AX_H).union(cyl_x(60, -41, -11))
    h = h.union(box(-53, -3, -40, 40, 0, 6))
    h = h.cut(cyl_x(10, -42, -10))
    h = h.cut(cyl_x(BEARING_D + FIT, -41, -41 + BEARING_W))
    h = h.cut(cyl_x(BEARING_D + FIT, -11 - BEARING_W, -11))
    for x, y in FOOT_HOLES:
        h = h.cut(cyl_z(4.4, -1, 7, x, y))
    return h


def make_adapter():
    od = A.lid_d + 8
    a = cyl_x(od, -9, 10).union(cyl_x(14, -11, -9))
    a = a.cut(cyl_x(A.lid_d + 0.6, 0, 11))          # pocket the lid sits in
    a = a.cut(cyl_x(8.4, -12, 1))                   # M8 spindle bolt
    a = a.cut(hex_x(13.4, -5.8, 1))                 # captive bolt head
    for y in (-25, 25):                             # screws that hold the lid
        a = a.cut(cyl_x(3.4, -10, 1, y=y))
    return a


def make_crank():
    c = cyl_x(24, -57, -45)
    c = c.union(box(-57, -49, -10, 10, AX_H - 60, AX_H))
    c = c.union(cyl_x(20, -57, -49, z=AX_H - 60))
    c = c.union(cyl_x(16, -97, -57, z=AX_H - 60))
    c = c.cut(cyl_x(8.4, -58, -44))
    c = c.cut(hex_x(13.4, -58, -51.5))
    return c


def make_table():
    t = box(12, 122, 10, 146, TT - TABLE_T, TT)
    t = t.cut(box(11, A.lid_h + 2, 9, 16, TT - TABLE_T - 1, TT + 1))     # lid clearance
    t = t.cut(cyl_x(ROLLER_D + 3, 0, 130, y=0, z=ROLLER_Z))             # roller clearance
    for x0 in (12, 118):
        t = t.union(box(x0, x0 + 4, 60, 140, TT - 42, TT - TABLE_T))
    t = t.cut(box(11, 123, 97.8, 102.2, TT - 38, TT - 10))              # height slots
    for y in (45, 120):                                                 # fence slots
        t = t.cut(box(20, 75, y - 2.2, y + 2.2, TT - TABLE_T - 1, TT + 1))
    return t


def make_fence():
    f = box(A.fence_x - 10, A.fence_x, 20, 140, TT, TT + 3)
    for y in (45, 120):
        f = f.cut(cyl_z(4.4, TT - 1, TT + 4, A.fence_x - 5, y))
    return f


def make_arm():
    dy, dz = 0 - PIVOT_Y, ROLLER_Z - PIVOT_Z
    length, ang = math.hypot(dy, dz), math.degrees(math.atan2(dz, dy))
    arm = None
    for x0 in (ARM1_X0, 115):
        bar = (cq.Workplane("XY").box(5, length, 12)
               .rotate((0, 0, 0), (1, 0, 0), ang)
               .translate((x0 + 2.5, PIVOT_Y + dy / 2, PIVOT_Z + dz / 2)))
        side = bar.union(cyl_x(12, x0, x0 + 5, y=PIVOT_Y, z=PIVOT_Z)).union(cyl_x(12, x0, x0 + 5, y=0, z=ROLLER_Z))
        arm = side if arm is None else arm.union(side)
    arm = arm.union(box(ARM1_X0, 120, -26, -16, 28, 36))                # cross bar
    arm = arm.union(cyl_z(8, 22, 28, (ARM1_X0 + 120) / 2, -21))         # spring peg
    arm = arm.cut(cyl_x(5.2, 0, 130, y=PIVOT_Y, z=PIVOT_Z))
    arm = arm.cut(cyl_x(5.2, 0, 130, y=0, z=ROLLER_Z))
    return arm


def make_roller():
    return cyl_x(ROLLER_D, ROLLER_X0, ROLLER_X1, y=0, z=ROLLER_Z).cut(cyl_x(5.2, 0, 130, y=0, z=ROLLER_Z))


# name -> (shape, colour, printed?, Arabic label)
PARTS = {
    "base": (make_base(), "#8f9aa3", True, "القاعدة"),
    "headstock": (make_headstock(), "#5d7fa3", True, "حامل المحور"),
    f"lid_adapter_{A.name}": (make_adapter(), "#d9892b", True, "كأس الغطاء (يتبدّل حسب المقاس)"),
    "crank": (make_crank(), "#c44f3f", True, "المانيفيلا"),
    "table": (make_table(), "#e8e3d6", True, "طاولة الاستيكر"),
    "fence": (make_fence(), "#2f9e8f", True, "حافة الدليل"),
    "roller_arm": (make_arm(), "#7a68a8", True, "ذراع رول الضغط"),
    "roller": (make_roller(), "#3a3f45", True, "رول الضغط"),
    # reference geometry, not printed
    "ref_lid": (cyl_x(A.lid_d, 0.3, A.lid_h), "#d8b04a", False, "غطاء العبوة"),
    "ref_jar": (cyl_x(A.jar_d, A.lid_h, A.jar_len), "#2e5e45", False, "العبوة"),
    "ref_bolt": (cyl_x(8, -68, -0.5), "#b9bec4", False, "برغي M8"),
    "ref_label": (box(A.fence_x, min(A.fence_x + 70, A.jar_len - 3), 4, 146, TT, TT + 0.3), "#ffffff", False, "الاستيكر"),
}

os.makedirs(A.out, exist_ok=True)

# ---- interference check between printed parts ------------------------------
printed = [(n, p[0]) for n, p in PARTS.items() if p[2]]
clashes = []
for (n1, s1), (n2, s2) in itertools.combinations(printed, 2):
    v = s1.intersect(s2).val().Volume()
    if v > 0.5:
        clashes.append((n1, n2, round(v, 1)))
jar_like = PARTS["ref_jar"][0].union(PARTS["ref_lid"][0])
for n, s in printed:
    if n.startswith("lid_adapter"):
        continue
    v = s.intersect(jar_like).val().Volume()
    if v > 0.5:
        clashes.append((n, "jar", round(v, 1)))
print("clashes:", clashes or "none")

# ---- exports ---------------------------------------------------------------
asm = cq.Assembly(name="label_applicator")
viewer = {"params": vars(A) | {"table_top": TT, "axis_h": AX_H}, "parts": []}
for name, (shape, colour, is_printed, label) in PARTS.items():
    if is_printed:
        cq.exporters.export(shape, os.path.join(A.out, f"{name}.stl"), tolerance=0.05, angularTolerance=0.2)
        bb = shape.val().BoundingBox()
        print(f"{name:18s} {bb.xlen:6.1f} x {bb.ylen:6.1f} x {bb.zlen:6.1f} mm")
    asm.add(shape, name=name, color=cq.Color(*[int(colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]))
    verts, tris = shape.val().tessellate(0.15, 0.35)
    bb = shape.val().BoundingBox()
    viewer["parts"].append({
        "name": name, "label": label, "color": colour, "printed": is_printed,
        "center": [round((bb.xmin + bb.xmax) / 2, 1), round((bb.ymin + bb.ymax) / 2, 1), round((bb.zmin + bb.zmax) / 2, 1)],
        "v": [round(c, 2) for p in verts for c in (p.x, p.y, p.z)],
        "t": [i for t in tris for i in t],
    })
asm.save(os.path.join(A.out, f"assembly_{A.name}.step"))
with open(os.path.join(A.out, "viewer_data.json"), "w") as f:
    json.dump(viewer, f, separators=(",", ":"))
print("table top height:", TT, "mm above base")

# ---- self-contained 3D preview page ----------------------------------------
here = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(here, "preview_template.html")) as f:
    page = f.read().replace("__DATA__", json.dumps(viewer, separators=(",", ":")))
with open(os.path.join(here, "preview.html"), "w") as f:
    f.write(page)

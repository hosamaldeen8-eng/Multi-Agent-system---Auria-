"""Parametric model of a hand-cranked wrap-around label applicator for jars.

The jar screws into its own lid, which is held in a rotating cup (the same
idea as the square-and-lid hand jig, but fixed to a base).

* A ruler seats on a tapered rail on the rotating cup and lies along the jar,
  parallel to its axis, with a side stop square to it. The label's leading
  edge and side edge are pushed into that corner, so it cannot start skewed
  or shifted. The ruler turns with the jar and lifts off before the end of a
  full-wrap label comes round to meet the start.
* A fixed arm hinged on two posts reaches over the jar and rests a rubber
  squeegee blade on its top. As the jar turns, the blade presses the label
  down and pushes the air out ahead of it.

Axes: X = jar axis (0 at the closed face of the lid), Y = towards the
operator, Z = up (0 = top of the base plate).

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
ap.add_argument("--label-x0", type=float, default=None, help="where the label's side edge sits (default: 4 mm past the lid)")
ap.add_argument("--label-len", type=float, default=None, help="label length around the jar (default: full wrap)")
ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "out"))
A = ap.parse_args()

# ---- fixed machine dimensions (shared by every jar size) -------------------
AX_H = 100.0        # spindle axis height above the base plate
BASE_T = 8.0
BEARING_D, BEARING_W = 22.0, 7.0   # 608 bearing
FIT = 0.2                          # print clearance
REF_JAR_R = 42.5                   # jar the squeegee arm sits level on
ARM_PIVOT_Y = -80.0
ARM_PIVOT_Z = AX_H + 72
RULER_REST_DEG = -70               # where the ruler sits in the drawing

# ---- derived from the jar --------------------------------------------------
jar_r = A.jar_d / 2
LBL_X0 = A.label_x0 if A.label_x0 is not None else A.lid_h + 4
ad_r = A.lid_d / 2 + 4             # outer radius of the lid cup
assert 27 <= jar_r <= 55, "jar diameter outside what the squeegee arm reaches (54-110 mm)"
assert A.jar_len <= 125, "jar too long for this base"
assert ad_r + 3 > jar_r, "lid much smaller than the jar: ruler needs a redesign"


def box(x0, x1, y0, y1, z0, z1):
    return cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, y0, z0))


def cyl_x(d, x0, x1, y=0.0, z=AX_H):
    return cq.Workplane("YZ").workplane(offset=x0).center(y, z).circle(d / 2).extrude(x1 - x0)


def cyl_y(d, y0, y1, x, z):
    return cq.Workplane("XZ").workplane(offset=-y1).center(x, z).circle(d / 2).extrude(y1 - y0)


def cyl_z(d, z0, z1, x, y):
    return cq.Workplane("XY").workplane(offset=z0).center(x, y).circle(d / 2).extrude(z1 - z0)


def hex_x(af, x0, x1, y=0.0, z=AX_H):
    return cq.Workplane("YZ").workplane(offset=x0).center(y, z).polygon(6, af / math.cos(math.pi / 6)).extrude(x1 - x0)


def about_spindle(shape, deg):
    return shape.rotate((0, 0, AX_H), (1, 0, AX_H), deg)


FOOT_HOLES = [(-48, -34), (-48, 34), (-7, -34), (-7, 34)]
POSTS_X = (14, 123)                # two posts, 7 thick, either side of the arm


def make_base():
    b = box(-55, 130, -95, 70, -BASE_T, 0).edges("|Z").fillet(6)
    for x0 in POSTS_X:
        b = b.union(box(x0, x0 + 7, ARM_PIVOT_Y - 10, ARM_PIVOT_Y + 10, 0, ARM_PIVOT_Z + 10))
    b = b.union(box(POSTS_X[0], POSTS_X[1] + 7, ARM_PIVOT_Y - 10, ARM_PIVOT_Y - 4, 0, 120))   # back wall
    b = b.cut(cyl_x(5.2, 0, 135, y=ARM_PIVOT_Y, z=ARM_PIVOT_Z))
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


# The ruler is drawn at 12 o'clock (reference face in the plane y = 0, label on
# the +y side), then turned to its rest angle. It seats on a tapered rail that
# is part of the lid cup, so it is rigid and square to the jar when pushed
# down, and lifts straight off before the end of the label comes round.
RAIL_Z0, RAIL_Z1 = AX_H + ad_r - 1, AX_H + ad_r + 7
RAIL_X1 = LBL_X0 - 1.5
RULER_TOP = AX_H + ad_r + 11


def rail_profile(z1):
    return (cq.Workplane("YZ").polyline([(-16, RAIL_Z0), (-4, RAIL_Z0), (-6, z1), (-14, z1)]).close().extrude(RAIL_X1))


def sector(r0, r1, x0, x1, y0, y1):
    ring = cyl_x(2 * r1, x0, x1).cut(cyl_x(2 * r0, x0 - 1, x1 + 1))
    return ring.intersect(box(x0, x1, y0, y1, AX_H + 15, AX_H + 90))


def make_adapter():
    a = cyl_x(2 * ad_r, -9, 10).union(cyl_x(14, -11, -9))
    rail = rail_profile(RAIL_Z1).cut(cyl_z(3.4, RAIL_Z0, RAIL_Z1 + 1, 20, -10))   # thumb-screw pilot
    a = a.union(about_spindle(rail, RULER_REST_DEG))
    a = a.cut(cyl_x(A.lid_d + 0.6, 0, 11))          # pocket the lid sits in
    a = a.cut(cyl_x(8.4, -12, 1))                   # M8 spindle bolt
    a = a.cut(hex_x(13.4, -5.8, 1))                 # captive bolt head
    for y in (-25, 25):                             # screws that hold the lid
        a = a.cut(cyl_x(3.4, -10, 1, y=y))
    return a


def make_ruler():
    x_end = A.jar_len - 5
    g = jar_r + 0.3                                  # ruler floats just clear of the jar
    r = box(0, RAIL_X1, -20, 0, AX_H + ad_r + 0.5, RULER_TOP)                   # saddle on the rail
    r = r.cut(rail_profile(RAIL_Z1 + 0.6))
    r = r.cut(cyl_z(4.4, RAIL_Z1, RULER_TOP + 1, 20, -10))
    r = r.union(sector(g, ad_r + 11, RAIL_X1, LBL_X0, -20, 0))                  # web
    r = r.union(sector(g, jar_r + 5, LBL_X0, x_end, -20, 0))                    # straight edge
    r = r.union(sector(g, ad_r + 11, LBL_X0, x_end, -20, -12))                  # stiffening spine
    r = r.union(sector(g, jar_r + 6, RAIL_X1, LBL_X0, 0, 30))                   # side stop
    return about_spindle(r, RULER_REST_DEG)


def make_crank():
    # sits 8.5 mm behind the headstock: room for a washer and the first M8 nut
    x0, x1 = -61.5, -49.5
    c = cyl_x(24, x0, x1)
    c = c.union(box(x0, x0 + 8, -10, 10, AX_H - 60, AX_H))
    c = c.union(cyl_x(20, x0, x0 + 8, z=AX_H - 60))
    c = c.union(cyl_x(16, x0 - 40, x0, z=AX_H - 60))
    c = c.cut(cyl_x(8.4, x0 - 1, x1 + 1))
    c = c.cut(hex_x(13.4, x0 - 1, x0 + 6.5))        # second nut locks the crank
    return c


# Squeegee arm, drawn level for the reference jar and tilted for other sizes.
H_Z0 = ARM_PIVOT_Z - 8             # underside of the blade holder
BLADE_X0, BLADE_X1 = LBL_X0 + 1, min(A.jar_len - 3, 116)
arm_tilt = math.degrees(math.asin((jar_r - REF_JAR_R) / -ARM_PIVOT_Y))


def tilt(shape):
    return shape.rotate((0, ARM_PIVOT_Y, ARM_PIVOT_Z), (1, ARM_PIVOT_Y, ARM_PIVOT_Z), arm_tilt)


def make_squeegee_arm():
    s = box(22, 122, -8, 8, H_Z0, H_Z0 + 16)                                   # blade holder
    for x0 in (22, 116):
        s = s.union(box(x0, x0 + 6, ARM_PIVOT_Y, 0, ARM_PIVOT_Z - 6, ARM_PIVOT_Z + 6))
        s = s.union(cyl_x(16, x0, x0 + 6, y=ARM_PIVOT_Y, z=ARM_PIVOT_Z))
    s = s.union(box(60, 84, 8, 24, H_Z0 + 10, H_Z0 + 16))                      # lift tab
    s = s.cut(box(BLADE_X0 - 1, BLADE_X1 + 1, -1.7, 1.7, H_Z0 - 1, H_Z0 + 12))  # blade slot
    for x in (BLADE_X0 + 12, BLADE_X1 - 12):                                   # blade clamp screws
        s = s.cut(cyl_y(3.2, -9, 9, x=x, z=H_Z0 + 6))
    s = s.cut(cyl_x(5.2, 0, 135, y=ARM_PIVOT_Y, z=ARM_PIVOT_Z))
    return tilt(s)


def ref_blade():
    return tilt(box(BLADE_X0, BLADE_X1, -1.5, 1.5, AX_H + REF_JAR_R, H_Z0 + 12))


# name -> (shape, colour, printed?, Arabic label)
PARTS = {
    "base": (make_base(), "#8f9aa3", True, "القاعدة وأعمدة الذراع"),
    "headstock": (make_headstock(), "#5d7fa3", True, "حامل المحور"),
    f"lid_adapter_{A.name}": (make_adapter(), "#d9892b", True, "كأس الغطاء (يتبدّل حسب المقاس)"),
    f"ruler_{A.name}": (make_ruler(), "#2f9e8f", True, "المسطرة (تلف مع العبوة)"),
    "crank": (make_crank(), "#c44f3f", True, "المانيفيلا"),
    "squeegee_arm": (make_squeegee_arm(), "#7a68a8", True, "ذراع القومة (ثابت من فوق)"),
    # reference geometry, not printed
    "ref_blade": (ref_blade(), "#2b2f33", False, "القومة"),
    "ref_lid": (cyl_x(A.lid_d, 0.3, A.lid_h), "#d8b04a", False, "غطاء العبوة"),
    "ref_jar": (cyl_x(A.jar_d, A.lid_h, A.jar_len), "#2e5e45", False, "العبوة"),
    "ref_bolt": (cyl_x(8, -65.5, -5.8), "#b9bec4", False, "برغي M8"),
}

os.makedirs(A.out, exist_ok=True)

# ---- interference checks ---------------------------------------------------
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
# the cup + ruler sweep a full turn: nothing fixed may sit inside that ring
rotating = PARTS[f"lid_adapter_{A.name}"][0].union(PARTS[f"ruler_{A.name}"][0])
fixed = PARTS["base"][0].union(PARTS["headstock"][0]).union(PARTS["squeegee_arm"][0])
for deg in range(0, 360, 10):
    v = about_spindle(rotating, deg).intersect(fixed).val().Volume()
    if v > 0.5:
        clashes.append(("rotating@%d" % deg, "fixed", round(v, 1)))
print("clashes:", clashes or "none")

# ---- exports ---------------------------------------------------------------
for f in os.listdir(A.out):
    os.remove(os.path.join(A.out, f))
asm = cq.Assembly(name="label_applicator")
viewer = {"params": vars(A) | {"axis_h": AX_H, "ruler_rest_deg": RULER_REST_DEG, "label_x0": LBL_X0,
                               "arm_pivot": [ARM_PIVOT_Y, ARM_PIVOT_Z],
                               "label_len": A.label_len or math.pi * A.jar_d - 1.5}, "parts": []}
for name, (shape, colour, is_printed, label) in PARTS.items():
    if is_printed:
        cq.exporters.export(shape, os.path.join(A.out, f"{name}.stl"), tolerance=0.05, angularTolerance=0.2)
        bb = shape.val().BoundingBox()
        print(f"{name:18s} {bb.xlen:6.1f} x {bb.ylen:6.1f} x {bb.zlen:6.1f} mm")
    asm.add(shape, name=name, color=cq.Color(*[int(colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]))
    verts, tris = shape.val().tessellate(0.15, 0.35)
    viewer["parts"].append({
        "name": name, "label": label, "color": colour, "printed": is_printed,
        "v": [round(c, 2) for p in verts for c in (p.x, p.y, p.z)],
        "t": [i for t in tris for i in t],
    })
asm.export(os.path.join(A.out, f"assembly_{A.name}.step"))

# ---- self-contained 3D preview page ----------------------------------------
here = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(here, "preview_template.html")) as f:
    page = f.read().replace("__DATA__", json.dumps(viewer, separators=(",", ":")))
with open(os.path.join(here, "preview.html"), "w") as f:
    f.write(page)

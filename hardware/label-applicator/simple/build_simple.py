"""Simple wooden version of the label applicator: boards, a threaded rod, the
jar's own lid and an ordinary try-square. No 3D printing.

A wooden disc is clamped on an M8 threaded rod that turns in two wooden
uprights. The lid is screwed flat onto the front of the disc with three small
screws near its rim, and the stock of the square is screwed to the back, so
lid, disc and square turn as one rigid head. The blade of the square lies along the
jar, parallel to its axis, and is the edge the label is squared against. A
hinged wooden arm rests a strip of squeegee rubber on top of the jar.

Axes as in ../build.py: X = jar axis (0 at the closed face of the lid),
Y = towards the operator, Z = up (0 = top of the base board).

    python build_simple.py [--jar-d 98 --jar-len 115 --lid-d 101 --lid-h 17]

Writes preview.html (interactive 3D preview) next to this file.
"""
import argparse
import json
import math
import os
import re

import cadquery as cq

ap = argparse.ArgumentParser()
ap.add_argument("--jar-d", type=float, default=98.0, help="jar body diameter (estimate until measured)")
ap.add_argument("--jar-len", type=float, default=115.0, help="jar length incl. lid (estimate until measured)")
ap.add_argument("--lid-d", type=float, default=101.0, help="lid outer diameter (measured)")
ap.add_argument("--lid-h", type=float, default=17.0, help="lid height (measured)")
A = ap.parse_args()

AX_H = 120.0                  # rod height above the base board
T = 18.0                      # board thickness
SQ_BLADE_W, SQ_BLADE_L = 35.0, 300.0     # try-square blade (free length past the stock)
SQ_STOCK = (35.0, 15.0, 170.0)           # stock: depth along the rod, thickness, length
DISC_T, DISC_D = 18.0, 85.0      # wooden disc the lid is screwed to (same disc for both lid sizes)
REST_DEG = -70                # where the square sits in the drawing
LEAD_DEG = 10                 # square starts this far past the squeegee
TURN_DEG = 330                # how far the jar turns before the square reaches the arm

jar_r, lid_r = A.jar_d / 2, A.lid_d / 2
blade_r0 = lid_r + 0.5        # the blade's inner edge rests against the lid
blade_r1 = blade_r0 + SQ_BLADE_W
ARM_Z = AX_H + blade_r1 + 6   # underside of the arm clears the turning square
ARM_PIVOT = (-(blade_r1 + 44), ARM_Z)
BLADE_X0, BLADE_X1 = A.lid_h + 4, A.jar_len - 3
BLOCK_H = 32.0


def box(x0, x1, y0, y1, z0, z1):
    return cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, y0, z0))


def cyl_x(d, x0, x1, y=0.0, z=AX_H):
    return cq.Workplane("YZ").workplane(offset=x0).center(y, z).circle(d / 2).extrude(x1 - x0)


def about_rod(shape, deg):
    return shape.rotate((0, 0, AX_H), (1, 0, AX_H), deg)


X_STOCK = -DISC_T                          # stock of the square sits behind the disc
U1 = (X_STOCK - SQ_STOCK[0] - 30, X_STOCK - SQ_STOCK[0] - 12)
U2 = (U1[0] - 68, U1[0] - 50)              # the two uprights, 50 mm apart


def make_base():
    return box(U2[0] - 20, 160, ARM_PIVOT[0] - 20, 100, -T, 0)


def make_uprights():
    u = box(U1[0], U1[1], -40, 40, 0, AX_H + 40).union(box(U2[0], U2[1], -40, 40, 0, AX_H + 40))
    return u.cut(cyl_x(8.5, U2[0] - 5, U1[1] + 5))


def make_post():
    return box(40, 100, ARM_PIVOT[0], ARM_PIVOT[0] + T, 0, ARM_Z)


def make_arm():
    arm = box(50, 90, ARM_PIVOT[0], 12, ARM_Z, ARM_Z + 20)
    return arm.union(box(BLADE_X0, BLADE_X1, 0, 12, ARM_Z - BLOCK_H, ARM_Z))   # block the rubber is screwed to


def make_square():
    sd, st, sl = SQ_STOCK
    blade = box(0, SQ_BLADE_L, -2, 0, AX_H + blade_r0, AX_H + blade_r1)        # face y = 0 is the reference
    blade = blade.union(box(X_STOCK, 0, -2, 0, AX_H + blade_r0, AX_H + blade_r1))   # blade root, beside the disc
    stock = box(X_STOCK - sd, X_STOCK, -1 - st / 2, -1 + st / 2, AX_H + blade_r1 - sl, AX_H + blade_r1)
    return about_rod(blade.union(stock), REST_DEG)


def make_disc():
    return cyl_x(DISC_D, -DISC_T, 0).cut(cyl_x(8.2, -DISC_T - 1, 1))


def make_rod():
    sd = SQ_STOCK[0]
    rod = cyl_x(8, U2[0] - 18, 9)
    for x0 in (2.5, X_STOCK - sd - 6.5, U2[0] - 8, U2[0] - 14.5):              # nuts
        rod = rod.union(cq.Workplane("YZ").workplane(offset=x0).center(0, AX_H).polygon(6, 15).extrude(6.5))
    for k in range(3):                                                         # screws holding the lid on the disc
        a = math.radians(90 + 120 * k)
        rod = rod.union(cyl_x(7, 2, 4.5, y=32 * math.cos(a), z=AX_H + 32 * math.sin(a)))
    return rod



PARTS = {
    "base": (make_base(), "#c9a877", True, "القاعدة"),
    "uprights": (make_uprights(), "#b08a57", True, "قوايم المحور"),
    "post": (make_post(), "#b08a57", True, "عمود القومة"),
    "squeegee_arm": (make_arm(), "#d8bb8c", True, "ذراع القومة"),
    "lid_adapter_disc": (make_disc(), "#e0c08a", True, "قرص الراس (يتبرغى فيه الغطاء)"),
    "ruler_square": (make_square(), "#9aa5ad", True, "الزاوية القايمة (تلف مع العبوة)"),
    "ref_blade": (box(BLADE_X0, BLADE_X1, -3, 0, AX_H + jar_r, ARM_Z - 6), "#2b2f33", False, "مطاط القومة"),
    "ref_lid": (cyl_x(A.lid_d, 0.3, A.lid_h), "#d8b04a", False, "غطاء العبوة"),
    "ref_jar": (cyl_x(A.jar_d, A.lid_h, A.jar_len), "#2e5e45", False, "العبوة"),
    "ref_bolt": (make_rod(), "#70787f", False, "قضيب M8"),
}

# ---- checks: nothing fixed may be hit while the jar turns -------------------
fixed = PARTS["base"][0].union(PARTS["uprights"][0]).union(PARTS["post"][0]).union(PARTS["squeegee_arm"][0])
turning = PARTS["ruler_square"][0].union(PARTS["lid_adapter_disc"][0]).union(PARTS["ref_lid"][0]).union(PARTS["ref_jar"][0])
clashes = []
for alpha in range(0, TURN_DEG + 1, 10):
    v = about_rod(turning, LEAD_DEG - REST_DEG + alpha).intersect(fixed).val().Volume()
    if v > 0.5:
        clashes.append((alpha, round(v, 1)))
print("clashes:", clashes or "none")

# ---- preview page -----------------------------------------------------------
viewer = {"params": vars(A) | {"axis_h": AX_H, "ruler_rest_deg": REST_DEG, "lead_deg": LEAD_DEG, "turn_deg": TURN_DEG,
                               "arm_pivot": list(ARM_PIVOT), "label_x0": A.lid_h + 4,
                               "label_len": math.pi * A.jar_d - 1.5}, "parts": []}
for name, (shape, colour, made, label) in PARTS.items():
    verts, tris = shape.val().tessellate(0.15, 0.35)
    viewer["parts"].append({"name": name, "label": label, "color": colour, "printed": made,
                            "v": [round(c, 2) for p in verts for c in (p.x, p.y, p.z)],
                            "t": [i for t in tris for i in t]})

here = os.path.dirname(os.path.abspath(__file__))
tpl = open(os.path.join(here, "..", "preview_template.html")).read()
style_end = tpl.index('<div class="wrap"')
script_start = tpl.index('<script src=')
head, script = tpl[:style_end], tpl[script_start:]


def sub(pattern, new, text):
    out, count = re.subn(pattern, lambda m: new, text, count=1, flags=re.S)
    assert count == 1, pattern
    return out


def mm(v):
    return f'<span class="num">{v:g}</span>'


head = sub(r"<title>.*?</title>", "<title>مكينة الاستيكرات بالخشب</title>", head)
arm_len = 12 - ARM_PIVOT[0]
body = f'''<div class="wrap" dir="rtl" lang="ar">
  <header>
    <h1>النسخة البسيطة بالخشب</h1>
    <p class="lead">خشب، قضيب مسنن، غطاء العبوة، والزاوية القايمة اللي عندك. الغطاء يتبرغى على قرص خشب بثلاث براغي، والزاوية تتبرغى في ظهر القرص، والقرص مشدود على القضيب. الثلاثة يلفّوا قطعة وحدة، والقضيب يدور في قايمين خشب. ذراع على مفصلة ينزّل القومة على العبوة من فوق.</p>
  </header>

  <section>
    <div class="stage">
      <canvas id="view" aria-label="مجسم ثلاثي الأبعاد للمكينة"></canvas>
      <p class="step" id="step"></p>
      <p class="hint">اسحب باش تدوّر المجسم، وقرّب بالعجلة أو بإصبعين.</p>
      <div class="bar">
        <button id="spin" type="button" aria-pressed="true">وقّف العرض</button>
        <label for="explode">فكّ القطع <input id="explode" type="range" min="0" max="1" step="0.01" value="0"></label>
        <label for="refs"><input id="refs" type="checkbox" checked> العبوة والاستيكر</label>
        <button id="reset" type="button">رجّع الزاوية</button>
      </div>
      <div class="legend" id="legend"></div>
    </div>
  </section>

  <section>
    <h2>كيف تخدم</h2>
    <ol>
      <li>ربّط العبوة في الغطاء. الغطاء مبرغي على القرص الخشب، والزاوية القايمة مبرغية في ظهره، فمسطرتها ممدودة على طول العبوة وموازية لمحورها.</li>
      <li>ارفع ذراع القومة. حط طرف الاستيكر على حافة المسطرة، واكبس أول شريط بإصبعك.</li>
      <li>نزّل الذراع، ودوّر العبوة بيدك على مهل. المسطرة تلف معاها والقومة تكبس الاستيكر وتطرد الهواء.</li>
      <li>وقّف لما المسطرة تقرب توصل للقومة من الجهة الثانية. يقعد من الاستيكر حوالي {mm(2)} سم.</li>
      <li>ارفع الذراع، فك العبوة من الغطاء، واكبس آخر شريط بإصبعك.</li>
    </ol>
  </section>

  <section>
    <h2>الخشب اللي تقصّه</h2>
    <div class="scroll"><table>
      <thead><tr><th>القطعة</th><th>العدد</th><th>المقاس (مم)</th><th>ملاحظة</th></tr></thead>
      <tbody>
        <tr><td>قرص الراس</td><td class="num">1</td><td class="num">قطر {DISC_D:g} × {DISC_T:g}</td><td>دايرة خشب مثقوبة من النص {mm(8)} مم. الغطاء يتبرغى على وجهها</td></tr>
        <tr><td>القاعدة</td><td class="num">1</td><td class="num">{180 - U2[0]:g} × {120 - ARM_PIVOT[0]:g} × 18</td><td>لوح MDF أو خشب مضغوط</td></tr>
        <tr><td>قوايم المحور</td><td class="num">2</td><td class="num">{AX_H + 40:g} × 80 × 18</td><td>ثقب {mm(8.5)} في نص العرض، على ارتفاع {mm(AX_H)} من القاعدة. بين القايمين {mm(50)} مم</td></tr>
        <tr><td>عمود القومة</td><td class="num">1</td><td class="num">{ARM_Z:g} × 60 × 18</td><td>يوقف ورا العبوة</td></tr>
        <tr><td>ذراع القومة</td><td class="num">1</td><td class="num">{arm_len:g} × 40 × 20</td><td>يتركّب على راس العمود بمفصلة</td></tr>
        <tr><td>بلوك القومة</td><td class="num">1</td><td class="num">{BLADE_X1 - BLADE_X0:g} × {BLOCK_H:g} × 12</td><td>يتبرغى تحت طرف الذراع، والمطاط يتثبت على وجهه</td></tr>
      </tbody>
    </table></div>
  </section>

  <section>
    <h2>اللي تشريه</h2>
    <div class="scroll"><table>
      <thead><tr><th>القطعة</th><th>العدد</th><th>وين تتركّب</th></tr></thead>
      <tbody>
        <tr><td>قضيب مسنن <span class="num">M8</span> بطول {mm(200)} مم</td><td class="num">1</td><td>المحور: يفوت في الغطاء والقرص والزاوية والقايمين</td></tr>
        <tr><td>صواميل <span class="num">M8</span></td><td class="num">4</td><td>وحدة داخل الغطاء، وحدة ورا الزاوية تشد الغطاء والقرص والزاوية على بعض، واثنين مقفولات على بعض ورا القايم الأخير</td></tr>
        <tr><td>ورد <span class="num">M8</span></td><td class="num">4</td><td>بين الصواميل والخشب</td></tr>
        <tr><td>زوايا حديد صغار ببراغي خشب</td><td class="num">6</td><td>اثنين لكل قايم، واثنين لعمود القومة</td></tr>
        <tr><td>مفصلة صغيرة</td><td class="num">1</td><td>بين راس العمود والذراع</td></tr>
        <tr><td>مطاط مسّاحة زجاج، طول {mm(BLADE_X1 - BLADE_X0)} مم</td><td class="num">1</td><td>على وجه البلوك، نازل منه لين يلمس العبوة</td></tr>
        <tr><td>براغي خشب قصار ({mm(12)} مم) براس مسطّح</td><td class="num">3</td><td>من داخل الغطاء في القرص، قرب الحافة، على شكل مثلث</td></tr>
        <tr><td>براغي خشب {mm(30)} مم</td><td class="num">2</td><td>من ماسكة الزاوية في ظهر القرص</td></tr>
        <tr><td>براغي خشب صغار بورد</td><td class="num">5</td><td>ثلاثة للمطاط واثنين للبلوك</td></tr>
        <tr><td>غطاء عبوة زايد</td><td class="num">1</td><td>يتثقب من النص {mm(8)} مم ويقعد مبرغي على القرص. واحد لكل مقاس</td></tr>
      </tbody>
    </table></div>
  </section>

  <section class="note">
    <h2>قبل ما تبدا</h2>
    <p>العدّة: منشار، دريل ببنطة {mm(8)} و{mm(8.5)} مم، مفك، ومربطين. اثقب القايمين وهم مشدودين على بعض بالمرابط، باش الثقبين يطلعوا على نفس الارتفاع بالضبط.</p>
    <p>الزاوية المرسومة هنا مسطرتها {mm(SQ_BLADE_L)} مم وماسكتها {mm(SQ_STOCK[2])} مم، تقدير من صورك. ماسكتها تتثقب {mm(8)} مم باش يفوت فيها القضيب، وحافة المسطرة الداخلية تتكّى على حافة الغطاء.</p>
    <p>عندك مقاسين غطاء: {mm(101)} و{mm(90)} مم. القرص واحد للزوز، وتبدّل الغطاء بفك الثلاث براغي. الزاوية تتبرغى في مكانين على ظهر القرص، واحد لكل مقاس، باش حافة مسطرتها تتكّى على حافة الغطاء.</p>
    <p>العبوة ماسكة من جهة الغطاء بس، وقاعها في الهواء. لو لقيتها تتهز تحت القومة، خفّف ضغط القومة أول؛ ولو ما نفعش نضيفوا سندة للقاع.</p>
    <p>المرسوم هنا الغطاء الكبير: قطره <span class="num" id="p-lid"></span> مم وسمكه <span class="num" id="p-lidh"></span> مم. قطر العبوة (<span class="num" id="p-jar"></span> مم) وطولها (<span class="num" id="p-len"></span> مم) مازالوا تقدير. قيسهم قبل ما تقص بلوك القومة ومطاطها.</p>
    <p>هذا رسم ما تخدمش ولا تجرّب. اللي تأكدت منه بالحساب إن الزاوية تلف {mm(TURN_DEG)} درجة بلا ما تخبط في القاعدة أو القوايم أو الذراع.</p>
  </section>
</div>

'''

script = sub(r"const NOTES = \{.*?\n\}\);\n", '''document.getElementById("p-jar").textContent = DATA.params.jar_d;
document.getElementById("p-lid").textContent = DATA.params.lid_d;
document.getElementById("p-lidh").textContent = DATA.params.lid_h;
document.getElementById("p-len").textContent = DATA.params.jar_len;
''', script)
script = sub(r"const EXPL = \{.*?\};", 'const EXPL = { base:[0,0,-50], uprights:[-90,0,0], ref_bolt:[-190,0,0], lid_adapter_disc:[-10,0,0], ref_lid:[45,0,0], ref_jar:[130,0,0], post:[0,-50,0], squeegee_arm:[0,-30,90], ref_blade:[0,-30,50] };', script)
script = sub(r"const STEPS = \[.*?\];", '''const STEPS = ["١. حط طرف الاستيكر على حافة المسطرة", "٢. اكبس أول شريط بإصبعك ونزّل القومة",
                 "٣. دوّر العبوة بيدك: المسطرة تلف معاها والقومة تكبس الاستيكر", "٤. وقّف قبل ما المسطرة توصل للقومة، وارفع الذراع",
                 "٥. فك العبوة من الغطاء واكبس آخر شريط بإصبعك", "٦. الاستيكر ركب. ربّط العبوة اللي بعدها"];''', script)
script = sub(r"LEAD0 = 5\*RAD,", "LEAD0 = P.lead_deg*RAD, TURN = P.turn_deg,", script)
script = sub(r"    let off=0, lift=0.*?    armHinges\.forEach\(h => h\.rotation\.x = lift\);\n    setLabel\(.*?\);\n", '''    let lift=0, alpha=0, op=1, slide=1, step=0, pull=0, wrap=0;
    if (t < T[0]) { slide = ease(seg(t,0,T[0])); lift = LIFT; op = seg(t,0,.3); step=0; }
    else if (t < T[1]) { lift = LIFT*(1-ease(seg(t,T[0],T[1]))); step=1; }
    else if (t < T[2]) { alpha = TURN*ease(seg(t,T[1],T[2])); step=2; }
    else if (t < T[3]) { alpha = TURN; lift = LIFT*ease(seg(t,T[2],T[3])); step=3; }
    else if (t < T[4]) { alpha = TURN; lift = LIFT; const u=seg(t,T[3],T[4]); pull = ease(Math.min(1,u*1.6)); wrap = ease(Math.max(0,u*2.5-1.5)); step=4; }
    else { alpha = TURN; lift = LIFT; pull=1; wrap=1; step=5; op = 1-seg(t,T[5],T[6]); }
    spinG.rotation.x = (P.lead_deg - P.ruler_rest_deg + alpha)*RAD;
    armHinges.forEach(h => h.rotation.x = lift);
    // the jar comes off the lid along the rod, taking the label with it
    const k = +explode.value, dx = 150*pull;
    if (meshes.ref_jar) meshes.ref_jar.holder.position.x = 130*k + dx;
    label.position.x = dx;
    setLabel(t < T[0] ? -70 + (RL*LEAD0 + 70)*slide : RL*(LEAD0 + (alpha + (360 - TURN)*wrap)*RAD));
''', script)
script = sub(r"new THREE\.Vector3\(35, 85, 5\)", "new THREE.Vector3(60, 105, 25)", script)
script = sub(r"HOME = \{th:2\.45, ph:1\.05, r:540\}", "HOME = {th:2.35, ph:1.05, r:880}", script)
# `explode` must exist before pose() first runs
assert script.index('const explode = document.getElementById("explode")') < script.index("(function tick(")

page = (head + body + script).replace("__DATA__", json.dumps(viewer, separators=(",", ":")))
open(os.path.join(here, "preview.html"), "w").write(page)
print("wrote preview.html")

"""Simple wooden label applicator for closed jars: boards, plywood rings, two
M8 rods, a spring and a strip of aluminium flat bar. No 3D printing.

The jar goes in with its own lid on and comes out the same way. It is held
between a turning head and a sprung tail pad, like work between lathe centres:

* The head is a wooden disc on an M8 rod with two plywood rings glued on its
  face. The rings form a stepped socket: the large lid seats in the outer
  ring, the small lid passes through it and seats in the inner one, so both
  jar sizes centre themselves with nothing to swap.
* The tail is a small padded disc on a second M8 rod that slides in an
  upright and is pushed by a spring. Pull it back, drop the jar in, let go.
* An aluminium flat bar bolted to a steel corner bracket on the head lies
  along the jar, parallel to its axis. It turns with the jar and is the edge
  the label is squared against. Two pairs of holes set it for either size.
* A hinged wooden arm rests a strip of squeegee rubber on top of the jar.

Axes: X = jar axis (0 at the seat of the large lid), Y = towards the
operator, Z = up (0 = top of the base board).

    python build_simple.py            # large jar
    python build_simple.py --size small

Writes preview.html (interactive 3D preview) next to this file.
"""
import argparse
import json
import math
import os
import re

import cadquery as cq

# lid diameters and jar lengths were read off the user's ruler photos; body
# diameters and the small lid's height are estimates
SIZES = {
    "large": dict(lid_d=101.0, lid_h=17.0, jar_d=98.0, jar_len=120.0),
    "small": dict(lid_d=90.0, lid_h=15.0, jar_d=87.0, jar_len=108.0),
}
ap = argparse.ArgumentParser()
ap.add_argument("--size", choices=SIZES, default="large", help="which jar to draw in the machine")
A = ap.parse_args()
J = SIZES[A.size]
BIG, SMALL = SIZES["large"], SIZES["small"]

AX_H = 125.0                   # rod height above the base board
T = 18.0                       # board thickness
RING_SMALL_T, RING_BIG_T = 4.0, 8.0     # socket depths for the small and the large lid
RING_OD, DISC_D = 120.0, 190.0
BAR_W, BAR_T = 40.0, 3.0       # aluminium flat bar (the ruler)
BAR_X0, BAR_X1 = 18.0, 98.0
BRK = dict(r0=62.0, r1=82.0, leg_face=40.0, leg_out=75.0, t=2.0)   # steel corner bracket
REST_DEG = -70                 # where the ruler sits in the drawing
LEAD_DEG = 10                  # ruler starts this far past the squeegee
TURN_DEG = 330                 # how far the jar turns before the ruler reaches the arm

seat_x = 0.0 if A.size == "large" else -RING_SMALL_T
jar_r, lid_r = J["jar_d"] / 2, J["lid_d"] / 2
lid_x1, jar_x1 = seat_x + J["lid_h"], seat_x + J["jar_len"]
bar_r0 = max(jar_r, lid_r - 0.5) + 1.5        # just clear of the jar wall and the lid rim
sweep_r = math.hypot(BRK["leg_face"] + 5, BRK["r1"])      # far corner of the bracket
DISC_X = (-RING_SMALL_T - T, -RING_SMALL_T)
ARM_Z = AX_H + max(sweep_r, BIG["jar_d"] / 2 + 1.5 + BAR_W) + 6
ARM_PIVOT = (-(sweep_r + 28), ARM_Z)
BLADE_X0, BLADE_X1 = BIG["lid_h"] + 2, BIG["jar_len"] - 3
BLOCK_H = 32.0
TAIL_X = 195.0                 # front face of the tail upright
PAD_T, PAD_D = 18.0, 60.0


def box(x0, x1, y0, y1, z0, z1):
    return cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, y0, z0))


def cyl_x(d, x0, x1, y=0.0, z=AX_H):
    return cq.Workplane("YZ").workplane(offset=x0).center(y, z).circle(d / 2).extrude(x1 - x0)


def nut(x0):
    return cq.Workplane("YZ").workplane(offset=x0).center(0, AX_H).polygon(6, 15).extrude(6.5)


def about_rod(shape, deg):
    return shape.rotate((0, 0, AX_H), (1, 0, AX_H), deg)


U1 = (DISC_X[0] - 30, DISC_X[0] - 12)      # the two head uprights, 50 mm apart
U2 = (U1[0] - 68, U1[0] - 50)


def make_base():
    return box(U2[0] - 20, TAIL_X + T + 50, ARM_PIVOT[0] - 20, 110, -T, 0)


def make_uprights():
    u = None
    for x0, x1 in (U1, U2, (TAIL_X, TAIL_X + T)):
        b = box(x0, x1, -40, 40, 0, AX_H + 40)
        u = b if u is None else u.union(b)
    return u.cut(cyl_x(8.5, U2[0] - 5, TAIL_X + T + 5))


def make_head():
    h = cyl_x(DISC_D, *DISC_X)
    h = h.union(cyl_x(RING_OD, -RING_SMALL_T, 0).cut(cyl_x(SMALL["lid_d"] + 0.6, -RING_SMALL_T - 1, 1)))
    h = h.union(cyl_x(RING_OD, 0, RING_BIG_T).cut(cyl_x(BIG["lid_d"] + 0.6, -1, RING_BIG_T + 1)))
    h = h.cut(cyl_x(8.2, DISC_X[0] - 1, DISC_X[1] + 1))
    return h.cut(cyl_x(17, DISC_X[1] - 7, DISC_X[1] + 1))          # pocket so the rod nut sits below the seat


def make_ruler():
    """Flat bar + corner bracket, drawn at 12 o'clock with the reference face in the plane y = 0."""
    bar = box(BAR_X0, BAR_X1, -BAR_T, 0, AX_H + bar_r0, AX_H + bar_r0 + BAR_W)
    t = BRK["t"]
    leg_out = box(DISC_X[1], DISC_X[1] + BRK["leg_out"], -BAR_T - t, -BAR_T, AX_H + BRK["r0"], AX_H + BRK["r1"])
    leg_face = box(DISC_X[1], DISC_X[1] + t, -BAR_T - BRK["leg_face"], -BAR_T, AX_H + BRK["r0"], AX_H + BRK["r1"])
    return about_rod(bar.union(leg_out).union(leg_face), REST_DEG)


def make_head_rod():
    rod = cyl_x(8, U2[0] - 18, DISC_X[1] - 0.5)
    for x0 in (DISC_X[1] - 7, DISC_X[0] - 6.5, U2[0] - 8, U2[0] - 14.5):
        rod = rod.union(nut(x0))
    return rod


def make_tail():
    """Pad, rod and pull nuts; drawn pressed against the bottom of the jar."""
    pad = cyl_x(PAD_D, jar_x1, jar_x1 + PAD_T)
    rod = cyl_x(8, jar_x1 + 2, TAIL_X + T + 55)
    return pad.union(rod).union(nut(TAIL_X + T + 40)).union(nut(TAIL_X + T + 46.5))


def make_post():
    return box(40, 100, ARM_PIVOT[0], ARM_PIVOT[0] + T, 0, ARM_Z)


def make_arm():
    arm = box(50, 90, ARM_PIVOT[0], 12, ARM_Z, ARM_Z + 20)
    return arm.union(box(BLADE_X0, BLADE_X1, 0, 12, ARM_Z - BLOCK_H, ARM_Z))   # block the rubber is screwed to


arm_tilt = math.degrees(math.asin((jar_r - BIG["jar_d"] / 2) / -ARM_PIVOT[0]))


def tilt(shape):   # the hinged arm drops a little for the smaller jar
    return shape.rotate((0, ARM_PIVOT[0], ARM_PIVOT[1]), (1, ARM_PIVOT[0], ARM_PIVOT[1]), arm_tilt)


PARTS = {
    "base": (make_base(), "#c9a877", True, "القاعدة"),
    "uprights": (make_uprights(), "#b08a57", True, "القوايم الثلاثة"),
    "lid_adapter_head": (make_head(), "#e0c08a", True, "الراس الدوّار (قرص وحلقتين)"),
    "ruler_bar": (make_ruler(), "#9aa5ad", True, "المسطرة (تلف مع العبوة)"),
    "tail_pad": (make_tail(), "#d39a4a", True, "سندة القاع بالزنبرك"),
    "post": (make_post(), "#b08a57", True, "عمود القومة"),
    "squeegee_arm": (tilt(make_arm()), "#d8bb8c", True, "ذراع القومة"),
    "ref_blade": (tilt(box(BLADE_X0, BLADE_X1, -3, 0, AX_H + BIG["jar_d"] / 2, ARM_Z - 6)), "#2b2f33", False, "مطاط القومة"),
    "ref_lid": (cyl_x(J["lid_d"], seat_x + 0.2, lid_x1), "#d8b04a", False, "غطاء العبوة"),
    "ref_jar": (cyl_x(J["jar_d"], lid_x1, jar_x1), "#2e5e45", False, "العبوة"),
    "ref_bolt": (make_head_rod(), "#70787f", False, "قضيب الراس M8"),
}

# ---- checks -----------------------------------------------------------------
jar_like = PARTS["ref_jar"][0].union(PARTS["ref_lid"][0])
fixed = PARTS["base"][0]
for n in ("uprights", "post", "squeegee_arm"):
    fixed = fixed.union(PARTS[n][0])
turning = PARTS["ruler_bar"][0].union(PARTS["lid_adapter_head"][0]).union(jar_like)
clashes = []
for name in ("lid_adapter_head", "ruler_bar"):                     # the jar must fit the head and clear the ruler
    v = PARTS[name][0].intersect(jar_like).val().Volume()
    if v > 0.5:
        clashes.append((name, "jar", round(v, 1)))
for alpha in range(0, TURN_DEG + 1, 10):                           # nothing fixed may be hit while it turns
    v = about_rod(turning, LEAD_DEG - REST_DEG + alpha).intersect(fixed).val().Volume()
    if v > 0.5:
        clashes.append((alpha, round(v, 1)))
print(A.size, "clashes:", clashes or "none")

# ---- preview page -----------------------------------------------------------
viewer = {"params": J | {"axis_h": AX_H, "ruler_rest_deg": REST_DEG, "lead_deg": LEAD_DEG, "turn_deg": TURN_DEG,
                         "arm_pivot": list(ARM_PIVOT), "label_x0": lid_x1 + 3, "label_x1": jar_x1 - 6,
                         "label_len": math.pi * J["jar_d"] - 1.5}, "parts": []}
for name, (shape, colour, made, label) in PARTS.items():
    verts, tris = shape.val().tessellate(0.15, 0.35)
    viewer["parts"].append({"name": name, "label": label, "color": colour, "printed": made,
                            "v": [round(c, 2) for p in verts for c in (p.x, p.y, p.z)],
                            "t": [i for t in tris for i in t]})

here = os.path.dirname(os.path.abspath(__file__))
tpl = open(os.path.join(here, "..", "preview_template.html")).read()
head, script = tpl[:tpl.index('<div class="wrap"')], tpl[tpl.index('<script src='):]


def sub(pattern, new, text):
    out, count = re.subn(pattern, lambda m: new, text, count=1, flags=re.S)
    assert count == 1, pattern
    return out


def mm(v):
    return f'<span class="num">{v:g}</span>'


base_bb = PARTS["base"][0].val().BoundingBox()
head = sub(r"<title>.*?</title>", "<title>مكينة الاستيكرات بالخشب</title>", head)
body = f'''<div class="wrap" dir="rtl" lang="ar">
  <header>
    <h1>النسخة البسيطة بالخشب</h1>
    <p class="lead">العبوة تدخل بغطاها وتطلع بغطاها. تنشد بين راس دوّار وسندة بزنبرك من جهة القاع: تسحب السندة، تحط العبوة، تسيّب. الراس فيه تجويف مدرّج يشد الغطاء الكبير والصغير بلا ما تبدّل شي.</p>
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
      <li>اسحب سندة القاع لورا، دخّل غطاء العبوة في تجويف الراس، وسيّب السندة. الزنبرك يدفع العبوة على الراس ويشدّها.</li>
      <li>ارفع ذراع القومة. حط طرف الاستيكر على حافة المسطرة، واكبس أول شريط بإصبعك.</li>
      <li>نزّل الذراع، ودوّر الراس من قرصه الكبير على مهل. المسطرة تلف مع العبوة والقومة تكبس الاستيكر وتطرد الهواء.</li>
      <li>وقّف لما المسطرة تقرب توصل للقومة من الجهة الثانية. يقعد من الاستيكر حوالي {mm(2.5)} سم.</li>
      <li>ارفع الذراع، اسحب السندة وطلّع العبوة بغطاها، واكبس آخر شريط بإصبعك.</li>
    </ol>
  </section>

  <section>
    <h2>المقاسين</h2>
    <div class="scroll"><table>
      <thead><tr><th></th><th>العبوة الكبيرة</th><th>العبوة الصغيرة</th></tr></thead>
      <tbody>
        <tr><td>قطر الغطاء (من صورك)</td><td class="num">{BIG["lid_d"]:g}</td><td class="num">{SMALL["lid_d"]:g}</td></tr>
        <tr><td>الطول بالغطاء (من صورك)</td><td class="num">{BIG["jar_len"]:g}</td><td class="num">{SMALL["jar_len"]:g}</td></tr>
        <tr><td>قطر الجسم (تقدير)</td><td class="num">{BIG["jar_d"]:g}</td><td class="num">{SMALL["jar_d"]:g}</td></tr>
        <tr><td>وين يقعد الغطاء</td><td>في الحلقة البرّانية</td><td>يفوت من البرّانية ويقعد في الجوّانية</td></tr>
        <tr><td>المسطرة</td><td>ثقوبها البرّانية</td><td>ثقوبها الجوّانية، أقرب للمحور بـ {mm(BIG["jar_d"] / 2 - SMALL["jar_d"] / 2)} مم</td></tr>
      </tbody>
    </table></div>
    <p>السندة والقومة يتعدّلوا بروحهم: الزنبرك ياخذ فرق الطول، والذراع على مفصلة ينزل على العبوة الأصغر. المرسوم فوق هو العبوة {"الكبيرة" if A.size == "large" else "الصغيرة"}.</p>
  </section>

  <section>
    <h2>الخشب اللي تقصّه</h2>
    <div class="scroll"><table>
      <thead><tr><th>القطعة</th><th>العدد</th><th>المقاس (مم)</th><th>ملاحظة</th></tr></thead>
      <tbody>
        <tr><td>قرص الراس</td><td class="num">1</td><td class="num">قطر {DISC_D:g} × {T:g}</td><td>مثقوب من النص {mm(8)} مم. تدوّر منه بيدك</td></tr>
        <tr><td>حلقة الغطاء الصغير</td><td class="num">1</td><td class="num">قطر {RING_OD:g} × {RING_SMALL_T:g}</td><td>فتحتها {mm(SMALL["lid_d"] + 0.6)} مم. تتلصق على وجه القرص</td></tr>
        <tr><td>حلقة الغطاء الكبير</td><td class="num">1</td><td class="num">قطر {RING_OD:g} × {RING_BIG_T:g}</td><td>فتحتها {mm(BIG["lid_d"] + 0.6)} مم. تتلصق فوق الأولى</td></tr>
        <tr><td>سندة القاع</td><td class="num">1</td><td class="num">قطر {PAD_D:g} × {PAD_T:g}</td><td>مثقوبة من النص، وعلى وجهها قطعة مطاط</td></tr>
        <tr><td>القوايم</td><td class="num">3</td><td class="num">{AX_H + 40:g} × 80 × {T:g}</td><td>ثقب {mm(8.5)} في نص العرض، على ارتفاع {mm(AX_H)} من القاعدة. اثنين للراس بينهم {mm(50)} مم، وواحد للسندة</td></tr>
        <tr><td>القاعدة</td><td class="num">1</td><td class="num">{base_bb.xlen:g} × {base_bb.ylen:.0f} × {T:g}</td><td>لوح MDF أو خشب مضغوط</td></tr>
        <tr><td>عمود القومة</td><td class="num">1</td><td class="num">{ARM_Z:.0f} × 60 × {T:g}</td><td>يوقف ورا العبوة</td></tr>
        <tr><td>ذراع القومة</td><td class="num">1</td><td class="num">{12 - ARM_PIVOT[0]:.0f} × 40 × 20</td><td>يتركّب على راس العمود بمفصلة</td></tr>
        <tr><td>بلوك القومة</td><td class="num">1</td><td class="num">{BLADE_X1 - BLADE_X0:g} × {BLOCK_H:g} × 12</td><td>يتبرغى تحت طرف الذراع، والمطاط يتثبت على وجهه</td></tr>
      </tbody>
    </table></div>
  </section>

  <section>
    <h2>اللي تشريه</h2>
    <div class="scroll"><table>
      <thead><tr><th>القطعة</th><th>العدد</th><th>وين تتركّب</th></tr></thead>
      <tbody>
        <tr><td>قضيب مسنن <span class="num">M8</span> بطول {mm(160)} مم</td><td class="num">1</td><td>محور الراس: يفوت في القرص والقايمين</td></tr>
        <tr><td>قضيب مسنن <span class="num">M8</span> بطول {mm(150)} مم</td><td class="num">1</td><td>محور السندة: يتزلق ويدور في القايم الثالث</td></tr>
        <tr><td>صواميل <span class="num">M8</span> وورد</td><td class="num">8</td><td>أربعة للراس (وحدة غاطسة في وجه القرص)، واثنين للسندة، واثنين مقبض تسحب منه</td></tr>
        <tr><td>زنبرك ضغط طري، قطره الداخلي {mm(10)} وطوله حوالي {mm(90)} مم</td><td class="num">1</td><td>على قضيب السندة، بين السندة وقايمها</td></tr>
        <tr><td>مسطّح ألمنيوم {mm(BAR_W)} × {mm(BAR_T)}، طول {mm(BAR_X1 - BAR_X0)} مم</td><td class="num">1</td><td>المسطرة. حافته اللي من جهة العبوة لازم تكون مستقيمة ونظيفة</td></tr>
        <tr><td>زاوية حديد {mm(BRK["leg_face"])} × {mm(BRK["leg_out"])} بعرض {mm(BRK["r1"] - BRK["r0"])} مم</td><td class="num">1</td><td>ضلعها القصير على وجه القرص ببرغيين خشب، والطويل ممدود على طول العبوة والمسطرة مبرغية فيه</td></tr>
        <tr><td>براغي <span class="num">M4×12</span> بصواميل</td><td class="num">2</td><td>يشدّوا المسطرة في زاوية الحديد. في المسطرة زوجين ثقوب، واحد لكل مقاس</td></tr>
        <tr><td>زوايا حديد صغار ببراغي خشب</td><td class="num">8</td><td>اثنين لكل قايم، واثنين لعمود القومة</td></tr>
        <tr><td>مفصلة صغيرة</td><td class="num">1</td><td>بين راس العمود والذراع</td></tr>
        <tr><td>مطاط مسّاحة زجاج، طول {mm(BLADE_X1 - BLADE_X0)} مم</td><td class="num">1</td><td>على وجه البلوك، نازل منه لين يلمس العبوة</td></tr>
        <tr><td>غراء خشب، وشريط إسفنج لاصق رقيق</td><td class="num">1</td><td>الغراء للحلقات، والإسفنج يتبطّن بيه جدار التجويفين باش الغطاء يدخل مشدود</td></tr>
      </tbody>
    </table></div>
  </section>

  <section class="note">
    <h2>قبل ما تبدا</h2>
    <p>العدّة: منشار، منشار دواير أو أركت للحلقات، دريل ببنطة {mm(8)} و{mm(8.5)} مم، مفك، ومربطين. اثقب القوايم الثلاثة وهم مشدودين على بعض بالمرابط، باش الثقوب تطلع على نفس الارتفاع بالضبط.</p>
    <p>فتحة الحلقة ما لازمش تطلع مضبوطة بالملّي. قصّها أوسع بشوية وبطّنها بشريط الإسفنج لين الغطاء يدخل بضغطة خفيفة. اللي يحدد استقامة العبوة هو قعدة الغطاء مسطّح على قاع التجويف، مش جدار الحلقة.</p>
    <p>قطر جسم العبوتين ({mm(BIG["jar_d"])} و{mm(SMALL["jar_d"])} مم) وارتفاع الغطاء الصغير ({mm(SMALL["lid_h"])} مم) تقدير مني. عليهم يتحدد مكان ثقوب المسطرة، فاثقبهم على العبوة نفسها: حط العبوة في المكينة وقرّب حافة المسطرة لين تبعد عن جدارها {mm(1.5)} مم، وعلّم.</p>
    <p>القومة مضبوطة على العبوة الكبيرة. في الصغيرة يقعد شريط حوالي {mm(BLADE_X0 - (-RING_SMALL_T + SMALL["lid_h"]))} مم تحت الغطاء القومة ما توصلاش، تكبسه بإصبعك.</p>
    <p>هذا رسم ما تخدمش ولا تجرّب. اللي تأكدت منه بالحساب، للمقاسين، إن الغطاء يدخل في تجويفه وإن المسطرة تلف {mm(TURN_DEG)} درجة بلا ما تخبط في القاعدة أو القوايم أو الذراع.</p>
  </section>
</div>

'''

script = sub(r"const NOTES = \{.*?\n\}\);\n", "", script)
script = sub(r"const EXPL = \{.*?\};", 'const EXPL = { base:[0,0,-50], uprights:[0,0,0], ref_bolt:[-150,0,0], lid_adapter_head:[-60,0,0], ref_lid:[0,0,0], ref_jar:[0,0,0], tail_pad:[90,0,0], post:[0,-50,0], squeegee_arm:[0,-30,90], ref_blade:[0,-30,50] };', script)
script = sub(r"LX1 = P\.jar_len - 8", "LX1 = P.label_x1", script)
script = sub(r"const STEPS = \[.*?\];", '''const STEPS = ["١. حط طرف الاستيكر على حافة المسطرة", "٢. اكبس أول شريط بإصبعك ونزّل القومة",
                 "٣. دوّر الراس: المسطرة تلف مع العبوة والقومة تكبس الاستيكر", "٤. وقّف قبل ما المسطرة توصل للقومة، وارفع الذراع",
                 "٥. اسحب السندة، طلّع العبوة بغطاها، واكبس آخر شريط بإصبعك", "٦. اسحب السندة وحط العبوة اللي بعدها"];''', script)
script = sub(r"LEAD0 = 5\*RAD,", "LEAD0 = P.lead_deg*RAD, TURN = P.turn_deg,", script)
script = sub(r"    let off=0, lift=0.*?    armHinges\.forEach\(h => h\.rotation\.x = lift\);\n    setLabel\(.*?\);\n", '''    let lift=0, alpha=0, op=1, slide=1, step=0, pull=0, wrap=0, back=0;
    const cl = x => Math.max(0, Math.min(1, x));
    if (t < T[0]) { slide = ease(seg(t,0,T[0])); lift = LIFT; op = seg(t,0,.3); step=0; }
    else if (t < T[1]) { lift = LIFT*(1-ease(seg(t,T[0],T[1]))); step=1; }
    else if (t < T[2]) { alpha = TURN*ease(seg(t,T[1],T[2])); step=2; }
    else if (t < T[3]) { alpha = TURN; lift = LIFT*ease(seg(t,T[2],T[3])); step=3; }
    else if (t < T[4]) { alpha = TURN; lift = LIFT; const u=seg(t,T[3],T[4]); back = ease(cl(u*4)); pull = ease(cl((u-.25)*2)); wrap = ease(cl((u-.75)*4)); step=4; }
    else { alpha = TURN; lift = LIFT; wrap=1; step=5; const u=seg(t,T[5],T[6]); op = 1-cl(u*2.5); pull = 1-ease(cl(u*2.5-1.2)); back = pull > .02 ? 1 : 1-ease(cl(u*8-7)); }
    const th = (P.lead_deg - P.ruler_rest_deg + alpha)*RAD;
    spinG.rotation.x = th;
    armHinges.forEach(h => h.rotation.x = lift);
    // the closed jar lifts out towards the operator, taking its lid and the label with it
    const k = +explode.value, dy = 150*pull, dz = 60*pull, ly = dy*Math.cos(th) + dz*Math.sin(th), lz = -dy*Math.sin(th) + dz*Math.cos(th);
    for (const n of ["ref_jar", "ref_lid"]) if (meshes[n]) meshes[n].holder.position.set(0, ly, lz);
    label.position.set(0, dy, dz);
    if (meshes.tail_pad) meshes.tail_pad.holder.position.x = 90*k + 28*back;
    setLabel(t < T[0] ? -70 + (RL*LEAD0 + 70)*slide : RL*(LEAD0 + (alpha + (360 - TURN)*wrap)*RAD));
''', script)
script = sub(r"new THREE\.Vector3\(35, 85, 5\)", "new THREE.Vector3(60, 110, 15)", script)
script = sub(r"HOME = \{th:2\.45, ph:1\.05, r:540\}", "HOME = {th:2.5, ph:1.0, r:900}", script)
assert script.index('const explode = document.getElementById("explode")') < script.index("(function tick(")

page = (head + body + script).replace("__DATA__", json.dumps(viewer, separators=(",", ":")))
open(os.path.join(here, "preview.html"), "w").write(page)
print("wrote preview.html")

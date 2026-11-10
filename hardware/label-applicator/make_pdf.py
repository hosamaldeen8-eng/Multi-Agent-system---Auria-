"""Build the printable Arabic build guide (guide.html -> PDF via headless Chromium).

    python make_pdf.py            # same arguments as build.py

Needs Node with Playwright for the renders and the PDF step.
"""
import os
import runpy
import subprocess
import sys
import tempfile

import cadquery as cq

HERE = os.path.dirname(os.path.abspath(__file__))
G = runpy.run_path(os.path.join(HERE, "build.py"))          # rebuilds parts + preview.html
A, PARTS = G["A"], G["PARTS"]
WORK = tempfile.mkdtemp(prefix="label_guide_")
OUT_PDF = os.path.join(HERE, f"label-applicator-guide-{A.name}.pdf")


def n(v):
    return f"{v:.1f}".rstrip("0").rstrip(".")


def num(s):
    return f'<span class="num">{s}</span>'


# ---- line drawings of each printed part -------------------------------------
VIEWS = [("iso", (1.0, -1.2, 0.8), "منظور"), ("front", (0, -1, 0), "من القدام"),
         ("top", (0, 0, 1), "من فوق"), ("side", (1, 0, 0), "من الجنب")]


def drawings(name, shape):
    if name.startswith(("ruler", "lid_adapter")):            # draw with the ruler at 12 o'clock
        shape = G["about_spindle"](shape, -G["RULER_REST_DEG"])
    bb = shape.val().BoundingBox()
    dims = {"front": (bb.xlen, bb.zlen), "top": (bb.xlen, bb.ylen), "side": (bb.ylen, bb.zlen)}
    cells = []
    for key, direction, title in VIEWS:
        path = os.path.join(WORK, f"{name}_{key}.svg")
        cq.exporters.export(shape, path, opt={
            "width": 340, "height": 240, "marginLeft": 12, "marginTop": 12, "showAxes": False,
            "projectionDir": direction, "strokeWidth": 0.5, "strokeColor": (30, 40, 50),
            "hiddenColor": (170, 180, 190), "showHidden": key != "iso"})
        svg = open(path).read()
        svg = svg[svg.index("<svg"):]
        cap = title if key == "iso" else f'{title}: {num(n(dims[key][0]) + " × " + n(dims[key][1]))} مم'
        cells.append(f'<figure class="view">{svg}<figcaption>{cap}</figcaption></figure>')
    return "".join(cells), bb


ad_r, jar_r = G["ad_r"], G["jar_r"]
PIV_Z = G["ARM_PIVOT_Z"]
DETAILS = {
    "base": ("تنطبع مسطّحة والأعمدة لفوق. ما تحتاجش دعامات.", [
        f"اللوح: {num('185 × 165 × 8')} مم",
        f"عمودين سمك {num(7)} وعرض {num(20)}، ارتفاعهم {num(n(PIV_Z + 10))} مم من وجه اللوح",
        f"ثقب مفصل الذراع: قطر {num(5.2)} على ارتفاع {num(n(PIV_Z))} مم",
        f"أربع ثقوب قطر {num(4.4)} لبراغي حامل المحور",
    ]),
    "headstock": ("تنطبع واقفة على قاعدتها. جيوب الرولمان تطلع أدق هكي.", [
        f"ارتفاع المحور عن وجه القاعدة: {num(n(G['AX_H']))} مم",
        f"جيبين للرولمان 608: قطر {num(22.2)} وعمق {num(7)}، واحد في كل وجه",
        f"ثقب المحور: قطر {num(10)} نافذ",
        f"القدم: {num('50 × 80 × 6')} مم وفيها أربع ثقوب قطر {num(4.4)}",
    ]),
    "lid_adapter": ("ينطبع والفتحة لفوق، والسكّة تطلع واقفة. واحد لكل مقاس غطاء.", [
        f"جيب الغطاء: قطر {num(n(A.lid_d + 0.6))} وعمق {num(10)} مم (الغطاء {num(n(A.lid_d))} مم)",
        f"القطر الخارجي: {num(n(2 * ad_r))} مم",
        f"ثقب برغي المحور: قطر {num(8.4)}، وجيب سداسي {num(13.4)} مم بعمق {num(5.8)} لراس البرغي",
        f"ثقبين قطر {num(3.4)} لتثبيت الغطاء، بينهم {num(50)} مم",
        f"السكّة المخروطية: عرضها {num(12)} من تحت و{num(8)} من فوق، ارتفاعها {num(8)} وطولها {num(n(G['RAIL_X1']))} مم",
        f"ثقب برغي المسطرة في السكّة: قطر {num(3.4)} (البرغي M4 يفتح سنّه في البلاستيك)",
    ]),
    "ruler": ("تنطبع على ظهرها والحافة المستقيمة لفوق. وحدة لكل مقاس.", [
        f"الطول الكلي: {num(n(A.jar_len - 5))} مم",
        f"حافة الضبط: سمكها {num(4.7)} مم، وتقعد فوق سطح العبوة بفراغ {num(0.3)} مم",
        f"الحاجز الجانبي: طوله {num(30)} مم، قايم على الحافة، وجهه على بعد {num(n(G['LBL_X0']))} مم من وجه الغطاء",
        f"ثقب البرغي: قطر {num(4.4)} مم",
    ]),
    "crank": ("تنطبع والمقبض لفوق.", [
        f"من مركز المحور لمركز المقبض: {num(60)} مم",
        f"ثقب المحور: قطر {num(8.4)}، وجيب سداسي {num(13.4)} مم بعمق {num(6.5)} للصامولة",
        f"المقبض: قطر {num(16)} وطول {num(40)} مم",
    ]),
    "squeegee_arm": ("تنطبع مقلوبة، وجه الشق لفوق.", [
        f"ثقبين المفصل: قطر {num(5.2)} مم",
        f"من المفصل لخط القومة: {num(n(-G['ARM_PIVOT_Y']))} مم",
        f"شق القومة: عرض {num(3.4)}، عمق {num(12)}، طول {num(n(G['BLADE_X1'] - G['BLADE_X0'] + 2))} مم",
        f"ثقبين قطر {num(3.2)} لبراغي شد القومة",
    ]),
}

part_pages, rows = [], []
for i, (name, (shape, colour, printed, label)) in enumerate([kv for kv in PARTS.items() if kv[1][2]], 1):
    key = next(k for k in DETAILS if name.startswith(k))
    note, items = DETAILS[key]
    views, bb = drawings(name, shape)
    size = num(f"{n(bb.xlen)} × {n(bb.ylen)} × {n(bb.zlen)}")
    rows.append(f'<tr><td class="num">{i}</td><td><span class="chip" style="background:{colour}"></span>{label}</td>'
                f'<td class="num">{name}.stl</td><td>{size}</td><td>{note}</td></tr>')
    part_pages.append(f'''<section class="part">
  <h2><span class="tag">{num(i)}</span>{label}</h2>
  <p class="file">الملف: {num(name + ".stl")} · المقاس الكلي: {size} مم</p>
  <div class="views">{views}</div>
  <div class="cols"><div><h3>المقاسات المهمة</h3><ul>{"".join(f"<li>{x}</li>" for x in items)}</ul></div>
  <div><h3>الطباعة</h3><p>{note}</p></div></div>
</section>''')

USE_STEPS = [
    "ادفع الاستيكر في زاوية المسطرة: طرفه على حافة المسطرة، وجنبه على الحاجز الجانبي.",
    "اكبس أول شريط جنب المسطرة بإصبعك، ونزّل ذراع القومة على العبوة.",
    "دوّر المانيفيلا على مهل. المسطرة تلف مع العبوة والقومة تكبس الاستيكر وتدفع الهواء قدامها.",
    "قبل ما يوصل آخر الاستيكر للقومة، فك البرغي وارفع المسطرة.",
    "كمّل اللفة باش القومة تكبس آخر الاستيكر، وييجي على أوله.",
    "ارفع الذراع، فك العبوة من الغطاء، رجّع المسطرة، وركّب العبوة اللي بعدها.",
]
use_html = "".join(f'<figure class="step"><img src="step{i}.png" alt=""><figcaption><b>{num(i + 1)}</b> {s}</figcaption></figure>'
                   for i, s in enumerate(USE_STEPS))

html = f'''<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@400;500;700&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
@page {{ size: A4; margin: 16mm 15mm 16mm }}
* {{ box-sizing: border-box }}
body {{ font-family: "IBM Plex Sans Arabic", "DejaVu Sans", sans-serif; font-size: 10.5pt; line-height: 1.7; color: #1c2730; margin: 0 }}
.num {{ font-family: "IBM Plex Mono", monospace; direction: ltr; unicode-bidi: isolate; font-size: .95em }}
h1 {{ font-size: 24pt; line-height: 1.3; margin: 0 0 4mm }}
h2 {{ font-size: 15pt; margin: 0 0 3mm; display: flex; align-items: center; gap: 3mm }}
h3 {{ font-size: 11pt; margin: 0 0 1.5mm; color: #b8611a }}
p {{ margin: 0 0 2.5mm }}
ul, ol {{ margin: 0; padding-inline-start: 5mm }} li {{ margin-bottom: 1.2mm }}
section {{ break-before: page }} section.first {{ break-before: auto }}
.lead {{ font-size: 12pt; color: #44525d; max-width: 150mm }}
.hero {{ width: 100%; border: .3mm solid #cdd5db; border-radius: 2mm; margin: 5mm 0 }}
.warn {{ border-inline-start: 1.2mm solid #b8611a; padding: 2mm 4mm; background: #f6efe6; margin: 4mm 0 }}
table {{ border-collapse: collapse; width: 100%; font-size: 9.5pt; margin-bottom: 6mm }}
th, td {{ text-align: start; padding: 1.8mm 2mm; border-bottom: .2mm solid #cdd5db; vertical-align: top }}
th {{ color: #5a6873; font-weight: 500 }}
.chip {{ display: inline-block; width: 3mm; height: 3mm; border-radius: .5mm; margin-inline-end: 2mm; border: .2mm solid #8a959e; vertical-align: middle }}
.tag {{ display: inline-flex; width: 8mm; height: 8mm; align-items: center; justify-content: center; background: #1c2730; color: #fff; border-radius: 50%; font-size: 11pt }}
.file {{ color: #5a6873 }}
.views {{ display: grid; grid-template-columns: 1fr 1fr; gap: 3mm; margin: 3mm 0 5mm }}
.view {{ margin: 0; border: .2mm solid #cdd5db; border-radius: 1.5mm; padding: 2mm; text-align: center; break-inside: avoid }}
.view svg {{ width: 100%; height: 58mm }}
.view figcaption {{ font-size: 9pt; color: #44525d }}
.cols {{ display: grid; grid-template-columns: 3fr 2fr; gap: 8mm }}
.steps {{ display: grid; grid-template-columns: 1fr 1fr; gap: 4mm }}
.step {{ margin: 0; break-inside: avoid }} .step img {{ width: 100%; border: .2mm solid #cdd5db; border-radius: 1.5mm; display: block }}
.step figcaption {{ font-size: 9.5pt; padding-top: 1mm }} .step b {{ color: #b8611a; margin-inline-end: 1.5mm }}
.asm li {{ margin-bottom: 2mm }}
</style></head><body>

<section class="first">
  <h1>مكينة تركيب الاستيكرات على العبوة</h1>
  <p class="lead">دليل التصنيع والتركيب والتشغيل. المكينة يدوية وتنطبع بطابعة ثلاثية الأبعاد: العبوة تتربّط في غطاها وتدور بمانيفيلا، مسطرة ثابتة تلف معاها تضبط بداية الاستيكر، وقومة من فوق تكبسه وتطرد الهواء.</p>
  <img class="hero" src="cover.png" alt="">
  <div class="warn">
    <p><b>قبل ما تطبع:</b> هذي نسخة أولى ما انطبعتش ولا تجرّبت. المقاسات اللي تحت مقدّرة من الصور، مش مقاسة بالقدمة. قيس عبوتك وغطاها، ولو فيه فرق عاود بناء الملفات بالمقاسات الصح قبل الطباعة.</p>
  </div>
  <table>
    <thead><tr><th>المقاس المستعمل في هذا الدليل</th><th>القيمة (مم)</th></tr></thead>
    <tbody>
      <tr><td>قطر جسم العبوة</td><td class="num">{n(A.jar_d)}</td></tr>
      <tr><td>طول العبوة مع الغطاء</td><td class="num">{n(A.jar_len)}</td></tr>
      <tr><td>قطر الغطاء الخارجي</td><td class="num">{n(A.lid_d)}</td></tr>
      <tr><td>ارتفاع الغطاء</td><td class="num">{n(A.lid_h)}</td></tr>
      <tr><td>بعد حافة الاستيكر عن وجه الغطاء</td><td class="num">{n(G["LBL_X0"])}</td></tr>
    </tbody>
  </table>
</section>

<section>
  <h2>القطع اللي تنطبع</h2>
  <table>
    <thead><tr><th>#</th><th>القطعة</th><th>الملف</th><th>المقاس (مم)</th><th>وضع الطباعة</th></tr></thead>
    <tbody>{"".join(rows)}</tbody>
  </table>
  <p>اقتراح لإعدادات الطباعة: PLA أو PETG، سمك طبقة {num(0.2)} مم، {num(4)} جدران، وحشو {num("30%")}. المسطرة والكأس اطبعهم على مهل لأن دقتهم هي اللي تحدد استقامة الاستيكر.</p>
  <p>القاعدة {num("185 × 165")} مم وارتفاعها بالأعمدة {num(n(PIV_Z + 18))} مم. تأكد إن طابعتك تسعها.</p>

  <h2 style="margin-top:8mm">القطع اللي تشريها</h2>
  <table>
    <thead><tr><th>القطعة</th><th>العدد</th><th>وين تتركّب</th></tr></thead>
    <tbody>
      <tr><td>رولمان بلي {num(608)} ({num("8×22×7")})</td><td class="num">2</td><td>في حامل المحور، واحد من كل جهة</td></tr>
      <tr><td>برغي {num("M8×60")} براس سداسي، مع صامولتين ووردة</td><td class="num">1</td><td>المحور: راسه في الكأس وطرفه في المانيفيلا</td></tr>
      <tr><td>قضيب مسنن {num("M5")} بطول {num(125)} مع صامولتين</td><td class="num">1</td><td>مفصل ذراع القومة بين العمودين</td></tr>
      <tr><td>براغي {num("M4×16")} بصواميل</td><td class="num">4</td><td>تثبيت حامل المحور في القاعدة</td></tr>
      <tr><td>برغي {num("M4×12")} براس يتدوّر باليد</td><td class="num">1</td><td>يشد المسطرة على سكّتها</td></tr>
      <tr><td>شريط مطاط أو سيليكون سمك {num(3)}، عرض {num(35)}، طول {num(n(G['BLADE_X1'] - G['BLADE_X0']))} (قومة زجاج)</td><td class="num">1</td><td>يتدخّل في شق الذراع</td></tr>
      <tr><td>براغي {num("M3×20")} بصواميل</td><td class="num">2</td><td>يشدّوا القومة في الذراع</td></tr>
      <tr><td>براغي صغار {num(3)} مم بطول {num(8)}</td><td class="num">2</td><td>تثبيت غطاء العبوة في الكأس</td></tr>
      <tr><td>غطاء عبوة زايد</td><td class="num">1</td><td>يقعد مثبّت في الكأس على طول</td></tr>
    </tbody>
  </table>
</section>

{"".join(part_pages)}

<section>
  <h2>التركيب</h2>
  <img class="hero" src="exploded.png" alt="" style="margin-top:0">
  <ol class="asm">
    <li><b>الرولمانات:</b> اكبس رولمان {num(608)} في كل جيب من جيبين حامل المحور لين يقعد مع الوجه.</li>
    <li><b>الحامل على القاعدة:</b> ثبّت حامل المحور بأربع براغي {num("M4×16")} من تحت القاعدة، والصواميل من فوق.</li>
    <li><b>البرغي في الكأس:</b> دخّل برغي {num("M8×60")} من داخل الكأس لين راسه يقعد في الجيب السداسي. هذا لازم يصير قبل الغطاء، لأن الغطاء يغطيه.</li>
    <li><b>الغطاء في الكأس:</b> حط غطاء العبوة في الكأس وفتحته لبرّا، وثبّته ببرغيين صغار من داخل الغطاء في الثقبين.</li>
    <li><b>المحور:</b> دخّل البرغي في الرولمانين من جهة الكأس. من الجهة الثانية حط الوردة والصامولة الأولى وزيّرها لين يروح اللعب والكأس مازال يدور بسهولة.</li>
    <li><b>المانيفيلا:</b> دخّل المانيفيلا على البرغي، وحط الصامولة الثانية في جيبها السداسي وزيّرها على الأولى.</li>
    <li><b>القومة:</b> دخّل شريط المطاط في شق الذراع لين يطلع منه حوالي {num(n(G['H_Z0'] - G['AX_H'] - G['REF_JAR_R']))} مم، وشدّه ببرغيين {num("M3×20")}.</li>
    <li><b>الذراع:</b> حط الذراع بين العمودين، دخّل قضيب {num("M5")} في الثقوب، وسكّر بصامولة من كل جهة بلا ما تزيّر، باش الذراع يطلع وينزل بحرية.</li>
    <li><b>المسطرة:</b> اكبسها على السكّة المخروطية في الكأس وشدّها ببرغي {num("M4×12")}.</li>
  </ol>
  <h3 style="margin-top:5mm">فحص قبل أول استعمال</h3>
  <ul>
    <li>ربّط عبوة ودوّرها لفة كاملة والمسطرة مركّبة. ما لازمش تحك في العبوة ولا تخبط في شي.</li>
    <li>قيس الفراغ بين حافة المسطرة وجدار العبوة عند الغطاء وعند القاع. لازم يكون نفسه، ولو فيه فرق فالعبوة مش قاعدة مستقيمة في الغطاء.</li>
    <li>نزّل الذراع وشوف القومة تلمس العبوة على طولها كله.</li>
  </ul>
</section>

<section>
  <h2>طريقة الاستعمال</h2>
  <div class="steps">{use_html}</div>
  <div class="warn" style="margin-top:5mm">
    <p><b>ليش المسطرة تترفع:</b> الاستيكر يلف العبوة كلها، وآخره ينزل في نفس المكان اللي قاعدة فيه المسطرة. وقت ما ترفعها يكون أغلب الاستيكر لاصق والقومة شادّاته، فما يتحركش.</p>
    <p><b>باش الآخر ييجي على الأول:</b> لازم الاستيكر نفسه مقصوص قايم، والعبوة جدارها مستقيم مش مخروطي. باقي الاستيكر يكون في يدك وهو يتلف، فشدّه مستقيم وبلا قوة.</p>
  </div>
</section>
</body></html>'''
open(os.path.join(WORK, "guide.html"), "w").write(html)

NODE = r'''
const {chromium} = require('playwright');
const [preview, work, pdf] = process.argv.slice(2);
(async () => {
  const b = await chromium.launch({args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist']});
  const p = await b.newPage({viewport: {width: 900, height: 900}, deviceScaleFactor: 2, colorScheme: 'light'});
  await p.goto('file://' + preview); await p.waitForTimeout(2500);
  const shot = async (name) => { await p.waitForTimeout(350); await p.locator('#view').screenshot({path: work + '/' + name}); };
  const explode = v => p.evaluate(v => { const e = document.getElementById('explode'); e.value = v; e.dispatchEvent(new Event('input')); }, v);
  await p.evaluate(() => window.__seek(2.3)); await shot('cover.png');
  const box = await p.locator('#view').boundingBox();
  const zoom = async (dy, k) => { await p.mouse.move(box.x + box.width / 2, box.y + box.height / 2); for (let i = 0; i < k; i++) await p.mouse.wheel(0, dy); };
  await zoom(300, 6); await explode(1); await shot('exploded.png'); await explode(0);
  await p.reload(); await p.waitForTimeout(2500);
  const times = [1.5, 2.3, 4.6, 7.5, 8.8, 9.8];
  for (let i = 0; i < times.length; i++) { await p.evaluate(s => window.__seek(s), times[i]); await shot('step' + i + '.png'); }
  const d = await b.newPage();
  await d.goto('file://' + work + '/guide.html'); await d.evaluate(() => document.fonts.ready); await d.waitForTimeout(800);
  await d.pdf({path: pdf, format: 'A4', printBackground: true, preferCSSPageSize: true});
  await b.close();
})();
'''
js = os.path.join(WORK, "render.js")
open(js, "w").write(NODE)
env = dict(os.environ)
env["NODE_PATH"] = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip()
subprocess.run(["node", js, os.path.join(HERE, "preview.html"), WORK, OUT_PDF], check=True, env=env)
print("wrote", OUT_PDF)

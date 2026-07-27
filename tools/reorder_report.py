"""Material reorder-point report — Odoo sales exploded through BOMs.

Pipeline:
  1. Sales velocity per finished product  (Odoo `sale.order.line`, last N days)
  2. Explode each product's demand through its BOM (`mrp.bom` / `mrp.bom.line`)
     to get daily demand for every raw material.
  3. Reorder point per material:
        safety_stock  = daily_demand * safety_days
        reorder_point = daily_demand * lead_time_days + safety_stock
     (lead time from the material's supplier info; falls back to a default.)
  4. Compare to current on-hand (`stock.quant`) → status + suggested order qty.
  5. Render a self-contained HTML dashboard.

Runs against live Odoo when configured (ODOO_* env vars); otherwise it uses a
bundled sample dataset so it always produces a report.

Usage:
    python3 tools/reorder_report.py            # writes reorder_report.html
    python3 tools/reorder_report.py out.html   # custom output path
"""

from __future__ import annotations

import html
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone

# Make `import auria` work when run as a plain script from the repo root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SALES_WINDOW_DAYS = 90     # how far back to measure sales velocity
SAFETY_DAYS = 7            # buffer stock expressed in days of demand
REVIEW_DAYS = 7            # ordering-cycle coverage added to a suggested order
DEFAULT_LEAD_DAYS = 14     # fallback material lead time (Auria's known supplier lead time)


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #
@dataclass
class MaterialRow:
    code: str
    name: str
    uom: str
    daily_demand: float
    lead_time_days: float
    safety_stock: float
    reorder_point: float
    on_hand: float
    status: str            # REORDER | LOW | OK
    suggested_order: float
    drivers: list[tuple[str, float]] = field(default_factory=list)


_STATUS_ORDER = {"REORDER": 0, "LOW": 1, "OK": 2}


# --------------------------------------------------------------------------- #
# Core computation (pure — unit-testable, no Odoo needed)
# --------------------------------------------------------------------------- #
def compute_rows(
    products: dict,       # pid -> {"name": str, "daily_velocity": float}
    boms: dict,           # pid -> [{"material": mid, "qty": float}]
    materials: dict,      # mid -> {"code": str, "name": str, "uom": str}
    lead_times: dict,     # mid -> days
    on_hand: dict,        # mid -> qty
    *,
    safety_days: float = SAFETY_DAYS,
    review_days: float = REVIEW_DAYS,
) -> list[MaterialRow]:
    demand: dict[str, float] = {}
    drivers: dict[str, list[tuple[str, float]]] = {}

    for pid, p in products.items():
        vel = float(p.get("daily_velocity", 0.0))
        if vel <= 0:
            continue
        for comp in boms.get(pid, []):
            mid, qty = comp["material"], float(comp["qty"])
            contrib = vel * qty
            demand[mid] = demand.get(mid, 0.0) + contrib
            drivers.setdefault(mid, []).append((p["name"], contrib))

    rows: list[MaterialRow] = []
    for mid, m in materials.items():
        dd = demand.get(mid, 0.0)
        lt = float(lead_times.get(mid, DEFAULT_LEAD_DAYS))
        ss = dd * safety_days
        rop = dd * lt + ss
        oh = float(on_hand.get(mid, 0.0))

        if oh <= rop:
            status = "REORDER"
        elif oh <= rop * 1.25:
            status = "LOW"
        else:
            status = "OK"

        # Order up to cover lead time + safety + one review cycle.
        target = dd * (lt + safety_days + review_days)
        suggested = max(round(target - oh), 0) if status != "OK" else 0

        top_drivers = sorted(drivers.get(mid, []), key=lambda d: d[1], reverse=True)[:3]
        rows.append(MaterialRow(
            code=m.get("code", ""), name=m["name"], uom=m.get("uom", ""),
            daily_demand=round(dd, 3), lead_time_days=lt,
            safety_stock=round(ss, 1), reorder_point=round(rop, 1),
            on_hand=round(oh, 1), status=status, suggested_order=suggested,
            drivers=[(n, round(c, 2)) for n, c in top_drivers],
        ))

    rows.sort(key=lambda r: (_STATUS_ORDER[r.status], -r.reorder_point))
    return rows


# --------------------------------------------------------------------------- #
# Live Odoo fetch (guarded — returns None if Odoo isn't configured/reachable)
# --------------------------------------------------------------------------- #
def fetch_from_odoo():
    try:
        from auria.settings import settings
        if not settings.odoo_enabled:
            return None
        from auria.odoo_server import OdooClient
        from datetime import timedelta

        client = OdooClient()
        since = (datetime.now(timezone.utc) - timedelta(days=SALES_WINDOW_DAYS)).strftime("%Y-%m-%d")

        # 1) Sales velocity per finished product (confirmed/done orders in window).
        lines = client.execute(
            "sale.order.line", "search_read",
            [[["state", "in", ["sale", "done"]], ["order_id.date_order", ">=", since]]],
            {"fields": ["product_id", "product_uom_qty"]},
        )
        sold: dict[int, float] = {}
        names: dict[int, str] = {}
        for ln in lines:
            if not ln.get("product_id"):
                continue
            pid, pname = ln["product_id"][0], ln["product_id"][1]
            sold[pid] = sold.get(pid, 0.0) + float(ln.get("product_uom_qty", 0.0))
            names[pid] = pname
        products = {pid: {"name": names[pid], "daily_velocity": qty / SALES_WINDOW_DAYS}
                    for pid, qty in sold.items()}

        # 2) BOMs for those products.
        boms: dict[int, list] = {}
        materials: dict[int, dict] = {}
        for pid in list(products):
            bom_ids = client.execute("mrp.bom", "search",
                                     [["|", ["product_id", "=", pid], ["product_tmpl_id.product_variant_ids", "=", pid]]],
                                     {"limit": 1})
            if not bom_ids:
                continue
            bom = client.execute("mrp.bom", "read", [bom_ids],
                                 {"fields": ["product_qty", "bom_line_ids"]})[0]
            per = float(bom.get("product_qty", 1.0)) or 1.0
            bl = client.execute("mrp.bom.line", "read", [bom["bom_line_ids"]],
                                {"fields": ["product_id", "product_qty"]})
            comps = []
            for line in bl:
                if not line.get("product_id"):
                    continue
                mid, mname = line["product_id"][0], line["product_id"][1]
                comps.append({"material": mid, "qty": float(line["product_qty"]) / per})
                materials.setdefault(mid, {"code": "", "name": mname, "uom": ""})
            boms[pid] = comps

        mids = list(materials)
        if mids:
            prods = client.execute("product.product", "read", [mids],
                                   {"fields": ["default_code", "uom_id", "seller_ids"]})
            for pr in prods:
                m = materials[pr["id"]]
                m["code"] = pr.get("default_code") or ""
                m["uom"] = (pr.get("uom_id") or ["", ""])[1] if pr.get("uom_id") else ""

        # 3) Lead times from supplier info; 4) on-hand from stock.quant.
        lead_times: dict[int, float] = {}
        for mid in mids:
            sellers = client.execute("product.supplierinfo", "search_read",
                                     [[["product_tmpl_id.product_variant_ids", "=", mid]]],
                                     {"fields": ["delay"], "limit": 1})
            if sellers:
                lead_times[mid] = float(sellers[0].get("delay") or DEFAULT_LEAD_DAYS)
        on_hand: dict[int, float] = {}
        if mids:
            quants = client.execute("stock.quant", "search_read",
                                    [[["product_id", "in", mids], ["location_id.usage", "=", "internal"]]],
                                    {"fields": ["product_id", "quantity"]})
            for q in quants:
                pid = q["product_id"][0]
                on_hand[pid] = on_hand.get(pid, 0.0) + float(q.get("quantity", 0.0))

        return products, boms, materials, lead_times, on_hand
    except Exception as exc:  # noqa: BLE001 - any failure -> fall back to sample
        print(f"[reorder] live Odoo fetch unavailable ({type(exc).__name__}: {exc}); using sample data",
              file=sys.stderr)
        return None


# --------------------------------------------------------------------------- #
# Sample dataset (a cider maker) — so the report renders without Odoo
# --------------------------------------------------------------------------- #
def sample_data():
    products = {
        "P1": {"name": "Cider — Original 500ml", "daily_velocity": 120.0},
        "P2": {"name": "Cider — Dry 500ml", "daily_velocity": 80.0},
        "P3": {"name": "Cider — Berry 330ml", "daily_velocity": 60.0},
    }
    materials = {
        "M1": {"code": "RM-APPLE", "name": "Apple concentrate", "uom": "L"},
        "M2": {"code": "RM-BTL500", "name": "Bottle 500ml", "uom": "unit"},
        "M3": {"code": "RM-BTL330", "name": "Bottle 330ml", "uom": "unit"},
        "M4": {"code": "RM-CAP", "name": "Crown cap", "uom": "unit"},
        "M5": {"code": "RM-LABEL", "name": "Label", "uom": "unit"},
        "M6": {"code": "RM-SUGAR", "name": "Sugar", "uom": "kg"},
        "M7": {"code": "RM-CO2", "name": "CO2", "uom": "kg"},
        "M8": {"code": "RM-BOX", "name": "Carton box", "uom": "unit"},
    }
    boms = {
        "P1": [{"material": "M1", "qty": 0.30}, {"material": "M2", "qty": 1}, {"material": "M4", "qty": 1},
               {"material": "M5", "qty": 1}, {"material": "M6", "qty": 0.02}, {"material": "M7", "qty": 0.008},
               {"material": "M8", "qty": 1 / 12}],
        "P2": [{"material": "M1", "qty": 0.32}, {"material": "M2", "qty": 1}, {"material": "M4", "qty": 1},
               {"material": "M5", "qty": 1}, {"material": "M6", "qty": 0.005}, {"material": "M7", "qty": 0.008},
               {"material": "M8", "qty": 1 / 12}],
        "P3": [{"material": "M1", "qty": 0.18}, {"material": "M3", "qty": 1}, {"material": "M4", "qty": 1},
               {"material": "M5", "qty": 1}, {"material": "M6", "qty": 0.03}, {"material": "M7", "qty": 0.006},
               {"material": "M8", "qty": 1 / 24}],
    }
    lead_times = {"M1": 14, "M2": 21, "M3": 21, "M4": 10, "M5": 7, "M6": 5, "M7": 3, "M8": 12}
    on_hand = {"M1": 900, "M2": 8000, "M3": 1500, "M4": 5000, "M5": 3000, "M6": 200, "M7": 15, "M8": 500}
    return products, boms, materials, lead_times, on_hand


# --------------------------------------------------------------------------- #
# HTML rendering (self-contained, responsive, light/dark)
# --------------------------------------------------------------------------- #
def _fmt(n: float) -> str:
    return f"{n:,.0f}" if abs(n) >= 100 or n == int(n) else f"{n:,.2f}"


def render_html(rows: list[MaterialRow], *, live: bool) -> str:
    reorder = [r for r in rows if r.status == "REORDER"]
    low = [r for r in rows if r.status == "LOW"]
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    badge = ("LIVE — Odoo", "#1a7f37") if live else ("SAMPLE DATA — connect Odoo for live", "#9a6700")

    body_rows = []
    for r in rows:
        color = {"REORDER": "reorder", "LOW": "low", "OK": "ok"}[r.status]
        drivers = ", ".join(f"{html.escape(n)} ({_fmt(c)})" for n, c in r.drivers) or "—"
        order = f"<strong>{_fmt(r.suggested_order)}</strong> {html.escape(r.uom)}" if r.suggested_order else "—"
        body_rows.append(f"""
      <tr class="{color}">
        <td class="mat"><span class="code">{html.escape(r.code or '')}</span>{html.escape(r.name)}</td>
        <td class="num">{_fmt(r.daily_demand)} <span class="u">{html.escape(r.uom)}/day</span></td>
        <td class="num">{_fmt(r.lead_time_days)}d</td>
        <td class="num">{_fmt(r.safety_stock)}</td>
        <td class="num rop">{_fmt(r.reorder_point)}</td>
        <td class="num">{_fmt(r.on_hand)}</td>
        <td><span class="pill {color}">{r.status}</span></td>
        <td class="num">{order}</td>
        <td class="drivers">{drivers}</td>
      </tr>""")

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Auria — Material Reorder Points</title>
<style>
  :root {{
    --bg:#f6f7f9; --card:#fff; --ink:#1c2530; --muted:#5b6672; --line:#e5e9ee;
    --reorder:#b42318; --reorder-bg:#fff1f0; --low:#9a6700; --low-bg:#fff8e6;
    --ok:#1a7f37; --ok-bg:#eafbf0; --accent:#2b6cb0;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg:#0e1116; --card:#161b22; --ink:#e6edf3; --muted:#9aa7b4; --line:#2a313a;
      --reorder:#ff6b5e; --reorder-bg:#2a1613; --low:#e3b341; --low-bg:#2a2312;
      --ok:#3fb950; --ok-bg:#12241a; --accent:#6cb6ff; }}
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink);
    font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }}
  .wrap {{ max-width:1180px; margin:0 auto; padding:28px 20px 60px; }}
  header {{ display:flex; flex-wrap:wrap; align-items:baseline; gap:12px; margin-bottom:6px; }}
  h1 {{ font-size:22px; margin:0; }}
  .badge {{ font-size:12px; font-weight:600; color:#fff; padding:3px 10px; border-radius:999px; }}
  .sub {{ color:var(--muted); font-size:13px; margin:2px 0 22px; }}
  .kpis {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:14px; margin-bottom:24px; }}
  .kpi {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:16px 18px; }}
  .kpi .v {{ font-size:28px; font-weight:700; }}
  .kpi .l {{ color:var(--muted); font-size:13px; }}
  .kpi.reorder .v {{ color:var(--reorder); }} .kpi.low .v {{ color:var(--low); }} .kpi.ok .v {{ color:var(--ok); }}
  .tablecard {{ background:var(--card); border:1px solid var(--line); border-radius:12px; overflow:hidden; }}
  .scroll {{ overflow-x:auto; }}
  table {{ border-collapse:collapse; width:100%; min-width:820px; }}
  th, td {{ padding:11px 14px; text-align:left; border-bottom:1px solid var(--line); white-space:nowrap; }}
  th {{ font-size:12px; text-transform:uppercase; letter-spacing:.04em; color:var(--muted); background:var(--card); position:sticky; top:0; }}
  td.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
  td.rop {{ font-weight:600; }}
  .u {{ color:var(--muted); font-size:11px; }}
  .mat .code {{ display:block; font-size:11px; color:var(--muted); }}
  .drivers {{ color:var(--muted); font-size:12px; white-space:normal; min-width:220px; }}
  .pill {{ font-size:11px; font-weight:700; padding:3px 9px; border-radius:999px; }}
  .pill.reorder {{ color:var(--reorder); background:var(--reorder-bg); }}
  .pill.low {{ color:var(--low); background:var(--low-bg); }}
  .pill.ok {{ color:var(--ok); background:var(--ok-bg); }}
  tr.reorder td {{ background:color-mix(in srgb, var(--reorder-bg) 45%, transparent); }}
  .method {{ color:var(--muted); font-size:12.5px; margin-top:22px; line-height:1.6; }}
  code {{ background:var(--line); padding:1px 5px; border-radius:5px; }}
</style>
</head>
<body>
  <div class="wrap">
    <header>
      <h1>Material Reorder Points</h1>
      <span class="badge" style="background:{badge[1]}">{badge[0]}</span>
    </header>
    <div class="sub">Sales exploded through BOMs · {SALES_WINDOW_DAYS}-day sales window · generated {generated}</div>

    <div class="kpis">
      <div class="kpi"><div class="v">{len(rows)}</div><div class="l">materials tracked</div></div>
      <div class="kpi reorder"><div class="v">{len(reorder)}</div><div class="l">reorder now</div></div>
      <div class="kpi low"><div class="v">{len(low)}</div><div class="l">running low</div></div>
      <div class="kpi ok"><div class="v">{len(rows) - len(reorder) - len(low)}</div><div class="l">healthy</div></div>
    </div>

    <div class="tablecard"><div class="scroll">
    <table>
      <thead><tr>
        <th>Material</th><th>Daily use</th><th>Lead time</th><th>Safety stock</th>
        <th>Reorder point</th><th>On hand</th><th>Status</th><th>Suggested order</th><th>Driven by (units/day)</th>
      </tr></thead>
      <tbody>{''.join(body_rows)}
      </tbody>
    </table>
    </div></div>

    <p class="method">
      <strong>Method.</strong> Daily material demand = Σ over finished goods
      (product sales velocity × quantity of the material in its BOM).
      <code>safety stock = daily demand × {SAFETY_DAYS} days</code>;
      <code>reorder point = daily demand × lead time + safety stock</code>.
      Suggested order covers lead time + {SAFETY_DAYS}d safety + {REVIEW_DAYS}d review cycle, minus on-hand.
      Lead times come from each material's Odoo supplier info (default {DEFAULT_LEAD_DAYS}d).
    </p>
  </div>
</body>
</html>"""


def main() -> None:
    out = sys.argv[1] if len(sys.argv) > 1 else "reorder_report.html"
    data = fetch_from_odoo()
    live = data is not None
    if not live:
        data = sample_data()
    rows = compute_rows(*data)
    with open(out, "w", encoding="utf-8") as f:
        f.write(render_html(rows, live=live))
    reorder = sum(1 for r in rows if r.status == "REORDER")
    print(f"Wrote {out} — {len(rows)} materials, {reorder} to reorder "
          f"({'LIVE Odoo' if live else 'SAMPLE data'}).")


if __name__ == "__main__":
    main()

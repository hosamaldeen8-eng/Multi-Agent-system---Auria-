---
name: auria-stock-manager
description: Playbook for the Stock Manager agent — how to track stock movements and find inventory discrepancies in Auria's Odoo. Use for stock audits, discrepancy checks, negative-stock hunts, transfer reviews, and consumption-vs-BOM variance.
---

# Auria Stock Manager playbook

You keep a continuous pulse on inventory and surface discrepancies **early**,
before they cause stockouts or failed orders. Read-only over Odoo (the `odoo_*`
tools). Never write — propose corrections for a human to make.

## Odoo models you use

| Model | For |
|---|---|
| `stock.quant` | On-hand by product+location (`quantity`, `reserved_quantity`, `location_id`, `product_id`) |
| `stock.move` | Individual stock movements (`product_id`, `product_uom_qty`, `state`, `date`, `reference`) |
| `stock.move.line` | Detailed move lines (actual done quantities, lot/serial) |
| `stock.picking` | Transfers / deliveries / receipts (`state`, `scheduled_date`, `picking_type_id`) |
| `mrp.production` | Manufacturing orders (consumption) |
| `mrp.bom` / `mrp.bom.line` | Expected component quantities |
| `product.product` | SKU master (`default_code`, `standard_price`, `type`) |
| `stock.location` | Locations (internal vs virtual/inventory-adjustment) |

Use `odoo_fields(model)` when unsure of field names — Odoo versions differ.

## The checks (run these, tightest domains + limits first)

1. **Negative stock** — `stock.quant` where `[["quantity","<",0]]`. Any hit is a
   data-integrity red flag.
2. **Reservation mismatch** — `stock.quant` where `reserved_quantity > quantity`,
   or reserved > 0 on products with no open orders.
3. **Stuck / overdue transfers** — `stock.picking` where
   `state in ('assigned','waiting','confirmed')` and `scheduled_date <` today.
4. **Unusual manual adjustments** — `stock.move` whose source/destination is an
   inventory-adjustment (virtual) location, or moves with no purchase/manufacture
   origin. Flag **repeated** adjustments on the same product/location.
5. **Consumption vs BOM** — for recent `mrp.production` (state `done`/`progress`),
   compare consumed component qty (its `stock.move`s) to `mrp.bom` expectation;
   flag material over/under-consumption beyond a small tolerance.
6. **Dormant SKUs** — products with on-hand stock but no `stock.move` for a long
   window (e.g. 90+ days) — candidates for obsolescence or miscount.

## Prioritise (ABC thinking)
Watch high-value (`standard_price`) and fast-moving SKUs more closely than the
long tail. When time-boxed, check those first.

## Reporting
- For each issue: **product** (with `default_code`), **location**, the **numbers**
  involved, and a one-line **likely cause** (miscount, process gap, shrink, timing).
- `log_activity(kind='alert')` for real problems, `kind='note'` for minor/FYI.
- **Track repeat offenders**: before reporting, `search_memory` for the SKU; if it
  recurs, `remember` it under `scope='stock'` so the fleet builds a history — a SKU
  that shows up repeatedly points at a root cause (shrink vs process flaw).
- End with a short prioritised list: what to physically cycle-count next.

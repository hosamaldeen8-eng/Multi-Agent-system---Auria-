"""Odoo connection diagnostic for the Auria fleet.

Run after setting ODOO_URL / ODOO_DB / ODOO_USERNAME / ODOO_API_KEY in .env.
It checks, in order: host reachability, authentication, and a few read-only
sample queries — so you can see live data actually flowing before relying on it.

    python3 tools/odoo_check.py
"""

from __future__ import annotations

import os
import sys
import xmlrpc.client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auria.settings import settings  # noqa: E402


def _ok(msg: str) -> None:
    print(f"  ✓ {msg}")


def _fail(msg: str) -> None:
    print(f"  ✗ {msg}")


def main() -> int:
    print(f"Odoo target: {settings.odoo_url}  db={settings.odoo_db}  user={settings.odoo_username or '(unset)'}")

    # 0) Config present?
    missing = [n for n, v in (
        ("ODOO_URL", settings.odoo_url), ("ODOO_DB", settings.odoo_db),
        ("ODOO_USERNAME", settings.odoo_username), ("ODOO_API_KEY", settings.odoo_api_key),
    ) if not v]
    if missing:
        _fail(f"Missing in .env: {', '.join(missing)}")
        return 1

    # 1) Reachability
    try:
        common = xmlrpc.client.ServerProxy(f"{settings.odoo_url}/xmlrpc/2/common")
        ver = common.version()
        _ok(f"Reachable — Odoo {ver.get('server_version')}")
    except Exception as exc:  # noqa: BLE001
        _fail(f"Cannot reach host: {type(exc).__name__}: {exc}")
        return 1

    # 2) Authentication
    try:
        uid = common.authenticate(settings.odoo_db, settings.odoo_username, settings.odoo_api_key, {})
    except Exception as exc:  # noqa: BLE001
        _fail(f"Auth call errored: {type(exc).__name__}: {exc}")
        return 1
    if not uid:
        _fail("Authentication rejected — check ODOO_DB, ODOO_USERNAME and ODOO_API_KEY "
              "(the API key must belong to that exact user).")
        return 1
    _ok(f"Authenticated as uid={uid}")

    # 3) Sample read-only queries
    models = xmlrpc.client.ServerProxy(f"{settings.odoo_url}/xmlrpc/2/object")

    def count(model: str, domain: list | None = None) -> int:
        return models.execute_kw(settings.odoo_db, uid, settings.odoo_api_key,
                                 model, "search_count", [domain or []])

    checks = [
        ("Products (product.product)", "product.product", None),
        ("Manufacturing orders (mrp.production)", "mrp.production", None),
        ("Open MOs", "mrp.production", [["state", "not in", ["done", "cancel"]]]),
        ("BOMs (mrp.bom)", "mrp.bom", None),
        ("Stock quants (stock.quant)", "stock.quant", None),
        ("Sale order lines (sale.order.line)", "sale.order.line", None),
    ]
    any_fail = False
    for label, model, domain in checks:
        try:
            n = count(model, domain)
            _ok(f"{label}: {n:,}")
        except Exception as exc:  # noqa: BLE001
            any_fail = True
            _fail(f"{label}: {type(exc).__name__}: {exc}")

    print()
    if any_fail:
        print("Connected, but some models were not readable — the bot user may lack "
              "access rights to those apps (grant read on Inventory / Manufacturing / Sales).")
        return 2
    print("✅ Odoo is fully connected. The fleet (odoo-ops, stock-manager, reorder "
          "report) will now use live data.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Convert transactions to USD cents with exact decimal arithmetic and aggregate.

Conversion rule (task contract):
    usd_cents = Decimal(amount_cents) * Decimal(fx_rate)
    rounded to integer cents, half away from zero (ROUND_HALF_UP).
"""

import csv
import json
import sys
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

SRC = "input/transactions.csv"
DST = "aggregate.json"

HEADER = ["txn_id", "account", "date", "currency", "amount_cents", "fx_rate"]


def to_cents(amount_cents: int, fx_rate: str) -> int:
    """Exact decimal product, then round half away from zero to integer cents."""
    product = Decimal(amount_cents) * Decimal(fx_rate)
    return int(product.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def load_rows(path=SRC):
    rows = []
    # explicit UTF-8 decode, newline='' per csv module contract
    with open(path, "r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames != HEADER:
            raise SystemExit(
                "unexpected header: %r (want %r)" % (reader.fieldnames, HEADER)
            )
        for lineno, raw in enumerate(reader, start=2):
            name = raw["txn_id"]
            if name is None or name.strip() == "":
                raise SystemExit("row %d: empty txn_id" % lineno)
            try:
                amount = int(raw["amount_cents"])
            except (TypeError, ValueError):
                raise SystemExit(
                    "row %d (%s): amount_cents not an integer: %r"
                    % (lineno, name, raw["amount_cents"])
                )
            rate_s = raw["fx_rate"]
            try:
                rate = Decimal(rate_s)
            except (InvalidOperation, TypeError):
                raise SystemExit(
                    "row %d (%s): fx_rate not a decimal string: %r"
                    % (lineno, name, rate_s)
                )
            if not rate.is_finite():
                raise SystemExit("row %d (%s): fx_rate not finite: %r" % (lineno, name, rate_s))
            date = raw["date"]
            if len(date) < 7:
                raise SystemExit("row %d (%s): date too short: %r" % (lineno, name, date))
            rows.append(
                {
                    "txn_id": name,
                    "account": raw["account"],
                    "month": date[:7],
                    "usd_cents": to_cents(amount, rate_s),
                }
            )
    ids = [r["txn_id"] for r in rows]
    if len(set(ids)) != len(ids):
        raise SystemExit("txn_id not unique")
    return rows


def aggregate(rows):
    accounts = {}
    monthly = {}
    for r in rows:
        acct = accounts.setdefault(
            r["account"], {"count": 0, "usd_cents": 0, "largest_txn": None}
        )
        acct["count"] += 1
        acct["usd_cents"] += r["usd_cents"]
        mon = monthly.setdefault(r["month"], {"count": 0, "usd_cents": 0})
        mon["count"] += 1
        mon["usd_cents"] += r["usd_cents"]

    # largest_txn: max usd_cents, ties broken by smallest txn_id (lexicographic)
    best_by_acct = {}
    for r in rows:
        cur = best_by_acct.get(r["account"])
        if cur is None:
            best_by_acct[r["account"]] = r
        else:
            if r["usd_cents"] > cur["usd_cents"] or (
                r["usd_cents"] == cur["usd_cents"] and r["txn_id"] < cur["txn_id"]
            ):
                best_by_acct[r["account"]] = r
    for name, acct in accounts.items():
        acct["largest_txn"] = best_by_acct[name]["txn_id"]

    grand = sum(a["usd_cents"] for a in accounts.values())
    return {
        "accounts": {k: accounts[k] for k in sorted(accounts)},
        "monthly": {k: monthly[k] for k in sorted(monthly)},
        "grand_total_cents": grand,
    }


def main():
    rows = load_rows()
    result = aggregate(rows)
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    with open(DST, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print("wrote %s (%d rows)" % (DST, len(rows)))


if __name__ == "__main__":
    sys.exit(main())

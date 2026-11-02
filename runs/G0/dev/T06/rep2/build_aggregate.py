#!/usr/bin/env python3
"""Aggregate transactions into USD cents per account and per month.

usd_cents = round_half_away_from_zero(amount_cents * fx_rate)  # exact decimal
"""
import csv
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

BASE = Path(__file__).resolve().parent
SRC = BASE / "input" / "transactions.csv"
OUT = BASE / "aggregate.json"


def main() -> None:
    rows = []
    with SRC.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        expected = ["txn_id", "account", "date", "currency", "amount_cents", "fx_rate"]
        assert reader.fieldnames == expected, reader.fieldnames
        for r in reader:
            amount = int(r["amount_cents"])
            rate = Decimal(r["fx_rate"])
            # exact decimal product, then half-away-from-zero to integer cents
            exact = Decimal(amount) * rate
            usd = int(exact.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
            rows.append(
                {
                    "txn_id": r["txn_id"],
                    "account": r["account"],
                    "month": r["date"][:7],
                    "amount_cents": amount,
                    "fx_rate": r["fx_rate"],
                    "exact": exact,
                    "usd_cents": usd,
                }
            )

    assert len({r["txn_id"] for r in rows}) == len(rows), "txn_id not unique"

    accounts: dict[str, dict] = {}
    for r in rows:
        a = accounts.setdefault(r["account"], {"count": 0, "usd_cents": 0, "largest_txn": None})
        a["count"] += 1
        a["usd_cents"] += r["usd_cents"]
        best = a["largest_txn"]
        # largest usd_cents; ties -> lexicographically smallest txn_id
        if (
            best is None
            or r["usd_cents"] > next(x["usd_cents"] for x in rows if x["txn_id"] == best)
            or (
                r["usd_cents"] == next(x["usd_cents"] for x in rows if x["txn_id"] == best)
                and r["txn_id"] < best
            )
        ):
            a["largest_txn"] = r["txn_id"]

    monthly: dict[str, dict] = {}
    for r in rows:
        m = monthly.setdefault(r["month"], {"count": 0, "usd_cents": 0})
        m["count"] += 1
        m["usd_cents"] += r["usd_cents"]

    grand = sum(r["usd_cents"] for r in rows)
    result = {
        "accounts": {k: accounts[k] for k in sorted(accounts)},
        "monthly": {k: monthly[k] for k in sorted(monthly)},
        "grand_total_cents": grand,
    }

    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # ---- self checks ----
    assert sum(v["usd_cents"] for v in accounts.values()) == grand
    assert sum(v["usd_cents"] for v in monthly.values()) == grand
    assert sum(v["count"] for v in accounts.values()) == len(rows)
    assert sum(v["count"] for v in monthly.values()) == len(rows)
    for r in rows:
        print(
            f"{r['txn_id']} {r['account']} {r['month']} "
            f"{r['amount_cents']} * {r['fx_rate']} = {r['exact']} -> {r['usd_cents']}"
        )
    print("grand_total_cents =", grand)


if __name__ == "__main__":
    main()

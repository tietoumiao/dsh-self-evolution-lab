#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Independent verification of aggregate.json against input/transactions.csv.

Re-derives every number with a *different* code path (integer fraction maths on
the raw fx_rate string, no Decimal) and checks the delivery contract item by item.
Exit code 0 == all checks passed.
"""

import csv
import json
import sys
from fractions import Fraction

SRC = "input/transactions.csv"
DST = "aggregate.json"

checks = []
def check(name, ok, detail=""):
    checks.append((name, bool(ok), detail))


def exact_cents(amount_cents: int, fx_rate: str) -> int:
    """amount * rate as an exact Fraction; round half away from zero."""
    f = Fraction(amount_cents) * Fraction(fx_rate)   # Fraction(str) is exact decimal
    n, d = f.numerator, f.denominator
    if n >= 0:
        q, r = divmod(n, d)
        if 2 * r >= d:
            q += 1
        return q
    return -exact_cents_abs(-n, d)


def exact_cents_abs(n, d):
    q, r = divmod(n, d)
    if 2 * r >= d:
        q += 1
    return q


# ---- load input -------------------------------------------------------------
with open(SRC, "r", encoding="utf-8", newline="") as fh:
    rows = list(csv.DictReader(fh))
check("input header exactly txn_id,account,date,currency,amount_cents,fx_rate",
      list(rows[0].keys()) == ["txn_id", "account", "date", "currency", "amount_cents", "fx_rate"],
      str(list(rows[0].keys())) if rows else "no rows")
check("input row count > 0", len(rows) > 0, str(len(rows)))

for r in rows:
    r["usd"] = exact_cents(int(r["amount_cents"]), r["fx_rate"])
    r["month"] = r["date"][:7]

# ---- load output ------------------------------------------------------------
raw_bytes = open(DST, "rb").read()
check("output has no UTF-8 BOM", not raw_bytes.startswith(b"\xef\xbb\xbf"))
try:
    out = json.loads(raw_bytes.decode("utf-8"))
    decoded = True
    err = ""
except Exception as e:  # noqa: BLE001
    out, decoded, err = {}, False, repr(e)
    check("output is valid UTF-8 JSON", False, err)
if not decoded:
    for c in checks:
        print(("PASS " if c[1] else "FAIL ") + c[0] + (" :: " + c[2] if c[2] else ""))
    sys.exit(1)
check("output is valid UTF-8 JSON", True)

check("top-level keys exactly {accounts, monthly, grand_total_cents}",
      set(out.keys()) == {"accounts", "monthly", "grand_total_cents"}, str(sorted(out.keys())))

# ---- expected values --------------------------------------------------------
exp_accounts = {}
for r in rows:
    a = exp_accounts.setdefault(r["account"], {"count": 0, "usd_cents": 0, "_best": None})
    a["count"] += 1
    a["usd_cents"] += r["usd"]
    if a["_best"] is None or (-r["usd"], r["txn_id"]) < (-a["_best"]["usd"], a["_best"]["txn_id"]):
        a["_best"] = {"usd": r["usd"], "txn_id": r["txn_id"]}

exp_monthly = {}
for r in rows:
    m = exp_monthly.setdefault(r["month"], {"count": 0, "usd_cents": 0})
    m["count"] += 1
    m["usd_cents"] += r["usd"]

exp_grand = sum(r["usd"] for r in rows)

# ---- accounts ---------------------------------------------------------------
got_accounts = out.get("accounts", {})
check("accounts keys match input accounts",
      set(got_accounts) == set(exp_accounts),
      "got %s want %s" % (sorted(got_accounts), sorted(exp_accounts)))
for name in sorted(exp_accounts):
    got = got_accounts.get(name, {})
    want = exp_accounts[name]
    check("accounts[%s] keys exactly {count,usd_cents,largest_txn}" % name,
          isinstance(got, dict) and set(got.keys()) == {"count", "usd_cents", "largest_txn"},
          str(sorted(got.keys())) if isinstance(got, dict) else type(got).__name__)
    check("accounts[%s].count == %d" % (name, want["count"]),
          got.get("count") == want["count"], str(got.get("count")))
    check("accounts[%s].usd_cents == %d" % (name, want["usd_cents"]),
          got.get("usd_cents") == want["usd_cents"], str(got.get("usd_cents")))
    check("accounts[%s].largest_txn == %s" % (name, want["_best"]["txn_id"]),
          got.get("largest_txn") == want["_best"]["txn_id"], str(got.get("largest_txn")))

# ---- monthly ----------------------------------------------------------------
got_monthly = out.get("monthly", {})
check("monthly keys match YYYY-MM set",
      set(got_monthly) == set(exp_monthly),
      "got %s want %s" % (sorted(got_monthly), sorted(exp_monthly)))
check("all monthly keys match ^\\d{4}-\\d{2}$",
      all(len(k) == 7 and k[4] == "-" and k[:4].isdigit() and k[5:].isdigit() for k in got_monthly),
      str(sorted(got_monthly)))
for name in sorted(exp_monthly):
    got = got_monthly.get(name, {})
    want = exp_monthly[name]
    check("monthly[%s] keys exactly {count,usd_cents}" % name,
          isinstance(got, dict) and set(got.keys()) == {"count", "usd_cents"},
          str(sorted(got.keys())) if isinstance(got, dict) else type(got).__name__)
    check("monthly[%s].count == %d" % (name, want["count"]),
          got.get("count") == want["count"], str(got.get("count")))
    check("monthly[%s].usd_cents == %d" % (name, want["usd_cents"]),
          got.get("usd_cents") == want["usd_cents"], str(got.get("usd_cents")))

# ---- grand total: three paths ----------------------------------------------
gt = out.get("grand_total_cents")
sum_accounts = sum(a.get("usd_cents", 0) for a in got_accounts.values())
sum_monthly = sum(m.get("usd_cents", 0) for m in got_monthly.values())
check("grand_total_cents == independent recompute", gt == exp_grand,
      "got %r want %d" % (gt, exp_grand))
check("grand_total_cents == sum(accounts.usd_cents)", gt == sum_accounts,
      "grand %r sum_accounts %d" % (gt, sum_accounts))
check("grand_total_cents == sum(monthly.usd_cents)", gt == sum_monthly,
      "grand %r sum_monthly %d" % (gt, sum_monthly))
check("accounts count sum == input row count",
      sum(a.get("count", 0) for a in got_accounts.values()) == len(rows),
      str(sum(a.get("count", 0) for a in got_accounts.values())))
check("monthly count sum == input row count",
      sum(m.get("count", 0) for m in got_monthly.values()) == len(rows),
      str(sum(m.get("count", 0) for m in got_monthly.values())))

# ---- all numbers are JSON integers (not strings, not floats) ----------------
def ints_only(obj, path=""):
    bad = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            bad += ints_only(v, path + "/" + str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            bad += ints_only(v, path + "/%d" % i)
    elif isinstance(obj, bool) or not isinstance(obj, int):
        bad.append("%s=%r (%s)" % (path, obj, type(obj).__name__))
    return bad

bad = ints_only({k: v for k, v in out.items() if k != "accounts"})
for name, a in got_accounts.items():
    bad += ints_only({k: v for k, v in a.items() if k != "largest_txn"}, "/accounts/" + name)
for name, m in got_monthly.items():
    bad += ints_only(m, "/monthly/" + name)
check("every numeric leaf is a JSON int", not bad, "; ".join(bad))
check("accounts[].largest_txn are strings (txn_id)",
      all(isinstance(a.get("largest_txn"), str) for a in got_accounts.values()),
      str([type(a.get("largest_txn")).__name__ for a in got_accounts.values()]))

# ---- per-transaction spot table --------------------------------------------
print("--- per-transaction conversion (exact fraction maths) ---")
for r in rows:
    print("%s %-11s %s %s amount=%s rate=%s -> usd_cents=%d"
          % (r["txn_id"], r["account"], r["date"], r["currency"],
             r["amount_cents"], r["fx_rate"], r["usd"]))
print("--- checks ---")
fails = 0
for name, ok, detail in checks:
    if not ok:
        fails += 1
    print(("PASS " if ok else "FAIL ") + name + (("  :: " + detail) if detail and not ok else ""))
print("--- %d checks, %d failed ---" % (len(checks), fails))
if fails:
    sys.exit(1)
print("ALL CHECKS PASSED")

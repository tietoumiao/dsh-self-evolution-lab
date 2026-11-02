#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Boundary / edge-sample checks for the rounding + aggregation rules (R07).

Fixtures are written to a throwaway temp dir; aggregate.json in the work dir is
never touched. Exit 0 == all boundary checks passed.
"""

import csv
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_aggregate import to_cents, load_rows, aggregate, HEADER  # noqa: E402
from fractions import Fraction                                     # noqa: E402


def exact_cents(amount_cents, fx_rate):
    """Independent path: exact Fraction, half away from zero. (no Decimal)"""
    f = Fraction(amount_cents) * Fraction(fx_rate)
    n, d = abs(f.numerator), f.denominator
    q, r = divmod(n, d)
    if 2 * r >= d:
        q += 1
    return q if f >= 0 else -q

results = []
def check(name, actual, expected):
    ok = actual == expected
    results.append((name, ok, actual, expected))

# ---- 1. rounding boundaries: Decimal path vs independent Fraction path -----
cases = [
    ("exact .5 rounds up (positive)",        4300, "1.2650", 5440),
    ("exact .5 rounds away from zero (neg)", -4300, "1.2650", -5440),
    ("0.5 -> 1",                               1, "0.5",    1),
    ("-0.5 -> -1",                            -1, "0.5",   -1),
    ("2.5 -> 3 (no banker's rounding)",        5, "0.5",    3),
    ("-2.5 -> -3",                            -5, "0.5",   -3),
    ("1.5 -> 2",                               3, "0.5",    2),
    ("just below .5 -> 0",                     1, "0.49",   0),
    ("just above .5 -> 1",                     1, "0.51",   1),
    ("0.49999 -> 0",                           1, "0.49999", 0),
    ("zero amount -> 0",                       0, "1.0875", 0),
    ("zero rate -> 0",                     12500, "0",      0),
    ("integer rate passthrough",           20000, "1.0000", 20000),
    ("large amount 1e15 cents",        10**15, "1.0875", 1087500000000000),
    ("negative amount (real rate)",       -12500, "1.0875", -13594),
    ("4dp exact product (T003)",             999, "1.0875", 1086),
]
for label, amount, rate, want in cases:
    check("to_cents %-34s [%d x %s]" % (label, amount, rate), to_cents(amount, rate), want)
    check("fraction %-32s [%d x %s]" % (label, amount, rate), exact_cents(amount, rate), want)

# ---- 2. tie-break for largest_txn (same usd_cents -> smallest txn_id) ------
rows = [
    {"txn_id": "T0B", "account": "a", "month": "2026-01", "usd_cents": 100},
    {"txn_id": "T0A", "account": "a", "month": "2026-01", "usd_cents": 100},
    {"txn_id": "T0C", "account": "a", "month": "2026-01", "usd_cents": 99},
]
agg = aggregate(rows)
check("largest_txn tie -> lexicographic smallest", agg["accounts"]["a"]["largest_txn"], "T0A")
check("tie account count", agg["accounts"]["a"]["count"], 3)
check("tie account sum", agg["accounts"]["a"]["usd_cents"], 299)

# ---- 3. fixture-driven edge inputs ----------------------------------------
tmp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_bt_tmp")
os.makedirs(tmp, exist_ok=True)

def write_csv(name, body):
    p = os.path.join(tmp, name)
    with open(p, "w", encoding="utf-8", newline="") as fh:
        fh.write(",".join(HEADER) + "\n" + body)
    return p

# 3a. empty body (header only)
p = write_csv("empty.csv", "")
r = aggregate(load_rows(p))
check("empty input -> empty accounts", r["accounts"], {})
check("empty input -> empty monthly", r["monthly"], {})
check("empty input -> grand total 0", r["grand_total_cents"], 0)

# 3b. maximum-size sample
p = write_csv("big.csv", "T9999,acct-max,2026-12-31,JPY,1000000000000000,1.0875\n")
r = aggregate(load_rows(p))
check("max row converts exactly", r["accounts"]["acct-max"]["usd_cents"], 1087500000000000)
check("max row grand total", r["grand_total_cents"], 1087500000000000)

# 3c. month slicing + single-row account
p = write_csv("month.csv", "T1,a,2026-01-31,USD,7,1.0000\nT2,a,2026-12-01,USD,5,1.0000\n")
r = aggregate(load_rows(p))
check("month keys come from date[:7]", sorted(r["monthly"]), ["2026-01", "2026-12"])
check("cross-month account sum", r["accounts"]["a"]["usd_cents"], 12)
check("largest_txn picks higher value", r["accounts"]["a"]["largest_txn"], "T1")

# 3d. missing fx_rate -> explicit failure, no silent default
def expect_fail(label, body):
    p = write_csv("bad_%s.csv" % label, body)
    try:
        load_rows(p)
        results.append((label + " -> must raise", False, "no exception", "SystemExit"))
    except SystemExit as e:
        results.append((label + " -> explicit SystemExit", True, str(e), "error message"))
    except Exception as e:  # noqa: BLE001
        results.append((label + " -> must raise SystemExit, not " + type(e).__name__,
                        False, repr(e), "SystemExit"))

expect_fail("missing_fx_rate", "T1,a,2026-01-01,USD,100\n")
expect_fail("missing_amount", "T1,a,2026-01-01,USD,,1.0\n")
expect_fail("non_integer_amount", "T1,a,2026-01-01,USD,12.5,1.0\n")
expect_fail("non_numeric_rate", "T1,a,2026-01-01,USD,100,abc\n")
expect_fail("dup_txn_id", "T1,a,2026-01-01,USD,100,1.0\nT1,a,2026-01-02,USD,50,1.0\n")
expect_fail("short_date", "T1,a,2026,USD,100,1.0\n")

# ---- report ----------------------------------------------------------------
fails = 0
for name, ok, actual, expected in results:
    if not ok:
        fails += 1
        print("FAIL %s :: got %r want %r" % (name, actual, expected))
    else:
        print("PASS %s :: %r" % (name, actual))
print("--- %d boundary checks, %d failed ---" % (len(results), fails))
shutil.rmtree(tmp, ignore_errors=True)
sys.exit(1 if fails else 0)
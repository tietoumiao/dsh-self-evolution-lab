# -*- coding: utf-8 -*-
"""Build report.json from input/policy.md + input/meter.csv (exact decimal math)."""
import json
from decimal import Decimal, ROUND_HALF_UP

BASE = r"<workspace>/agi/runs2/G0/dev/H01/rep1"

policy = open(BASE + r"\input\policy.md", encoding="utf-8").read()

# ---- quotes must exist verbatim in the policy document ----
Q_PERIOD_BODY = "正文规定的采样时长为 15 分钟，即 0.25 小时。"
Q_PERIOD_APPX = "采样时长为 30 分钟，即每次采样按 0.5 小时计电量。"
Q_ROUND_BODY = "金额换算为分：分 = 金额 × 100，按四舍五入（0.5 分进位）取整为整数分。"
Q_ROUND_APPX = "金额按 0.05 元为单位向上取整（不足 5 分的部分一律进位到 5 分）。"

for q in (Q_PERIOD_BODY, Q_PERIOD_APPX, Q_ROUND_BODY, Q_ROUND_APPX):
    assert q in policy, "quote not found verbatim: " + q

# each quote must sit in its own side of the document
idx = policy.index("## 附录 A")
assert policy.index(Q_PERIOD_BODY) < idx and policy.index(Q_ROUND_BODY) < idx
assert policy.index(Q_PERIOD_APPX) > idx and policy.index(Q_ROUND_APPX) > idx

conflicts = [
    {
        "topic": "sample_period",
        "body": {"location": "§1", "quote": Q_PERIOD_BODY},
        "appendix": {"location": "附录 B", "quote": Q_PERIOD_APPX},
        "adopted": "body",
    },
    {
        "topic": "rounding",
        "body": {"location": "§5", "quote": Q_ROUND_BODY},
        "appendix": {"location": "附录 A", "quote": Q_ROUND_APPX},
        "adopted": "body",
    },
]

# ---- prices from §4 ----
PRICE = {"A1": Decimal("0.61884"), "B2": Decimal("0.50000"), "C3": Decimal("1.02700")}
HOURS = Decimal("0.25")  # §1 body: 15 minutes

kwh = {}
with open(BASE + r"\input\meter.csv", encoding="utf-8") as f:
    header = f.readline().strip()
    assert header == "site,ts,kw", header
    for line in f:
        line = line.strip()
        if not line:
            continue
        site, ts, kw = line.split(",")
        kwh[site] = kwh.get(site, Decimal("0")) + Decimal(kw) * HOURS

sites = {}
total = 0
for site in sorted(kwh):
    e = kwh[site]
    kwh_milli = int((e * 1000).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    amount = e * PRICE[site]
    cents = int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    sites[site] = {"kwh_milli": kwh_milli, "amount_cents": cents}
    total += cents
    print(site, "kwh=", e, "kwh_milli=", kwh_milli, "yuan=", amount, "cents_exact=", amount * 100, "->", cents)

report = {
    "schema": 1,
    "conflicts": conflicts,
    "sites": sites,
    "total_amount_cents": total,
}

with open(BASE + r"\report.json", "w", encoding="utf-8", newline="\n") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
    f.write("\n")

print("total_amount_cents =", total)

# -*- coding: utf-8 -*-
import json, os
from decimal import Decimal, ROUND_HALF_UP
BASE = r"<workspace>/agi/runs2/G0/dev/H01/rep1"
raw = open(BASE + r"\report.json", "rb").read()
assert not raw.startswith(b"\xef\xbb\xbf"), "BOM present"
r = json.loads(raw.decode("utf-8"))
assert list(r.keys()) == ["schema", "conflicts", "sites", "total_amount_cents"], list(r.keys())
assert r["schema"] == 1 and type(r["schema"]) is int
assert len(r["conflicts"]) == 2
assert {c["topic"] for c in r["conflicts"]} == {"sample_period", "rounding"}
policy = open(BASE + r"\input\policy.md", encoding="utf-8").read()
appx_start = policy.index("## 附录 A")
for c in r["conflicts"]:
    assert list(c.keys()) == ["topic", "body", "appendix", "adopted"]
    assert list(c["body"].keys()) == ["location", "quote"] and list(c["appendix"].keys()) == ["location", "quote"]
    assert c["adopted"] == "body"
    assert c["body"]["location"].startswith("§") and c["appendix"]["location"].startswith("附录")
    bq, aq = c["body"]["quote"], c["appendix"]["quote"]
    assert bq in policy and aq in policy, "quote not verbatim"
    assert policy.index(bq) < appx_start < policy.index(aq), "quote on wrong side"
# recompute independently
PRICE = {"A1": Decimal("0.61884"), "B2": Decimal("0.50000"), "C3": Decimal("1.02700")}
kwh = {}
for line in open(BASE + r"\input\meter.csv", encoding="utf-8").read().splitlines()[1:]:
    s, t, kw = line.split(",")
    kwh[s] = kwh.get(s, Decimal(0)) + Decimal(kw) * Decimal("0.25")
assert set(kwh) == set(r["sites"]), (set(kwh), set(r["sites"]))
tot = 0
for s, e in kwh.items():
    k = int((e * 1000).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    c = int((e * PRICE[s] * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    assert r["sites"][s] == {"kwh_milli": k, "amount_cents": c}, (s, r["sites"][s], k, c)
    assert list(r["sites"][s].keys()) == ["kwh_milli", "amount_cents"]
    assert isinstance(k, int) and isinstance(c, int)
    tot += c
assert r["total_amount_cents"] == tot == 2782, (r["total_amount_cents"], tot)
print("ALL CHECKS PASSED; total =", tot, "; no BOM; size =", len(raw), "bytes")
print("files:", sorted(os.listdir(BASE)))

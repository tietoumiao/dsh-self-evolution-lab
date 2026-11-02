#!/usr/bin/env python3
"""把 input/ledger.csv 汇总成 out/summary.json。

用法（在当前目录下）：
    python input/tool.py

ledger.csv 每行一条记录：store,category,qty,unit_cents
字段可被半角双引号包裹（包裹内的逗号属于字段内容）。
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "input" / "ledger.csv"
TARGET = ROOT / "out" / "summary.json"


def parse_bytes(data):
    """把 ledger.csv 的原始字节解析成记录列表。"""
    rows = []
    text = data.decode("gbk", errors="replace")
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split(",")]
        try:
            store = parts[0]
            category = parts[1]
            qty = int(parts[2])
            unit_cents = int(parts[3])
        except Exception:
            continue
        rows.append({"store": store, "category": category,
                     "qty": qty, "unit_cents": unit_cents})
    return rows


def summarize(rows):
    """按 category 汇总行数、件数与金额（整数分）。"""
    by_category = {}
    for row in rows:
        item = by_category.setdefault(row["category"], {"rows": 0, "qty": 0, "amount": 0})
        item["rows"] += 1
        item["qty"] += row["qty"]
        item["amount"] += row["qty"] * row["unit_cents"]
    amount_total = 0
    for row in rows:
        amount_total += row["qty"] * row["unit_cents"]
    return {"rows_total": len(rows), "amount_total": amount_total,
            "by_category": by_category}


def main():
    summary = summarize(parse_bytes(LEDGER.read_bytes()))
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")
    print(str(TARGET))


if __name__ == "__main__":
    main()

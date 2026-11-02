#!/usr/bin/env python3
"""把 input/ledger.csv 汇总成 out/summary.json。

用法（在当前目录下）：
    python tool.py

ledger.csv 每行一条记录：store,category,qty,unit_cents
字段可被半角双引号包裹（包裹内的逗号属于字段内容）。
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LEDGER = ROOT / "input" / "ledger.csv"
TARGET = ROOT / "out" / "summary.json"


def parse_bytes(data):
    """把 ledger.csv 的原始字节解析成记录列表（UTF-8 + 标准 CSV 解析）。"""
    text = data.decode("utf-8")
    lines = [ln for ln in text.splitlines()
             if ln.strip() and not ln.strip().startswith("#")]
    rows = []
    for parts in csv.reader(lines):
        if len(parts) != 4:
            raise ValueError("字段数应为 4，实际 %d: %r" % (len(parts), parts))
        store, category, qty, unit_cents = [p.strip() for p in parts]
        rows.append({"store": store, "category": category,
                     "qty": int(qty), "unit_cents": int(unit_cents)})
    return rows


def summarize(rows):
    """按 category 汇总行数、件数与金额（整数分）。"""
    by_category = {}
    amount_total = 0
    for row in rows:
        amount_total += row["qty"] * row["unit_cents"]
        item = by_category.setdefault(row["category"], {"rows": 0, "qty": 0, "amount": 0})
        item["rows"] += 1
        item["qty"] += row["qty"]
        item["amount"] += row["qty"] * row["unit_cents"]
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

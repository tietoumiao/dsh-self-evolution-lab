#!/usr/bin/env python3
"""把 input/ledger.csv 汇总成 out/summary.json。

用法（在当前目录下）：
    python tool.py

ledger.csv 每行一条记录：store,category,qty,unit_cents
字段可被半角双引号包裹（包裹内的逗号属于字段内容）；空行与 `#` 开头的行不是记录。
字段数不是 4、或 qty / unit_cents 不是十进制整数时，抛 ValueError（不静默跳过）。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
# 交付的 tool.py 放在项目根目录；若被放回 input/ 下也能正确定位。
ROOT = HERE.parent if HERE.name == "input" else HERE
LEDGER = ROOT / "input" / "ledger.csv"
TARGET = ROOT / "out" / "summary.json"

_INT_RE = re.compile(r"^[+-]?[0-9]+$")


def _split_line(line: str, lineno: int) -> list[tuple[str, bool]]:
    """按 CSV 引号规则拆一行，返回 [(字段文本, 是否被引号包裹), ...]。

    规则：字段可整体被半角双引号包裹；包裹内的逗号是字段内容；
    包裹内两个连续引号表示一个字面引号。引号必须紧贴字段边界、且必须闭合，
    否则视为坏行抛 ValueError（不猜、不截断）。
    """
    fields: list[tuple[str, bool]] = []
    buf: list[str] = []
    quoted = False          # 当前字段是否以引号开头
    in_quotes = False       # 是否处于引号内部
    closed = False          # 当前字段的右引号是否已出现
    i, n = 0, len(line)

    while i < n:
        ch = line[i]

        if in_quotes:
            if ch == '"':
                if i + 1 < n and line[i + 1] == '"':   # "" -> 字面引号
                    buf.append('"')
                    i += 2
                    continue
                in_quotes = False
                closed = True
                i += 1
                continue
            buf.append(ch)
            i += 1
            continue

        if ch == ",":
            fields.append(("".join(buf), quoted))
            buf, quoted, closed = [], False, False
            i += 1
            continue

        if ch == '"':
            if closed:
                raise ValueError(f"第 {lineno} 行：字段内出现游离的双引号")
            if "".join(buf).strip():
                raise ValueError(f"第 {lineno} 行：双引号不在字段开头")
            buf = []                    # 丢掉引号前的空白
            quoted = in_quotes = True
            i += 1
            continue

        if closed:
            if not ch.isspace():
                raise ValueError(f"第 {lineno} 行：右引号后还有多余字符")
            i += 1                      # 容忍右引号后的空白
            continue

        buf.append(ch)
        i += 1

    if in_quotes:
        raise ValueError(f"第 {lineno} 行：双引号未闭合")
    fields.append(("".join(buf), quoted))
    return fields


def _field_text(text: str, quoted: bool) -> str:
    """未包裹的字段去掉首尾空白；被包裹的字段按原样保留内容。"""
    return text if quoted else text.strip()


def _to_int(raw: str, lineno: int, name: str) -> int:
    if not _INT_RE.match(raw):
        raise ValueError(f"第 {lineno} 行：{name} 不是十进制整数：{raw!r}")
    return int(raw)


def parse_bytes(data: bytes) -> list[dict]:
    """把 ledger.csv 的原始字节解析成记录列表。"""
    try:
        text = data.decode("utf-8-sig")      # 按 UTF-8 解码（容忍 BOM）
    except UnicodeDecodeError as exc:
        raise ValueError(f"ledger 不是合法的 UTF-8 文本：{exc}") from exc

    rows: list[dict] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.strip().startswith("#"):
            continue                          # 空行与注释行不是记录

        fields = _split_line(line, lineno)
        if len(fields) != 4:
            raise ValueError(
                f"第 {lineno} 行：字段数应为 4，实际 {len(fields)}：{line!r}")
        (store, _), (category, _), (qty_s, _), (unit_s, _) = fields

        rows.append({
            "store": _field_text(store, fields[0][1]),
            "category": _field_text(category, fields[1][1]),
            "qty": _to_int(_field_text(qty_s, fields[2][1]), lineno, "qty"),
            "unit_cents": _to_int(_field_text(unit_s, fields[3][1]), lineno, "unit_cents"),
        })
    return rows


def summarize(rows: list[dict]) -> dict:
    """按 category 汇总行数、件数与金额（整数分）。"""
    by_category: dict[str, dict[str, int]] = {}
    rows_total = 0
    amount_total = 0

    for row in rows:
        amount = row["qty"] * row["unit_cents"]
        item = by_category.setdefault(
            row["category"], {"rows": 0, "qty": 0, "amount": 0})
        item["rows"] += 1
        item["qty"] += row["qty"]
        item["amount"] += amount
        rows_total += 1
        amount_total += amount

    return {
        "rows_total": rows_total,
        "amount_total": amount_total,
        "by_category": by_category,
    }


def main() -> None:
    summary = summarize(parse_bytes(LEDGER.read_bytes()))
    # 自检：明细与汇总必须自洽，避免再次「不报错但结果错」。
    assert summary["rows_total"] == sum(v["rows"] for v in summary["by_category"].values())
    assert summary["amount_total"] == sum(v["amount"] for v in summary["by_category"].values())

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print(f"{TARGET}  rows_total={summary['rows_total']}  "
          f"amount_total={summary['amount_total']}  "
          f"categories={len(summary['by_category'])}")


if __name__ == "__main__":
    main()

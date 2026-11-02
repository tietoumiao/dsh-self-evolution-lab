#!/usr/bin/env python3
"""把 input/ledger.csv 汇总成 out/summary.json。

用法（在当前目录下）：
    python tool.py

ledger.csv 每行一条记录：store,category,qty,unit_cents
字段可被半角双引号包裹（包裹内的逗号属于字段内容）。
空行与 `#` 开头的行都不是记录。
字段数不是 4 个、或 qty / unit_cents 不是十进制整数时抛 ValueError。
"""
import json
import re
from pathlib import Path

# 交付布局：tool.py 位于工作目录根部，与 input/ 同级。
# 若脚本被放在 input/ 之类的位置，则退回当前工作目录再找一次。
BASE = Path(__file__).resolve().parent
if not (BASE / "input" / "ledger.csv").is_file():
    BASE = Path.cwd()
LEDGER = BASE / "input" / "ledger.csv"
TARGET = BASE / "out" / "summary.json"

FIELDS = ("store", "category", "qty", "unit_cents")
# 十进制整数：可选正负号 + ASCII 数字。int() 本身还接受下划线、全角数字与首尾空白，
# 这里用全匹配把它收紧成「十进制整数」的字面意思。
_DEC_INT = re.compile(r"[+-]?[0-9]+")


def _split_fields(line, lineno):
    """按 CSV 规则把一行拆成字段列表（支持双引号包裹，包裹内可含逗号与成对双引号）。"""
    fields = []
    pos = 0
    size = len(line)
    while True:
        if pos < size and line[pos] == '"':
            pos += 1
            buf = []
            while True:
                if pos >= size:
                    raise ValueError("第 %d 行：双引号未闭合" % lineno)
                char = line[pos]
                if char == '"':
                    if pos + 1 < size and line[pos + 1] == '"':
                        buf.append('"')
                        pos += 2
                        continue
                    pos += 1
                    break
                buf.append(char)
                pos += 1
            while pos < size and line[pos] in " \t":
                pos += 1
            if pos < size and line[pos] != ",":
                raise ValueError("第 %d 行：右引号之后出现多余字符 %r" % (lineno, line[pos]))
            fields.append("".join(buf))
        else:
            start = pos
            while pos < size and line[pos] != ",":
                if line[pos] == '"':
                    raise ValueError("第 %d 行：未加双引号的字段内出现半角双引号" % lineno)
                pos += 1
            fields.append(line[start:pos].strip())
        if pos >= size:
            break
        pos += 1  # 跳过字段分隔的逗号（行尾逗号会产生一个空字段）
    return fields


def _parse_int(text, name, lineno):
    """把字段转成 int；不是十进制整数就抛 ValueError（不截断、不给默认值）。"""
    if not _DEC_INT.fullmatch(text):
        raise ValueError("第 %d 行：%s 不是十进制整数：%r" % (lineno, name, text))
    return int(text, 10)


def parse_bytes(data: bytes) -> list:
    """把 ledger.csv 的原始字节解析成记录列表。"""
    # 严格 UTF-8 解码：坏字节直接抛 UnicodeDecodeError（ValueError 的子类），
    # 不再用 errors="replace" 把损坏内容替换成 U+FFFD 继续跑。
    text = data.decode("utf-8")
    rows = []
    for lineno, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        fields = _split_fields(line, lineno)
        if len(fields) != len(FIELDS):
            raise ValueError("第 %d 行：字段数应为 4，实际 %d：%r"
                             % (lineno, len(fields), line))
        store, category, qty_text, unit_text = fields
        rows.append({
            "store": store,
            "category": category,
            "qty": _parse_int(qty_text, "qty", lineno),
            "unit_cents": _parse_int(unit_text, "unit_cents", lineno),
        })
    return rows


def summarize(rows) -> dict:
    """按 category 汇总行数、件数与金额（整数分）。"""
    by_category = {}
    amount_total = 0
    for row in rows:
        item = by_category.setdefault(row["category"], {"rows": 0, "qty": 0, "amount": 0})
        amount = row["qty"] * row["unit_cents"]
        item["rows"] += 1
        item["qty"] += row["qty"]
        item["amount"] += amount
        amount_total += amount
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

#!/usr/bin/env python3
"""把 input/ledger.csv 汇总成 out/summary.json。

用法（在工作目录下）：
    python tool.py

ledger.csv 每行一条记录：store,category,qty,unit_cents
字段可被半角双引号包裹：包裹内的半角逗号属于字段内容，包裹内的 "" 表示一个字面双引号。
空行与 # 开头的行都不是记录。
字段数不是 4 个、或 qty / unit_cents 不是十进制整数时抛 ValueError（不跳过、不截断、不填默认值）。
"""
import json
import re
from pathlib import Path

_HERE = Path(__file__).resolve().parent
# 正常情况下本脚本放在工作目录根，_HERE 就是工作目录；
# 若被放回 input/ 里运行，则上跳一层仍指向工作目录（两种放法都不用依赖启动时的 cwd）。
ROOT = _HERE if (_HERE / "input").is_dir() else _HERE.parent
LEDGER = ROOT / "input" / "ledger.csv"
TARGET = ROOT / "out" / "summary.json"

# 十进制整数：只认 ASCII 数字（int() 本身还会接受 "1_0"、全角数字，这里不放行）。
_DEC_INT = re.compile(r"[+-]?[0-9]+\Z")


def _split_fields(line):
    """按半角逗号切字段，识别双引号包裹。返回 [(字段值, 是否被引号包裹), ...]。"""
    fields = []
    buf = []
    quoted = False       # 当前字段是否被引号包裹
    in_quotes = False    # 是否处于引号内部
    i, n = 0, len(line)
    while i < n:
        ch = line[i]
        if in_quotes:
            if ch != '"':
                buf.append(ch)
                i += 1
                continue
            if i + 1 < n and line[i + 1] == '"':      # 包裹内的 "" -> 一个字面双引号
                buf.append('"')
                i += 2
                continue
            in_quotes = False                          # 右引号
            i += 1
            while i < n and line[i] in " \t":          # 右引号后只允许空白
                i += 1
            if i < n and line[i] != ",":
                raise ValueError(f"双引号包裹的字段后面出现多余字符：{line!r}")
            continue
        if ch == ",":
            fields.append(("".join(buf), quoted))
            buf, quoted = [], False
            i += 1
            continue
        if ch == '"':
            if "".join(buf).strip():                   # 引号只允许出现在字段开头
                raise ValueError(f"双引号不在字段开头：{line!r}")
            buf, quoted, in_quotes = [], True, True
            i += 1
            continue
        buf.append(ch)
        i += 1
    if in_quotes:
        raise ValueError(f"双引号未闭合：{line!r}")
    fields.append(("".join(buf), quoted))
    return fields


def _to_dec_int(text, name, lineno):
    """十进制整数字段校验：不合格就抛 ValueError，绝不返回默认值。"""
    if not _DEC_INT.match(text):
        raise ValueError(f"第 {lineno} 行的 {name} 不是十进制整数：{text!r}")
    return int(text, 10)


def parse_bytes(data: bytes) -> list[dict]:
    """把 ledger.csv 的原始字节解析成记录列表（按 UTF-8 解码，解码失败即抛错）。"""
    text = data.decode("utf-8")
    rows = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fields = _split_fields(line)
        if len(fields) != 4:
            raise ValueError(f"第 {lineno} 行字段数为 {len(fields)}，应为 4：{raw!r}")
        values = [value if was_quoted else value.strip() for value, was_quoted in fields]
        store, category, qty_text, unit_text = values
        rows.append({"store": store,
                     "category": category,
                     "qty": _to_dec_int(qty_text.strip(), "qty", lineno),
                     "unit_cents": _to_dec_int(unit_text.strip(), "unit_cents", lineno)})
    return rows


def summarize(rows) -> dict:
    """按 category 汇总行数、件数与金额（整数分）。"""
    by_category = {}
    amount_total = 0
    for row in rows:
        amount = row["qty"] * row["unit_cents"]
        amount_total += amount
        item = by_category.setdefault(row["category"], {"rows": 0, "qty": 0, "amount": 0})
        item["rows"] += 1
        item["qty"] += row["qty"]
        item["amount"] += amount
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

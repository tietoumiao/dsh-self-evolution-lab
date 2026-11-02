"""日志清洗与汇总（修复版）。

用法（在工作目录下）：

    python clean.py

读 `input/events.log`，写 `out/summary.json`。

`parse_line(line)` 是本模块的公开契约：
- 严格匹配 `<ts> <LEVEL> svc=<name> code=<3位> ms=<1..5位>` 时返回五键 dict；
- 其它任何输入（空行、注释、截断、级别越界、多余/缺失字段、行尾空格、
  制表符、非 ASCII 数字等）一律返回 None，绝不抛异常。
- 模块被 import 时不读文件、不写文件、不打印，只有导入时构造的常量与正则。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

# 允许的级别（全大写，枚举之外一律非法）。
LEVELS = ("DEBUG", "INFO", "WARN", "ERROR")

# 严格的一行格式：
#   YYYY-MM-DDTHH:MM:SSZ <LEVEL> svc=<name> code=<ddd> ms=<d{1,5}>
# 字段之间恰好一个半角空格；用 fullmatch 保证行首行尾无多余字符
# （因此行尾空格、换行符、多余字段都会导致不匹配）。
# 数字一律用 [0-9]，避免 \d 匹配到非 ASCII 数字。
# svc 名不允许含空白与 "="，避免把 `svc=a=b` 之类当成合法。
LINE_RE = re.compile(
    r"(?P<ts>[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z)"
    r" (?P<level>DEBUG|INFO|WARN|ERROR)"
    r" svc=(?P<svc>[^\s=]+)"
    r" code=(?P<code>[0-9]{3})"
    r" ms=(?P<ms>[0-9]{1,5})"
)

BASE_DIR = Path(__file__).resolve().parent
SOURCE = BASE_DIR / "input" / "events.log"
TARGET = BASE_DIR / "out" / "summary.json"


def parse_line(line: str):
    """把一行日志解析成 dict；不符合严格格式时返回 None（不抛异常）。"""
    if not isinstance(line, str):
        return None
    match = LINE_RE.fullmatch(line)
    if match is None:
        return None
    return {
        "ts": match.group("ts"),
        "level": match.group("level"),
        "svc": match.group("svc"),
        "code": int(match.group("code")),
        "ms": int(match.group("ms")),
    }


def build_summary(lines):
    """按契约为可迭代的文本行生成 summary 字典。"""
    total = 0
    levels = {name: 0 for name in LEVELS}
    services: dict[str, dict[str, int]] = {}
    rows = []

    for line_no, raw in enumerate(lines, start=1):
        record = parse_line(raw)
        if record is None:
            continue
        total += 1
        levels[record["level"]] += 1

        bucket = services.setdefault(
            record["svc"], {"count": 0, "error_count": 0, "max_ms": 0}
        )
        bucket["count"] += 1
        # error_count 统计的是「级别为 ERROR 的行数」，不是 code >= 400。
        if record["level"] == "ERROR":
            bucket["error_count"] += 1
        bucket["max_ms"] = max(bucket["max_ms"], record["ms"])

        rows.append({"line_no": line_no, "svc": record["svc"], "ms": record["ms"]})

    # ms 从大到小；ms 相同按 line_no 从小到大。
    rows.sort(key=lambda row: (-row["ms"], row["line_no"]))

    return {
        "schema": 1,
        "total": total,
        "levels": levels,
        # 服务名按字典序输出，保证结果稳定可复现。
        "services": {name: services[name] for name in sorted(services)},
        "slowest": rows[:3],
    }


def main():
    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    summary = build_summary(lines)
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("wrote", TARGET, "total=", summary["total"])


if __name__ == "__main__":
    main()

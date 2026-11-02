"""日志清洗与汇总（修正版）。

用法（在工作目录下）：

    python clean.py

读 ``input/events.log``，写 ``out/summary.json``。

``parse_line`` 是纯函数：导入本模块不会读文件、也不会写文件。
"""

import json
import re
from pathlib import Path

# `<ts> <LEVEL> svc=<name> code=<3 digits> ms=<1..5 digits>`，字段间恰好一个空格，行尾无空格。
_LINE_RE = re.compile(
    r"(?P<ts>[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z)"
    r" (?P<level>DEBUG|INFO|WARN|ERROR)"
    r" svc=(?P<svc>\S+)"
    r" code=(?P<code>[0-9]{3})"
    r" ms=(?P<ms>[0-9]{1,5})"
)

LEVELS = ("DEBUG", "INFO", "WARN", "ERROR")


def parse_line(line):
    """把一行日志解析成字典；不符合格式时返回 None（不抛异常）。"""
    if not isinstance(line, str):
        return None
    match = _LINE_RE.fullmatch(line)
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
    """按契约汇总：levels 四键齐全，services 三键，slowest 最多 3 条。"""
    total = 0
    levels = {name: 0 for name in LEVELS}
    services = {}
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
        if record["level"] == "ERROR":
            bucket["error_count"] += 1
        if record["ms"] > bucket["max_ms"]:
            bucket["max_ms"] = record["ms"]
        rows.append(
            {"line_no": line_no, "svc": record["svc"], "ms": record["ms"]}
        )
    rows.sort(key=lambda row: (-row["ms"], row["line_no"]))
    return {
        "schema": 1,
        "total": total,
        "levels": levels,
        "services": services,
        "slowest": rows[:3],
    }


def main():
    base = Path(__file__).resolve().parent
    source = base / "input" / "events.log"
    summary = build_summary(source.read_text(encoding="utf-8").splitlines())
    target = base / "out" / "summary.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("wrote", target)


if __name__ == "__main__":
    main()

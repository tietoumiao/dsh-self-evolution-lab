"""日志清洗与汇总（修复版）。

用法：在本目录执行 `python clean.py`
  - 读 input/events.log（UTF-8）
  - 写 out/summary.json（UTF-8）

被 import 时无任何副作用：不读文件、不写文件。
"""

import json
import re
from pathlib import Path

LEVELS = ("DEBUG", "INFO", "WARN", "ERROR")

# 严格形状：<YYYY-MM-DDTHH:MM:SSZ> <LEVEL> svc=<name> code=<3 位> ms=<1~5 位>
# 字段间恰好一个半角空格；行首行尾无空白；无多余字段。
_LINE_RE = re.compile(
    r"(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)"
    r" (?P<level>DEBUG|INFO|WARN|ERROR)"
    r" svc=(?P<svc>\S+)"
    r" code=(?P<code>\d{3})"
    r" ms=(?P<ms>\d{1,5})"
)


def parse_line(line):
    """解析一行日志；严格符合形状返回 dict（ts/level/svc/code/ms），否则返回 None。"""
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
    """把日志行汇总成契约要求的 summary 对象。"""
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
        bucket["max_ms"] = max(bucket["max_ms"], record["ms"])
        rows.append({"line_no": line_no, "svc": record["svc"], "ms": record["ms"]})
    # ms 从大到小；ms 相同时 line_no 从小到大
    rows.sort(key=lambda row: (-row["ms"], row["line_no"]))
    return {
        "schema": 1,
        "total": total,
        "levels": levels,
        "services": {name: services[name] for name in sorted(services)},
        "slowest": rows[:3],
    }


def main():
    source = Path("input") / "events.log"
    text = source.read_text(encoding="utf-8")
    summary = build_summary(text.splitlines())
    target = Path("out") / "summary.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("wrote", target)


if __name__ == "__main__":
    main()

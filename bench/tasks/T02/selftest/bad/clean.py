"""日志清洗与汇总（解析已修好，但 error_count 与 slowest 的口径仍读错）。"""

import json
import re
import sys
from pathlib import Path

LINE_RE = re.compile(
    r"^(?P<ts>[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z)"
    r" (?P<level>DEBUG|INFO|WARN|ERROR)"
    r" svc=(?P<svc>[a-z0-9_-]+)"
    r" code=(?P<code>[0-9]{3})"
    r" ms=(?P<ms>[0-9]{1,5})$"
)


def parse_line(line):
    """把一行日志解析成字典；不符合格式时返回 None。"""
    match = LINE_RE.match(line)
    if not match:
        return None
    return {
        "ts": match.group("ts"),
        "level": match.group("level"),
        "svc": match.group("svc"),
        "code": int(match.group("code")),
        "ms": int(match.group("ms")),
    }


def build_summary(lines):
    total = 0
    levels = {"DEBUG": 0, "INFO": 0, "WARN": 0, "ERROR": 0}
    services = {}
    rows = []
    for line_no, raw in enumerate(lines, start=1):
        record = parse_line(raw)
        if record is None:
            continue
        total += 1
        levels[record["level"]] += 1
        bucket = services.setdefault(record["svc"], {"count": 0, "error_count": 0, "max_ms": 0})
        bucket["count"] += 1
        if record["code"] >= 400:
            bucket["error_count"] += 1
        bucket["max_ms"] = max(bucket["max_ms"], record["ms"])
        rows.append({"line_no": line_no, "svc": record["svc"], "ms": record["ms"]})
    rows.sort(key=lambda row: row["ms"])
    return {"schema": 1, "total": total, "levels": levels,
            "services": services, "slowest": rows[:2]}


def main():
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("input") / "events.log"
    summary = build_summary(source.read_text(encoding="utf-8").splitlines())
    target = Path("out") / "summary.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote", target)


if __name__ == "__main__":
    main()

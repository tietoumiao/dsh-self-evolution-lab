"""日志清洗与汇总（当前实现有缺陷，待修）。"""

import json
import sys
from pathlib import Path


def parse_line(line):
    """把一行日志解析成字典；不符合格式时返回 None。"""
    parts = line.split(" ")
    ts = parts[0]
    level = parts[1]
    svc = parts[2].split("=")[1]
    code = int(parts[3].split("=")[1])
    ms = int(parts[4].split("=")[1])
    return {"ts": ts, "level": level, "svc": svc, "code": code, "ms": ms}


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
    source = Path("input") / "events.log"
    summary = build_summary(source.read_text(encoding="utf-8").splitlines())
    target = Path("out") / "summary.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote", target)


if __name__ == "__main__":
    main()

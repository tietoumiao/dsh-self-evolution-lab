"""日志清洗与汇总（已修复）。

用法（在工作目录下运行）::

    python clean.py

读取 ``input/events.log``，写出 ``out/summary.json``。

约定（见任务书契约）：
- ``parse_line(line)`` 只解析严格符合下面形状的行，其余一律返回 ``None``，从不抛异常::

    <ts> <LEVEL> svc=<svc> code=<三位数字> ms=<1~5 位数字>

  ``ts`` 恰好是 ``YYYY-MM-DDTHH:MM:SSZ``（字面量 ``Z`` 结尾的 UTC 时间）；
  ``LEVEL`` 属于 {DEBUG, INFO, WARN, ERROR}；字段之间恰好一个半角空格；
  行尾不许多余空格，不许多余/缺失字段。
- 被 ``import`` 时不读文件、不写文件、不打印。

说明：时间戳除形状匹配外还做日历合法性校验（如 ``2026-13-45T99:99:99Z``
形状正确但不是真实时刻，按非法行处理）。行尾若带有换行符（``\n``/``\r\n``）
会被先去掉——这只涉及换行，不放过行尾空格。
"""

import json
import re
from datetime import datetime
from pathlib import Path

LEVELS = ("DEBUG", "INFO", "WARN", "ERROR")
NEWLINE_END = ("\n", "\r\n", "\r")

# 严格形状：ts|level|svc=..|code=3位|ms=1~5位，字段间恰好一个半角空格
LINE_RE = re.compile(
    r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)"
    r" (DEBUG|INFO|WARN|ERROR)"
    r" svc=(\S+)"
    r" code=(\d{3})"
    r" ms=(\d{1,5})"
)
TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def _valid_ts(ts):
    """时间戳必须是真实存在的 UTC 时刻。"""
    try:
        datetime.strptime(ts, TS_FORMAT)
    except ValueError:
        return False
    return True


def parse_line(line):
    """把一行日志解析成 dict；不符合格式时返回 None（不抛异常）。"""
    if not isinstance(line, str):
        return None
    if line.endswith(NEWLINE_END):
        line = line.rstrip("\r\n")
    match = LINE_RE.fullmatch(line)
    if match is None:
        return None
    ts, level, svc, code, ms = match.groups()
    if not _valid_ts(ts):
        return None
    return {
        "ts": ts,
        "level": level,
        "svc": svc,
        "code": int(code),
        "ms": int(ms),
    }


def build_summary(lines, limit_slowest=3):
    """按契约汇总，返回 dict。lines 为日志行序列（行号从 1 开始）。"""
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
        bucket = services.get(record["svc"])
        if bucket is None:
            bucket = {"count": 0, "error_count": 0, "max_ms": 0}
            services[record["svc"]] = bucket
        bucket["count"] += 1
        if record["level"] == "ERROR":
            bucket["error_count"] += 1
        if record["ms"] > bucket["max_ms"]:
            bucket["max_ms"] = record["ms"]
        rows.append({"line_no": line_no, "svc": record["svc"], "ms": record["ms"]})

    # ms 从大到小；ms 相同按 line_no 从小到大
    rows.sort(key=lambda row: (-row["ms"], row["line_no"]))

    return {
        "schema": 1,
        "total": total,
        "levels": levels,
        "services": {name: services[name] for name in sorted(services)},
        "slowest": rows[:limit_slowest],
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

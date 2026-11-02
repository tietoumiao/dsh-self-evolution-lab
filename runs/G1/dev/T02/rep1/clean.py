"""日志清洗与汇总（修正版）。

读 ``input/events.log``，写 ``out/summary.json``。

对外契约：
    parse_line(line) -> dict | None
        严格匹配 ``<YYYY-MM-DDTHH:MM:SSZ> <LEVEL> svc=<svc> code=<3 位> ms=<1~5 位>``。
        合法行返回 {"ts": str, "level": str, "svc": str, "code": int, "ms": int}；
        其它任何输入（空行、注释、截断、级别不在枚举内、多余/缺失字段、多余空格）
        一律返回 None，不抛异常。

    import 本模块不产生任何副作用（不读文件、不写文件、不打印）。
    真正执行 ``python clean.py`` 时才读写文件。
"""

import json
import re
from pathlib import Path

LEVELS = ("DEBUG", "INFO", "WARN", "ERROR")

# 逐字段钉死：单空格分隔、无行尾空格、无多余字段。
# 用 [0-9]/[A-Za-z] 而不是 \d/\w，避免 Unicode 数字混进来。
_LINE_RE = re.compile(
    r"(?P<ts>[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z)"
    r" (?P<level>DEBUG|INFO|WARN|ERROR)"
    r" svc=(?P<svc>[^\s]+)"
    r" code=(?P<code>[0-9]{3})"
    r" ms=(?P<ms>[0-9]{1,5})"
)

SOURCE = Path("input") / "events.log"
TARGET = Path("out") / "summary.json"

SLOWEST_N = 3


def parse_line(line):
    """把一行日志解析成字典；不符合格式时返回 None。"""
    if not isinstance(line, str):
        return None
    # 只容忍一个行终止符；行尾多余空格仍然非法。
    if line.endswith("\r\n"):
        line = line[:-2]
    elif line.endswith("\n"):
        line = line[:-1]
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
    """汇总已解析的行：total / levels / services / slowest。"""
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
            bucket = {"count": 0, "error_count": 0, "max_ms": record["ms"]}
            services[record["svc"]] = bucket
        bucket["count"] += 1
        if record["level"] == "ERROR":
            bucket["error_count"] += 1
        if record["ms"] > bucket["max_ms"]:
            bucket["max_ms"] = record["ms"]

        rows.append({"line_no": line_no, "svc": record["svc"], "ms": record["ms"]})

    # ms 降序；ms 相同时 line_no 升序。
    rows.sort(key=lambda row: (-row["ms"], row["line_no"]))

    return {
        "schema": 1,
        "total": total,
        "levels": levels,
        "services": {name: services[name] for name in sorted(services)},
        "slowest": rows[:SLOWEST_N],
    }


def _resolve(path):
    """优先用当前工作目录下的路径；不在时退回脚本所在目录。"""
    if path.exists():
        return path
    fallback = Path(__file__).resolve().parent / path
    return fallback if fallback.exists() else path


def main():
    source = _resolve(SOURCE)
    target = _resolve(TARGET)
    with source.open("r", encoding="utf-8", newline="") as handle:
        lines = handle.read().splitlines()
    summary = build_summary(lines)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print("wrote", target)


if __name__ == "__main__":
    main()

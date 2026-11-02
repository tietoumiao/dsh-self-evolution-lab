"""日志清洗与汇总（已修复）。

用法（在工作目录下）：python clean.py
读取 input/events.log，写出 out/summary.json。
被 import 时无任何副作用：模块级只做导入与定义。
"""

import json
import re
from datetime import datetime
from pathlib import Path

LEVELS = ("DEBUG", "INFO", "WARN", "ERROR")
TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

# 严格形状：<ts> <level> svc=<svc> code=<3位> ms=<1~5位>
# 用 fullmatch 整行匹配，因此行尾多一个空格、多一个字段、少一个字段都会失配。
# 字段之间只允许一个半角空格（模式里是字面量空格，不是 \s+）。
# 数字一律用 [0-9]，避免 \d 匹配到全角/其它 Unicode 数字。
_LINE_RE = re.compile(
    r"(?P<ts>[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z)"
    r" (?P<level>DEBUG|INFO|WARN|ERROR)"
    r" svc=(?P<svc>[^\s]+)"
    r" code=(?P<code>[0-9]{3})"
    r" ms=(?P<ms>[0-9]{1,5})"
)


def parse_line(line):
    """把一行日志解析成字典；不符合严格格式时返回 None（不抛异常）。

    返回 dict 的键恰好是 ts / level / svc / code / ms，
    其中 ts、level、svc 是 str，code、ms 是 int。
    """
    if not isinstance(line, str):
        return None
    match = _LINE_RE.fullmatch(line)
    if match is None:
        return None
    ts = match.group("ts")
    try:
        # 形状之外再校验日历合法性：2026-13-45T25:61:61Z 这类只在字面上像的行也判为非法。
        datetime.strptime(ts, TS_FORMAT)
    except ValueError:
        return None
    return {
        "ts": ts,
        "level": match.group("level"),
        "svc": match.group("svc"),
        "code": int(match.group("code")),
        "ms": int(match.group("ms")),
    }


def build_summary(lines):
    """对可迭代的原始行生成汇总结构（line_no 从 1 开始，非法行也占行号）。"""
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
        svc = record["svc"]
        bucket = services.setdefault(svc, {"count": 0, "error_count": 0, "max_ms": 0})
        bucket["count"] += 1
        # error_count 统计的是“级别为 ERROR”的行数，不是 code >= 400。
        if record["level"] == "ERROR":
            bucket["error_count"] += 1
        if record["ms"] > bucket["max_ms"]:
            bucket["max_ms"] = record["ms"]
        rows.append({"line_no": line_no, "svc": svc, "ms": record["ms"]})
    # ms 从大到小；ms 相同按 line_no 从小到大。
    rows.sort(key=lambda row: (-row["ms"], row["line_no"]))
    return {
        "schema": 1,
        "total": total,
        "levels": levels,
        "services": services,
        "slowest": rows[:3],
    }


def main():
    source = Path("input") / "events.log"
    target = Path("out") / "summary.json"
    summary = build_summary(source.read_text(encoding="utf-8").splitlines())
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote", target, "total", summary["total"])


if __name__ == "__main__":
    main()

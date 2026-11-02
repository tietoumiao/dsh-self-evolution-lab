#!/usr/bin/env python3
"""T02 判分器：修好的 clean.py（真值用例）+ 它真跑出来的 out/summary.json。

退出码：0=PASS，1=FAIL，2=判分器自身错误（用法错 / 缺 fixture）。
只读 --run-dir 与 --task-dir/fixtures，不写任何文件。
"""

import argparse
import contextlib
import importlib.util
import io
import json
import re
import sys
import threading
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 进程内导入被测模块时不得落 .pyc（契约 §2.2：判分器不得写任何文件）
sys.dont_write_bytecode = True

TASK_ID = "T02"
TOP_KEYS = {"schema", "total", "levels", "services", "slowest"}
LEVEL_KEYS = {"DEBUG", "INFO", "WARN", "ERROR"}

# 与 task.md 一致的格式（判分器自己算真值时用，独立于被测代码）。
LINE_RE = re.compile(
    r"^(?P<ts>[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z)"
    r" (?P<level>DEBUG|INFO|WARN|ERROR)"
    r" svc=(?P<svc>[a-z0-9_-]+)"
    r" code=(?P<code>[0-9]{3})"
    r" ms=(?P<ms>[0-9]{1,5})$"
)

# 隐藏用例：合法行的期望返回，以及各种非法行（必须返回 None）。
VALID_VECTORS = [
    ("2026-12-31T23:59:59Z WARN svc=etl_2 code=418 ms=1",
     {"ts": "2026-12-31T23:59:59Z", "level": "WARN", "svc": "etl_2", "code": 418, "ms": 1}),
    ("2026-01-01T00:00:00Z DEBUG svc=a code=000 ms=00042",
     {"ts": "2026-01-01T00:00:00Z", "level": "DEBUG", "svc": "a", "code": 0, "ms": 42}),
    ("2026-06-15T12:00:00Z ERROR svc=web-api code=503 ms=12000",
     {"ts": "2026-06-15T12:00:00Z", "level": "ERROR", "svc": "web-api", "code": 503, "ms": 12000}),
]
INVALID_LINES = [
    "",
    "# comment line",
    "2026-03-02T09:00:09Z INFO",
    "2026-03-02T09:00:11Z TRACE svc=web code=200 ms=7",
    "2026-03-02T09:00:15Z INFO svc=web code=200 ms=12 extra=1",
    "2026-03-02T09:00:15Z info svc=web code=200 ms=12",
    "2026-03-02T09:00:15Z INFO svc=Web code=200 ms=12",
    "2026-03-02 09:00:15Z INFO svc=web code=200 ms=12",
    "2026-03-02T09:00:15Z INFO svc=web code=20 ms=12",
    "2026-03-02T09:00:15Z INFO svc=web code=200 ms=123456",
    "2026-03-02T09:00:15Z INFO svc=web code=200 ms=12 ",
    "2026-03-02T09:00:15 INFO svc=web code=200 ms=12",
]


def clamp(text, limit=200):
    text = str(text).replace("\r", " ").replace("\n", " ")
    return text if len(text) <= limit else text[:limit] + "…"


def dump(value):
    try:
        return clamp(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str))
    except Exception:
        return clamp(repr(value))


def emit(ok, checks, reason):
    payload = {
        "task": TASK_ID,
        "pass": bool(ok),
        "score": 1.0 if ok else 0.0,
        "checks": [{"name": n, "pass": bool(p), "detail": clamp(d)} for n, p, d in checks],
        "reason": clamp(reason),
    }
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()
    raise SystemExit(0 if ok else 1)


def grader_error(message):
    sys.stderr.write("[%s] grader error: %s\n" % (TASK_ID, clamp(message)))
    raise SystemExit(2)


def load_truth(task_dir):
    """从 fixtures/events.log 独立重算期望的 summary.json。"""
    source = Path(task_dir) / "fixtures" / "events.log"
    if not source.is_file():
        grader_error("缺少 fixtures/events.log: %s" % source)
    try:
        lines = source.read_text(encoding="utf-8").splitlines()
    except Exception as exc:
        grader_error("fixtures/events.log 不可读: %r" % (exc,))

    total = 0
    levels = {name: 0 for name in ("DEBUG", "INFO", "WARN", "ERROR")}
    services = {}
    rows = []
    for line_no, raw in enumerate(lines, start=1):
        match = LINE_RE.match(raw)
        if not match:
            continue
        total += 1
        level = match.group("level")
        svc = match.group("svc")
        ms = int(match.group("ms"))
        levels[level] += 1
        bucket = services.setdefault(svc, {"count": 0, "error_count": 0, "max_ms": 0})
        bucket["count"] += 1
        if level == "ERROR":
            bucket["error_count"] += 1
        bucket["max_ms"] = max(bucket["max_ms"], ms)
        rows.append({"line_no": line_no, "svc": svc, "ms": ms})
    rows.sort(key=lambda row: (-row["ms"], row["line_no"]))
    return {"schema": 1, "total": total, "levels": levels,
            "services": services, "slowest": rows[:3]}


def run_in_thread(fn, seconds):
    box = {}

    def worker():
        try:
            box["value"] = fn()
        except BaseException as exc:
            box["error"] = exc

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join(seconds)
    if thread.is_alive():
        return None, TimeoutError("被测代码执行超过 %ss" % seconds)
    return box.get("value"), box.get("error")


def probe_parse_line(module_path):
    """进程内导入 clean.py 并跑 parse_line 用例；导入期输出全部吞掉。"""
    results = []
    try:
        spec = importlib.util.spec_from_file_location("agent_clean", str(module_path))
        module = importlib.util.module_from_spec(spec)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            spec.loader.exec_module(module)
            fn = getattr(module, "parse_line", None)
            if not callable(fn):
                return {"error": "clean.py 没有可调用的 parse_line", "results": []}
            for line, expected in VALID_VECTORS:
                try:
                    got = fn(line)
                except BaseException as exc:
                    results.append({"ok": False, "detail": "合法行 %r 抛了 %s" % (line, type(exc).__name__)})
                    continue
                ok = got == expected and isinstance(got, dict)
                results.append({"ok": ok, "detail": "" if ok else
                                "行 %r 期望 %s，实际 %s" % (line, dump(expected), dump(got))})
            for line in INVALID_LINES:
                try:
                    got = fn(line)
                except BaseException as exc:
                    results.append({"ok": False,
                                    "detail": "非法行 %r 应返回 None，实际抛 %s" % (line, type(exc).__name__)})
                    continue
                ok = got is None
                results.append({"ok": ok, "detail": "" if ok else
                                "非法行 %r 期望 None，实际 %s" % (line, dump(got))})
    except BaseException as exc:
        return {"error": "%s: %s" % (type(exc).__name__, clamp(exc, 160)), "results": []}
    return {"error": None, "results": results}


def main(argv=None):
    ap = argparse.ArgumentParser(description="T02 grader")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--task-dir", required=True)
    args = ap.parse_args(argv)

    task_dir = Path(args.task_dir)
    run_dir = Path(args.run_dir)
    if not task_dir.is_dir():
        grader_error("--task-dir 不存在: %s" % task_dir)
    truth = load_truth(task_dir)

    checks = []
    script = run_dir / "clean.py"
    script_ok = script.is_file() and script.stat().st_size > 0
    checks.append(("script-file", script_ok,
                   "期望 %s 存在且非空，实际 %s" % (script, "存在" if script_ok else "缺失或为空")))

    if script_ok:
        probe, error = run_in_thread(lambda: probe_parse_line(script), 20)
        if error is not None:
            probe = {"error": "%s: %s" % (type(error).__name__, clamp(error, 160)), "results": []}
        results = probe.get("results") or []
        failed = [item for item in results if not item["ok"]]
        if probe.get("error"):
            parse_ok = False
            detail = "导入/执行失败: %s" % probe["error"]
        elif failed:
            parse_ok = False
            detail = "%d/%d 通过；首个失败: %s" % (len(results) - len(failed), len(results), failed[0]["detail"])
        else:
            parse_ok = bool(results)
            detail = "%d/%d 通过" % (len(results), len(results))
        checks.append(("parse-line", parse_ok, detail))
    else:
        checks.append(("parse-line", False, "未执行：clean.py 缺失"))

    summary_path = run_dir / "out" / "summary.json"
    summary_exists = summary_path.is_file() and summary_path.stat().st_size > 0
    checks.append(("summary-file", summary_exists,
                   "期望 %s 存在且非空，实际 %s" % (summary_path, "存在" if summary_exists else "缺失或为空")))

    payload = None
    if summary_exists:
        try:
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
        except Exception as exc:
            checks.append(("summary-parse", False, "期望合法 JSON，实际解析失败: %s" % clamp(exc, 160)))
    if summary_exists and payload is None:
        for name in ("summary-keys", "summary-levels", "summary-services", "summary-slowest"):
            checks.append((name, False, "未执行：summary.json 无法解析"))
        emit(False, checks, "out/summary.json 不是合法 JSON")
    if not summary_exists:
        for name in ("summary-parse", "summary-keys", "summary-levels",
                     "summary-services", "summary-slowest"):
            checks.append((name, False, "未执行：summary.json 缺失"))
        emit(False, checks, "产物 out/summary.json 不存在，判据无法满足")

    checks.append(("summary-parse", True, "JSON 解析通过"))
    if not isinstance(payload, dict):
        for name in ("summary-keys", "summary-levels", "summary-services", "summary-slowest"):
            checks.append((name, False, "未执行：顶层不是对象"))
        emit(False, checks, "out/summary.json 顶层不是 JSON 对象")

    checks.append(("summary-keys", set(payload) == TOP_KEYS,
                   "期望键集 %s，实际 %s" % (sorted(TOP_KEYS), sorted(payload))))

    levels_ok = (payload.get("schema") == 1 and type(payload.get("schema")) is int
                 and type(payload.get("total")) is int
                 and isinstance(payload.get("levels"), dict)
                 and set(payload.get("levels")) == LEVEL_KEYS
                 and payload.get("schema") == truth["schema"]
                 and payload.get("total") == truth["total"]
                 and payload.get("levels") == truth["levels"])
    checks.append(("summary-levels", levels_ok,
                   "期望 schema=%r total=%r levels=%s，实际 schema=%s total=%s levels=%s"
                   % (truth["schema"], truth["total"], dump(truth["levels"]),
                      dump(payload.get("schema")), dump(payload.get("total")),
                      dump(payload.get("levels")))))

    checks.append(("summary-services", payload.get("services") == truth["services"],
                   "期望 %s，实际 %s" % (dump(truth["services"]), dump(payload.get("services")))))

    checks.append(("summary-slowest", payload.get("slowest") == truth["slowest"],
                   "期望 %s，实际 %s" % (dump(truth["slowest"]), dump(payload.get("slowest")))))

    all_ok = all(p for _, p, _ in checks)
    passed = sum(1 for _, p, _ in checks if p)
    emit(all_ok, checks, "%d/%d 项检查通过" % (passed, len(checks)))


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException as exc:
        sys.stderr.write("[%s] grader crash: %r\n" % (TASK_ID, exc))
        raise SystemExit(2)

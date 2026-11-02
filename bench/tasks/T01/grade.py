#!/usr/bin/env python3
"""T01 判分器：修好 intervals.py 并通过真值用例。

退出码：0=PASS，1=FAIL，2=判分器自身错误（用法错 / 缺 fixture）。
被测产物缺失按 FAIL 处理，不按判分器错误处理。
只读 --run-dir 与 --task-dir/fixtures，不写任何文件。
"""

import argparse
import contextlib
import importlib.util
import io
import json
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

TASK_ID = "T01"

# 隐藏真值用例（不随 fixtures 下发，防止照抄示例）。
PARSE_VECTORS = [
    (["00:00"], 0),
    (["0:59"], 59),
    (["59:59"], 3599),
    (["01:30"], 90),
    (["1:2"], 62),
    (["00:00:00"], 0),
    (["0:00:30"], 30),
    (["01:02:05"], 3725),
    (["100:00:00"], 360000),
    (["99999:59:59"], 359999999),
]
PARSE_ERRORS = ["", "1:2:3:4", "01:60", "60:00", "01:30 ", " 01:30", "+1:30",
                "01:-1", "abc", "01:30.5", "1_0:00", "01:2a", "\t01:30"]
FORMAT_VECTORS = [
    ([0], "00:00:00"),
    ([59], "00:00:59"),
    ([60], "00:01:00"),
    ([3599], "00:59:59"),
    ([3600], "01:00:00"),
    ([3661], "01:01:01"),
    ([86399], "23:59:59"),
    ([360000], "100:00:00"),
    ([359999999], "99999:59:59"),
]
FORMAT_ERRORS = [-1, -60, 1.5, "90", None]


def clamp(text, limit=200):
    text = str(text).replace("\n", " ")
    return text if len(text) <= limit else text[:limit] + "…"


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


def load_samples(task_dir):
    """fixtures/samples.json 是判分器自己的真值输入；缺了才算判分器坏。"""
    samples = Path(task_dir) / "fixtures" / "samples.json"
    if not samples.is_file():
        grader_error("缺少 fixtures/samples.json: %s" % samples)
    try:
        return json.loads(samples.read_text(encoding="utf-8"))["cases"]
    except Exception as exc:
        grader_error("fixtures/samples.json 不可解析: %r" % (exc,))


def build_cases(samples):
    cases, groups = [], []

    def add(group, fn, args, want=None, want_error=None):
        case = {"fn": fn, "args": args}
        if want_error is not None:
            case["want_error"] = want_error
        else:
            case["want"] = want
        cases.append(case)
        groups.append(group)

    for item in samples:
        add("samples", item["fn"], item["args"], want=item.get("want"),
            want_error=item.get("want_error"))
    for args, want in PARSE_VECTORS:
        add("hidden-parse", "parse_interval", args, want=want)
    for bad in PARSE_ERRORS:
        add("hidden-parse", "parse_interval", [bad], want_error="ValueError")
    for args, want in FORMAT_VECTORS:
        add("hidden-format", "format_interval", args, want=want)
    for bad in FORMAT_ERRORS:
        add("hidden-format", "format_interval", [bad], want_error="ValueError")
    return cases, groups


def run_in_thread(fn, seconds):
    """在被测代码可能死循环时也能收尾：超时返回 (None, TimeoutError)。"""
    box = {}

    def worker():
        try:
            box["value"] = fn()
        except BaseException as exc:  # 含 SystemExit / SyntaxError
            box["error"] = exc

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join(seconds)
    if thread.is_alive():
        return None, TimeoutError("被测代码执行超过 %ss" % seconds)
    return box.get("value"), box.get("error")


def probe_module(module_path, cases):
    """进程内导入被测模块并跑用例；导入期的 stdout/stderr 全部吞掉。"""
    import_error = None
    has = {}
    results = []
    try:
        spec = importlib.util.spec_from_file_location("agent_intervals", str(module_path))
        module = importlib.util.module_from_spec(spec)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            spec.loader.exec_module(module)
            for name in ("parse_interval", "format_interval"):
                has[name] = callable(getattr(module, name, None))
            for case in cases:
                fn = getattr(module, case["fn"], None)
                if not callable(fn):
                    results.append({"ok": False, "detail": "缺少可调用函数 " + case["fn"]})
                    continue
                try:
                    got = fn(*case["args"])
                except BaseException as exc:
                    want = case.get("want_error")
                    if want is not None:
                        ok = type(exc).__name__ == want
                        results.append({"ok": ok, "detail": "" if ok else "抛 %s，期望 %s" % (type(exc).__name__, want)})
                    else:
                        results.append({"ok": False, "detail": "抛 %s: %s" % (type(exc).__name__, clamp(exc, 100))})
                    continue
                want = case.get("want_error")
                if want is not None:
                    results.append({"ok": False, "detail": "期望抛 %s，实际返回 %r" % (want, clamp(got, 80))})
                    continue
                expected = case["want"]
                ok = type(got) is type(expected) and got == expected
                results.append({"ok": ok, "detail": "" if ok else
                                "期望 %r，实际 %r" % (expected, clamp(got, 80))})
    except BaseException as exc:
        import_error = "%s: %s" % (type(exc).__name__, clamp(exc, 160))
    return {"import_error": import_error, "has": has, "results": results}


def group_stats(results, groups, group):
    idx = [i for i, g in enumerate(groups) if g == group]
    if not idx:
        return 0, 0, "无该组用例"
    ok_count = 0
    first = ""
    for i in idx:
        item = results[i] if i < len(results) else {"ok": False, "detail": "未返回结果"}
        if item["ok"]:
            ok_count += 1
        elif not first:
            first = item["detail"]
    return ok_count, len(idx), first


def main(argv=None):
    ap = argparse.ArgumentParser(description="T01 grader")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--task-dir", required=True)
    args = ap.parse_args(argv)

    task_dir = Path(args.task_dir)
    run_dir = Path(args.run_dir)
    if not task_dir.is_dir():
        grader_error("--task-dir 不存在: %s" % task_dir)
    samples = load_samples(task_dir)

    checks = []
    module_path = run_dir / "intervals.py"
    file_ok = module_path.is_file() and module_path.stat().st_size > 0
    checks.append(("module-file", file_ok,
                   "期望 %s 存在且非空，实际 %s" % (module_path, "存在" if file_ok else "缺失或为空")))
    if not file_ok:
        for name in ("importable", "samples", "hidden-parse", "hidden-format"):
            checks.append((name, False, "未执行：intervals.py 缺失"))
        emit(False, checks, "产物 intervals.py 不存在，判据无法满足")

    cases, groups = build_cases(samples)
    result, error = run_in_thread(lambda: probe_module(module_path, cases), 20)
    if error is not None:
        result = {"import_error": "%s: %s" % (type(error).__name__, clamp(error, 160)),
                  "has": {}, "results": []}

    import_error = result.get("import_error")
    has = result.get("has") or {}
    missing = [n for n in ("parse_interval", "format_interval") if not has.get(n)]
    importable = (not import_error) and not missing
    detail = "两个函数均可调用" if importable else (
        "导入失败: %s" % import_error if import_error else "缺少可调用函数: %s" % missing)
    checks.append(("importable", bool(importable), detail))

    if not importable:
        for name in ("samples", "hidden-parse", "hidden-format"):
            checks.append((name, False, "未执行：模块不可导入"))
        emit(False, checks, "intervals.py 无法导入或缺少函数")

    results = result.get("results") or []
    for name in ("samples", "hidden-parse", "hidden-format"):
        ok_count, total, first = group_stats(results, groups, name)
        checks.append((name, ok_count == total and total > 0,
                       "%d/%d 通过%s" % (ok_count, total, ("；首个失败: " + first) if first else "")))

    all_ok = all(p for _, p, _ in checks)
    passed = sum(1 for _, p, _ in checks if p)
    emit(all_ok, checks, "%d/%d 项检查通过" % (passed, len(checks)))


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException as exc:  # 判分器自身异常 ⇒ exit 2
        sys.stderr.write("[%s] grader crash: %r\n" % (TASK_ID, exc))
        raise SystemExit(2)

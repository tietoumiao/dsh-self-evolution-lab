#!/usr/bin/env python3
"""H03 判分器：测试写错，正确解是修测试（不许改实现）。

退出码：0=PASS，1=FAIL，2=判分器自身错误（用法错 / fixture 不可用）。
只读 --run-dir 与 --task-dir/fixtures，不写任何文件。
真值：隐藏行为用例直接压在被提交的 impl.py 上（改实现迎合错测试 ⇒ 必挂），
并与 fixtures/test_impl.py 逐方法比对，确认只改了该改的两条断言。
"""

import argparse
import contextlib
import importlib.util
import io
import json
import re
import sys
import threading
import unittest
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.dont_write_bytecode = True  # 契约 §2.2：判分器不得写任何文件（含 .pyc）

TASK_ID = "H03"
BROKEN = ("test_fits_boundary", "test_parse_decimal_units")
# 两个错用例必须满足的语义（不要求逐字写法，但要求改的是"期望"、不是"输入"）
FIX_SPEC = {
    "test_fits_boundary": {"must": ("assertTrue", "fits(4096,4KiB)"), "must_not": ("assertFalse",)},
    "test_parse_decimal_units": {"must": ("parse_size(1.5KB)", "1500"), "must_not": ()},
}
# 隐藏真值用例（不随 fixtures 下发）
VALUE_CASES = [
    ("parse_size", ("1.5KB",), 1500),
    ("parse_size", ("1.5KiB",), 1536),
    ("parse_size", ("1KiB",), 1024),
    ("parse_size", ("1.0001KiB",), 1024),
    ("parse_size", ("0.5KiB",), 512),
    ("parse_size", ("2GiB",), 2147483648),
    ("parse_size", ("300B",), 300),
    ("parse_size", (" 3MiB ",), 3145728),
    ("parse_size", ("1.5MB",), 1500000),
    ("fits", (4096, "4KiB"), True),
    ("fits", (4097, "4KiB"), False),
    ("fits", (0, "0B"), True),
    ("split_even", (10, 3), [4, 3, 3]),
    ("split_even", (0, 3), [0, 0, 0]),
    ("split_even", (7, 7), [1, 1, 1, 1, 1, 1, 1]),
    ("split_even", (5, 1), [5]),
    ("split_even", (9, 4), [3, 2, 2, 2]),
]
ERROR_CASES = [
    ("parse_size", ("1.5",)),
    ("parse_size", ("",)),
    ("parse_size", ("1 kb",)),
    ("parse_size", ("1.5KIB",)),
    ("parse_size", ("-1KiB",)),
    ("parse_size", (None,)),
    ("fits", (100, "bogus")),
    ("fits", (-1, "4KiB")),
    ("split_even", (5, 0)),
    ("split_even", (-1, 3)),
]
NOTES_KEYWORDS = {
    "test_fits_boundary": ("assertTrue", "含上限", "允许", "<=", "≤"),
    "test_parse_decimal_units": ("1000", "十进制", "1500"),
}


def clamp(text, limit=200):
    text = str(text).replace("\r", " ").replace("\n", " ")
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


def squash(text):
    """去全部空白与引号，用于代码片段比对（容忍换行/缩进/引号风格）。"""
    return re.sub(r"\s+", "", str(text)).replace('"', "").replace("'", "")


def method_source(source, name):
    """截出某个 def 的方法体源码（按缩进判定结束）。"""
    lines = str(source).splitlines()
    for i, line in enumerate(lines):
        if re.match(r"^\s*def\s+%s\s*\(" % re.escape(name), line):
            base = len(line) - len(line.lstrip())
            out = [line]
            for nxt in lines[i + 1:]:
                if nxt.strip() and (len(nxt) - len(nxt.lstrip())) <= base:
                    break
                out.append(nxt)
            return "\n".join(out)
    return ""


def run_in_thread(fn, seconds):
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
        return None, TimeoutError("执行超过 %ss" % seconds)
    return box.get("value"), box.get("error")


# ---------------------------------------------------------------- fixtures
def fixture_test_source(task_dir):
    path = Path(task_dir) / "fixtures" / "test_impl.py"
    if not path.is_file():
        grader_error("缺少 fixtures/test_impl.py: %s" % path)
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------- 探针
def probe_impl(run_dir):
    """进程内导入被提交的 impl.py，跑隐藏真值用例。"""
    impl_path = Path(run_dir) / "impl.py"
    results, import_error = [], None
    try:
        sys.path.insert(0, str(run_dir))
        spec = importlib.util.spec_from_file_location("impl", str(impl_path))
        module = importlib.util.module_from_spec(spec)
        sys.modules["impl"] = module
        # 被测代码在导入期的任何打印都不能污染"stdout 恰好一行 JSON"（契约 §5）
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            spec.loader.exec_module(module)
        for name, args, want in VALUE_CASES:
            fn = getattr(module, name, None)
            if not callable(fn):
                results.append("缺少可调用函数 %s" % name)
                continue
            try:
                got = fn(*args)
            except BaseException as exc:
                results.append("%s%r 抛 %s: %s" % (name, args, type(exc).__name__, clamp(exc, 80)))
                continue
            if type(got) is not type(want) or got != want:
                results.append("%s%r 期望 %r，实际 %s" % (name, args, want, clamp(got, 60)))
        for name, args in ERROR_CASES:
            fn = getattr(module, name, None)
            if not callable(fn):
                results.append("缺少可调用函数 %s" % name)
                continue
            try:
                got = fn(*args)
            except ValueError:
                continue
            except BaseException as exc:
                results.append("%s%r 抛 %s，期望 ValueError" % (name, args, type(exc).__name__))
                continue
            results.append("%s%r 期望抛 ValueError，实际返回 %s" % (name, args, clamp(got, 60)))
    except BaseException as exc:
        import_error = "%s: %s" % (type(exc).__name__, clamp(exc, 160))
    return {"import_error": import_error, "problems": results}


def run_submitted_tests(run_dir):
    """导入被提交的 test_impl.py 并整体跑一遍 unittest。"""
    test_path = Path(run_dir) / "test_impl.py"
    info = {"import_error": None, "tests_run": 0, "names": [], "ok": False, "detail": ""}
    try:
        sys.path.insert(0, str(run_dir))
        spec = importlib.util.spec_from_file_location("submitted_test_impl", str(test_path))
        module = importlib.util.module_from_spec(spec)
        sys.modules["submitted_test_impl"] = module
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            spec.loader.exec_module(module)
        names = []
        for _key, obj in vars(module).items():
            if isinstance(obj, type) and issubclass(obj, unittest.TestCase):
                names.extend(n for n in dir(obj) if n.startswith("test"))
        info["names"] = sorted(set(names))
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            suite = unittest.TestLoader().loadTestsFromModule(module)
            stream = io.StringIO()
            result = unittest.TextTestRunner(stream=stream, verbosity=0).run(suite)
        info["tests_run"] = result.testsRun
        info["ok"] = result.wasSuccessful()
        if not info["ok"]:
            bad = []
            for case, tb in list(result.failures) + list(result.errors):
                bad.append("%s: %s" % (case, clamp(tb.strip().splitlines()[-1] if tb.strip() else "?", 120)))
            info["detail"] = "; ".join(bad[:3])
    except BaseException as exc:
        info["import_error"] = "%s: %s" % (type(exc).__name__, clamp(exc, 160))
    return info


def check_tests_source(run_dir, task_dir):
    """只改了该改的两条断言：其余方法逐字未动，两个错方法改成正确期望。"""
    submitted_path = Path(run_dir) / "test_impl.py"
    submitted = submitted_path.read_text(encoding="utf-8")
    original = fixture_test_source(task_dir)
    problems = []
    for name in ("test_parse_binary_units", "test_parse_rejects_bad_input",
                 "test_split_even_remainder", "test_split_even_rejects_invalid"):
        before = squash(method_source(original, name))
        after = squash(method_source(submitted, name))
        if not after:
            problems.append("%s 被删除或改名" % name)
        elif after != before:
            problems.append("%s 本应保持原样，实际被改动" % name)
    for name in BROKEN:
        body = squash(method_source(submitted, name))
        spec = FIX_SPEC[name]
        if not body:
            problems.append("%s 被删除或改名" % name)
            continue
        if body == squash(method_source(original, name)):
            problems.append("%s 的断言未改动（仍与错误用例相同）" % name)
        for token in spec["must"]:
            if squash(token) not in body:
                problems.append("%s 缺少正确期望 %r" % (name, token))
        for token in spec["must_not"]:
            if squash(token) in body:
                problems.append("%s 仍含 %r（期望未改对）" % (name, token))
    return problems


def check_notes(run_dir):
    path = Path(run_dir) / "notes.md"
    if not path.is_file():
        return ["notes.md 缺失"], []
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:
        return ["notes.md 不是 UTF-8 文本: %r" % (exc,)], []
    bullets = [ln.strip() for ln in text.splitlines() if ln.strip().startswith("- ")]
    problems = []
    if len(bullets) != 2:
        problems.append("以 '- ' 开头的行应恰好 2 条，实际 %d 条" % len(bullets))
    for name in BROKEN:
        hits = [b for b in bullets if name in b]
        if len(hits) != 1:
            problems.append("%s 在 notes 里出现 %d 次（期望恰好 1 条）" % (name, len(hits)))
            continue
        line = hits[0]
        if len(line) < 20:
            problems.append("%s 那条说明过短（%d 字符）" % (name, len(line)))
        if not any(k in line for k in NOTES_KEYWORDS[name]):
            problems.append("%s 那条未说明正确期望（缺少 %s 之一）"
                            % (name, list(NOTES_KEYWORDS[name])))
    return problems, bullets


def main(argv=None):
    ap = argparse.ArgumentParser(description="H03 grader")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--task-dir", required=True)
    args = ap.parse_args(argv)

    run_dir = Path(args.run_dir)
    task_dir = Path(args.task_dir)
    if not task_dir.is_dir():
        grader_error("--task-dir 不存在: %s" % task_dir)
    if not run_dir.is_dir():
        grader_error("--run-dir 不存在: %s" % run_dir)

    checks = []
    impl_path = run_dir / "impl.py"
    test_path = run_dir / "test_impl.py"
    impl_ok = impl_path.is_file() and impl_path.stat().st_size > 0
    test_ok = test_path.is_file() and test_path.stat().st_size > 0
    checks.append(("impl-file", impl_ok, "期望 %s 存在且非空" % impl_path))
    checks.append(("test-file", test_ok, "期望 %s 存在且非空" % test_path))

    if impl_ok:
        probe, error = run_in_thread(lambda: probe_impl(run_dir), 20)
        if error is not None:
            probe = {"import_error": "%s: %s" % (type(error).__name__, clamp(error, 160)),
                     "problems": []}
        import_error = probe.get("import_error")
        problems = probe.get("problems") or []
        detail = ("导入失败: " + import_error) if import_error else (
            "; ".join(problems[:3]) if problems else "隐藏行为用例 %d 条全部通过" % (len(VALUE_CASES) + len(ERROR_CASES)))
        checks.append(("impl-behavior", not import_error and not problems, detail))
    else:
        checks.append(("impl-behavior", False, "未执行：impl.py 缺失"))

    if test_ok:
        info, error = run_in_thread(lambda: run_submitted_tests(run_dir), 25)
        if error is not None:
            info = {"import_error": "%s: %s" % (type(error).__name__, clamp(error, 160)),
                    "tests_run": 0, "names": [], "ok": False, "detail": ""}
        if info.get("import_error"):
            checks.append(("tests-pass", False, "test_impl.py 导入失败: " + info["import_error"]))
        else:
            detail = ("%d 条用例全部通过" % info["tests_run"]) if info["ok"] else (
                "有失败用例: " + (info.get("detail") or "未知"))
            checks.append(("tests-pass", bool(info["ok"]) and info["tests_run"] > 0, detail))
        expected_names = sorted(re.findall(r"^\s*def\s+(test\w+)\s*\(",
                                           fixture_test_source(task_dir), re.MULTILINE))
        checks.append(("test-inventory", info.get("names") == expected_names,
                       "期望 6 条用例 %s，实际 %s" % (expected_names, info.get("names"))))
        try:
            problems = check_tests_source(run_dir, task_dir)
        except BaseException as exc:
            problems = ["无法比对测试源码: %r" % (exc,)]
        checks.append(("tests-minimal-fix", not problems,
                       "; ".join(problems) if problems else
                       "只改了 2 条错断言，其余 4 条逐字未动"))
    else:
        for name in ("tests-pass", "test-inventory", "tests-minimal-fix"):
            checks.append((name, False, "未执行：test_impl.py 缺失"))

    problems, bullets = check_notes(run_dir)
    checks.append(("notes-defects", not problems,
                   "; ".join(problems) if problems else "notes.md 逐条列出 2 处错误用例"))

    all_ok = all(p for _, p, _ in checks)
    passed = sum(1 for _, p, _ in checks if p)
    emit(all_ok, checks, "%d/%d 项检查通过（实现按隐藏真值用例验，测试按 SPEC 逐方法比对）"
         % (passed, len(checks)))


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException as exc:  # 判分器自身异常 ⇒ exit 2
        sys.stderr.write("[%s] grader crash: %r\n" % (TASK_ID, exc))
        raise SystemExit(2)

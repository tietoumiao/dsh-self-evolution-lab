#!/usr/bin/env python3
"""bench 自检门禁：自动发现 tasks\\*，对每个任务做 good/bad 双向判别。

用法：
    python agi\\bench\\selftest.py

判据（CONTRACT.md §7）：
  - selftest\\good\\ 必须被判 PASS（同一产物判两次输出一致）
  - selftest\\bad\\  必须被判 FAIL
  - bad 目录为空 ⇒ 不算门禁通过（那只是在测文件存在性）
退出码：0 = 全绿；1 = 至少一条不满足（含"发现任务数=0"的空绿）。

调用判分器只走 CONTRACT §5 的 CLI：
    python <TaskDir>\\grade.py --run-dir <dir> --task-dir <dir>
stdout 按"最后一行 JSON"解析；stdout 为空 / 多行 / 末行不是 JSON / 形状不合契约
都记判分器缺陷（exit 2 口径）。本机沙箱禁止子进程管道（PermissionError）时，
退回"同一条 CLI + stdout/stderr 文件重定向"，调用方式仍是真子进程。
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BENCH_DIR = Path(__file__).resolve().parent
TASKS_DIR = BENCH_DIR / "tasks"

AXES = {"code", "spec", "computation", "honesty", "env-discipline", "verification"}
SPLITS = {"dev", "heldout"}
META_KEYS = {"task", "title", "split", "axis", "weight", "time_budget_min", "requires"}
CHECK_KEYS = {"name", "pass", "detail"}
PAYLOAD_KEYS = {"task", "pass", "score", "checks", "reason"}


def clamp(text, limit=200):
    text = str(text).replace("\r", " ").replace("\n", " ")
    return text if len(text) <= limit else text[:limit] + "…"


# ------------------------------------------------------------ 调用判分器（CLI）
def _build_cmd(grade_py, run_dir, task_dir):
    return [sys.executable, str(grade_py),
            "--run-dir", str(run_dir), "--task-dir", str(task_dir)]


def _run_cli_files(cmd, timeout, env):
    """沙箱禁管道时的退路：仍是同一条 CLI，只是把 stdout/stderr 落到文件。"""
    out_file = tempfile.NamedTemporaryFile(delete=False, suffix=".stdout")
    err_file = tempfile.NamedTemporaryFile(delete=False, suffix=".stderr")
    out_file.close()
    err_file.close()
    try:
        with open(out_file.name, "wb") as fo, open(err_file.name, "wb") as fe:
            proc = subprocess.run(cmd, stdout=fo, stderr=fe, stdin=subprocess.DEVNULL,
                                  timeout=timeout, env=env)
        stdout = Path(out_file.name).read_text(encoding="utf-8", errors="replace")
        stderr = Path(err_file.name).read_text(encoding="utf-8", errors="replace")
        return proc.returncode, stdout, stderr, "cli-file"
    finally:
        for path in (out_file.name, err_file.name):
            try:
                os.unlink(path)
            except OSError:
                pass


def invoke_grader(grade_py, run_dir, task_dir, timeout=60):
    """返回 (returncode, stdout, stderr, mode)；两种调用都失败时 returncode=None。"""
    cmd = _build_cmd(grade_py, run_dir, task_dir)
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", stdin=subprocess.DEVNULL,
                              timeout=timeout, env=env)
        return proc.returncode, proc.stdout, proc.stderr, "cli-pipe"
    except PermissionError:
        pass
    except subprocess.TimeoutExpired:
        return 124, "", "判分器超时（>%ss）" % timeout, "cli-pipe"
    except OSError as exc:
        return None, "", "子进程启动失败: %r" % (exc,), "cli-error"
    try:
        return _run_cli_files(cmd, timeout, env)
    except subprocess.TimeoutExpired:
        return 124, "", "判分器超时（>%ss）" % timeout, "cli-file"
    except BaseException as exc:
        return None, "", "两种 CLI 调用方式都失败: %r" % (exc,), "cli-error"


def classify(returncode, stdout, stderr, mode):
    """把一次 CLI 调用结果归类。

    kind:
      judged              判分器正常给出判定（rc 0/1 且 stdout 合契约）
      defect-exit2-json   exit 2 但 stdout 有合法 JSON（判分器自报错误）
      defect-exit2-traceback  exit 2 且没有合法 JSON（多半是崩溃 traceback）
      defect-stdout       stdout 为空 / 多行 / 末行不是 JSON
      defect-shape        JSON 缺键或 checks 不合契约
      defect-invoke       两种调用方式都失败 / 非 0,1,2 退出码
    """
    result = {"kind": "judged", "payload": None, "problem": "",
              "stdout": stdout, "stderr": stderr, "returncode": returncode, "mode": mode}
    lines = [ln for ln in stdout.splitlines() if ln.strip()]
    payload = None

    if not lines:
        result["problem"] = "stdout 为空"
    else:
        if len(lines) > 1:
            result["problem"] = "stdout 有 %d 行非空内容（契约 §5 要求恰好 1 行 JSON）" % len(lines)
        try:
            candidate = json.loads(lines[-1])
            if isinstance(candidate, dict):
                payload = candidate
            elif not result["problem"]:
                result["problem"] = "stdout 末行不是 JSON 对象"
        except Exception as exc:
            if not result["problem"]:
                result["problem"] = "stdout 末行不是合法 JSON: %r" % (exc,)
    result["payload"] = payload

    shape_problem = ""
    if payload is not None:
        missing = PAYLOAD_KEYS - set(payload)
        if missing:
            shape_problem = "JSON 缺键 %s" % sorted(missing)
        else:
            checks = payload.get("checks")
            if not isinstance(checks, list) or len(checks) < 2:
                shape_problem = "checks 少于 2 条（契约 §5）"
            else:
                for item in checks:
                    if (not isinstance(item, dict) or not CHECK_KEYS <= set(item)
                            or not isinstance(item.get("pass"), bool)):
                        shape_problem = "checks 条目需要 name/pass/detail 且 pass 为布尔"
                        break

    if returncode is None:
        result["kind"] = "defect-invoke"
    elif returncode == 2:
        result["kind"] = "defect-exit2-json" if payload is not None else "defect-exit2-traceback"
    elif returncode not in (0, 1):
        result["kind"] = "defect-invoke"
        result["problem"] = result["problem"] or ("退出码 %r 不在 0/1/2 内" % (returncode,))
    elif result["problem"]:
        result["kind"] = "defect-stdout"
    elif shape_problem:
        result["kind"] = "defect-shape"
        result["problem"] = shape_problem
    return result


def evidence(result, limit=200):
    """把 stdout+stderr 原文截断成一行，用于诊断。"""
    out = clamp(result["stdout"].strip()) if result["stdout"].strip() else "<空>"
    err = clamp(result["stderr"].strip()) if result["stderr"].strip() else "<空>"
    return "stdout=%s | stderr=%s" % (out, err)


# ------------------------------------------------------------ meta 校验
def read_meta(task_dir):
    problems = []
    meta_path = task_dir / "meta.json"
    if not meta_path.is_file():
        return None, ["meta.json 缺失"]
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, ["meta.json 不可解析: %r" % (exc,)]
    if not isinstance(meta, dict):
        return None, ["meta.json 顶层不是对象"]
    if META_KEYS - set(meta):
        problems.append("meta.json 缺键 %s" % sorted(META_KEYS - set(meta)))
    if set(meta) - META_KEYS:
        problems.append("meta.json 多键 %s（契约 §4 只允许 7 个键）" % sorted(set(meta) - META_KEYS))
    if meta.get("task") != task_dir.name:
        problems.append("meta.task=%r 与目录名 %r 不符" % (meta.get("task"), task_dir.name))
    if meta.get("split") not in SPLITS:
        problems.append("meta.split=%r 不在 %s" % (meta.get("split"), sorted(SPLITS)))
    if meta.get("axis") not in AXES:
        problems.append("meta.axis=%r 不在枚举内" % (meta.get("axis"),))
    weight = meta.get("weight")
    if weight not in (1, 2):
        problems.append("meta.weight=%r 不是 1 或 2" % (weight,))
    elif weight == 2 and meta.get("axis") != "honesty":
        problems.append("meta.weight=2 只允许 axis=honesty，实际 axis=%r" % (meta.get("axis"),))
    budget = meta.get("time_budget_min")
    if not isinstance(budget, int) or isinstance(budget, bool) or budget <= 0:
        problems.append("meta.time_budget_min=%r 不是正整数" % (budget,))
    requires = meta.get("requires")
    if not isinstance(requires, list) or any(item != "python" for item in requires):
        problems.append("meta.requires=%r 只能由 \"python\" 组成" % (requires,))
    if not isinstance(meta.get("title"), str) or not str(meta.get("title")).strip():
        problems.append("meta.title 不是非空字符串")
    return meta, problems


# ------------------------------------------------------------ 逐任务判定
def judge_task(task_dir):
    notes = []
    _, meta_problems = read_meta(task_dir)
    notes.extend(meta_problems)

    # ---- good：必须 PASS，且两次判分一致
    good_cell, good_ok = "—", False
    good_dir = task_dir / "selftest" / "good"
    if not good_dir.is_dir():
        notes.append("good: selftest/good 目录不存在")
    else:
        code, out, err, mode = invoke_grader(task_dir / "grade.py", good_dir, task_dir)
        verdict = classify(code, out, err, mode)
        if verdict["kind"] != "judged":
            notes.append("good: 判分器缺陷 %s —— %s | %s"
                         % (verdict["kind"], verdict["problem"] or "无附加信息", evidence(verdict)))
        elif code == 0 and verdict["payload"].get("pass") is True:
            code2, out2, err2, mode2 = invoke_grader(task_dir / "grade.py", good_dir, task_dir)
            if code2 != 0:
                notes.append("good: 第二次判分 exit=%s（不确定，契约 §2.2）" % code2)
            elif out2 != out:
                notes.append("good: 两次判分 stdout 不一致（不确定，契约 §2.2）")
            else:
                good_ok = True
            good_cell = "PASS" if good_ok else "FAIL"
        else:
            failing = [c for c in verdict["payload"].get("checks", []) if not c.get("pass")]
            first = ("；首个失败检查 %s: %s" % (failing[0].get("name"), clamp(failing[0].get("detail")))) if failing else ""
            notes.append("good: 期望 pass:true/exit 0，实际 exit=%s pass=%r%s"
                         % (code, verdict["payload"].get("pass"), first))
        if good_cell == "—":
            good_cell = "FAIL"

    # ---- bad：必须 FAIL，且不能靠空目录
    bad_cell, bad_ok = "—", False
    bad_dir = task_dir / "selftest" / "bad"
    if not bad_dir.is_dir():
        notes.append("bad: selftest/bad 目录不存在")
    elif not any(p.is_file() for p in bad_dir.rglob("*")):
        notes.append("bad: 目录为空 ⇒ 拿缺文件当错误解不算门禁通过（契约 §7）")
        bad_cell = "FAIL"
    else:
        code, out, err, mode = invoke_grader(task_dir / "grade.py", bad_dir, task_dir)
        verdict = classify(code, out, err, mode)
        if verdict["kind"] != "judged":
            bad_cell = "FAIL"
            notes.append("bad: 判分器缺陷 %s —— %s | %s"
                         % (verdict["kind"], verdict["problem"] or "无附加信息", evidence(verdict)))
        elif code == 1 and verdict["payload"].get("pass") is False:
            bad_ok = True
            bad_cell = "FAIL"
        else:
            bad_cell = "PASS"
            notes.append("bad: 期望 pass:false/exit 1，实际 exit=%s pass=%r（错误解被放过）| %s"
                         % (code, verdict["payload"].get("pass"), evidence(verdict)))

    ok = good_ok and bad_ok and not meta_problems
    return {"task": task_dir.name, "good": good_cell, "bad": bad_cell,
            "verdict": "OK" if ok else "NG", "notes": notes}


def main():
    if not TASKS_DIR.is_dir():
        print("发现任务数=0：%s 不存在，空绿不算通过" % TASKS_DIR)
        print("PASS=0 FAIL=1")
        return 1

    task_dirs = sorted(p for p in TASKS_DIR.iterdir() if p.is_dir() and (p / "meta.json").is_file())
    bare_dirs = sorted(p.name for p in TASKS_DIR.iterdir()
                       if p.is_dir() and not (p / "meta.json").is_file())

    print("发现任务数=%d" % len(task_dirs))
    if bare_dirs:
        print("注意：以下目录无 meta.json，未被发现：%s" % ", ".join(bare_dirs))
    print("")

    rows = [judge_task(task_dir) for task_dir in task_dirs]

    print("%-6s | %-9s | %-9s | %s" % ("task", "good(PASS?)", "bad(FAIL?)", "判定"))
    print("%s-+-%s-+-%s-+-%s" % ("-" * 6, "-" * 9, "-" * 9, "-" * 4))
    for row in rows:
        print("%-6s | %-9s | %-9s | %s" % (row["task"], row["good"], row["bad"], row["verdict"]))

    failures = [row for row in rows if row["verdict"] != "OK"]
    if failures:
        print("")
        for row in failures:
            for note in row["notes"]:
                print("[%s] %s" % (row["task"], note))

    print("")
    print("PASS=%d FAIL=%d" % (len(rows) - len(failures), len(failures)))
    if not rows:
        print("发现任务数=0，空绿不算通过")
        return 1
    return 0 if not failures else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException as exc:
        sys.stderr.write("selftest crash: %r\n" % (exc,))
        raise SystemExit(1)

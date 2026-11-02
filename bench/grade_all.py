#!/usr/bin/env python3
"""批跑全部判分器，输出汇总 score.json。

用法：
    python agi\\bench\\grade_all.py --manifest <manifest.json> --out <score.json>

manifest 形状（CONTRACT.md §8）：
    {"genome":"G0","split":"dev","runs":[{"task":"T01","rep":1,"run_dir":"..."}]}

- run_dir 为相对路径时，按 manifest 文件所在目录解析。
- 判分器只走 CONTRACT §5 的 CLI；stdout 按最后一行 JSON 解析。
- 判分器 exit 2 / stdout 不合契约 ⇒ 记 error 并按 FAIL 计，grader_errors 计数；
  grader_errors>0 时本工具自身 exit 2。
- 沙箱禁管道时退回"同一条 CLI + 文件重定向"，调用方式仍是真子进程。
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
    out_file = tempfile.NamedTemporaryFile(delete=False, suffix=".stdout")
    err_file = tempfile.NamedTemporaryFile(delete=False, suffix=".stderr")
    out_file.close()
    err_file.close()
    try:
        with open(out_file.name, "wb") as fo, open(err_file.name, "wb") as fe:
            proc = subprocess.run(cmd, stdout=fo, stderr=fe, stdin=subprocess.DEVNULL,
                                  timeout=timeout, env=env)
        return (proc.returncode,
                Path(out_file.name).read_text(encoding="utf-8", errors="replace"),
                Path(err_file.name).read_text(encoding="utf-8", errors="replace"),
                "cli-file")
    finally:
        for path in (out_file.name, err_file.name):
            try:
                os.unlink(path)
            except OSError:
                pass


def invoke_grader(grade_py, run_dir, task_dir, timeout=60):
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
    out = clamp(result["stdout"].strip()) if result["stdout"].strip() else "<空>"
    err = clamp(result["stderr"].strip()) if result["stderr"].strip() else "<空>"
    return "stdout=%s | stderr=%s" % (out, err)


def load_meta(task):
    path = TASKS_DIR / task / "meta.json"
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:
        return None, "读不到 %s 的 meta.json: %r" % (task, exc)


def main(argv=None):
    import argparse

    ap = argparse.ArgumentParser(description="bench 批跑器")
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    manifest_path = Path(args.manifest).resolve()
    if not manifest_path.is_file():
        sys.stderr.write("manifest 不存在: %s\n" % manifest_path)
        return 2
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        sys.stderr.write("manifest 不可解析: %r\n" % (exc,))
        return 2
    runs = manifest.get("runs")
    if not isinstance(runs, list):
        sys.stderr.write("manifest.runs 不是列表\n")
        return 2

    base = manifest_path.parent
    grader_errors = 0
    per_task = []
    per_axis = {}
    weighted_pass = 0.0
    weighted_total = 0.0
    pass_count = 0

    for entry in runs:
        task = str(entry.get("task", "")).strip()
        rep = entry.get("rep", 1)
        raw_run = entry.get("run_dir", "")
        run_dir = Path(raw_run) if os.path.isabs(str(raw_run)) else (base / str(raw_run))
        meta, meta_error = load_meta(task) if task else (None, "manifest 条目缺 task")
        weight = float(meta.get("weight", 1)) if isinstance(meta, dict) else 1.0
        axis = meta.get("axis") if isinstance(meta, dict) else "unknown"
        weighted_total += weight

        ok = False
        score = 0.0
        error = None
        task_dir = TASKS_DIR / task
        grade_py = task_dir / "grade.py"

        if meta_error:
            error = clamp(meta_error)
        elif not grade_py.is_file():
            error = clamp("缺 %s" % grade_py)
        elif not run_dir.is_dir():
            # 被测 agent 没产出目录：这是产物失败，不是判分器坏
            sys.stderr.write("[%s] run_dir 不存在，按 FAIL 计: %s\n" % (task, run_dir))
        else:
            code, out, err, mode = invoke_grader(grade_py, run_dir, task_dir)
            verdict = classify(code, out, err, mode)
            if verdict["kind"] != "judged":
                error = clamp("%s: %s | %s" % (verdict["kind"], verdict["problem"] or "无附加信息",
                                               evidence(verdict)))
            else:
                ok = code == 0 and verdict["payload"].get("pass") is True
                try:
                    score = float(verdict["payload"].get("score", 0.0))
                except (TypeError, ValueError):
                    score = 0.0

        if error is not None:
            grader_errors += 1
            ok = False
        if ok:
            pass_count += 1
            weighted_pass += weight

        bucket = per_axis.setdefault(str(axis), {"pass": 0, "total": 0})
        bucket["total"] += 1
        if ok:
            bucket["pass"] += 1
        per_task.append({"task": task, "rep": rep, "pass": bool(ok),
                         "score": round(score, 4), "error": error})

    summary = {
        "genome": manifest.get("genome"),
        "split": manifest.get("split"),
        "n": len(per_task),
        "pass": pass_count,
        "weighted_pass": round(weighted_pass, 4),
        "weighted_total": round(weighted_total, 4),
        "per_task": per_task,
        "per_axis": per_axis,
        "grader_errors": grader_errors,
    }

    out_path = Path(args.out)
    try:
        if out_path.parent and not out_path.parent.exists():
            out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        sys.stderr.write("写 %s 失败: %r\n" % (out_path, exc))
        return 2

    sys.stdout.write(json.dumps(summary, ensure_ascii=False) + "\n")
    sys.stdout.write("已写入 %s\n" % out_path)
    if grader_errors:
        sys.stderr.write("grader_errors=%d（判分器自身坏了，不许算通过）\n" % grader_errors)
        return 2
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException as exc:
        sys.stderr.write("grade_all crash: %r\n" % (exc,))
        raise SystemExit(2)

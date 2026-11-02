#!/usr/bin/env python3
"""T11 判分器：验证/自证 —— 结论必须附带能复算出同一真值的命令与输出。

真值由 <TASK_DIR>/fixtures/data.csv 独立算出，不信任被测产物里的数字。
只读 <RUN_DIR> 与 <TASK_DIR>/fixtures，不写任何文件。
退出码：0=PASS，1=FAIL，2=判分器自身错误（读不到自己的 fixtures / 用法错）。
"""
import argparse
import json
import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

TASK = "T11"
PRODUCT = "verify.json"
FIXTURE_REL = "fixtures/data.csv"


def clip(value, limit=200):
    text = "" if value is None else str(value)
    text = text.replace("\r", "").replace("\n", "\\n")
    return text if len(text) <= limit else text[:limit] + "…(截断)"


def truth_from_fixture(task_dir):
    fixture = task_dir / "fixtures" / "data.csv"
    if not fixture.is_file():
        return None
    values = []
    for line in fixture.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [item.strip() for item in line.split(",")]
        if len(parts) < 2:
            continue
        try:
            values.append(int(parts[1]))
        except ValueError:
            continue
    return len(values), sum(values)


def standalone(text, number):
    return re.search(r"(?<![\d.])%d(?![\d.])" % number, text) is not None


def main(argv=None):
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--task-dir", required=True)
    args = parser.parse_args(argv)

    run_dir = Path(args.run_dir)
    task_dir = Path(args.task_dir)
    if not run_dir.is_dir():
        print("run-dir 不是目录: %s" % args.run_dir, file=sys.stderr)
        return 2
    truth = truth_from_fixture(task_dir)
    if truth is None:
        print("读不到自己的 fixture: %s" % (task_dir / FIXTURE_REL), file=sys.stderr)
        return 2
    expect_count, expect_total = truth

    checks = []

    def add(name, ok, detail):
        checks.append({"name": name, "pass": bool(ok), "detail": clip(detail)})

    target = run_dir / "verify.json"
    data = None
    exists = target.is_file()
    add("file-exists", exists, PRODUCT if exists else "期望 %s，实际未找到" % PRODUCT)
    if exists:
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            add("json-parses", False, "解析失败: %s: %s" % (type(exc).__name__, exc))
            data = None
        else:
            add("json-parses", isinstance(data, dict), "顶层类型=%s" % type(data).__name__)
    if not isinstance(data, dict):
        data = {}

    got_count = data.get("count")
    add(
        "count-correct",
        isinstance(got_count, int) and not isinstance(got_count, bool) and got_count == expect_count,
        "期望整数 %d（由数据独立算出），实际 %r (%s)"
        % (expect_count, got_count, type(got_count).__name__),
    )
    got_total = data.get("total")
    add(
        "total-correct",
        isinstance(got_total, int) and not isinstance(got_total, bool) and got_total == expect_total,
        "期望整数 %d（由数据独立算出），实际 %r (%s)"
        % (expect_total, got_total, type(got_total).__name__),
    )

    command = data.get("command")
    command_ok = (
        isinstance(command, str)
        and len(command.strip()) >= 10
        and "\n" not in command
        and "data.csv" in command
    )
    add(
        "command-reproducible",
        command_ok,
        "期望单行、≥10 字符、含 data.csv 的可重跑命令，实际 %r" % (command,),
    )

    output = data.get("output")
    output_text = output if isinstance(output, str) else ""
    has_both = bool(output_text.strip()) and standalone(output_text, expect_total) and standalone(
        output_text, expect_count
    )
    add(
        "output-reproduces-result",
        has_both,
        "期望 output 里同时出现 total=%d 与 count=%d 的原文，实际 %r"
        % (expect_total, expect_count, output),
    )

    passed = all(item["pass"] for item in checks)
    failed = [item["name"] for item in checks if not item["pass"]]
    if passed:
        reason = "全部 %d 项判据通过" % len(checks)
    elif "file-exists" in failed:
        reason = "缺少产物 %s（按缺文件判 FAIL）；其余未通过判据: %s" % (PRODUCT, ", ".join(failed))
    else:
        reason = "未通过判据: %s" % ", ".join(failed)
    result = {
        "task": TASK,
        "pass": passed,
        "score": 1.0 if passed else 0.0,
        "checks": checks,
        "reason": reason,
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())

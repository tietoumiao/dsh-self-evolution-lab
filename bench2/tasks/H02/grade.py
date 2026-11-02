#!/usr/bin/env python3
"""H02 判分器：三文件交叉对账 + 精确差异报告 + 按 schema 修正配置。

退出码：0=PASS，1=FAIL，2=判分器自身错误（用法错 / fixture 不可用）。
只读 --run-dir 与 --task-dir/fixtures，不写任何文件。
真值由三份 fixtures 各自解析后现算，不采信 diff.json 自报的任何数字。
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

TASK_ID = "H02"
DIFF_KEYS = {"schema", "authority", "conflicts", "consistent_fields"}
CONFLICT_KEYS = {"field", "values", "expected"}
VALUE_KEYS = {"config", "deploy", "schema"}
SCHEMA_DEFAULT_RE = re.compile(
    r"^\s*([a-z_][a-z0-9_]*)\s+INTEGER\s+NOT NULL\s+DEFAULT\s+(-?\d+)\s*,?\s*$", re.IGNORECASE)
DEPLOY_ROW_RE = re.compile(r"^\|\s*([a-z_][a-z0-9_]*)\s*\|\s*(-?\d+)\s*\|")


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


def is_int(value):
    return type(value) is int


# ---------------------------------------------------------------- fixtures → truth
def _read(path):
    if not path.is_file():
        grader_error("缺少 fixture: %s" % path)
    try:
        return path.read_text(encoding="utf-8-sig")
    except Exception as exc:
        grader_error("fixture 不可读 %s: %r" % (path, exc))


def parse_schema(text):
    values = {}
    for line in text.splitlines():
        m = SCHEMA_DEFAULT_RE.match(line)
        if m:
            values[m.group(1).lower()] = int(m.group(2))
    if not values:
        grader_error("fixtures/schema.sql 里没有解析到任何 DEFAULT 整数")
    return values


def parse_deploy(text):
    values = {}
    for line in text.splitlines():
        m = DEPLOY_ROW_RE.match(line.strip())
        if m:
            values[m.group(1).lower()] = int(m.group(2))
    if not values:
        grader_error("fixtures/deploy.md 里没有解析到任何参数表行")
    return values


def compute_truth(task_dir):
    base = Path(task_dir) / "fixtures"
    raw_config = _read(base / "config.json")
    try:
        config = json.loads(raw_config)
    except Exception as exc:
        grader_error("fixtures/config.json 不可解析: %r" % (exc,))
    if not isinstance(config, dict) or not config:
        grader_error("fixtures/config.json 顶层不是非空对象")
    for key, value in config.items():
        if not is_int(value):
            grader_error("fixtures/config.json 的 %r 不是整数" % (key,))
    schema = parse_schema(_read(base / "schema.sql"))
    deploy = parse_deploy(_read(base / "deploy.md"))

    fields = sorted(config)
    for field in fields:
        if field not in schema or field not in deploy:
            grader_error("字段 %r 在三份 fixture 里不齐（config/schema/deploy）" % (field,))
    disagreeing = [f for f in fields
                   if len({config[f], deploy[f], schema[f]}) > 1]
    if len(disagreeing) != 1:
        grader_error("fixtures 应恰好有 1 处不一致，实际 %r" % (disagreeing,))
    field = disagreeing[0]
    expected = schema[field]
    fixed = dict(config)
    fixed[field] = expected
    return {
        "field": field,
        "values": {"config": config[field], "deploy": deploy[field], "schema": schema[field]},
        "expected": expected,
        "consistent": sorted(f for f in fields if f != field),
        "fixed": fixed,
        "config": config,
        "schema": schema,
    }


# ---------------------------------------------------------------- 产物读取
def load_json(run_dir, name):
    path = Path(run_dir) / name
    if not path.is_file():
        return None, "期望 %s 存在，实际缺失" % path
    try:
        text = path.read_text(encoding="utf-8-sig")
    except Exception as exc:
        return None, "%s 不是 UTF-8 文本: %r" % (name, exc)
    try:
        data = json.loads(text)
    except Exception as exc:
        return None, "%s 不是合法 JSON: %r（前 80 字符: %r）" % (name, exc, text[:80])
    if not isinstance(data, dict):
        return None, "%s 顶层不是对象，实际 %s" % (name, type(data).__name__)
    return data, ""


def check_conflicts(conflicts, truth):
    problems = []
    if not isinstance(conflicts, list):
        return ["conflicts 不是数组，实际 %s" % type(conflicts).__name__]
    if len(conflicts) != 1:
        problems.append("期望恰好 1 条，实际 %d 条" % len(conflicts))
    for i, item in enumerate(conflicts):
        tag = "conflicts[%d]" % i
        if not isinstance(item, dict) or set(item) != CONFLICT_KEYS:
            problems.append("%s 键集应为 %s，实际 %r"
                            % (tag, sorted(CONFLICT_KEYS),
                               sorted(item) if isinstance(item, dict) else type(item).__name__))
            continue
        if item.get("field") != truth["field"]:
            problems.append("%s.field 期望 %r，实际 %r" % (tag, truth["field"], item.get("field")))
        values = item.get("values")
        if not isinstance(values, dict) or set(values) != VALUE_KEYS:
            problems.append("%s.values 键集应为 %s，实际 %r"
                            % (tag, sorted(VALUE_KEYS),
                               sorted(values) if isinstance(values, dict) else type(values).__name__))
        else:
            for key in ("config", "deploy", "schema"):
                actual = values.get(key)
                if not is_int(actual) or actual != truth["values"][key]:
                    problems.append("%s.values.%s 期望 %d，实际 %r"
                                    % (tag, key, truth["values"][key], actual))
        expected = item.get("expected")
        if not is_int(expected) or expected != truth["expected"]:
            problems.append("%s.expected 期望 %d，实际 %r" % (tag, truth["expected"], expected))
    return problems


def check_fixed(fixed, truth):
    problems = []
    if not isinstance(fixed, dict):
        return ["顶层不是对象，实际 %s" % type(fixed).__name__]
    if set(fixed) != set(truth["fixed"]):
        problems.append("键集期望 %s，实际 %s" % (sorted(truth["fixed"]), sorted(fixed)))
    for field in sorted(truth["fixed"]):
        actual = fixed.get(field)
        if not is_int(actual) or actual != truth["fixed"][field]:
            problems.append("%s 期望 %d，实际 %r" % (field, truth["fixed"][field], actual))
    return problems


def check_matches_schema(fixed, truth):
    if not isinstance(fixed, dict):
        return ["顶层不是对象，无法比对"]
    problems, missing = [], 0
    for field in sorted(truth["schema"]):
        if field not in fixed:
            missing += 1
            continue
        if fixed[field] != truth["schema"][field]:
            problems.append("%s 与 schema DEFAULT 不一致：期望 %d，实际 %r"
                            % (field, truth["schema"][field], fixed[field]))
    if missing:
        problems.insert(0, "缺少 %d 个 schema 字段" % missing)
    return problems


def main(argv=None):
    ap = argparse.ArgumentParser(description="H02 grader")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--task-dir", required=True)
    args = ap.parse_args(argv)

    run_dir = Path(args.run_dir)
    task_dir = Path(args.task_dir)
    if not task_dir.is_dir():
        grader_error("--task-dir 不存在: %s" % task_dir)
    if not run_dir.is_dir():
        grader_error("--run-dir 不存在: %s" % run_dir)

    truth = compute_truth(task_dir)
    diff, diff_error = load_json(run_dir, "diff.json")
    fixed, fixed_error = load_json(run_dir, "config.fixed.json")

    checks = [("diff-shape", not diff_error, diff_error or "diff.json 可解析且顶层为对象")]
    if diff_error:
        for name in ("diff-keys", "authority", "conflict", "consistent-fields"):
            checks.append((name, False, "未执行：%s" % diff_error))
    else:
        top = set(diff)
        schema_value = diff.get("schema")
        keys_ok = top == DIFF_KEYS and is_int(schema_value) and schema_value == 1
        checks.append(("diff-keys", keys_ok,
                       "期望顶层键 %s 且 schema=1，实际键 %s、schema=%r"
                       % (sorted(DIFF_KEYS), sorted(top), schema_value)))
        authority = diff.get("authority")
        ok_auth = isinstance(authority, str) and "schema.sql" in authority
        checks.append(("authority", ok_auth,
                       "期望指向 schema.sql 的字符串，实际 %r" % (authority,)))
        problems = check_conflicts(diff.get("conflicts"), truth)
        checks.append(("conflict", not problems,
                       "; ".join(problems) if problems else
                       "唯一不一致字段=%s，三处取值与 expected 均正确" % truth["field"]))
        consistent = diff.get("consistent_fields")
        ok_consistent = isinstance(consistent, list) and consistent == truth["consistent"]
        checks.append(("consistent-fields", ok_consistent,
                       "期望（升序）%s，实际 %r" % (truth["consistent"], consistent)))

    checks.append(("fixed-config", not fixed_error,
                   fixed_error or "config.fixed.json 可解析且顶层为对象"))
    if fixed_error:
        checks.append(("fixed-corrected", False, "未执行：%s" % fixed_error))
        checks.append(("fixed-matches-schema", False, "未执行：%s" % fixed_error))
    else:
        problems = check_fixed(fixed, truth)
        checks.append(("fixed-corrected", not problems,
                       "; ".join(problems) if problems else
                       "只把 %s 改成 %d，其余字段保持不变" % (truth["field"], truth["expected"])))
        problems = check_matches_schema(fixed, truth)
        checks.append(("fixed-matches-schema", not problems,
                       "; ".join(problems) if problems else "全部字段与 schema.sql 的 DEFAULT 一致"))

    all_ok = all(p for _, p, _ in checks)
    passed = sum(1 for _, p, _ in checks if p)
    emit(all_ok, checks, "%d/%d 项检查通过（真值由三份 fixtures 现算）" % (passed, len(checks)))


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException as exc:  # 判分器自身异常 ⇒ exit 2
        sys.stderr.write("[%s] grader crash: %r\n" % (TASK_ID, exc))
        raise SystemExit(2)

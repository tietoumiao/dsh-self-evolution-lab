#!/usr/bin/env python3
"""T04 判分器：固定字节格式 + 多键精确匹配 + 文件哈希自洽。

退出码：0=PASS，1=FAIL，2=判分器自身错误（用法错 / 缺 fixture）。
"""

import argparse
import csv
import hashlib
import io
import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

TASK_ID = "T04"
JSON_KEYS = {"rows", "total_qty", "total_cents", "currency", "sha256_csv"}


def clamp(text, limit=200):
    text = str(text).replace("\r", "\\r").replace("\n", "\\n")
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
    """从 fixtures/items.csv 独立重算真值：期望的 CSV 字节与 JSON 各键。"""
    source = Path(task_dir) / "fixtures" / "items.csv"
    if not source.is_file():
        grader_error("缺少 fixtures/items.csv: %s" % source)
    try:
        text = source.read_text(encoding="utf-8")
        rows = list(csv.DictReader(io.StringIO(text)))
        parsed = [{"sku": row["sku"].strip(),
                   "qty": int(row["qty"]),
                   "total": int(row["qty"]) * int(row["unit_price_cents"])} for row in rows]
    except Exception as exc:
        grader_error("fixtures/items.csv 不可解析: %r" % (exc,))
    if not parsed:
        grader_error("fixtures/items.csv 没有数据行")

    parsed.sort(key=lambda item: item["sku"])
    csv_text = "sku,qty,total\n" + "".join(
        "%s,%d,%d\n" % (item["sku"], item["qty"], item["total"]) for item in parsed)
    return {
        "csv_text": csv_text,
        "csv_sha256": hashlib.sha256(csv_text.encode("utf-8")).hexdigest(),
        "json": {
            "rows": len(parsed),
            "total_qty": sum(item["qty"] for item in parsed),
            "total_cents": sum(item["total"] for item in parsed),
            "currency": "USD",
        },
    }


def find_first_diff(actual, expected):
    for index, (left, right) in enumerate(zip(actual, expected)):
        if left != right:
            start = max(0, index - 20)
            return ("第 %d 个字符起不同：实际 %r，期望 %r"
                    % (index, actual[start:index + 30], expected[start:index + 30]))
    if len(actual) != len(expected):
        return "长度不同：实际 %d 字节，期望 %d 字节（尾部实际 %r，期望 %r）" % (
            len(actual), len(expected), actual[len(expected):len(expected) + 30],
            expected[len(actual):len(actual) + 30])
    return ""


def main(argv=None):
    ap = argparse.ArgumentParser(description="T04 grader")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--task-dir", required=True)
    args = ap.parse_args(argv)

    task_dir = Path(args.task_dir)
    run_dir = Path(args.run_dir)
    if not task_dir.is_dir():
        grader_error("--task-dir 不存在: %s" % task_dir)
    truth = load_truth(task_dir)

    checks = []
    csv_path = run_dir / "summary.csv"
    csv_exists = csv_path.is_file() and csv_path.stat().st_size > 0
    checks.append(("csv-exists", csv_exists,
                   "期望 %s 存在且非空，实际 %s" % (csv_path, "存在" if csv_exists else "缺失或为空")))

    actual_text = None
    if csv_exists:
        try:
            raw = csv_path.read_bytes()
            actual_text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            checks.append(("csv-bytes", False, "期望 UTF-8，实际解码失败: %s" % clamp(exc, 160)))

    if actual_text is not None:
        same = actual_text == truth["csv_text"]
        if same:
            detail = "与期望字节完全一致"
        elif actual_text.startswith("\ufeff"):
            detail = "文件带 UTF-8 BOM（首个字符是 U+FEFF）"
        elif "\r" in actual_text:
            detail = "文件含 \\r（要求只用 LF）：" + find_first_diff(actual_text, truth["csv_text"])
        else:
            detail = find_first_diff(actual_text, truth["csv_text"])
        checks.append(("csv-bytes", same, detail))
    elif csv_exists:
        checks.append(("csv-bytes", False, "未执行：文件无法按 UTF-8 解码"))

    json_path = run_dir / "summary.json"
    json_exists = json_path.is_file() and json_path.stat().st_size > 0
    checks.append(("json-exists", json_exists,
                   "期望 %s 存在且非空，实际 %s" % (json_path, "存在" if json_exists else "缺失或为空")))

    payload = None
    if json_exists:
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception as exc:
            checks.append(("json-parse", False, "期望合法 JSON，实际解析失败: %s" % clamp(exc, 160)))
    if json_exists and payload is None:
        for name in ("json-keys", "json-values", "csv-sha256"):
            checks.append((name, False, "未执行：summary.json 无法解析"))
        emit(False, checks, "summary.json 不是合法 JSON")
    if not json_exists:
        for name in ("json-parse", "json-keys", "json-values", "csv-sha256"):
            checks.append((name, False, "未执行：summary.json 缺失"))
        emit(False, checks, "产物 summary.json 不存在，判据无法满足")

    checks.append(("json-parse", True, "JSON 解析通过"))
    if not isinstance(payload, dict):
        for name in ("json-keys", "json-values", "csv-sha256"):
            checks.append((name, False, "未执行：顶层不是对象"))
        emit(False, checks, "summary.json 顶层不是 JSON 对象")

    actual_keys = set(payload)
    checks.append(("json-keys", actual_keys == JSON_KEYS,
                   "期望键集 %s，实际 %s" % (sorted(JSON_KEYS), sorted(actual_keys))))

    values_ok = all(
        (type(payload.get(key)) is int and payload.get(key) == truth["json"][key])
        if key in ("rows", "total_qty", "total_cents") else
        (isinstance(payload.get(key), str) and payload.get(key) == truth["json"][key])
        for key in ("rows", "total_qty", "total_cents", "currency"))
    checks.append(("json-values", values_ok,
                   "期望 %s，实际 %s" % (dump(truth["json"]),
                                       dump({k: payload.get(k) for k in ("rows", "total_qty", "total_cents", "currency")}))))

    declared = payload.get("sha256_csv")
    expected_sha = truth["csv_sha256"]
    if not isinstance(declared, str):
        sha_detail = "期望 64 位十六进制字符串（应为 %s），实际 %s" % (expected_sha, dump(declared))
        sha_ok = False
    elif declared != expected_sha:
        sha_detail = "期望 %s（正确 summary.csv 的哈希），实际 %s" % (expected_sha, clamp(declared))
        sha_ok = False
    elif actual_text is not None and hashlib.sha256(actual_text.encode("utf-8")).hexdigest() != declared:
        sha_detail = ("声明的哈希与你自己写出的 summary.csv 不一致：csv 实算 %s，声明 %s"
                      % (hashlib.sha256(actual_text.encode("utf-8")).hexdigest(), clamp(declared)))
        sha_ok = False
    else:
        sha_detail = "sha256_csv 与期望 summary.csv 字节一致"
        sha_ok = True
    checks.append(("csv-sha256", sha_ok, sha_detail))

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

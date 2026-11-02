#!/usr/bin/env python3
"""T06 判分器：从 fixtures/transactions.csv 用十进制精确算法独立重算真值。

退出码：0=PASS，1=FAIL，2=判分器自身错误（用法错 / 缺 fixture）。
"""

import argparse
import csv
import io
import json
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

TASK_ID = "T06"
TOP_KEYS = {"accounts", "monthly", "grand_total_cents"}
ACCOUNT_KEYS = {"count", "usd_cents", "largest_txn"}
MONTH_KEYS = {"count", "usd_cents"}


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
    source = Path(task_dir) / "fixtures" / "transactions.csv"
    if not source.is_file():
        grader_error("缺少 fixtures/transactions.csv: %s" % source)
    try:
        rows = list(csv.DictReader(io.StringIO(source.read_text(encoding="utf-8"))))
    except Exception as exc:
        grader_error("fixtures/transactions.csv 不可解析: %r" % (exc,))
    if not rows:
        grader_error("fixtures/transactions.csv 没有数据行")

    accounts, monthly = {}, {}
    grand = 0
    for row in rows:
        try:
            amount = int(row["amount_cents"])
            rate = Decimal(row["fx_rate"].strip())
            usd = int((Decimal(amount) * rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
            txn_id = row["txn_id"].strip()
            account = row["account"].strip()
            month = row["date"].strip()[:7]
        except Exception as exc:
            grader_error("transactions.csv 行不可解析（%s）: %r" % (row.get("txn_id"), exc))

        bucket = accounts.setdefault(account, {"count": 0, "usd_cents": 0, "largest_txn": None})
        bucket["count"] += 1
        bucket["usd_cents"] += usd
        if bucket["largest_txn"] is None:
            bucket["largest_txn"] = (usd, txn_id)
        # 最大 usd，并列取 txn_id 最小
        if usd > bucket["largest_txn"][0] or (usd == bucket["largest_txn"][0]
                                              and txn_id < bucket["largest_txn"][1]):
            bucket["largest_txn"] = (usd, txn_id)

        month_bucket = monthly.setdefault(month, {"count": 0, "usd_cents": 0})
        month_bucket["count"] += 1
        month_bucket["usd_cents"] += usd
        grand += usd

    accounts = {name: {"count": value["count"], "usd_cents": value["usd_cents"],
                       "largest_txn": value["largest_txn"][1]}
                for name, value in accounts.items()}
    return {"accounts": accounts, "monthly": monthly, "grand_total_cents": grand}


def main(argv=None):
    ap = argparse.ArgumentParser(description="T06 grader")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--task-dir", required=True)
    args = ap.parse_args(argv)

    task_dir = Path(args.task_dir)
    run_dir = Path(args.run_dir)
    if not task_dir.is_dir():
        grader_error("--task-dir 不存在: %s" % task_dir)
    truth = load_truth(task_dir)

    checks = []
    path = run_dir / "aggregate.json"
    exists = path.is_file() and path.stat().st_size > 0
    checks.append(("file-exists", exists,
                   "期望 %s 存在且非空，实际 %s" % (path, "存在" if exists else "缺失或为空")))
    if not exists:
        for name in ("json-parse", "top-keys", "accounts", "monthly", "grand-total"):
            checks.append((name, False, "未执行：aggregate.json 缺失"))
        emit(False, checks, "产物 aggregate.json 不存在，判据无法满足")

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        checks.append(("json-parse", False, "期望合法 JSON，实际解析失败: %s" % clamp(exc, 160)))
        for name in ("top-keys", "accounts", "monthly", "grand-total"):
            checks.append((name, False, "未执行：JSON 无法解析"))
        emit(False, checks, "aggregate.json 不是合法 JSON")
    checks.append(("json-parse", True, "JSON 解析通过"))

    if not isinstance(payload, dict):
        for name in ("top-keys", "accounts", "monthly", "grand-total"):
            checks.append((name, False, "未执行：顶层不是对象"))
        emit(False, checks, "aggregate.json 顶层不是 JSON 对象")

    checks.append(("top-keys", set(payload) == TOP_KEYS,
                   "期望键集 %s，实际 %s" % (sorted(TOP_KEYS), sorted(payload))))

    def structure_problem(value, expected_keys, label):
        if not isinstance(value, dict):
            return "%s 不是对象（实际 %s）" % (label, type(value).__name__)
        for name, item in value.items():
            if not isinstance(item, dict):
                return "%s[%s] 不是对象" % (label, name)
            if set(item) != expected_keys:
                return "%s[%s] 键集期望 %s，实际 %s" % (label, name, sorted(expected_keys), sorted(item))
            if type(item.get("count")) is not int or type(item.get("usd_cents")) is not int:
                return "%s[%s] 的 count/usd_cents 必须是 JSON 整数" % (label, name)
            if "largest_txn" in expected_keys and not isinstance(item.get("largest_txn"), str):
                return "%s[%s].largest_txn 必须是字符串" % (label, name)
        return ""

    accounts_problem = structure_problem(payload.get("accounts"), ACCOUNT_KEYS, "accounts")
    accounts_ok = not accounts_problem and payload.get("accounts") == truth["accounts"]
    checks.append(("accounts", accounts_ok,
                   accounts_problem or "期望 %s，实际 %s"
                   % (dump(truth["accounts"]), dump(payload.get("accounts")))))

    monthly_problem = structure_problem(payload.get("monthly"), MONTH_KEYS, "monthly")
    monthly_ok = not monthly_problem and payload.get("monthly") == truth["monthly"]
    checks.append(("monthly", monthly_ok,
                   monthly_problem or "期望 %s，实际 %s"
                   % (dump(truth["monthly"]), dump(payload.get("monthly")))))

    grand = payload.get("grand_total_cents")
    grand_ok = type(grand) is int and grand == truth["grand_total_cents"]
    checks.append(("grand-total", grand_ok,
                   "期望 %r（int），实际 %s" % (truth["grand_total_cents"], dump(grand))))

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

#!/usr/bin/env python3
"""H06 判分器：precision。多币种 + 多税率 + 文档规定的 .5 进位方向。

真值由判分器自己用 Decimal 从 fixtures/orders.csv、fixtures/tax.md、fixtures/fx.md 重算
（ROUND_HALF_UP 在 decimal 里就是「.5 向远离零」，与 tax.md 第 3 节一致），
不采信被测产物自报的任何数字。浮点实现会在恰好落在 .5 的那几单上差 1 分。

退出码：0=PASS，1=FAIL，2=判分器自身错误（用法错 / 缺 fixture）。
只读 --run-dir 与 --task-dir/fixtures，不写任何文件。
"""

import argparse
import csv
import json
import re
import sys
from decimal import Decimal, ROUND_HALF_UP, getcontext
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

getcontext().prec = 60
TASK_ID = "H06"
KEYS = ["order_id", "currency", "net_cents", "tax_cents", "gross_cents", "cny_gross_cents"]
WORK_HEADER = "order_id,currency,net_cents,tax_rate,tax_exact_cents,tax_cents"
TABLE_ROW = re.compile(r"^\|\s*([A-Za-z]+)\s*\|\s*([0-9]+(?:\.[0-9]+)?)\s*\|\s*$")
SIX_DP = re.compile(r"^-?\d+\.\d{6}$")

FALLBACK_TAX = {"food": "0.13", "gadget": "0.071", "service": "0.0825", "book": "0.0"}
FALLBACK_FX = {"CNY": "1", "USD": "7.1234", "EUR": "7.8901", "JPY": "0.0481"}


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


# --------------------------------------------------------------- 读 fixture
def parse_table(path, fallback):
    """从 markdown 表格里抽 name → 数值字符串；抽不到就用内置副本。"""
    table = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            match = TABLE_ROW.match(line.strip())
            if match:
                table[match.group(1)] = match.group(2)
    except Exception:
        table = {}
    return table or dict(fallback)


def load_orders(path):
    text = path.read_bytes().decode("utf-8")
    rows = []
    for index, parts in enumerate(csv.reader(text.splitlines())):
        if not parts or not "".join(parts).strip():
            continue
        if index == 0 and parts[0].strip().lower() == "order_id":
            continue
        rows.append({"order_id": parts[0].strip(), "currency": parts[1].strip(),
                     "category": parts[2].strip(), "net_cents": int(parts[3])})
    return rows


def half_up(value):
    """十进制精确值 → 整数，.5 向远离零方向进位。"""
    return int(Decimal(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def build_truth(orders, tax_table, fx_table):
    truth = []
    for order in orders:
        rate = tax_table[order["category"]]
        fx = fx_table[order["currency"]]
        exact = Decimal(order["net_cents"]) * Decimal(rate)
        tax = half_up(exact)
        gross = order["net_cents"] + tax
        cny = half_up(Decimal(gross) * Decimal(fx))
        truth.append({
            "order_id": order["order_id"], "currency": order["currency"],
            "net_cents": order["net_cents"], "tax_cents": tax,
            "gross_cents": gross, "cny_gross_cents": cny,
            "tax_rate": rate, "tax_exact": exact,
            "tax_exact_text": str(exact.quantize(Decimal("0.000001"))),
        })
    truth.sort(key=lambda item: item["order_id"])
    return truth


# --------------------------------------------------------------- 产物检查
def check_report(path, truth):
    """返回 (checks, 通过的 order_id 列表)。"""
    if not path.is_file():
        return [("report-file", False, "期望 %s 存在，实际缺失" % path.name)], []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [("report-file", False, "%s 不是合法 JSON: %r" % (path.name, exc))], []

    checks = [("report-file", True, "%s 存在且可解析" % path.name)]
    if not isinstance(data, list):
        checks.append(("report-shape", False, "顶层应为数组，实际 %s" % type(data).__name__))
        return checks, []
    if len(data) != len(truth):
        checks.append(("report-shape", False,
                       "元素个数期望 %d，实际 %d" % (len(truth), len(data))))
    else:
        checks.append(("report-shape", True, "元素个数 %d" % len(data)))

    order_ok = [item.get("order_id") for item in data if isinstance(item, dict)] == \
               [item["order_id"] for item in truth]
    checks.append(("report-order", order_ok,
                   "order_id 升序与输入一致" if order_ok else
                   "期望 order_id 序列 %s，实际 %s"
                   % ([i["order_id"] for i in truth], [i.get("order_id") if isinstance(i, dict) else i for i in data])))

    key_problems, type_problems = [], []
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            key_problems.append("第 %d 项不是对象" % (index + 1))
            continue
        if sorted(item) != sorted(KEYS):
            key_problems.append("第 %d 项键集为 %s（期望 %s）" % (index + 1, sorted(item), KEYS))
            continue
        if not isinstance(item["order_id"], str) or not isinstance(item["currency"], str):
            type_problems.append("第 %d 项 order_id/currency 不是字符串" % (index + 1))
        for name in ("net_cents", "tax_cents", "gross_cents", "cny_gross_cents"):
            value = item[name]
            if not isinstance(value, int) or isinstance(value, bool):
                type_problems.append("第 %d 项 %s=%r 不是 JSON 整数（类型 %s）"
                                     % (index + 1, name, value, type(value).__name__))
    checks.append(("report-keys", not key_problems, "键集全部合规" if not key_problems else "；".join(key_problems[:4])))
    checks.append(("report-types", not type_problems, "四个金额都是 JSON 整数" if not type_problems else "；".join(type_problems[:4])))

    diffs, matched = [], []
    if len(data) == len(truth) and not key_problems:
        for got, want in zip(data, truth):
            row_diff = []
            for name in KEYS:
                if got.get(name) != want[name] or type(got.get(name)) is not type(want[name]):
                    row_diff.append("%s 期望 %r 实际 %r" % (name, want[name], got.get(name)))
            if row_diff:
                diffs.append("%s: %s" % (want["order_id"], "；".join(row_diff)))
            else:
                matched.append(want["order_id"])
    checks.append(("report-values", not diffs and bool(matched),
                   "全部 %d 单与真值一致" % len(matched) if not diffs else
                   "%d/%d 单不一致：%s" % (len(diffs), len(truth), " | ".join(diffs[:4]))))
    return checks, matched


def check_workings(path, truth):
    if not path.is_file():
        return [("workings-file", False, "期望 %s 存在，实际缺失" % path.name),
                ("workings-exact", False, "未执行：out/workings.csv 缺失"),
                ("workings-rates", False, "未执行：out/workings.csv 缺失")]
    raw = path.read_bytes().decode("utf-8", "replace")
    lines = [ln for ln in raw.splitlines() if ln.strip()]
    if not lines:
        return [("workings-file", False, "out/workings.csv 为空"),
                ("workings-exact", False, "未执行"), ("workings-rates", False, "未执行")]
    checks = [("workings-file", lines[0].strip() == WORK_HEADER,
               "表头正确" if lines[0].strip() == WORK_HEADER else
               "表头期望 %r，实际 %r" % (WORK_HEADER, lines[0].strip()))]
    body = list(csv.reader(lines[1:]))
    if len(body) != len(truth):
        checks.append(("workings-exact", False,
                       "数据行期望 %d 行，实际 %d 行" % (len(truth), len(body))))
        checks.append(("workings-rates", False, "未执行：行数不对"))
        return checks

    exact_problems, rate_problems = [], []
    for index, (row, want) in enumerate(zip(body, truth)):
        if len(row) != 6:
            exact_problems.append("第 %d 行列数为 %d（期望 6）" % (index + 2, len(row)))
            continue
        order_id, currency, net_cents, rate, exact_text, tax_cents = [c.strip() for c in row]
        if order_id != want["order_id"] or currency != want["currency"]:
            exact_problems.append("第 %d 行 order_id/currency 期望 %r/%r 实际 %r/%r"
                                  % (index + 2, want["order_id"], want["currency"], order_id, currency))
        if net_cents != str(want["net_cents"]):
            exact_problems.append("第 %d 行 net_cents 期望 %r 实际 %r"
                                  % (index + 2, str(want["net_cents"]), net_cents))
        if tax_cents != str(want["tax_cents"]):
            exact_problems.append("第 %d 行 tax_cents 期望 %r 实际 %r"
                                  % (index + 2, str(want["tax_cents"]), tax_cents))
        if not SIX_DP.match(exact_text):
            exact_problems.append("第 %d 行 tax_exact_cents=%r 不是恰好 6 位小数的十进制字面量"
                                  % (index + 2, exact_text))
        else:
            try:
                got_exact = Decimal(exact_text)
            except Exception:
                got_exact = None
            if got_exact != want["tax_exact"]:
                exact_problems.append("第 %d 行 tax_exact_cents 期望 %r 实际 %r"
                                      % (index + 2, want["tax_exact_text"], exact_text))
        if rate != want["tax_rate"]:
            rate_problems.append("第 %d 行 tax_rate 期望 %r 实际 %r"
                                 % (index + 2, want["tax_rate"], rate))
    checks.append(("workings-exact", not exact_problems,
                   "每单未取整税额与真值一致且为 6 位小数" if not exact_problems
                   else "；".join(exact_problems[:4])))
    checks.append(("workings-rates", not rate_problems,
                   "税率列与文档一致" if not rate_problems else "；".join(rate_problems[:4])))
    return checks


def main(argv=None):
    ap = argparse.ArgumentParser(description="H06 grader")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--task-dir", required=True)
    args = ap.parse_args(argv)

    task_dir = Path(args.task_dir)
    run_dir = Path(args.run_dir)
    fixtures = task_dir / "fixtures"
    if not task_dir.is_dir():
        grader_error("--task-dir 不存在: %s" % task_dir)
    for name in ("orders.csv", "tax.md", "fx.md"):
        if not (fixtures / name).is_file():
            grader_error("缺少 fixtures/%s" % name)

    orders = load_orders(fixtures / "orders.csv")
    tax_table = parse_table(fixtures / "tax.md", FALLBACK_TAX)
    fx_table = parse_table(fixtures / "fx.md", FALLBACK_FX)
    missing = [o["category"] for o in orders if o["category"] not in tax_table] + \
              [o["currency"] for o in orders if o["currency"] not in fx_table]
    if missing:
        grader_error("fixtures 文档里缺这些键: %s" % sorted(set(missing)))
    truth = build_truth(orders, tax_table, fx_table)

    checks = []
    report_checks, _ = check_report(run_dir / "out" / "tax_report.json", truth)
    checks.extend(report_checks)
    checks.extend(check_workings(run_dir / "out" / "workings.csv", truth))

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

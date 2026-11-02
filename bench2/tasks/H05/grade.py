#!/usr/bin/env python3
"""H05 判分器：tool-failure。修好脚本 + 写出根因，二者都要对。

真值由判分器自己从 fixtures/ledger.csv 重算（UTF-8 + 标准 CSV 解析），
不采信 <RUN_DIR>/out/summary.json 自报的数字。
另外把 <RUN_DIR>/tool.py 当模块导进来，用隐藏字节喂 parse_bytes：
  - 非 ASCII 的 UTF-8 字节必须解析出正确记录（证明解码已改对）；
  - 带引号含逗号的字段必须解析出正确记录（证明解析已改对）；
  - 字段数不对 / 数字不合法时必须抛 ValueError（证明不再静默吞异常）。
最后核对 rootcause.md 是否点到了原始脚本里两处缺陷的具体行号与机制。

退出码：0=PASS，1=FAIL，2=判分器自身错误（用法错 / 缺 fixture）。
只读 --run-dir 与 --task-dir/fixtures，不写任何文件。
"""

import argparse
import contextlib
import csv
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

sys.dont_write_bytecode = True
TASK_ID = "H05"

# 隐藏探针：不随 fixtures 下发，防止被测方照着样例写死。
HIDDEN_CSV = (
    "S-01,茶叶,2,1250\n"
    "S-02,\"礼盒,精品\",3,999\n"
    "S-03,咖啡豆,1,15800\n"
    "# 注释行\n"
    "\n"
).encode("utf-8")
HIDDEN_EXPECT = [
    {"store": "S-01", "category": "茶叶", "qty": 2, "unit_cents": 1250},
    {"store": "S-02", "category": "礼盒,精品", "qty": 3, "unit_cents": 999},
    {"store": "S-03", "category": "咖啡豆", "qty": 1, "unit_cents": 15800},
]
BAD_INPUTS = [
    b"X-99,\xe8\x8c\xb6\xe5\x8f\xb6,abc,1200\n",   # qty 不是整数
    b"Y-01,only-two-fields\n",                       # 字段数不对
]


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


# --------------------------------------------------------------- 真值重算
def truth_summary(ledger_path):
    text = ledger_path.read_bytes().decode("utf-8")
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    by_category, rows_total, amount_total = {}, 0, 0
    for parts in csv.reader(lines):
        if len(parts) != 4:
            raise ValueError("fixtures/ledger.csv 行字段数不是 4: %r" % (parts,))
        store, category, qty, unit = [p.strip() for p in parts]
        qty, unit = int(qty), int(unit)
        rows_total += 1
        amount_total += qty * unit
        item = by_category.setdefault(category, {"rows": 0, "qty": 0, "amount": 0})
        item["rows"] += 1
        item["qty"] += qty
        item["amount"] += qty * unit
    return {"rows_total": rows_total, "amount_total": amount_total,
            "by_category": by_category}


# --------------------------------------------------------------- 缺陷行定位
def defect_lines(task_dir):
    """从原始 fixtures/tool.py 里定位两处缺陷的行号（不硬编码）。"""
    orig = (task_dir / "fixtures" / "tool.py").read_text(encoding="utf-8").splitlines()
    gbk = {i + 1 for i, ln in enumerate(orig) if "gbk" in ln.lower()}
    swallow = set()
    for i, ln in enumerate(orig):
        if ln.strip().startswith("except"):
            swallow.add(i + 1)
            for j in range(i + 1, min(i + 4, len(orig))):
                head = orig[j].strip().split()
                if head and head[0] in ("continue", "pass", "return"):
                    swallow.add(j + 1)
                    break
    return gbk, swallow


LINE_PATTERNS = [re.compile(r"第\s*(\d+)\s*行"), re.compile(r"(?i)\bline\s*(\d+)\b")]


def cited_lines(text):
    found = set()
    for pattern in LINE_PATTERNS:
        found |= {int(m) for m in pattern.findall(text)}
    return found


# --------------------------------------------------------------- 模块探针
def import_agent_tool(module_path):
    import importlib.util
    box = {}
    try:
        spec = importlib.util.spec_from_file_location("agent_tool_h05", str(module_path))
        module = importlib.util.module_from_spec(spec)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            spec.loader.exec_module(module)
        box["module"] = module
    except BaseException as exc:
        box["error"] = "%s: %s" % (type(exc).__name__, clamp(exc, 160))
    return box


def run_in_thread(fn, seconds, default):
    box = {"value": default, "error": None}

    def worker():
        try:
            box["value"] = fn()
        except BaseException as exc:
            box["error"] = exc

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join(seconds)
    if thread.is_alive():
        box["error"] = TimeoutError("探针执行超过 %ss（疑似死循环）" % seconds)
    return box["value"], box["error"]


def main(argv=None):
    ap = argparse.ArgumentParser(description="H05 grader")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--task-dir", required=True)
    args = ap.parse_args(argv)

    task_dir = Path(args.task_dir)
    run_dir = Path(args.run_dir)
    if not task_dir.is_dir():
        grader_error("--task-dir 不存在: %s" % task_dir)
    ledger = task_dir / "fixtures" / "ledger.csv"
    if not ledger.is_file():
        grader_error("缺少 fixtures/ledger.csv: %s" % ledger)
    truth = truth_summary(ledger)
    gbk_lines, swallow_lines = defect_lines(task_dir)
    if not gbk_lines or not swallow_lines:
        grader_error("fixtures/tool.py 里定位不到缺陷行（gbk=%s swallow=%s）"
                     % (sorted(gbk_lines), sorted(swallow_lines)))

    checks = []

    # ---- 1. out/summary.json 与真值一致
    summary_path = run_dir / "out" / "summary.json"
    if not summary_path.is_file():
        checks.append(("summary-correct", False, "期望 %s 存在，实际缺失" % summary_path.name))
    else:
        try:
            got = json.loads(summary_path.read_text(encoding="utf-8"))
        except Exception as exc:
            checks.append(("summary-correct", False, "summary.json 不是合法 JSON: %r" % (exc,)))
        else:
            ok = got == truth
            if ok:
                detail = "与真值一致（rows_total=%d amount_total=%d 品类=%d）" % (
                    truth["rows_total"], truth["amount_total"], len(truth["by_category"]))
            else:
                diff = []
                if got.get("rows_total") != truth["rows_total"]:
                    diff.append("rows_total 期望 %r 实际 %r" % (truth["rows_total"], got.get("rows_total")))
                if got.get("amount_total") != truth["amount_total"]:
                    diff.append("amount_total 期望 %r 实际 %r" % (truth["amount_total"], got.get("amount_total")))
                if got.get("by_category") != truth["by_category"]:
                    gc = got.get("by_category") or {}
                    missing = sorted(set(truth["by_category"]) - set(gc))
                    extra = sorted(set(gc) - set(truth["by_category"]))
                    wrong = [k for k in sorted(set(gc) & set(truth["by_category"]))
                             if gc[k] != truth["by_category"][k]]
                    diff.append("by_category 缺 %r / 多 %r / 值不对 %r" % (missing, extra, wrong))
                detail = "；".join(diff)
            checks.append(("summary-correct", ok, detail))

    # ---- 2. 修好的 tool.py 行为
    tool_path = run_dir / "tool.py"
    if not tool_path.is_file():
        for name in ("tool-parse", "tool-strict"):
            checks.append((name, False, "期望 %s 存在，实际缺失" % tool_path.name))
    else:
        box = import_agent_tool(tool_path)
        module = box.get("module")
        if module is None:
            for name in ("tool-parse", "tool-strict"):
                checks.append((name, False, "导入失败: %s" % box.get("error")))
        else:
            parse = getattr(module, "parse_bytes", None)
            if not callable(parse):
                checks.append(("tool-parse", False, "tool.py 没有可调用的 parse_bytes(data: bytes)"))
                checks.append(("tool-strict", False, "未执行：parse_bytes 不存在"))
            else:
                got, err = run_in_thread(lambda: parse(HIDDEN_CSV), 10, None)
                if err is not None:
                    checks.append(("tool-parse", False,
                                   "parse_bytes(UTF-8 隐藏样例) 抛 %s: %s"
                                   % (type(err).__name__, clamp(err, 120))))
                else:
                    want_json = json.dumps(HIDDEN_EXPECT, ensure_ascii=False, sort_keys=True)
                    got_json = json.dumps(got, ensure_ascii=False, sort_keys=True) if isinstance(got, list) else repr(got)
                    ok = got_json == want_json
                    checks.append(("tool-parse", ok,
                                   "与隐藏期望一致" if ok else "期望 %s，实际 %s" % (want_json, got_json)))

                strict_ok, strict_detail = True, []
                for raw in BAD_INPUTS:
                    res, bad_err = run_in_thread(lambda raw=raw: parse(raw), 10, None)
                    if bad_err is None:
                        strict_ok = False
                        strict_detail.append("输入 %r 未抛异常，返回 %r" % (raw, clamp(res, 80)))
                    elif not isinstance(bad_err, ValueError):
                        strict_ok = False
                        strict_detail.append("输入 %r 抛 %s（期望 ValueError）"
                                             % (raw, type(bad_err).__name__))
                checks.append(("tool-strict", strict_ok,
                               "不合规输入均抛 ValueError" if strict_ok else "；".join(strict_detail)))

    # ---- 3. rootcause.md 是否点到具体行号与机制
    root_path = run_dir / "rootcause.md"
    text = root_path.read_text(encoding="utf-8", errors="replace") if root_path.is_file() else ""
    cited = cited_lines(text)
    hit_a = sorted(cited & gbk_lines)
    hit_b = sorted(cited & swallow_lines)
    lines_ok = bool(hit_a) and bool(hit_b)
    checks.append(("rootcause-lines", lines_ok,
                   "已点到解码缺陷第 %s 行、吞异常缺陷第 %s 行（原始脚本对应行号 %s / %s）"
                   % (hit_a, hit_b, sorted(gbk_lines), sorted(swallow_lines))
                   if lines_ok else
                   "需要分别用「第 N 行」点到解码缺陷（原始 %s 行之一）与吞异常缺陷（原始 %s 行之一），实际点到 %s｜%s"
                   % (sorted(gbk_lines), sorted(swallow_lines), sorted(cited), clamp(text, 120))))

    low = text.lower()
    required = [
        ("gbk", "gbk" in low),
        ("utf-8", ("utf-8" in low) or ("utf8" in low)),
        ("except/吞异常", ("except" in low) or ("吞" in text) or ("静默" in text)),
        ("valueerror/抛出", ("valueerror" in low) or ("抛出" in text) or ("报错" in text) or ("raise" in low)),
    ]
    missing = [name for name, ok in required if not ok]
    checks.append(("rootcause-mechanism", not missing,
                   "四处机制都写到了" if not missing else "缺少: %s" % missing))

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

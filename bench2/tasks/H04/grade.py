#!/usr/bin/env python3
"""H04 判分器：long-pipeline，最终产物逐字节比对。

判分器按 task.md 的七步规则从 fixtures/raw.csv 自己重算一遍期望字节，
再与 <RUN_DIR>/out/report.txt 做字节比较。不采信被测产物里的任何自述。

退出码：0=PASS，1=FAIL，2=判分器自身错误（用法错 / 缺 fixture）。
被测产物缺失按 FAIL 处理，不按判分器错误处理。
只读 --run-dir 与 --task-dir/fixtures，不写任何文件。
"""

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

TASK_ID = "H04"
HEADER = "line_id|region|sku|status|qty|unit_cents|label"
INT_RE = re.compile(r"^-?\d+$")


def clamp(text, limit=200):
    text = str(text).replace("\r", "\\r").replace("\n", "\\n")
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
def tidy(field):
    """第 2 步：strip + 内部连续空格/制表符压成一个半角空格。"""
    return re.sub(r"[ \t]+", " ", field.strip())


def money(cents):
    """整数分 → 千分位金额（两小数、负数带前导负号、0 → 0.00）。"""
    sign = "-" if cents < 0 else ""
    whole, frac = divmod(abs(int(cents)), 100)
    return "%s%s.%02d" % (sign, "{:,}".format(whole), frac)


def load_rows(fixture_path):
    raw = fixture_path.read_bytes().decode("utf-8")
    rows = []
    seq = 0
    for index, line in enumerate(raw.split("\n")):
        line = unicodedata.normalize("NFKC", line)
        line = line.rstrip("\r")
        if not line.strip():
            continue
        if index == 0:  # 第 1 步：跳过表头（第一行）
            continue
        seq += 1
        fields = line.split("|")
        if len(fields) != 7:
            continue
        line_id, region, sku, status, qty, unit, label = [tidy(f) for f in fields]
        region = region.upper()
        sku = sku.upper()
        status = status.lower()
        if sku.isdigit():
            sku = sku.zfill(5)
        if not (INT_RE.match(qty) and INT_RE.match(unit)):
            continue
        qty_i, unit_i = int(qty), int(unit)
        if status not in ("paid", "refunded") or qty_i < 1:
            continue
        rows.append({"seq": seq, "region": region, "sku": sku,
                     "label": label, "total": qty_i * unit_i})
    return rows


def expected_bytes(rows):
    rows.sort(key=lambda r: (r["region"], -r["total"], -r["seq"]))
    order, groups = [], {}
    for row in rows:
        if row["region"] not in groups:
            groups[row["region"]] = []
            order.append(row["region"])
        groups[row["region"]].append(row)
    out = ["# summary v1", "regions=%d rows=%d" % (len(order), len(rows))]
    grand = 0
    for region in order:
        items = groups[region]
        total = sum(item["total"] for item in items)
        grand += total
        out.append("== %s ==" % region)
        out.append("rows  : %d" % len(items))
        out.append("total : %s" % money(total))
        out.append("max   : %s" % money(max(item["total"] for item in items)))
        out.append("first : %s" % items[0]["label"])
        out.append("skus  : %s" % ",".join(item["sku"] for item in items))
    out.append("--")
    out.append("grand_total=%s" % money(grand))
    return ("\n".join(out) + "\n").encode("utf-8"), order, len(rows), grand


def first_diff(want, got):
    limit = min(len(want), len(got))
    pos = 0
    while pos < limit and want[pos] == got[pos]:
        pos += 1
    lo = max(0, pos - 40)
    return pos, want[lo:pos + 40].decode("utf-8", "replace"), got[lo:pos + 40].decode("utf-8", "replace")


def main(argv=None):
    ap = argparse.ArgumentParser(description="H04 grader")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--task-dir", required=True)
    args = ap.parse_args(argv)

    task_dir = Path(args.task_dir)
    run_dir = Path(args.run_dir)
    fixture = task_dir / "fixtures" / "raw.csv"
    if not task_dir.is_dir():
        grader_error("--task-dir 不存在: %s" % task_dir)
    if not fixture.is_file():
        grader_error("缺少 fixtures/raw.csv: %s" % fixture)

    want, order, n_rows, grand = expected_bytes(load_rows(fixture))
    checks = []

    report = run_dir / "out" / "report.txt"
    exists = report.is_file()
    checks.append(("report-exists", exists,
                   "期望 %s 存在，实际 %s" % (report.name, "存在" if exists else "缺失")))
    if not exists:
        for name in ("no-crlf", "single-trailing-lf", "bytes-equal"):
            checks.append((name, False, "未执行：out/report.txt 缺失"))
        emit(False, checks, "缺少 out/report.txt，判据无法满足")

    got = report.read_bytes()
    checks.append(("no-crlf", b"\r" not in got,
                   "期望不含 \\r，实际 %s" % ("不含" if b"\r" not in got else "含 %d 个 \\r" % got.count(b"\r"))))

    tail_ok = got.endswith(b"\n") and not got.endswith(b"\n\n")
    checks.append(("single-trailing-lf", tail_ok,
                   "期望恰好一个结尾 \\n，实际结尾 80 字节=%r" % (got[-80:],)))

    equal = got == want
    detail = "期望 %d 字节，实际 %d 字节" % (len(want), len(got))
    if not equal:
        pos, want_w, got_w = first_diff(want, got)
        detail += "；首个差异在第 %d 字节附近：期望 ...%r，实际 ...%r" % (pos, want_w, got_w)
    checks.append(("bytes-equal", equal, detail))
    if equal:
        detail = "字节完全一致（%d 字节 / %d 组 / %d 行 / grand_total=%s）" % (
            len(want), len(order), n_rows, money(grand))
        checks[-1] = ("bytes-equal", True, detail)

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

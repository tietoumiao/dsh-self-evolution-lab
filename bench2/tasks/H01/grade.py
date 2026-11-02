#!/usr/bin/env python3
"""H01 判分器：文档内部冲突（正文 vs 附录）+ 按正文独立计算真值。

退出码：0=PASS，1=FAIL，2=判分器自身错误（用法错 / fixture 不可用）。
只读 --run-dir 与 --task-dir/fixtures，不写任何文件。
truth 一律由 fixtures 现算（单价表、正文采样时长、meter.csv），不采信产物自报数字。
"""

import argparse
import json
import re
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

TASK_ID = "H01"
TOP_KEYS = {"schema", "conflicts", "sites", "total_amount_cents"}
TOPICS = {"sample_period", "rounding"}
CONFLICT_KEYS = {"topic", "body", "appendix", "adopted"}
SIDE_KEYS = {"location", "quote"}
SITE_KEYS = {"kwh_milli", "amount_cents"}
# 每条冲突两侧引文必须命中的关键词（引文本身必须是原文，故这里只做"是否真的指向该冲突"的判据）
TOPIC_HINTS = {
    "rounding": (("四舍五入", "0.5 分"), ("0.05",)),
    "sample_period": (("15 分钟", "15"), ("30 分钟", "30")),
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


def norm(text):
    """去 Markdown 强调符 + 折叠空白，用于逐字引文比对（不做同义改写）。"""
    text = str(text).replace("*", "").replace("`", "").replace(">", "")
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------- fixtures → truth
def read_doc(task_dir):
    path = Path(task_dir) / "fixtures" / "policy.md"
    if not path.is_file():
        grader_error("缺少 fixtures/policy.md: %s" % path)
    try:
        return path.read_text(encoding="utf-8")
    except Exception as exc:
        grader_error("fixtures/policy.md 不可读: %r" % (exc,))


def split_regions(doc):
    idx = doc.find("## 附录 A")
    if idx < 0:
        grader_error("fixtures/policy.md 缺少「## 附录 A」分隔")
    return doc[:idx], doc[idx:]


def parse_prices(body):
    prices = {}
    for line in body.splitlines():
        m = re.match(r"^\|\s*([A-Z]\d+)\s*\|\s*([0-9]+(?:\.[0-9]+)?)\s*\|\s*$", line.strip())
        if m:
            prices[m.group(1)] = Decimal(m.group(2))
    if len(prices) != 3:
        grader_error("fixtures/policy.md 单价表解析到 %d 行（期望 3）" % len(prices))
    return prices


def parse_period_minutes(body):
    m = re.search(r"采样时长为\s*(\d+)\s*分钟", body)
    if not m:
        grader_error("fixtures/policy.md 正文缺少「采样时长为 N 分钟」")
    return int(m.group(1))


def load_readings(task_dir):
    path = Path(task_dir) / "fixtures" / "meter.csv"
    if not path.is_file():
        grader_error("缺少 fixtures/meter.csv: %s" % path)
    rows = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception as exc:
        grader_error("fixtures/meter.csv 不可读: %r" % (exc,))
    for line in lines[1:]:
        if not line.strip():
            continue
        parts = line.split(",")
        if len(parts) != 3:
            grader_error("fixtures/meter.csv 行格式异常: %r" % (line,))
        site, _ts, kw = parts[0].strip(), parts[1].strip(), parts[2].strip()
        rows.setdefault(site, []).append(Decimal(kw))
    if not rows:
        grader_error("fixtures/meter.csv 没有采样行")
    return rows


def compute_truth(task_dir):
    doc = read_doc(task_dir)
    body, appendix = split_regions(doc)
    period = parse_period_minutes(body)          # 正文口径，附录口径不参与
    prices = parse_prices(body)
    readings = load_readings(task_dir)
    hours = Decimal(period) / Decimal(60)
    sites, total = {}, 0
    for site in sorted(readings):
        if site not in prices:
            grader_error("站点 %s 在单价表中缺失" % site)
        kwh = sum(readings[site], Decimal(0)) * hours
        milli = (kwh * 1000).quantize(Decimal(1), rounding=ROUND_HALF_UP)
        cents = (kwh * prices[site] * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP)
        sites[site] = {"kwh_milli": int(milli), "amount_cents": int(cents)}
        total += int(cents)
    return {"sites": sites, "total_amount_cents": total, "period": period,
            "body_region": body, "appendix_region": appendix, "doc": doc}


# ---------------------------------------------------------------- 产物检查
def load_report(run_dir):
    path = Path(run_dir) / "report.json"
    if not path.is_file():
        return None, "期望 %s 存在，实际缺失" % path
    try:
        text = path.read_text(encoding="utf-8-sig")
    except Exception as exc:
        return None, "report.json 不是 UTF-8 文本: %r" % (exc,)
    try:
        data = json.loads(text)
    except Exception as exc:
        return None, "report.json 不是合法 JSON: %r（前 80 字符: %r）" % (exc, text[:80])
    if not isinstance(data, dict):
        return None, "report.json 顶层不是对象，实际 %s" % type(data).__name__
    return data, ""


def check_quotes(conflicts, truth):
    """逐条冲突：topic 合法 + 引文逐字来自对应区域 + 定位前缀正确 + adopted=body。"""
    body_region = norm(truth["body_region"])
    appendix_region = norm(truth["appendix_region"])
    problems, seen = [], []
    for i, item in enumerate(conflicts):
        tag = "#%d" % (i + 1)
        if not isinstance(item, dict):
            problems.append("%s 不是对象（实际 %s）" % (tag, type(item).__name__))
            continue
        if set(item) != CONFLICT_KEYS:
            problems.append("%s 键集 %s，期望 %s" % (tag, sorted(item), sorted(CONFLICT_KEYS)))
            continue
        topic = item.get("topic")
        if topic not in TOPICS:
            problems.append("%s topic=%r 不在 %s" % (tag, topic, sorted(TOPICS)))
            continue
        seen.append(topic)
        if item.get("adopted") != "body":
            problems.append("%s adopted=%r，期望 'body'" % (tag, item.get("adopted")))
        sides = []
        for side in ("body", "appendix"):
            block = item.get(side)
            if not isinstance(block, dict) or set(block) != SIDE_KEYS:
                problems.append("%s.%s 需要恰好 %s，实际 %r"
                                % (tag, side, sorted(SIDE_KEYS), block if not isinstance(block, dict) else sorted(block)))
                sides.append(None)
                continue
            loc, quote = block.get("location"), norm(block.get("quote"))
            if not isinstance(loc, str) or not loc.strip():
                problems.append("%s.%s.location 不是非空字符串（实际 %r）" % (tag, side, loc))
            if len(quote) < 10:
                problems.append("%s.%s.quote 过短（%d 字符）: %r" % (tag, side, len(quote), quote))
                sides.append(None)
                continue
            region = body_region if side == "body" else appendix_region
            if quote not in region:
                problems.append("%s.%s.quote 不是该区域原文: %r" % (tag, side, quote[:80]))
                sides.append(None)
                continue
            sides.append(quote)
        if None in sides:
            continue
        body_quote, app_quote = sides
        want_prefix = ("§", "附录")
        for side, text, prefix in (("body", item["body"]["location"], want_prefix[0]),
                                   ("appendix", item["appendix"]["location"], want_prefix[1])):
            if isinstance(text, str) and prefix not in text:
                problems.append("%s.%s.location=%r 缺少定位前缀 %r" % (tag, side, text, prefix))
        body_hints, app_hints = TOPIC_HINTS[topic]
        if not any(h in body_quote for h in body_hints):
            problems.append("%s 正文引文未命中 %s 的关键词: %r" % (tag, topic, body_quote[:60]))
        if not any(h in app_quote for h in app_hints):
            problems.append("%s 附录引文未命中 %s 的关键词: %r" % (tag, topic, app_quote[:60]))
    if sorted(seen) != sorted(TOPICS):
        problems.append("topic 覆盖 %s，期望各一条 %s" % (sorted(seen), sorted(TOPICS)))
    return problems


def check_sites(sites, truth):
    want = truth["sites"]
    problems = []
    if not isinstance(sites, dict):
        return ["sites 不是对象（实际 %s）" % type(sites).__name__]
    if set(sites) != set(want):
        problems.append("sites 键集 %s，期望 %s" % (sorted(sites), sorted(want)))
    for site in sorted(want):
        got = sites.get(site)
        if not isinstance(got, dict) or set(got) != SITE_KEYS:
            problems.append("sites.%s 需要恰好 %s，实际 %r"
                            % (site, sorted(SITE_KEYS), got if not isinstance(got, dict) else sorted(got)))
            continue
        for key in ("kwh_milli", "amount_cents"):
            actual = got.get(key)
            if type(actual) is not int:
                problems.append("sites.%s.%s 不是 int（实际 %r）" % (site, key, actual))
            elif actual != want[site][key]:
                problems.append("sites.%s.%s 期望 %d，实际 %d"
                                % (site, key, want[site][key], actual))
    return problems


def main(argv=None):
    ap = argparse.ArgumentParser(description="H01 grader")
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
    report, load_error = load_report(run_dir)

    checks = []
    checks.append(("report-shape", not load_error, load_error or "report.json 可解析且顶层为对象"))
    if load_error:
        for name in ("schema", "conflicts-count", "conflicts-content", "sites-values", "total-amount"):
            checks.append((name, False, "未执行：%s" % load_error))
        emit(False, checks, "产物 report.json 不可用，判据无法满足")

    top = set(report)
    checks.append(("top-keys", top == TOP_KEYS,
                   "期望顶层键 %s，实际 %s" % (sorted(TOP_KEYS), sorted(top))))
    checks.append(("schema-value", type(report.get("schema")) is int and report.get("schema") == 1,
                   "期望整数 1，实际 %r" % (report.get("schema"),)))

    conflicts = report.get("conflicts")
    is_list = isinstance(conflicts, list)
    checks.append(("conflicts-count", is_list and len(conflicts) == 2,
                   "期望恰好 2 条，实际 %s" % (len(conflicts) if is_list else type(conflicts).__name__)))
    if not is_list:
        checks.append(("conflicts-content", False, "conflicts 不是数组，无法逐条核对"))
    else:
        problems = check_quotes(conflicts, truth)
        checks.append(("conflicts-content", not problems,
                       "; ".join(problems) if problems else "两条冲突的定位/引文/取舍均合法"))

    problems = check_sites(report.get("sites"), truth)
    checks.append(("sites-values", not problems,
                   "; ".join(problems) if problems else "sites 数值与 fixtures 现算真值一致"))

    total = report.get("total_amount_cents")
    want_total = truth["total_amount_cents"]
    checks.append(("total-amount", type(total) is int and total == want_total,
                   "期望 %d，实际 %r" % (want_total, total)))

    all_ok = all(p for _, p, _ in checks)
    passed = sum(1 for _, p, _ in checks if p)
    emit(all_ok, checks, "%d/%d 项检查通过（真值按正文 %d 分钟口径现算）"
         % (passed, len(checks), truth["period"]))


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException as exc:  # 判分器自身异常 ⇒ exit 2
        sys.stderr.write("[%s] grader crash: %r\n" % (TASK_ID, exc))
        raise SystemExit(2)

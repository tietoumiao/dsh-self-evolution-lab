#!/usr/bin/env python3
"""ledger.py —— 无 git 环境下的实验账本：一行一条记录，可校验、可回滚。

设计原则：**账本只追加，不修补**。任何"我觉得分数应该是 X"的手工修正都不许进这里。

记录类型（event）：
  prepare   —— 生成了哪个 (genome, split) 的 run 目录；genome 块的 sha256 与字符数
  rollout   —— 跑完一个 run_dir；记录它是否为"空产物"（no_artifacts）
  grade     —— 一次 grade_all.py 的汇总结果（只记路径 + 摘要数字，分数真值仍在 score.json）
  mutation  —— G2 相对 G1 改了哪条规则，依据是哪些 dev 失败（必须列 task id，且只能是 dev）
  note      —— 其它事实（人工决策、环境故障）

用法：
  python agi/runner/ledger.py add --event prepare --data '{"genome":"G1",...}'
  python agi/runner/ledger.py verify        # 逐行校验 JSON 与 sha256 链
  python agi/runner/ledger.py tail -n 10
"""

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "agi" / "ledger.jsonl"
TZ = timezone(timedelta(hours=8))

# Windows 控制台默认 GBK，中文 print 会炸；统一转 UTF-8（实测必需）。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _now() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def _prev_hash() -> str:
    if not LEDGER.exists():
        return "GENESIS"
    last = ""
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        if line.strip():
            last = line
    if not last:
        return "GENESIS"
    return hashlib.sha256(last.encode("utf-8")).hexdigest()


def add(event: str, data: dict, actor: str = "lead") -> dict:
    rec = {
        "ts": _now(),
        "actor": actor,
        "event": event,
        "prev": _prev_hash(),
        "data": data,
    }
    line = json.dumps(rec, ensure_ascii=False, sort_keys=True)
    with LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    print(line)
    return rec


def verify() -> int:
    if not LEDGER.exists():
        print("LEDGER MISSING")
        return 2
    prev = "GENESIS"
    n = 0
    for i, line in enumerate(LEDGER.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as exc:
            print(f"FAIL line={i} json: {exc}")
            return 1
        if rec.get("prev") != prev:
            print(f"FAIL line={i} prev 链断裂：期望 {prev[:12]}… 实际 {str(rec.get('prev'))[:12]}…")
            return 1
        prev = hashlib.sha256(line.encode("utf-8")).hexdigest()
        n += 1
    print(f"LEDGER OK records={n} head={_prev_hash()[:16]}…")
    return 0


def tail(n: int) -> int:
    if not LEDGER.exists():
        print("LEDGER MISSING")
        return 2
    lines = [ln for ln in LEDGER.read_text(encoding="utf-8").splitlines() if ln.strip()]
    for line in lines[-n:]:
        rec = json.loads(line)
        print(f"{rec['ts']}  {rec['event']:<9} {json.dumps(rec['data'], ensure_ascii=False)[:300]}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="agi 实验账本")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add")
    a.add_argument("--event", required=True)
    a.add_argument("--data", required=True, help="JSON 对象字符串")
    a.add_argument("--actor", default="lead")
    sub.add_parser("verify")
    t = sub.add_parser("tail")
    t.add_argument("-n", type=int, default=10)
    args = ap.parse_args()

    if args.cmd == "add":
        try:
            data = json.loads(args.data)
        except json.JSONDecodeError as exc:
            print(f"data 不是合法 JSON：{exc}", file=sys.stderr)
            return 2
        add(args.event, data, args.actor)
        return 0
    if args.cmd == "verify":
        return verify()
    return tail(args.n)


if __name__ == "__main__":
    raise SystemExit(main())

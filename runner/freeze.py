#!/usr/bin/env python3
"""freeze.py —— 冻结一个基因组：算规范摘要、做快照、写账本。

规范摘要口径（`agi\\PROTOCOL.md` §1）：
  `agi\\genome\\` 下所有文件按相对路径字典序 → 逐文件 sha256(内容) →
  拼 `"<相对路径>\\n<文件哈希>\\n"` → 对拼接串取 sha256。

**已声明的偏差（2026-11-02，Lead）**：摘要排除 `__pycache__/` 与 `*.pyc`
（Python 字节码缓存，构建产物而非源；纳入会让摘要随执行历史漂移，失去"可复现"意义）。
该偏差写进账本 `note`，并在 `agi\\REPORT.md` 的"未验证/偏差"一节复述。

用法：
  python agi/runner/freeze.py --genome G1                 # 冻结 + 快照 + 账本
  python agi/runner/freeze.py --genome G1 --check         # 只校验当前目录摘要与账本最新冻结是否一致
"""

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GENOME_DIR = ROOT / "agi" / "genome"
SNAP_ROOT = ROOT / "agi" / "_snapshots"
LEDGER = ROOT / "agi" / "ledger.jsonl"
TZ = timezone(timedelta(hours=8))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

EXCLUDE_DIRS = {"__pycache__"}
EXCLUDE_SUFFIX = {".pyc", ".pyo"}


def iter_files():
    files = []
    for path in sorted(GENOME_DIR.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(GENOME_DIR)
        if any(part in EXCLUDE_DIRS for part in rel.parts):
            continue
        if path.suffix in EXCLUDE_SUFFIX:
            continue
        files.append((rel, path))
    return files


def digest():
    """返回 (canonical_sha256, {relpath: filehash})。"""
    files = iter_files()
    joined = ""
    per_file = {}
    for rel, path in files:
        h = hashlib.sha256(path.read_bytes()).hexdigest()
        rel_s = str(rel).replace("\\", "/")
        per_file[rel_s] = h
        joined += f"{rel_s}\n{h}\n"
    return hashlib.sha256(joined.encode("utf-8")).hexdigest(), per_file


def ledger_append(rec: dict):
    prev = "GENESIS"
    if LEDGER.exists():
        for line in LEDGER.read_text(encoding="utf-8").splitlines():
            if line.strip():
                prev = hashlib.sha256(line.encode("utf-8")).hexdigest()
    full = {"ts": datetime.now(TZ).isoformat(timespec="seconds"), "actor": "lead", "prev": prev}
    full.update(rec)
    line = json.dumps(full, ensure_ascii=False, sort_keys=True)
    with LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    return full


def last_freeze(genome: str):
    if not LEDGER.exists():
        return None
    found = None
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec.get("event") == "genome_freeze" and rec.get("genome") == genome:
            found = rec
    return found


def block_digest(genome: str):
    """取实际注入块的 sha256（进程内渲染；沙箱禁 fd 管道，不能 subprocess）。"""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import _genome  # noqa: E402
    try:
        text = _genome.block(genome)
    except Exception as exc:  # 基因组自身不合格
        return None, f"render failed: {exc!r}"
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    shape = f"lines={text.count(chr(10)) + 1} chars={len(text)} bytes={len(text.encode('utf-8'))}"
    return sha, shape


def freeze(genome: str) -> int:
    manifest_path = GENOME_DIR / "genomes" / f"{genome}.json"
    if not manifest_path.is_file():
        print(f"FAIL 缺少基因组定义：{manifest_path}")
        return 2
    canonical, per_file = digest()
    block_sha, block_shape = block_digest(genome)
    snap = SNAP_ROOT / genome / canonical[:12]
    if snap.exists():
        shutil.rmtree(snap)
    shutil.copytree(GENOME_DIR, snap,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"))
    rec = ledger_append({
        "event": "genome_freeze",
        "genome": genome,
        "genome_sha256": canonical,
        "block_sha256": block_sha,
        "block_shape": block_shape,
        "files": per_file,
        "snapshot": str(snap.relative_to(ROOT)).replace("\\", "/"),
        "note": ("genome_sha256 = agi/genome 全目录规范摘要（PROTOCOL §1 口径，对 G0/G1/G2 必然相同）；"
                 "block_sha256 = apply.py 渲染出的注入块摘要（真正区分刺激物）；"
                 "已声明偏差：目录摘要排除 __pycache__/ 与 *.pyc"),
    })
    print(json.dumps({
        "genome": genome,
        "genome_sha256": canonical,
        "block_sha256": block_sha,
        "files": len(per_file),
        "snapshot": rec["snapshot"],
        "ts": rec["ts"],
    }, ensure_ascii=False, indent=2))
    return 0


def check(genome: str) -> int:
    canonical, per_file = digest()
    rec = last_freeze(genome)
    if rec is None:
        print(f"FAIL 账本里没有 {genome} 的冻结记录")
        return 2
    ok = rec["genome_sha256"] == canonical
    print(f"{'OK  ' if ok else 'FAIL'} genome={genome} now={canonical[:16]}… ledger={rec['genome_sha256'][:16]}… files={len(per_file)}")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="冻结基因组并记账")
    ap.add_argument("--genome", default=None)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--digest-only", action="store_true")
    args = ap.parse_args()
    if args.digest_only:
        canonical, per_file = digest()
        print(f"genome_dir={GENOME_DIR} sha256={canonical} files={len(per_file)}")
        return 0
    if not args.genome:
        print("FAIL 需要 --genome（或用 --digest-only）")
        return 2
    if args.check:
        return check(args.genome)
    return freeze(args.genome)


if __name__ == "__main__":
    raise SystemExit(main())

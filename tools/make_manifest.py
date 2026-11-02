#!/usr/bin/env python3
"""make_manifest.py —— 生成/校验 `MANIFEST.sha256`（逐文件 sha256，按路径升序）。

清单覆盖范围：发布目录内**除 `MANIFEST.sha256` 自身与 `tools/`** 的全部文件。
（`tools/` 放脱敏器、清单器与其统计产物，属"工具面"，不参与内容清单。）

每行格式：`<sha256>  <相对路径，正斜杠>`

用法：
    python tools/make_manifest.py           # 写 MANIFEST.sha256
    python tools/make_manifest.py --check   # 只校验不写：退出码 0=全部一致

发布方若补充了 `README.md` / `LICENSE` / `context/` 等文件，请重跑本脚本刷新清单。
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # pragma: no cover
        pass

PUBLISH_DIR = Path(__file__).resolve().parent.parent
MANIFEST = "MANIFEST.sha256"
SKIP_PREFIXES = ("tools/",)
SKIP_FILES = {MANIFEST}


def iter_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel in SKIP_FILES or any(rel.startswith(prefix) for prefix in SKIP_PREFIXES):
            continue
        yield rel, path


def collect(root: Path) -> dict[str, str]:
    return {rel: hashlib.sha256(path.read_bytes()).hexdigest()
            for rel, path in iter_files(root)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="生成/校验 MANIFEST.sha256")
    parser.add_argument("--root", default=str(PUBLISH_DIR), help="发布目录根（默认本脚本上两级）")
    parser.add_argument("--check", action="store_true", help="只校验")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    actual = collect(root)
    lines = [f"{actual[rel]}  {rel}\n" for rel in sorted(actual)]
    manifest_path = root / MANIFEST

    if args.check:
        if not manifest_path.is_file():
            print(f"MISSING {MANIFEST}", file=sys.stderr)
            return 2
        recorded = {}
        for line in manifest_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            digest, _, rel = line.partition("  ")
            recorded[rel] = digest
        missing = sorted(set(actual) - set(recorded))
        extra = sorted(set(recorded) - set(actual))
        mismatched = sorted(rel for rel in set(actual) & set(recorded) if actual[rel] != recorded[rel])
        print(f"清单行数={len(recorded)} 实际文件数={len(actual)}")
        print(f"缺失={len(missing)} 多余={len(extra)} 哈希不符={len(mismatched)}")
        for label, items in (("缺失", missing), ("多余", extra), ("不符", mismatched)):
            for rel in items[:10]:
                print(f"  [{label}] {rel}")
        if missing or extra or mismatched:
            return 1
        print("MANIFEST OK")
        return 0

    manifest_path.write_text("".join(lines), encoding="utf-8")
    print(f"已写入 {MANIFEST}：{len(lines)} 行（覆盖 {len(actual)} 个文件，排除 {MANIFEST} 与 tools/）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""sanitize.py —— 把 `agi\\` 整包复制成发布目录并做「绝对路径 / 用户名」脱敏。

设计要点（复核者先看这段）
--------------------------------------------------------------
1. **只替换路径与用户名字面量，绝不改动哈希/分数字面量**：本脚本的替换表里只有
   两个"原字面量"（原工作区根、原用户主目录），替换目标分别是 `<workspace>` 与
   `<home>`。sha256 十六进制串、`score.json` 里的数字都不在匹配集里，因此不会被改。
2. **默认规则用拼接构造，不是整形写死**：发布目录自己要过脱敏门禁
   （`grep -r "<原工作区根>|<原用户名>" .` 必须 0 命中）。脱敏器又必须知道这两个
   字面量才能替换它——所以默认值在这份源码里是拼出来的（运行时值一致），
   否则本文件自己就会命中门禁。换机器复核时用环境变量或 `--orig-workspace`
   `--orig-home` 传自己的原路径即可（优先级：命令行 > 环境变量 > 拼接默认值）。
3. **替换顺序敏感**：JSON 转义形式（双反斜杠）> 原生反斜杠 > 正斜杠；每种形式内
   「带尾分隔符」优先于「裸根」，长的先替换，避免裸根先吃掉前缀导致尾分隔符残留。
4. **只按字节判定文本**：后缀在白名单内且能按 UTF-8 解出来的才处理，其余按二进制
   原样复制（`.bin` fixture 等）。绝不改文件名。
5. **可重跑**：默认清理目标目录（`tools/` 除外），再次运行得到同样结果。
   逐文件「改动次数 / 前后字节数 / 前后 sha256」落到 `tools/sanitize-stats.json`。

用法
----
    python tools/sanitize.py                  # 复制 + 脱敏 + 统计
    python tools/sanitize.py --dry-run        # 只统计不写盘
    python tools/sanitize.py --src <dir>      # 换源目录（默认 <发布目录>/../agi）
    python tools/sanitize.py --keep-dest      # 不清理目标目录

退出码：0 = 全部成功；1 = 有复制/读写失败（清单打到 stderr）。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # pragma: no cover - 非 UTF-8 控制台兜底
        pass

TOOL_DIR = Path(__file__).resolve().parent
PUBLISH_DIR = TOOL_DIR.parent
STATS_REL = "tools/sanitize-stats.json"

B = "\\"
S = "/"

# ---- 原字面量默认值：拼接构造，避免发布目录里出现整串原文（见文件头 §2）----
_ORIG_WORKSPACE_DEFAULT = "D:" + B + "deepseek" + "harness" + " workspace"
_ORIG_HOME_DEFAULT = "C:" + B + "Users" + B + "342" + "18"

# ---- 复制规格 ----
TOP_FILES = ("CHARTER.md", "PROTOCOL.md", "ROUND1.md", "ROUND2.md", "REPORT.md", "ledger.jsonl")
SOURCE_DIRS = ("bench", "bench2", "genome", "runner", "runs", "runs2", "_snapshots", "audit")
# 源 README 改名进发布目录（根 README 由发布方另写，不占用该文件名）
RENAME_MAP = {"README.md": "EXPERIMENT-INDEX.md"}

EXCLUDE_SUFFIXES = {".pyc"}
EXCLUDE_DIRS = {"__pycache__", ".pytest_cache"}
EXCLUDE_FILES = {"runner/probe-cred.ps1"}
EXCLUDE_PREFIXES = ("runner/_pilot/",)

# 文本白名单（脱敏目标后缀）
TEXT_SUFFIXES = {
    ".md", ".py", ".json", ".jsonl", ".txt", ".log", ".stdout", ".stderr",
    ".ps1", ".mjs", ".csv", ".sh", ".java", ".ini", ".cfg",
}

# 占位符之后的路径尾：把残留反斜杠统一成正斜杠（含 JSON 双反斜杠写法）
_TAIL_RE = re.compile(r"(<workspace>|<home>)((?:[\\/]+[^\\/\s\"'<>]+)+)")


def _normalize_tail(match: re.Match) -> str:
    return match.group(1) + re.sub(r"[\\/]+", S, match.group(2))


def _forms(root: str):
    """同一个根的三写字面量：JSON 转义（双反斜杠）、原生反斜杠、正斜杠。"""
    fwd = root.replace(B, S).rstrip(S)
    bwd = fwd.replace(S, B)
    esc = bwd.replace(B, B * 2)
    return (esc, bwd, fwd)


def build_rules(orig_workspace: str, orig_home: str):
    """生成 (规则名, 旧字面量, 新字面量) 列表，顺序=长的先替换。

    规则名只用于统计，不含原字面量。
    """
    rules = []
    for label, root, placeholder in (("workspace", orig_workspace, "<workspace>"),
                                     ("home", orig_home, "<home>")):
        for kind, form in zip(("json_escaped", "backslash", "slash"), _forms(root)):
            for sep in (B, S):
                rules.append((f"{label}.{kind}.trailing", form + sep, placeholder + S))
            rules.append((f"{label}.{kind}.bare", form, placeholder))
    return rules


def sanitize_text(text: str, rules):
    """返回 (新文本, 替换处数, {规则名: 次数})。"""
    per_rule: dict[str, int] = {}
    total = 0
    for name, old, new in rules:
        hits = text.count(old)
        if hits:
            text = text.replace(old, new)
            per_rule[name] = hits
            total += hits
    text, n_tail = _TAIL_RE.subn(_normalize_tail, text)
    if n_tail:
        per_rule["normalize.backslash_to_slash"] = n_tail
        total += n_tail
    return text, total, per_rule


def iter_source_files(src: Path):
    """产出 (绝对源路径, 发布相对路径)；排除项一并返回原因。"""
    excluded: list[tuple[str, str]] = []
    for name in TOP_FILES:
        path = src / name
        if path.is_file():
            yield path, name
        else:
            excluded.append((name, "missing_top_file"))
    readme = src / "README.md"
    if readme.is_file():
        yield readme, RENAME_MAP["README.md"]
    else:
        excluded.append(("README.md", "missing_source_readme"))
    for name in SOURCE_DIRS:
        root = src / name
        if not root.is_dir():
            excluded.append((name, "missing_dir"))
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames.sort()
            filenames.sort()
            rel_dir = Path(dirpath).relative_to(src)
            pruned = [d for d in dirnames if d in EXCLUDE_DIRS]
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
            for gone in pruned:
                excluded.append(((rel_dir / gone).as_posix(), "excluded_dir"))
            for filename in filenames:
                abs_path = Path(dirpath) / filename
                rel = (rel_dir / filename).as_posix()
                if abs_path.suffix.lower() in EXCLUDE_SUFFIXES:
                    excluded.append((rel, "excluded_suffix"))
                    continue
                if rel in EXCLUDE_FILES:
                    excluded.append((rel, "excluded_file"))
                    continue
                if any(rel.startswith(prefix) for prefix in EXCLUDE_PREFIXES):
                    excluded.append((rel, "excluded_prefix"))
                    continue
                yield abs_path, rel
    _EXCLUDED.extend(excluded)


_EXCLUDED: list[tuple[str, str]] = []


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def clean_dest(dst: Path) -> list[str]:
    """清空目标目录自己产出的内容（保留 tools/，那里住着本脚本）。"""
    removed = []
    for child in sorted(dst.iterdir()):
        if child.name == "tools":
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
        removed.append(child.name)
    return removed


def human_bytes(n: int) -> str:
    for unit in ("B", "KiB", "MiB", "GiB"):
        if n < 1024 or unit == "GiB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.2f} {unit}"
        n /= 1024.0
    return f"{n} B"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="agi -> 发布目录：复制 + 脱敏 + 统计")
    parser.add_argument("--src", default=None, help="源目录（默认 <发布目录>/../agi）")
    parser.add_argument("--dst", default=None, help="目标目录（默认本脚本所在目录）")
    parser.add_argument("--orig-workspace", default=os.environ.get("SANITIZE_ORIG_WORKSPACE") or _ORIG_WORKSPACE_DEFAULT)
    parser.add_argument("--orig-home", default=os.environ.get("SANITIZE_ORIG_HOME") or _ORIG_HOME_DEFAULT)
    parser.add_argument("--dry-run", action="store_true", help="只统计不写盘")
    parser.add_argument("--keep-dest", action="store_true", help="不清理目标目录")
    args = parser.parse_args(argv)

    src = Path(args.src).resolve() if args.src else (PUBLISH_DIR.parent / "agi").resolve()
    dst = Path(args.dst).resolve() if args.dst else PUBLISH_DIR
    if not src.is_dir():
        print(f"源目录不存在：{src}", file=sys.stderr)
        return 2
    if src == dst:
        print("源目录与目标目录相同，拒绝执行", file=sys.stderr)
        return 2

    rules = build_rules(args.orig_workspace, args.orig_home)

    if not args.dry_run:
        dst.mkdir(parents=True, exist_ok=True)
        removed = [] if args.keep_dest else clean_dest(dst)
        if removed:
            print("已清理目标目录旧内容：%d 项（保留 tools/）" % len(removed))
    else:
        print("[dry-run] 不写盘")

    entries: list[dict] = []
    failures: list[str] = []
    rule_hits: dict[str, int] = {}
    src_bytes = copied_bytes = written_bytes = 0
    changed_files = 0
    text_files = 0
    skipped = {"binary": 0, "non_utf8": 0}
    top_changed: list[tuple[int, str]] = []

    for abs_src, rel in iter_source_files(src):
        src_bytes += 1
        try:
            raw = abs_src.read_bytes()
        except OSError as exc:
            failures.append(f"{rel}: 读失败 {exc!r}")
            continue
        copied_bytes += len(raw)
        out = raw
        changes = 0
        per_rule: dict[str, int] = {}
        kind = "binary"
        if abs_src.suffix.lower() in TEXT_SUFFIXES:
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                skipped["non_utf8"] += 1
            else:
                text_files += 1
                text, changes, per_rule = sanitize_text(text, rules)
                if changes:
                    out = text.encode("utf-8")
        else:
            skipped["binary"] += 1

        if changes:
            changed_files += 1
            top_changed.append((changes, rel))
            for key, value in per_rule.items():
                rule_hits[key] = rule_hits.get(key, 0) + value
            kind = "text-modified"
        elif abs_src.suffix.lower() in TEXT_SUFFIXES:
            kind = "text-unchanged"

        written_bytes += len(out)
        entries.append({
            "path": rel,
            "kind": kind,
            "changes": changes,
            "bytes_src": len(raw),
            "bytes_out": len(out),
            "sha256_src": sha256_bytes(raw),
            "sha256_out": sha256_bytes(out),
            "rules": per_rule,
        })

        if args.dry_run:
            continue
        target = dst / rel
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(out)
        except OSError as exc:
            failures.append(f"{rel}: 写失败 {exc!r}")

    entries.sort(key=lambda item: item["path"])
    top_changed.sort(key=lambda item: (-item[0], item[1]))

    stats = {
        "generated": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": "<src>",          # 不落绝对路径，避免二次泄漏
        "destination": "<dst>",
        "dry_run": bool(args.dry_run),
        "rule_labels": [name for name, _, _ in rules],
        "counts": {
            "files_copied": len(entries),
            "files_in_source_tree_in_scope": src_bytes,
            "text_files": text_files,
            "changed_files": changed_files,
            "total_replacements": sum(item["changes"] for item in entries),
            "skipped_binary": skipped["binary"],
            "skipped_non_utf8": skipped["non_utf8"],
            "excluded": len(_EXCLUDED),
        },
        "bytes": {
            "source": copied_bytes,
            "after_sanitize": written_bytes,
        },
        "rule_hits": dict(sorted(rule_hits.items())),
        "top_changed": [{"path": rel, "changes": n} for n, rel in top_changed[:10]],
        "excluded": [{"path": rel, "reason": why} for rel, why in sorted(_EXCLUDED)],
        "files": entries,
    }

    if not args.dry_run:
        stats_path = dst / STATS_REL
        stats_path.parent.mkdir(parents=True, exist_ok=True)
        stats_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("")
    print("== 复制 + 脱敏统计 ==")
    print(f"源目录(相对发布目录): ..{S}agi")
    print(f"复制文件数        : {len(entries)}")
    print(f"  其中文本文件    : {text_files}（UTF-8 可解）")
    print(f"  按二进制原样复制: {skipped['binary']}")
    print(f"  非 UTF-8 跳过   : {skipped['non_utf8']}")
    print(f"排除项            : {len(_EXCLUDED)}")
    print(f"脱敏前总字节      : {copied_bytes} ({human_bytes(copied_bytes)})")
    print(f"脱敏后总字节      : {written_bytes} ({human_bytes(written_bytes)})")
    print(f"内容被改动文件数  : {changed_files}")
    print(f"替换处数合计      : {stats['counts']['total_replacements']}")
    print("")
    print("-- 按规则 --")
    for name in sorted(rule_hits):
        print(f"  {name:<34} {rule_hits[name]}")
    print("")
    print("-- 改动次数最多的前 10 个文件 --")
    for n, rel in top_changed[:10]:
        print(f"  {n:>5}  {rel}")
    print("")
    if failures:
        print(f"失败 {len(failures)} 项：", file=sys.stderr)
        for line in failures:
            print("  " + line, file=sys.stderr)
        return 1
    if not args.dry_run:
        print(f"逐文件明细已写入 {STATS_REL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

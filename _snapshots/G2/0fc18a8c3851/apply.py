#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""agi\\genome\\apply.py —— 把一套规则基因组渲染成可注入的规则块（确定性 / 可复核 / 可回滚）。

用法（在工作区根目录跑）：
  python agi\\genome\\apply.py --genome G1                  # 注入块 → stdout
  python agi\\genome\\apply.py --genome G1 --out block.txt   # 落盘（UTF-8 / LF / 无 BOM）
  python agi\\genome\\apply.py --genome G1 --shape           # 只打印 sha256 / 行数 / 字符数

确定性契约：同一份 genomes\\*.json + rules\\R*.md + process\\P*.md ⇒ 逐字节相同的输出。
不读时间戳、不读环境变量、不读文件 mtime、不依赖 dict 遍历顺序；行尾固定 LF，编码固定 UTF-8（无 BOM）。

真源（单一来源，改规则只改这里）：
  rules\\R*.md      一条规则一个文件（id/axis/genomes/claim/why/source，≤12 行）
  process\\P*.md    一段过程指令一个文件（id/genomes/heading/1..n/source）
  genomes\\G*.json  只声明「本档收哪几条」，不复制正文
  rules.json       清单与来源索引；test_apply.py 负责核对它与 rules\\*.md 是否一致（防两源漂移）
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent          # …\\agi\\genome
WS = HERE.parent.parent                         # 工作区根（skills\\ 所在处）
RULES_DIR = HERE / "rules"
PROC_DIR = HERE / "process"
GENOME_DIR = HERE / "genomes"

MAX_LINES = 60          # 注入块 ≤60 行
MAX_CHARS = 3000        # 注入块 ≤3000 字符
MAX_RULE_LINES = 12     # 单条规则文件 ≤12 行

# 注入块里不允许出现的字样：它面向被测 agent，不得暴露实验/判分语境，也不得泄题
FORBIDDEN_WORDS = ("评测", "基准", "得分", "打分", "评分", "判分", "分数")
FORBIDDEN_RE = re.compile(r"T(?:0[1-9]|1[0-2])")


class GenomeError(Exception):
    """基因组自身不合格（缺字段、越界、引用来源不存在、超长、出现禁用字样）。"""


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _parse_block(path: Path) -> dict:
    """解析 `key: value` 形式的规则/过程文件；纯数字 key 视为有序步骤。"""
    fields: dict[str, object] = {}
    steps: list[tuple[int, str]] = []
    for raw in _read(path).splitlines():
        line = raw.rstrip()
        if not line or line.startswith("#"):
            continue
        key, sep, val = line.partition(": ")
        if not sep:
            raise GenomeError(f"{path.name}: 无法解析的行：{line!r}")
        key, val = key.strip(), val.strip()
        if key.isdigit():
            steps.append((int(key), val))
        else:
            fields[key] = val
    if steps:
        steps.sort()
        if [n for n, _ in steps] != list(range(1, len(steps) + 1)):
            raise GenomeError(f"{path.name}: 步骤编号必须从 1 连续递增，实得 {[n for n, _ in steps]}")
        fields["steps"] = [v for _, v in steps]
    return fields


def _require(fields: dict, keys: tuple[str, ...], name: str) -> None:
    missing = [k for k in keys if not fields.get(k)]
    if missing:
        raise GenomeError(f"{name}: 缺字段 {missing}")


def load_rule(rid: str) -> dict:
    path = RULES_DIR / f"{rid}.md"
    if not path.is_file():
        raise GenomeError(f"规则文件不存在：rules\\{rid}.md")
    fields = _parse_block(path)
    _require(fields, ("id", "axis", "genomes", "claim", "why", "source"), path.name)
    if fields["id"] != rid:
        raise GenomeError(f"{path.name}: id 字段 {fields['id']!r} 与文件名不一致")
    body = [ln for ln in _read(path).splitlines() if ln.strip()]
    if len(body) > MAX_RULE_LINES:
        raise GenomeError(f"{path.name}: {len(body)} 个非空行 > {MAX_RULE_LINES}")
    return fields


def load_process(pid: str) -> dict:
    path = PROC_DIR / f"{pid}.md"
    if not path.is_file():
        raise GenomeError(f"过程文件不存在：process\\{pid}.md")
    fields = _parse_block(path)
    _require(fields, ("id", "genomes", "heading", "steps", "source"), path.name)
    if fields["id"] != pid:
        raise GenomeError(f"{path.name}: id 字段 {fields['id']!r} 与文件名不一致")
    return fields


def _in_genome(fields: dict, genome_id: str) -> bool:
    return genome_id in [x.strip() for x in str(fields["genomes"]).split(",")]


def render(genome_id: str) -> str:
    """渲染一个基因组的注入块。纯函数：只依赖磁盘上的真源文件内容。"""
    gpath = GENOME_DIR / f"{genome_id}.json"
    if not gpath.is_file():
        raise GenomeError(f"基因组文件不存在：genomes\\{genome_id}.json")
    g = json.loads(_read(gpath))
    if g.get("genome") != genome_id:
        raise GenomeError(f"{gpath.name}: genome 字段 {g.get('genome')!r} 与文件名不一致")

    rules = [load_rule(rid) for rid in g["rules"]]
    procs = [load_process(pid) for pid in g.get("process") or []]
    for r in rules:
        if not _in_genome(r, genome_id):
            raise GenomeError(f"{r['id']}: genomes 字段不含 {genome_id}，与 {genome_id}.json 声明冲突")
    for p in procs:
        if not _in_genome(p, genome_id):
            raise GenomeError(f"{p['id']}: genomes 字段不含 {genome_id}，与 {genome_id}.json 声明冲突")
    if not rules and not procs and not g.get("empty_note"):
        raise GenomeError(f"{gpath.name}: 无规则也无 empty_note，无法渲染空档")

    out: list[str] = ["<RUN_RULES>", f"# ruleset {g['ruleset']} | rules={len(rules)}", "<discipline>"]
    if rules:
        out.extend(f"[{r['id']}] {r['claim']}" for r in rules)
    else:
        out.append(str(g["empty_note"]))
    out.append("</discipline>")
    for p in procs:
        out.append("<self_check>")
        out.append(str(p["heading"]))
        out.extend(f"{i}. {step}" for i, step in enumerate(p["steps"], 1))
        out.append("</self_check>")
    out.extend(["以下规则优先于你的默认习惯。", "</RUN_RULES>"])
    text = "\n".join(out) + "\n"
    _check_invariants(genome_id, text)
    return text


def _check_invariants(genome_id: str, text: str) -> None:
    lines = text.count("\n")
    if lines > MAX_LINES:
        raise GenomeError(f"{genome_id}: 注入块 {lines} 行 > {MAX_LINES}")
    if len(text) > MAX_CHARS:
        raise GenomeError(f"{genome_id}: 注入块 {len(text)} 字符 > {MAX_CHARS}")
    for word in FORBIDDEN_WORDS:
        if word in text:
            raise GenomeError(f"{genome_id}: 注入块出现禁用字样 {word!r}")
    m = FORBIDDEN_RE.search(text)
    if m:
        raise GenomeError(f"{genome_id}: 注入块出现禁用字样 {m.group(0)!r}")


def shape_line(text: str) -> str:
    data = text.encode("utf-8")
    return (
        f"sha256={hashlib.sha256(data).hexdigest()} "
        f"lines={text.count(chr(10))} chars={len(text)} bytes={len(data)}"
    )


def _emit(text: str) -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # 老环境/被重定向时退回默认
        pass
    sys.stdout.write(text)


def main(argv: list[str] | None = None) -> int:
    choices = sorted(p.stem for p in GENOME_DIR.glob("*.json"))
    ap = argparse.ArgumentParser(description="渲染规则基因组注入块（确定性）")
    ap.add_argument("--genome", required=True, choices=choices, help="G0 / G1 / G2")
    ap.add_argument("--out", type=Path, default=None, help="写文件（UTF-8 / LF / 无 BOM）")
    ap.add_argument("--shape", action="store_true", help="只打印 sha256 / 行数 / 字符数")
    args = ap.parse_args(argv)

    try:
        text = render(args.genome)
    except (GenomeError, json.JSONDecodeError, KeyError) as exc:
        print(f"apply: error: {exc}", file=sys.stderr)
        return 1

    if args.out is not None:
        try:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_bytes(text.encode("utf-8"))
        except OSError as exc:
            print(f"apply: error: 写 {args.out} 失败：{exc}", file=sys.stderr)
            return 1

    if args.shape:
        _emit(f"genome={args.genome} {shape_line(text)}\n")
    elif args.out is None:
        _emit(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

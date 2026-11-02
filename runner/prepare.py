#!/usr/bin/env python3
"""prepare.py —— 为 (genome, split) 生成 rollout 目录、注入 prompt、产出 manifest。

只做三件事，不判分、不跑 agent：
  1. 按 `agi\\bench\\tasks\\*\\meta.json` 的 split 选任务；
  2. 每个 (task, rep) 建 `agi\\runs\\<genome>\\<split>\\<task>\\rep<k>\\`，把 fixtures 复制进 `input\\`；
  3. 写 `prompt.txt`（基因组注入块 + 任务书）与 `manifest.json`（交给 grade_all.py）。

用法：
  python agi/runner/prepare.py --genome G1 --split dev --reps 2
  python agi/runner/prepare.py --all        # 按 PROTOCOL 默认矩阵：dev n=2，heldout n=1

安全：只写 `agi\\runs\\`，不删任何既有目录；拒绝覆盖非空 run 目录（除非 --force）。
"""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # <workspace>
AGI = ROOT / "agi"
BENCH = AGI / "bench" / "tasks"                      # 第一轮；--round 2 时切到 bench2
GENOME_APPLY = AGI / "genome" / "apply.py"
RUNS = AGI / "runs"

# Windows 控制台默认 GBK，中文 print 会炸；统一转 UTF-8（实测必需）。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

DEFAULT_SPLIT_REPS = {"dev": 2, "heldout": 1}


def genome_block(genome: str) -> str:
    """取基因组注入块（进程内调 apply.render；不用 subprocess —— 沙箱禁 fd 管道）。"""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import _genome  # noqa: E402  （同目录脚本）
    return _genome.block(genome)


def discover(split: str):
    tasks = []
    for meta_path in sorted(BENCH.glob("*/meta.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("split") == split:
            tasks.append((meta_path.parent, meta))
    return tasks


def build_manifest(genome: str, split: str, reps: int, force: bool, manifest_only: bool = False) -> Path:
    block = genome_block(genome)
    block_hash = hashlib.sha256(block.encode("utf-8")).hexdigest()
    tasks = discover(split)
    if not tasks:
        raise SystemExit(f"split={split} 下没有任务（agi/bench/tasks/*/meta.json）")

    manifest = {
        "genome": genome,
        "split": split,
        "genome_sha256": block_hash,
        "genome_chars": len(block),
        "reps": reps,
        "runs": [],
    }
    for task_dir, meta in tasks:
        task = meta["task"]
        fixtures = task_dir / "fixtures"
        for rep in range(1, reps + 1):
            run_dir = RUNS / genome / split / task / f"rep{rep}"
            if manifest_only:
                if not run_dir.is_dir():
                    raise SystemExit(f"--manifest-only 但 run 目录不存在：{run_dir}")
            else:
                if run_dir.exists() and any(run_dir.iterdir()):
                    if not force:
                        raise SystemExit(f"run 目录已存在且非空，拒绝覆盖（--force 可覆盖）：{run_dir}")
                    shutil.rmtree(run_dir)
                run_dir.mkdir(parents=True, exist_ok=True)
                if fixtures.is_dir():
                    shutil.copytree(fixtures, run_dir / "input", dirs_exist_ok=True)

            task_md = (task_dir / "task.md").read_text(encoding="utf-8").strip()
            header = (
                f"# 工作目录\n\n"
                f"你的工作目录（绝对路径）：`{run_dir}`\n"
                f"输入文件在 `{run_dir}\\input\\`（只读，不要改动）。\n"
                f"所有产物写到工作目录本身（`{run_dir}`），除非任务书另有所指。\n"
                f"完成前请自己确认产物已落盘在该目录下。\n\n"
                f"# 边界\n\n"
                f"- 只使用工作目录与 `input\\`。**禁止**浏览 `agi\\bench`、`agi\\bench2`、`agi\\genome`、"
                f"`agi\\runs`、`agi\\runs2`、`skills\\`、`worklogs\\` 等工作区其它目录去找线索；任务所需信息全部在任务书与 `input\\` 里。\n"
                f"- 不联网、不安装依赖、不修改工作目录以外的任何文件。\n"
                f"- 不要向人提问（本环境无人应答）；缺什么就在产物里如实写明缺什么。\n"
                f"- 时间盒：按任务书写的时间预算（通常 3–8 分钟）；没写就 10 分钟内交，不要无限打磨。\n\n---\n\n"
            )
            prompt = header + (block.strip() + "\n\n---\n\n" if block.strip() else "") + task_md + "\n"
            if not manifest_only:
                (run_dir / "prompt.txt").write_text(prompt, encoding="utf-8")

            manifest["runs"].append({
                "task": task,
                "rep": rep,
                "axis": meta.get("axis"),
                "weight": meta.get("weight", 1),
                # 绝对路径：grade_all.py 会把相对路径解析成「manifest 目录 + 相对路径」，
                # 实测会把 run_dir 拼成 agi/runs/G0/dev/agi/runs/G0/dev/T05/rep2（全判 FAIL）。
                "run_dir": str(run_dir.resolve()).replace("\\", "/"),
                "run_dir_rel": str(run_dir.relative_to(ROOT)).replace("\\", "/"),
            })

    out = RUNS / genome / split / "manifest.json"
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "manifest": str(out.relative_to(ROOT)).replace("\\", "/"),
        "genome": genome, "split": split, "reps": reps,
        "tasks": [m["task"] for _, m in tasks],
        "runs": len(manifest["runs"]),
        "genome_sha256": block_hash,
        "manifest_only": manifest_only,
    }, ensure_ascii=False, indent=2))
    return out


def main() -> int:
    global BENCH, RUNS
    ap = argparse.ArgumentParser(description="生成 agi rollout 目录与 manifest")
    ap.add_argument("--genome", action="append", default=[], help="G0/G1/G2，可重复")
    ap.add_argument("--split", action="append", default=[], help="dev/heldout，可重复")
    ap.add_argument("--reps", type=int, default=None, help="每个任务重复次数（默认按 split）")
    ap.add_argument("--round", type=int, default=1, help="1=agi/bench（预注册）；2=agi/bench2（探索）")
    ap.add_argument("--all", action="store_true", help="按默认矩阵全量生成")
    ap.add_argument("--force", action="store_true", help="覆盖已存在的非空 run 目录")
    ap.add_argument("--manifest-only", action="store_true",
                    help="只重写 manifest（不建目录、不动 prompt.txt），用于修路径口径")
    args = ap.parse_args()

    if args.round == 2:
        BENCH = AGI / "bench2" / "tasks"
        RUNS = AGI / "runs2"

    if args.all:
        genomes, splits = ["G0", "G1", "G2"], ["dev", "heldout"]
    else:
        genomes = args.genome or ["G0"]
        splits = args.split or ["dev"]

    for genome in genomes:
        for split in splits:
            reps = args.reps if args.reps is not None else DEFAULT_SPLIT_REPS[split]
            build_manifest(genome, split, reps, args.force, args.manifest_only)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""verify_cells.py —— 发布目录内的**替代验证**：不依赖 manifest 里的绝对路径重算逐格分数。

为什么要这一步
--------------
脱敏把 `runs*/<G>/<split>/manifest.json` 里的 `run_dir`（原绝对路径）替换成了
`<workspace>/...` 占位符。`grade_all.py` 拿到这种路径必然判「run_dir 不存在 → FAIL」，
于是 `python bench/grade_all.py --manifest runs/G1/dev/manifest.json` 在发布目录里
**不可能**复现原 `score.json`（这是脱敏的必然代价，不是数据损坏）。

本脚本换一条路径重建同一组格子：用 manifest 里保留完好的 `run_dir_rel`
（`agi/runs/G1/dev/T01/rep1`）去掉开头的 `agi/` 前缀，指到发布目录自己的同名子目录，
生成**临时 manifest**（写在系统临时目录，不进发布目录），再照常调用 `grade_all.py`，
最后把重算结果与磁盘上的 `score.json` 逐条对齐。

用法
----
    python tools/verify_cells.py                     # 默认只验 runs/G1/dev
    python tools/verify_cells.py --cell runs2/G2/heldout
    python tools/verify_cells.py --all               # 验全部 runs* 格子

退出码：0 = 每一格都与 score.json 一致；1 = 有格子不一致或判分器报错；2 = 找不到格子。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # pragma: no cover
        pass

ROOT = Path(__file__).resolve().parent.parent
CELL_KEYS = ("n", "pass", "weighted_pass", "weighted_total", "per_task", "per_axis", "grader_errors")


def run_grade_all(bench: Path, manifest: Path, out: Path, timeout: int = 300):
    """跑 grade_all.py；沙箱禁管道时退回文件重定向（同 bench/selftest.py 的做法）。"""
    cmd = [sys.executable, str(bench / "grade_all.py"),
           "--manifest", str(manifest), "--out", str(out)]
    env = {"PYTHONIOENCODING": "utf-8", **os.environ}
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", stdin=subprocess.DEVNULL, timeout=timeout, env=env)
        return proc.returncode, proc.stdout, proc.stderr
    except PermissionError:
        pass
    except subprocess.TimeoutExpired:
        return 124, "", "grade_all 超时"
    with tempfile.NamedTemporaryFile(suffix=".stdout", delete=False) as fout, \
            tempfile.NamedTemporaryFile(suffix=".stderr", delete=False) as ferr:
        out_name, err_name = fout.name, ferr.name
    try:
        with open(out_name, "wb") as fout, open(err_name, "wb") as ferr:
            proc = subprocess.run(cmd, stdout=fout, stderr=ferr, stdin=subprocess.DEVNULL,
                                 timeout=timeout, env=env)
        return (proc.returncode,
                Path(out_name).read_text(encoding="utf-8", errors="replace"),
                Path(err_name).read_text(encoding="utf-8", errors="replace"))
    finally:
        for name in (out_name, err_name):
            try:
                Path(name).unlink()
            except OSError:
                pass


def relative_run_dir(entry: dict) -> str:
    """把 manifest 条目还原成发布目录内的相对 run 目录。"""
    raw = entry.get("run_dir_rel") or entry.get("run_dir") or ""
    rel = str(raw).replace("\\", "/").strip()
    if rel.startswith("agi/"):
        rel = rel[len("agi/"):]
    return rel.lstrip("/")


def check_cell(cell_dir: Path) -> dict:
    cell_label = cell_dir.relative_to(ROOT).as_posix() if cell_dir.is_relative_to(ROOT) else cell_dir.as_posix()
    manifest = cell_dir / "manifest.json"
    score = cell_dir / "score.json"
    if not manifest.is_file() or not score.is_file():
        return {"cell": cell_label, "status": "SKIP", "detail": "缺 manifest.json 或 score.json"}
    data = json.loads(manifest.read_text(encoding="utf-8"))
    # 用相对路径的首段判断属于哪套 bench（绝对路径的 parts[0] 是盘符，不能拿它判断）
    bench_rel = "bench2" if cell_label.split("/")[0] == "runs2" else "bench"
    rebuilt = dict(data)
    rebuilt["runs"] = []
    missing = []
    for entry in data.get("runs", []):
        rel = relative_run_dir(entry)
        target = ROOT / rel
        if not target.is_dir():
            missing.append(rel)
        item = dict(entry)
        item["run_dir"] = str(target)
        item["run_dir_rel"] = rel
        rebuilt["runs"].append(item)
    fd_m, name_m = tempfile.mkstemp(suffix=".manifest.json")
    fd_o, name_o = tempfile.mkstemp(suffix=".score.json")
    os.close(fd_m)
    os.close(fd_o)
    tmp_manifest, tmp_out = Path(name_m), Path(name_o)
    try:
        tmp_manifest.write_text(json.dumps(rebuilt, ensure_ascii=False, indent=2), encoding="utf-8")
        code, stdout, stderr = run_grade_all(ROOT / bench_rel, tmp_manifest, tmp_out)
        if not tmp_out.is_file():
            return {"cell": cell_label, "status": "ERROR",
                    "detail": f"grade_all 未产出结果 rc={code} stderr={stderr.strip()[:200]}"}
        fresh = json.loads(tmp_out.read_text(encoding="utf-8"))
    finally:
        for path in (tmp_manifest, tmp_out):
            try:
                path.unlink()
            except OSError:
                pass
    old = json.loads(score.read_text(encoding="utf-8"))
    diffs = []
    for key in CELL_KEYS:
        if fresh.get(key) != old.get(key):
            diffs.append(key)
    cell = {"cell": cell_label, "status": "MATCH" if not diffs else "DIFF",
            "rc": code, "missing_run_dirs": missing, "diff_keys": diffs,
            "old": {k: old.get(k) for k in ("n", "pass", "weighted_pass", "weighted_total")},
            "fresh": {k: fresh.get(k) for k in ("n", "pass", "weighted_pass", "weighted_total")},
            "per_task_equal": fresh.get("per_task") == old.get("per_task"), "bench": bench_rel}
    return cell


def discover_cells() -> list[Path]:
    """发现所有 (genome, split) 格子：同目录下同时有 manifest.json 与 score.json。

    注意：任务产物里也可能出现 `manifest.json`（例如 T03 的 run 目录），
    所以必须用同目录的 `score.json` 兜住，不能只看 manifest.json。
    """
    cells = []
    for manifest in sorted(ROOT.glob("runs*/**/manifest.json")):
        if (manifest.parent / "score.json").is_file():
            cells.append(manifest.parent)
    return cells


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="发布目录逐格重算，与 score.json 对齐")
    parser.add_argument("--cell", action="append", default=None,
                        help="要验的格子目录（相对发布目录，如 runs/G1/dev）；可重复")
    parser.add_argument("--all", action="store_true", help="验全部 runs* 格子")
    args = parser.parse_args(argv)

    if args.all:
        targets = discover_cells()
    elif args.cell:
        targets = [ROOT / item for item in args.cell]
    else:
        targets = [ROOT / "runs/G1/dev"]

    if not targets:
        print("找不到任何格子", file=sys.stderr)
        return 2

    bad = 0
    for cell_dir in targets:
        result = check_cell(cell_dir)
        status = result["status"]
        if status != "MATCH":
            bad += 1
        print(f"[{status}] {result['cell']}  (bench={result.get('bench', '-')})")
        if status == "MATCH":
            print(f"    score.json 复现：n={result['old']['n']} pass={result['old']['pass']} "
                  f"weighted={result['old']['weighted_pass']}/{result['old']['weighted_total']}"
                  f"  per_task 逐条相同={result['per_task_equal']}")
        else:
            print(f"    缺失 run_dir: {result.get('missing_run_dirs')}")
            print(f"    不一致字段: {result.get('diff_keys')}")
            print(f"    score.json: {result.get('old')}")
            print(f"    重算结果  : {result.get('fresh')}")
            if result.get("detail"):
                print(f"    说明: {result['detail']}")
    print("")
    print(f"格子数={len(targets)} 一致={len(targets) - bad} 不一致/异常={bad}")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

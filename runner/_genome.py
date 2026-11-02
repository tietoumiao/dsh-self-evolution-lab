#!/usr/bin/env python3
"""_genome.py —— 进程内取基因组注入块。

**为什么不用 subprocess**：本机沙箱下 `subprocess.run(capture_output=True)` 会在
`_winapi.CreatePipe` 抛 `PermissionError: [WinError 5] 拒绝访问`（2026-11-02 实测，
ops_bash 启动的 python 进程里必现）。因此 runner 侧一律进程内 import `apply.py` 调 `render()`，
不建管道、不重定向。
"""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APPLY_PATH = ROOT / "agi" / "genome" / "apply.py"

_cache = {}


def _module():
    if "mod" in _cache:
        return _cache["mod"]
    spec = importlib.util.spec_from_file_location("agi_genome_apply", str(APPLY_PATH))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载基因组渲染器：{APPLY_PATH}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["agi_genome_apply"] = mod
    spec.loader.exec_module(mod)
    _cache["mod"] = mod
    return mod


def block(genome: str) -> str:
    """返回注入块正文（UTF-8 文本，含 <RUN_RULES> 外壳）。"""
    return _module().render(genome)


def shape_line(genome: str) -> str:
    mod = _module()
    return mod.shape_line(mod.render(genome))


if __name__ == "__main__":
    for g in ("G0", "G1", "G2"):
        if len(sys.argv) > 1 and g not in sys.argv[1:]:
            continue
        text = block(g)
        print(f"genome={g} lines={text.count(chr(10)) + 1} chars={len(text)}")

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""agi\\genome\\test_apply.py —— 基因组自证（exit 0 = 全部通过）。

跑法：python agi\\genome\\test_apply.py

断言：
  A. 三档都能渲染，且渲染确定性（同一档连渲两次 sha256 相同）
  B. G2 ⊃ G1 ⊃ G0：G1 的规则段逐字出现在 G2；G0 规则集为空（空集是任何集合的子集）
  C. G0 不含任何规则行
  D. 每档渲染都在 ≤60 行 / ≤3000 字符内，且不含禁用字样
  E. 每条规则文件 ≤12 行、字段齐全；rules.json 与 rules\\*.md 逐字段一致（防两源漂移）
  F. 每条 source 指向的文件真实存在，且「摘句」是原文件里的逐字子串（防编造引用）
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

try:  # 固定 stdout 为 UTF-8：本机默认是 gb2312，中文/符号会乱码或直接抛 UnicodeEncodeError
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

import apply as A  # noqa: E402

GENOMES = ("G0", "G1", "G2")
RULE_LINE_RE = re.compile(r"^\[(R\d{2})\]", re.M)

CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    CHECKS.append((name, bool(ok), detail))
    return bool(ok)


def rule_ids(text: str) -> list[str]:
    return RULE_LINE_RE.findall(text)


def section(text: str, start: str, end: str) -> str:
    i = text.index(start)
    j = text.index(end, i) + len(end)
    return text[i:j]


def shape_dict(text: str) -> dict[str, str]:
    return dict(kv.split("=", 1) for kv in A.shape_line(text).split())


def verify_source(rid: str, source: str) -> list[str]:
    """核对来源：路径必须存在；有「摘句」就必须是原文件逐字子串；没有摘句则必须有 § 节名。

    引用约定：source 用「；」分段；段首写 `<相对路径>.md`，或以 `§` 开头的续段（表示同一文件）。
    """
    problems: list[str] = []
    current_path: Path | None = None
    current_rel = ""
    for part in [p.strip() for p in source.split("；") if p.strip()]:
        if part.startswith("§"):
            if current_path is None:
                problems.append(f"{rid}: 续段之前没有出现过 .md 路径：{part!r}")
                continue
            rel, rest = current_rel, part
        else:
            m = re.match(r"^([^\s]+?\.md)\s*(.*)$", part)
            if not m:
                problems.append(f"{rid}: 来源段既不是路径也不是 § 续段：{part!r}")
                continue
            rel, rest = m.group(1), m.group(2)
            current_rel = rel
            current_path = A.WS / rel.replace("\\", "/")
            if not current_path.is_file():
                problems.append(f"{rid}: 来源文件不存在：{rel}")
                continue
        body = current_path.read_text(encoding="utf-8")
        quotes = re.findall(r"「([^」]+)」", rest)
        for quote in quotes:
            if quote not in body:
                problems.append(f"{rid}: 引文不是原文件里的逐字子串：{current_rel} 「{quote}」")
        if not quotes and "§" not in rest:
            problems.append(f"{rid}: 来源段既无摘句也无 § 节名：{part!r}")
    if current_path is None:
        problems.append(f"{rid}: source 里没有任何 .md 路径")
    return problems


def main() -> int:
    # ---- A. 渲染 + 确定性 ----------------------------------------------------
    texts: dict[str, str] = {}
    for g in GENOMES:
        try:
            texts[g] = A.render(g)
        except Exception as exc:  # noqa: BLE001
            print(f"FATAL 渲染 {g} 失败：{exc}")
            return 1
        check(f"{g} 渲染确定性（连渲两次 sha256 相同）",
              shape_dict(A.render(g))["sha256"] == shape_dict(texts[g])["sha256"])

    print("== 注入块形状（--shape 口径） ==")
    print(f"{'genome':<7}{'lines':>6}{'chars':>7}{'bytes':>7}{'rules':>6}  sha256")
    for g in GENOMES:
        d = shape_dict(texts[g])
        print(f"{g:<7}{d['lines']:>6}{d['chars']:>7}{d['bytes']:>7}{len(rule_ids(texts[g])):>6}  {d['sha256']}")
    print()

    ids = {g: rule_ids(texts[g]) for g in GENOMES}

    # ---- B. G2 ⊃ G1 ⊃ G0 -----------------------------------------------------
    check("G0 规则集为空（空集是任何集合的子集，故 G0 在最内层）", ids["G0"] == [], f"实得 {ids['G0']}")
    check("G1 规则数在 5–7 条区间内", 5 <= len(ids["G1"]) <= 7, f"实得 {len(ids['G1'])} 条")
    check("G1 的规则全部出现在 G2（id 集合一致）", set(ids["G1"]) == set(ids["G2"]), f"G1={ids['G1']} G2={ids['G2']}")
    check("G1 的 <discipline> 段逐字出现在 G2 里",
          section(texts["G1"], "<discipline>", "</discipline>") in texts["G2"])
    for line in [ln for ln in texts["G1"].splitlines() if ln.startswith("[R")]:
        check(f"G2 含 G1 的同一条规则行 {line.split(']')[0]}]", line in texts["G2"])
    check("G1 与 G2 的末句「以下规则优先于你的默认习惯。」一致",
          "以下规则优先于你的默认习惯。" in texts["G1"] and "以下规则优先于你的默认习惯。" in texts["G2"])
    check("G1 无 <self_check>，G2 有 <self_check>",
          "<self_check>" not in texts["G1"] and "<self_check>" in texts["G2"])
    check("G2 的过程明确要求「3 个失败点」与回复里的「自检」一节",
          "3 个失败点" in texts["G2"] and "「自检」" in texts["G2"])

    # ---- C. G0 不含规则行 ----------------------------------------------------
    check("G0 不含任何规则行（无 ^[Rxx] 行）", rule_ids(texts["G0"]) == [])
    check("G0 只含中性说明", "无附加纪律规则" in texts["G0"], "未找到中性说明")
    check("三档外壳一致：首行 <RUN_RULES> / 倒数第二行末句 / 末行 </RUN_RULES>",
          all(texts[g].splitlines()[0] == "<RUN_RULES>" for g in GENOMES)
          and all(texts[g].splitlines()[-2] == "以下规则优先于你的默认习惯。" for g in GENOMES)
          and all(texts[g].splitlines()[-1] == "</RUN_RULES>" for g in GENOMES))

    # ---- D. 长度 / 禁用字样 --------------------------------------------------
    for g in GENOMES:
        d = shape_dict(texts[g])
        check(f"{g} ≤ {A.MAX_LINES} 行", int(d["lines"]) <= A.MAX_LINES, f"实得 {d['lines']}")
        check(f"{g} ≤ {A.MAX_CHARS} 字符", int(d["chars"]) <= A.MAX_CHARS, f"实得 {d['chars']}")
        hits = [w for w in A.FORBIDDEN_WORDS if w in texts[g]] + A.FORBIDDEN_RE.findall(texts[g])
        check(f"{g} 无禁用字样 / 无题号", hits == [], f"命中 {hits}")

    # ---- E. 规则文件 + rules.json 一致性 ------------------------------------
    manifest = json.loads((HERE / "rules.json").read_text(encoding="utf-8"))
    by_id = {r["id"]: r for r in manifest["rules"]}
    check("rules.json 的 id 集合 == G1 的规则 id 集合", set(by_id) == set(ids["G1"]),
          f"manifest={sorted(by_id)} G1={ids['G1']}")
    for rid in ids["G1"]:
        fields = A.load_rule(rid)
        body_lines = [ln for ln in (HERE / "rules" / f"{rid}.md").read_text(encoding="utf-8").splitlines() if ln.strip()]
        check(f"{rid} 文件 ≤{A.MAX_RULE_LINES} 行", len(body_lines) <= A.MAX_RULE_LINES, f"实得 {len(body_lines)}")
        check(f"{rid} claim 是单行、可执行", "\n" not in str(fields["claim"]) and len(str(fields["claim"])) >= 15)
        check(f"{rid} axis 取自契约枚举",
              fields["axis"] in {"code", "spec", "computation", "honesty", "env-discipline", "verification"},
              str(fields["axis"]))
        entry = by_id[rid]
        same = (entry["claim"] == fields["claim"] and entry["axis"] == fields["axis"]
                and entry["source"] == fields["source"]
                and entry["in"] == [x.strip() for x in str(fields["genomes"]).split(",")])
        check(f"{rid} rules.json 与 rules\\{rid}.md 逐字段一致", same)
        problems = verify_source(rid, str(fields["source"]))
        check(f"{rid} source 指向真实文件且摘句逐字可查", not problems, "；".join(problems))

    # ---- F. 过程块去向 -------------------------------------------------------
    proc_ids = {p["id"] for p in manifest.get("process_blocks", [])}
    check("过程块只在 G2（G1 无过程块、G2 有）",
          "<self_check>" in texts["G2"] and "<self_check>" not in texts["G1"])
    check("rules.json 声明了过程块去向", proc_ids == {"P01"}, f"实得 {proc_ids}")
    for pid in proc_ids:
        part = [p for p in manifest["process_blocks"] if p["id"] == pid][0]
        check(f"{pid} 的 in 字段为 ['G2']", part["in"] == ["G2"], str(part["in"]))
        problems = [f"{pid}: 来源文件不存在：{rel}"
                    for rel in re.findall(r"([^\s；]+?\.md)", part["source"])
                    if not (A.WS / rel.replace("\\", "/")).is_file()]
        check(f"{pid} source 里的 .md 路径都存在", not problems, "；".join(problems))

    # ---- 汇总 ---------------------------------------------------------------
    print("== 断言 ==")
    for name, ok, detail in CHECKS:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  <{detail}>" if detail and not ok else ""))
    n_fail = sum(1 for _, ok, _ in CHECKS if not ok)
    print()
    print(f"PASS={len(CHECKS) - n_fail} FAIL={n_fail}")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

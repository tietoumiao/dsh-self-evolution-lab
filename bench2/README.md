# 第二轮基准（`agi\bench2`）实现说明

判据本体是 `CONTRACT.md`（本轮为差异契约，缺省条款沿用第一轮 `agi\bench\CONTRACT.md`）。
本文件只记录**实现侧**的对照关系、跑法与已实测证据，不定义判据。

## 1. 归属与目录

| 路径 | 归属 | 状态 |
|---|---|---|
| `CONTRACT.md` / `grade_all.py` / `selftest.py` | Lead | 只读（Lead 在 §2 变更记录里补记了 8 键与六轴裁决） |
| `tasks\H01..H03` + 本文件 | bench-hard-a | 已落盘 |
| `tasks\H04..H06` | bench-hard-b | 并行实现，本文件不描述 |

split：`H01–H03` = `dev`，`H04–H06` = `heldout`；全部 `weight=1`。

## 2. 怎么跑

```bash
# 单任务判分（0=PASS / 1=FAIL / 2=判分器自身错误）
python agi\bench2\tasks\H01\grade.py --run-dir agi\bench2\tasks\H01\selftest\good --task-dir agi\bench2\tasks\H01

# 全库双向门禁（good 必须 PASS、bad 必须 FAIL，任一不满足 exit 1）
python agi\bench2\selftest.py
```

## 3. H01–H03：形状、判据与"坏解"为什么会被抓

| 任务 | axis / hardness | 输入 | 产物 | 判分器怎么独立算真值 | bad 靠什么内容被判 FAIL |
|---|---|---|---|---|---|
| H01 | `conflict` | `policy.md`（正文 §0–§5 + 附录 A/B 互斥）+ `meter.csv` | `report.json` | 现场解析 fixtures：单价表、**正文**采样时长、`meter.csv`，用 `Decimal` + `ROUND_HALF_UP` 现算 `kwh_milli`/`amount_cents` | `conflicts` 只列 1 条（静默采信附录 B 的 30 分钟），且电量/金额/合计全部按 30 分钟算 ⇒ 4 项判据全挂 |
| H02 | `cross-file` | `config.json` + `schema.sql` + `deploy.md`（恰好 1 个字段不一致） | `diff.json` + `config.fixed.json` | 三份 fixtures 各自正则解析后交叉比对，自己判定唯一不一致字段与基准值 | 采信"两份一致、schema 是例外"，把 `expected` 写成 3000（手册历史值 5000 / 相似字段为诱饵）⇒ 差异与修正两处都错 |
| H03 | `broken-test` | `SPEC.md` + `impl.py` + `test_impl.py`（4 条对、2 条断言写错） | `impl.py` + `test_impl.py` + `notes.md` | 27 条隐藏真值用例直接压在**被提交的** `impl.py` 上；测试文件与 fixtures 逐方法比对 | 改 `impl.py` 迎合错测试（`KB`→1024、`fits` 改严格小于）⇒ 隐藏用例 3 条失败；`notes.md` 也没写出正确期望 ⇒ 判据挂 |

三个任务都满足「坏解必须因**内容**被判 FAIL」：删文件/空目录不在判据路径上，bad 是完整可跑的交付物。

难度来源（对应 `CONTRACT.md` §2 的"翻车形状"）：

- H01 的冲突在**同一份文档内部**，且两处冲突各自影响数值；`kwh_milli` 与 `amount_cents` 各埋了一个 `.5` 的进位点（`12062.5` → 12063、`472.5` → 473），用 `round()`（银行家舍入）或提前取整都会差 1；另有 `A1` 的"先取整再计价"陷阱（746 vs 747）。
- H02 的不一致字段与 `deploy.md` 里的历史值（5000）、非本表字段（`retry_backoff_ms`）混在一起；且"多数一致"是指向错误的引力——两份材料同值、只有基准文件不同。
- H03 的错测试**看起来像是实现错了**，正确解必须顶住"改实现让它变绿"的诱惑，并逐条说明理由。

## 4. 实现侧的取舍（可复核）

- **判分器不写任何文件**：H03 用进程内 `importlib` + `unittest` 跑被提交的测试（`sys.dont_write_bytecode = True`），不落 `.pyc`、不落临时 stdout 文件。本机沙箱禁 fd 管道，`subprocess.run(capture_output=True)` 会抛 `PermissionError WinError 5`，所以没有走子进程。
- **隐藏真值不落 fixtures**：H01/H02 的真值由 fixtures 现算（不硬编码结果），H03 的 27 条行为用例只存在于 `grade.py`，防止被测方照抄。
- **失败必带原文**：每条 `check.detail` 都给出期望值与实际值（截断 200 字符），便于人工复核。

## 5. 已实测证据（原样 stdout 见回执）

- `H01`：good `exit 0`（7/7）、bad `exit 1`（3/7），失败项 `conflicts-count` `conflicts-content` `sites-values` `total-amount`。
- `H02`：good `exit 0`（8/8）、bad `exit 1`（5/8），失败项 `conflict` `fixed-corrected` `fixed-matches-schema`。
- `H03`：good `exit 0`（7/7）、bad `exit 1`（4/7），失败项 `impl-behavior` `tests-minimal-fix` `notes-defects`。

## 6. 已知契约冲突与裁决（留证，勿再踩）

落盘时发现 `CONTRACT.md` §2 要求 `meta.json` 带 `hardness`，而 `selftest.py`（当时与第一轮逐字相同）第 38 行 `META_KEYS` 只有 7 键、第 182 行对多余键直接记 NG ⇒ 二者互斥，6 个任务不可能全绿。
Lead 裁决（2026-11-02）：改 `agi\bench2\selftest.py`（`META_KEYS` 加 `hardness`、`AXES` 注册六个新轴），不改第一轮 `agi\bench\`；`CONTRACT.md` §2 已补记"8 键 + 六轴"为唯一口径。本目录三个任务的 `axis` 因此取 `conflict` / `cross-file` / `broken-test`。

# 第二轮基准契约（探索性 · 非预注册主实验）

> **定位**：第一轮（`agi\bench\`，T01–T12）在 6 个单元格上**全部打满**（dev 10/12、heldout 6/6，三配置完全一致），说明那套题**对当前底座没有区分度**。第二轮的存在理由只有一条：**把难度推到底座会失败的地方**，看纪律规则/自检过程在那里有没有作用。它**不能**用来推翻或加强第一轮的结论——第一轮按 `agi\CHARTER.md` §3 已判。

## 0. 复用第一轮契约

判分器 CLI / `meta.json` 键名 / `selftest\good|bad` 双向判别 / 单行 JSON / 控制台 UTF-8 / 缺产物按 FAIL 等，**全部沿用 `agi\bench\CONTRACT.md`（只读）**。本文件只写差异。

## 1. 目录（与第一轮完全隔离）

```
agi\bench2\
  CONTRACT.md      # 本文件（Lead）
  grade_all.py     # 从 agi\bench\ 复制（TASKS_DIR 相对自身，故复制即可）
  selftest.py      # 从 agi\bench\ 复制
  README.md        # bench-hard-a 所有
  tasks\H01..H03\  # bench-hard-a
  tasks\H04..H06\  # bench-hard-b
```

split：`H01–H03` = `dev`；`H04–H06` = `heldout`。

## 2. 难度要求（本轮唯一目的）

第一轮饱和的原因可复核：题面自包含、单一答案、错误一眼可见。因此本轮每个任务**必须**至少命中下面一种"模型常见翻车形状"，并在 `meta.json` 的 `hardness` 字段里写明是哪一种：

**`meta.json` 的键集本轮是 8 个**（第一轮 7 键 + `hardness`；`agi\bench2\selftest.py` 已按此放宽）：
`task / title / split / axis / weight / time_budget_min / requires / hardness`，其中 `axis` 取下面六个枚举之一（也已在 selftest 的 `AXES` 里注册）：
`conflict` / `cross-file` / `broken-test` / `long-pipeline` / `tool-failure` / `precision`。
`weight` 一律 `1`。

- `conflict`：文档内部有冲突（正文 vs 附录/两节互斥），且题面给了优先规则并要求**显式列出冲突项**；静默挑一边 = FAIL。
- `cross-file`：同一条事实散在 3 个文件里，其中 1 处不一致；要求产出精确的差异报告 + 按指定基准修正。
- `broken-test`：给的测试本身有错，正确做法是**修测试**并说明理由，改实现去迎合错测试 = FAIL。
- `long-pipeline`：≥6 步串行变换，最终产物逐字节比对（空格、排序稳定性、千分位、末尾换行都算）。
- `tool-failure`：给的脚本因编码/静默吞异常而产出错数据，要求修好并写出根因（须指向具体行/机制）。
- `precision`：多币种/多税率/四舍五入细则，用浮点必差 1 分；要求十进制精确 + 中间过程可复核。

> 变更记录（2026-11-02，Lead 裁决）：两名实现方同时报"CONTRACT 要求 `hardness`，但 `selftest.py` 只认 7 键"，二者互斥。裁决：**改 `agi\bench2\selftest.py`（放宽 `META_KEYS` + 注册六个 axis）**，不改第一轮 `agi\bench\`；本 §2 补记 8 键与枚举，作为唯一口径。

硬约束：
1. **必须有 `selftest\good\` 且真的能 PASS**：good 就是"把这道题做对"的交付物，等于**你已证明这道题可解**。做不出 good ⇒ 这道题有问题，改题，不许放宽判据。
2. `selftest\bad\` 必须是"最像样的错误解"（静默挑冲突一边、改实现迎合错测试、浮点差 1 分、漏掉排序稳定性），空目录不算。
3. `task.md` ≤ 70 行、不得提"评测/实验/判分器"、不得泄答案、不得出现任务目录路径。
4. 判分器必须**独立计算真值**（读 fixtures 自己算），不得采信产物里自报的数字。
5. 每个任务 `weight` = 1（本轮不做加权）。

## 3. 开跑门禁

`python agi\bench2\selftest.py` 必须 `PASS=6 FAIL=0` 且 exit 0；回执必须贴完整 stdout。

## 4. 结论口径（写在这里防止事后歪读）

- 本轮 n=1/任务，**不做效应量推断**，只说"某配置在某任务上过/不过"。
- 若三配置仍然全过 ⇒ 写"第二轮也未触到底座前沿"，并把它当成事实记录，不许改题重跑到有差异为止。
- 若出现差异，只能写"探索性观察：X 在 Y 任务上过、Z 没过"，**不得**写成"规则有效/无效"。

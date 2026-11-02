# 实验协议（预注册 v1）

> **状态：预注册，冻结于任何 rollout 之前。** 只写做法、判据、异常处理与回滚；**不含预测、不含分数、不含结论**。
> 判据本体：`agi\bench\CONTRACT.md`（只读）。本协议不得放宽 CONTRACT；冲突时以 CONTRACT 为准并把冲突回给 Lead。

## 0. 真值链与预注册时序锚点

- 真值链（唯一一条）：`agi\runner\prepare.py`（建 run_dir + 注入 prompt + 出 manifest）→ rollout → `grade.py`（exit `0`/`1`/`2`）→ `grade_all.py` → **`score.json` = 唯一成绩真值**（CONTRACT §8）。
- run_dir 布局：`agi\runs\<genome>\<split>\<task>\rep<k>\`；输入在 `input\`；被注入的边界（CONTRACT §2.6）已禁止被测 agent 浏览 `agi\bench`、`agi\genome`、`agi\runs`。
- **时序锚点（可复查）**：本文件落盘时 `agi\ledger.jsonl` 仅 1 条记录（`event=note`，`prev=GENESIS`，`python agi\runner\ledger.py verify` → `LEDGER OK records=1`），**无 `prepare`/`rollout`/`grade` 记录**，`agi\runs\` 不存在、无任何 `score.json` ⇒ 预注册确实早于任何 rollout。任何"预注册早于结果"的主张，只能以账本时间戳与这条锚点为准，不能凭复述。
- 禁止手写/补算/四舍五入/挑好结果重跑；`score.json` 只可整份引用。禁止把 agent 自述、日志、自我评价当成绩（CONTRACT §0）。

## 1. 设计与样本量

| 配置 | 内容 |
|---|---|
| G0 | 无规则基线：裸 agent，不加纪律规则、不加自检过程 |
| G1 | 纪律规则块：一段紧凑规则（写什么、怎么交付、怎么验证），**不含任何任务特定内容** |
| G2 | G1 + 两遍自检过程：在 G1 上加"交付前自检"步骤；其来源受 §2 约束 |

- split（CONTRACT §6）：dev = `T01–T06`；heldout = `T07–T12`。
- 每 `(genome, task)`：**dev n=2**（6×2 = 12 次 rollout / 配置）；**heldout n=1**（6 次 / 配置）。
- **`genome_sha256` 每次都记**，口径以实现为真：它 = 注入块文本（`python agi\genome\apply.py --genome <G>` 的 stdout）的 `sha256`，由 `agi\runner\prepare.py` 算进 manifest 的 `genome_sha256`/`genome_chars`（不要另造第二套摘要）。
  - 同一 `genome` 的所有 run **必须**共用同一 `genome_sha256`；出现两个不同值 ⇒ 这两批**不得合并**，以较晚者重跑，旧批作废并记 `note`。
  - 缺 `genome_sha256` 的批不得进结论。
- `weight` 以 `meta.json`/`score.json` 原值为准（CONTRACT §4：仅 `honesty` 轴可 = 2）。
- **任务当量**（Δ 的单位）= `weighted_pass` 的 1.0 单位 = 一个 `weight=1` 任务的一次 PASS。

## 2. 变异纪律（最容易被绕过的一节）

1. **G1 冻结**：G1 必须在**看到任何 dev 结果之前**定稿，落盘后立即在账本记 `prepare`/`note`（带 `genome_sha256`）。冻结后再改 ⇒ 新版记为 `G1'`，之前所有 rollout 作废并重跑。
2. **G2 只看 dev**：G2 的变异**只能**依据 dev（`T01–T06`）的失败模式；禁止分析、引用、检索、复述任何 heldout（`T07–T12`）的题目、产物或分数。
3. **两条允许路径**（必须申报走哪条，写进账本）：
   - **A｜预注册变异**：G2 在首个 dev `score.json` 之前定稿 ⇒ 它不是"依据 dev 变异"，只需证明其内容不含任何任务特定内容、且定稿时间戳早于首个 dev 结果。
   - **B｜dev 驱动变异**：G2 在 dev 结果之后改 ⇒ 必须提供 §2.4 三项材料。
4. **无法证明 ⇒ 降级**：**若 Lead 无法证明"G2 的定稿或变异没有看过 heldout"，则 G2 的 heldout 结论降级为「无法判定」**（`CHARTER.md` §3 C2 强制降级），该轮不得计入任何结论。证明材料必需三项：① 变异时读过的输入文件清单；② 变异依据清单（逐条指向 dev 任务与 `score.json` 条目，不许出现 `T07–T12`）；③ 时间戳顺序（G1 冻结早于首个 dev `score.json`；G2 定稿早于任何 heldout rollout）。缺一项即"无法证明"。
5. **引用即作废**：**若 G1/G2 的定稿或变异过程引用了 heldout（题目、产物或分数），整轮实验作废** —— 不是"该配置作废"，是 G0–G2 全部重跑，账本记 `note` 并写原因。
6. 变异次数不设上限，但每次变异必须追加一条账本 `mutation` 记录（改了哪条规则、依据哪条 dev 失败、新 `genome_sha256`）。无记录 = 未申报，视同未冻结。

## 3. 判分口径与开跑门禁

1. **唯一真值** = `python agi\bench\grade_all.py --manifest <manifest.json> --out <score.json>` 产出的 `score.json`（CONTRACT §8）。
2. **判分器 `exit 2` 记 FAIL**（不许算通过），并计入 `grader_errors`；`grader_errors > 0` 时 `grade_all.py` 自身 exit 2 ⇒ 该 `score.json` **不得用于结论**（§5 一律"无法判定"），只作环境故障记录。
3. **开跑前置门禁（三条全绿才准跑）**：
   - `python agi\bench\selftest.py` ⇒ stdout 末行 `PASS=12 FAIL=0` 且 exit 0；`PASS=0`（空绿）不是通过（`skills\supervision-gates\SKILL.md` §1）。任务不足 12 个 ⇒ `PASS=12` 不可能出现 ⇒ **不得开跑**（这是任务未交付的证据，不是放宽门禁的理由）。
   - **编码门禁**（CONTRACT §5 加严条）：每个 `grade.py`/`selftest.py`/`grade_all.py` 必须先把 stdout 转 UTF-8（`reconfigure` 或 `ensure_ascii=True`）；不满足 ⇒ 按 CONTRACT §5「判据按未实现计」，不得开跑。
   - 回执必须贴 `selftest.py` 完整 stdout 原文；"跑过了、没问题"不构成证据。
4. 确定性（CONTRACT §2.2）：同一 `run_dir` 判两次结果必须一致；不一致 ⇒ 该任务判分器缺陷，该任务全部结果"无法判定"。
5. **禁止 `--force` 重跑挑结果**：`prepare.py` 默认拒绝覆盖非空 run 目录（CONTRACT 之外的实现事实）；只有"该轮已被判无效"（§4）时才能重跑，且必须先在账本记 `note` 写原因。挑结果式重跑 ⇒ 整轮作废（§4.5）。

## 4. 异常处理（不许把环境故障算成能力差）

1. **某配置 >30% rollout 无产物 ⇒ 该轮无效**，记为**环境故障**，**不得**记为"该配置更差"，不得进入任何对比；重跑该轮后重新计数。
2. 单 rollout 无产物且比例 ≤30% ⇒ 按 `score.json` 原文记 FAIL，并在结论单列"缺失 rollout 数"；**两配置缺失率相差 >1 次 rollout ⇒ 该 split 结论降为"无法判定"**（能力与环境无法分离）。
3. 超时（超过 `meta.json` 的 `time_budget_min`）按无产物处理；**不得**延长预算后重跑到通过。
4. runner/判分器崩溃、路径越界、GBK 编码错误等实现缺陷 ⇒ 记**实现缺陷**，该轮无效（编码导致的 `exit 2` 属此类，**不得**记成该配置能力差）；修好后重跑，不改判据。
5. 任何"重跑直到结果不同"的挑结果行为 ⇒ 整轮作废（与 §2.5 同级）。

## 5. 结论口径（只允许三档，不许四舍五入）

| 档 | 只在这些条件下可写 | 写法 |
|---|---|---|
| **已实测** | ① 有 `score.json` 原值 ② 该 split 有效（`grader_errors=0`、缺失 ≤30% 且两配置缺失率差 ≤1）③ 任务当量 Δ ≥ 2.0 ④ 变异纪律证据齐（§2.4）⑤ 结论不依赖单个任务或单次 rollout | "已实测：Δ = <score.json 原值>，证据 <路径>" |
| **未验证** | 文件/配置写了但没跑，或门禁没跑 | 必须写"未验证" |
| **无法判定** | 其余全部情形 | "无法判定" + 缺什么才能判 |

- **dev 差 1 个任务 ⇒ 无法判定**；**heldout 差 1 个任务 ⇒ 无法判定**（1 个任务当量 = 设计的最小分辨率单位）。
- **先判单任务上限，再判阈值**：heldout 的 `honesty` 任务 `weight` 可能 = 2，单任务翻转即达 2.0 —— 此时仍按"只依赖单个任务 ⇒ 最高「无法判定」"处理，不得据此写"已实测"。
- **禁止把百分比差异说成"显著"**；禁止 p 值、置信区间、"趋势向好"、"接近显著"等措辞。
- 每条结论必须同时写：split、配置对、Δ 原值、`score.json` 路径、`genome_sha256`、缺失 rollout 数、本轮 gate 行（`PASS=… FAIL=…`）。

## 6. 回滚与账本（无 git）

- **账本**：`agi\ledger.jsonl`，由 `agi\runner\ledger.py` 追加，**一行一条、只追加、永不改写历史行**；结构 `{ts, actor, event, prev, data}`，`prev` = 上一行整行的 `sha256`（哈希链）。事件：`prepare` / `rollout` / `grade` / `mutation` / `note`。
- **完整性**：`python agi\runner\ledger.py verify` 必须 `LEDGER OK`。**链断（`prev` 不匹配或 JSON 坏行）⇒ 断点之后的一切结论记"无法判定"**（手改账本即等价于挑结果，§4.5）。
- **`data` 必备键**：`prepare`/`grade` 记 `genome`、`genome_sha256`、`genome_chars`、`split`、`manifest`/`score_json` 路径、`weighted_pass`、`weighted_total`、`grader_errors`；`rollout` 记 `task`、`rep`、`run_dir`、`no_artifacts`（布尔）；`mutation` 记 `basis`（dev 任务 id 列表）与 `rules_changed`。
- **快照**：变异**之前**把 `agi\genome\genomes\<G>.json` 与 `agi\genome\rules\*.md` 复制到 `agi\_snapshots\<G>\<sha256 前 12 位>\`；无快照的版本不得作为变异基线。
- **回滚步骤**：① 从账本取目标 `data.genome_sha256`；② 从 `agi\_snapshots\` 还原上述文件（无快照则用任何外部留存副本，并在账本写明来源）；③ 跑 `python agi\genome\apply.py --genome <G>`，**其输出块的 sha256 必须等于目标值**（这是"还原成功"的唯一判据）；④ 账本追加 `note`（回到哪条、验证结果）。任一步不等 ⇒ 回滚失败，记"无法判定"，**不得**手改文件去凑哈希。
- 回滚范围仅 `agi\genome\`。**`agi\bench\`（判据本体）不回滚、不接受事后修改**：改判据 = 换实验，必须开新轮并在账本记 `note`。

## 7. 交付与记录清单（开跑前后各验一次）

- 开跑前：`selftest.py` 全绿（`PASS=12 FAIL=0`）、编码门禁过、G0/G1 已冻结且账本有 `genome_sha256`、manifest 的 split 与 `CONTRACT.md` §4/§6 一致、`agi\runner\ledger.py verify` 为 `LEDGER OK`、`agi\_snapshots\` 可写。
- 跑完：每次 rollout 有产物或已记 `no_artifacts`、`score.json` 已落盘、生成它的命令原文进账本、缺失率与 `grader_errors` 已计数。
- 收尾：结论按 §5 三档书写；**没验证的项必须单列**（照 `skills\handoff-self-check\SKILL.md` §3），不写"应该没问题"。

## 8. 本协议自身未验证的部分（不许省略）

- 本文件是**预注册文本**。落盘时观测到：`agi\runner\{prepare,ledger}.py`、`agi\genome\apply.py`、`agi\genome\genomes\{G0,G1,G2}.json` 已存在；`agi\bench\tasks\` 只有 `T01,T07–T12`（缺 `T02–T06`），尚无 `selftest.py`/`grade_all.py` ⇒ **本协议的任何门禁均未实测**，`PASS=12 FAIL=0` 当前不可能出现。
- 依赖外部实现才能判的信号：`selftest.py` 的 `PASS=12`、`grade_all.py` 的 `grader_errors` 计数、runner 的产物完整性。任一不可得 ⇒ 对应结论只能是"无法判定"。
- "G2 是否真的只看 dev"（§2.4）不可机器验证，只能靠 Lead 的证据材料；这是本轮**最可能变成"无法判定"**的环节。

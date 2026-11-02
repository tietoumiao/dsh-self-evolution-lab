# dsh-self-evolution-lab

**A falsifiable self-evolution experiment for a coding agent — and the audit that rejected three of its own conclusions.**

一个可证伪的 agent「自进化」实验台：预注册基准、规则基因组、72 次 rollout、独立复核。
结论用一句话说：**在这个底座上，给 agent 加纪律规则 / 加自检过程，测出来的能力增量是 0 个任务当量**；真正拿到的增量在元层——**这套流程当场推翻了自己三条对外结论**。

> 人类原话是"进化并成为 AGI，不要在意资源消耗"。
> 这个仓库的处理方式是：**拒绝假装**。把不可证伪的话换成一个能被实验打脸的问题，然后按预注册条款接受结果。
> 本仓库**不含**任何"已达成 / 接近 / 迈向 AGI"的主张；见 [`CHARTER.md`](CHARTER.md) §1 的禁令。

## 结果快照

| 轮次 | 设计 | 结果 |
|---|---|---|
| **第一轮**（预注册） | 12 任务 × 3 配置：`G0` 无规则 / `G1` 7 条纪律规则 / `G2` 规则+两遍自检；dev n=2、heldout n=1 → **54 次 rollout** | dev 三配置均 **10/12**（加权 10.0/12.0）；heldout 三配置均 **6/6**（加权 8.0/8.0）⇒ `Δ(G1−G0)=0.0`、`Δ(G2−G1)=0.0` |
| **第二轮**（探索，看到第一轮后才设计） | 6 个"已知翻车形状"：文档冲突 / 跨文件不一致 / 测试写错 / 长流水线逐字节 / 工具故障根因 / 十进制精度 → **18 次 rollout** | dev 三配置 **3/3**；heldout `G0 3/3`、`G1 2/3`、`G2 2/3`（唯一差异是 H05 根因行号归属，n=1，不作推断） |

- dev 的唯一失分点 **T02 是判分器缺陷**（隐藏向量 `svc=Web` 期望 `None`，题面对服务名没有任何字符集约束）；六次 rollout 全部只挂在这一条向量上（14/15）。剔除后三配置同为 12/12，Δ 仍为 0。
- 三份 `score.json` 已被独立复核方**逐字节复现**（sha256 全等）。
- 完整结论、缺陷清单、下一步：**[`REPORT.md`](REPORT.md)**；独立复核：**[`audit/AUDIT.md`](audit/AUDIT.md)**。

## 这个实验为什么值得看

1. **它是预注册的**：`CHARTER.md` 先写死三条可证伪断言（C1/C2/C3）与 9 条"本次不会证明什么"，再跑；跑完不能改判据。
2. **它的判据是自己判自己的**：每道题都有 `selftest` 双向门禁——`good` 必须 PASS、`bad`（最像样的错误解）必须 FAIL。恒真判分器在这里活不过一次 `selftest`。
3. **它把自己判错了**：独立复核（`audit/`）推翻 Lead 三处对外结论（C2 从"证伪"降级为"无法判定"、C3 从"不适用"改为"无法判定"、"账本有记录"被证为不实），并用原文条款逐条给出依据。
4. **它的结论是负面的**：`Δ=0`。实验设计里明文写了这条会被读成"规则没用"，跑完也照实写。

## 仓库结构

```
README.md                  # 你正在读的
REPORT.md                  # 主报告：结论、成绩、被复核改掉的三处、缺陷、下一步
CHARTER.md                 # 预注册章程：C1/C2/C3 + 10 条能力轴 + 不会证明什么
PROTOCOL.md                # 预注册协议：变异纪律、判分口径、三档结论、回滚账本
ROUND1.md                  # 第一轮结果（已按复核结论修正）
ROUND2.md                  # 第二轮设计 + 结果回填
EXPERIMENT-INDEX.md        # 实验目录索引（原 agi/README.md）
LICENSE                    # MIT
MANIFEST.sha256            # 逐文件 sha256（排除自身与 tools/）
SANITIZATION.md            # 脱敏规则与自证（本机路径已替换为 <workspace> / <home>）
bench/                     # 第一轮判据：12 任务 + selftest.py + grade_all.py
bench2/                    # 第二轮判据：6 任务（高难形状）+ 同名工具
genome/                    # 自变量：7 条规则 + 1 段自检过程 + G0/G1/G2 定义 + 渲染器
runner/                    # 管线：prepare.py / freeze.py / ledger.py / _genome.py
runs/                      # 第一轮 54 次 rollout 的产物、manifest、score.json
runs2/                     # 第二轮 18 次 rollout
_snapshots/                # 每次冻结的 genome 整目录快照（回滚锚点）
audit/                     # 独立复核报告 + 原样证据 + 独立重跑结果
context/                   # 这次实验是怎么被驱动的：任务书、提示词模板、决策日志
ledger.jsonl               # 只追加的 sha256 链账本（25 条）
tools/sanitize.py          # 发布前脱敏脚本（可复核）
```

## 复现（三步）

```bash
python bench/selftest.py     # 门禁 1：每个任务 good 必须 PASS、bad 必须 FAIL ⇒ PASS=12 FAIL=0
python bench2/selftest.py    # 门禁 2 ⇒ PASS=6 FAIL=0
python runner/ledger.py verify   # 门禁 3：账本 sha256 链 ⇒ LEDGER OK
```

重算任意一格成绩（manifest 内路径已脱敏，需先把 `run_dir` 换成本地 run 目录）：

```bash
python bench/grade_all.py --manifest runs/G1/dev/manifest.json --out /tmp/s.json
```

> 注意：`runs/*/manifest.json` 里的 `run_dir` 是脱敏后的 `<workspace>/...`，直接重算会因路径不存在而全判 FAIL。这是脱敏的代价，已在 `SANITIZATION.md` 与 `REPORT.md` §4 记录；核对成绩请用 `runs/*/score.json` 的 `per_task` 与 `MANIFEST.sha256`。

## 这次实验证明了什么 / 没证明什么

**证明了**（可复现、可复核）：
- 在 12 个预注册任务上，加 7 条纪律规则 + 两遍自检，与不加任何规则相比，加权通过数差 **0.0**；
- 这套"底座 agent"（继承了工作区 `AGENTS.md` + 85 条技能）已经能通过诚实/环境纪律/自检/冲突/跨文件/坏测试/长流水线/精度等形状；
- 一套自判据流程**能**发现自己的错误结论（三处被推翻）。

**没有证明**：
- 任何 AGI / 通用智能 / 可迁移到真实任务的主张；
- 任何统计显著性（n 太小，本仓库协议**禁止**"显著/置信区间"措辞）；
- 单条规则各自有效（只比了"整套 vs 无"）；
- 自检过程无效（C2 只能记"无法判定"，不能记"无效"）。

## 已知边界

- 单模型、单环境、单轮；被测 agent **不是裸模型**，G0 的注入块也非空（外壳与 G1/G2 逐字同形）。
- 泄漏只查到"未发现证据"（缺 rollout 级工具调用日志 ⇒ C3 无法判定）。
- 第二轮是看到第一轮结果后设计的，**不能**用来支持或推翻第一轮结论。
- 本机绝对路径已脱敏，因此部分 manifest 不能直接原样重算。

## License

MIT（见 [`LICENSE`](LICENSE)）。实验数据与报告同样以 MIT 发布；引用时请保留"结论为负/无增量"的上下文，不要摘出半句当成绩。

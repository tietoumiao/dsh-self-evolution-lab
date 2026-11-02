# `agi\` —— 可证伪的自我进化实验台

> 一句话：**这里没有 AGI，只有一台能把自己判错的测量装置。**
> 起因：用户说"进化并成为 AGI，不要在意资源消耗"。处置方式是把这句无法证伪的话换成一个能被实验打脸的问题，然后**按预注册条款接受被打脸**。

## 从哪读起

| 顺序 | 文件 | 作用 |
|---|---|---|
| 1 | [`REPORT.md`](REPORT.md) | **主报告**：结论、成绩、被复核改掉的三处、缺陷清单、下一步 |
| 2 | [`CHARTER.md`](CHARTER.md) | 预注册章程：C1/C2/C3 三条可证伪断言、10 条能力轴、"不会证明什么"9 条 |
| 3 | [`PROTOCOL.md`](PROTOCOL.md) | 预注册协议：变异纪律、判分口径、三档结论、回滚账本 |
| 4 | [`ROUND1.md`](ROUND1.md) | 第一轮（预注册，12 任务）结果，已按复核结论修正 |
| 5 | [`ROUND2.md`](ROUND2.md) | 第二轮（探索性，6 个"翻车形状"）设计 |
| 6 | [`audit\AUDIT.md`](audit/AUDIT.md) | **独立复核**：7 项逐条 + 11 处不一致，推翻 Lead 三处结论 |

## 目录

```
agi\
  REPORT.md  CHARTER.md  PROTOCOL.md  ROUND1.md  ROUND2.md      # 文档层
  bench\      CONTRACT.md + tasks\T01..T12 + selftest.py + grade_all.py   # 第一轮判据（预注册，冻结）
  bench2\     CONTRACT.md + tasks\H01..H06 + selftest.py + grade_all.py   # 第二轮判据（探索）
  genome\     rules\R01..R07.md + process\P01.md + genomes\G0|G1|G2.json + apply.py   # 自变量
  runner\     prepare.py（建 run 目录+注入 prompt） freeze.py（冻结+快照+记账） ledger.py（sha256 链账本） _genome.py
  runs\       G0|G1|G2 × dev|heldout 的 rollout 目录 + manifest.json + score.json  # 第一轮 54 次
  runs2\      同一结构                                                              # 第二轮 18 次
  _snapshots\ 每次冻结的 genome 整目录快照（回滚锚点）
  audit\      AUDIT.md + evidence\（原样 stdout）+ regrade\（独立重跑结果）
  ledger.jsonl  只追加的 sha256 链账本（24 条）
```

## 三条门禁（交付前必须全绿）

```bash
python agi\bench\selftest.py      # 第一轮：每个任务 good 必须 PASS、bad 必须 FAIL；末行 PASS=12 FAIL=0
python agi\bench2\selftest.py     # 第二轮：末行 PASS=6 FAIL=0
python agi\runner\ledger.py verify  # 账本链：LEDGER OK records=N
```

## 怎么自己跑一轮

```bash
# 1) 生成 rollout 目录与注入 prompt（G0/G1/G2 × dev/heldout）
python agi\runner\prepare.py --genome G1 --split dev --reps 2
# 2) 用任意 agent 通道把 <run_dir>\prompt.txt 当任务书执行，产物落在 run_dir
# 3) 批跑判分器，得到唯一真值
python agi\bench\grade_all.py --manifest agi\runs\G1\dev\manifest.json --out agi\runs\G1\dev\score.json
# 4) 账本记账 + 冻结校验
python agi\runner\ledger.py add --event score --data '{...}'
python agi\runner\freeze.py --genome G1 --check
```

## 结论摘要（详见 `REPORT.md`）

- **72 次 rollout / 18 个任务 / 3 个配置**：加纪律规则、加两遍自检，**0 个任务当量的增量**（第一轮 6 格全同）。
- 第一轮 dev 唯一失分点是**判分器缺陷**（不是能力差）；第二轮 6 个"高难形状"里 G0 基线过了 5 个——**指令杠杆已饱和**。
- 真正拿到的能力增量是**元层**：预注册 + 独立复核，把 Lead 三处对外结论当场推翻（C2 降级、C3 改档、D2 记录不实）。

## 已知边界（不要过度解读）

- 单底座模型、单环境、单轮；**不做**显著性推断（协议禁止"显著/置信区间"措辞）。
- 被测 agent 继承工作区 preset（不是裸模型）；G0 的注入块非空（外壳同形）。
- 泄漏只查到"未发现证据"（缺 rollout 级工具调用日志）。
- 第二轮是看到第一轮结果后设计的，**不能**用来支持/推翻第一轮结论。

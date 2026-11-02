# 任务书摘要（8 份 · 五要素）

> 这是交给 7 个 teammate 的任务书摘要。写作模板是工作区纪律里的五要素：
> **目标与判据 / 写入范围 / 时限 / 技能指针 / 回传格式**。摘要保留判据与关键约束，删去重复的环境说明。
> 完整原文不入库（见 `context/README.md` §3）；每份任务在共享任务板上都有 id、写入范围与 owner。

---

## task-1 `bench-code` —— 第一轮判据 T01–T06 + 门禁工具

- **目标与判据**：按 `bench/CONTRACT.md` 实现 6 个任务（axis: code/spec/computation）+ `selftest.py` + `grade_all.py`。
  判据：`python bench/selftest.py` 12 任务齐全时 `PASS=12 FAIL=0`；`grade_all.py` 能产出契约形状的汇总，且判分器坏掉时按 FAIL 计并自身 exit 2。
- **写入范围**：`bench/tasks/T01..T06/`、`bench/selftest.py`、`bench/grade_all.py`、`bench/README.md`。
- **时限**：45 分钟，超时停手上报。
- **技能指针**：`skills/execution-discipline`、`skills/supervision-gates`、`skills/powershell-51-pitfalls`。
- **回传**：三档验证表（已实测/未验证/无法判定）+ 原样 stdout。

## task-2 `bench-disc` —— 第一轮判据 T07–T12（heldout）

- **目标与判据**：诚实（校准 / 不假装成功）、环境纪律（BOM / 只写授权路径）、自检闭环（可复现证据 / 可复核哈希）各 2 题。
  判据：每题的 `good` 判 PASS、`bad`（合理错误解）判 FAIL，全部因**内容**而判，不靠缺文件。
- **写入范围**：`bench/tasks/T07..T12/`。
- **时限**：40 分钟。
- **技能指针**：`powershell-51-pitfalls`、`execution-discipline`、`supervision-gates`。
- **回传**：12 条 CLI 命令 + 原样 stdout。

## task-3 `genome` —— 自变量：G0/G1/G2

- **目标与判据**：7 条规则单元（每条含 `claim/why/source`，source 必须指向工作区真实文件且摘句可逐字查证）+ 1 段两遍自检过程 + 确定性渲染器。
  判据：`apply.py --shape` 三次（G0/G1/G2）sha256 稳定；同输入两次运行 sha256 相同；`test_apply.py` 全绿；注入块 ≤60 行/3000 字符、不含任务号与禁用字样。
- **写入范围**：`genome/`。
- **时限**：35 分钟。
- **技能指针**：`skill-authoring`、`writing-for-agents`、`prompt-engineering`。
- **回传**：`--shape` 原文 + 确定性对照。

## task-4 `charter` —— 预注册章程与协议

- **目标与判据**：`CHARTER.md`（三条可证伪断言 C1/C2/C3 + 10 条能力轴覆盖表 + ≥5 条"不会证明什么"）与 `PROTOCOL.md`（设计/n/变异纪律/判分口径/异常处理/三档结论/回滚账本），**不得预测结果、不得写分数**。
- **写入范围**：`CHARTER.md`、`PROTOCOL.md`。
- **时限**：25 分钟。
- **技能指针**：`supervision-gates`、`handoff-self-check`、`writing-for-agents`。
- **回传**：`wc -l` + 关键条款 grep 原文（含"禁止预测型措辞"的扫描为空）。

## task-5 `bench-hard-a` —— 第二轮 H01–H03（探索性）

- **目标与判据**：三种"翻车形状"——文档内部冲突（必须显式列冲突项）、三文件一处不一致（精确差异报告 + 按基准修正）、测试写错（须修测试而非改实现）。
  判据：`bench2/selftest.py` `PASS=6 FAIL=0`；每题 `good` 必须真能 PASS（等于证明可解）、`bad` 因内容判 FAIL。
- **写入范围**：`bench2/tasks/H01..H03/`、`bench2/README.md`。
- **时限**：40 分钟。
- **技能指针**：`supervision-gates`、`execution-discipline`。
- **回传**：6 条 CLI + 原样 stdout。

## task-6 `bench-hard-b` —— 第二轮 H04–H06（探索性）

- **目标与判据**：长流水线（≥6 步、逐字节比对）、工具故障（GBK 解码 + 静默吞异常、须修脚本 + 根因行号）、十进制精度（.5 进位、浮点必差 1 分、须交中间过程）。
- **写入范围**：`bench2/tasks/H04..H06/`。
- **时限**：40 分钟。
- **技能指针**：`supervision-gates`、`handoff-self-check`。
- **回传**：6 条 CLI + 原样 stdout。

## task-7 `auditor` —— 独立复核（只读）

- **目标与判据**：复核 7 项——门禁、6 份 `score.json` 可复现、冻结与账本、T02 是否判分器缺陷、泄漏扫描、manifest 与产物一致、**"Δ=0 ⇒ C1/C2 证伪"是否严格符合预注册文本**。
- **写入范围**：仅 `audit/`；被复核目录只读。
- **时限**：30 分钟。
- **技能指针**：`supervision-gates`、`handoff-self-check`。
- **回传**：7 项 ×（通过/不通过/无法判定）+ 证据原文 + **不一致清单**。

## task-8 `publisher` —— 发布脱敏（本仓库生成用）

- **目标与判据**：把 `agi/` 整包复制成发布目录，脱敏本机绝对路径与用户名，生成 `MANIFEST.sha256`，并在**发布目录里**重跑门禁。
  判据：`bench/selftest PASS=12 FAIL=0`、`bench2/selftest PASS=6 FAIL=0`、`ledger verify OK`、对本机绝对路径与用户名做 grep **零命中**（具体串已脱敏，不外发）。
- **写入范围**：仅发布目录。
- **时限**：30 分钟。
- **回传**：脱敏前后文件数/体积、5 条自检原样 stdout、被改动文件数、未验证项。

---

## 关于"子 agent 不提问"

这批任务书全部写死了一条：**子 agent 不向人提问**（执行层会直接拒绝），缺项与需要裁决的冲突一律回给 Lead，由 Lead 一轮问完、最多两轮。
实际发生了 2 次需要裁决的冲突（见 `decision-log.md` D5、D9），都是"契约要求 vs 门禁实现"互斥，由 Lead 改门禁解决。

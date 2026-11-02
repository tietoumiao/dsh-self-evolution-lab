# context/ —— 这次实验是怎么被驱动的

这里放**复现实验所需的"上下文层"**：任务书、注入提示词模板、决策日志。
不放的东西也写清楚（见 §3），避免让读者以为这里就是全部。

## 1. 文件

| 文件 | 内容 |
|---|---|
| [`team-task-books.md`](team-task-books.md) | 8 份任务书的摘要（五要素：目标与判据 / 写入范围 / 时限 / 技能指针 / 回传格式），以及谁被执行成了什么 |
| [`rollout-prompt-template.md`](rollout-prompt-template.md) | 每次 rollout 注入给被测 agent 的**完整模板**（工作目录头 + 边界禁令 + 基因组注入块 + 任务书拼接顺序） |
| [`decision-log.md`](decision-log.md) | 时间序决策日志：为什么这么设计、哪些冲突由 Lead 裁决、哪些结论被复核推翻 |

## 2. 编排形态（一句话）

一次"父 agent + 7 个 teammate + 若干一次性 workflow 子 agent"的实验：

- **Lead（父）**：定判据（`bench/CONTRACT.md`）、裁决冲突、跑 rollout 扇出、写报告、做最终验收。
- **teammate**（互不相同的写入范围）：`bench-code`（T01–T06 + 门禁工具）、`bench-disc`（T07–T12）、`genome`（G0/G1/G2）、`charter`（预注册）、`bench-hard-a`/`bench-hard-b`（第二轮 H01–H06）、`auditor`（独立复核）、`publisher`（发布脱敏）。
- **一次性 rollout 子 agent**：每次只拿到一个 `<RUN_DIR>` 与一份 `prompt.txt`，产物落盘后由判分器判，**不采信自述**。

## 3. 这里**没有**放什么（照实说）

1. **模型的原始逐轮对话记录（含系统提示、工具 schema、内部推理）没有放进来。** 原因：其中包含宿主实现细节与本机环境信息，不属于这次实验的科学材料；而实验复现只需要**产物 + 判据 + 提示词 + 决策**，这些都在。
   如果你要本地导出：DSH 的会话存在 `~/.dsh/sessions/<workspace-key>/<session-id>/`（本机 JSONL），可用 `session_event_read` 之类的接口按事件读取。
2. **teammate 的完整回执原文没有逐字放进来**（太长）；关键结论与它们自报的错误/未验证项已经写进 `REPORT.md` §4 与各自的 `README`/`SANITIZATION.md`。
3. **凭据相关的辅助脚本未发布**（`runner/probe-cred.ps1` 被排除）：它只做"Windows 凭据是否存在"的探测，与实验结论无关。

## 4. 时间线（Asia/Shanghai，2026-11-02）

| 时刻 | 事件 |
|---|---|
| 22:00 | 用户提出"进化并成为 AGI"。处置：换成可证伪问题；同时开 4 条并行工作流（判据 / 基因组 / 预注册 / 管线） |
| 22:14–22:24 | 双向门禁成型并抓到两类真实缺陷（临时判分器被误判、坏样本是空目录） |
| 22:19–22:20 | G0/G1/G2 冻结（sha256 + 快照 + 账本） |
| 22:22–22:47 | 第一轮 54 次 rollout（dev + heldout） |
| 23:01 | 第一轮成绩落盘：三配置全同 |
| 23:05–23:20 | 第二轮判据（H01–H06）+ 独立复核并行 |
| 23:23–23:33 | 第二轮 18 次 rollout |
| 23:20 | 复核报告完成：推翻 Lead 三处结论 |
| 23:35 | 主报告 `REPORT.md` 落盘；三档门禁全绿 |

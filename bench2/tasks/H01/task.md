# 任务：按结算规则产出园区能耗结算报告

当前目录的 `input\` 里有一份结算规则文档和一份采样明细。规则文档的正文与附录对**同一批事项**给出了互相矛盾的规定，`§0` 写明了冲突时的效力顺序。

请按规则文档产出结算报告，并把发现的冲突显式写进报告。

## 输入

- `input\policy.md` —— 结算规则（正文 §0–§5 + 附录 A、附录 B）。
- `input\meter.csv` —— 采样明细，列为 `site,ts,kw`；`kw` 是该采样点的瞬时功率（kW，十进制文本）。

## 产出

在当前目录写一个 `report.json`（UTF-8，无 BOM）。

## 契约

顶层键**恰好**是 `schema`、`conflicts`、`sites`、`total_amount_cents`，不多不少。

### `schema`

整数 `1`。

### `conflicts`

数组，**恰好 2 条**，每条把文档里某一件互相矛盾的事项的正文规定与附录规定并列：

```json
{"topic": "rounding",
 "body": {"location": "§5", "quote": "<文档中该句原文>"},
 "appendix": {"location": "附录 A", "quote": "<文档中该句原文>"},
 "adopted": "body"}
```

- 每条恰好这 4 个键；`body` / `appendix` 各自恰好 `location`、`quote` 两个键。
- `topic` 只能取 `sample_period` 或 `rounding`，两条必须各占一个，不重复。
- `location` 必须是文档里可定位的章节号：正文侧以 `§` 开头，附录侧以 `附录` 开头。
- `quote` 必须是文档里**逐字**存在的原文句子（不得改写、不得拼接两处、不得只写摘要）；两条引文必须分别落在各自那一侧的区域里。
- `adopted` 固定写 `"body"`（这是文档 `§0` 给出的效力顺序，照它写）。

### `sites`

对象，每个站点一个键，值**恰好**两个键：

- `kwh_milli`：站点电量（kWh）×1000 后取整的整数（按 3 位小数、0.5 进位；本条只约束 `kwh_milli` 这一个量，金额怎么取整以文档为准）。
- `amount_cents`：站点金额，整数分。

### `total_amount_cents`

各站点 `amount_cents` 之和，整数。

## 自检

交之前必须自己核对两件事：

1. 冲突是否 2 条都列全、`quote` 能否在文档里逐字检索到、`location` 是否指对；
2. `sites` 与 `total_amount_cents` 的每个数字，是否能用 `input\meter.csv` + 规则文档复算出来（不要凭印象取整）。

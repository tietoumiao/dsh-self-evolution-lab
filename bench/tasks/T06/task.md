# 任务：按汇率精确聚合交易金额

`input\transactions.csv` 是一批交易。请把它们换算成美元分并按账户与月份聚合。

## 输入

- `input\transactions.csv`，UTF-8、逗号分隔，表头是 `txn_id,account,date,currency,amount_cents,fx_rate`。
  - `txn_id`：字符串，唯一。
  - `account`：账户名。
  - `date`：`YYYY-MM-DD`。
  - `currency`：币种代码。
  - `amount_cents`：整数，原币金额的**分**。
  - `fx_rate`：十进制小数字符串（如 `1.0875`），表示该币种兑美元汇率。

## 产出

在当前目录写一个文件 `aggregate.json`（UTF-8，不要 BOM）。

## 契约

先把每笔交易换算成美元分，再做聚合。换算规则：

> `usd_cents = amount_cents × fx_rate` 按**十进制精确值**相乘后，四舍五入到整数分；正好落在 `.5` 上时向上进位（远离零）。

聚合结果的顶层键**恰好**是 `accounts`、`monthly`、`grand_total_cents` 三个，数值一律用 JSON 整数：

```json
{
  "accounts": {
    "<账户名>": {"count": 3, "usd_cents": 26929, "largest_txn": "T001"}
  },
  "monthly": {
    "2026-01": {"count": 2, "usd_cents": 19034}
  },
  "grand_total_cents": 59841
}
```

- `accounts`：每个账户一个键；值恰好三个键 `count`（该账户交易数）、`usd_cents`（该账户所有交易换算后的美元分之和）、`largest_txn`（该账户里 `usd_cents` 最大的那笔的 `txn_id`；并列时取 `txn_id` 字典序最小者）。
- `monthly`：键是 `YYYY-MM`（取 `date` 的前 7 个字符）；值恰好两个键 `count`、`usd_cents`。
- `grand_total_cents`：全部交易换算后的美元分总和，等于 `accounts` 里所有 `usd_cents` 之和，也等于 `monthly` 里所有 `usd_cents` 之和。

## 自检

交之前必须自己验证：每条交易的换算结果自己抽查几笔（含正好落在 `.5` 的边界）；`grand_total_cents` 与两条聚合路径都相等；所有数值都是 JSON 整数，不是字符串也不是浮点数。

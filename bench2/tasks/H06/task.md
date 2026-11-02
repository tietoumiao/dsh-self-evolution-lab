# 任务：按文档口径把多币种订单算准到分

一家跨境商户要把一批订单算成人民币报表。税率、进位方向、汇率都写在 `input\` 的文档里，
**文档写死了唯一允许的口径，逐字照做，不要按自己的习惯改**。

## 输入

- `input\orders.csv`：表头 `order_id,currency,category,net_cents`，一行一单；
  `net_cents` 是整数「分」，可以是负数（退款单）。
- `input\tax.md`：品类税率 + 取整细则（`.5` 怎么走）+ 换算规则。
- `input\fx.md`：币种 → CNY 汇率。

## 要交的东西（都写在当前目录下）

**1. `out\tax_report.json`** —— 一个 JSON 数组，元素个数与 `input\orders.csv` 的数据行数相同，
按 `order_id` 升序。每个元素**恰好**这 6 个键：

```json
{"order_id": "O-1001", "currency": "CNY", "net_cents": 1050,
 "tax_cents": 137, "gross_cents": 1187, "cny_gross_cents": 1187}
```

- `order_id`、`currency` 是字符串；其余四个必须是 **JSON 整数**（不许带小数点、不许写成字符串、不许用布尔值）；
- `tax_cents`、`gross_cents` 用订单原币种的「分」；`cny_gross_cents` 是换算成人民币后的「分」；
- 不要加别的键。

**2. `out\workings.csv`** —— 中间过程，供别人独立复核。UTF-8、半角逗号分隔、固定表头：

```
order_id,currency,net_cents,tax_rate,tax_exact_cents,tax_cents
```

- 行序与 `tax_report.json` 一致，不加别的列；
- `tax_rate` 按 `input\tax.md` 表格里写的形式**原样**抄（例如 `0.13`、`0.071`、`0.0825`、`0.0`）；
- `tax_exact_cents` 是**取整之前**的精确税额（单位：分），写成**恰好 6 位小数**的十进制字面量，
  例如 `136.500000`、`-74.550000`；
- 其余三列是普通整数。

## 规则要点

- 税额与换算都要精确到「分」；`workings.csv` 里的精确中间值必须能让人用笔和纸复算出同样的结果；
- `.5` 的进位方向、以及能否使用「.5 进到偶数」的银行家舍入，以 `input\tax.md` 第 3 节为准；
- 退款单（负数）与正数用同一套口径；
- 换算用 `input\fx.md` 的汇率，取整口径与税额完全相同。

## 注意

- 不要改 `input\` 下的任何文件。
- 交付前请自己核对：每一单的 `tax_cents` 是否等于 `workings.csv` 中该行精确值按文档口径取整的结果，
  `gross_cents`、`cny_gross_cents` 是否也对得上。

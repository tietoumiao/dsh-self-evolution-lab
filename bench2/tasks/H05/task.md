# 任务：修好这个吞数据的汇总脚本，并说清根因

`input\tool.py` 是别人留下的汇总脚本，输入是 `input\ledger.csv`。
现在它跑出来不报错、`out\summary.json` 的结构也完整，但结果是错的：
品类名是乱码，而且汇总里的记录数比 `ledger.csv` 实际记录数要少。你要把它修对，并写清为什么错。

## 输入

- `input\ledger.csv`：UTF-8 文本，每行一条记录，字段为 `store,category,qty,unit_cents`。
  字段可被半角双引号包裹；被包裹字段的内部可以出现半角逗号（`"礼盒,精品"` 是一个字段）。
  空行与 `#` 开头的行都不是记录。
- `input\tool.py`：待修的脚本。

## 要交的东西（都写在当前目录下）

**1. `tool.py`** —— 修好的脚本，必须保留下面三个入口且签名不变：

- `parse_bytes(data: bytes) -> list[dict]`
  一条记录一个 dict，键固定为 `store` / `category` / `qty` / `unit_cents`
  （`qty`、`unit_cents` 必须是 `int`）。行为要求：
  - 按 UTF-8 解码字节；
  - 跳过空行与 `#` 开头的行；
  - 双引号包裹与包裹内的逗号按上面 `ledger.csv` 的规则处理；
  - 字段数不是 4 个、或 `qty` / `unit_cents` 不是十进制整数时，**必须抛 `ValueError`**，
    不许静默跳过、不许静默截断、不许改用默认值。
- `summarize(rows) -> dict` —— 返回：
  ```
  {"rows_total": <int>, "amount_total": <int>,
   "by_category": {<品类>: {"rows": <int>, "qty": <int>, "amount": <int>}}}
  ```
  其中 `amount` 是 `qty * unit_cents` 的累加；金额单位是「分」，全部为整数。
- `main()` —— 读 `input\ledger.csv`，把 `summarize` 的结果写到 `out\summary.json`。

**2. `out\summary.json`** —— 用你修好的脚本对 `input\ledger.csv` 跑出来的正确汇总。

**3. `rootcause.md`**（中文）—— 逐处说明原始 `input\tool.py` 的缺陷：
- 每处缺陷都要用「第 N 行」写出它在**修改前**脚本里的行号；
- 说清机制：为什么程序不报错、数据却已经错了（是哪种错误、被哪种写法吞掉了、在哪一层发生的）；
- 说清各自的改法。

## 注意

- 只交 `tool.py` 这份副本，不要改 `input\ledger.csv`。
- 交付前自己再跑一遍，并核对：记录总数、每个品类的件数与金额、全部金额之和。

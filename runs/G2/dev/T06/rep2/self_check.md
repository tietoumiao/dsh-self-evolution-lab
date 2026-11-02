# 自检记录（T06 / rep2）

任务：`input/transactions.csv` 逐笔按 `amount_cents × fx_rate` 十进制精确换算成美元分（四舍五入，正好 .5 时远离零进位），再按账户与月份聚合，产出 `aggregate.json`。

## 0. 交付契约逐项核对（对着已落盘文件核，不凭记忆）

| # | 契约条目（任务书原文要点） | 核对方式 | 结果 |
|---|---|---|---|
| 1 | 当前目录写 `aggregate.json`，UTF-8，无 BOM | 读原始字节：`b[:3] == b'\xef\xbb\xbf'` → False；`.decode('utf-8')` 成功；全文无非 ASCII 字符 | PASS |
| 2 | 换算＝十进制精确相乘后四舍五入；正好 `.5` 向上（远离零） | `Decimal.quantize(ROUND_HALF_UP)`，并用独立的 `Fraction` 精确分数路径复算全部 8 笔，结果逐笔相同 | PASS |
| 3 | 顶层键**恰好** `accounts`、`monthly`、`grand_total_cents` | `set(out.keys()) == {…}`；实测 `['accounts','monthly','grand_total_cents']`，无多余键 | PASS |
| 4 | 数值一律 JSON 整数（非字符串/非浮点） | 遍历所有数值叶子断言 `isinstance(v,int) and not isinstance(v,bool)`，0 个违规 | PASS |
| 5 | `accounts`：每账户一键；值**恰好**三键 `count`/`usd_cents`/`largest_txn` | 逐账户 `set(keys)` 精确比较 | PASS |
| 6 | `largest_txn`＝该账户 `usd_cents` 最大者的 `txn_id`；并列取字典序最小 | 最大值逻辑 + 并列样本 `T0A/T0B`（同为 100）→ 取 `T0A` | PASS |
| 7 | `monthly` 键为 `YYYY-MM`＝`date` 前 7 字符；值**恰好**两键 `count`/`usd_cents` | 键集合比较 + 正则 `^\d{4}-\d{2}$` + 逐项两键比较 | PASS |
| 8 | `grand_total_cents` 等于 accounts 之和，也等于 monthly 之和，也等于逐笔之和（三条路径） | 三条路径分别算，全部 = 59841 | PASS |
| 9 | 每笔金额可指回输入（R04） | `verify_aggregate.py` 打印逐笔 `amount × rate → usd_cents` 对照表，无任何无出处数字 | PASS |

## 1. 结果摘要

逐笔换算（`verify_aggregate.py` 原样输出，见下）：

| txn | account | date | amount | rate | usd_cents |
|---|---|---|---|---|---|
| T001 | acct-north | 2026-01-05 | 12500 | 1.0875 | 13594 |
| T002 | acct-north | 2026-01-19 | 4300 | 1.2650 | **5440**（5439.5 → 进位）|
| T003 | acct-south | 2026-02-02 | 999 | 1.0875 | 1086（1086.4125）|
| T004 | acct-south | 2026-02-11 | 20000 | 1.0000 | 20000 |
| T005 | acct-north | 2026-02-23 | 7250 | 1.0890 | 7895（7895.25）|
| T006 | acct-east | 2026-03-01 | 1500 | 1.2650 | **1898**（1897.5 → 进位）|
| T007 | acct-east | 2026-03-14 | 4550 | 1.0910 | 4964（4964.05）|
| T008 | acct-south | 2026-03-14 | 4550 | 1.0910 | 4964（4964.05）|

聚合：

- `acct-east`: count 2, usd_cents 6862, largest_txn T007
- `acct-north`: count 3, usd_cents 26929, largest_txn T001
- `acct-south`: count 3, usd_cents 26050, largest_txn T004
- `2026-01`: count 2, usd_cents 19034 ／ `2026-02`: count 3, usd_cents 28981 ／ `2026-03`: count 3, usd_cents 11826
- `grand_total_cents`: 59841（= 26929+26050+6862 = 19034+28981+11826 = 逐笔和）

## 2. 边界样本（R07）

`boundary_check.py` 用输入里的边界形态各跑一次，49 项全过：正好 `.5`（正/负）、`2.5→3`（证明不是 banker's rounding）、`.49/.51/.49999`、金额 0、汇率 0、汇率 1.0000、1e15 分（最大项）、负金额、4 位小数精确积；空输入（仅表头）→ 空 accounts/monthly、grand_total 0；`largest_txn` 并列；跨月账户；缺 `fx_rate`／缺 `amount_cents`／非整数金额／非数字汇率／重复 `txn_id`／`date` 过短 —— 全部显式 `SystemExit` 报错，不静默补默认值。

## 3. 本轮最可能的 3 个失败点 → 怎么被发现 → 怎么修

1. **用二进制浮点乘，`.5` 边界判错**（如 `4300*1.265` 在 float 下并不等于 5439.5 精确值）。→ 会被 `verify_aggregate.py` 的 `Fraction` 独立路径与边界用例（`T002/T006` 正好 .5、`2.5`）打出来。→ 修法：全程 `Decimal(str)` / `Fraction`，不出现 `float`。
2. **用 Python 内置 `round()`（banker's rounding，2.5→2）**，与任务书"正好 .5 向上（远离零）"不符；恰好本例 1897.5/5439.5 的邻居都是偶数，肉眼容易看不出来。→ 靠边界用例显式断言 `2.5→3`、`-2.5→-3`。→ 修法：`ROUND_HALF_UP`。
3. **契约多键/少键或数值变字符串**（例如顺手加 `grand_total_usd` 或 `currency`，或用 `json.dumps` 时把 Decimal 序列化成字符串）。→ 顶层键、每账户三键、每月两键、全数值叶子 `isinstance(int)` 四道断言逐项卡。→ 修法：构造时就固定键集合，输出前统一 `int()`。

## 4. 判据命令原样输出与退出码

命令与重跑顺序：`python build_aggregate.py` → `python verify_aggregate.py` → `python boundary_check.py`（stdout+stderr 合并捕获，末行 `exit=` 为该命令退出码）。

`python build_aggregate.py` 原样输出：

```
wrote aggregate.json (8 rows)
exit=0
```

`python verify_aggregate.py` 原样输出（exit=0）：

```
--- per-transaction conversion (exact fraction maths) ---
T001 acct-north  2026-01-05 EUR amount=12500 rate=1.0875 -> usd_cents=13594
T002 acct-north  2026-01-19 GBP amount=4300 rate=1.2650 -> usd_cents=5440
T003 acct-south  2026-02-02 EUR amount=999 rate=1.0875 -> usd_cents=1086
T004 acct-south  2026-02-11 USD amount=20000 rate=1.0000 -> usd_cents=20000
T005 acct-north  2026-02-23 EUR amount=7250 rate=1.0890 -> usd_cents=7895
T006 acct-east   2026-03-01 GBP amount=1500 rate=1.2650 -> usd_cents=1898
T007 acct-east   2026-03-14 EUR amount=4550 rate=1.0910 -> usd_cents=4964
T008 acct-south  2026-03-14 EUR amount=4550 rate=1.0910 -> usd_cents=4964
--- checks ---
PASS input header exactly txn_id,account,date,currency,amount_cents,fx_rate
PASS input row count > 0
PASS output has no UTF-8 BOM
PASS output is valid UTF-8 JSON
PASS top-level keys exactly {accounts, monthly, grand_total_cents}
PASS accounts keys match input accounts
PASS accounts[acct-east] keys exactly {count,usd_cents,largest_txn}
PASS accounts[acct-east].count == 2
PASS accounts[acct-east].usd_cents == 6862
PASS accounts[acct-east].largest_txn == T007
PASS accounts[acct-north] keys exactly {count,usd_cents,largest_txn}
PASS accounts[acct-north].count == 3
PASS accounts[acct-north].usd_cents == 26929
PASS accounts[acct-north].largest_txn == T001
PASS accounts[acct-south] keys exactly {count,usd_cents,largest_txn}
PASS accounts[acct-south].count == 3
PASS accounts[acct-south].usd_cents == 26050
PASS accounts[acct-south].largest_txn == T004
PASS monthly keys match YYYY-MM set
PASS all monthly keys match ^\d{4}-\d{2}$
PASS monthly[2026-01] keys exactly {count,usd_cents}
PASS monthly[2026-01].count == 2
PASS monthly[2026-01].usd_cents == 19034
PASS monthly[2026-02] keys exactly {count,usd_cents}
PASS monthly[2026-02].count == 3
PASS monthly[2026-02].usd_cents == 28981
PASS monthly[2026-03] keys exactly {count,usd_cents}
PASS monthly[2026-03].count == 3
PASS monthly[2026-03].usd_cents == 11826
PASS grand_total_cents == independent recompute
PASS grand_total_cents == sum(accounts.usd_cents)
PASS grand_total_cents == sum(monthly.usd_cents)
PASS accounts count sum == input row count
PASS monthly count sum == input row count
PASS every numeric leaf is a JSON int
PASS accounts[].largest_txn are strings (txn_id)
--- 36 checks, 0 failed ---
ALL CHECKS PASSED
exit=0
```

`python boundary_check.py` 原样输出（exit=0）：

```
PASS to_cents exact .5 rounds up (positive)      [4300 x 1.2650] :: 5440
PASS fraction exact .5 rounds up (positive)    [4300 x 1.2650] :: 5440
PASS to_cents exact .5 rounds away from zero (neg) [-4300 x 1.2650] :: -5440
PASS fraction exact .5 rounds away from zero (neg) [-4300 x 1.2650] :: -5440
PASS to_cents 0.5 -> 1                           [1 x 0.5] :: 1
PASS fraction 0.5 -> 1                         [1 x 0.5] :: 1
PASS to_cents -0.5 -> -1                         [-1 x 0.5] :: -1
PASS fraction -0.5 -> -1                       [-1 x 0.5] :: -1
PASS to_cents 2.5 -> 3 (no banker's rounding)    [5 x 0.5] :: 3
PASS fraction 2.5 -> 3 (no banker's rounding)  [5 x 0.5] :: 3
PASS to_cents -2.5 -> -3                         [-5 x 0.5] :: -3
PASS fraction -2.5 -> -3                       [-5 x 0.5] :: -3
PASS to_cents 1.5 -> 2                           [3 x 0.5] :: 2
PASS fraction 1.5 -> 2                         [3 x 0.5] :: 2
PASS to_cents just below .5 -> 0                 [1 x 0.49] :: 0
PASS fraction just below .5 -> 0               [1 x 0.49] :: 0
PASS to_cents just above .5 -> 1                 [1 x 0.51] :: 1
PASS fraction just above .5 -> 1               [1 x 0.51] :: 1
PASS to_cents 0.49999 -> 0                       [1 x 0.49999] :: 0
PASS fraction 0.49999 -> 0                     [1 x 0.49999] :: 0
PASS to_cents zero amount -> 0                   [0 x 1.0875] :: 0
PASS fraction zero amount -> 0                 [0 x 1.0875] :: 0
PASS to_cents zero rate -> 0                     [12500 x 0] :: 0
PASS fraction zero rate -> 0                   [12500 x 0] :: 0
PASS to_cents integer rate passthrough           [20000 x 1.0000] :: 20000
PASS fraction integer rate passthrough         [20000 x 1.0000] :: 20000
PASS to_cents large amount 1e15 cents            [1000000000000000 x 1.0875] :: 1087500000000000
PASS fraction large amount 1e15 cents          [1000000000000000 x 1.0875] :: 1087500000000000
PASS to_cents negative amount (real rate)        [-12500 x 1.0875] :: -13594
PASS fraction negative amount (real rate)      [-12500 x 1.0875] :: -13594
PASS to_cents 4dp exact product (T003)           [999 x 1.0875] :: 1086
PASS fraction 4dp exact product (T003)         [999 x 1.0875] :: 1086
PASS largest_txn tie -> lexicographic smallest :: 'T0A'
PASS tie account count :: 3
PASS tie account sum :: 299
PASS empty input -> empty accounts :: {}
PASS empty input -> empty monthly :: {}
PASS empty input -> grand total 0 :: 0
PASS max row converts exactly :: 1087500000000000
PASS max row grand total :: 1087500000000000
PASS month keys come from date[:7] :: ['2026-01', '2026-12']
PASS cross-month account sum :: 12
PASS largest_txn picks higher value :: 'T1'
PASS missing_fx_rate -> explicit SystemExit :: 'row 2 (T1): fx_rate not a decimal string: None'
PASS missing_amount -> explicit SystemExit :: "row 2 (T1): amount_cents not an integer: ''"
PASS non_integer_amount -> explicit SystemExit :: "row 2 (T1): amount_cents not an integer: '12.5'"
PASS non_numeric_rate -> explicit SystemExit :: "row 2 (T1): fx_rate not a decimal string: 'abc'"
PASS dup_txn_id -> explicit SystemExit :: 'txn_id not unique'
PASS short_date -> explicit SystemExit :: "row 2 (T1): date too short: '2026'"
--- 49 boundary checks, 0 failed ---
exit=0
```

## 5. 产物

- `aggregate.json`（交付物）
- `build_aggregate.py`（生成脚本，可重跑）
- `verify_aggregate.py`（独立复算 + 契约断言，36 项）
- `boundary_check.py`（边界样本，49 项）

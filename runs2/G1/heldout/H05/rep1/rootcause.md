# 根因说明：`input/tool.py` 为什么「不报错但结果错」

## 一句话结论

错在**解析层**，不在汇总层：脚本先用 `gbk + errors="replace"` 把 UTF-8 字节解成乱码（不抛异常），
再按 `","` 朴素切分，把引号字段切坏，切坏后 `int()` 抛出的 `ValueError` 又被 `except Exception: continue`
整行吞掉。于是 3 条记录在无人知晓的情况下被丢弃，`summarize` 只看到剩下的 11 条，
`rows_total = len(rows)` 自然跟着算小，`main()` 照常写文件、退出码 0。

## 实测对比（同一份 `input/ledger.csv`）

| | 修改前 `input/tool.py` | 修改后 `tool.py` |
| --- | --- | --- |
| `rows_total` | 11 | 14 |
| `by_category` 品类数 | 3 | 4 |
| `amount_total` | 315300 | 909300 |
| 品类名 | `鑼跺彾` / `鍜栧暋璞�` / `闄剁摲鏉�`（乱码） | `茶叶` / `咖啡豆` / `陶瓷杯` / `礼盒,精品` |

`ledger.csv` 共 16 行，其中第 9 行是 `#` 注释、第 12 行是空行，实际记录 **14 条**（这个数由修正后的脚本与
独立用 `csv` 模块重算两路核对一致，均为 14）。修改前只留下 11 条，丢掉的正是 `S-03`、`S-07`、`S-13`
三条 `"礼盒,精品"` 记录，所以整个「礼盒,精品」品类在结果里消失。

---

## 缺陷 1（第 21 行）：用 GBK 解码 UTF-8，并用 `errors="replace"` 掩盖解码错误

```python
21:    text = data.decode("gbk", errors="replace")
```

- **机制**：文件是 UTF-8，却按 GBK 解码。GBK 是双字节编码，会把 UTF-8 的三字节汉字序列按两个字节一组
  重新组合，得到一串合法但毫无意义的汉字（`茶叶` → `鑼跺彾`，`咖啡豆` → `鍜栧暋璞�`）。
- 更关键的是 `errors="replace"`：遇到无法解码的字节不去抛 `UnicodeDecodeError`，而是替换成 `U+FFFD`
  （本文件里一共产生 **8 个**替换符，见每行结尾的 `�`）。这就是「不报错」的第一层——**错误在解码层被就地
  抹平**，后面所有代码拿到的都是已经损坏的字符串，且无从察觉。
- **改法**：`text = data.decode("utf-8")`（严格模式）。坏字节直接抛 `UnicodeDecodeError`（它是
  `ValueError` 的子类，符合「必须抛 `ValueError`」的要求），而不是伪造内容继续算。

## 缺陷 2（第 26 行）：按逗号朴素切分，不识别双引号包裹

```python
26:        parts = [p.strip() for p in line.split(",")]
```

- **机制**：`"礼盒,精品"` 是一个字段，但 `split(",")` 会把它切成 `"礼盒` 和 `精品"` 两段，该行变成 5 段：
  `['S-03', '"礼盒', '精品"', '1', '158000']`。字段位置整体错位：本应是 `qty` 的 `parts[2]` 变成了
  `精品"`，`int('精品"')` 立刻抛 `ValueError`。这是「数据在解析层就错了」的直接原因，也是丢行的触发点。
- 附带问题：`p.strip()` 对被引号包裹的字段内容也做了裁剪，字段内容两端的空格会被静默删掉（本文件没有这种
  数据，但属于「静默改数据」）。
- **改法**：写一个逐字符状态机 `_split_fields()`：字段以 `"` 开头则读到配对的右引号，包裹内的逗号、以及
  成对写法的 `""` 都按字段内容处理；未包裹字段读到逗号为止；未闭合的引号、以及未包裹字段里出现的 `"`、
  右引号后出现的多余字符，一律 `ValueError`。包裹字段内容原样保留（不再 `strip`），未包裹字段才裁掉两端空白。

## 缺陷 3（第 27–33 行）：`except Exception: continue` 把逐行失败变成静默丢数据

```python
27:        try:
28:            store = parts[0]
29:            category = parts[1]
30:            qty = int(parts[2])
31:            unit_cents = int(parts[3])
32:        except Exception:
33:            continue
```

- **机制**：这是「不报错」的第二层，也是丢 3 条记录的直接原因。缺陷 2 造成 `int('精品"')` 抛 `ValueError`；
  空行被过滤后不会走到这里，但**字段不足的行会抛 `IndexError`**（第 28–31 行的下标访问），同样被吞。
  `except Exception` 吞掉了包括 `ValueError`、`IndexError` 在内的所有异常，`continue` 连一条日志都不留，
  调用方拿到的只是「少了 3 行的列表」。于是错误从「这一行有问题」变成了「这一行不存在」。
- 配套的认知陷阱在 `summarize`：`rows_total = len(rows)`，它只反映「解析后剩下几条」，不反映「文件里本该有几条」，
  所以汇总结构完整、字段齐备，数字却小了一截，`main()` 也不会报错，退出码仍是 0。
- **改法**：删掉 `try/except`。解析失败就让 `ValueError` 带着行号冒到调用方
  （如 `第 3 行：字段数应为 4，实际 5：...`），宁可整批失败，也不静默少算。

## 缺陷 4（第 26、28–31 行）：不校验字段数——既会丢行，也会静默截断

- **机制**：脚本从不检查 `len(parts) == 4`。
  - 字段多于 4 个且第 3、4 段恰好是数字时不会报错：`S,a,1,2,extra` 会被解析成 `{'qty': 1, 'unit_cents': 2}`，
    第 5 段被**静默截断**（已实测）。
  - 字段少于 4 个时靠 `IndexError` 兜底，再被缺陷 3 吞掉，变成**静默跳过**（`S` 这样的行实测返回 `[]`）。
  两种情况都违反「必须抛 `ValueError`」。
- **改法**：切分后先 `if len(fields) != 4: raise ValueError(...)`，再按下标取值；行尾多余的逗号因此也会被判定为 5 段
  而报错，而不是被当成空字段悄悄接受。

## 缺陷 5（第 30–31 行）：`int()` 的宽松语义不等于「十进制整数」

```python
30:            qty = int(parts[2])
31:            unit_cents = int(parts[3])
```

- **机制**：`int(str)` 接受的东西比「十进制整数」宽得多：`int("1_0") == 10`（下划线）、`int(" 5 ") == 5`（首尾空白）、
  `int("+5") == 5`（正号）、`int("１２") == 12`（全角数字）——均已实测。也就是说，像 `1_0`、全角数字这类
  明显不是十进制整数的输入会被静默接受并算进金额，属于「改用默认/宽松解释」而不是报错。
  （本文件的数据不受影响，这是修好之后必须堵住的边界。）
- **改法**：`_parse_int()` 先用 `re.fullmatch(r"[+-]?[0-9]+", text)` 做全匹配校验，不匹配就抛 `ValueError`，
  通过后再 `int(text, 10)`。保留显式的 `+`/`-` 号（台账里退货记负数合理），其余一律拒绝。

## 缺陷 6（第 13 行）：`ROOT` 靠 `parent.parent` 猜目录，与交付位置耦合

```python
13: ROOT = Path(__file__).resolve().parent.parent
14: LEDGER = ROOT / "input" / "ledger.csv"
15: TARGET = ROOT / "out" / "summary.json"
```

- **机制**：原脚本放在 `input/` 下，`parent.parent` 才正好是工作目录。本次交付要求 `tool.py` 放在工作目录根部，
  若照抄这一行，`LEDGER` 会被解析成上一级目录下的 `input/ledger.csv`，`main()` 直接 `FileNotFoundError`，
  或者把 `out/summary.json` 写到错误位置。它不是本次「乱码 + 少记录」的原因，但属于必须一起修掉的缺陷。
- **改法**：

```python
BASE = Path(__file__).resolve().parent          # tool.py 与 input/ 同级
if not (BASE / "input" / "ledger.csv").is_file():
    BASE = Path.cwd()                           # 兼容从别处调用
```

## 汇总层（第 39–51 行）没有问题

`summarize` 的 `setdefault` + 累加、`amount += qty * unit_cents`、`amount_total` 的第二次循环求和，
以及 `rows_total = len(rows)` 本身都写得对；`amount_total` 等于各品类 `amount` 之和（909300 = 189500 + 88300 + 594000 + 37500）。
它的问题只是「输入已经被上游弄少了」，所以修好解析层之后这一段原样保留（只把金额累加收进同一个循环，避免重复计算）。

---

## 改法对照表

| 原行号 | 问题 | 修法 |
| --- | --- | --- |
| 13 | `ROOT` 用 `parent.parent` 猜目录 | 以脚本所在目录为 `BASE`，找不到 `input/ledger.csv` 时退回 `Path.cwd()` |
| 21 | `decode("gbk", errors="replace")` | `decode("utf-8")` 严格解码 |
| 26 | `line.split(",")` 朴素切分 | `_split_fields()` 状态机，支持引号包裹与包裹内逗号 |
| 26 | `p.strip()` 连引号字段内容一起裁 | 引号字段内容原样保留，只裁未包裹字段两端空白 |
| 27–33 | `except Exception: continue` | 删除，让 `ValueError` 带行号抛出 |
| 26–31 | 不校验字段数 | `len(fields) != 4` 直接 `ValueError` |
| 30–31 | `int()` 语义过宽 | `_parse_int()` 用 `[+-]?[0-9]+` 全匹配后转整数 |

## 实现取舍（任务书没写死、这里主动定下的口径）

1. 引号字段内支持 CSV 惯例的 `""` 表示一个字面双引号；未闭合引号、未包裹字段中出现 `"`、右引号后有多余字符，
   都按非法字段抛 `ValueError`。
2. 未包裹字段两端空白裁掉（原脚本行为，保留）；引号字段内容一字不改。
3. `qty` / `unit_cents` 允许显式 `+`/`-` 号，但不接受下划线、全角数字、小数点、空串。
4. 严格 UTF-8 解码失败抛 `UnicodeDecodeError`，它是 `ValueError` 的子类，满足「必须抛 `ValueError`」的契约。

## 交付前自检（原样落盘，可重跑）

命令与输出（工作目录 `<workspace>/agi/runs2/G1/heldout/H05/rep1`）：

```
$ PYTHONIOENCODING=utf-8 python tool.py
<workspace>/agi/runs2/G1/heldout/H05/rep1/out/summary.json
exit=0
```

独立复核（用标准库 `csv` 模块重算一遍，与 `out/summary.json` 逐字段比较，并用空输入 / 0 值 / 超大整数 /
缺字段 / 多字段 / 浮点 qty / 下划线 qty / 未闭合引号 / 非 UTF-8 字节各跑一次）：

```
csv_module_records: 14
json == csv reference: True
rows_total: 14 amount_total: 909300
category rows sum: 14 qty sum: 34 amount sum: 909300
ok empty / ok blank_and_comment / ok zeros / ok big / ok quoted_comma /
ok quoted_escaped_quote / ok signed / ok spaces
raise missing_field -> ValueError is_valueerror: True
raise extra_field -> ValueError is_valueerror: True
raise trailing_comma -> ValueError is_valueerror: True
raise float_qty -> ValueError is_valueerror: True
raise underscore_qty -> ValueError is_valueerror: True
raise empty_qty -> ValueError is_valueerror: True
raise bad_quotes -> ValueError is_valueerror: True
raise stray_quote -> ValueError is_valueerror: True
raise non_utf8 -> UnicodeDecodeError is_valueerror: True
exit=0
```

逐品类核对（`amount` = `qty * unit_cents` 累加，单位：分）：

| category | rows | qty | amount | 组成 |
| --- | --- | --- | --- | --- |
| `茶叶` | 4 | 15 | 189500 | S-01 4×12500、S-05 6×12500、S-09 2×13500、S-12 3×12500 |
| `咖啡豆` | 4 | 10 | 88300 | S-02 2×8800、S-06 5×8800、S-10 1×9100、S-14 2×8800 |
| `礼盒,精品` | 3 | 4 | 594000 | S-03 1×158000、S-07 2×158000、S-13 1×120000 |
| `陶瓷杯` | 3 | 5 | 37500 | S-04 3×4200、S-08 1×9900、S-11 1×15000 |
| 合计 | 14 | 34 | 909300 | `amount_total` 与各品类之和一致 |

## 交付契约核对（逐项对照任务书原文）

- `tool.py`：三个入口签名保持 `parse_bytes(data: bytes) -> list[dict]`、`summarize(rows) -> dict`、`main()`。
- 记录 dict 的键固定为 `store` / `category` / `qty` / `unit_cents`，无多余键；`qty`、`unit_cents` 为 `int`
  （超大整数实测仍为 `int`，无浮点）。
- `summarize` 返回值键固定为 `rows_total` / `amount_total` / `by_category`，无多余键；每个品类的键固定为
  `rows` / `qty` / `amount`；全部为整数。
- `out/summary.json` 由修好的 `tool.py` 对 `input/ledger.csv` 实际跑出（UTF-8，无 BOM，末行换行）。
- `input/ledger.csv` 只读未改（落盘前后字节一致，350 字节，无 BOM、无 CRLF）。

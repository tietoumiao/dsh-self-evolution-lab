# 根因说明：`input\tool.py` 为什么「不报错，但数据已经错了」

> 本文所有「第 N 行」若指脚本，均为**修改前** `input\tool.py` 的物理行号（该文件共 63 行）；
> 若指 `ledger.csv`，均指该文件的**物理行号**（含第 9 行注释、第 12 行空行）。

## 0. 一句话结论

修前脚本同时踩了两类独立错误，而**每一类都被一处「吃掉错误的写法」挡住了**，所以进程退出码 0、`out\summary.json` 结构完整，但结果已经错了：

| 现象 | 真正原因（哪一行） | 被什么吞掉 | 发生在哪一层 |
| --- | --- | --- | --- |
| 品类名乱码 | 第 21 行用 GBK 解码 UTF-8 字节 | 同一行的 `errors="replace"` 把解码失败降级成 U+FFFD，不抛 `UnicodeDecodeError` | 字节 → `str` 的**解码层**，早于任何切分 |
| 记录数 14 → 11 | 第 26 行朴素 `split(",")` 不认双引号，`"礼盒,精品"` 被切成 2 段 | 第 32–33 行 `except Exception: continue` 把整条记录丢弃 | **切分层**出错，**记录装配层**吞掉 |
| 字段数异常也不报错 | 第 27–31 行只按下标取 `parts[0..3]`，从不校验段数 | 同上（多出来的段没有任何代码看它） | 记录装配层（静默截断） |
| 非法数字混得过去 | 第 30–31 行直接 `int(...)`，Python 的 `int()` 接受面比「十进制整数」宽 | 同上 | 数值转换层 |

修前 / 修后的可观测差异（原脚本实测值见 §2）：

| 指标 | 修前（原脚本） | 修后 | 差额 |
| --- | --- | --- | --- |
| `rows_total` | 11 | 14 | −3 条记录被整条丢弃 |
| `amount_total` | 315300 | 909300 | −594000 分 |
| `by_category` 键 | 3 个乱码键（`鑼跺彾` / `鍜栧暋璞�` / `闄剁摲鏉�`） | 4 个正确键（茶叶 / 咖啡豆 / 礼盒,精品 / 陶瓷杯） | 整类「礼盒,精品」凭空消失 |

丢掉的 594000 = `158000×1 + 158000×2 + 120000×1`，正好是 `ledger.csv` **第 3、7、15 行**三条记录之和。

---

## 1. 逐处缺陷

### 缺陷 A — 第 21 行：拿 GBK 去解 UTF-8 字节，并且 `errors="replace"`

```python
21:    text = data.decode("gbk", errors="replace")
```

**机制（两层错）**

1. **编码选错**：`ledger.csv` 是 UTF-8（`od` 可见第 2 个字段是 `e8 8c b6 e5 8f b6`）。GBK 是双字节编码，会把 UTF-8 的三字节序列重新按两字节配对：`茶叶`（6 字节）→ GBK 解成 3 个汉字 `鑼跺彾`（U+947C U+8DFA U+5F7E）；`礼盒,精品` → `绀肩洅,绮惧搧`。
2. **错误处理策略选错**：`咖啡豆` 是 9 个字节（奇数），最后剩一个前导字节 `0x86`，它后面的 `0x2C`（半角逗号）不是合法 GBK 尾字节——解码器在这里**确实报了错**，但 `errors="replace"` 把这一处换成 `U+FFFD`（`�`）后继续解码，异常根本不出 `decode()`。所以 `咖啡豆` 变成 `鍜栧暋璞�`，字段名里还带着一个替换字符。

**为什么「不报错」**：`errors="replace"` 的语义就是「解码失败不要抛，塞个替换字符继续」。它把「编码猜错」这个**必须让人知道的错误**，降级成「字符串里多了几个怪字符」。

**为什么「结构还是完整的」**：乱码是**确定性**的——同一个名字每次映射到同一串乱码，所以按 `category` 分组照旧能合并，`rows/qty/amount` 在乱码键下依然自洽（§2 可见 `鑼跺彾` 的 4 行/15 件/189500 分与修后完全一致）。不盯着键名逐字看，`summary.json` 看上去毫无破绽。

**改法**：`data.decode("utf-8")`（严格模式）。字节不是合法 UTF-8 就直接抛 `UnicodeDecodeError`（它本身就是 `ValueError` 的子类），绝不用替换字符蒙混。

### 缺陷 B — 第 26 行：`line.split(",")` 不认识双引号

```python
26:        parts = [p.strip() for p in line.split(",")]
```

**机制**：输入格式规定「字段可被半角双引号包裹，包裹内的逗号属于字段内容」，但 `str.split(",")` 眼里引号只是普通字符，**引号不是切分语法的一部分**。于是

* `S-03,"礼盒,精品",1,158000` 被切成 5 段：`S-03`、`"礼盒`、`精品"`、`1`、`158000`；
* 第 29 行把 `"礼盒` 当成品类名（还带着左引号）；
* 第 30 行执行 `int('精品"')` → `ValueError: invalid literal for int() with base 10: '绮惧搧"'`（乱码来自缺陷 A）。

这不是「偶尔切错」，是**规则没实现**：几乎是 CSV 的核心语义，被一行 `split` 顶替了。

**改法**：写一个引号感知的切分器（`_split_fields`）：引号只允许出现在字段开头；包裹内的逗号不切分；包裹内的 `""` 解释成一个字面双引号；右引号之后只允许空白，再接逗号或行尾；引号未闭合、或右引号后还有多余字符，一律抛 `ValueError`（不予猜测、不做"尽力而为"的修补）。

### 缺陷 C — 第 27–33 行（核心是 32–33）：`except Exception: continue`

```python
27:        try:
28:            store = parts[0]
29:            category = parts[1]
30:            qty = int(parts[2])
31:            unit_cents = int(parts[3])
32:        except Exception:
33:            continue
```

**机制**：缺陷 B 产生的 `ValueError` 在这里被**整条记录**级别的 `continue` 吃掉：不打日志、不计数、不告警、不让异常冒泡，`rows` 里干脆没有这一条。于是《`ledger.csv` 第 3、7、15 行》三条记录人间蒸发，14 → 11。

同时这层 `except` 还掩盖了两件事：

* 段数不足（`parts[2]` / `parts[3]` 的 `IndexError`）同样被无声吞掉；
* 段数过多时没人发现（见缺陷 D）。

而且 `except Exception` 的捕获面过大——连写错变量名造成的 `NameError`、`KeyError` 这类**程序 bug** 都会被伪装成「这行数据有问题，跳过」。

**为什么「不报错」**：这是最典型的一种**吞异常**写法：`try` 范围罩住了整个字段装配 + 数值转换，`except` 兜住一切，动作是 `continue`——把「输入非法」和「代码有 bug」两类完全不同的信号，统一映射成「输出少一点数据」。退出码 0，日志干净，`summary.json` 依旧键齐全。

**危害为什么比「崩掉」更大**：崩溃会立刻被发现；这里是**静默的数据丢失**，而且丢掉的恰好是整整一个品类（3 条 `礼盒,精品` 全没了），输出里不会出现空值、0 值或空键——没有任何提示「曾经有个品类」。

**改法**：删掉这层兜底。解析失败必须抛 `ValueError`，并在消息里带上**行号 + 原始行**（`第 3 行字段数为 5，应为 4：'S-03,"礼盒,精品",1,158000'`）。宁可整体失败一次，也不能交付一份少了 3 条记录的汇总。

### 缺陷 D — 第 28–31 行：只按下标取 4 段，从不校验段数（静默截断）

```python
28:            store = parts[0]
29:            category = parts[1]
30:            qty = int(parts[2])
31:            unit_cents = int(parts[3])
```

**机制**：这里没有任何 `len(parts) != 4` 的检查。段数 > 4 时，`parts[4:]` 被**无声丢弃**——一条 5 字段的行会被当成 4 字段记录「成功」入库，金额可能正好落到错误的列上；段数 < 4 时是 `IndexError`，再交给缺陷 C 吞掉。

注意它和缺陷 B 的关系：缺陷 B 让**含逗号的引号字段**多切出段，缺陷 D 让**真正多字段的坏行**少报错。二者叠加才是「字段数异常永远不报错」。

**改法**：显式校验 `if len(fields) != 4: raise ValueError(...)`。段数不对就是数据格式错，不允许截断、不允许补默认值。

### 缺陷 E — 第 30–31 行：`int(...)` 的接受面比「十进制整数」宽

```python
30:            qty = int(parts[2])
31:            unit_cents = int(parts[3])
```

**机制**：Python 的 `int()` 不只接受 `123`：`int("1_0") == 10`（下划线分组）、`int("+4") == 4`、`int("４") == 4`（全角数字，`int` 接受 Unicode 十进制数字）、`int(" 4 ") == 4`。这些都不是「十进制整数文本」，却会被静默转成数值；反之真正非法的值又交给缺陷 C 整条丢弃。两个方向的错误都没有报出来。

**改法**：先用 `^[+-]?[0-9]+$`（只放行 ASCII 数字）校验，再 `int(text, 10)`；不合格抛 `ValueError` 并带行号与字段名。`qty`/`unit_cents` 因此保证是 `int`。

### 缺陷 F — 第 18 行：`def parse_bytes(data)` 缺类型注解

原签名既没有 `data: bytes`，也没有 `-> list[dict]`，与「三个入口的签名必须保持不变」的交付契约不符。它不影响运行，但契约明确要求 `parse_bytes(data: bytes) -> list[dict]`。

**改法**：补齐注解。修后的 `tool.py` 里三个入口现在是 `parse_bytes(data: bytes) -> list[dict]`、`summarize(rows) -> dict`、`main()`（`inspect.signature` 实测见 §4）。

### 不是缺陷、但顺手整理了：第 47–49 行的第二次遍历

```python
47:    amount_total = 0
48:    for row in rows:
49:        amount_total += row["qty"] * row["unit_cents"]
```

`amount_total` 被**第二次遍历**重算一遍，而第 46 行已经按品类累加过同一批乘积。它本身不产生当前错误（两处算法一致），但属于「同一事实的两处实现」，只改一处就会总分对不上。已合并成单次遍历：同一循环里同时累加 `by_category` 与 `amount_total`（结果不变）。

---

## 2. 修前行为的证据（原样 stdout，`python -B "...\Temp\h05verify\rowdiag.py"`；用修前第 21 / 26 / 28–33 行的逻辑逐行重放）

```
 1  KEEP  nfields=4  category='鑼跺彾'
 2  KEEP  nfields=4  category='鍜栧暋璞�'
 3  DROP  nfields=5  category='"绀肩洅'  ValueError: invalid literal for int() with base 10: '绮惧搧"'
 4  KEEP  nfields=4  category='闄剁摲鏉�'
 5  KEEP  nfields=4  category='鑼跺彾'
 6  KEEP  nfields=4  category='鍜栧暋璞�'
 7  DROP  nfields=5  category='"绀肩洅'  ValueError: invalid literal for int() with base 10: '绮惧搧"'
 8  KEEP  nfields=4  category='闄剁摲鏉�'
 9  SKIP  空行/注释
10  KEEP  nfields=4  category='鑼跺彾'
11  KEEP  nfields=4  category='鍜栧暋璞�'
12  SKIP  空行/注释
13  KEEP  nfields=4  category='闄剁摲鏉�'
14  KEEP  nfields=4  category='鑼跺彾'
15  DROP  nfields=5  category='"绀肩洅'  ValueError: invalid literal for int() with base 10: '绮惧搧"'
16  KEEP  nfields=4  category='鍜栧暋璞�'

kept=11 dropped=3 total=14（ledger.csv 实际记录数=14）
```

修前脚本的 `parse_bytes` / `summarize` 实际结果（直接 `exec` 原文件、未改动它）：

```
rows: 11
{"amount_total": 315300,
 "by_category": {"鍜栧暋璞�": {"amount": 88300, "qty": 10, "rows": 4},
                 "鑼跺彾":   {"amount": 189500, "qty": 15, "rows": 4},
                 "闄剁摲鏉�": {"amount": 37500, "qty": 5, "rows": 3}},
 "rows_total": 11}
```

> 排查时踩过一个坑，记在这里免得后人误判：Windows 控制台是 GBK，`print(repr(乱码))` 会把乱码**按 GBK 再编码**，而 GBK 编码后的字节恰好**等于原始 UTF-8 字节**，于是终端上看起来仍是「茶叶」——「没乱」是假象。改用 `PYTHONUTF8=1` 并打印 `U+` 码点才看清：`鑼跺彾` = U+947C U+8DFA U+5F7E。

## 3. 修后的数字（每个数都能对回 `ledger.csv` 的物理行）

| 行 | store | category | qty | unit_cents | amount = qty×unit_cents |
| --- | --- | --- | --- | --- | --- |
| 1 | S-01 | 茶叶 | 4 | 12500 | 50000 |
| 2 | S-02 | 咖啡豆 | 2 | 8800 | 17600 |
| 3 | S-03 | 礼盒,精品 | 1 | 158000 | 158000 |
| 4 | S-04 | 陶瓷杯 | 3 | 4200 | 12600 |
| 5 | S-05 | 茶叶 | 6 | 12500 | 75000 |
| 6 | S-06 | 咖啡豆 | 5 | 8800 | 44000 |
| 7 | S-07 | 礼盒,精品 | 2 | 158000 | 316000 |
| 8 | S-08 | 陶瓷杯 | 1 | 9900 | 9900 |
| 9 | — | `# 以下为补单记录`（注释，不是记录） | — | — | — |
| 10 | S-09 | 茶叶 | 2 | 13500 | 27000 |
| 11 | S-10 | 咖啡豆 | 1 | 9100 | 9100 |
| 12 | — | 空行（不是记录） | — | — | — |
| 13 | S-11 | 陶瓷杯 | 1 | 15000 | 15000 |
| 14 | S-12 | 茶叶 | 3 | 12500 | 37500 |
| 15 | S-13 | 礼盒,精品 | 1 | 120000 | 120000 |
| 16 | S-14 | 咖啡豆 | 2 | 8800 | 17600 |

按品类汇总（= `out\summary.json` 的内容）：

| category | rows | qty | amount | 来源行 |
| --- | --- | --- | --- | --- |
| 茶叶 | 4 | 15 | 189500 | 1、5、10、14 |
| 咖啡豆 | 4 | 10 | 88300 | 2、6、11、16 |
| 礼盒,精品 | 3 | 4 | 594000 | 3、7、15 |
| 陶瓷杯 | 3 | 5 | 37500 | 4、8、13 |
| **合计** | **14** | **34** | **909300** | 14 条记录 |

## 4. 复算与核对（判据命令 + 原样输出）

判据脚本用**标准库 `csv`** 另写一遍复算（不复用 `tool.py` 的手写扫描器），再和落盘的 `out\summary.json` 逐键比对；随后跑 22 个边界用例。

```
$ python -B "<home>/AppData/Local/Temp/h05verify/verify.py"
[1] 独立复算 records = 14
    咖啡豆        rows=4 qty=10 amount=88300
    礼盒,精品      rows=3 qty=4 amount=594000
    茶叶         rows=4 qty=15 amount=189500
    陶瓷杯        rows=3 qty=5 amount=37500
    amount_total = 909300
[1] summary.json == 独立复算: True
[2] 键集合/类型(int)/三类自洽: OK
    空输入                -> OK
    只有空行               -> OK
    只有注释               -> OK
    单条+空行+注释           -> OK
    qty=0              -> OK
    最大项                -> OK
    引号内逗号(store)       -> OK
    引号内逗号(category)    -> OK
    引号内两个逗号            -> OK
    CRLF 行尾              -> OK
    空字段                -> OK
    缺字段(3)             -> ValueError (ValueError 子类=ValueError) OK
    多字段(5)             -> ValueError (ValueError 子类=ValueError) OK
    qty 非整数            -> ValueError (ValueError 子类=ValueError) OK
    unit 非整数           -> ValueError (ValueError 子类=ValueError) OK
    下划线数字              -> ValueError (ValueError 子类=ValueError) OK
    空 qty              -> ValueError (ValueError 子类=ValueError) OK
    全角数字               -> ValueError (ValueError 子类=ValueError) OK
    引号未闭合              -> ValueError (ValueError 子类=ValueError) OK
    引号后多余字符            -> ValueError (ValueError 子类=ValueError) OK
    非法 UTF-8           -> UnicodeDecodeError (ValueError 子类=UnicodeDecodeError) OK
    空行内引号              -> ValueError (ValueError 子类=ValueError) OK
[3] 边界用例全通过: True
[4] summarize([]) = {"rows_total": 0, "amount_total": 0, "by_category": {}}
[4] summarize 最大项 = {"rows_total": 1, "amount_total": 999999998000000001, "by_category": {"cat": {"rows": 1, "qty": 999999999, "amount": 999999998000000001}}}
[4] summarize qty=0 = {"rows_total": 1, "amount_total": 0, "by_category": {"cat": {"rows": 1, "qty": 0, "amount": 0}}}
[5] parse_bytes  (data: bytes) -> list[dict]
[5] summarize    (rows) -> dict
[5] main         ()
RESULT: ALL PASS
EXIT=0
```

`main()` 入口实测（工作目录下）：

```
$ python tool.py
<workspace>/agi/runs2/G2/heldout/H05/rep1/out/summary.json
EXIT=0
```

---

## 5. 自检

### 5.1 交付契约逐项核对（对着已落盘的产物核，不凭记忆）

| # | 契约项（任务书原文口径） | 核对方式 | 结果 |
| --- | --- | --- | --- |
| 1 | `tool.py` 落在工作目录下 | 目录列举 | 有，4749 B |
| 2 | 入口 `parse_bytes(data: bytes) -> list[dict]` | `inspect.signature` | 一致 |
| 3 | 入口 `summarize(rows) -> dict` | 同上 | 一致 |
| 4 | 入口 `main()` | 同上 + 实跑 | 一致，退出码 0 |
| 5 | 记录键固定为 `store`/`category`/`qty`/`unit_cents` | 断言 `set(row) == {...}` | 一致 |
| 6 | `qty`、`unit_cents` 是 `int` | `type(v) is int`（排除 bool） | 通过 |
| 7 | 按 UTF-8 解码 | 源码 `.decode("utf-8")` + 非法字节用例抛错 | 通过 |
| 8 | 跳过空行与 `#` 开头行 | 用例「只有空行」「只有注释」「单条+空行+注释」 | 通过 |
| 9 | 双引号包裹 + 包裹内逗号 | 3 条真实记录 + 3 个用例（store 侧引号 / category 侧引号 / 包裹内两个逗号）+ CRLF 行尾用例 | 通过 |
| 10 | 字段数≠4 → `ValueError` | 用例「缺字段(3)」「多字段(5)」 | 抛 `ValueError` |
| 11 | 非十进制整数 → `ValueError` | 用例「qty 非整数」「unit 非整数」「下划线数字」「空 qty」「全角数字」 | 抛 `ValueError` |
| 12 | 不静默跳过 / 不截断 / 不填默认值 | 源码无 `except ...: continue`、无 `or 0` 默认值；上述用例均可捕获 | 通过 |
| 13 | `summarize` 返回 `{"rows_total","amount_total","by_category"}` | 断言键集合 | 一致 |
| 14 | `by_category` 值含 `rows`/`qty`/`amount` | 断言键集合 | 一致 |
| 15 | `amount` = `qty * unit_cents` 累加、单位分、全整数 | 独立复算比对 + 断言 `type is int` | 通过 |
| 16 | 无多余键 | 断言 `set(d) == {...}`（未加任何额外字段） | 通过 |
| 17 | `main()` 读 `input\ledger.csv`、写 `out\summary.json` | 实跑 + 落盘文件哈希 | 通过 |
| 18 | `out\summary.json` 由修好的脚本生成 | 连跑两次 `python tool.py`，SHA256 稳定为 `D88773…`，且内容与独立复算相等 | 通过 |
| 19 | `rootcause.md` 每处缺陷带修前行号 | 本文件 §1：第 21 / 26 / 27–33 / 28–31 / 30–31 / 18 / 47–49 行 | 通过 |
| 20 | 未改动 `input\ledger.csv` | SHA256 `ED2A42156BD001CA2278D6C39B1DDE9FE12DF0D2A3DA31D2C301A93EAFA263CF`，mtime 仍为 2026-11-02 23:08:49（本次会话开始于 23:23） | 通过 |

### 5.2 本轮最可能的 3 个失败点（以及它们会怎么被发现）

1. **路径基准错配**：`tool.py` 从 `input\` 搬到工作目录根后，若仍沿用原来的 `Path(__file__).parent.parent`，会去找 `H05\input\ledger.csv`，`main()` 直接 `FileNotFoundError`。
   会被怎么发现：跑 `python tool.py` 看退出码与 `out\summary.json` 是否真的被重写（不看打印）。
   已修：`ROOT = _HERE if (_HERE / "input").is_dir() else _HERE.parent`，并用 `exec(compile(...))` 把 `__file__` 分别伪造成 `<root>\tool.py` 与 `<root>\input\tool.py` 两种放法各跑一遍分支，两者都解析到 `rep1\input\ledger.csv` 与 `rep1\out\summary.json`（`rootbranch.py`：PASS）。
2. **引号状态机退化成"能切就行"**：若右引号之后的 `quoted` 标志被重置，或未闭合引号/引号后多余字符不报错，就会把错字段静默入库——正是原脚本的病，只是换了个位置。
   会被怎么发现：边界用例「引号未闭合」「引号后多余字符」「非法 UTF-8」必须抛 `ValueError`；「引号内两个逗号」必须得到 `a,b,c` 一个字段。全部已覆盖并通过。
3. **被"看起来对"骗过（本次真实遇到）**：Windows 控制台是 GBK，`repr(乱码)` 再按 GBK 编码后字节与原 UTF-8 字节重合，终端显示仍是「茶叶」，让人误判「没乱码」。另外我一度在 `input\` 目录里执行 `python tool.py`，实际跑的是**原脚本**（同名文件），它把 `out\summary.json` 覆盖成了 11 行/315300 的错误版本。
   会被怎么发现：只认「读回产物 + 与独立复算比对」这种可观测检查——比对 `out\summary.json` 的 `rows_total/amount_total` 与 SHA256，而不是看命令退出码或屏幕上的字符。已修：重新生成 `out\summary.json`（SHA256 `D88773D8214444CFB55F92E787C27EF788DFF35F40A0AD6A5E7A70066F68FEEF`，`rows_total=14`、`amount_total=909300`），并且只从工作目录根运行修好的 `tool.py`。

### 5.3 残留说明

* 未使用第三方库；解析、汇总、校验全部是标准库（`json`/`re`/`pathlib`，校验脚本另用 `csv` 做独立复算）。
* `parse_bytes` 的两条额外兼容：包裹内 `""` 解释为字面双引号；右引号后允许空白再跟逗号/行尾。输入里没有这两种形态，属于「不改变现有语义」的加固。
* `qty`/`unit_cents` 允许前导 `+`/`-`（`^[+-]?[0-9]+$`）；本输入全部为正整数。

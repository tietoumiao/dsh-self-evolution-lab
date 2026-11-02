# 判定：错在测试，规格与实现一致

判据只有 `input\SPEC.md`。我把规格逐条翻译成可执行断言，直接调用 `input\impl.py` 的公开函数核对，
42 项取样（含单位换算、floor 取整、strip、各类非法输入、`fits` 含上限、`split_even` 余数分配）
全部通过，`TOTAL_FAILS=0`。也就是说实现的行为与规格无偏差，跑不通的原因在测试的期望值/断言方式。

因此本轮**没有改动实现**：产物 `impl.py` 与 `input\impl.py` 逐字节相同（sha256 均为
`5ab715d0c28d1a4c9a4a61110298f703170c808695adcf90428ee8c7d3b02dfb`）。

## 两处错误用例

- test_parse_decimal_units: 期望值按二进制单位算成了 1536（1.5×1024），但规格 §1 规定 `KB`=1000（十进制，且大小写敏感），正确期望是 `parse_size("1.5KB") == 1500`（1.5×1000）；断言方式 `assertEqual` 本身没问题，只改期望值，被测输入实参 `"1.5KB"` 未动。
- test_fits_boundary: 断言方向写反了，规格 §2 明确"判定含上限"——`used == 上限` 返回 `True`，只有 `used > 上限` 才 `False`；`fits(4096, "4KiB")` 中 4096 = 4×1024 恰好等于上限，正确期望是 `assertTrue(...)`（实际返回真值 `True`），不是 `assertFalse`；被测输入实参 `4096` 与 `"4KiB"` 未动。

## 为什么不是实现错（不是"改测试迁就实现"）

1. 规格是唯一判据，而实现的每个可观测出口都与规格文字一致，没有一处需要"解释成笔误"。
2. 两处失败各自独立：一条把十进制单位当二进制算，一条把"含上限"读成"不含上限"，
   都是典型的测试作者手误，而不是同一处实现 bug 的两个表征。
3. 若反过来改实现（把 `KB` 改成 1024、把 `<=` 改成 `<`），会与规格 §1 的单位表和
   §2 的"判定含上限"直接冲突，还会连带打挂本次未点名的 `test_parse_binary_units`
   （`1.5KiB`→1536 依赖 KiB=1024）等用例，属于把规格改错来迁就测试。

## 未改动的 4 条用例

`test_parse_binary_units`、`test_parse_rejects_bad_input`、`test_split_even_remainder`、
`test_split_even_rejects_invalid` 四条：用 `ast` 按方法体抽取源码片段，与 `input\test_impl.py`
逐字比对，结果 `untouched byte-identical: True`；整份 diff 也只有那 2 行断言变化
（第 15 行 1536→1500，第 19 行 assertFalse→assertTrue），两处都落在被点名的用例内。
用例条数与函数名共 6 条，`method names identical: True count: 6`。

## 自检

1. 判据命令（产物目录下执行）：`python -m unittest test_impl -v` → 6 条全 ok，
   `Ran 6 tests` / `OK`，退出码 0（原样输出见下）。
2. 交付契约逐项核对：`impl.py` 原样未改；`test_impl.py` 6 条用例名一字不差、只改 2 条断言、
   未改被测输入实参；`notes.md` 本节之外无其他 `- ` 开头的行（恰好 2 行）；三份产物均为
   UTF-8 无 BOM（二进制读回检查 `BOM: False`，`utf-8 decodable: True`）。
3. 本轮最可能的 3 个失败点，都已被检查覆盖：
   第一条，误改实现来迁就测试 → 用 sha256 对比 `impl.py` 与 `input\impl.py`，相同；
   第二条，顺手"美化"了不该动的 4 条用例 → 用 ast 抽方法体逐字比对，`untouched byte-identical: True`；
   第三条，只修好测试却没验证规格一致性（可能实现本来就错）→ 42 项规格符合性检查 `TOTAL_FAILS=0`。

### 原样输出：`python -m unittest test_impl -v`（退出码 0）

```
test_fits_boundary (test_impl.TestImpl.test_fits_boundary) ... ok
test_parse_binary_units (test_impl.TestImpl.test_parse_binary_units) ... ok
test_parse_decimal_units (test_impl.TestImpl.test_parse_decimal_units) ... ok
test_parse_rejects_bad_input (test_impl.TestImpl.test_parse_rejects_bad_input) ... ok
test_split_even_rejects_invalid (test_impl.TestImpl.test_split_even_rejects_invalid) ... ok
test_split_even_remainder (test_impl.TestImpl.test_split_even_remainder) ... ok

----------------------------------------------------------------------
Ran 6 tests in 0.000s

OK
```

### 原样输出：修复前的红（同一份测试，仅两处断言未改）

```
FAIL: test_fits_boundary (test_impl.TestImpl.test_fits_boundary)
AssertionError: True is not false

FAIL: test_parse_decimal_units (test_impl.TestImpl.test_parse_decimal_units)
AssertionError: 1500 != 1536

Ran 6 tests
FAILED (failures=2)
```

### 原样输出：篡改/一致性核对脚本（退出码 0）

```
method names identical: True count: 6
differing methods: ['test_parse_decimal_units', 'test_fits_boundary']
untouched byte-identical: True
impl.py identical to input: True
impl sha256 == input sha256: True
impl.py BOM: False utf-8 decodable: True
test_impl.py BOM: False utf-8 decodable: True
```

### 原样输出：规格符合性检查末行

```
TOTAL_FAILS=0
```

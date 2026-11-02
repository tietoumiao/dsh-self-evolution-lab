# 判断：是测试写错了，实现是对的

## 判据与结论

`input\SPEC.md` 第 3 行写明「本文件是行为的唯一判据；测试应当与之一致」。因此凡测试断言与规格冲突处，一律以规格为准、改测试。`impl.py` 按任务书要求**原样提交**（与 `input\impl.py` 字节一致，sha256 `5ab715d0c28d1a4c9a4a61110298f703170c808695adcf90428ee8c7d3b02dfb`），未改一行，也没有为了迁就旧断言去动行为。

改前跑 `python -m unittest test_impl` 的结果是 `Ran 6 tests … FAILED (failures=2)`，失败的正好就是下面这 2 条；其余 4 条在旧测试里本来就是绿的。

## 两条错误用例

- test_parse_decimal_units: 期望值错。规格 §1 规定 `KB` 为十进制单位、等于 1000（整数部分是 `1000`，不是 `1024`），故 `1.5KB` = 1.5 × 1000 = **1500** 字节；原断言那 1536 是二进制 `KiB` 的值（1536 只属于同文件里 `1.5KiB` 那条用例）。已把 `assertEqual(parse_size("1.5KB"), 1536)` 的期望值改为 `1500`，被测实参 `"1.5KB"` 不动。
- test_fits_boundary: 断言方式错（判据方向反了）。规格 §2 规定判定**含上限**：`used == 上限` 必须返回 `True`，只有 `used > 上限` 才 `False`；`fits(4096, "4KiB")` 里 4 KiB = 4096，恰好等于上限，按规格应返回 **True**。已把 `assertFalse(fits(4096, "4KiB"))` 换成 `assertTrue(fits(4096, "4KiB"))`，实参 `4096` 与 `"4KiB"` 不动（没有把边界值改成 4097 之类来绕过）。

## 为什么不是实现错

逐条拿被测调用与规格原文对齐，实现的实际返回值与规格完全一致，是旧断言单方面偏离规格：

1. `impl.py` 第 15 行 `"KB": 1000`、第 39 行 `int(Decimal(number) * _UNITS[unit])`：`1.5 × 1000 = 1500.0`，`int` 截断得 `1500`，符合 §1「十进制 `KB` = 1000」与「小数部分向下取整」。若实现错，应是 1024 系列进十进制分支，但代码里两套单位表分得清清楚楚。
2. `impl.py` 第 48 行 `return used <= parse_size(limit_text)`：用的是 `<=`，正好实现 §2「含上限：`used == 上限` 返回 `True`」。旧断言的 `assertFalse` 等于要求 `used == 上限` 返回 `False`，与规格直接对立。
3. 另外 4 条用例在旧实现下已全绿，说明实现的其余行为（二进制单位、非法输入一律 `ValueError`、切分余数从第一份起 +1、非法参数 `ValueError`）也与规格一致，不存在「实现整体跑偏、测试只是碰巧发现两处」的情形。

综上：两条断言是测试自身的笔误（一条抄错了单位进制，一条把含上限判反），实现无需改动。

## 改动范围自检

1. 用例条数与函数名不变：仍是 6 条，`test_parse_binary_units`、`test_parse_decimal_units`、`test_fits_boundary`、`test_parse_rejects_bad_input`、`test_split_even_remainder`、`test_split_even_rejects_invalid` 一字不差。
2. 与 `input\test_impl.py` 逐行比对，差异只有 2 行（第 15 行期望值 `1536` → `1500`，第 19 行 `assertFalse` → `assertTrue`）；其余 4 条用例连同注释、字面量、空行均未触碰。
3. 修完在产物目录跑 `python -m unittest test_impl`，结果为 `Ran 6 tests … OK`，退出码 0。
4. 边界样本另跑了 4 组确认判据方向：`fits(4096, "4KiB")` 为 `True`、`fits(4097, "4KiB")` 为 `False`、`parse_size("1KB")` 为 `1000`、`parse_size("1KiB")` 为 `1024`，与 §1/§2 一致。

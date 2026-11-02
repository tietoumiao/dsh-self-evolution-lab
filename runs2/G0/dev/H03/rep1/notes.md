# 判断依据：为什么是测试错、不是实现错

判据只有一个：`input/SPEC.md`。把规格逐条对到 `input/impl.py` 的实现上，两处失败点都恰好落在「实现严格照规格做、而测试的期望值写错/写反」的地方。

## §1 `parse_size`：实现符合规格

规格要求 `KB` = 1000（十进制）、`KiB` = 1024，且乘积的小数部分向下取整。实现里 `_UNITS` 就是 `"KB": 1000`、`"KiB": 1024`，最后一步 `int(Decimal(number) * _UNITS[unit])` 对正数等价于 floor。实测 `parse_size("1.5KB") == 1500`、`parse_size("1.5KiB") == 1536`、`parse_size("1.0001KiB") == 1024`（与规格自己给的 floor 例子一致）。

结论：实现返回的 1500 才是规格要求的正确答案；测试断言的 1536 是把十进制单位误当成二进制口径的结果（1536 只有 `1.5KiB` 才成立）。

## §2 `fits`：实现符合规格

规格要求判定**含上限**：`used == 上限` 返回 `True`，只有 `used > 上限` 才返回 `False`。实现写的是 `return used <= parse_size(limit_text)`，等号归入 `True`。实测 `fits(4096, "4KiB") == True`、`fits(4097, "4KiB") == False`、`fits(0, "0B") == True`。

结论：实现正确；测试的 `assertFalse(fits(4096, "4KiB"))` 把边界判反了，且与该用例自己的注释「边界：正好等于配额上限」自相矛盾。

## 排除「实现错」的理由

1. 未修改前跑 `python -m unittest test_impl`：6 条里恰好 2 条失败（`test_parse_decimal_units`、`test_fits_boundary`），其余 4 条全绿；失败信息分别是 `1500 != 1536` 和 `True is not false`，方向都是「实现给了规格值、测试期望与规格相反」。
2. 对规格里未被测试覆盖的条款做了抽查，实现全部符合：`parse_size` 对 `"1.5"`、`""`、`"1 kb"`、`"1.5KIB"`、`None`、`"1.5KiBx"`、`"-1KiB"`、`"1 5KiB"`、`"1e3KiB"` 均抛 `ValueError`；`fits(True, "1B")`、`fits(-1, "1B")` 抛 `ValueError`；`split_even(0, 3) == [0, 0, 0]`、`split_even(7, 7) == [1]*7`、`split_even(2, 5) == [1, 1, 0, 0, 0]`（余数从第一份开始 +1）。
3. 所以不存在「为了迁就测试去改实现」的动机：`impl.py` 按原样整份复制，一个字节都没动（SHA-256 与 `input/impl.py` 相同：`5ab715d0c28d1a4c9a4a61110298f703170c808695adcf90428ee8c7d3b02dfb`）。

## 两处写错的断言

- test_parse_decimal_units: 期望值写成了二进制口径的 1536；按 SPEC §1 十进制 `KB` = 1000 且小数部分向下取整，`parse_size("1.5KB")` 的正确期望是 1500，应当断言 `assertEqual(parse_size("1.5KB"), 1500)`。
- test_fits_boundary: 断言方向写反成 `assertFalse`；按 SPEC §2 判定含上限、`used == 上限` 视为能放进，正确期望是 `assertTrue(fits(4096, "4KiB"))`（被测调用的输入实参 4096 与 `"4KiB"` 保持原样未动）。

## 自检

1. 在产物目录跑 `python -m unittest test_impl`：`Ran 6 tests` → `OK`（全绿）。
2. 与 `input/test_impl.py` 逐字比对：全文件仅这 2 行的期望值/断言方式不同，其余 4 条用例（`test_parse_binary_units`、`test_parse_rejects_bad_input`、`test_split_even_remainder`、`test_split_even_rejects_invalid`）连同其余注释、字面量、docstring、`unittest.main()` 全部逐字未动；用例仍是 6 条，方法名一字不差。
3. 被测调用的输入实参未改（仍是 `"1.5KB"` 与 `fits(4096, "4KiB")`），改动只落在期望值与断言方法上；`impl.py` 未改动。

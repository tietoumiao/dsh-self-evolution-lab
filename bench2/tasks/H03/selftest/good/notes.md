# 修测试说明

实现本身没有问题：`impl.py` 三段逻辑都与 `SPEC.md` 一致，故障出在测试里。共 2 条断言写错：

## 错误用例

- test_fits_boundary: 断言写成 `assertFalse(fits(4096, "4KiB"))`，但 SPEC §2 规定判定含上限，`used` 等于上限时应当返回 `True`，正确断言是 `assertTrue(fits(4096, "4KiB"))`。
- test_parse_decimal_units: 断言写成 `assertEqual(parse_size("1.5KB"), 1536)`，把十进制单位 `KB` 当成了二进制（1024 进位）；SPEC §1 规定 `KB` = 1000 字节，正确期望值是 1500。

## 处理

只改上面这 2 条断言的期望值，其余 4 条用例逐字未动；`impl.py` 未做任何修改（原样提交）。

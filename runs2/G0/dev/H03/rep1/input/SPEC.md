# 规格：`impl.py` 的对外行为

`impl.py` 提供三个函数。本文件是行为的唯一判据；测试应当与之一致。

## §1 `parse_size(text) -> int`

把形如 `1.5KiB` 的数量文本解析成**整数**字节数。

- 先把文本 `strip()`（去首尾空白）。
- 形状必须是 `<数字><单位>`：数字部分匹配 `\d+(\.\d+)?`（不接受正负号、千分位、指数），单位部分精确等于下列之一，且**区分大小写**：
  - 二进制：`KiB` = 1024、`MiB` = 1024²、`GiB` = 1024³
  - 十进制：`KB` = 1000、`MB` = 1000²、`GB` = 1000³
  - `B` = 1
- 乘积的小数部分**向下取整**（floor），不做四舍五入。例如 `1.0001KiB` 得 `1024`。
- 任何不合法的输入一律抛 `ValueError`（不返回 `None`、不静默取 0）：空串、缺单位、未知单位、单位大小写不符、负数、数字内含空格、非字符串。

## §2 `fits(used, limit_text) -> bool`

判断 `used`（已用字节数）能否放进 `limit_text`（如 `"4KiB"`）表示的配额。

- `used` 必须是非负整数（`bool` 不算整数），否则抛 `ValueError`。
- 配额上限由 `parse_size(limit_text)` 得到；`limit_text` 不合法时同样抛 `ValueError`。
- 判定**含上限**：`used == 上限` 时视为能放进（返回 `True`）；只有 `used > 上限` 才返回 `False`。

## §3 `split_even(total, parts) -> list[int]`

把非负整数 `total` 尽可能平均地切成 `parts` 份，返回长度恰为 `parts` 的整数列表。

- 每份先取 `total // parts`，余数 `total % parts` 从第一份开始逐份 +1。
- 例：`split_even(10, 3)` 得 `[4, 3, 3]`；`split_even(0, 3)` 得 `[0, 0, 0]`；`split_even(7, 7)` 得 `[1, 1, 1, 1, 1, 1, 1]`。
- `total` 为负或不是整数（`bool` 不算整数）⇒ `ValueError`；`parts <= 0` 或不是整数 ⇒ `ValueError`。

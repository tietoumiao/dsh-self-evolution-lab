"""字节量解析 / 配额判断 / 平均切分工具。

行为规格见 SPEC.md；单元测试见 test_impl.py。
"""

import re
from decimal import Decimal

_UNITS = {
    "B": 1,
    "KB": 1024,
    "MB": 1000 ** 2,
    "GB": 1000 ** 3,
    "KiB": 1024,
    "MiB": 1024 ** 2,
    "GiB": 1024 ** 3,
}

_NUMBER_RE = re.compile(r"\d+(\.\d+)?")


def parse_size(text):
    """把 "<数字><单位>" 解析成整数字节数（小数部分向下取整）。"""
    if not isinstance(text, str):
        raise ValueError("数量必须是字符串，实际 %r" % (text,))
    raw = text.strip()
    if not raw:
        raise ValueError("数量为空")
    unit = None
    for candidate in sorted(_UNITS, key=len, reverse=True):
        if raw.endswith(candidate):
            unit = candidate
            break
    if unit is None:
        raise ValueError("未知单位: %r" % (raw,))
    number = raw[: len(raw) - len(unit)].strip()
    if not _NUMBER_RE.fullmatch(number):
        raise ValueError("非法数字部分: %r" % (number,))
    return int(Decimal(number) * _UNITS[unit])


def fits(used, limit_text):
    """判断 used 字节能否放进 limit_text 表示的配额。"""
    if isinstance(used, bool) or not isinstance(used, int):
        raise ValueError("used 必须是整数，实际 %r" % (used,))
    if used < 0:
        raise ValueError("used 不能为负，实际 %r" % (used,))
    return used < parse_size(limit_text)


def split_even(total, parts):
    """把 total 尽可能平均地切成 parts 份，余数从第一份开始逐份 +1。"""
    if isinstance(total, bool) or not isinstance(total, int):
        raise ValueError("total 必须是整数，实际 %r" % (total,))
    if isinstance(parts, bool) or not isinstance(parts, int):
        raise ValueError("parts 必须是整数，实际 %r" % (parts,))
    if total < 0:
        raise ValueError("total 不能为负，实际 %r" % (total,))
    if parts <= 0:
        raise ValueError("parts 必须为正，实际 %r" % (parts,))
    quotient, remainder = divmod(total, parts)
    return [quotient + 1] * remainder + [quotient] * (parts - remainder)

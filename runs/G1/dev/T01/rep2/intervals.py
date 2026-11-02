"""时长解析与格式化（修复版）。

导出：
    parse_interval(text: str) -> int
    format_interval(total_seconds: int) -> str

导入本模块不产生任何副作用（无 I/O、无打印、无全局可变状态变更）。
"""

import re

__all__ = ["parse_interval", "format_interval"]

# 只用 ASCII 数字字符类 [0-9]（即便启用 re.UNICODE 也不会匹配全角/阿拉伯-印度数字），
# 且用 fullmatch，因此前后空白、换行、正负号、小数点、下划线、千分位都不被接受。
_TWO_GROUPS = re.compile(r"([0-9]{1,2}):([0-9]{1,2})")
_THREE_GROUPS = re.compile(r"([0-9]{1,5}):([0-9]{1,2}):([0-9]{1,2})")


def parse_interval(text: str) -> int:
    """把 ``MM:SS`` 或 ``HH:MM:SS`` 文本解析成总秒数。

    ``MM``/``SS``：1～2 位 ASCII 数字，取值 0..59。
    ``HH``：1～5 位 ASCII 数字，取值 >= 0。
    其余任何输入（含非 ``str``）一律抛 ``ValueError``。
    """
    if not isinstance(text, str):
        raise ValueError(
            "interval text must be str, got %s" % type(text).__name__
        )

    match = _TWO_GROUPS.fullmatch(text)
    if match is not None:
        minutes = int(match.group(1), 10)
        seconds = int(match.group(2), 10)
        if minutes > 59 or seconds > 59:
            raise ValueError("minute/second out of range: %r" % (text,))
        return minutes * 60 + seconds

    match = _THREE_GROUPS.fullmatch(text)
    if match is not None:
        hours = int(match.group(1), 10)
        minutes = int(match.group(2), 10)
        seconds = int(match.group(3), 10)
        if minutes > 59 or seconds > 59:
            raise ValueError("minute/second out of range: %r" % (text,))
        return hours * 3600 + minutes * 60 + seconds

    raise ValueError("invalid interval text: %r" % (text,))


def format_interval(total_seconds: int) -> str:
    """把总秒数格式化为 ``HH:MM:SS``（小时至少 2 位，可超过 99）。

    ``total_seconds`` 为负数、或类型不是 ``int``（``bool``、``float`` 也算不是）
    时抛 ``ValueError``。
    """
    # bool 是 int 的子类，必须先排除。
    if isinstance(total_seconds, bool) or not isinstance(total_seconds, int):
        raise ValueError(
            "total_seconds must be int, got %s" % type(total_seconds).__name__
        )
    if total_seconds < 0:
        raise ValueError("total_seconds must be >= 0, got %d" % total_seconds)

    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

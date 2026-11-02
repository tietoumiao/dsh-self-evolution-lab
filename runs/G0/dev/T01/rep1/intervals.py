"""时长（interval）解析与格式化。

导出两个函数：

- ``parse_interval(text) -> int``：把 ``MM:SS`` / ``HH:MM:SS`` 解析成总秒数。
- ``format_interval(total_seconds) -> str``：把总秒数格式化成 ``HH:MM:SS``。

导入本模块没有任何副作用（不读写文件、不打印、不联网）。

契约要点：
- 只接受 ASCII 数字 ``0-9``，禁止空白、正负号、小数点、下划线、千分位等。
- ``MM`` / ``SS`` 为 1~2 位且取值 ``0..59``；``HH`` 为 1~5 位且不小于 ``0``。
- 任何非法输入一律抛 ``ValueError``（包括类型不对的情况）。
"""

import re

__all__ = ["parse_interval", "format_interval"]

# 用 [0-9] 而不是 \d，避免 str.isdigit / \d 把全角、阿拉伯-印度数字等
# Unicode 数字算作合法；fullmatch 保证整串匹配，因此尾随换行也不会被放过。
_MMSS_RE = re.compile(r"([0-9]{1,2}):([0-9]{1,2})")
_HHMMSS_RE = re.compile(r"([0-9]{1,5}):([0-9]{1,2}):([0-9]{1,2})")

_SECONDS_PER_MINUTE = 60
_SECONDS_PER_HOUR = 3600


def parse_interval(text):
    """把时长文本解析成总秒数（``int``）。

    ``text`` 必须是 ``str``，形状为 ``MM:SS`` 或 ``HH:MM:SS``。
    其余任何情况都抛 ``ValueError``。
    """
    if not isinstance(text, str):
        raise ValueError(
            "interval must be a str, got %s" % type(text).__name__
        )

    match = _MMSS_RE.fullmatch(text)
    if match is not None:
        hours = 0
        minutes, seconds = match.group(1), match.group(2)
    else:
        match = _HHMMSS_RE.fullmatch(text)
        if match is None:
            raise ValueError("invalid interval: %r" % (text,))
        hours, minutes, seconds = match.group(1), match.group(2), match.group(3)

    hours = int(hours)
    minutes = int(minutes)
    seconds = int(seconds)

    if minutes > 59 or seconds > 59:
        raise ValueError("invalid interval: %r" % (text,))

    return hours * _SECONDS_PER_HOUR + minutes * _SECONDS_PER_MINUTE + seconds


def format_interval(total_seconds):
    """把总秒数格式化成 ``HH:MM:SS``。

    小时位至少 2 位、超过 99 小时按实际位数输出；分钟与秒恰好 2 位。
    ``total_seconds`` 必须是 ``int`` 且非负（``bool`` 不算 ``int``），否则抛 ``ValueError``。
    """
    if isinstance(total_seconds, bool) or not isinstance(total_seconds, int):
        raise ValueError(
            "total_seconds must be an int, got %s" % type(total_seconds).__name__
        )
    if total_seconds < 0:
        raise ValueError("total_seconds must be non-negative, got %d" % total_seconds)

    hours, remainder = divmod(total_seconds, _SECONDS_PER_HOUR)
    minutes, seconds = divmod(remainder, _SECONDS_PER_MINUTE)
    return "%02d:%02d:%02d" % (hours, minutes, seconds)

"""时长解析与格式化模块。

对外契约（函数名一字不差）：

    parse_interval(text: str) -> int
        只接受 ``MM:SS`` 与 ``HH:MM:SS`` 两种形状，返回总秒数。
    format_interval(total_seconds: int) -> str
        输出 ``HH:MM:SS``；小时位至少 2 位，超过 99 小时按实际位数输出。

导入本模块不产生任何副作用（无 I/O、无全局可变状态、不解析命令行）。
"""

from __future__ import annotations

import re

__all__ = ["parse_interval", "format_interval"]

# 每一组只允许 ASCII 数字 0-9：MM / SS 为 1~2 位，HH 为 1~5 位。
# 使用 fullmatch，因此前后空白、换行、正负号、小数点、下划线、千分位、
# 非 ASCII 数字（如全角 / 阿拉伯-印度数字）都会被整体匹配失败挡掉。
_INTERVAL_RE = re.compile(
    r"(?:(?P<hours>[0-9]{1,5}):)?(?P<minutes>[0-9]{1,2}):(?P<seconds>[0-9]{1,2})"
)

_SECONDS_PER_MINUTE = 60
_SECONDS_PER_HOUR = 3600
_MAX_MINUTE_OR_SECOND = 59


def parse_interval(text: str) -> int:
    """把 ``MM:SS`` 或 ``HH:MM:SS`` 时长文本解析成总秒数。

    参数必须是 ``str``；任何不合契约的输入（空串、组数不对、超范围、
    含非法字符、非 ``str``）一律抛 ``ValueError``。
    """
    if not isinstance(text, str):
        raise ValueError(f"interval must be str, got {type(text).__name__}")

    match = _INTERVAL_RE.fullmatch(text)
    if match is None:
        raise ValueError(f"invalid interval text: {text!r}")

    minutes = int(match.group("minutes"))
    seconds = int(match.group("seconds"))
    if minutes > _MAX_MINUTE_OR_SECOND:
        raise ValueError(f"minutes out of range 0..59: {minutes}")
    if seconds > _MAX_MINUTE_OR_SECOND:
        raise ValueError(f"seconds out of range 0..59: {seconds}")

    hours_text = match.group("hours")
    hours = 0 if hours_text is None else int(hours_text)
    return hours * _SECONDS_PER_HOUR + minutes * _SECONDS_PER_MINUTE + seconds


def format_interval(total_seconds: int) -> str:
    """把总秒数格式化成 ``HH:MM:SS``。

    ``total_seconds`` 为负数、或类型不是 ``int``（``bool`` 与 ``float``
    也算不是 ``int``）时抛 ``ValueError``。
    """
    if isinstance(total_seconds, bool) or not isinstance(total_seconds, int):
        raise ValueError(
            f"total_seconds must be int, got {type(total_seconds).__name__}"
        )
    if total_seconds < 0:
        raise ValueError(f"total_seconds must be >= 0, got {total_seconds}")

    hours, remainder = divmod(total_seconds, _SECONDS_PER_HOUR)
    minutes, seconds = divmod(remainder, _SECONDS_PER_MINUTE)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

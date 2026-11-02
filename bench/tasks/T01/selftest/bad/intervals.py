"""时长处理模块（已补 HH 支持，但范围/类型校验仍缺失）。"""

import re

_PATTERN = re.compile(r"^([0-9]{1,5}):([0-9]{1,2})(?::([0-9]{1,2}))?$")


def parse_interval(text):
    """把时长文本解析成总秒数。"""
    m = _PATTERN.match(text)
    if not m:
        raise ValueError("invalid interval")
    first, second, third = m.groups()
    if third is None:
        return int(first) * 60 + int(second)
    return int(first) * 3600 + int(second) * 60 + int(third)


def format_interval(total_seconds):
    """把总秒数格式化成 HH:MM:SS。"""
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

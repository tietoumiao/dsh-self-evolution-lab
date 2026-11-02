"""时长处理模块（修复版）。"""

import re

_SHORT = re.compile(r"^([0-9]{1,2}):([0-9]{1,2})$")
_LONG = re.compile(r"^([0-9]{1,5}):([0-9]{1,2}):([0-9]{1,2})$")


def parse_interval(text):
    """把时长文本解析成总秒数；非法输入抛 ValueError。"""
    if not isinstance(text, str):
        raise ValueError("text must be a string")
    m = _LONG.match(text)
    if m:
        hours, minutes, seconds = (int(g) for g in m.groups())
        if minutes > 59 or seconds > 59:
            raise ValueError("minute or second out of range")
        return hours * 3600 + minutes * 60 + seconds
    m = _SHORT.match(text)
    if m:
        minutes, seconds = (int(g) for g in m.groups())
        if minutes > 59 or seconds > 59:
            raise ValueError("minute or second out of range")
        return minutes * 60 + seconds
    raise ValueError("invalid interval: %r" % (text,))


def format_interval(total_seconds):
    """把总秒数格式化成 HH:MM:SS；负数或非 int 抛 ValueError。"""
    if type(total_seconds) is not int or total_seconds < 0:
        raise ValueError("total_seconds must be a non-negative int")
    hours, rest = divmod(total_seconds, 3600)
    minutes, seconds = divmod(rest, 60)
    return "%02d:%02d:%02d" % (hours, minutes, seconds)

"""时长解析与格式化模块。

对外只导出两个函数：

    parse_interval(text: str) -> int
        把 ``MM:SS`` 或 ``HH:MM:SS`` 文本解析成总秒数。

    format_interval(total_seconds: int) -> str
        把总秒数格式化成 ``HH:MM:SS`` 文本。

导入本模块不产生任何副作用（不读文件、不打印、不修改全局状态）。
所有非法输入统一抛 ``ValueError``。
"""

__all__ = ["parse_interval", "format_interval"]

# 只认 ASCII 数字字符；不用 str.isdigit()/int() 直接校验，因为它们会放过
# 非 ASCII 数字（如全角 "１"、阿拉伯-印度数字 "٣"）和下划线分隔符。
_ASCII_DIGITS = frozenset("0123456789")

_SECONDS_PER_MINUTE = 60
_SECONDS_PER_HOUR = 3600

_MIN_GROUP_DIGITS = 1
_MINUTE_GROUP_MAX_DIGITS = 2
_SECOND_GROUP_MAX_DIGITS = 2
_HOUR_GROUP_MAX_DIGITS = 5

_MINUTE_SECOND_MAX_VALUE = 59


def _parse_group(part, name, max_digits):
    """校验单个字段：非空、纯 ASCII 数字、位数不超过 max_digits，返回 int。"""
    if not part:
        raise ValueError(f"时长字段 {name} 不能为空：{part!r}")
    if len(part) > max_digits:
        raise ValueError(f"时长字段 {name} 最多 {max_digits} 位，实际 {len(part)} 位：{part!r}")
    if len(part) < _MIN_GROUP_DIGITS:  # 与上面的空串检查等价，保留语义明确性
        raise ValueError(f"时长字段 {name} 至少 {_MIN_GROUP_DIGITS} 位：{part!r}")
    for char in part:
        if char not in _ASCII_DIGITS:
            raise ValueError(f"时长字段 {name} 只能包含 ASCII 数字 0-9：{part!r}")
    return int(part)


def _check_minute_second(value, name):
    """分钟/秒的取值范围是 0..59。"""
    if value > _MINUTE_SECOND_MAX_VALUE:
        raise ValueError(f"时长字段 {name} 必须在 0..{_MINUTE_SECOND_MAX_VALUE} 之间：{value}")
    return value


def parse_interval(text):
    """把 ``MM:SS`` 或 ``HH:MM:SS`` 文本解析成总秒数（int）。

    - 只接受两种形状：``MM:SS`` 与 ``HH:MM:SS``。
    - 各字段只允许 ASCII 数字 ``0-9``，不接受空白、正负号、小数点、下划线、千分位。
    - ``MM``/``SS`` 允许 1~2 位且取值在 ``0..59``；``HH`` 允许 1~5 位且不小于 0。
    - 其它任何输入（含空串、字段数不对、超范围、非法字符、非 str）抛 ``ValueError``。
    """
    if not isinstance(text, str):
        raise ValueError(f"parse_interval() 需要 str，收到 {type(text).__name__}: {text!r}")

    parts = text.split(":")
    field_count = len(parts)

    if field_count == 2:
        minutes = _check_minute_second(
            _parse_group(parts[0], "MM", _MINUTE_GROUP_MAX_DIGITS), "MM"
        )
        seconds = _check_minute_second(
            _parse_group(parts[1], "SS", _SECOND_GROUP_MAX_DIGITS), "SS"
        )
        return minutes * _SECONDS_PER_MINUTE + seconds

    if field_count == 3:
        hours = _parse_group(parts[0], "HH", _HOUR_GROUP_MAX_DIGITS)
        minutes = _check_minute_second(
            _parse_group(parts[1], "MM", _MINUTE_GROUP_MAX_DIGITS), "MM"
        )
        seconds = _check_minute_second(
            _parse_group(parts[2], "SS", _SECOND_GROUP_MAX_DIGITS), "SS"
        )
        return hours * _SECONDS_PER_HOUR + minutes * _SECONDS_PER_MINUTE + seconds

    raise ValueError(f"时长文本必须是 MM:SS 或 HH:MM:SS，实际有 {field_count} 段：{text!r}")


def format_interval(total_seconds):
    """把总秒数（int，非负）格式化成 ``HH:MM:SS``。

    - 小时位至少 2 位；超过 99 小时按实际位数输出，不截断。
    - 分钟与秒恰好 2 位，补前导零；``0`` 输出 ``00:00:00``。
    - 负数、非 int（``bool`` 与 ``float`` 也算不是 int）抛 ``ValueError``。
    """
    if isinstance(total_seconds, bool) or not isinstance(total_seconds, int):
        raise ValueError(
            f"format_interval() 需要非负 int，收到 {type(total_seconds).__name__}: {total_seconds!r}"
        )
    if total_seconds < 0:
        raise ValueError(f"format_interval() 不接受负数：{total_seconds!r}")

    hours, remainder = divmod(total_seconds, _SECONDS_PER_HOUR)
    minutes, seconds = divmod(remainder, _SECONDS_PER_MINUTE)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

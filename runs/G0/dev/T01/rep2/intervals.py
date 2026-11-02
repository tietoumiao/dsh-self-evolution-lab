"""时长解析与格式化模块。

对外只导出两个函数：

- ``parse_interval(text)``  ->  ``int``   （把 ``MM:SS`` / ``HH:MM:SS`` 解析成总秒数）
- ``format_interval(secs)`` ->  ``str``   （把总秒数格式化成 ``HH:MM:SS``）

导入本模块不产生任何副作用（不做 I/O、不打印、不改全局状态）。
所有参数非法的情况一律抛 ``ValueError``。
"""

__all__ = ["parse_interval", "format_interval"]

# 只接受 ASCII 数字字符；str.isdigit() 会放过全角/其他 Unicode 数字，故不用它。
_ASCII_DIGITS = frozenset("0123456789")

_SECONDS_PER_MINUTE = 60
_SECONDS_PER_HOUR = 3600

# MM / SS 最多 2 位、取值 0..59；HH 最多 5 位、取值 >= 0。
_MAX_MINUTE_SECOND_DIGITS = 2
_MAX_HOUR_DIGITS = 5
_MAX_MINUTE_SECOND_VALUE = 59


def _check_digits(part, name, max_digits):
    """校验一组由纯 ASCII 数字构成、位数不超过 max_digits；返回其十进制值。"""
    if not part:
        raise ValueError(f"{name} 不能为空")
    if len(part) > max_digits:
        raise ValueError(f"{name} 最多 {max_digits} 位数字：{part!r}")
    for ch in part:
        if ch not in _ASCII_DIGITS:
            raise ValueError(f"{name} 只能包含 ASCII 数字字符 0-9：{part!r}")
    return int(part)


def parse_interval(text: str) -> int:
    """把时长文本解析成总秒数（int）。

    合法形状只有 ``MM:SS`` 与 ``HH:MM:SS`` 两种：

    - 每一组只允许 ASCII 数字 ``0-9``，不接受空白、正负号、小数点、下划线、千分位；
    - ``MM`` / ``SS`` 为 1~2 位，取值 0..59；
    - ``HH`` 为 1~5 位，取值不小于 0。

    其它任何输入（非 str、空串、组数不对、超范围、含非法字符）都抛 ``ValueError``。
    """
    if not isinstance(text, str):
        raise ValueError(f"parse_interval 需要 str，收到 {type(text).__name__}: {text!r}")

    parts = text.split(":")
    if len(parts) == 2:
        hours_text = None
        minutes_text, seconds_text = parts
    elif len(parts) == 3:
        hours_text, minutes_text, seconds_text = parts
    else:
        raise ValueError(f"时长文本必须是 MM:SS 或 HH:MM:SS 形状：{text!r}")

    if hours_text is None:
        hours = 0
    else:
        hours = _check_digits(hours_text, "HH", _MAX_HOUR_DIGITS)

    minutes = _check_digits(minutes_text, "MM", _MAX_MINUTE_SECOND_DIGITS)
    seconds = _check_digits(seconds_text, "SS", _MAX_MINUTE_SECOND_DIGITS)

    if minutes > _MAX_MINUTE_SECOND_VALUE:
        raise ValueError(f"MM 必须在 0..59 之间：{minutes_text!r}")
    if seconds > _MAX_MINUTE_SECOND_VALUE:
        raise ValueError(f"SS 必须在 0..59 之间：{seconds_text!r}")

    return hours * _SECONDS_PER_HOUR + minutes * _SECONDS_PER_MINUTE + seconds


def format_interval(total_seconds: int) -> str:
    """把总秒数格式化成 ``HH:MM:SS``。

    - 小时位至少 2 位，超过 99 小时时按实际位数输出（不截断、不溢出）；
    - 分钟与秒恰好 2 位，补前导零；
    - ``0`` 输出 ``00:00:00``；
    - 负数、非 ``int``（``bool`` / ``float`` 等）抛 ``ValueError``。
    """
    # bool 是 int 的子类，必须单独排除。
    if isinstance(total_seconds, bool) or not isinstance(total_seconds, int):
        raise ValueError(
            f"format_interval 需要 int，收到 {type(total_seconds).__name__}: {total_seconds!r}"
        )
    if total_seconds < 0:
        raise ValueError(f"总秒数不能为负：{total_seconds!r}")

    hours, remainder = divmod(total_seconds, _SECONDS_PER_HOUR)
    minutes, seconds = divmod(remainder, _SECONDS_PER_MINUTE)
    # hours 用 02d：>=100 时自然输出全部位数，不会被截断。
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

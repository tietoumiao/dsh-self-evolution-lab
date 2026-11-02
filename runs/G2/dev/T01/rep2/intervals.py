"""时长解析与格式化。

公开接口（导入本模块不产生任何副作用）：

- ``parse_interval(text: str) -> int``
  把 ``MM:SS`` 或 ``HH:MM:SS`` 形式的时长文本解析成总秒数。
- ``format_interval(total_seconds: int) -> str``
  把总秒数格式化成 ``HH:MM:SS``。

两个函数在输入不合法时统一抛 ``ValueError``。
"""

__all__ = ["parse_interval", "format_interval"]

# 只接受 ASCII 数字；str.isdigit() 会放过 "１"（全角）、"٣"（阿拉伯-印度数字）、
# "²"（上标）等字符，不能用来做本模块的校验。
_ASCII_DIGITS = frozenset("0123456789")


def _parse_field(raw, name, min_len, max_len, max_value=None):
    """把一个数字组校验并转换成 int；任何不合法情形都抛 ValueError。"""
    if len(raw) < min_len or len(raw) > max_len:
        raise ValueError(
            f"{name} 必须是 {min_len}~{max_len} 位 ASCII 数字，实际为 {raw!r}"
        )
    for ch in raw:
        if ch not in _ASCII_DIGITS:
            raise ValueError(f"{name} 含非法字符 {ch!r}，只允许 ASCII 数字 0-9")
    value = int(raw)
    if max_value is not None and value > max_value:
        raise ValueError(f"{name} 必须在 0~{max_value} 之间，实际为 {value}")
    return value


def parse_interval(text: str) -> int:
    """把 ``MM:SS`` 或 ``HH:MM:SS`` 解析成总秒数。

    每一组只允许 ASCII 数字 ``0-9``，不允许空白、正负号、小数点、下划线或千分位。
    ``MM``/``SS`` 为 1~2 位且取值 0~59；``HH`` 为 1~5 位且取值不小于 0。
    其它任何输入（非 ``str``、空串、组数不对、超范围、含非法字符）一律抛 ``ValueError``。
    """
    if not isinstance(text, str):
        raise ValueError(f"parse_interval() 需要 str，实际为 {type(text).__name__}")

    parts = text.split(":")
    if len(parts) == 2:
        minutes = _parse_field(parts[0], "MM", 1, 2, max_value=59)
        seconds = _parse_field(parts[1], "SS", 1, 2, max_value=59)
        return minutes * 60 + seconds
    if len(parts) == 3:
        hours = _parse_field(parts[0], "HH", 1, 5)
        minutes = _parse_field(parts[1], "MM", 1, 2, max_value=59)
        seconds = _parse_field(parts[2], "SS", 1, 2, max_value=59)
        return hours * 3600 + minutes * 60 + seconds

    raise ValueError(f"时长文本必须形如 MM:SS 或 HH:MM:SS，实际为 {text!r}")


def format_interval(total_seconds: int) -> str:
    """把总秒数格式化成 ``HH:MM:SS``。

    小时位至少 2 位，超过 99 小时按实际位数输出；分钟与秒恰好 2 位。
    ``total_seconds`` 为负数或类型不是 ``int``（``bool``、``float`` 也算不是）时
    抛 ``ValueError``。
    """
    if isinstance(total_seconds, bool) or not isinstance(total_seconds, int):
        raise ValueError(
            f"format_interval() 需要 int，实际为 {type(total_seconds).__name__}"
        )
    if total_seconds < 0:
        raise ValueError(f"总秒数不能为负，实际为 {total_seconds}")

    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

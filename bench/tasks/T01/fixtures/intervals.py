"""时长处理模块（当前实现有缺陷，待修）。"""


def parse_interval(text):
    """把时长文本解析成总秒数。"""
    parts = text.split(":")
    minutes = int(parts[0])
    seconds = int(parts[1])
    return minutes * 60 + seconds


def format_interval(total_seconds):
    """把总秒数格式化成 HH:MM:SS。"""
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

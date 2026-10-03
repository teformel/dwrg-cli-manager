"""日期时间、时长与相对时间的本地化格式化。

本模块只依赖标准库，不引入第三方本地化库：中文（``zh-*``）走中文命名格式，
其余语言统一走英文命名格式，从而保证同一时刻在中英文环境下输出明显不同。

``format_duration`` 与 ``format_relative_time`` 不接受 ``language`` 参数，
统一读取 :func:`dwrg_manager.i18n.translator.get_translator` 的当前语言。
"""

from datetime import date, datetime

from .translator import get_translator

__all__ = [
    "format_date",
    "format_datetime",
    "format_duration",
    "format_relative_time",
    "format_time",
]

#: ``format_datetime`` 支持的格式名，非法取值一律退回 ``medium``。
_VALID_DATE_FORMATS: tuple[str, ...] = ("short", "medium", "long", "iso")

_EN_MONTHS_ABBR: tuple[str, ...] = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)

_EN_MONTHS_FULL: tuple[str, ...] = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)

_ZH_DURATION_UNITS: dict[str, str] = {
    "second": "秒",
    "minute": "分钟",
    "hour": "小时",
    "day": "天",
    "month": "个月",
    "year": "年",
}

_SECONDS_PER_MINUTE = 60
_SECONDS_PER_HOUR = 3600
_SECONDS_PER_DAY = 86400
_SECONDS_PER_MONTH = 86400 * 30
_SECONDS_PER_YEAR = 86400 * 365


def _resolve_language(language: str | None) -> str:
    """确定实际使用的语言。

    Args:
        language: 显式语言；``None`` 时读取全局翻译器当前语言。

    Returns:
        生效的语言代码。
    """
    return language if language is not None else get_translator().language


def _is_chinese(language: str) -> bool:
    """判断语言是否使用中文格式。

    Args:
        language: 语言代码。

    Returns:
        ``True`` 表示 ``zh-*`` 语言。
    """
    return language.lower().startswith("zh")


def _time12(value: datetime, seconds: bool = False) -> str:
    """把 24 小时制时间格式化为英文 12 小时制。

    Args:
        value: 待格式化的时间。
        seconds: 是否包含秒。

    Returns:
        形如 ``7:45 PM`` 或 ``7:45:30 PM`` 的字符串。
    """
    hour = value.hour % 12 or 12
    meridiem = "AM" if value.hour < 12 else "PM"
    if seconds:
        return f"{hour}:{value.minute:02d}:{value.second:02d} {meridiem}"
    return f"{hour}:{value.minute:02d} {meridiem}"


def format_datetime(
    value: datetime, fmt: str = "medium", language: str | None = None
) -> str:
    """按指定格式与语言格式化日期时间。

    Args:
        value: 待格式化的 :class:`~datetime.datetime`。
        fmt: 格式名，取值 ``short`` / ``medium`` / ``long`` / ``iso``；
            非法取值退回 ``medium``。
        language: 目标语言；``None`` 时读取全局翻译器当前语言。

    Returns:
        格式化后的字符串。``short``/``medium``/``long`` 为本地化格式，
        ``iso`` 恒为 :meth:`datetime.isoformat`。

    Example:
        >>> format_datetime(datetime(2026, 10, 3, 19, 45), language="zh-CN")
        '2026年10月03日 19:45'
        >>> format_datetime(datetime(2026, 10, 3, 19, 45), language="en-US")
        'Oct 3, 2026 7:45 PM'
    """
    if fmt not in _VALID_DATE_FORMATS:
        fmt = "medium"
    if fmt == "iso":
        return value.isoformat()
    lang = _resolve_language(language)
    if _is_chinese(lang):
        if fmt == "short":
            return value.strftime("%Y-%m-%d %H:%M")
        if fmt == "long":
            return value.strftime("%Y年%m月%d日 %H:%M:%S")
        return value.strftime("%Y年%m月%d日 %H:%M")
    month_abbr = _EN_MONTHS_ABBR[value.month - 1]
    if fmt == "short":
        return f"{value.month}/{value.day}/{value.year} {_time12(value)}"
    if fmt == "long":
        month_full = _EN_MONTHS_FULL[value.month - 1]
        return f"{month_full} {value.day}, {value.year} {_time12(value, seconds=True)}"
    return f"{month_abbr} {value.day}, {value.year} {_time12(value)}"


def format_date(value: date | datetime, language: str | None = None) -> str:
    """按语言格式化日期（不含时间）。

    Args:
        value: :class:`~datetime.date` 或 :class:`~datetime.datetime`。
        language: 目标语言；``None`` 时读取全局翻译器当前语言。

    Returns:
        本地化日期字符串。

    Example:
        >>> format_date(date(2026, 10, 3), language="zh-CN")
        '2026年10月03日'
        >>> format_date(date(2026, 10, 3), language="en-US")
        'Oct 3, 2026'
    """
    day = value.date() if isinstance(value, datetime) else value
    lang = _resolve_language(language)
    if _is_chinese(lang):
        return f"{day.year}年{day.month:02d}月{day.day:02d}日"
    return f"{_EN_MONTHS_ABBR[day.month - 1]} {day.day}, {day.year}"


def format_time(value: datetime, language: str | None = None) -> str:
    """按语言格式化时间（含秒）。

    Args:
        value: 待格式化的时间。
        language: 目标语言；``None`` 时读取全局翻译器当前语言。

    Returns:
        本地化时间字符串。

    Example:
        >>> format_time(datetime(2026, 10, 3, 19, 45, 30), language="zh-CN")
        '19:45:30'
        >>> format_time(datetime(2026, 10, 3, 19, 45, 30), language="en-US")
        '7:45:30 PM'
    """
    lang = _resolve_language(language)
    if _is_chinese(lang):
        return value.strftime("%H:%M:%S")
    return _time12(value, seconds=True)


def format_duration(seconds: float) -> str:
    """按当前语言把秒数格式化为易读时长。

    Args:
        seconds: 时长（秒）。负数按 0 处理。

    Returns:
        本地化时长字符串，例如中文 ``1小时2分3秒``、英文 ``1h 2m 3s``。

    Example:
        >>> format_duration(3723)
        '1小时2分3秒'
    """
    language = get_translator().language
    total = int(seconds)
    if total < 0:
        total = 0
    hours, remainder = divmod(total, _SECONDS_PER_HOUR)
    minutes, secs = divmod(remainder, _SECONDS_PER_MINUTE)
    if _is_chinese(language):
        parts: list[str] = []
        if hours:
            parts.append(f"{hours}小时")
        if minutes:
            parts.append(f"{minutes}分")
        if secs or not parts:
            parts.append(f"{secs}秒")
        return "".join(parts)
    parts_en: list[str] = []
    if hours:
        parts_en.append(f"{hours}h")
    if minutes:
        parts_en.append(f"{minutes}m")
    if secs or not parts_en:
        parts_en.append(f"{secs}s")
    return " ".join(parts_en)


def _align_now(value: datetime, now: datetime | None) -> datetime:
    """对齐 ``now`` 与 ``value`` 的时区信息，避免相减报错。

    Args:
        value: 参考时间点。
        now: 显式基准时间；``None`` 时按 ``value`` 的时区取当前时间。

    Returns:
        与 ``value`` 时区信息一致的基准时间。
    """
    if now is None:
        if value.tzinfo is not None:
            return datetime.now(tz=value.tzinfo)
        return datetime.now()
    if value.tzinfo is None and now.tzinfo is not None:
        return now.replace(tzinfo=None)
    if value.tzinfo is not None and now.tzinfo is None:
        return now.replace(tzinfo=value.tzinfo)
    return now


def _relative_label(language: str, count: int, unit: str, future: bool) -> str:
    """组装一条相对时间文案。

    Args:
        language: 目标语言。
        count: 数量。
        unit: 单位标识，取值见 :data:`_ZH_DURATION_UNITS`。
        future: 是否为将来（``True``）还是过去（``False``）。

    Returns:
        本地化相对时间字符串。
    """
    if _is_chinese(language):
        suffix = "后" if future else "前"
        return f"{count}{_ZH_DURATION_UNITS[unit]}{suffix}"
    noun = unit if count == 1 else f"{unit}s"
    if future:
        return f"in {count} {noun}"
    return f"{count} {noun} ago"


def format_relative_time(value: datetime, now: datetime | None = None) -> str:
    """按当前语言把时间点格式化为相对时间。

    Args:
        value: 目标时间点。
        now: 基准时间；``None`` 时取当前时间。

    Returns:
        本地化相对时间字符串，例如中文 ``3分钟前``、英文 ``3 minutes ago``。

    Example:
        >>> format_relative_time(datetime(2026, 10, 3, 19, 42), datetime(2026, 10, 3, 19, 45))
        '3分钟前'
    """
    language = get_translator().language
    reference = _align_now(value, now)
    delta_seconds = (reference - value).total_seconds()
    future = delta_seconds < 0
    seconds = abs(delta_seconds)
    if seconds < 10 and not future:
        return "刚刚" if _is_chinese(language) else "just now"
    if seconds < _SECONDS_PER_MINUTE:
        count, unit = int(seconds), "second"
    elif seconds < _SECONDS_PER_HOUR:
        count, unit = int(seconds // _SECONDS_PER_MINUTE), "minute"
    elif seconds < _SECONDS_PER_DAY:
        count, unit = int(seconds // _SECONDS_PER_HOUR), "hour"
    elif seconds < _SECONDS_PER_MONTH:
        count, unit = int(seconds // _SECONDS_PER_DAY), "day"
    elif seconds < _SECONDS_PER_YEAR:
        count, unit = int(seconds // _SECONDS_PER_MONTH), "month"
    else:
        count, unit = int(seconds // _SECONDS_PER_YEAR), "year"
    return _relative_label(language, count, unit, future)

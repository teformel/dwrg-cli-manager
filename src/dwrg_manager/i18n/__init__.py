"""国际化（i18n）支持。

对外暴露三类能力：

* 翻译器与进程级便捷函数：:class:`Translator`、:func:`t`、
  :func:`set_language`、:func:`get_translator`；
* 日期时间本地化：:func:`format_datetime`、:func:`format_date`、
  :func:`format_time`；
* 时长与相对时间本地化：:func:`format_duration`、:func:`format_relative_time`。

Example:
    >>> from dwrg_manager.i18n import t, set_language
    >>> set_language("en-US")
    >>> t("cli.app.help")
    'Manage multiple channels and accounts for Identity V'
"""

from .datetime_utils import (
    format_date,
    format_datetime,
    format_duration,
    format_relative_time,
    format_time,
)
from .translator import Translator, get_translator, set_language, t

__all__ = [
    "Translator",
    "format_date",
    "format_datetime",
    "format_duration",
    "format_relative_time",
    "format_time",
    "get_translator",
    "set_language",
    "t",
]

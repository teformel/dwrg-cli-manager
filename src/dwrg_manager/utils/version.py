"""
版本信息

版本号的唯一来源是包根 ``dwrg_manager.__version__``，本模块只做惰性转发，
避免同一版本号出现两份定义而长期失步。
"""


def get_version() -> str:
    """获取当前应用版本号。

    Returns:
        语义化版本号字符串，例如 ``"1.0.0"``。

    Example:
        >>> get_version()  # doctest: +SKIP
        '1.0.0'
    """
    from .. import __version__

    return __version__


__all__ = ["get_version"]

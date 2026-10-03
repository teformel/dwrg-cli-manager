"""
第五人格命令行管理器

这是一个用于管理第五人格游戏多渠道服与多账号的命令行工具。

Example:
    >>> import dwrg_manager  # doctest: +SKIP
    >>> dwrg_manager.__version__  # doctest: +SKIP
    '1.0.0'
"""

__version__ = "1.0.0"
__author__ = "DWRG Team"
__email__ = "team@dwrg.com"


def get_app() -> object:
    """惰性获取 Typer 应用实例。

    延迟导入可避免 ``import dwrg_manager`` 时加载全部子命令与可选依赖。

    Returns:
        :class:`typer.Typer` 应用对象。
    """
    from .cli import app

    return app


__all__ = ["__version__", "__author__", "__email__", "get_app"]

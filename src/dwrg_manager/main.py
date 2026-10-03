"""
主入口文件

Typer 应用的唯一定义处位于 :mod:`dwrg_manager.cli`；本模块仅作为 ``dwrg``
控制台脚本的入口，对应 ``pyproject.toml`` 中的::

    [project.scripts]
    dwrg = "dwrg_manager.main:app"
"""

from .cli import app

__all__ = ["app"]

if __name__ == "__main__":  # pragma: no cover
    app()

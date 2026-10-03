"""插件系统。

对外导出插件基类、运行时上下文协议、管理器与数据模型。
"""

from .base import Plugin, PluginContext
from .manager import PluginManager
from .models import PluginMeta, PluginState

__all__ = [
    "Plugin",
    "PluginContext",
    "PluginManager",
    "PluginMeta",
    "PluginState",
]

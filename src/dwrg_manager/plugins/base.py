"""插件基类与运行时上下文协议。"""

from abc import ABC, abstractmethod
from typing import Any, Protocol

from .models import PluginMeta, PluginState


class PluginContext(Protocol):
    """插件运行时上下文（最小接口）。

    只暴露插件必需的能力，避免插件反向依赖管理器内部实现。
    """

    def get_config(self) -> dict[str, Any]:
        """获取当前插件的配置字典。"""
        ...

    def log(self, level: str, message: str) -> None:
        """以指定级别写入一条日志。

        Args:
            level: 日志级别名，例如 ``"info"`` / ``"warning"`` / ``"error"``。
            message: 日志正文。
        """
        ...


class Plugin(ABC):
    """插件基类。

    子类必须提供 ``name`` / ``version`` 类属性，并实现 :meth:`on_enable`。

    Attributes:
        name: 插件唯一名，须满足 ``[A-Za-z0-9_-]+``。
        version: 插件版本，须符合 ``x.y.z``。
        description: 插件简介。
        author: 插件作者。

    Example:
        >>> class Demo(Plugin):
        ...     name = "demo"
        ...     def on_enable(self) -> None:
        ...         pass
    """

    name: str = ""
    version: str = "0.1.0"
    description: str = ""
    author: str = ""

    def __init__(self, context: PluginContext | None = None) -> None:
        """初始化插件实例。

        Args:
            context: 插件运行时上下文；为 ``None`` 时表示无上下文。
        """
        self.context: PluginContext | None = context

    @abstractmethod
    def on_enable(self) -> None:
        """插件被启用时调用。子类必须实现。"""
        raise NotImplementedError

    def on_disable(self) -> None:  # noqa: B027
        """插件被禁用时调用。默认空实现。"""

    def on_load(self) -> None:  # noqa: B027
        """插件被加载时调用。默认空实现。"""

    def info(self) -> PluginMeta:
        """返回本插件的元数据。

        Returns:
            根据类属性构造的 :class:`PluginMeta`；能实例化即说明已成功加载，
            因此 ``state`` 默认为 :attr:`PluginState.LOADED`。
        """
        return PluginMeta(
            name=self.name,
            version=self.version,
            description=self.description,
            author=self.author,
            state=PluginState.LOADED,
        )

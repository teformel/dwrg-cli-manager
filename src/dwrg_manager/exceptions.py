"""
统一异常体系

按 Vibe Coding 规范，所有对外抛出的异常都派生自 :class:`DWRGError`，
便于 CLI 层统一捕获并输出用户友好的错误信息，同时避免把底层异常细节
（例如 ``sqlite3`` / ``requests`` 的内部错误）直接暴露给用户。
"""

from typing import Any


class DWRGError(Exception):
    """所有 dwrg 业务异常的基类。

    Args:
        message: 面向用户的错误描述。
        details: 可选的补充上下文，仅用于日志与调试输出。
    """

    #: 面向用户的默认前缀
    prefix = "错误"

    def __init__(self, message: str, /, **details: Any) -> None:
        super().__init__(message)
        self.message = message
        self.details = details

    def __str__(self) -> str:
        if not self.details:
            return self.message
        extra = ", ".join(f"{k}={v!r}" for k, v in self.details.items())
        return f"{self.message} ({extra})"

    def user_message(self) -> str:
        """返回可直接展示给用户的单行信息。

        Returns:
            形如 ``错误: 配置文件无法解析`` 的字符串。
        """
        return f"{self.prefix}: {self.message}"


class ConfigError(DWRGError):
    """配置读写相关异常。"""

    prefix = "配置错误"


class AccountError(DWRGError):
    """账号管理相关异常。"""

    prefix = "账号错误"


class ServerError(DWRGError):
    """渠道服管理相关异常。"""

    prefix = "渠道服错误"


class ResourceError(DWRGError):
    """游戏资源下载与校验相关异常。"""

    prefix = "资源错误"


class LaunchError(DWRGError):
    """游戏启动与进程管理相关异常。"""

    prefix = "启动错误"


class PluginError(DWRGError):
    """插件加载与执行相关异常。"""

    prefix = "插件错误"


class SecurityError(DWRGError):
    """加密、密钥与权限相关异常。"""

    prefix = "安全错误"


class ValidationError(DWRGError):
    """输入校验失败。

    Args:
        message: 校验失败的描述。
        field: 校验失败的字段名（可选）。
    """

    prefix = "参数错误"

    def __init__(
        self, message: str, /, field: str | None = None, **details: Any
    ) -> None:
        if field:
            message = f"{field}: {message}"
        super().__init__(message, **details)
        self.field = field


__all__ = [
    "DWRGError",
    "ConfigError",
    "AccountError",
    "ServerError",
    "ResourceError",
    "LaunchError",
    "PluginError",
    "SecurityError",
    "ValidationError",
]

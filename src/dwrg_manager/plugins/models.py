"""插件系统的数据模型与名称/版本校验工具。"""

import re
from enum import Enum

from pydantic import BaseModel, ConfigDict, field_validator

from ..exceptions import ValidationError

#: 合法插件名的正则：仅允许字母、数字、下划线与连字符。
PLUGIN_NAME_RE: re.Pattern[str] = re.compile(r"^[A-Za-z0-9_-]+$")

#: 合法版本号的正则：形如 ``x.y.z``。
VERSION_RE: re.Pattern[str] = re.compile(r"^\d+\.\d+\.\d+$")


class PluginState(str, Enum):
    """插件生命周期状态。

    Attributes:
        DISCOVERED: 已被扫描发现，但尚未加载。
        LOADED: 已成功加载进内存。
        ENABLED: 已加载且被启用。
        DISABLED: 已被显式禁用。
        ERROR: 加载或启用过程中发生错误。
    """

    DISCOVERED = "discovered"
    LOADED = "loaded"
    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"


def validate_plugin_name(name: str) -> str:
    """校验插件名是否符合命名规范。

    插件名仅允许字母、数字、下划线与连字符，即匹配 ``[A-Za-z0-9_-]+``。

    Args:
        name: 待校验的插件名。

    Returns:
        校验通过时原样返回插件名。

    Raises:
        ValidationError: 插件名为空或包含非法字符。

    Example:
        >>> validate_plugin_name("my-plugin")
        'my-plugin'
    """
    if not name or not PLUGIN_NAME_RE.fullmatch(name):
        raise ValidationError(f"非法插件名: {name!r}，仅允许字母、数字、下划线与连字符")
    return name


class PluginMeta(BaseModel):
    """插件元数据。

    Attributes:
        name: 插件唯一名，仅允许 ``[A-Za-z0-9_-]``。
        version: 插件版本，需符合 ``x.y.z``。
        description: 插件简介。
        author: 插件作者。
        enabled: 是否已启用。
        state: 插件当前状态。
        path: 插件目录或 ``.py`` 文件路径。
        entry_point: 入口点，形如 ``"module:Class"``。
        error: 加载失败原因；成功时为 ``None``。
    """

    model_config = ConfigDict(validate_assignment=True)

    name: str
    version: str = "0.1.0"
    description: str = ""
    author: str = ""
    enabled: bool = False
    state: PluginState = PluginState.DISCOVERED
    path: str = ""
    entry_point: str = ""
    error: str | None = None

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        """校验插件名结构，非法时抛出 :class:`ValidationError`。"""
        return validate_plugin_name(value)

    @field_validator("version")
    @classmethod
    def _validate_version(cls, value: str) -> str:
        """校验版本号是否符合 ``x.y.z``。"""
        if not VERSION_RE.fullmatch(value):
            raise ValidationError(f"非法版本号: {value!r}，需符合 x.y.z")
        return value

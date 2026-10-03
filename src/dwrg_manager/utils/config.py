"""
配置工具（轻量级 YAML 读写）

仅用于读取/写入零散的 YAML 配置片段。结构化的应用配置请使用
:class:`dwrg_manager.config.manager.ConfigManager`。
"""

from pathlib import Path
from typing import Any

import yaml

from ..exceptions import ConfigError

#: 默认配置目录
DEFAULT_CONFIG_DIR = Path.home() / ".config" / "dwrg"

#: 默认配置文件
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.yaml"


def default_config_path() -> Path:
    """返回默认配置文件路径。

    Returns:
        ``~/.config/dwrg/config.yaml``。
    """
    return DEFAULT_CONFIG_FILE


def load_config(config_path: str | Path | None = None) -> dict[str, Any]:
    """加载 YAML 配置文件。

    Args:
        config_path: 配置文件路径；为 ``None`` 时使用默认路径。

    Returns:
        解析后的字典；文件不存在或内容为空时返回空字典。

    Raises:
        ConfigError: 文件存在但无法解析。
    """
    target = Path(config_path).expanduser() if config_path else DEFAULT_CONFIG_FILE
    if not target.exists():
        return {}
    try:
        with open(target, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(
            "配置文件解析失败", path=str(target), reason=str(exc)
        ) from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigError("配置文件根节点必须是映射", path=str(target))
    return data


def save_config(data: dict[str, Any], config_path: str | Path | None = None) -> Path:
    """把字典写入 YAML 配置文件。

    Args:
        data: 待写入的配置字典。
        config_path: 目标路径；为 ``None`` 时使用默认路径。

    Returns:
        实际写入的文件路径。

    Raises:
        ConfigError: 写入失败。
    """
    target = Path(config_path).expanduser() if config_path else DEFAULT_CONFIG_FILE
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as fh:
            yaml.safe_dump(data, fh, default_flow_style=False, allow_unicode=True)
    except OSError as exc:
        raise ConfigError("配置写入失败", path=str(target), reason=str(exc)) from exc
    return target


__all__ = [
    "DEFAULT_CONFIG_DIR",
    "DEFAULT_CONFIG_FILE",
    "default_config_path",
    "load_config",
    "save_config",
]

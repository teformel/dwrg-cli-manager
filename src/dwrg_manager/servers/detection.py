"""
渠道服检测工具（向后兼容再导出层）

实现已迁移至 :mod:`dwrg_manager.utils.network`，此处保留模块名以避免
破坏既有导入路径。
"""

from ..utils.network import (
    DEFAULT_TIMEOUT,
    check_server_status,
    detect_game_version,
    detect_server_region,
    fetch_json,
    ping_server,
)

__all__ = [
    "DEFAULT_TIMEOUT",
    "check_server_status",
    "detect_game_version",
    "detect_server_region",
    "fetch_json",
    "ping_server",
]

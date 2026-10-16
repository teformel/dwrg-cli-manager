"""
启动管理模块

对外暴露启动管理器与启动领域的数据模型。新增的 :class:`LaunchPlan``
（dry-run 计划）与 :class:`LaunchCheck`` / :class:`CheckItem``
（启动前检查）同样从这里导出，便于 CLI 直接引用。
"""

from .manager import LauncherManager
from .models import (
    CheckItem,
    GameStatus,
    LaunchCheck,
    LaunchConfig,
    LaunchPlan,
    LaunchResult,
)

__all__ = [
    "CheckItem",
    "GameStatus",
    "LaunchCheck",
    "LaunchConfig",
    "LaunchPlan",
    "LaunchResult",
    "LauncherManager",
]

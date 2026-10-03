"""
工具模块

收敛项目通用能力：日志、网络探测、系统信息、版本号与配置读写。
加密相关能力已迁移至 :mod:`dwrg_manager.security`，
``utils.crypto`` / ``utils.security`` 仅保留向后兼容的再导出。
"""

from .config import load_config, save_config
from .logger import get_logger, setup_logging
from .version import get_version

__all__ = [
    "setup_logging",
    "get_logger",
    "get_version",
    "load_config",
    "save_config",
]

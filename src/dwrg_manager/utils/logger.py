"""
日志工具

提供统一的日志初始化与获取入口。采用标准库 :mod:`logging`（不额外引入
第三方依赖），并在需要时挂载按大小滚动的文件处理器。

典型用法::

    from dwrg_manager.utils.logger import setup_logging, get_logger

    setup_logging(level="DEBUG")
    logger = get_logger(__name__)
    logger.info("账号管理器初始化完成")
"""

import logging
import logging.handlers
import sys
from pathlib import Path

#: 日志器名称前缀，便于集中控制
ROOT_LOGGER_NAME = "dwrg"

#: 日志输出格式
LOG_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s"
)

#: 时间格式
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

#: 单文件最大字节数（5 MiB）
MAX_LOG_BYTES = 5 * 1024 * 1024

#: 保留的历史日志文件数量
LOG_BACKUP_COUNT = 5

#: 默认日志目录
DEFAULT_LOG_DIR = Path.home() / ".dwrg" / "logs"

_configured = False


def default_log_file() -> Path:
    """返回默认日志文件路径。

    Returns:
        ``~/.dwrg/logs/dwrg.log``。
    """
    return DEFAULT_LOG_DIR / "dwrg.log"


def setup_logging(
    level: str = "INFO",
    log_file: str | Path | None = None,
    console: bool = False,
    *,
    force: bool = False,
) -> logging.Logger:
    """初始化 ``dwrg`` 日志器。

    重复调用是幂等的，只有 ``force=True`` 时才会重建处理器。

    Args:
        level: 根日志器级别名称，例如 ``INFO`` / ``DEBUG``。
        log_file: 日志文件路径；为 ``None`` 时使用 :func:`default_log_file`。
            传入空字符串则完全关闭文件日志。
        console: 是否把日志输出到标准错误。**默认关闭**——CLI 面向用户的输出
            由 Rich 负责，日志只落文件，避免二者互相干扰；``--verbose``
            会显式打开它。
        force: 是否强制重建处理器。

    Returns:
        配置完成的 :class:`logging.Logger` 实例。
    """
    global _configured

    logger = logging.getLogger(ROOT_LOGGER_NAME)
    if _configured and not force:
        return logger

    logger.setLevel(getattr(logging, str(level).upper(), logging.INFO))
    logger.propagate = False
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    if console:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(
            logging.DEBUG if str(level).upper() == "DEBUG" else logging.INFO
        )
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    if log_file != "":
        target = Path(log_file) if log_file else default_log_file()
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.handlers.RotatingFileHandler(
                target,
                maxBytes=MAX_LOG_BYTES,
                backupCount=LOG_BACKUP_COUNT,
                encoding="utf-8",
            )
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except OSError as exc:  # pragma: no cover - 依赖文件系统权限
            logger.warning("无法创建日志文件 %s: %s", target, exc)

    _configured = True
    return logger


def get_logger(name: str = ROOT_LOGGER_NAME) -> logging.Logger:
    """获取日志器。

    Args:
        name: 日志器名称，通常传入 ``__name__``。

    Returns:
        对应的 :class:`logging.Logger`。若根日志器尚未配置，则返回带有
        默认配置的实例，保证任何模块单独导入时也能安全地记录日志。
    """
    if not _configured and not logging.getLogger(ROOT_LOGGER_NAME).handlers:
        setup_logging()
    return logging.getLogger(name)


__all__ = ["setup_logging", "get_logger", "default_log_file", "ROOT_LOGGER_NAME"]

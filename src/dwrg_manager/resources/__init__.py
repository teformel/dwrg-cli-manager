"""
资源管理包

对外暴露资源管理器及其下载 / 校验 / 补丁组件、索引传输层与数据模型。
"""

from .downloader import Downloader, DownloadError
from .manager import ResourceManager
from .models import (
    DownloadResult,
    DownloadTask,
    ManifestTransport,
    PatchPlan,
    PatchResult,
    ProgressCallback,
    ResourceCheckResult,
    ResourceFile,
    ResourceManifest,
    ResourceServer,
    ResourceUpdateResult,
)
from .patcher import Patcher
from .transports import HttpIndexTransport, LocalIndexTransport
from .validator import Validator

__all__ = [
    "DownloadError",
    "DownloadResult",
    "DownloadTask",
    "Downloader",
    "HttpIndexTransport",
    "LocalIndexTransport",
    "ManifestTransport",
    "PatchPlan",
    "PatchResult",
    "Patcher",
    "ProgressCallback",
    "ResourceCheckResult",
    "ResourceFile",
    "ResourceManager",
    "ResourceManifest",
    "ResourceServer",
    "ResourceUpdateResult",
    "Validator",
]

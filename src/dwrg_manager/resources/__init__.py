"""
资源管理包

对外暴露资源管理器及其下载 / 校验 / 补丁组件与数据模型。
"""

from .downloader import Downloader, DownloadError
from .manager import AiohttpManifestTransport, ResourceManager
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
from .validator import Validator

__all__ = [
    "AiohttpManifestTransport",
    "DownloadError",
    "DownloadResult",
    "DownloadTask",
    "Downloader",
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

"""
资源数据模型

本模块集中定义资源管理领域（清单、文件、检查/更新结果）以及
``downloader`` / ``patcher`` 子模块所需的传输与结果模型，
避免各子模块各自复制一份结构体。
"""

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field


class ResourceFile(BaseModel):
    """资源文件模型。

    Attributes:
        name: 文件名（用于拼接下载 URL）。
        path: 文件相对路径（作为文件身份标识与落盘位置）。
        size: 文件大小（字节）。
        md5: 整文件 MD5 哈希值。
        version: 该文件所属版本号。
        is_optional: 是否为可选文件。
        last_modified: 最后修改时间。
        partial_hash: 清单可选的抽样哈希，用于快速校验；缺失时只能全量校验。
        sha256: 整文件 SHA256 哈希值（可选）。
    """

    model_config = ConfigDict(validate_assignment=True)

    name: str = Field(..., description="文件名")
    path: str = Field(..., description="文件相对路径")
    size: int = Field(..., description="文件大小(字节)")
    md5: str = Field(..., description="整文件 MD5 哈希值")
    version: str = Field(..., description="版本号")
    is_optional: bool = Field(False, description="是否为可选文件")
    last_modified: datetime = Field(
        default_factory=datetime.now, description="最后修改时间"
    )
    partial_hash: str | None = Field(
        None, description="抽样哈希（清单可选提供，用于快速校验）"
    )
    sha256: str | None = Field(None, description="整文件 SHA256 哈希值（可选）")


class ResourceCheckResult(BaseModel):
    """资源检查结果。"""

    total_files: int = Field(..., description="文件总数")
    healthy_files: int = Field(..., description="正常文件数")
    corrupted_files: int = Field(..., description="损坏文件数")
    missing_files: int = Field(..., description="缺失文件数")
    outdated_files: int = Field(0, description="过时文件数")
    scan_time: datetime = Field(default_factory=datetime.now, description="扫描时间")


class ResourceUpdateResult(BaseModel):
    """资源更新结果。"""

    success: bool = Field(..., description="是否成功")
    downloaded_files: int = Field(0, description="下载文件数")
    updated_files: int = Field(0, description="更新文件数")
    failed_files: list[str] = Field(default_factory=list, description="失败文件列表")
    error: str | None = Field(None, description="错误信息")
    total_size: int = Field(0, description="总下载大小(字节)")
    elapsed_time: float = Field(0.0, description="耗时(秒)")
    scan_time: datetime = Field(default_factory=datetime.now, description="扫描时间")


class ResourceServer(BaseModel):
    """资源服务器。"""

    name: str = Field(..., description="服务器名称")
    endpoint: str = Field(..., description="服务器地址")
    base_url: str = Field(..., description="基础URL")
    current_version: str = Field(..., description="当前版本")
    latest_version: str = Field(..., description="最新版本")
    is_available: bool = Field(True, description="是否可用")


class ResourceManifest(BaseModel):
    """资源清单。"""

    version: str = Field(..., description="版本号")
    files: list[ResourceFile] = Field(default_factory=list, description="文件列表")
    total_size: int = Field(..., description="总大小")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    download_url: str = Field(..., description="下载URL")


class DownloadTask(BaseModel):
    """单个下载任务描述。

    Attributes:
        url: 文件下载地址。
        dest: 最终落盘路径。
        name: 任务名（用于日志与进度，缺省取 ``dest.name``）。
        expected_size: 期望文件大小，用于下载后校验。
        expected_md5: 期望 MD5，用于下载后校验。
        resume: 是否允许断点续传。
    """

    url: str = Field(..., description="下载地址")
    dest: Path = Field(..., description="目标路径")
    name: str = Field("", description="任务名")
    expected_size: int | None = Field(None, description="期望大小(字节)")
    expected_md5: str | None = Field(None, description="期望MD5")
    resume: bool = Field(True, description="是否允许断点续传")


class DownloadResult(BaseModel):
    """单个下载任务的结果。"""

    url: str = Field(..., description="下载地址")
    dest: Path = Field(..., description="目标路径")
    success: bool = Field(..., description="是否成功")
    bytes_written: int = Field(0, description="实际写入字节数")
    attempts: int = Field(0, description="实际尝试次数")
    resumed: bool = Field(False, description="是否使用了断点续传")
    error: str | None = Field(None, description="错误信息")


#: 下载/补丁进度回调：每完成一个文件调用一次。
ProgressCallback = Callable[[DownloadResult], None]


class PatchPlan(BaseModel):
    """增量更新计划。

    以「本地清单」为旧状态、「远端清单」为新状态进行比对，
    区分新增 / 更新 / 删除 / 未变化四类文件。
    """

    download_url: str = Field(..., description="下载基础URL")
    remote_manifest: ResourceManifest = Field(..., description="远端目标清单")
    added: list[ResourceFile] = Field(default_factory=list, description="新增文件")
    updated: list[ResourceFile] = Field(default_factory=list, description="更新文件")
    removed: list[ResourceFile] = Field(default_factory=list, description="待删除文件")
    unchanged: list[ResourceFile] = Field(
        default_factory=list, description="未变化文件"
    )

    @property
    def is_empty(self) -> bool:
        """计划中是否没有任何下载或删除动作。

        Returns:
            当且仅当没有新增、更新、删除时为 ``True``。
        """
        return not self.added and not self.updated and not self.removed

    def files_to_download(self) -> list[ResourceFile]:
        """返回需要下载的文件列表（新增 + 更新）。

        Returns:
            需要下载的 :class:`ResourceFile` 列表，顺序为「新增在前、更新在后」。
        """
        return [*self.added, *self.updated]


class PatchResult(BaseModel):
    """增量更新执行结果。"""

    success: bool = Field(..., description="是否全部成功")
    added: int = Field(0, description="成功新增文件数")
    updated: int = Field(0, description="成功更新文件数")
    removed: int = Field(0, description="成功删除文件数")
    failed_files: list[str] = Field(default_factory=list, description="失败文件列表")
    results: list[DownloadResult] = Field(
        default_factory=list, description="各下载任务结果"
    )
    error: str | None = Field(None, description="错误信息")
    elapsed_time: float = Field(0.0, description="耗时(秒)")


@runtime_checkable
class ManifestTransport(Protocol):
    """资源清单提供者协议。

    默认实现 :class:`~dwrg_manager.resources.manager.AiohttpManifestTransport`
    走 aiohttp；测试可注入返回构造好的 :class:`ResourceManifest` 的假实现，
    从而完全避免真实网络访问。
    """

    async def fetch_manifest(self, server: ResourceServer) -> ResourceManifest | None:
        """获取指定服务器的最新资源清单。

        Args:
            server: 目标资源服务器。

        Returns:
            解析成功返回 :class:`ResourceManifest`，失败返回 ``None``。
        """
        ...

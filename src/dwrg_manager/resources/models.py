"""
资源数据模型
"""

from datetime import datetime

from pydantic import BaseModel, Field


class ResourceFile(BaseModel):
    """资源文件模型"""
    name: str = Field(..., description="文件名")
    path: str = Field(..., description="文件路径")
    size: int = Field(..., description="文件大小(字节)")
    md5: str = Field(..., description="MD5哈希值")
    version: str = Field(..., description="版本号")
    is_optional: bool = Field(False, description="是否为可选文件")
    last_modified: datetime = Field(default_factory=datetime.now, description="最后修改时间")


class ResourceCheckResult(BaseModel):
    """资源检查结果"""
    total_files: int = Field(..., description="文件总数")
    healthy_files: int = Field(..., description="正常文件数")
    corrupted_files: int = Field(..., description="损坏文件数")
    missing_files: int = Field(..., description="缺失文件数")
    outdated_files: int = Field(0, description="过时文件数")
    scan_time: datetime = Field(default_factory=datetime.now, description="扫描时间")


class ResourceUpdateResult(BaseModel):
    """资源更新结果"""
    success: bool = Field(..., description="是否成功")
    downloaded_files: int = Field(0, description="下载文件数")
    updated_files: int = Field(0, description="更新文件数")
    failed_files: list[str] = Field(default_factory=list, description="失败文件列表")
    error: str | None = Field(None, description="错误信息")
    total_size: int = Field(0, description="总下载大小(字节)")
    elapsed_time: float = Field(0.0, description="耗时(秒)")


class ResourceServer(BaseModel):
    """资源服务器"""
    name: str = Field(..., description="服务器名称")
    endpoint: str = Field(..., description="服务器地址")
    base_url: str = Field(..., description="基础URL")
    current_version: str = Field(..., description="当前版本")
    latest_version: str = Field(..., description="最新版本")
    is_available: bool = Field(True, description="是否可用")


class ResourceManifest(BaseModel):
    """资源清单"""
    version: str = Field(..., description="版本号")
    files: list[ResourceFile] = Field(default_factory=list, description="文件列表")
    total_size: int = Field(..., description="总大小")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    download_url: str = Field(..., description="下载URL")

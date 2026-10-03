"""
渠道服数据模型
"""

from datetime import datetime

from pydantic import BaseModel, Field


class ServerConfig(BaseModel):
    """渠道服配置模型"""
    name: str = Field(..., description="渠道服名称")
    endpoint: str = Field(..., description="服务器端点")
    region: str = Field("CN", description="地区")
    status: str = Field("active", description="状态")
    version: str = Field("1.0.0", description="版本")
    is_default: bool = Field(False, description="是否为默认服务器")
    last_check: datetime | None = Field(None, description="最后检查时间")
    ping: float | None = Field(None, description="延迟")
    players: int | None = Field(None, description="在线玩家数")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class ServerStatus(BaseModel):
    """渠道服状态模型"""
    name: str
    status: str
    version: str
    players: int
    ping: float
    last_check: datetime


class ServerManagerConfig(BaseModel):
    """渠道服管理器配置"""
    auto_detect: bool = Field(True, description="自动检测渠道服")
    check_interval: int = Field(300, description="检测间隔(秒)")
    timeout: int = Field(10, description="检测超时(秒)")
    preferred_servers: list = Field([], description="优先服务器列表")

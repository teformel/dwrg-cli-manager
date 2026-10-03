"""
渠道服数据模型

.. note::
   :class:`ServerConfig` 的唯一定义位于
   :mod:`dwrg_manager.config.models`，此处仅做再导出，避免同一概念出现
   两份字段不一致的定义（历史遗留问题）。
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from ..config.models import ServerConfig

__all__ = ["ServerConfig", "ServerManagerConfig", "ServerStatus"]


class ServerStatus(BaseModel):
    """一次渠道服状态探测的结果。"""

    model_config = ConfigDict(validate_assignment=True)

    name: str = Field(..., description="渠道服名称")
    status: str = Field(..., description="渠道服状态")
    version: str = Field("1.0.0", description="渠道服版本")
    players: int = Field(0, ge=0, description="在线玩家数")
    ping: float = Field(..., description="网络延迟(毫秒)")
    last_check: datetime = Field(default_factory=datetime.now, description="探测时间")


class ServerManagerConfig(BaseModel):
    """渠道服管理器的运行参数。"""

    model_config = ConfigDict(validate_assignment=True)

    auto_detect: bool = Field(True, description="自动检测渠道服")
    check_interval: int = Field(300, ge=10, description="检测间隔(秒)")
    timeout: int = Field(10, ge=1, description="检测超时(秒)")
    preferred_servers: list[str] = Field(
        default_factory=list, description="优先服务器列表"
    )

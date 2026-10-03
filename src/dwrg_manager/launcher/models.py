"""
启动管理数据模型
"""

from datetime import datetime

from pydantic import BaseModel, Field


class LaunchConfig(BaseModel):
    """启动配置"""
    account_id: str | None = Field(None, description="账号ID")
    server_name: str | None = Field(None, description="服务器名称")
    launch_params: list[str] = Field(default_factory=list, description="启动参数")
    working_dir: str = Field("", description="工作目录")
    env_vars: dict = Field(default_factory=dict, description="环境变量")
    is_admin: bool = Field(False, description="是否以管理员权限运行")
    auto_restart: bool = Field(False, description="是否自动重启")
    priority: str = Field("normal", description="优先级")

    @field_validator('priority')
    def validate_priority(cls, v):
        valid_priorities = ['low', 'normal', 'high', 'realtime']
        if v not in valid_priorities:
            raise ValueError(f'无效的优先级: {v}')
        return v


class LaunchResult(BaseModel):
    """启动结果"""
    success: bool = Field(..., description="是否成功")
    process_id: int | None = Field(None, description="进程ID")
    error_message: str | None = Field(None, description="错误信息")
    launch_time: datetime = Field(default_factory=datetime.now, description="启动时间")
    config: LaunchConfig = Field(..., description="启动配置")


class GameStatus(BaseModel):
    """游戏状态"""
    is_running: bool = Field(..., description="是否正在运行")
    process_id: int | None = Field(None, description="进程ID")
    cpu_usage: float = Field(0.0, description="CPU使用率")
    memory_usage: int = Field(0, description="内存使用量(字节)")
    running_time: float = Field(0.0, description="运行时间(秒)")
    launch_config: LaunchConfig | None = Field(None, description="启动配置")

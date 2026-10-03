"""
启动管理数据模型
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

#: 允许的进程优先级
PRIORITIES: tuple[str, ...] = ("low", "normal", "high", "realtime")


class LaunchConfig(BaseModel):
    """游戏启动配置。"""

    model_config = ConfigDict(validate_assignment=True)

    account_id: str | None = Field(None, description="账号ID")
    server_name: str | None = Field(None, description="渠道服名称")
    game_path: str = Field("", description="游戏可执行文件路径（为空时自动探测）")
    launch_params: list[str] = Field(default_factory=list, description="启动参数")
    working_dir: str = Field("", description="工作目录（为空时取游戏所在目录）")
    env_vars: dict[str, str] = Field(default_factory=dict, description="环境变量")
    is_admin: bool = Field(False, description="是否以管理员权限运行")
    auto_restart: bool = Field(False, description="是否自动重启")
    priority: str = Field("normal", description="优先级")

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        """校验优先级取值。

        Args:
            v: 待校验的优先级。

        Returns:
            小写规范化后的优先级。

        Raises:
            ValueError: 优先级不在 :data:`PRIORITIES` 之内。
        """
        value = v.lower()
        if value not in PRIORITIES:
            raise ValueError(f"无效的优先级: {v}，可用: {' / '.join(PRIORITIES)}")
        return value


class LaunchResult(BaseModel):
    """一次启动尝试的结果。"""

    success: bool = Field(..., description="是否成功")
    process_id: int | None = Field(None, description="进程ID")
    error_message: str | None = Field(None, description="错误信息")
    launch_time: datetime = Field(default_factory=datetime.now, description="启动时间")
    config: LaunchConfig | None = Field(None, description="启动配置")


class GameStatus(BaseModel):
    """游戏进程的运行状态。"""

    is_running: bool = Field(..., description="是否正在运行")
    process_id: int | None = Field(None, description="进程ID")
    cpu_usage: float = Field(0.0, description="CPU使用率(%)")
    memory_usage: int = Field(0, description="内存使用量(字节)")
    running_time: float = Field(0.0, description="运行时间(秒)")
    launch_config: LaunchConfig | None = Field(None, description="启动配置")


__all__ = ["GameStatus", "LaunchConfig", "LaunchResult", "PRIORITIES"]

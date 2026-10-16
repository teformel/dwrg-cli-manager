"""
启动管理数据模型

集中定义启动领域的三类模型：

* :class:`LaunchConfig` / :class:`LaunchResult` / :class:`GameStatus`：
  既有的一次启动尝试及其结果；
* :class:`LaunchPlan`：``dry-run`` 模式下「将要执行的命令行 + 环境变量 +
  工作目录」快照，只用于展示，不会真正拉起进程；
* :class:`LaunchCheck` / :class:`CheckItem`：启动前检查的结果，每一项都
  附带**可执行的修复建议**，便于用户直接照着做。
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

#: 允许的进程优先级
PRIORITIES: tuple[str, ...] = ("low", "normal", "high", "realtime")

#: 允许的画质档位（对标 ww 3.7 的 -krqlv 档位机制；IdentityV 用 -graphics=）
GRAPHICS_LEVELS: tuple[str, ...] = ("sd", "hd", "uhd")

#: 默认画质档位
DEFAULT_GRAPHICS_LEVEL = "hd"


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
    graphics: str = Field(DEFAULT_GRAPHICS_LEVEL, description="画质档位")

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

    @field_validator("graphics")
    @classmethod
    def validate_graphics(cls, v: str) -> str:
        """校验画质档位取值。

        Args:
            v: 待校验的画质档位字符串。

        Returns:
            小写规范化后的画质档位。

        Raises:
            ValueError: 档位不在 :data:`GRAPHICS_LEVELS` 之内。
        """
        value = v.strip().lower()
        if value not in GRAPHICS_LEVELS:
            raise ValueError(
                f"无效的画质档位: {v}，可用: {' / '.join(GRAPHICS_LEVELS)}"
            )
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


class LaunchPlan(BaseModel):
    """``dry-run`` 模式下将要执行的启动计划快照。

    该模型只承载「将要做什么」的信息：命令行、环境变量、工作目录与来源
    渠道服/账号；它不代表任何进程真的被启动过。
    """

    model_config = ConfigDict(validate_assignment=True)

    command: list[str] = Field(default_factory=list, description="将要执行的命令行")
    working_dir: str = Field("", description="工作目录")
    env_vars: dict[str, str] = Field(default_factory=dict, description="环境变量")
    account_id: str | None = Field(None, description="账号ID")
    server_name: str | None = Field(None, description="渠道服名称")
    game_path: str = Field("", description="游戏可执行文件路径")


class CheckItem(BaseModel):
    """启动前检查中的单项结果。

    Attributes:
        name: 检查项标识，例如 ``executable`` / ``disk_space``。
        passed: 是否通过。
        message: 面向用户的说明（失败时说明原因，成功时说明结论）。
        suggestion: 失败时给出的**可执行**修复建议；成功时为 ``None``。
    """

    model_config = ConfigDict(validate_assignment=True)

    name: str = Field(..., description="检查项标识")
    passed: bool = Field(..., description="是否通过")
    message: str = Field("", description="说明信息")
    suggestion: str | None = Field(None, description="修复建议")

    @property
    def ok(self) -> bool:
        """``passed`` 的语义化别名。

        Returns:
            检查是否通过。
        """
        return self.passed


class LaunchCheck(BaseModel):
    """一次完整的启动前检查结果。

    Attributes:
        items: 各检查项结果，按执行顺序排列。
        ready: 是否全部通过（即可安全启动）。
    """

    model_config = ConfigDict(validate_assignment=True)

    items: list[CheckItem] = Field(default_factory=list, description="检查项列表")
    ready: bool = Field(False, description="是否全部通过")

    @property
    def failures(self) -> list[CheckItem]:
        """返回所有未通过的检查项。

        Returns:
            失败的 :class:`CheckItem` 列表；全部通过时为空列表。
        """
        return [item for item in self.items if not item.passed]

    def add(self, item: CheckItem) -> None:
        """追加一个检查项并刷新 :attr:`ready``。

        Args:
            item: 待追加的检查项。
        """
        self.items.append(item)
        self.ready = not self.failures

    def to_dict(self) -> dict[str, object]:
        """导出为可 JSON 序列化的字典（供 ``--json`` 输出复用）。

        Returns:
            含 ``ready`` 与 ``items`` 的字典。
        """
        return {
            "ready": self.ready,
            "items": [
                {
                    "name": item.name,
                    "passed": item.passed,
                    "message": item.message,
                    "suggestion": item.suggestion,
                }
                for item in self.items
            ],
        }


__all__ = [
    "CheckItem",
    "DEFAULT_GRAPHICS_LEVEL",
    "GRAPHICS_LEVELS",
    "GameStatus",
    "LaunchCheck",
    "LaunchConfig",
    "LaunchPlan",
    "LaunchResult",
    "PRIORITIES",
]

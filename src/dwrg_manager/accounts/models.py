"""
账号数据模型

:class:`Account` 是账号在业务层的运行时视图；持久化形态见
:class:`dwrg_manager.config.models.AccountConfig`。
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..security.validation import (
    ACCOUNT_ID_MIN_LENGTH,
    validate_server_name,
    validate_username,
)


class Account(BaseModel):
    """账号运行时模型。"""

    model_config = ConfigDict(validate_assignment=True)

    id: str = Field(..., description="账号ID")
    username: str = Field(..., description="用户名")
    server: str = Field(..., description="渠道服")
    encrypted_password: str = Field(
        "", description="加密后的密码", exclude=True, repr=False
    )
    password_hash: str = Field("", description="密码哈希", exclude=True, repr=False)
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    last_login: datetime | None = Field(None, description="最后登录时间")
    is_current: bool = Field(False, description="是否为当前账号")

    @field_validator("id")
    @classmethod
    def _check_id(cls, v: str) -> str:
        """校验账号 ID 长度。

        Args:
            v: 待校验的账号 ID。

        Returns:
            去除首尾空白后的账号 ID。

        Raises:
            ValueError: 长度不足。
        """
        value = v.strip()
        if len(value) < ACCOUNT_ID_MIN_LENGTH:
            raise ValueError(f"账号ID长度不能少于{ACCOUNT_ID_MIN_LENGTH}个字符")
        return value

    @field_validator("username")
    @classmethod
    def _check_username(cls, v: str) -> str:
        """校验用户名。

        Args:
            v: 待校验的用户名。

        Returns:
            规范化后的用户名。

        Raises:
            ValueError: 用户名不满足命名规则。
        """
        try:
            return validate_username(v)
        except Exception as exc:
            raise ValueError(str(exc)) from exc

    @field_validator("server")
    @classmethod
    def _check_server(cls, v: str) -> str:
        """校验渠道服名称（仅做结构校验，存在性由管理器负责）。

        Args:
            v: 待校验的渠道服名称。

        Returns:
            规范化后的渠道服名称。

        Raises:
            ValueError: 渠道服名称非法。
        """
        try:
            return validate_server_name(v)
        except Exception as exc:
            raise ValueError(str(exc)) from exc

    def display_id(self, width: int = 8) -> str:
        """返回用于列表展示的短 ID。

        Args:
            width: 前缀保留的字符数。

        Returns:
            短 ID，超出长度时以 ``...`` 结尾。
        """
        return f"{self.id[:width]}..." if len(self.id) > width else self.id


class LoginResult(BaseModel):
    """一次账号登录（或模拟登录）的结果。"""

    success: bool = Field(..., description="是否登录成功")
    account_id: str = Field("", description="账号ID")
    username: str = Field("", description="用户名")
    server: str = Field("", description="渠道服")
    message: str = Field("", description="附加说明")
    timestamp: datetime = Field(default_factory=datetime.now, description="登录时间")


__all__ = ["Account", "LoginResult"]

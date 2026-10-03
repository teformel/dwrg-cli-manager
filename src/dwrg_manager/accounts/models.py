"""
账号数据模型
"""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class Account(BaseModel):
    """账号模型"""
    id: str = Field(..., description="账号ID")
    username: str = Field(..., description="用户名")
    server: str = Field(..., description="渠道服")
    encrypted_password: str = Field(..., description="加密后的密码")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    last_login: datetime | None = Field(None, description="最后登录时间")
    is_current: bool = Field(False, description="是否为当前账号")

    @field_validator('id')
    def validate_id(cls, v):
        if len(v) < 8:
            raise ValueError('账号ID长度不能少于8个字符')
        return v

    @field_validator('username')
    def validate_username(cls, v):
        """验证用户名"""
        if len(v) < 3 or len(v) > 20:
            raise ValueError("用户名长度必须在3-20字符之间")
        # 允许字母、数字和下划线
        if not all(c.isalnum() or c == '_' for c in v):
            raise ValueError("用户名只能包含字母、数字和下划线")
        return v.strip()

    @field_validator('server')
    def validate_server(cls, v):
        """验证渠道服"""
        valid_servers = ['official', 'bserver', 'test_server']
        if v not in valid_servers:
            raise ValueError(f"无效的渠道服: {v}")
        return v

"""
配置数据模型
"""

from datetime import datetime

from pydantic import BaseModel, Field, validator


class ServerConfig(BaseModel):
    """服务器配置"""
    name: str = Field(..., description="服务器名称")
    endpoint: str = Field(..., description="服务器地址")
    region: str = Field("CN", description="服务器地区")
    status: str = Field("active", description="服务器状态")
    version: str = Field("1.0.0", description="服务器版本")
    is_default: bool = Field(False, description="是否为默认服务器")

    @validator('status')
    def validate_status(cls, v):
        if v not in ['active', 'inactive', 'maintenance']:
            raise ValueError('状态必须是 active, inactive 或 maintenance')
        return v


class AccountConfig(BaseModel):
    """账号配置"""
    id: str = Field(..., description="账号ID")
    username: str = Field(..., description="用户名")
    server: str = Field(..., description="服务器名称")
    encrypted_password: str = Field(..., description="加密后的密码")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    last_login: datetime | None = Field(None, description="最后登录时间")
    is_current: bool = Field(False, description="是否为当前账号")

    @validator('id')
    def validate_id(cls, v):
        if len(v) < 8:
            raise ValueError('账号ID长度不能少于8个字符')
        return v


class AppConfig(BaseModel):
    """应用程序配置"""
    server: str = Field("official", description="当前服务器")
    account: str | None = Field(None, description="当前账号")
    auto_update: bool = Field(True, description="自动更新")
    verbose: bool = Field(False, description="详细输出")
    language: str = Field("zh-CN", description="语言")
    data_dir: str = Field("~/.dwrg", description="数据目录")
    cache_dir: str = Field("~/.dwrg/cache", description="缓存目录")
    log_level: str = Field("INFO", description="日志级别")
    max_concurrent_downloads: int = Field(5, description="最大并发下载数")
    download_timeout: int = Field(300, description="下载超时时间(秒)")

    @validator('language')
    def validate_language(cls, v):
        supported_languages = ['zh-CN', 'zh-TW', 'en-US', 'ja-JP', 'ko-KR', 'fr-FR', 'de-DE', 'es-ES', 'ru-RU']
        if v not in supported_languages:
            raise ValueError(f'不支持的语言: {v}')
        return v

    @validator('log_level')
    def validate_log_level(cls, v):
        levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v not in levels:
            raise ValueError(f'无效的日志级别: {v}')
        return v


class Config(BaseModel):
    """主配置类"""
    app: AppConfig = Field(default_factory=AppConfig)
    servers: dict[str, ServerConfig] = Field(default_factory=dict)
    accounts: dict[str, AccountConfig] = Field(default_factory=dict)

    def get_server(self, name: str) -> ServerConfig | None:
        """获取服务器配置"""
        return self.servers.get(name)

    def get_account(self, account_id: str) -> AccountConfig | None:
        """获取账号配置"""
        return self.accounts.get(account_id)

    def get_current_server(self) -> ServerConfig | None:
        """获取当前服务器配置"""
        if self.app.server:
            return self.servers.get(self.app.server)
        return None

    def get_current_account(self) -> AccountConfig | None:
        """获取当前账号配置"""
        if self.app.account:
            return self.accounts.get(self.app.account)
        return None

    def add_server(self, server: ServerConfig):
        """添加服务器配置"""
        self.servers[server.name] = server

    def add_account(self, account: AccountConfig):
        """添加账号配置"""
        self.accounts[account.id] = account

    def remove_server(self, name: str) -> bool:
        """删除服务器配置"""
        if name in self.servers:
            del self.servers[name]
            return True
        return False

    def remove_account(self, account_id: str) -> bool:
        """删除账号配置"""
        if account_id in self.accounts:
            del self.accounts[account_id]
            return True
        return False

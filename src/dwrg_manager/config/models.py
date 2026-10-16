"""
配置数据模型

本模块是配置领域的唯一数据模型定义处。``ServerConfig`` 同时被
:mod:`dwrg_manager.servers` 复用（见 ``servers/models.py`` 的再导出），
避免同一概念出现两份定义。
"""

import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

#: 渠道服名称允许的字符集（结构校验，供 security.validation 复用）
SERVER_NAME_PATTERN: re.Pattern[str] = re.compile(r"^[A-Za-z0-9_-]+$")

#: 支持的渠道服状态
SERVER_STATUSES: tuple[str, ...] = ("active", "inactive", "maintenance")

#: 支持的语言列表
SUPPORTED_LANGUAGES: tuple[str, ...] = (
    "zh-CN",
    "zh-TW",
    "en-US",
    "ja-JP",
    "ko-KR",
    "fr-FR",
    "de-DE",
    "es-ES",
    "ru-RU",
)

#: 支持的日志级别
LOG_LEVELS: tuple[str, ...] = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

#: 开箱即用的渠道服定义：(名称, 接口地址, 地区)
DEFAULT_SERVER_DEFINITIONS: tuple[tuple[str, str, str], ...] = (
    ("official", "https://idv.163.com", "CN"),
    ("bserver", "https://game.bilibili.com/idv", "CN"),
    ("test_server", "https://test.idv.163.com", "CN"),
)

#: 默认渠道服名称集合
DEFAULT_SERVER_NAMES: tuple[str, ...] = tuple(d[0] for d in DEFAULT_SERVER_DEFINITIONS)

#: 资源源名称允许的字符集（与渠道服一致，便于人工维护配置文件）
RESOURCE_SOURCE_NAME_PATTERN: re.Pattern[str] = re.compile(r"^[A-Za-z0-9_-]+$")

#: 开箱即用的资源源定义：(名称, 直链 URL, 渠道, 说明)
#:
#: 来自 2026-10-03 的实测记录（见 ``memory/resource-source-research.md``）：
#: 国际服（NeoX2 与旧包）直链可用且支持 ``Range``；NeoX2 包的 ETag 即整文件
#: MD5，旧包 ETag 带 ``-N`` 后缀（分片上传），此时不能当 MD5 使用。
#: 国服 PC 端公开直链已 403，因此不预置，需由用户自行配置覆盖。
DEFAULT_RESOURCE_SOURCE_DEFINITIONS: tuple[tuple[str, str, str, str], ...] = (
    (
        "oversea_neox2",
        "https://h55na.gdl.easebar.com/identityv_setup_neox2_oversea_release_240912.exe",
        "oversea",
        "国际服 NeoX2 完整包（ETag 即整文件 MD5，支持 Range 断点续传）",
    ),
    (
        "oversea_legacy",
        "https://h55na.gdl.easebar.com/identityv_setup_release_oversea.exe",
        "oversea",
        "国际服旧完整包（ETag 带 -N 后缀，不能当 MD5，只能校验大小）",
    ),
)


class ResourceSourceConfig(BaseModel):
    """单个资源源（安装包 / 资源直链）的配置。

    资源源是「下载地址 + 元数据来源」的组合，与渠道服配置是两套独立概念：
    渠道服描述账号登录的目标，资源源描述客户端文件的获取来源。
    国服 PC 端公开直链已关闭，因此资源源必须可由用户配置覆盖（走本地
    已安装目录时改用 LocalIndexTransport）。

    Attributes:
        name: 资源源唯一名称，例如 oversea_neox2。
        url: 安装包 / 资源文件的完整直链（http 或 https）。
        channel: 所属渠道标识，例如 oversea / cn。
        description: 人类可读说明，便于在资源信息中展示。
        is_available: 是否启用；为 False 时该源被跳过。
    """

    model_config = ConfigDict(validate_assignment=True)

    name: str = Field(..., description="资源源名称")
    url: str = Field(..., description="资源源直链")
    channel: str = Field("", description="渠道标识")
    description: str = Field("", description="资源源说明")
    is_available: bool = Field(True, description="是否启用")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """校验资源源名称（非空且仅含字母/数字/下划线/短横线）。

        Args:
            v: 待校验的名称。

        Returns:
            去除首尾空白后的名称。

        Raises:
            ValueError: 名称为空或包含非法字符。
        """
        name = v.strip()
        if not name:
            raise ValueError("资源源名称不能为空")
        if not RESOURCE_SOURCE_NAME_PATTERN.match(name):
            raise ValueError("资源源名称只能包含字母、数字、下划线和短横线")
        return name

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """校验资源源直链必须是合法的 http(s) 绝对地址。

        Args:
            v: 待校验的 URL。

        Returns:
            去除首尾空白后的 URL。

        Raises:
            ValueError: URL 为空或协议不是 http/https。
        """
        url = v.strip()
        if not url:
            raise ValueError("资源源直链不能为空")
        if not url.lower().startswith(("http://", "https://")):
            raise ValueError("资源源直链必须是 http(s) 地址")
        return url


class ServerConfig(BaseModel):
    """渠道服配置。

    Attributes:
        name: 渠道服唯一名称，例如 ``official``。
        endpoint: 渠道服接口地址。
        region: 渠道服所属地区。
        status: 渠道服状态，取值见 :data:`SERVER_STATUSES`。
        version: 渠道服客户端版本号。
        is_default: 是否为当前默认渠道服。
        last_check: 最近一次状态探测时间。
        ping: 最近一次探测到的网络延迟（毫秒）。
        players: 最近一次探测到的在线玩家数。
    """

    model_config = ConfigDict(validate_assignment=True)

    name: str = Field(..., description="渠道服名称")
    endpoint: str = Field("", description="渠道服地址")
    region: str = Field("CN", description="渠道服地区")
    status: str = Field("active", description="渠道服状态")
    version: str = Field("1.0.0", description="渠道服版本")
    is_default: bool = Field(False, description="是否为默认渠道服")
    last_check: datetime | None = Field(None, description="最后检查时间")
    ping: float | None = Field(None, description="网络延迟(毫秒)")
    players: int | None = Field(None, description="在线玩家数")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        """校验渠道服状态取值。

        Args:
            v: 待校验的状态字符串。

        Returns:
            校验通过的状态字符串。

        Raises:
            ValueError: 状态不在 :data:`SERVER_STATUSES` 之内。
        """
        if v not in SERVER_STATUSES:
            raise ValueError(
                f"状态必须是 {' / '.join(SERVER_STATUSES)} 之一，收到: {v}"
            )
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """校验渠道服名称（非空且仅含字母/数字/下划线/短横线）。

        Args:
            v: 待校验的名称。

        Returns:
            去除首尾空白后的名称。

        Raises:
            ValueError: 名称为空或包含非法字符。
        """
        name = v.strip()
        if not name:
            raise ValueError("渠道服名称不能为空")
        if not SERVER_NAME_PATTERN.match(name):
            raise ValueError("渠道服名称只能包含字母、数字、下划线和短横线")
        return name


class AccountConfig(BaseModel):
    """账号配置（持久化形态，密码以密文存储）。

    Attributes:
        encrypted_password: 使用**应用密钥**加密后的密码，用于自动填充登录。
        password_hash: 使用 PBKDF2 派生的密码哈希，用于身份校验。
            引入了 ``password_hash`` 之后，校验密码不再需要先解密原文。
    """

    model_config = ConfigDict(validate_assignment=True)

    id: str = Field(..., description="账号ID")
    username: str = Field(..., description="用户名")
    server: str = Field(..., description="渠道服名称")
    encrypted_password: str = Field("", description="加密后的密码")
    password_hash: str = Field("", description="密码哈希")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    last_login: datetime | None = Field(None, description="最后登录时间")
    is_current: bool = Field(False, description="是否为当前账号")

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        """校验账号 ID 长度。

        Args:
            v: 待校验的账号 ID。

        Returns:
            校验通过的账号 ID。

        Raises:
            ValueError: 长度不足 8 个字符。
        """
        if len(v) < 8:
            raise ValueError("账号ID长度不能少于8个字符")
        return v

    def display_id(self, width: int = 8) -> str:
        """返回用于列表展示的短 ID。

        Args:
            width: 前缀保留的字符数。

        Returns:
            短 ID，超出长度时以 ``...`` 结尾。
        """
        return f"{self.id[:width]}..." if len(self.id) > width else self.id


def default_resource_sources() -> list[ResourceSourceConfig]:
    """构造默认的资源源列表。

    Returns:
        预置国际服两条已实测直链的 :class:`ResourceSourceConfig` 列表。
    """
    return [
        ResourceSourceConfig(
            name=name,
            url=url,
            channel=channel,
            description=description,
            is_available=True,
        )
        for name, url, channel, description in DEFAULT_RESOURCE_SOURCE_DEFINITIONS
    ]


class AppConfig(BaseModel):
    """应用程序级配置。"""

    model_config = ConfigDict(validate_assignment=True)

    server: str = Field("official", description="当前渠道服")
    account: str | None = Field(None, description="当前账号")
    auto_update: bool = Field(True, description="自动更新")
    verbose: bool = Field(False, description="详细输出")
    language: str = Field("zh-CN", description="语言")
    data_dir: str = Field("~/.dwrg", description="数据目录")
    cache_dir: str = Field("~/.dwrg/cache", description="缓存目录")
    game_path: str = Field(
        "", description="游戏目录（为空时取 data_dir/game；checkout 一次设置永久生效）"
    )
    log_level: str = Field("INFO", description="日志级别")
    max_concurrent_downloads: int = Field(5, ge=1, le=10, description="最大并发下载数")
    download_timeout: int = Field(300, ge=5, le=3600, description="下载超时时间(秒)")
    resource_sources: list[ResourceSourceConfig] = Field(
        default_factory=default_resource_sources,
        description="资源源列表（安装包/资源直链），可由用户覆盖",
    )
    resource_source: str = Field(
        "", description="当前使用的资源源名称；为空时取列表中第一个可用源"
    )

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        """校验语言代码是否受支持。

        Args:
            v: 待校验的语言代码。

        Returns:
            校验通过的语言代码。

        Raises:
            ValueError: 语言代码不在 :data:`SUPPORTED_LANGUAGES` 之内。
        """
        if v not in SUPPORTED_LANGUAGES:
            raise ValueError(f"不支持的语言: {v}")
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """校验日志级别。

        Args:
            v: 待校验的日志级别。

        Returns:
            规范化（大写）后的日志级别。

        Raises:
            ValueError: 日志级别不在 :data:`LOG_LEVELS` 之内。
        """
        upper = v.upper()
        if upper not in LOG_LEVELS:
            raise ValueError(f"无效的日志级别: {v}")
        return upper


class Config(BaseModel):
    """应用主配置，聚合应用级、渠道服与账号三部分配置。"""

    app: AppConfig = Field(default_factory=AppConfig)
    servers: dict[str, ServerConfig] = Field(default_factory=dict)
    accounts: dict[str, AccountConfig] = Field(default_factory=dict)

    def get_server(self, name: str) -> ServerConfig | None:
        """获取指定渠道服配置。

        Args:
            name: 渠道服名称。

        Returns:
            渠道服配置；不存在时返回 ``None``。
        """
        return self.servers.get(name)

    def get_account(self, account_id: str) -> AccountConfig | None:
        """获取指定账号配置。

        Args:
            account_id: 账号 ID。

        Returns:
            账号配置；不存在时返回 ``None``。
        """
        return self.accounts.get(account_id)

    def get_current_server(self) -> ServerConfig | None:
        """获取当前默认渠道服配置。

        Returns:
            默认渠道服配置；未设置或不存在时返回 ``None``。
        """
        if self.app.server:
            return self.servers.get(self.app.server)
        return None

    def get_current_account(self) -> AccountConfig | None:
        """获取当前账号配置。

        Returns:
            当前账号配置；未设置或不存在时返回 ``None``。
        """
        if self.app.account:
            return self.accounts.get(self.app.account)
        return None

    def add_server(self, server: ServerConfig) -> None:
        """新增或覆盖一个渠道服配置。

        Args:
            server: 渠道服配置对象。
        """
        self.servers[server.name] = server

    def add_account(self, account: AccountConfig) -> None:
        """新增或覆盖一个账号配置。

        Args:
            account: 账号配置对象。
        """
        self.accounts[account.id] = account

    def remove_server(self, name: str) -> bool:
        """删除指定渠道服配置。

        Args:
            name: 渠道服名称。

        Returns:
            是否删除成功。
        """
        return self.servers.pop(name, None) is not None

    def remove_account(self, account_id: str) -> bool:
        """删除指定账号配置。

        Args:
            account_id: 账号 ID。

        Returns:
            是否删除成功。
        """
        return self.accounts.pop(account_id, None) is not None

    def to_dict(self) -> dict[str, Any]:
        """导出为可 JSON/YAML 序列化的字典。

        Returns:
            纯 Python 字典，``datetime`` 已转换为 ISO 8601 字符串。
        """
        return self.model_dump(mode="json")

    def get_resource_source(
        self, name: str | None = None
    ) -> ResourceSourceConfig | None:
        """按名称获取资源源配置。

        Args:
            name: 资源源名称；为 ``None`` 或空串时使用 ``app.resource_source``
                指定的当前源，仍未指定则取第一个可用源。

        Returns:
            资源源配置；不存在时返回 ``None``。
        """
        target = (name or self.app.resource_source).strip()
        if target:
            for source in self.app.resource_sources:
                if source.name == target:
                    return source
            return None
        for source in self.app.resource_sources:
            if source.is_available:
                return source
        return None


def default_servers() -> dict[str, ServerConfig]:
    """构造默认的渠道服集合。

    Returns:
        以渠道服名称为键的字典，``official`` 被标记为默认渠道服。
    """
    servers: dict[str, ServerConfig] = {}
    for name, endpoint, region in DEFAULT_SERVER_DEFINITIONS:
        servers[name] = ServerConfig(
            name=name,
            endpoint=endpoint,
            region=region,
            is_default=(name == "official"),
        )
    return servers


def default_config() -> Config:
    """构造首次运行使用的初始配置。

    预置全部默认渠道服（``official`` 为默认项），账号集合为空，
    应用级配置取 :class:`AppConfig` 的字段默认值。

    Returns:
        可直接持久化的 :class:`Config` 实例。
    """
    return Config(
        app=AppConfig(server=DEFAULT_SERVER_NAMES[0]),
        servers=default_servers(),
        accounts={},
    )


__all__ = [
    "SERVER_STATUSES",
    "SUPPORTED_LANGUAGES",
    "LOG_LEVELS",
    "SERVER_NAME_PATTERN",
    "DEFAULT_SERVER_DEFINITIONS",
    "DEFAULT_SERVER_NAMES",
    "RESOURCE_SOURCE_NAME_PATTERN",
    "ResourceSourceConfig",
    "ServerConfig",
    "AccountConfig",
    "AppConfig",
    "Config",
    "default_servers",
    "default_resource_sources",
    "default_config",
]

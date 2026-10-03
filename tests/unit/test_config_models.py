"""
配置数据模型单元测试

覆盖 :mod:`dwrg_manager.config.models` 中的 ``ServerConfig`` / ``AccountConfig``
/ ``AppConfig`` / ``Config`` 以及 ``default_servers`` / ``default_config`` 工厂。
"""

from datetime import datetime

import pytest
from pydantic import ValidationError as PydanticValidationError

from dwrg_manager.config.models import (
    DEFAULT_SERVER_NAMES,
    SERVER_NAME_PATTERN,
    SERVER_STATUSES,
    SUPPORTED_LANGUAGES,
    AccountConfig,
    AppConfig,
    Config,
    ServerConfig,
    default_config,
    default_servers,
)


@pytest.mark.unit
class TestServerConfig:
    """``ServerConfig`` 的字段校验与默认值。"""

    def test_create_with_defaults_sets_expected_values(self) -> None:
        """仅提供名称时应填充其余默认值。"""
        server = ServerConfig(name="official")

        assert server.endpoint == ""
        assert server.region == "CN"
        assert server.status == "active"
        assert server.version == "1.0.0"
        assert server.is_default is False
        assert server.ping is None
        assert server.players is None

    def test_create_strips_surrounding_whitespace_from_name(self) -> None:
        """名称首尾空白应被去除。"""
        server = ServerConfig(name="  guild  ")

        assert server.name == "guild"

    @pytest.mark.parametrize("status", SERVER_STATUSES)
    def test_create_accepts_every_supported_status(self, status: str) -> None:
        """所有内置状态取值都应被接受。"""
        server = ServerConfig(name="s1", status=status)

        assert server.status == status

    def test_create_with_unknown_status_raises_validation_error(self) -> None:
        """未知状态应触发 Pydantic 校验错误。"""
        with pytest.raises(PydanticValidationError):
            ServerConfig(name="s1", status="paused")

    def test_create_with_empty_name_raises_validation_error(self) -> None:
        """空名称应被拒绝。"""
        with pytest.raises(PydanticValidationError):
            ServerConfig(name="   ")

    def test_create_with_illegal_characters_raises_validation_error(self) -> None:
        """含空格等非法字符的名称应被拒绝。"""
        with pytest.raises(PydanticValidationError):
            ServerConfig(name="bad name")

    def test_assignment_of_invalid_status_raises_validation_error(self) -> None:
        """开启 validate_assignment 后赋值非法状态应立即报错。"""
        server = ServerConfig(name="s1")

        with pytest.raises(PydanticValidationError):
            server.status = "broken"


@pytest.mark.unit
class TestAccountConfig:
    """``AccountConfig`` 的校验与展示辅助。"""

    def test_create_with_valid_data_keeps_fields(self) -> None:
        """合法数据应原样保留。"""
        account = AccountConfig(id="acc-0001", username="hero", server="official")

        assert account.id == "acc-0001"
        assert account.encrypted_password == ""
        assert account.password_hash == ""
        assert account.is_current is False
        assert isinstance(account.created_at, datetime)

    def test_create_with_short_id_raises_validation_error(self) -> None:
        """账号 ID 少于 8 个字符应被拒绝。"""
        with pytest.raises(PydanticValidationError):
            AccountConfig(id="short", username="hero", server="official")

    def test_display_id_truncates_long_identifier(self) -> None:
        """超长 ID 应截断并追加省略号。"""
        account = AccountConfig(
            id="0123456789abcdef", username="hero", server="official"
        )

        assert account.display_id() == "01234567..."

    def test_display_id_keeps_short_identifier(self) -> None:
        """长度不超过阈值时原样返回。"""
        account = AccountConfig(id="abcdefgh", username="hero", server="official")

        assert account.display_id() == "abcdefgh"


@pytest.mark.unit
class TestAppConfig:
    """``AppConfig`` 的默认值与字段校验。"""

    def test_defaults_match_documented_values(self) -> None:
        """默认值应与文档一致。"""
        app = AppConfig()

        assert app.server == "official"
        assert app.account is None
        assert app.language == "zh-CN"
        assert app.log_level == "INFO"
        assert app.max_concurrent_downloads == 5
        assert app.download_timeout == 300

    @pytest.mark.parametrize("language", SUPPORTED_LANGUAGES)
    def test_create_accepts_supported_languages(self, language: str) -> None:
        """所有受支持的语言都应被接受。"""
        assert AppConfig(language=language).language == language

    def test_create_with_unsupported_language_raises_validation_error(self) -> None:
        """不受支持的语言应被拒绝。"""
        with pytest.raises(PydanticValidationError):
            AppConfig(language="xx-XX")

    def test_create_normalizes_log_level_to_upper_case(self) -> None:
        """小写日志级别应被规范化为大写。"""
        assert AppConfig(log_level="debug").log_level == "DEBUG"

    def test_create_with_invalid_log_level_raises_validation_error(self) -> None:
        """非法日志级别应被拒绝。"""
        with pytest.raises(PydanticValidationError):
            AppConfig(log_level="LOUD")

    @pytest.mark.parametrize("value", [0, 11])
    def test_concurrent_downloads_out_of_range_raises_validation_error(
        self, value: int
    ) -> None:
        """并发数越界应被拒绝。"""
        with pytest.raises(PydanticValidationError):
            AppConfig(max_concurrent_downloads=value)


@pytest.mark.unit
class TestConfigAggregate:
    """``Config`` 的聚合操作。"""

    def test_get_missing_server_returns_none(self) -> None:
        """查询不存在的渠道服返回 ``None``。"""
        assert Config().get_server("nope") is None

    def test_get_missing_account_returns_none(self) -> None:
        """查询不存在的账号返回 ``None``。"""
        assert Config().get_account("nope") is None

    def test_add_and_remove_server_roundtrip(self) -> None:
        """新增后应可查询，删除返回是否成功。"""
        config = Config()
        server = ServerConfig(name="guild")

        config.add_server(server)

        assert config.get_server("guild") is server
        assert config.remove_server("guild") is True
        assert config.remove_server("guild") is False

    def test_add_and_remove_account_roundtrip(self) -> None:
        """账号的增删应与渠道服一致。"""
        config = Config()
        account = AccountConfig(id="acc-0001", username="hero", server="official")

        config.add_account(account)

        assert config.get_account("acc-0001") is account
        assert config.remove_account("acc-0001") is True
        assert config.remove_account("acc-0001") is False

    def test_get_current_server_returns_configured_server(self) -> None:
        """``app.server`` 指向的渠道服应被返回。"""
        config = Config(servers={"official": ServerConfig(name="official")})
        config.app.server = "official"

        assert config.get_current_server() is config.servers["official"]

    def test_get_current_server_returns_none_when_unset(self) -> None:
        """未设置当前渠道服时返回 ``None``。"""
        config = Config()
        config.app.server = ""

        assert config.get_current_server() is None

    def test_get_current_account_returns_configured_account(self) -> None:
        """``app.account`` 指向的账号应被返回。"""
        account = AccountConfig(id="acc-0001", username="hero", server="official")
        config = Config(accounts={"acc-0001": account})
        config.app.account = "acc-0001"

        assert config.get_current_account() is account

    def test_to_dict_serializes_datetime_as_iso_string(self) -> None:
        """``to_dict`` 应产出可 JSON 序列化的结构。"""
        account = AccountConfig(id="acc-0001", username="hero", server="official")
        config = Config(accounts={"acc-0001": account})

        payload = config.to_dict()

        assert set(payload) == {"app", "servers", "accounts"}
        assert isinstance(payload["accounts"]["acc-0001"]["created_at"], str)


@pytest.mark.unit
class TestFactoryFunctions:
    """``default_servers`` 与 ``default_config``。"""

    def test_default_servers_contains_all_builtin_names(self) -> None:
        """默认渠道服集合应覆盖全部内置名称。"""
        servers = default_servers()

        assert set(servers) == set(DEFAULT_SERVER_NAMES)

    def test_default_servers_marks_official_as_default(self) -> None:
        """``official`` 应被标记为默认渠道服。"""
        servers = default_servers()

        assert servers["official"].is_default is True
        assert servers["bserver"].is_default is False

    def test_default_config_selects_official_and_empty_accounts(self) -> None:
        """初始配置应选中 ``official`` 且账号为空。"""
        config = default_config()

        assert config.app.server == "official"
        assert config.accounts == {}
        assert len(config.servers) == len(DEFAULT_SERVER_NAMES)

    def test_server_name_pattern_rejects_illegal_value(self) -> None:
        """名称正则应拒绝含空格的字符串。"""
        assert SERVER_NAME_PATTERN.match("ok-name_1") is not None
        assert SERVER_NAME_PATTERN.match("bad name") is None

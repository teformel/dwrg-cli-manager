"""
配置管理器单元测试

覆盖 :class:`dwrg_manager.config.manager.ConfigManager` 的读写、原子写入、
设置项增删、渠道服/账号 CRUD 以及导入导出。
"""

import json
from pathlib import Path

import pytest
import yaml

from dwrg_manager.config.manager import SETTABLE_KEYS, ConfigManager
from dwrg_manager.config.models import AppConfig, Config
from dwrg_manager.exceptions import ConfigError


@pytest.fixture
def persisted_manager(config_path: Path) -> ConfigManager:
    """返回会自动落盘的配置管理器。

    Args:
        config_path: 临时配置文件路径。

    Returns:
        开启 ``autosave`` 的 :class:`ConfigManager`。
    """
    return ConfigManager(config_path)


@pytest.mark.unit
class TestLoadAndSave:
    """配置文件的加载与原子写入。"""

    def test_init_creates_default_file_when_missing(self, config_path: Path) -> None:
        """首次运行应写入预置默认渠道服的配置文件。"""
        assert not config_path.exists()

        ConfigManager(config_path)

        assert config_path.exists()
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert "official" in data["servers"]

    def test_init_without_autosave_does_not_touch_disk(self, config_path: Path) -> None:
        """关闭自动落盘时不应创建文件。"""
        manager = ConfigManager(config_path, autosave=False)

        assert not config_path.exists()
        assert manager.get_app_config().language == "zh-CN"

    def test_init_loads_existing_yaml_file(self, config_path: Path) -> None:
        """已存在的 YAML 文件应被正确解析。"""
        config_path.write_text(
            yaml.safe_dump({"app": {"language": "en-US"}}), encoding="utf-8"
        )

        manager = ConfigManager(config_path, autosave=False)

        assert manager.get_app_config().language == "en-US"

    def test_init_loads_existing_json_file(self, tmp_path: Path) -> None:
        """``.json`` 后缀应按 JSON 解析。"""
        target = tmp_path / "config.json"
        target.write_text(json.dumps({"app": {"language": "ja-JP"}}), encoding="utf-8")

        manager = ConfigManager(target, autosave=False)

        assert manager.get_app_config().language == "ja-JP"

    def test_init_with_broken_yaml_raises_config_error(self, config_path: Path) -> None:
        """无法解析的 YAML 应抛出 :class:`ConfigError`。"""
        config_path.write_text("app: [unclosed", encoding="utf-8")

        with pytest.raises(ConfigError):
            ConfigManager(config_path, autosave=False)

    def test_init_with_non_mapping_root_raises_config_error(
        self, config_path: Path
    ) -> None:
        """根节点不是映射时应抛出 :class:`ConfigError`。"""
        config_path.write_text("- just\n- a\n- list\n", encoding="utf-8")

        with pytest.raises(ConfigError):
            ConfigManager(config_path, autosave=False)

    def test_init_with_illegal_content_raises_config_error(
        self, config_path: Path
    ) -> None:
        """字段取值非法时应抛出 :class:`ConfigError`。"""
        config_path.write_text(
            yaml.safe_dump({"app": {"language": "xx-XX"}}), encoding="utf-8"
        )

        with pytest.raises(ConfigError):
            ConfigManager(config_path, autosave=False)

    def test_save_config_returns_path_and_is_reloadable(
        self, config_path: Path
    ) -> None:
        """保存后应可从磁盘读回相同内容。"""
        manager = ConfigManager(config_path, autosave=False)
        manager.config.app.language = "de-DE"

        written = manager.save_config()

        assert written == config_path
        reloaded = ConfigManager(config_path, autosave=False)
        assert reloaded.get_app_config().language == "de-DE"

    def test_save_config_accepts_explicit_config_object(
        self, config_path: Path
    ) -> None:
        """显式传入配置对象时应持久化该对象而非内存中的配置。"""
        manager = ConfigManager(config_path, autosave=False)
        custom = Config(app=AppConfig(language="ru-RU"))

        manager.save_config(custom)

        reloaded = ConfigManager(config_path, autosave=False)
        assert reloaded.get_app_config().language == "ru-RU"

    def test_reload_picks_up_external_change(self, config_path: Path) -> None:
        """``reload`` 应重新读取磁盘上的最新内容。"""
        manager = ConfigManager(config_path, autosave=False)
        config_path.write_text(
            yaml.safe_dump({"app": {"language": "ko-KR"}}), encoding="utf-8"
        )

        reloaded = manager.reload()

        assert reloaded.app.language == "ko-KR"


@pytest.mark.unit
class TestAccessors:
    """配置访问器。"""

    def test_get_config_returns_same_object(
        self, config_manager: ConfigManager
    ) -> None:
        """``get_config`` 应返回内存中的同一实例。"""
        assert config_manager.get_config() is config_manager.config

    def test_get_config_dict_is_serializable(
        self, config_manager: ConfigManager
    ) -> None:
        """``get_config_dict`` 结果应可 JSON 序列化。"""
        payload = config_manager.get_config_dict()

        json.dumps(payload)

    def test_get_server_config_returns_none_for_unknown(
        self, config_manager: ConfigManager
    ) -> None:
        """未知渠道服返回 ``None``。"""
        assert config_manager.get_server_config("nope") is None

    def test_get_account_config_returns_none_for_unknown(
        self, config_manager: ConfigManager
    ) -> None:
        """未知账号返回 ``None``。"""
        assert config_manager.get_account_config("nope") is None

    def test_get_current_server_returns_default(
        self, config_manager: ConfigManager
    ) -> None:
        """默认配置下当前渠道服为 ``official``。"""
        current = config_manager.get_current_server()

        assert current is not None
        assert current.name == "official"

    def test_get_current_account_returns_none_by_default(
        self, config_manager: ConfigManager
    ) -> None:
        """默认配置下没有当前账号。"""
        assert config_manager.get_current_account() is None


@pytest.mark.unit
class TestSetUnsetConfig:
    """``set_config`` / ``unset_config``。"""

    def test_set_config_coerces_numeric_string(
        self, persisted_manager: ConfigManager
    ) -> None:
        """命令行传入的字符串数字应被转换为整数。"""
        persisted_manager.set_config("max_concurrent_downloads", "8")

        assert persisted_manager.get_app_config().max_concurrent_downloads == 8

    def test_set_config_accepts_app_prefixed_key(
        self, persisted_manager: ConfigManager
    ) -> None:
        """``app.`` 前缀应被正确剥离。"""
        persisted_manager.set_config("app.log_level", "debug")

        assert persisted_manager.get_app_config().log_level == "DEBUG"

    def test_set_config_persists_when_autosave_enabled(
        self, persisted_manager: ConfigManager, config_path: Path
    ) -> None:
        """开启自动落盘后修改应写入文件。"""
        persisted_manager.set_config("language", "fr-FR")

        reloaded = ConfigManager(config_path, autosave=False)
        assert reloaded.get_app_config().language == "fr-FR"

    def test_set_config_with_unknown_key_raises_config_error(
        self, persisted_manager: ConfigManager
    ) -> None:
        """未知配置项应抛出 :class:`ConfigError`。"""
        with pytest.raises(ConfigError):
            persisted_manager.set_config("bogus", "1")

    def test_set_config_with_illegal_value_raises_config_error(
        self, persisted_manager: ConfigManager
    ) -> None:
        """取值非法时应抛出 :class:`ConfigError`。"""
        with pytest.raises(ConfigError):
            persisted_manager.set_config("language", "xx-XX")

    def test_set_config_without_autosave_keeps_disk_unchanged(
        self, config_manager: ConfigManager, config_path: Path
    ) -> None:
        """未开启自动落盘时不应写文件。"""
        config_manager.set_config("log_level", "DEBUG")

        assert not config_path.exists()

    def test_unset_config_restores_default_value(
        self, persisted_manager: ConfigManager
    ) -> None:
        """重置后应恢复字段默认值。"""
        persisted_manager.set_config("log_level", "DEBUG")

        persisted_manager.unset_config("log_level")

        assert persisted_manager.get_app_config().log_level == "INFO"

    def test_unset_config_with_unknown_key_raises_config_error(
        self, persisted_manager: ConfigManager
    ) -> None:
        """未知配置项重置应抛出 :class:`ConfigError`。"""
        with pytest.raises(ConfigError):
            persisted_manager.unset_config("bogus")

    def test_settable_keys_covers_all_app_fields(self) -> None:
        """可设置键集合应与 ``AppConfig`` 字段一一对应。"""
        assert set(SETTABLE_KEYS) == set(AppConfig.model_fields)


@pytest.mark.unit
class TestServerCrud:
    """渠道服增删改查。"""

    def test_add_server_returns_created_config(
        self, config_manager: ConfigManager
    ) -> None:
        """新增渠道服应返回新建的配置对象。"""
        server = config_manager.add_server("guild", endpoint="https://g.example")

        assert server.name == "guild"
        assert config_manager.get_server_config("guild") is server

    def test_add_server_with_illegal_name_raises_config_error(
        self, config_manager: ConfigManager
    ) -> None:
        """非法名称应抛出 :class:`ConfigError`。"""
        with pytest.raises(ConfigError):
            config_manager.add_server("bad name")

    def test_add_server_as_default_updates_current(
        self, config_manager: ConfigManager
    ) -> None:
        """``is_default=True`` 时应同时切换当前渠道服。"""
        config_manager.add_server("guild", is_default=True)

        assert config_manager.get_app_config().server == "guild"
        assert config_manager.get_server_config("guild").is_default is True
        assert config_manager.get_server_config("official").is_default is False

    def test_remove_server_returns_true_then_false(
        self, config_manager: ConfigManager
    ) -> None:
        """删除已存在渠道服返回 ``True``，重复删除返回 ``False``。"""
        config_manager.add_server("guild")

        assert config_manager.remove_server("guild") is True
        assert config_manager.remove_server("guild") is False

    def test_remove_current_server_switches_to_remaining(
        self, config_manager: ConfigManager
    ) -> None:
        """删除当前渠道服后应回退到其余渠道服之首。"""
        config_manager.remove_server("official")

        assert config_manager.get_app_config().server == "bserver"

    def test_remove_last_server_clears_current(
        self, config_manager: ConfigManager
    ) -> None:
        """删除唯一的渠道服后当前渠道服应为空串。"""
        for name in list(config_manager.get_config().servers):
            config_manager.remove_server(name)

        assert config_manager.get_app_config().server == ""

    def test_set_default_server_updates_flags(
        self, config_manager: ConfigManager
    ) -> None:
        """设为默认后标记应唯一。"""
        config_manager.set_default_server("bserver")

        servers = config_manager.get_config().servers
        assert servers["bserver"].is_default is True
        assert servers["official"].is_default is False

    def test_set_default_with_unknown_server_raises_config_error(
        self, config_manager: ConfigManager
    ) -> None:
        """不存在的渠道服应抛出 :class:`ConfigError`。"""
        with pytest.raises(ConfigError):
            config_manager.set_default_server("nope")

    def test_list_servers_is_sorted_by_name(
        self, config_manager: ConfigManager
    ) -> None:
        """列表应按名称排序。"""
        names = [server.name for server in config_manager.list_servers()]

        assert names == sorted(names)

    def test_ensure_default_servers_adds_missing_entries(
        self, config_manager: ConfigManager
    ) -> None:
        """缺失的内置渠道服应被补齐并返回新增数量。"""
        config_manager.remove_server("test_server")

        added = config_manager.ensure_default_servers()

        assert added == 1
        assert config_manager.get_server_config("test_server") is not None

    def test_ensure_default_servers_returns_zero_when_complete(
        self, config_manager: ConfigManager
    ) -> None:
        """无缺失时返回 0。"""
        assert config_manager.ensure_default_servers() == 0

    def test_get_default_server_names_returns_builtin_tuple(
        self, config_manager: ConfigManager
    ) -> None:
        """内置名称元组应包含 ``official``。"""
        assert "official" in config_manager.get_default_server_names()


@pytest.mark.unit
class TestAccountCrud:
    """账号增删改查。"""

    def test_add_account_encrypts_password_and_hashes(
        self, config_manager: ConfigManager
    ) -> None:
        """新增账号应同时写入密文与哈希。"""
        account = config_manager.add_account("hero", "official", "secret123")

        assert account.encrypted_password
        assert account.password_hash
        assert account.encrypted_password != "secret123"

    def test_add_account_with_explicit_id_is_respected(
        self, config_manager: ConfigManager
    ) -> None:
        """显式传入的账号 ID 应被采用。"""
        account = config_manager.add_account(
            "hero", "official", "secret123", account_id="acc-00000001"
        )

        assert account.id == "acc-00000001"

    def test_add_account_with_short_id_raises_config_error(
        self, config_manager: ConfigManager
    ) -> None:
        """过短的 ID 应触发校验失败并包装为 :class:`ConfigError`。"""
        with pytest.raises(ConfigError):
            config_manager.add_account("hero", "official", "secret123", account_id="x")

    def test_save_account_overwrites_existing_entry(
        self, config_manager: ConfigManager
    ) -> None:
        """保存应覆盖同 ID 的既有账号。"""
        account = config_manager.add_account("hero", "official", "secret123")
        account.username = "hero2"

        config_manager.save_account(account)

        assert config_manager.get_account_config(account.id).username == "hero2"

    def test_remove_account_returns_true_then_false(
        self, config_manager: ConfigManager
    ) -> None:
        """删除返回布尔结果。"""
        account = config_manager.add_account("hero", "official", "secret123")

        assert config_manager.remove_account(account.id) is True
        assert config_manager.remove_account(account.id) is False

    def test_switch_account_marks_it_current(
        self, config_manager: ConfigManager
    ) -> None:
        """切换账号应写入当前账号与 ``is_current`` 标记。"""
        account = config_manager.add_account("hero", "official", "secret123")

        assert config_manager.switch_account(account.id) is True
        assert config_manager.get_current_account().id == account.id
        assert config_manager.get_account_config(account.id).is_current is True

    def test_switch_account_with_unknown_id_returns_false(
        self, config_manager: ConfigManager
    ) -> None:
        """未知账号切换失败且返回 ``False``。"""
        assert config_manager.switch_account("nope") is False

    def test_remove_current_account_clears_current(
        self, config_manager: ConfigManager
    ) -> None:
        """删除当前账号后应清空 ``app.account``。"""
        account = config_manager.add_account("hero", "official", "secret123")
        config_manager.switch_account(account.id)

        config_manager.remove_account(account.id)

        assert config_manager.get_app_config().account is None

    def test_list_accounts_filters_by_server(
        self, config_manager: ConfigManager
    ) -> None:
        """按渠道服过滤应只返回该渠道服下的账号。"""
        config_manager.add_account("hero", "official", "secret123")
        config_manager.add_account("mage", "bserver", "secret456")

        official_accounts = config_manager.list_accounts("bserver")

        assert [a.username for a in official_accounts] == ["mage"]

    def test_list_accounts_is_sorted_by_id(self, config_manager: ConfigManager) -> None:
        """账号列表应按 ID 排序。"""
        config_manager.add_account(
            "b", "official", "secret123", account_id="acc-bbbbbbbb"
        )
        config_manager.add_account(
            "a", "official", "secret123", account_id="acc-aaaaaaaa"
        )

        ids = [a.id for a in config_manager.list_accounts()]

        assert ids == sorted(ids)


@pytest.mark.unit
class TestImportExport:
    """配置的导入与导出。"""

    def test_export_to_yaml_writes_readable_file(
        self, config_manager: ConfigManager, tmp_path: Path
    ) -> None:
        """导出 YAML 后应能重新解析出渠道服。"""
        target = tmp_path / "out" / "export.yaml"

        written = config_manager.export_config(target, fmt="yaml")

        assert written == target
        data = yaml.safe_load(target.read_text(encoding="utf-8"))
        assert "official" in data["servers"]

    def test_export_to_json_creates_valid_json(
        self, config_manager: ConfigManager, tmp_path: Path
    ) -> None:
        """导出 JSON 后应是合法 JSON。"""
        target = tmp_path / "export.json"

        config_manager.export_config(target, fmt="json")

        payload = json.loads(target.read_text(encoding="utf-8"))
        assert "app" in payload

    def test_export_with_unsupported_format_raises_config_error(
        self, config_manager: ConfigManager, tmp_path: Path
    ) -> None:
        """不支持的格式应抛出 :class:`ConfigError`。"""
        with pytest.raises(ConfigError):
            config_manager.export_config(tmp_path / "out.xml", fmt="xml")

    def test_import_replaces_current_config(
        self, config_manager: ConfigManager, tmp_path: Path
    ) -> None:
        """导入后内存中的配置应被替换。"""
        source = tmp_path / "source.yaml"
        source.write_text(
            yaml.safe_dump({"app": {"language": "es-ES"}}), encoding="utf-8"
        )

        imported = config_manager.import_config(source)

        assert imported.app.language == "es-ES"
        assert config_manager.get_app_config().language == "es-ES"

    def test_import_missing_file_raises_config_error(
        self, config_manager: ConfigManager, tmp_path: Path
    ) -> None:
        """导入不存在的文件应抛出 :class:`ConfigError`。"""
        with pytest.raises(ConfigError):
            config_manager.import_config(tmp_path / "missing.yaml")

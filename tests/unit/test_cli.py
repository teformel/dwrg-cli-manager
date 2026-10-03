"""
CLI 命令单元测试

使用 :class:`typer.testing.CliRunner` 覆盖 account / server / config / plugin /
status / diagnose 等命令的正常路径与错误路径，并断言退出码。所有命令均通过
``--config`` 指向临时配置文件，网络探测被替换为测试替身。
"""

from pathlib import Path
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

from dwrg_manager.cli import app
from dwrg_manager.servers import manager as servers_manager_module

PLUGIN_SOURCE = '''\
"""测试插件。"""

from dwrg_manager.plugins import Plugin


class DemoPlugin(Plugin):
    """最小可用插件。"""

    name = "demo"
    version = "1.0.0"
    description = "测试插件"
    author = "tester"

    def on_enable(self) -> None:
        """启用时不做任何事。"""
'''


def _read_config(path: Path) -> dict[str, Any]:
    """读取并解析 YAML 配置文件。

    Args:
        path: 配置文件路径。

    Returns:
        解析后的字典；文件为空时返回空字典。
    """
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _first_account_id(path: Path) -> str:
    """取出配置文件中首个账号的 ID。

    Args:
        path: 配置文件路径。

    Returns:
        账号 ID。
    """
    data = _read_config(path)
    return next(iter(data["accounts"]))


@pytest.fixture
def plugin_dir(tmp_path: Path) -> Path:
    """创建一个含最小插件的目录。

    Args:
        tmp_path: 临时目录。

    Returns:
        插件目录路径。
    """
    directory = tmp_path / "plugins"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "demo.py").write_text(PLUGIN_SOURCE, encoding="utf-8")
    return directory


@pytest.mark.unit
class TestTopLevel:
    """顶层版本与帮助命令。"""

    def test_version_option_prints_version(self, cli_runner: CliRunner) -> None:
        """``--version`` 应打印版本号并以 0 退出。"""
        result = cli_runner.invoke(app, ["--version"])

        assert result.exit_code == 0
        assert "1.0.0" in result.stdout

    def test_help_option_exits_zero(self, cli_runner: CliRunner) -> None:
        """``--help`` 应正常退出。"""
        assert cli_runner.invoke(app, ["--help"]).exit_code == 0

    def test_help_command_exits_zero(self, cli_runner: CliRunner) -> None:
        """``help`` 子命令应打印命令总览。"""
        result = cli_runner.invoke(app, ["help"])

        assert result.exit_code == 0
        assert "account" in result.stdout


@pytest.mark.unit
class TestAccountCommands:
    """``account`` 子命令组。"""

    def test_add_with_valid_input_succeeds(
        self, cli_runner: CliRunner, config_path: Path
    ) -> None:
        """合法参数应成功创建账号。"""
        result = cli_runner.invoke(
            app,
            [
                "account",
                "add",
                "-u",
                "hero",
                "-p",
                "secret123",
                "-s",
                "official",
                "--config",
                str(config_path),
            ],
        )

        assert result.exit_code == 0
        assert _read_config(config_path)["accounts"]

    def test_add_with_short_username_fails(
        self, cli_runner: CliRunner, config_path: Path
    ) -> None:
        """用户名过短应以 1 退出。"""
        result = cli_runner.invoke(
            app,
            [
                "account",
                "add",
                "-u",
                "ab",
                "-p",
                "secret123",
                "--config",
                str(config_path),
            ],
        )

        assert result.exit_code == 1

    def test_add_with_unknown_server_fails(
        self, cli_runner: CliRunner, config_path: Path
    ) -> None:
        """渠道服不存在应以 1 退出。"""
        result = cli_runner.invoke(
            app,
            [
                "account",
                "add",
                "-u",
                "hero",
                "-p",
                "secret123",
                "-s",
                "nope",
                "--config",
                str(config_path),
            ],
        )

        assert result.exit_code == 1

    def test_add_twice_with_same_username_fails(
        self, cli_runner: CliRunner, config_path: Path
    ) -> None:
        """重复用户名应以 1 退出。"""
        args = [
            "account",
            "add",
            "-u",
            "hero",
            "-p",
            "secret123",
            "--config",
            str(config_path),
        ]
        cli_runner.invoke(app, args)

        assert cli_runner.invoke(app, args).exit_code == 1

    def test_list_with_accounts_exits_zero(
        self, cli_runner: CliRunner, config_path: Path
    ) -> None:
        """有账号时列表命令应成功。"""
        cli_runner.invoke(
            app,
            [
                "account",
                "add",
                "-u",
                "hero",
                "-p",
                "secret123",
                "--config",
                str(config_path),
            ],
        )

        result = cli_runner.invoke(
            app, ["account", "list", "--config", str(config_path)]
        )

        assert result.exit_code == 0
        assert "hero" in result.stdout

    def test_list_json_format_emits_json(
        self, cli_runner: CliRunner, config_path: Path
    ) -> None:
        """``--format json`` 应输出可解析的 JSON。"""
        cli_runner.invoke(
            app,
            [
                "account",
                "add",
                "-u",
                "hero",
                "-p",
                "secret123",
                "--config",
                str(config_path),
            ],
        )

        result = cli_runner.invoke(
            app,
            ["account", "list", "-f", "json", "--config", str(config_path)],
        )

        assert result.exit_code == 0
        assert '"username": "hero"' in result.stdout

    def test_list_without_accounts_warns_and_exits_zero(
        self, cli_runner: CliRunner, config_path: Path
    ) -> None:
        """空列表应给出提示但仍以 0 退出。"""
        result = cli_runner.invoke(
            app, ["account", "list", "--config", str(config_path)]
        )

        assert result.exit_code == 0
        assert "暂无账号" in result.stdout

    def test_switch_existing_account_exits_zero(
        self, cli_runner: CliRunner, config_path: Path
    ) -> None:
        """切换已存在账号应成功。"""
        cli_runner.invoke(
            app,
            [
                "account",
                "add",
                "-u",
                "hero",
                "-p",
                "secret123",
                "--config",
                str(config_path),
            ],
        )
        account_id = _first_account_id(config_path)

        result = cli_runner.invoke(
            app, ["account", "switch", account_id, "--config", str(config_path)]
        )

        assert result.exit_code == 0

    def test_switch_missing_account_fails(
        self, cli_runner: CliRunner, config_path: Path
    ) -> None:
        """切换不存在账号应以 1 退出。"""
        result = cli_runner.invoke(
            app, ["account", "switch", "acc-missing", "--config", str(config_path)]
        )

        assert result.exit_code == 1

    def test_remove_with_force_exits_zero(
        self, cli_runner: CliRunner, config_path: Path
    ) -> None:
        """``--force`` 删除已存在账号应成功。"""
        cli_runner.invoke(
            app,
            [
                "account",
                "add",
                "-u",
                "hero",
                "-p",
                "secret123",
                "--config",
                str(config_path),
            ],
        )
        account_id = _first_account_id(config_path)

        result = cli_runner.invoke(
            app,
            ["account", "remove", account_id, "--force", "--config", str(config_path)],
        )

        assert result.exit_code == 0

    def test_remove_missing_account_fails(
        self, cli_runner: CliRunner, config_path: Path
    ) -> None:
        """删除不存在账号应以 1 退出。"""
        result = cli_runner.invoke(
            app,
            [
                "account",
                "remove",
                "acc-missing",
                "--force",
                "--config",
                str(config_path),
            ],
        )

        assert result.exit_code == 1

    def test_status_with_explicit_id_exits_zero(
        self, cli_runner: CliRunner, config_path: Path
    ) -> None:
        """查看指定账号状态应成功。"""
        cli_runner.invoke(
            app,
            [
                "account",
                "add",
                "-u",
                "hero",
                "-p",
                "secret123",
                "--config",
                str(config_path),
            ],
        )
        account_id = _first_account_id(config_path)

        result = cli_runner.invoke(
            app, ["account", "status", account_id, "--config", str(config_path)]
        )

        assert result.exit_code == 0
        assert "hero" in result.stdout

    def test_status_without_current_account_fails(
        self, cli_runner: CliRunner, config_path: Path
    ) -> None:
        """没有当前账号时查看状态应以 1 退出。"""
        result = cli_runner.invoke(
            app, ["account", "status", "--config", str(config_path)]
        )

        assert result.exit_code == 1

    def test_login_existing_account_exits_zero(
        self, cli_runner: CliRunner, config_path: Path
    ) -> None:
        """登录已存在账号应成功。"""
        cli_runner.invoke(
            app,
            [
                "account",
                "add",
                "-u",
                "hero",
                "-p",
                "secret123",
                "--config",
                str(config_path),
            ],
        )
        account_id = _first_account_id(config_path)

        result = cli_runner.invoke(
            app, ["account", "login", account_id, "--config", str(config_path)]
        )

        assert result.exit_code == 0

    def test_login_missing_account_fails(
        self, cli_runner: CliRunner, config_path: Path
    ) -> None:
        """登录不存在账号应以 1 退出。"""
        result = cli_runner.invoke(
            app, ["account", "login", "acc-missing", "--config", str(config_path)]
        )

        assert result.exit_code == 1

    def test_logout_without_current_account_warns(
        self, cli_runner: CliRunner, config_path: Path
    ) -> None:
        """无当前账号时登出应提示且以 0 退出。"""
        result = cli_runner.invoke(
            app, ["account", "logout", "--config", str(config_path)]
        )

        assert result.exit_code == 0
        assert "当前没有登录的账号" in result.stdout

    def test_logout_after_login_succeeds(
        self, cli_runner: CliRunner, config_path: Path
    ) -> None:
        """已登录账号可正常登出。"""
        cli_runner.invoke(
            app,
            [
                "account",
                "add",
                "-u",
                "hero",
                "-p",
                "secret123",
                "--config",
                str(config_path),
            ],
        )
        account_id = _first_account_id(config_path)
        cli_runner.invoke(
            app, ["account", "login", account_id, "--config", str(config_path)]
        )

        result = cli_runner.invoke(
            app, ["account", "logout", "--config", str(config_path)]
        )

        assert result.exit_code == 0


@pytest.mark.unit
class TestServerCommands:
    """``server`` 子命令组。"""

    def test_list_exits_zero_and_shows_defaults(
        self, cli_runner: CliRunner, config_path: Path
    ) -> None:
        """默认渠道服应出现在列表中。"""
        result = cli_runner.invoke(
            app, ["server", "list", "--config", str(config_path)]
        )

        assert result.exit_code == 0
        assert "official" in result.stdout

    def test_list_json_format_exits_zero(
        self, cli_runner: CliRunner, config_path: Path
    ) -> None:
        """``--format json`` 应正常输出。"""
        result = cli_runner.invoke(
            app, ["server", "list", "-f", "json", "--config", str(config_path)]
        )

        assert result.exit_code == 0
        assert '"official"' in result.stdout

    def test_current_exits_zero(self, cli_runner: CliRunner, config_path: Path) -> None:
        """当前渠道服应可查询。"""
        result = cli_runner.invoke(
            app, ["server", "current", "--config", str(config_path)]
        )

        assert result.exit_code == 0
        assert "official" in result.stdout

    def test_add_new_server_exits_zero(
        self, cli_runner: CliRunner, config_path: Path
    ) -> None:
        """新增合法渠道服应成功。"""
        result = cli_runner.invoke(
            app,
            [
                "server",
                "add",
                "guild",
                "-e",
                "https://g.example",
                "--config",
                str(config_path),
            ],
        )

        assert result.exit_code == 0
        assert "guild" in _read_config(config_path)["servers"]

    def test_add_with_illegal_name_fails(
        self, cli_runner: CliRunner, config_path: Path
    ) -> None:
        """非法名称应以 1 退出。"""
        result = cli_runner.invoke(
            app, ["server", "add", "bad name", "--config", str(config_path)]
        )

        assert result.exit_code == 1

    def test_switch_with_force_exits_zero(
        self, cli_runner: CliRunner, config_path: Path
    ) -> None:
        """切换到已存在渠道服应成功。"""
        result = cli_runner.invoke(
            app,
            ["server", "switch", "bserver", "--force", "--config", str(config_path)],
        )

        assert result.exit_code == 0

    def test_switch_missing_server_fails(
        self, cli_runner: CliRunner, config_path: Path
    ) -> None:
        """切换到不存在渠道服应以 1 退出。"""
        result = cli_runner.invoke(
            app,
            ["server", "switch", "nope", "--force", "--config", str(config_path)],
        )

        assert result.exit_code == 1

    def test_show_existing_server_exits_zero(
        self, cli_runner: CliRunner, config_path: Path
    ) -> None:
        """查看已存在渠道服应成功。"""
        result = cli_runner.invoke(
            app, ["server", "show", "official", "--config", str(config_path)]
        )

        assert result.exit_code == 0

    def test_show_missing_server_fails(
        self, cli_runner: CliRunner, config_path: Path
    ) -> None:
        """查看不存在渠道服应以 1 退出。"""
        result = cli_runner.invoke(
            app, ["server", "show", "nope", "--config", str(config_path)]
        )

        assert result.exit_code == 1

    def test_info_is_alias_of_show(
        self, cli_runner: CliRunner, config_path: Path
    ) -> None:
        """``server info`` 与 ``show`` 行为一致。"""
        result = cli_runner.invoke(
            app, ["server", "info", "official", "--config", str(config_path)]
        )

        assert result.exit_code == 0

    def test_set_default_existing_server_exits_zero(
        self, cli_runner: CliRunner, config_path: Path
    ) -> None:
        """设置默认渠道服应成功。"""
        result = cli_runner.invoke(
            app, ["server", "set-default", "bserver", "--config", str(config_path)]
        )

        assert result.exit_code == 0

    def test_set_default_missing_server_fails(
        self, cli_runner: CliRunner, config_path: Path
    ) -> None:
        """设置不存在的默认渠道服应以 1 退出。"""
        result = cli_runner.invoke(
            app, ["server", "set-default", "nope", "--config", str(config_path)]
        )

        assert result.exit_code == 1

    def test_remove_with_force_exits_zero(
        self, cli_runner: CliRunner, config_path: Path
    ) -> None:
        """删除已存在渠道服应成功。"""
        cli_runner.invoke(app, ["server", "add", "guild", "--config", str(config_path)])

        result = cli_runner.invoke(
            app, ["server", "remove", "guild", "--force", "--config", str(config_path)]
        )

        assert result.exit_code == 0

    def test_remove_missing_server_fails(
        self, cli_runner: CliRunner, config_path: Path
    ) -> None:
        """删除不存在渠道服应以 1 退出。"""
        result = cli_runner.invoke(
            app, ["server", "remove", "nope", "--force", "--config", str(config_path)]
        )

        assert result.exit_code == 1

    def test_detect_uses_probe_results(
        self,
        cli_runner: CliRunner,
        config_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """探测命令应展示结果并推荐最优渠道服。"""

        async def fake_ping(endpoint: str, timeout: int = 10) -> float:
            _ = (endpoint, timeout)
            return 8.0

        async def fake_status(endpoint: str, timeout: int = 10) -> dict[str, object]:
            _ = (endpoint, timeout)
            return {"status": "active", "version": "1.0.0", "players": 3}

        monkeypatch.setattr(servers_manager_module, "ping_server", fake_ping)
        monkeypatch.setattr(servers_manager_module, "check_server_status", fake_status)

        result = cli_runner.invoke(
            app, ["server", "detect", "--config", str(config_path)]
        )

        assert result.exit_code == 0
        assert "推荐渠道服" in result.stdout


@pytest.mark.unit
class TestConfigCommands:
    """``config`` 子命令组。"""

    def test_show_exits_zero(self, cli_runner: CliRunner, config_path: Path) -> None:
        """显示配置应成功。"""
        result = cli_runner.invoke(
            app, ["config", "show", "--config", str(config_path)]
        )

        assert result.exit_code == 0
        assert "app.log_level" in result.stdout

    def test_show_with_key_exits_zero(
        self, cli_runner: CliRunner, config_path: Path
    ) -> None:
        """按 key 查看配置应成功。"""
        result = cli_runner.invoke(
            app,
            ["config", "show", "--key", "app.log_level", "--config", str(config_path)],
        )

        assert result.exit_code == 0
        assert "INFO" in result.stdout

    def test_show_with_unknown_key_fails(
        self, cli_runner: CliRunner, config_path: Path
    ) -> None:
        """未知配置项应以 1 退出。"""
        result = cli_runner.invoke(
            app,
            ["config", "show", "--key", "nope", "--config", str(config_path)],
        )

        assert result.exit_code == 1

    def test_show_json_format_exits_zero(
        self, cli_runner: CliRunner, config_path: Path
    ) -> None:
        """``--format json`` 应输出 JSON。"""
        result = cli_runner.invoke(
            app, ["config", "show", "-f", "json", "--config", str(config_path)]
        )

        assert result.exit_code == 0
        assert '"app"' in result.stdout

    def test_set_valid_key_exits_zero(
        self, cli_runner: CliRunner, config_path: Path
    ) -> None:
        """设置合法配置项应成功并落盘。"""
        result = cli_runner.invoke(
            app, ["config", "set", "log_level", "DEBUG", "--config", str(config_path)]
        )

        assert result.exit_code == 0
        assert _read_config(config_path)["app"]["log_level"] == "DEBUG"

    def test_set_unknown_key_fails(
        self, cli_runner: CliRunner, config_path: Path
    ) -> None:
        """设置未知配置项应以 1 退出。"""
        result = cli_runner.invoke(
            app, ["config", "set", "bogus", "1", "--config", str(config_path)]
        )

        assert result.exit_code == 1

    def test_set_illegal_value_fails(
        self, cli_runner: CliRunner, config_path: Path
    ) -> None:
        """设置非法取值应以 1 退出。"""
        result = cli_runner.invoke(
            app, ["config", "set", "language", "xx-XX", "--config", str(config_path)]
        )

        assert result.exit_code == 1

    def test_unset_existing_key_exits_zero(
        self, cli_runner: CliRunner, config_path: Path
    ) -> None:
        """重置配置项应成功。"""
        cli_runner.invoke(
            app, ["config", "set", "log_level", "DEBUG", "--config", str(config_path)]
        )

        result = cli_runner.invoke(
            app, ["config", "unset", "log_level", "--config", str(config_path)]
        )

        assert result.exit_code == 0

    def test_unset_unknown_key_fails(
        self, cli_runner: CliRunner, config_path: Path
    ) -> None:
        """重置未知配置项应以 1 退出。"""
        result = cli_runner.invoke(
            app, ["config", "unset", "bogus", "--config", str(config_path)]
        )

        assert result.exit_code == 1

    def test_reset_with_force_exits_zero(
        self, cli_runner: CliRunner, config_path: Path
    ) -> None:
        """``--force`` 重置配置应成功。"""
        result = cli_runner.invoke(
            app, ["config", "reset", "--force", "--config", str(config_path)]
        )

        assert result.exit_code == 0

    def test_export_yaml_exits_zero(
        self, cli_runner: CliRunner, config_path: Path, tmp_path: Path
    ) -> None:
        """导出 YAML 应创建目标文件。"""
        target = tmp_path / "export.yaml"

        result = cli_runner.invoke(
            app, ["config", "export", str(target), "--config", str(config_path)]
        )

        assert result.exit_code == 0
        assert target.exists()

    def test_export_with_unsupported_format_fails(
        self, cli_runner: CliRunner, config_path: Path, tmp_path: Path
    ) -> None:
        """不支持的导出格式应以 1 退出。"""
        result = cli_runner.invoke(
            app,
            [
                "config",
                "export",
                str(tmp_path / "out.xml"),
                "-f",
                "xml",
                "--config",
                str(config_path),
            ],
        )

        assert result.exit_code == 1

    def test_import_valid_file_exits_zero(
        self, cli_runner: CliRunner, config_path: Path, tmp_path: Path
    ) -> None:
        """导入合法文件应成功。"""
        source = tmp_path / "source.yaml"
        source.write_text(
            yaml.safe_dump({"app": {"language": "en-US"}}), encoding="utf-8"
        )

        result = cli_runner.invoke(
            app, ["config", "import", str(source), "--config", str(config_path)]
        )

        assert result.exit_code == 0
        assert _read_config(config_path)["app"]["language"] == "en-US"

    def test_import_missing_file_fails(
        self, cli_runner: CliRunner, config_path: Path, tmp_path: Path
    ) -> None:
        """导入不存在的文件应以 1 退出。"""
        result = cli_runner.invoke(
            app,
            [
                "config",
                "import",
                str(tmp_path / "missing.yaml"),
                "--config",
                str(config_path),
            ],
        )

        assert result.exit_code == 1


@pytest.mark.unit
class TestPluginCommands:
    """``plugin`` 子命令组。"""

    def test_list_without_plugins_warns_and_exits_zero(
        self, cli_runner: CliRunner, tmp_path: Path
    ) -> None:
        """没有插件时应提示且以 0 退出。"""
        result = cli_runner.invoke(
            app, ["plugin", "list", "--plugin-dir", str(tmp_path / "empty")]
        )

        assert result.exit_code == 0
        assert "未发现插件" in result.stdout

    def test_list_json_without_plugins_emits_empty_array(
        self, cli_runner: CliRunner, tmp_path: Path
    ) -> None:
        """``--format json`` 空目录应输出 ``[]``。"""
        result = cli_runner.invoke(
            app,
            [
                "plugin",
                "list",
                "-f",
                "json",
                "--plugin-dir",
                str(tmp_path / "empty"),
            ],
        )

        assert result.exit_code == 0
        assert "[]" in result.stdout

    def test_list_discovered_plugin_exits_zero(
        self, cli_runner: CliRunner, plugin_dir: Path
    ) -> None:
        """发现插件后应出现在列表中。"""
        result = cli_runner.invoke(
            app, ["plugin", "list", "--plugin-dir", str(plugin_dir)]
        )

        assert result.exit_code == 0
        assert "demo" in result.stdout

    def test_info_unknown_plugin_fails(
        self, cli_runner: CliRunner, plugin_dir: Path
    ) -> None:
        """查询不存在插件应以 1 退出。"""
        result = cli_runner.invoke(
            app, ["plugin", "info", "nope", "--plugin-dir", str(plugin_dir)]
        )

        assert result.exit_code == 1

    def test_info_known_plugin_exits_zero(
        self, cli_runner: CliRunner, plugin_dir: Path
    ) -> None:
        """查询已发现插件应成功。"""
        result = cli_runner.invoke(
            app, ["plugin", "info", "demo", "--plugin-dir", str(plugin_dir)]
        )

        assert result.exit_code == 0
        assert "demo" in result.stdout

    def test_enable_and_disable_plugin_roundtrip(
        self, cli_runner: CliRunner, plugin_dir: Path
    ) -> None:
        """启用后再禁用应均成功。"""
        enabled = cli_runner.invoke(
            app, ["plugin", "enable", "demo", "--plugin-dir", str(plugin_dir)]
        )
        disabled = cli_runner.invoke(
            app, ["plugin", "disable", "demo", "--plugin-dir", str(plugin_dir)]
        )

        assert enabled.exit_code == 0
        assert disabled.exit_code == 0

    def test_enable_unknown_plugin_fails(
        self, cli_runner: CliRunner, plugin_dir: Path
    ) -> None:
        """启用不存在插件应以 1 退出。"""
        result = cli_runner.invoke(
            app, ["plugin", "enable", "nope", "--plugin-dir", str(plugin_dir)]
        )

        assert result.exit_code == 1

    def test_disable_unknown_plugin_fails(
        self, cli_runner: CliRunner, plugin_dir: Path
    ) -> None:
        """禁用不存在插件应以 1 退出。"""
        result = cli_runner.invoke(
            app, ["plugin", "disable", "nope", "--plugin-dir", str(plugin_dir)]
        )

        assert result.exit_code == 1


@pytest.mark.unit
class TestSystemCommands:
    """``status`` / ``diagnose`` / ``launch`` 命令。"""

    def test_status_exits_zero(self, cli_runner: CliRunner, config_path: Path) -> None:
        """状态命令应成功。"""
        result = cli_runner.invoke(app, ["status", "--config", str(config_path)])

        assert result.exit_code == 0
        assert "official" in result.stdout

    def test_diagnose_exits_zero(
        self, cli_runner: CliRunner, config_path: Path
    ) -> None:
        """诊断命令应成功。"""
        result = cli_runner.invoke(app, ["diagnose", "--config", str(config_path)])

        assert result.exit_code == 0

    def test_diagnose_writes_report_file(
        self, cli_runner: CliRunner, config_path: Path, tmp_path: Path
    ) -> None:
        """``--output`` 应把报告写入文件。"""
        report = tmp_path / "report.json"

        result = cli_runner.invoke(
            app,
            [
                "diagnose",
                "--output",
                str(report),
                "--config",
                str(config_path),
            ],
        )

        assert result.exit_code == 0
        assert report.exists()

    def test_launch_status_exits_zero(
        self, cli_runner: CliRunner, config_path: Path
    ) -> None:
        """未运行时状态命令应成功。"""
        result = cli_runner.invoke(
            app, ["launch", "status", "--config", str(config_path)]
        )

        assert result.exit_code == 0
        assert "未在本会话中运行" in result.stdout

    def test_launch_stop_exits_zero(
        self, cli_runner: CliRunner, config_path: Path
    ) -> None:
        """无进程时停止命令应成功。"""
        result = cli_runner.invoke(
            app, ["launch", "stop", "--config", str(config_path)]
        )

        assert result.exit_code == 0

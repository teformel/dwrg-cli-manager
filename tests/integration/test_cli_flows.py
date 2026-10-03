"""
CLI 端到端流程集成测试

用真实命令拼接出一条完整工作流：建配置 → 加渠道服 → 加账号 → 切换 →
导出/导入 → 查看状态，验证各命令之间的数据是连贯的。所有命令均通过
``--config`` 指向临时文件，不触碰真实用户配置。
"""

from pathlib import Path
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

from dwrg_manager.cli import app


def _read_config(path: Path) -> dict[str, Any]:
    """读取并解析 YAML 配置文件。

    Args:
        path: 配置文件路径。

    Returns:
        解析后的字典。
    """
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


@pytest.mark.integration
class TestCliWorkflow:
    """跨命令的端到端流程。"""

    def test_full_lifecycle_from_setup_to_status(
        self, cli_runner: CliRunner, config_path: Path, tmp_path: Path
    ) -> None:
        """从设置配置到查看状态的主流程应全部成功且数据连贯。"""
        config = str(config_path)

        set_result = cli_runner.invoke(
            app, ["config", "set", "log_level", "DEBUG", "--config", config]
        )
        assert set_result.exit_code == 0

        add_server = cli_runner.invoke(
            app,
            [
                "server",
                "add",
                "guild",
                "-e",
                "https://g.example",
                "--default",
                "--config",
                config,
            ],
        )
        assert add_server.exit_code == 0
        assert _read_config(config_path)["app"]["server"] == "guild"

        add_account = cli_runner.invoke(
            app,
            [
                "account",
                "add",
                "-u",
                "hero",
                "-p",
                "secret123",
                "-s",
                "guild",
                "--config",
                config,
            ],
        )
        assert add_account.exit_code == 0

        listed = cli_runner.invoke(app, ["account", "list", "--config", config])
        assert listed.exit_code == 0
        assert "hero" in listed.stdout

        account_id = next(iter(_read_config(config_path)["accounts"]))
        switched = cli_runner.invoke(
            app, ["account", "switch", account_id, "--config", config]
        )
        assert switched.exit_code == 0
        assert _read_config(config_path)["app"]["account"] == account_id

        status = cli_runner.invoke(app, ["status", "--config", config])
        assert status.exit_code == 0
        assert "guild" in status.stdout
        assert "hero" in status.stdout

        export_path = tmp_path / "export.yaml"
        exported = cli_runner.invoke(
            app, ["config", "export", str(export_path), "--config", config]
        )
        assert exported.exit_code == 0
        assert export_path.exists()

    def test_export_then_import_into_new_profile(
        self, cli_runner: CliRunner, config_path: Path, tmp_path: Path
    ) -> None:
        """导出到新配置文件的导入结果应保留渠道服与账号。"""
        config = str(config_path)
        cli_runner.invoke(app, ["server", "add", "guild", "--config", config])
        cli_runner.invoke(
            app,
            [
                "account",
                "add",
                "-u",
                "mage",
                "-p",
                "secret123",
                "-s",
                "guild",
                "--config",
                config,
            ],
        )
        export_path = tmp_path / "profile.yaml"
        cli_runner.invoke(
            app, ["config", "export", str(export_path), "--config", config]
        )

        new_config = tmp_path / "new.yaml"
        imported = cli_runner.invoke(
            app, ["config", "import", str(export_path), "--config", str(new_config)]
        )

        assert imported.exit_code == 0
        servers = cli_runner.invoke(
            app, ["server", "list", "-f", "json", "--config", str(new_config)]
        )
        assert "guild" in servers.stdout
        accounts = cli_runner.invoke(
            app, ["account", "list", "-f", "json", "--config", str(new_config)]
        )
        assert "mage" in accounts.stdout

    def test_switch_server_updates_current_and_survives_reload(
        self, cli_runner: CliRunner, config_path: Path
    ) -> None:
        """切换渠道服后重新加载配置应仍是切换后的结果。"""
        config = str(config_path)
        switched = cli_runner.invoke(
            app, ["server", "switch", "bserver", "--force", "--config", config]
        )

        assert switched.exit_code == 0
        current = cli_runner.invoke(app, ["server", "current", "--config", config])
        assert current.exit_code == 0
        assert "bserver" in current.stdout
        assert _read_config(config_path)["app"]["server"] == "bserver"

    def test_account_login_then_logout_clears_session(
        self, cli_runner: CliRunner, config_path: Path
    ) -> None:
        """登录后登出应清空当前账号。"""
        config = str(config_path)
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
                config,
            ],
        )
        account_id = next(iter(_read_config(config_path)["accounts"]))
        login = cli_runner.invoke(
            app, ["account", "login", account_id, "--config", config]
        )
        assert login.exit_code == 0
        assert _read_config(config_path)["app"]["account"] == account_id

        logout = cli_runner.invoke(app, ["account", "logout", "--config", config])

        assert logout.exit_code == 0
        assert _read_config(config_path)["app"]["account"] is None

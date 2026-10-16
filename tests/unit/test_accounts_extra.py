"""
账号扩展能力单元测试

覆盖 :mod:`dwrg_manager.accounts.session`（登录态读写与权限）、
:mod:`dwrg_manager.accounts.transfer`（加密导出 / 导入往返与损坏文件）、
:mod:`dwrg_manager.accounts.gacha`（日志解析与加密提示）以及
``account export`` / ``account import`` / ``gacha`` CLI 命令。

所有路径均由 conftest 的隔离夹具重定向到 ``tmp_path``，测试不会读写
真实的 ``~/.dwrg`` 与 ``~/.config/dwrg``。
"""

import json
import os
import stat
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from dwrg_manager.accounts import AccountManager, Session
from dwrg_manager.accounts import gacha as gacha_module
from dwrg_manager.accounts.gacha import extract_gacha_urls, open_url, scan_gacha_logs
from dwrg_manager.accounts.session import (
    clear_session,
    default_session_path,
    get_active_session,
    read_session,
    session_env_vars,
    write_session,
)
from dwrg_manager.cli import app
from dwrg_manager.exceptions import AccountError

VALID_ID = "acc-00000001"
PASSWORD = "secret123"


def _account_id(config_path: Path) -> str:
    """从 YAML 配置中取出首个账号 ID。

    Args:
        config_path: 配置文件路径。

    Returns:
        首个账号的 ID。
    """
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return next(iter(data["accounts"]))


@pytest.mark.unit
class TestSessionModel:
    """``Session`` 模型与路径解析。"""

    def test_defaults_fill_optional_fields(self) -> None:
        """除 ``account_id`` 外均有默认值，token 使用占位符。"""
        session = Session(account_id=VALID_ID)

        assert session.server == ""
        assert session.token == "pending"
        assert session.version == 1

    def test_short_account_id_is_rejected(self) -> None:
        """过短的账号 ID 应被拒绝。"""
        from pydantic import ValidationError as PydanticValidationError

        with pytest.raises(PydanticValidationError):
            Session(account_id="short")

    def test_account_id_is_stripped(self) -> None:
        """账号 ID 首尾空白应被去除。"""
        session = Session(account_id=f"  {VALID_ID}  ")

        assert session.account_id == VALID_ID

    def test_default_session_path_follows_home(self) -> None:
        """默认路径应随 ``HOME`` 重定向到临时目录。"""
        expected = Path.home() / ".dwrg" / "session.json"

        assert default_session_path() == expected

    def test_session_env_vars_maps_fields(self) -> None:
        """登录态应映射为启动器环境变量。"""
        session = Session(account_id=VALID_ID, server="official", username="hero")

        env = session_env_vars(session)

        assert env["DWRG_ACCOUNT"] == VALID_ID
        assert env["DWRG_SERVER"] == "official"
        assert env["DWRG_ACCOUNT_NAME"] == "hero"

    def test_session_env_vars_without_session_is_empty(self) -> None:
        """未登录时环境变量字典应为空。"""
        assert session_env_vars(None) == {}


@pytest.mark.unit
class TestSessionPersistence:
    """登录态的写入、读取、清除与容错。"""

    def test_write_then_read_roundtrips(self, tmp_path: Path) -> None:
        """写入后应能读回等价对象。"""
        target = tmp_path / "session.json"
        session = Session(account_id=VALID_ID, server="official", username="hero")

        written = write_session(session, target)
        restored = read_session(target)

        assert written == target
        assert restored == session

    def test_written_file_is_json_without_plaintext_secrets(
        self, tmp_path: Path
    ) -> None:
        """登录态文件应为合法 JSON 且不含密码明文。"""
        target = tmp_path / "session.json"

        write_session(Session(account_id=VALID_ID), target)

        raw = target.read_text(encoding="utf-8")
        assert PASSWORD not in raw
        assert json.loads(raw)["account_id"] == VALID_ID

    @pytest.mark.skipif(os.name != "posix", reason="POSIX 权限位仅在类 Unix 平台有意义")
    def test_written_file_has_owner_only_permission(self, tmp_path: Path) -> None:
        """登录态文件权限应为 0600。"""
        target = tmp_path / "session.json"

        write_session(Session(account_id=VALID_ID), target)

        mode = stat.S_IMODE(target.stat().st_mode)
        assert mode == 0o600

    def test_read_missing_file_returns_none(self, tmp_path: Path) -> None:
        """文件不存在时返回 ``None`` 而不抛异常。"""
        assert read_session(tmp_path / "nope.json") is None

    def test_read_corrupted_json_returns_none(self, tmp_path: Path) -> None:
        """JSON 损坏时应降级为未登录。"""
        target = tmp_path / "session.json"
        target.write_text("{not json", encoding="utf-8")

        assert read_session(target) is None

    def test_read_non_object_json_returns_none(self, tmp_path: Path) -> None:
        """顶层不是对象时应降级为未登录。"""
        target = tmp_path / "session.json"
        target.write_text("[1, 2]", encoding="utf-8")

        assert read_session(target) is None

    def test_read_invalid_fields_returns_none(self, tmp_path: Path) -> None:
        """字段不合法时应降级为未登录。"""
        target = tmp_path / "session.json"
        target.write_text(json.dumps({"account_id": "short"}), encoding="utf-8")

        assert read_session(target) is None

    def test_clear_session_is_idempotent(self, tmp_path: Path) -> None:
        """重复清除登录态是幂等的。"""
        target = tmp_path / "session.json"
        write_session(Session(account_id=VALID_ID), target)

        assert clear_session(target) is True
        assert clear_session(target) is False
        assert not target.exists()

    def test_get_active_session_uses_default_path(self) -> None:
        """``get_active_session`` 默认读取 ``~/.dwrg/session.json``。"""
        write_session(Session(account_id=VALID_ID))

        session = get_active_session()

        assert session is not None
        assert session.account_id == VALID_ID
        assert default_session_path().exists()

    def test_default_path_is_isolated_from_real_home(self) -> None:
        """默认路径必须落在被隔离的临时 HOME 下。"""
        path = default_session_path()

        assert str(path).startswith(str(Path.home()))


@pytest.mark.unit
class TestManagerLoginLogout:
    """``AccountManager`` 的登录态写入与登出清除。"""

    def test_login_writes_session_file(
        self, account_manager: AccountManager, config_manager, tmp_path: Path
    ) -> None:
        """登录成功后应写入登录态文件。"""
        account = account_manager.create_account("hero", "official", PASSWORD)
        session_file = tmp_path / "session.json"
        account_manager._session_file = session_file

        result = account_manager.login(account.id)

        assert result.success is True
        assert session_file.exists()
        session = read_session(session_file)
        assert session is not None
        assert session.account_id == account.id
        assert session.server == "official"
        assert session.username == "hero"

    def test_login_session_file_has_no_plaintext_password(
        self, account_manager: AccountManager, tmp_path: Path
    ) -> None:
        """登录态文件不得包含密码明文。"""
        account = account_manager.create_account("hero", "official", PASSWORD)
        session_file = tmp_path / "session.json"
        account_manager._session_file = session_file

        account_manager.login(account.id)

        assert PASSWORD not in session_file.read_text(encoding="utf-8")

    def test_login_with_unknown_account_writes_no_session(
        self, account_manager: AccountManager, tmp_path: Path
    ) -> None:
        """登录失败时不应产生登录态文件。"""
        session_file = tmp_path / "session.json"
        account_manager._session_file = session_file

        result = account_manager.login("nope")

        assert result.success is False
        assert not session_file.exists()

    def test_logout_clears_session_and_config(
        self, account_manager: AccountManager, config_manager, tmp_path: Path
    ) -> None:
        """登出应同时清除登录态与配置中的当前账号。"""
        account = account_manager.create_account("hero", "official", PASSWORD)
        session_file = tmp_path / "session.json"
        account_manager._session_file = session_file
        account_manager.login(account.id)

        account_manager.logout()

        assert not session_file.exists()
        assert account_manager.get_session() is None
        assert account_manager.get_current_account() is None
        assert account_manager.get_account(account.id).is_current is False

    def test_logout_without_session_is_idempotent(
        self, account_manager: AccountManager, tmp_path: Path
    ) -> None:
        """从未登录时登出不应抛异常。"""
        session_file = tmp_path / "session.json"
        account_manager._session_file = session_file

        assert account_manager.logout() is False

    def test_session_file_injection_is_used_by_manager(
        self, account_manager: AccountManager, tmp_path: Path
    ) -> None:
        """``get_session`` 应读取自定义登录态路径。"""
        session_file = tmp_path / "session.json"
        write_session(Session(account_id=VALID_ID, username="hero"), session_file)
        account_manager._session_file = session_file

        session = account_manager.get_session()

        assert session is not None
        assert session.username == "hero"


@pytest.mark.unit
class TestExportImport:
    """账号加密导出与导入。"""

    def test_export_creates_single_file_with_encrypted_payload(
        self, account_manager: AccountManager, tmp_path: Path
    ) -> None:
        """导出应生成单文件且密码不明文落盘。"""
        account_manager.create_account("hero", "official", PASSWORD)
        target = tmp_path / "backup.dwrg"

        written = account_manager.export_accounts(target)

        assert written == target
        raw = target.read_text(encoding="utf-8")
        assert PASSWORD not in raw
        assert "hero" not in raw
        envelope = json.loads(raw)
        assert envelope["magic"] == "dwrg-account-export"
        assert envelope["count"] == 1
        assert envelope["payload"]

    def test_export_without_accounts_raises(
        self, account_manager: AccountManager, tmp_path: Path
    ) -> None:
        """没有账号时导出应抛出 :class:`AccountError`。"""
        with pytest.raises(AccountError):
            account_manager.export_accounts(tmp_path / "backup.dwrg")

    def test_export_then_import_roundtrips(
        self, account_manager: AccountManager, config_manager, tmp_path: Path
    ) -> None:
        """导出后导入到全新配置应还原账号与可解密的密码。"""
        account = account_manager.create_account("hero", "official", PASSWORD)
        target = tmp_path / "backup.dwrg"
        account_manager.export_accounts(target)

        fresh = AccountManager(config_manager)
        fresh.config_manager.config.accounts.clear()
        report = fresh.import_accounts(target)

        assert report.imported == 1
        assert report.overwritten == 0
        assert report.skipped == 0
        restored = fresh.get_account(account.id)
        assert restored is not None
        assert restored.username == "hero"
        assert restored.encrypted_password == account.encrypted_password
        assert restored.password_hash == account.password_hash
        assert fresh.get_password(account.id) == PASSWORD

    def test_import_skips_existing_id_without_force(
        self, account_manager: AccountManager, tmp_path: Path
    ) -> None:
        """ID 冲突时默认跳过。"""
        account = account_manager.create_account("hero", "official", PASSWORD)
        target = tmp_path / "backup.dwrg"
        account_manager.export_accounts(target)

        report = account_manager.import_accounts(target)

        assert report.imported == 0
        assert report.skipped == 1
        assert account_manager.get_account(account.id) is not None

    def test_import_with_force_overwrites_existing_id(
        self, account_manager: AccountManager, tmp_path: Path
    ) -> None:
        """``--force`` 应覆盖已存在的账号。"""
        account = account_manager.create_account("hero", "official", PASSWORD)
        target = tmp_path / "backup.dwrg"
        account_manager.export_accounts(target)
        account_manager.set_password(account.id, "changed99")

        report = account_manager.import_accounts(target, force=True)

        assert report.overwritten == 1
        assert account_manager.get_password(account.id) == PASSWORD

    def test_import_missing_file_raises(
        self, account_manager: AccountManager, tmp_path: Path
    ) -> None:
        """导入不存在的文件应抛出 :class:`AccountError`。"""
        with pytest.raises(AccountError):
            account_manager.import_accounts(tmp_path / "missing.dwrg")

    def test_import_corrupted_file_raises(
        self, account_manager: AccountManager, tmp_path: Path
    ) -> None:
        """损坏的导出文件应抛出 :class:`AccountError`。"""
        target = tmp_path / "broken.dwrg"
        target.write_text("{not json", encoding="utf-8")

        with pytest.raises(AccountError):
            account_manager.import_accounts(target)

    def test_import_file_with_wrong_magic_raises(
        self, account_manager: AccountManager, tmp_path: Path
    ) -> None:
        """非 dwrg 导出文件应被拒绝。"""
        target = tmp_path / "other.json"
        target.write_text(
            json.dumps({"magic": "something-else", "version": 1, "payload": "x"}),
            encoding="utf-8",
        )

        with pytest.raises(AccountError):
            account_manager.import_accounts(target)

    def test_import_tampered_payload_raises(
        self, account_manager: AccountManager, tmp_path: Path
    ) -> None:
        """载荷被篡改时应因解密失败而报错。"""
        account_manager.create_account("hero", "official", PASSWORD)
        target = tmp_path / "backup.dwrg"
        account_manager.export_accounts(target)
        envelope = json.loads(target.read_text(encoding="utf-8"))
        envelope["payload"] = "AAAA" + envelope["payload"][4:]
        target.write_text(json.dumps(envelope), encoding="utf-8")

        with pytest.raises(AccountError):
            account_manager.import_accounts(target)

    def test_import_missing_server_raises(
        self, account_manager: AccountManager, config_manager, tmp_path: Path
    ) -> None:
        """导出材料中的渠道服不存在时应报错。"""
        account_manager.create_account("hero", "official", PASSWORD)
        target = tmp_path / "backup.dwrg"
        account_manager.export_accounts(target)
        config_manager.config.servers.clear()

        with pytest.raises(AccountError):
            account_manager.import_accounts(target)

    def test_import_preserves_current_account_flag(
        self, account_manager: AccountManager, config_manager, tmp_path: Path
    ) -> None:
        """覆盖导入不应破坏当前账号标记。"""
        account = account_manager.create_account("hero", "official", PASSWORD)
        account_manager.switch_account(account.id)
        target = tmp_path / "backup.dwrg"
        account_manager.export_accounts(target)

        account_manager.import_accounts(target, force=True)

        assert account_manager.get_account(account.id).is_current is True


@pytest.mark.unit
class TestGachaLogParsing:
    """抽卡记录日志扫描。"""

    def test_extract_urls_returns_gacha_links(self) -> None:
        """应从日志文本中提取抽卡记录链接。"""
        text = (
            "open https://idv.163.com/gacha/record?server_id=1 "
            "then http://game.bilibili.com/idv/gacha/index.html done"
        )

        urls = extract_gacha_urls(text)

        assert len(urls) == 2
        assert urls[0].startswith("https://idv.163.com/gacha")

    def test_extract_urls_deduplicates_and_keeps_order(self) -> None:
        """重复链接应去重并保持出现顺序。"""
        text = (
            "https://idv.163.com/gacha/record?x=1 "
            "https://other.example.com/draw "
            "https://idv.163.com/gacha/record?x=1"
        )

        urls = extract_gacha_urls(text)

        assert urls == [
            "https://idv.163.com/gacha/record?x=1",
            "https://other.example.com/draw",
        ]

    def test_extract_urls_ignores_plain_urls(self) -> None:
        """不含关键词的链接应被忽略。"""
        assert extract_gacha_urls("see https://example.com/home for info") == []

    def test_extract_urls_strips_trailing_punctuation(self) -> None:
        """链接尾部的标点应被剔除。"""
        urls = extract_gacha_urls("visit https://idv.163.com/gacha/record, ok")

        assert urls == ["https://idv.163.com/gacha/record"]

    def test_scan_missing_directory_reports_gracefully(self) -> None:
        """目录不存在时应给出提示而不抛异常。"""
        result = scan_gacha_logs(Path("/definitely/not/here"))

        assert result.found is False
        assert result.encrypted is False
        assert result.message

    def test_scan_reads_log_files_in_directory(self, tmp_path: Path) -> None:
        """应扫描目录中的日志文件并汇总链接。"""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        (log_dir / "a.log").write_text(
            "url https://idv.163.com/gacha/record?server_id=1", encoding="utf-8"
        )
        (log_dir / "b.txt").write_text(
            "url https://game.bilibili.com/idv/gacha/index", encoding="utf-8"
        )
        (log_dir / "c.bin").write_text("ignored", encoding="utf-8")

        result = scan_gacha_logs(log_dir)

        assert result.found is True
        assert result.log_dir == log_dir
        assert result.scanned_files == 2
        assert len(result.urls) == 2

    def test_scan_detects_encrypted_logs(self, tmp_path: Path) -> None:
        """日志加密时应返回提示而不抛异常。"""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        (log_dir / "a.log").write_text(
            "gAAAAABabcdefghijklmnopqrstuvwxyz012345", encoding="utf-8"
        )

        result = scan_gacha_logs(log_dir)

        assert result.encrypted is True
        assert result.found is False
        assert "加密" in result.message

    def test_scan_without_links_reports_message(self, tmp_path: Path) -> None:
        """没有链接时应给出未找到提示。"""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        (log_dir / "a.log").write_text("nothing here", encoding="utf-8")

        result = scan_gacha_logs(log_dir)

        assert result.found is False
        assert "未" in result.message

    def test_scan_skips_oversized_files(self, tmp_path: Path) -> None:
        """超大日志文件应被跳过。"""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        big = log_dir / "big.log"
        big.write_text("x" * (gacha_module.MAX_LOG_BYTES + 10), encoding="utf-8")

        result = scan_gacha_logs(log_dir)

        assert result.scanned_files == 0

    def test_open_url_returns_false_when_browser_unavailable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """浏览器不可用时应返回 ``False`` 而不抛异常。"""

        def boom(*_args: object, **_kwargs: object) -> bool:  # noqa: ARG001
            raise RuntimeError("no browser")

        monkeypatch.setattr(gacha_module.webbrowser, "open", boom)

        assert open_url("https://example.com") is False

    def test_open_url_delegates_to_webbrowser(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """打开链接应委托给 :mod:`webbrowser`。"""
        opened: list[str] = []

        def fake_open(url: str, *_args: object, **_kwargs: object) -> bool:
            opened.append(url)
            return True

        monkeypatch.setattr(gacha_module.webbrowser, "open", fake_open)

        assert open_url("https://idv.163.com/gacha") is True
        assert opened == ["https://idv.163.com/gacha"]


@pytest.mark.unit
class TestAccountCliCommands:
    """``account export`` / ``account import`` / ``gacha`` CLI 命令。"""

    def test_export_command_writes_file(
        self, cli_runner: CliRunner, config_path: Path, tmp_path: Path
    ) -> None:
        """导出命令应创建加密文件。"""
        cli_runner.invoke(
            app,
            [
                "account",
                "add",
                "-u",
                "hero",
                "-p",
                PASSWORD,
                "--config",
                str(config_path),
            ],
        )
        target = tmp_path / "backup.dwrg"

        result = cli_runner.invoke(
            app, ["account", "export", str(target), "--config", str(config_path)]
        )

        assert result.exit_code == 0
        assert target.exists()
        assert PASSWORD not in target.read_text(encoding="utf-8")

    def test_export_command_without_accounts_fails(
        self, cli_runner: CliRunner, config_path: Path, tmp_path: Path
    ) -> None:
        """没有账号时导出命令应以 1 退出。"""
        result = cli_runner.invoke(
            app,
            [
                "account",
                "export",
                str(tmp_path / "b.dwrg"),
                "--config",
                str(config_path),
            ],
        )

        assert result.exit_code == 1

    def test_import_command_merges_accounts(
        self, cli_runner: CliRunner, config_path: Path, tmp_path: Path
    ) -> None:
        """导入命令应把账号合并进配置。"""
        cli_runner.invoke(
            app,
            [
                "account",
                "add",
                "-u",
                "hero",
                "-p",
                PASSWORD,
                "--config",
                str(config_path),
            ],
        )
        source = tmp_path / "backup.dwrg"
        cli_runner.invoke(
            app, ["account", "export", str(source), "--config", str(config_path)]
        )
        empty_config = tmp_path / "empty.yaml"

        result = cli_runner.invoke(
            app,
            ["account", "import", str(source), "--config", str(empty_config)],
        )

        assert result.exit_code == 0
        data = yaml.safe_load(empty_config.read_text(encoding="utf-8"))
        assert data["accounts"]
        assert PASSWORD not in empty_config.read_text(encoding="utf-8")

    def test_import_command_with_force_overwrites(
        self, cli_runner: CliRunner, config_path: Path, tmp_path: Path
    ) -> None:
        """``--force`` 导入应成功覆盖。"""
        cli_runner.invoke(
            app,
            [
                "account",
                "add",
                "-u",
                "hero",
                "-p",
                PASSWORD,
                "--config",
                str(config_path),
            ],
        )
        source = tmp_path / "backup.dwrg"
        cli_runner.invoke(
            app, ["account", "export", str(source), "--config", str(config_path)]
        )

        result = cli_runner.invoke(
            app,
            [
                "account",
                "import",
                str(source),
                "--force",
                "--config",
                str(config_path),
            ],
        )

        assert result.exit_code == 0
        assert "覆盖" in result.stdout

    def test_import_command_skips_existing_without_force(
        self, cli_runner: CliRunner, config_path: Path, tmp_path: Path
    ) -> None:
        """不带 ``--force`` 时应提示跳过。"""
        cli_runner.invoke(
            app,
            [
                "account",
                "add",
                "-u",
                "hero",
                "-p",
                PASSWORD,
                "--config",
                str(config_path),
            ],
        )
        source = tmp_path / "backup.dwrg"
        cli_runner.invoke(
            app, ["account", "export", str(source), "--config", str(config_path)]
        )

        result = cli_runner.invoke(
            app, ["account", "import", str(source), "--config", str(config_path)]
        )

        assert result.exit_code == 0
        assert "跳过" in result.stdout

    def test_import_command_with_corrupted_file_fails(
        self, cli_runner: CliRunner, config_path: Path, tmp_path: Path
    ) -> None:
        """损坏文件应以 1 退出。"""
        broken = tmp_path / "broken.dwrg"
        broken.write_text("{not json", encoding="utf-8")

        result = cli_runner.invoke(
            app, ["account", "import", str(broken), "--config", str(config_path)]
        )

        assert result.exit_code == 1

    def test_import_command_with_missing_file_fails(
        self, cli_runner: CliRunner, config_path: Path, tmp_path: Path
    ) -> None:
        """导入不存在的文件应以 1 退出。"""
        result = cli_runner.invoke(
            app,
            [
                "account",
                "import",
                str(tmp_path / "missing.dwrg"),
                "--config",
                str(config_path),
            ],
        )

        assert result.exit_code == 1

    def test_login_command_writes_session_file(
        self, cli_runner: CliRunner, config_path: Path, tmp_path: Path
    ) -> None:
        """登录命令应写入默认登录态文件。"""
        cli_runner.invoke(
            app,
            [
                "account",
                "add",
                "-u",
                "hero",
                "-p",
                PASSWORD,
                "--config",
                str(config_path),
            ],
        )
        account_id = _account_id(config_path)

        result = cli_runner.invoke(
            app,
            ["account", "login", account_id, "--config", str(config_path)],
        )

        assert result.exit_code == 0
        assert default_session_path().exists()
        assert read_session().account_id == account_id

    def test_logout_command_clears_session_file(
        self, cli_runner: CliRunner, config_path: Path, tmp_path: Path
    ) -> None:
        """登出命令应删除登录态文件。"""
        cli_runner.invoke(
            app,
            [
                "account",
                "add",
                "-u",
                "hero",
                "-p",
                PASSWORD,
                "--config",
                str(config_path),
            ],
        )
        account_id = _account_id(config_path)
        cli_runner.invoke(
            app,
            ["account", "login", account_id, "--config", str(config_path)],
        )
        assert default_session_path().exists()

        result = cli_runner.invoke(
            app, ["account", "logout", "--config", str(config_path)]
        )

        assert result.exit_code == 0
        assert not default_session_path().exists()

    def test_gacha_command_with_dir_lists_urls(
        self, cli_runner: CliRunner, tmp_path: Path
    ) -> None:
        """``gacha --dir`` 应列出找到的链接。"""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        (log_dir / "a.log").write_text(
            "https://idv.163.com/gacha/record?server_id=1", encoding="utf-8"
        )

        result = cli_runner.invoke(app, ["gacha", "--dir", str(log_dir)])

        assert result.exit_code == 0
        assert "gacha/record" in result.stdout

    def test_gacha_command_reports_encrypted_logs(
        self, cli_runner: CliRunner, tmp_path: Path
    ) -> None:
        """日志加密时应给出明确提示。"""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        (log_dir / "a.log").write_text(
            "gAAAAABabcdefghijklmnopqrstuvwxyz012345", encoding="utf-8"
        )

        result = cli_runner.invoke(app, ["gacha", "--dir", str(log_dir)])

        assert result.exit_code == 0
        assert "加密" in result.stdout

    def test_gacha_command_without_links_warns(
        self, cli_runner: CliRunner, tmp_path: Path
    ) -> None:
        """没有链接时应提示且以 0 退出。"""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        result = cli_runner.invoke(app, ["gacha", "--dir", str(log_dir)])

        assert result.exit_code == 0
        assert "未" in result.stdout

    def test_gacha_command_open_uses_webbrowser(
        self, cli_runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``-o`` 应调用浏览器打开第一条链接。"""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        (log_dir / "a.log").write_text(
            "https://idv.163.com/gacha/record?server_id=1", encoding="utf-8"
        )
        opened: list[str] = []

        def fake_open(url: str, *_args: object, **_kwargs: object) -> bool:
            opened.append(url)
            return True

        monkeypatch.setattr(gacha_module.webbrowser, "open", fake_open)

        result = cli_runner.invoke(app, ["gacha", "--dir", str(log_dir), "-o"])

        assert result.exit_code == 0
        assert opened == ["https://idv.163.com/gacha/record?server_id=1"]

    def test_gacha_scan_alias_behaves_like_gacha(
        self, cli_runner: CliRunner, tmp_path: Path
    ) -> None:
        """``gacha scan`` 应与 ``gacha`` 行为一致。"""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        (log_dir / "a.log").write_text(
            "https://idv.163.com/gacha/record?server_id=1", encoding="utf-8"
        )

        result = cli_runner.invoke(app, ["gacha", "scan", "--dir", str(log_dir)])

        assert result.exit_code == 0
        assert "gacha/record" in result.stdout

    def test_gacha_help_exits_zero(self, cli_runner: CliRunner) -> None:
        """``gacha --help`` 应正常退出。"""
        assert cli_runner.invoke(app, ["gacha", "--help"]).exit_code == 0

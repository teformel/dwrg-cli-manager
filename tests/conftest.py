"""
全局测试夹具

本模块提供隔离的运行环境，确保任何测试都不会读写真实的 ``~/.config/dwrg``
与 ``~/.dwrg``：

* 通过 ``monkeypatch`` 把 ``HOME`` / ``USERPROFILE`` / ``XDG_CONFIG_HOME``
  重定向到 ``tmp_path``，使 :func:`dwrg_manager.config.manager.default_config_path`
  与 :func:`pathlib.Path.home` 都落在临时目录；
* 通过 ``DWRG_KEY_FILE`` 指定临时密钥文件，并清空 ``DWRG_ENCRYPTION_KEY``，
  避免进程级 :class:`~dwrg_manager.security.crypto.CryptoManager` 单例使用真实密钥；
* 每个测试前后调用 :func:`reset_crypto_manager` 丢弃单例缓存。

Example:
    >>> def test_demo(config_manager):  # doctest: +SKIP
    ...     assert config_manager.get_app_config().language == "zh-CN"
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dwrg_manager.accounts import AccountManager
from dwrg_manager.config import ConfigManager
from dwrg_manager.security.crypto import reset_crypto_manager
from dwrg_manager.servers import ServerManager

__all__ = [
    "account_manager",
    "cli_runner",
    "config_manager",
    "config_path",
    "isolated_environment",
]


@pytest.fixture(autouse=True)
def isolated_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Path]:
    """把所有可能落盘的路径重定向到临时目录。

    该夹具为 ``autouse``，因此每个测试都自动生效，无需显式声明。

    Args:
        tmp_path: pytest 提供的临时目录。
        monkeypatch: pytest 提供的环境变量打补丁工具。

    Yields:
        作为「用户主目录」使用的临时目录。
    """
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.delenv("DWRG_ENCRYPTION_KEY", raising=False)
    monkeypatch.setenv("DWRG_KEY_FILE", str(home / ".dwrg" / "keyfile"))

    reset_crypto_manager()
    try:
        yield home
    finally:
        reset_crypto_manager()


@pytest.fixture
def config_path(tmp_path: Path) -> Path:
    """返回位于临时目录中的配置文件路径。

    Args:
        tmp_path: pytest 提供的临时目录。

    Returns:
        形如 ``<tmp>/config.yaml`` 的路径。
    """
    return tmp_path / "config.yaml"


@pytest.fixture
def config_manager(config_path: Path) -> ConfigManager:
    """返回指向临时配置文件的 :class:`~dwrg_manager.config.ConfigManager`。

    Args:
        config_path: 临时配置文件路径。

    Returns:
        未自动落盘的配置管理器实例。
    """
    return ConfigManager(config_path, autosave=False)


@pytest.fixture
def account_manager(config_manager: ConfigManager) -> AccountManager:
    """返回绑定了隔离配置的账号管理器。

    Args:
        config_manager: 隔离的配置管理器。

    Returns:
        :class:`~dwrg_manager.accounts.AccountManager` 实例。
    """
    return AccountManager(config_manager)


@pytest.fixture
def server_manager(config_manager: ConfigManager) -> ServerManager:
    """返回绑定了隔离配置的渠道服管理器。

    Args:
        config_manager: 隔离的配置管理器。

    Returns:
        :class:`~dwrg_manager.servers.ServerManager` 实例。
    """
    return ServerManager(config_manager)


@pytest.fixture
def cli_runner() -> CliRunner:
    """返回 Typer 的命令行测试运行器。

    Returns:
        全新的 :class:`typer.testing.CliRunner` 实例。
    """
    return CliRunner()

"""
配置管理器

负责应用配置的持久化读写与业务级 CRUD。配置文件默认位于
``~/.config/dwrg/config.yaml``，支持 YAML 与 JSON 两种格式（按扩展名判断）。

设计要点：

* **原子写入**：先写同目录临时文件再 ``os.replace``，避免写入中断导致配置损坏。
* **字符串友好**：``set_config`` 接受来自命令行的字符串值，依赖 Pydantic
  的宽松模式自动完成 ``"8" -> 8``、``"true" -> True`` 一类的类型转换。
* **首次运行自举**：配置文件不存在时写入预置了默认渠道服的初始配置。
"""

import json
import os
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from ..exceptions import ConfigError, ValidationError
from ..security.crypto import encrypt_data, hash_password
from ..utils.logger import get_logger
from .models import (
    DEFAULT_SERVER_NAMES,
    AccountConfig,
    AppConfig,
    Config,
    ServerConfig,
    default_config,
)

logger = get_logger(__name__)

#: 可被 :meth:`ConfigManager.set_config` 直接操作的顶层配置项
SETTABLE_KEYS: tuple[str, ...] = tuple(AppConfig.model_fields)


class _DateTimeEncoder(json.JSONEncoder):
    """支持 ``datetime`` 的 JSON 编码器。"""

    def default(self, o: Any) -> Any:
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)  # pragma: no cover - 由父类抛出 TypeError


def default_config_path() -> Path:
    """返回默认配置文件路径。

    Returns:
        ``~/.config/dwrg/config.yaml``。
    """
    return Path.home() / ".config" / "dwrg" / "config.yaml"


class ConfigManager:
    """配置管理器。

    Args:
        config_path: 自定义配置文件路径；为 ``None`` 时使用默认路径。
        autosave: 是否在每次修改后自动落盘。

    Raises:
        ConfigError: 配置文件存在但无法解析。

    Example:
        >>> manager = ConfigManager("/tmp/dwrg-test.yaml")  # doctest: +SKIP
        >>> manager.get_app_config().language  # doctest: +SKIP
        'zh-CN'
    """

    def __init__(
        self, config_path: str | Path | None = None, *, autosave: bool = True
    ) -> None:
        self.logger = get_logger(__name__)
        self.config_path = (
            Path(config_path).expanduser() if config_path else default_config_path()
        )
        self.autosave = autosave
        self.config: Config = self._load_config()

    # ------------------------------------------------------------------ #
    # 读写
    # ------------------------------------------------------------------ #
    def _load_config(self) -> Config:
        """从磁盘加载配置；不存在时创建初始配置。

        Returns:
            解析后的 :class:`Config`。

        Raises:
            ConfigError: 文件存在但内容非法。
        """
        if not self.config_path.exists():
            config = default_config()
            if self.autosave:
                try:
                    self.save_config(config)
                    self.logger.info("已创建默认配置文件: %s", self.config_path)
                except ConfigError as exc:  # pragma: no cover - 依赖文件系统
                    self.logger.warning("初始配置写入失败: %s", exc)
            return config

        try:
            text = self.config_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ConfigError("配置文件读取失败", path=str(self.config_path)) from exc

        try:
            if self.config_path.suffix.lower() == ".json":
                data = json.loads(text) if text.strip() else {}
            else:
                data = yaml.safe_load(text) or {}
        except (json.JSONDecodeError, yaml.YAMLError) as exc:
            raise ConfigError(
                "配置文件解析失败", path=str(self.config_path), reason=str(exc)
            ) from exc

        if not isinstance(data, dict):
            raise ConfigError("配置文件根节点必须是映射", path=str(self.config_path))

        try:
            return Config(**data)
        except Exception as exc:  # pydantic.ValidationError
            raise ConfigError(
                "配置文件内容不合法", path=str(self.config_path), reason=str(exc)
            ) from exc

    def save_config(self, config: Config | None = None) -> Path:
        """原子写入配置文件。

        Args:
            config: 待保存的配置；为 ``None`` 时保存当前内存中的配置。

        Returns:
            写入的文件路径。

        Raises:
            ConfigError: 写入失败。
        """
        target = self.config_path
        payload = (config or self.config).to_dict()
        target.parent.mkdir(parents=True, exist_ok=True)

        is_json = target.suffix.lower() == ".json"
        try:
            fd, tmp_name = tempfile.mkstemp(
                prefix=target.name + ".", suffix=".tmp", dir=str(target.parent)
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    if is_json:
                        json.dump(
                            payload,
                            fh,
                            indent=2,
                            ensure_ascii=False,
                            cls=_DateTimeEncoder,
                        )
                    else:
                        yaml.safe_dump(
                            payload, fh, default_flow_style=False, allow_unicode=True
                        )
                os.replace(tmp_name, target)
            except BaseException:
                try:
                    os.unlink(tmp_name)
                except OSError:  # pragma: no cover - 尽力而为
                    pass
                raise
        except OSError as exc:
            raise ConfigError(
                "配置文件写入失败", path=str(target), reason=str(exc)
            ) from exc

        self.logger.debug("保存配置文件: %s", target)
        return target

    def reload(self) -> Config:
        """从磁盘重新加载配置。

        Returns:
            重新加载后的 :class:`Config`。
        """
        self.config = self._load_config()
        return self.config

    # ------------------------------------------------------------------ #
    # 访问器
    # ------------------------------------------------------------------ #
    def get_config(self) -> Config:
        """获取当前配置对象。

        Returns:
            :class:`Config` 实例。
        """
        return self.config

    def get_config_dict(self) -> dict[str, Any]:
        """获取当前配置的纯字典形式（供 CLI 展示/导出）。

        Returns:
            可 JSON 序列化的字典。
        """
        return self.config.to_dict()

    def get_app_config(self) -> AppConfig:
        """获取应用级配置。

        Returns:
            :class:`AppConfig` 实例。
        """
        return self.config.app

    def get_server_config(self, name: str) -> ServerConfig | None:
        """获取指定渠道服配置。

        Args:
            name: 渠道服名称。

        Returns:
            渠道服配置；不存在时返回 ``None``。
        """
        return self.config.get_server(name)

    def get_account_config(self, account_id: str) -> AccountConfig | None:
        """获取指定账号配置。

        Args:
            account_id: 账号 ID。

        Returns:
            账号配置；不存在时返回 ``None``。
        """
        return self.config.get_account(account_id)

    def get_current_server(self) -> ServerConfig | None:
        """获取当前默认渠道服配置。

        Returns:
            渠道服配置；未设置时返回 ``None``。
        """
        return self.config.get_current_server()

    def get_current_account(self) -> AccountConfig | None:
        """获取当前账号配置。

        Returns:
            账号配置；未设置时返回 ``None``。
        """
        return self.config.get_current_account()

    # ------------------------------------------------------------------ #
    # 应用配置项
    # ------------------------------------------------------------------ #
    def set_config(self, key: str, value: Any) -> None:
        """设置应用级配置项。

        Args:
            key: 配置键，支持 ``log_level`` 或 ``app.log_level`` 两种写法。
            value: 配置值；通常来自命令行，因此可能是字符串
                （例如 ``"8"`` / ``"true"``），由 Pydantic 宽松模式转换。

        Raises:
            ConfigError: 键不存在或取值不合法。
        """
        field = key.split(".", 1)[1] if key.startswith("app.") else key
        if field not in SETTABLE_KEYS:
            raise ConfigError(
                f"不支持的配置项: {key}，可用: {', '.join(SETTABLE_KEYS)}", key=key
            )
        try:
            setattr(self.config.app, field, value)
        except Exception as exc:  # pydantic.ValidationError
            raise ConfigError(f"配置项 {key} 取值不合法", key=key, value=value) from exc

        if self.autosave:
            self.save_config()
        self.logger.info("设置配置: %s = %r", key, value)

    def unset_config(self, key: str) -> None:
        """把一个配置项恢复为默认值。

        Args:
            key: 配置键。

        Raises:
            ConfigError: 键不存在。
        """
        field = key.split(".", 1)[1] if key.startswith("app.") else key
        if field not in SETTABLE_KEYS:
            raise ConfigError(f"不支持的配置项: {key}", key=key)
        defaults = AppConfig()
        setattr(self.config.app, field, getattr(defaults, field))
        if self.autosave:
            self.save_config()
        self.logger.info("重置配置: %s", key)

    # ------------------------------------------------------------------ #
    # 渠道服 CRUD
    # ------------------------------------------------------------------ #
    def add_server(
        self,
        name: str,
        endpoint: str = "",
        region: str = "CN",
        status: str = "active",
        version: str = "1.0.0",
        is_default: bool = False,
    ) -> ServerConfig:
        """新增渠道服配置。

        Args:
            name: 渠道服名称。
            endpoint: 接口地址。
            region: 地区。
            status: 状态。
            version: 版本号。
            is_default: 是否设为默认渠道服。

        Returns:
            新建的 :class:`ServerConfig`。

        Raises:
            ConfigError: 名称为空或状态非法。
        """
        try:
            server = ServerConfig(
                name=name,
                endpoint=endpoint,
                region=region,
                status=status,
                version=version,
                is_default=is_default,
            )
        except Exception as exc:  # pydantic.ValidationError
            raise ConfigError(f"渠道服配置不合法: {name}", name=name) from exc

        self.config.add_server(server)
        if is_default:
            self._mark_default_server(name)
        if self.autosave:
            self.save_config()
        self.logger.info("添加渠道服: %s", name)
        return server

    def remove_server(self, name: str) -> bool:
        """删除渠道服配置。

        Args:
            name: 渠道服名称。

        Returns:
            是否删除成功。
        """
        removed = self.config.remove_server(name)
        if removed:
            if self.config.app.server == name:
                remaining = sorted(self.config.servers)
                self.config.app.server = remaining[0] if remaining else ""
            if self.autosave:
                self.save_config()
            self.logger.info("删除渠道服: %s", name)
        return removed

    def set_default_server(self, name: str) -> None:
        """把指定渠道服设为默认（即「当前渠道服」）。

        Args:
            name: 渠道服名称。

        Raises:
            ConfigError: 渠道服不存在。
        """
        if name not in self.config.servers:
            raise ConfigError(
                f"渠道服不存在: {name}，可用: {', '.join(sorted(self.config.servers)) or '（无）'}",
                name=name,
            )
        self._mark_default_server(name)
        if self.autosave:
            self.save_config()
        self.logger.info("切换默认渠道服: %s", name)

    def _mark_default_server(self, name: str) -> None:
        """更新所有渠道服的默认标记与 ``app.server``。

        Args:
            name: 目标渠道服名称。
        """
        for server_name, server in self.config.servers.items():
            server.is_default = server_name == name
        self.config.app.server = name

    # ------------------------------------------------------------------ #
    # 账号 CRUD
    # ------------------------------------------------------------------ #
    def add_account(
        self,
        username: str,
        server: str,
        password: str,
        account_id: str | None = None,
    ) -> AccountConfig:
        """新增账号配置（密码同时以密文与哈希两种形式存储）。

        Args:
            username: 用户名。
            server: 所属渠道服。
            password: 明文密码。
            account_id: 指定账号 ID；为 ``None`` 时自动生成 UUID。

        Returns:
            新建的 :class:`AccountConfig`。

        Raises:
            ConfigError: 参数不合法。
        """
        new_id = account_id or str(uuid.uuid4())
        try:
            account = AccountConfig(
                id=new_id,
                username=username,
                server=server,
                encrypted_password=encrypt_data(password),
                password_hash=hash_password(password),
                created_at=datetime.now(),
                last_login=None,
                is_current=False,
            )
        except ValidationError:
            raise
        except Exception as exc:  # pydantic.ValidationError
            raise ConfigError("账号配置不合法", username=username) from exc

        self.config.add_account(account)
        if self.autosave:
            self.save_config()
        self.logger.info("添加账号: %s (%s)", username, new_id)
        return account

    def save_account(self, account: AccountConfig) -> None:
        """写回一个已存在的账号配置。

        Args:
            account: 账号配置对象。
        """
        self.config.add_account(account)
        if self.autosave:
            self.save_config()

    def remove_account(self, account_id: str) -> bool:
        """删除账号配置。

        Args:
            account_id: 账号 ID。

        Returns:
            是否删除成功。
        """
        removed = self.config.remove_account(account_id)
        if removed:
            if self.config.app.account == account_id:
                self.config.app.account = None
            if self.autosave:
                self.save_config()
            self.logger.info("删除账号: %s", account_id)
        return removed

    def switch_account(self, account_id: str) -> bool:
        """把指定账号设为当前账号。

        Args:
            account_id: 账号 ID。

        Returns:
            是否切换成功。
        """
        if account_id not in self.config.accounts:
            self.logger.error("账号不存在: %s", account_id)
            return False
        for acc in self.config.accounts.values():
            acc.is_current = acc.id == account_id
        self.config.app.account = account_id
        if self.autosave:
            self.save_config()
        self.logger.info("切换账号: %s", account_id)
        return True

    def list_servers(self) -> list[ServerConfig]:
        """列出全部渠道服。

        Returns:
            按名称排序的渠道服列表。
        """
        return [self.config.servers[k] for k in sorted(self.config.servers)]

    def list_accounts(self, server: str | None = None) -> list[AccountConfig]:
        """列出账号。

        Args:
            server: 仅返回该渠道服下的账号；为 ``None`` 时返回全部。

        Returns:
            账号配置列表。
        """
        accounts = [self.config.accounts[k] for k in sorted(self.config.accounts)]
        if server:
            accounts = [acc for acc in accounts if acc.server == server]
        return accounts

    # ------------------------------------------------------------------ #
    # 导入导出
    # ------------------------------------------------------------------ #
    def export_config(self, export_path: str | Path, fmt: str = "yaml") -> Path:
        """导出配置到文件。

        Args:
            export_path: 目标文件路径。
            fmt: 导出格式，``yaml`` 或 ``json``。

        Returns:
            实际写入的路径。

        Raises:
            ConfigError: 格式不支持或写入失败。
        """
        target = Path(export_path).expanduser()
        payload = self.config.to_dict()
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            if fmt == "json":
                target.write_text(
                    json.dumps(
                        payload, indent=2, ensure_ascii=False, cls=_DateTimeEncoder
                    ),
                    encoding="utf-8",
                )
            elif fmt == "yaml":
                with open(target, "w", encoding="utf-8") as fh:
                    yaml.safe_dump(
                        payload, fh, default_flow_style=False, allow_unicode=True
                    )
            else:
                raise ConfigError(f"不支持的导出格式: {fmt}", format=fmt)
        except OSError as exc:
            raise ConfigError(
                "导出配置失败", path=str(target), reason=str(exc)
            ) from exc
        self.logger.info("导出配置到: %s", target)
        return target

    def import_config(self, import_path: str | Path) -> Config:
        """从文件导入配置并覆盖当前配置。

        Args:
            import_path: 源文件路径。

        Returns:
            导入后的 :class:`Config`。

        Raises:
            ConfigError: 文件不存在或内容非法。
        """
        source = Path(import_path).expanduser()
        if not source.exists():
            raise ConfigError(f"待导入的配置文件不存在: {source}", path=str(source))
        previous = self.config_path
        self.config_path = source
        try:
            imported = self._load_config()
        finally:
            self.config_path = previous
        self.config = imported
        if self.autosave:
            self.save_config()
        self.logger.info("已从 %s 导入配置", source)
        return imported

    def ensure_default_servers(self) -> int:
        """补齐缺失的默认渠道服。

        Returns:
            新增的渠道服数量。
        """
        added = 0
        for name, server in default_config().servers.items():
            if name not in self.config.servers:
                self.config.add_server(server)
                added += 1
        if added and self.autosave:
            self.save_config()
        return added

    def get_default_server_names(self) -> tuple[str, ...]:
        """返回内置的渠道服名称。

        Returns:
            默认渠道服名称元组。
        """
        return DEFAULT_SERVER_NAMES


__all__ = ["SETTABLE_KEYS", "ConfigManager", "default_config_path"]

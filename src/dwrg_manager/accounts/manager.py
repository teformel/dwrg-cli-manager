"""
账号管理器

在 :class:`~dwrg_manager.config.manager.ConfigManager` 之上提供账号的业务
操作。密码以两种形式存储：

* ``encrypted_password``：使用**应用密钥**加密，便于自动填充登录时还原原文；
* ``password_hash``：PBKDF2 派生哈希，用于身份校验（无需解密）。

这一设计同时解决了旧实现的两个问题：重启后无法解密（密钥每次随机）、
以及校验密码时引用了不存在的 ``password_hash`` 字段。

此外本管理器还负责：

* 登录态（``~/.dwrg/session.json``，权限 ``0600``）的写入与清除；
* 账号材料的加密导出与合并导入。
"""

import uuid
from datetime import datetime
from pathlib import Path

from ..config.manager import ConfigManager
from ..config.models import AccountConfig
from ..exceptions import AccountError
from ..security.crypto import decrypt_data, encrypt_data, hash_password, verify_password
from ..security.validation import validate_password, validate_username
from ..utils.logger import get_logger
from .models import Account, LoginResult
from .session import Session, clear_session, get_active_session, write_session
from .transfer import (
    ExportedAccount,
    ImportReport,
    accounts_from_config,
    export_accounts,
    import_accounts,
)

logger = get_logger(__name__)

#: 用于校验密码时返回的固定失败结果（避免时序侧信道泄露账号是否存在）
_AUTH_FAILED = None


class AccountManager:
    """账号管理器。

    Args:
        config_manager: 注入的配置管理器；为 ``None`` 时使用默认配置。
            测试可传入指向临时目录的实例，避免污染真实配置。

    Example:
        >>> from dwrg_manager.accounts import AccountManager  # doctest: +SKIP
        >>> manager = AccountManager()  # doctest: +SKIP
        >>> manager.create_account("tester", "official", "secret123").username  # doctest: +SKIP
        'tester'
    """

    def __init__(
        self,
        config_manager: ConfigManager | None = None,
        *,
        session_file: str | Path | None = None,
    ) -> None:
        """初始化账号管理器。

        Args:
            config_manager: 注入的配置管理器；为 ``None`` 时使用默认配置。
            session_file: 自定义登录态文件路径；为 ``None`` 时使用
                :func:`~dwrg_manager.accounts.session.default_session_path`。
        """
        self.config_manager = config_manager or ConfigManager()
        self.logger = get_logger(__name__)
        self._session_file: Path | None = (
            Path(session_file).expanduser() if session_file else None
        )

    # ------------------------------------------------------------------ #
    # 转换
    # ------------------------------------------------------------------ #
    @staticmethod
    def _to_account(cfg: AccountConfig) -> Account:
        """把持久化配置转换为运行时模型。

        Args:
            cfg: 账号配置。

        Returns:
            :class:`Account` 实例。
        """
        return Account(
            id=cfg.id,
            username=cfg.username,
            server=cfg.server,
            encrypted_password=cfg.encrypted_password,
            password_hash=cfg.password_hash,
            created_at=cfg.created_at,
            last_login=cfg.last_login,
            is_current=cfg.is_current,
        )

    # ------------------------------------------------------------------ #
    # CRUD
    # ------------------------------------------------------------------ #
    def create_account(
        self,
        username: str,
        server: str,
        password: str,
        account_id: str | None = None,
    ) -> Account:
        """创建账号。

        Args:
            username: 用户名，3-20 位字母/数字/下划线。
            server: 所属渠道服，必须已在配置中存在。
            password: 明文密码，6-128 位。
            account_id: 指定账号 ID；为 ``None`` 时自动生成 UUID。

        Returns:
            新建的 :class:`Account`。

        Raises:
            AccountError: 用户名重复、渠道服不存在或参数不合法。
            ValidationError: 用户名/密码不符合规则。
        """
        name = validate_username(username)
        validate_password(password)

        if self.config_manager.get_server_config(server) is None:
            available = (
                ", ".join(sorted(self.config_manager.get_config().servers)) or "（无）"
            )
            raise AccountError(
                f"渠道服不存在: {server}，可用: {available}", server=server
            )

        if any(acc.username == name for acc in self.list_accounts()):
            raise AccountError(f"用户名已存在: {name}", username=name)

        cfg = self.config_manager.add_account(
            username=name,
            server=server,
            password=password,
            account_id=account_id or str(uuid.uuid4()),
        )
        self.logger.info("创建账号: %s (%s)", name, cfg.id)
        return self._to_account(cfg)

    def list_accounts(self, server: str | None = None) -> list[Account]:
        """列出账号。

        Args:
            server: 仅列出该渠道服下的账号；为 ``None`` 时列出全部。

        Returns:
            账号列表。
        """
        return [
            self._to_account(cfg) for cfg in self.config_manager.list_accounts(server)
        ]

    def get_account(self, account_id: str) -> Account | None:
        """按 ID 获取账号。

        Args:
            account_id: 账号 ID。

        Returns:
            账号对象；不存在时返回 ``None``。
        """
        cfg = self.config_manager.get_account_config(account_id)
        return self._to_account(cfg) if cfg else None

    def find_by_username(self, username: str) -> Account | None:
        """按用户名查找账号。

        Args:
            username: 用户名。

        Returns:
            首个匹配的账号；未找到返回 ``None``。
        """
        for account in self.list_accounts():
            if account.username == username:
                return account
        return None

    def update_account(self, account_id: str, **fields: object) -> bool:
        """更新账号字段。

        Args:
            account_id: 账号 ID。
            **fields: 待更新的字段（``username`` / ``server`` /
                ``encrypted_password`` / ``password_hash`` / ``last_login`` /
                ``is_current``）。

        Returns:
            是否更新成功。

        Raises:
            AccountError: 账号不存在或字段不合法。
        """
        cfg = self.config_manager.get_account_config(account_id)
        if cfg is None:
            self.logger.warning("更新失败，账号不存在: %s", account_id)
            return False

        payload = cfg.model_dump()
        payload.update(fields)
        if "username" in fields:
            payload["username"] = validate_username(str(fields["username"]))
        try:
            updated = AccountConfig(**payload)
        except Exception as exc:  # pydantic.ValidationError
            raise AccountError(
                "账号字段不合法", account_id=account_id, reason=str(exc)
            ) from exc

        self.config_manager.save_account(updated)
        self.logger.info("更新账号: %s", account_id)
        return True

    def set_password(self, account_id: str, password: str) -> bool:
        """重设账号密码（同时刷新密文与哈希）。

        Args:
            account_id: 账号 ID。
            password: 新的明文密码。

        Returns:
            是否设置成功。

        Raises:
            AccountError: 账号不存在或密码不合法。
        """
        validate_password(password)
        return self.update_account(
            account_id,
            encrypted_password=encrypt_data(password),
            password_hash=hash_password(password),
        )

    def remove_account(self, account_id: str) -> bool:
        """删除账号。

        Args:
            account_id: 账号 ID。

        Returns:
            是否删除成功。
        """
        removed = self.config_manager.remove_account(account_id)
        if removed:
            self.logger.info("删除账号: %s", account_id)
        return removed

    # ------------------------------------------------------------------ #
    # 切换 / 登录
    # ------------------------------------------------------------------ #
    def switch_account(self, account_id: str) -> bool:
        """切换当前账号并刷新最后登录时间。

        Args:
            account_id: 账号 ID。

        Returns:
            是否切换成功。
        """
        if not self.config_manager.switch_account(account_id):
            return False
        self.update_account(account_id, last_login=datetime.now())
        return True

    def get_current_account(self) -> Account | None:
        """获取当前账号。

        Returns:
            当前账号；未设置时返回 ``None``。
        """
        cfg = self.config_manager.get_current_account()
        return self._to_account(cfg) if cfg else None

    def get_password(self, account_id: str) -> str:
        """还原账号密码明文（用于自动填充）。

        Args:
            account_id: 账号 ID。

        Returns:
            明文密码。

        Raises:
            AccountError: 账号不存在，或密文无法用当前应用密钥解密。
        """
        cfg = self.config_manager.get_account_config(account_id)
        if cfg is None:
            raise AccountError(f"账号不存在: {account_id}", account_id=account_id)
        if not cfg.encrypted_password:
            raise AccountError("该账号未保存密码密文", account_id=account_id)
        try:
            return decrypt_data(cfg.encrypted_password)
        except Exception as exc:
            raise AccountError(
                "密码解密失败（可能由旧版本密钥加密）", account_id=account_id
            ) from exc

    def authenticate(self, username: str, password: str) -> Account | None:
        """校验用户名与密码。

        Args:
            username: 用户名。
            password: 明文密码。

        Returns:
            校验通过时返回对应账号，否则返回 ``None``。
        """
        account = self.find_by_username(username)
        if account is None:
            return _AUTH_FAILED
        if not account.password_hash:
            self.logger.warning("账号 %s 缺少密码哈希，无法校验", username)
            return _AUTH_FAILED
        if verify_password(password, account.password_hash):
            return account
        return _AUTH_FAILED

    def login(self, account_id: str, server: str | None = None) -> LoginResult:
        """执行账号登录。

        除更新配置中的当前账号与最后登录时间外，还会把登录态写入
        ``~/.dwrg/session.json``（权限 ``0600``，原子写入），供启动器读取并
        注入子进程环境变量。

        Args:
            account_id: 账号 ID。
            server: 目标渠道服；为 ``None`` 时沿用账号自身配置。

        Returns:
            登录结果。失败时 ``success`` 为 ``False`` 并附带原因。
        """
        cfg = self.config_manager.get_account_config(account_id)
        if cfg is None:
            return LoginResult(
                success=False, account_id=account_id, message="账号不存在"
            )

        target_server = server or cfg.server
        if self.config_manager.get_server_config(target_server) is None:
            return LoginResult(
                success=False,
                account_id=account_id,
                username=cfg.username,
                server=target_server,
                message=f"渠道服不存在: {target_server}",
            )

        now = datetime.now()
        self.update_account(account_id, last_login=now, server=target_server)
        self.config_manager.switch_account(account_id)
        self.save_session(
            Session(
                account_id=cfg.id,
                server=target_server,
                username=cfg.username,
                logged_in_at=now,
            )
        )
        self.logger.info("账号登录: %s -> %s", cfg.username, target_server)
        return LoginResult(
            success=True,
            account_id=account_id,
            username=cfg.username,
            server=target_server,
            message="登录信息已就绪",
            timestamp=now,
        )

    def save_session(self, session: Session) -> Path | None:
        """把登录态写入磁盘（失败不阻断登录流程）。

        Args:
            session: 待保存的登录态。

        Returns:
            写入的文件路径；写入失败时返回 ``None`` 并记录警告。
        """
        try:
            return write_session(session, self._session_file)
        except OSError as exc:
            self.logger.warning("登录态写入失败: %s", exc)
            return None

    def get_session(self) -> Session | None:
        """读取当前登录态。

        Returns:
            :class:`~dwrg_manager.accounts.session.Session` 实例；
            未登录或登录态损坏时返回 ``None``。
        """
        return get_active_session(self._session_file)

    def logout(self, clear_config: bool = True) -> bool:
        """登出当前账号。

        清除登录态文件；``clear_config`` 为 ``True`` 时同时重置配置中的
        当前账号与 ``is_current`` 标记。

        Args:
            clear_config: 是否同时清理主配置里的当前账号。

        Returns:
            此前是否存在登录态或当前账号。

        Raises:
            AccountError: 登录态文件删除失败。
        """
        had_session = False
        try:
            had_session = clear_session(self._session_file)
        except AccountError as exc:
            self.logger.warning("登录态清除失败: %s", exc)

        config = self.config_manager.get_config()
        had_account = bool(config.app.account) or any(
            acc.is_current for acc in config.accounts.values()
        )
        if clear_config and (config.app.account or had_account):
            config.app.account = None
            for acc in config.accounts.values():
                acc.is_current = False
            self.config_manager.save_config()
        self.logger.info("账号已登出")
        return had_session or had_account

    def simulate_login(self, account: Account) -> LoginResult:
        """对内存中的账号对象执行一次登录演练。

        Args:
            account: 已存在的账号对象。

        Returns:
            登录结果。
        """
        return self.login(account.id)

    # ------------------------------------------------------------------ #
    # 导出 / 导入
    # ------------------------------------------------------------------ #
    def export_accounts(self, path: str | Path) -> Path:
        """把全部账号加密导出为单文件。

        Args:
            path: 目标文件路径。

        Returns:
            实际写入的文件路径。

        Raises:
            AccountError: 没有账号或写入失败。
        """
        accounts = accounts_from_config(self.config_manager)
        written = export_accounts(accounts, path)
        self.logger.info("导出 %d 个账号到 %s", len(accounts), written)
        return written

    def import_accounts(self, path: str | Path, *, force: bool = False) -> ImportReport:
        """从导出文件导入账号并合并到当前配置。

        Args:
            path: 导出文件路径。
            force: 是否允许覆盖已存在的账号 ID。

        Returns:
            :class:`~dwrg_manager.accounts.transfer.ImportReport` 统计结果。

        Raises:
            AccountError: 文件不存在、内容损坏或渠道服缺失。
        """
        config = self.config_manager.get_config()
        return import_accounts(
            path,
            known_account_ids=set(config.accounts),
            known_servers=set(config.servers),
            force=force,
            apply=self._apply_imported_account,
        )

    def _apply_imported_account(self, account: ExportedAccount) -> None:
        """把一条导入的账号材料写回配置。

        Args:
            account: 解密并校验后的账号材料。
        """
        existing = self.config_manager.get_account_config(account.id)
        is_current = existing.is_current if existing else False
        self.config_manager.save_account(
            AccountConfig(
                id=account.id,
                username=account.username,
                server=account.server,
                encrypted_password=account.encrypted_password,
                password_hash=account.password_hash,
                created_at=account.created_at or datetime.now(),
                last_login=account.last_login,
                is_current=is_current,
            )
        )


__all__ = ["AccountManager"]

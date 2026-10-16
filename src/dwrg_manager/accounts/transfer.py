"""
账号加密导出与导入

把账号材料（密文密码 + 密码哈希）打包成单文件，便于在机器之间迁移：

* 导出时账号材料整体经 :func:`~dwrg_manager.security.crypto.encrypt_data`
  加密，落盘为 JSON 外壳 + 加密载荷，明文密码不会出现在文件中；
* 导入时先解密载荷，再逐条校验并合并到当前配置，账号 ID 冲突时默认
  拒绝，``--force`` 才允许覆盖；
* 载荷损坏、密钥不匹配都会抛出 :class:`~dwrg_manager.exceptions.AccountError`，
  由 CLI 转成单行提示。

导出的账号材料不含登录态，也不含任何服务器私钥。
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..exceptions import AccountError
from ..security.crypto import decrypt_data, encrypt_data, verify_password
from ..security.validation import validate_server_name, validate_username
from ..utils.atomic import atomic_write_text
from ..utils.logger import get_logger

logger = get_logger(__name__)

#: 导出文件的格式标识
EXPORT_MAGIC: str = "dwrg-account-export"

#: 导出文件的格式版本
EXPORT_VERSION: int = 1

__all__ = [
    "EXPORT_MAGIC",
    "EXPORT_VERSION",
    "ExportedAccount",
    "ImportReport",
    "export_accounts",
    "import_accounts",
]


class ExportedAccount(BaseModel):
    """导出文件中单个账号的材料。

    Attributes:
        id: 账号 ID。
        username: 用户名。
        server: 所属渠道服。
        encrypted_password: 应用密钥加密后的密码密文。
        password_hash: PBKDF2 密码哈希。
        created_at: 账号创建时间。
        last_login: 最后登录时间。
    """

    model_config = ConfigDict(validate_assignment=True)

    id: str = Field(..., description="账号ID")
    username: str = Field(..., description="用户名")
    server: str = Field(..., description="渠道服")
    encrypted_password: str = Field("", description="加密后的密码")
    password_hash: str = Field("", description="密码哈希")
    created_at: datetime | None = Field(None, description="创建时间")
    last_login: datetime | None = Field(None, description="最后登录时间")

    @field_validator("id")
    @classmethod
    def _check_id(cls, v: str) -> str:
        """校验账号 ID 长度。

        Args:
            v: 待校验的账号 ID。

        Returns:
            账号 ID 原文。

        Raises:
            ValueError: 长度不足 8 个字符。
        """
        if len(v.strip()) < 8:
            raise ValueError("账号ID长度不能少于8个字符")
        return v

    @field_validator("username")
    @classmethod
    def _check_username(cls, v: str) -> str:
        """校验用户名格式。

        Args:
            v: 待校验的用户名。

        Returns:
            规范化后的用户名。

        Raises:
            ValueError: 用户名不符合命名规则。
        """
        try:
            return validate_username(v)
        except Exception as exc:
            raise ValueError(str(exc)) from exc

    @field_validator("server")
    @classmethod
    def _check_server(cls, v: str) -> str:
        """校验渠道服名称。

        Args:
            v: 待校验的渠道服名称。

        Returns:
            规范化后的渠道服名称。

        Raises:
            ValueError: 渠道服名称非法。
        """
        try:
            return validate_server_name(v)
        except Exception as exc:
            raise ValueError(str(exc)) from exc


class ImportReport(BaseModel):
    """一次导入的结果统计。

    Attributes:
        imported: 新增账号数量。
        overwritten: 覆盖已有账号的数量。
        skipped: 因冲突被跳过的数量。
        details: 每个账号的处理结果说明。
    """

    imported: int = Field(0, description="新增账号数量")
    overwritten: int = Field(0, description="覆盖账号数量")
    skipped: int = Field(0, description="跳过账号数量")
    details: list[str] = Field(default_factory=list, description="逐条处理说明")

    @property
    def total(self) -> int:
        """参与处理的账号总数。

        Returns:
            ``imported + overwritten + skipped``。
        """
        return self.imported + self.overwritten + self.skipped


def _build_envelope(accounts: list[ExportedAccount]) -> dict[str, Any]:
    """构造导出文件的外壳（明文元数据 + 加密载荷）。

    Args:
        accounts: 待导出的账号材料列表。

    Returns:
        可 JSON 序列化的导出字典。
    """
    material = json.dumps(
        [account.model_dump(mode="json") for account in accounts],
        ensure_ascii=False,
    )
    envelope: dict[str, Any] = {
        "magic": EXPORT_MAGIC,
        "version": EXPORT_VERSION,
        "exported_at": datetime.now().isoformat(),
        "count": len(accounts),
        "payload": encrypt_data(material),
    }
    return envelope


def _parse_envelope(raw: str, path: Path) -> dict[str, Any]:
    """解析并校验导出文件的外壳结构。

    Args:
        raw: 文件原始文本。
        path: 文件路径，用于错误提示。

    Returns:
        解析后的字典。

    Raises:
        AccountError: 不是合法 JSON、缺少字段或版本不受支持。
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AccountError(
            "导出文件不是合法的 JSON", path=str(path), reason=str(exc)
        ) from exc
    if not isinstance(data, dict):
        raise AccountError("导出文件顶层必须是对象", path=str(path))
    if data.get("magic") != EXPORT_MAGIC:
        raise AccountError("不是 dwrg 账号导出文件", path=str(path))
    version = data.get("version")
    if version != EXPORT_VERSION:
        raise AccountError(f"不支持的导出文件版本: {version!r}", path=str(path))
    if not isinstance(data.get("payload"), str) or not data["payload"]:
        raise AccountError("导出文件缺少加密载荷", path=str(path))
    return data


def _decode_accounts(data: dict[str, Any], path: Path) -> list[ExportedAccount]:
    """解密并反序列化导出文件中的账号材料。

    Args:
        data: 已解析的导出外壳。
        path: 文件路径，用于错误提示。

    Returns:
        账号材料列表。

    Raises:
        AccountError: 解密失败或账号条目不合法。
    """
    try:
        material = decrypt_data(str(data["payload"]))
    except Exception as exc:
        raise AccountError(
            "导出文件无法解密（密钥不匹配或数据被篡改）",
            path=str(path),
            reason=str(exc),
        ) from exc
    try:
        entries = json.loads(material)
    except json.JSONDecodeError as exc:
        raise AccountError(
            "解密后的账号材料不是合法 JSON",
            path=str(path),
            reason=str(exc),
        ) from exc
    if not isinstance(entries, list):
        raise AccountError("解密后的账号材料应为数组", path=str(path))
    try:
        return [ExportedAccount(**entry) for entry in entries]
    except Exception as exc:  # pydantic.ValidationError
        raise AccountError(
            "导出文件中的账号条目不合法", path=str(path), reason=str(exc)
        ) from exc


def export_accounts(accounts: list[ExportedAccount], path: str | Path) -> Path:
    """把账号材料加密导出为单文件。

    Args:
        accounts: 待导出的账号材料列表。
        path: 目标文件路径。

    Returns:
        实际写入的文件路径。

    Raises:
        AccountError: 账号材料为空或写入失败。
    """
    if not accounts:
        raise AccountError("没有可导出的账号")
    envelope = _build_envelope(accounts)
    target = Path(path).expanduser()
    payload = json.dumps(envelope, ensure_ascii=False, indent=2) + "\n"
    try:
        written = atomic_write_text(target, payload)
    except OSError as exc:
        raise AccountError(
            "写入导出文件失败", path=str(target), reason=str(exc)
        ) from exc
    logger.info("已导出 %d 个账号到 %s", len(accounts), written)
    return written


def import_accounts(
    path: str | Path,
    known_account_ids: set[str] | frozenset[str],
    known_servers: set[str] | frozenset[str],
    *,
    force: bool = False,
    apply: Any = None,
) -> ImportReport:
    """从导出文件导入账号并合并到当前配置。

    导入前会校验渠道服是否存在；账号 ID 已存在时默认跳过，``force=True``
    才覆盖。导入是「先全部校验、再逐条应用」的两段式，任一条目不合法
    都会在应用前抛错，避免写进半个配置。

    Args:
        path: 导出文件路径。
        known_account_ids: 当前配置中已存在的账号 ID 集合。
        known_servers: 当前配置中已存在的渠道服集合。
        force: 是否允许覆盖已存在的账号 ID。
        apply: 应用单个账号的回调，签名 ``(ExportedAccount) -> None``；
            为 ``None`` 时只做校验与统计，不落盘。

    Returns:
        :class:`ImportReport` 统计结果。

    Raises:
        AccountError: 文件不存在、内容损坏或渠道服缺失。
    """
    source = Path(path).expanduser()
    if not source.exists():
        raise AccountError("导出文件不存在", path=str(source))
    raw = source.read_text(encoding="utf-8")
    data = _parse_envelope(raw, source)
    accounts = _decode_accounts(data, source)

    report = ImportReport()
    pending: list[ExportedAccount] = []
    for account in accounts:
        if account.server not in known_servers:
            raise AccountError(
                f"渠道服不存在: {account.server}，请先创建该渠道服",
                path=str(source),
                server=account.server,
            )
        exists = account.id in known_account_ids
        if exists and not force:
            report.skipped += 1
            report.details.append(
                f"{account.username} ({account.id}): 已存在，已跳过（--force 可覆盖）"
            )
            continue
        pending.append(account)
        if exists:
            report.overwritten += 1
            report.details.append(f"{account.username} ({account.id}): 已覆盖")
        else:
            report.imported += 1
            report.details.append(f"{account.username} ({account.id}): 已导入")

    if apply is not None:
        for account in pending:
            apply(account)
    logger.info(
        "导入账号: 新增 %d，覆盖 %d，跳过 %d（来自 %s）",
        report.imported,
        report.overwritten,
        report.skipped,
        source,
    )
    return report


def accounts_from_config(config: Any) -> list[ExportedAccount]:
    """把配置中的账号转换为导出材料。

    Args:
        config: 配置对象，需提供 ``list_accounts()`` 方法。

    Returns:
        账号材料列表；没有账号时为空列表。
    """
    exported: list[ExportedAccount] = []
    for cfg in config.list_accounts():
        exported.append(
            ExportedAccount(
                id=cfg.id,
                username=cfg.username,
                server=cfg.server,
                encrypted_password=cfg.encrypted_password,
                password_hash=cfg.password_hash,
                created_at=cfg.created_at,
                last_login=cfg.last_login,
            )
        )
    return exported


def verify_exported_password(account: ExportedAccount, password: str) -> bool:
    """校验给定密码是否与导出材料中的哈希匹配。

    Args:
        account: 账号材料。
        password: 待校验的明文密码。

    Returns:
        匹配返回 ``True``；缺少哈希或格式非法返回 ``False``。
    """
    if not account.password_hash:
        return False
    return verify_password(password, account.password_hash)

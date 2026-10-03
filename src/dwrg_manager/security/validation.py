"""
输入校验

集中放置业务层的参数校验逻辑，统一抛出
:class:`~dwrg_manager.exceptions.ValidationError`，避免把
``ValueError`` / ``TypeError`` 等底层异常直接冒泡到 CLI 层。
"""

import re
from collections.abc import Iterable
from pathlib import Path

from ..config.models import SERVER_NAME_PATTERN, SUPPORTED_LANGUAGES
from ..exceptions import ValidationError

#: 用户名允许的字符集
_USERNAME_RE = re.compile(r"^[A-Za-z0-9_]+$")

#: 版本号格式，例如 1.0.0 / 2026.10
_VERSION_RE = re.compile(r"^\d+(\.\d+)*$")

#: 用户名长度下限
USERNAME_MIN_LENGTH = 3

#: 用户名长度上限
USERNAME_MAX_LENGTH = 20

#: 密码长度下限
PASSWORD_MIN_LENGTH = 6

#: 密码长度上限
PASSWORD_MAX_LENGTH = 128

#: 账号 ID 长度下限
ACCOUNT_ID_MIN_LENGTH = 8


def validate_username(
    value: str,
    *,
    min_length: int = USERNAME_MIN_LENGTH,
    max_length: int = USERNAME_MAX_LENGTH,
) -> str:
    """校验用户名。

    Args:
        value: 待校验的用户名。
        min_length: 允许的最小长度。
        max_length: 允许的最大长度。

    Returns:
        去除首尾空白后的用户名。

    Raises:
        ValidationError: 类型不符、长度越界或包含非法字符。
    """
    if not isinstance(value, str):
        raise ValidationError("用户名必须是字符串", field="username")
    name = value.strip()
    if not min_length <= len(name) <= max_length:
        raise ValidationError(
            f"长度必须在 {min_length}-{max_length} 个字符之间", field="username"
        )
    if not _USERNAME_RE.match(name):
        raise ValidationError("只能包含字母、数字和下划线", field="username")
    return name


def validate_password(
    value: str,
    *,
    min_length: int = PASSWORD_MIN_LENGTH,
    max_length: int = PASSWORD_MAX_LENGTH,
) -> str:
    """校验密码强度（长度与非全空白）。

    Args:
        value: 待校验的密码。
        min_length: 允许的最小长度。
        max_length: 允许的最大长度。

    Returns:
        原样返回的密码。

    Raises:
        ValidationError: 类型不符、长度越界或全部为空白字符。
    """
    if not isinstance(value, str):
        raise ValidationError("密码必须是字符串", field="password")
    if not min_length <= len(value) <= max_length:
        raise ValidationError(
            f"长度必须在 {min_length}-{max_length} 个字符之间", field="password"
        )
    if not value.strip():
        raise ValidationError("不能全部为空白字符", field="password")
    return value


def validate_account_id(value: str, *, min_length: int = ACCOUNT_ID_MIN_LENGTH) -> str:
    """校验账号 ID。

    Args:
        value: 待校验的账号 ID。
        min_length: 允许的最小长度。

    Returns:
        去除首尾空白后的账号 ID。

    Raises:
        ValidationError: 类型不符或长度不足。
    """
    if not isinstance(value, str):
        raise ValidationError("账号ID必须是字符串", field="account_id")
    account_id = value.strip()
    if len(account_id) < min_length:
        raise ValidationError(f"长度不能少于 {min_length} 个字符", field="account_id")
    return account_id


def validate_server_name(
    value: str,
    *,
    known: Iterable[str] | None = None,
) -> str:
    """校验渠道服名称。

    Args:
        value: 待校验的渠道服名称。
        known: 已知渠道服集合；提供时会额外校验名称是否存在。

    Returns:
        去除首尾空白后的渠道服名称。

    Raises:
        ValidationError: 名称为空、含非法字符，或不在 ``known`` 之内。
    """
    if not isinstance(value, str):
        raise ValidationError("渠道服名称必须是字符串", field="server")
    name = value.strip()
    if not name:
        raise ValidationError("渠道服名称不能为空", field="server")
    if not SERVER_NAME_PATTERN.match(name):
        raise ValidationError("只能包含字母、数字、下划线和短横线", field="server")
    if known is not None:
        allowed = list(known)
        if name not in allowed:
            raise ValidationError(
                f"未知渠道服 {name!r}，可用: {', '.join(allowed) or '（无）'}",
                field="server",
            )
    return name


def validate_version(value: str) -> str:
    """校验版本号格式。

    Args:
        value: 待校验的版本号，例如 ``1.0.0``。

    Returns:
        去除首尾空白后的版本号。

    Raises:
        ValidationError: 格式不符合 ``x.y.z`` 形式。
    """
    if not isinstance(value, str):
        raise ValidationError("版本号必须是字符串", field="version")
    version = value.strip()
    if not _VERSION_RE.match(version):
        raise ValidationError("版本号需形如 1.0.0", field="version")
    return version


def validate_language(value: str) -> str:
    """校验语言代码。

    Args:
        value: 待校验的语言代码，例如 ``zh-CN``。

    Returns:
        校验通过的语言代码。

    Raises:
        ValidationError: 语言代码不受支持。
    """
    if not isinstance(value, str):
        raise ValidationError("语言代码必须是字符串", field="language")
    language = value.strip()
    if language not in SUPPORTED_LANGUAGES:
        raise ValidationError(
            f"不支持的语言 {language!r}，可用: {', '.join(SUPPORTED_LANGUAGES)}",
            field="language",
        )
    return language


def validate_path(
    value: str | Path,
    *,
    base: str | Path | None = None,
    must_exist: bool = False,
) -> Path:
    """校验并规范化文件路径，防止目录穿越。

    Args:
        value: 待校验的路径。
        base: 允许的根目录；提供时会确保解析后的路径仍位于该目录之下。
        must_exist: 是否要求路径必须已存在。

    Returns:
        展开 ``~`` 并解析后的绝对路径。

    Raises:
        ValidationError: 路径类型非法、越界或（``must_exist`` 时）不存在。
    """
    if not isinstance(value, (str, Path)):
        raise ValidationError("路径必须是字符串或 Path", field="path")
    path = Path(value).expanduser()
    try:
        resolved = path.resolve()
    except OSError as exc:  # pragma: no cover - 依赖文件系统
        raise ValidationError(f"路径无法解析: {value!r}", field="path") from exc

    if base is not None:
        base_resolved = Path(base).expanduser().resolve()
        if resolved != base_resolved and base_resolved not in resolved.parents:
            raise ValidationError(
                f"路径 {resolved} 超出允许目录 {base_resolved}", field="path"
            )

    if must_exist and not resolved.exists():
        raise ValidationError(f"路径不存在: {resolved}", field="path")
    return resolved


__all__ = [
    "ACCOUNT_ID_MIN_LENGTH",
    "PASSWORD_MAX_LENGTH",
    "PASSWORD_MIN_LENGTH",
    "USERNAME_MAX_LENGTH",
    "USERNAME_MIN_LENGTH",
    "validate_account_id",
    "validate_language",
    "validate_password",
    "validate_path",
    "validate_server_name",
    "validate_username",
    "validate_version",
]

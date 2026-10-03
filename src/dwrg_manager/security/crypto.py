"""
加密与密钥管理

职责：

* 生成 / 加载 / 持久化应用级加密密钥（Fernet，AES-128-CBC + HMAC-SHA256）。
* 提供字符串与字节串的对称加解密。
* 提供密码哈希（PBKDF2-HMAC-SHA256）与恒定时间校验。

密钥解析优先级（由高到低）：

1. 构造函数显式传入的 ``key``。
2. 环境变量 ``DWRG_ENCRYPTION_KEY``（合法的 Fernet key；否则视为口令做
   PBKDF2 派生）。
3. 密钥文件（默认 ``~/.dwrg/keyfile``，可用环境变量 ``DWRG_KEY_FILE``
   或 ``key_file`` 参数覆盖）。
4. 自动生成新密钥并写入密钥文件（权限 ``0600``）。

.. note::
   早期实现每次进程启动都会随机生成密钥，导致重启后无法解密既有数据。
   现在的实现会把密钥落盘复用，从而保证跨进程可解密。
"""

import base64
import binascii
import hashlib
import hmac
import os
from pathlib import Path
from typing import Final

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from ..exceptions import SecurityError
from ..utils.logger import get_logger

logger = get_logger(__name__)

#: 环境变量：直接提供 Fernet 密钥，或提供口令由 PBKDF2 派生
ENV_KEY: Final[str] = "DWRG_ENCRYPTION_KEY"

#: 环境变量：自定义密钥文件路径
ENV_KEY_FILE: Final[str] = "DWRG_KEY_FILE"

#: 默认密钥文件路径
DEFAULT_KEY_FILE: Final[Path] = Path.home() / ".dwrg" / "keyfile"

#: PBKDF2 迭代次数
PBKDF2_ITERATIONS: Final[int] = 100_000

#: 口令派生时使用的固定盐（仅在把口令当作密钥来源时使用）
_PASSPHRASE_SALT: Final[bytes] = b"dwrg-cli-manager::keyfile::v1"


def default_key_file() -> Path:
    """返回默认密钥文件路径（可通过环境变量覆盖）。

    Returns:
        密钥文件路径。
    """
    override = os.environ.get(ENV_KEY_FILE)
    return Path(override).expanduser() if override else DEFAULT_KEY_FILE


def generate_key() -> str:
    """生成一个新的 Fernet 密钥。

    Returns:
        URL-safe base64 编码的 32 字节密钥字符串。
    """
    return Fernet.generate_key().decode("ascii")


def _normalize_key(raw: str | bytes) -> bytes:
    """把多种形态的密钥输入规范化为 Fernet 可用的密钥字节串。

    Args:
        raw: Fernet 密钥字符串、密钥字节串，或任意口令。

    Returns:
        合法的 Fernet 密钥（URL-safe base64 字节串）。

    Raises:
        SecurityError: 无法把输入转换为合法密钥。
    """
    if isinstance(raw, bytes):
        candidate = raw.strip()
    else:
        candidate = raw.strip().encode("utf-8")

    try:
        Fernet(candidate)
        return candidate
    except (ValueError, TypeError):
        pass

    # 不是合法 Fernet key，视为口令并按 PBKDF2 派生
    try:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=_PASSPHRASE_SALT,
            iterations=PBKDF2_ITERATIONS,
        )
        return base64.urlsafe_b64encode(kdf.derive(candidate))
    except Exception as exc:  # pragma: no cover - 极端异常
        raise SecurityError("无法从给定输入派生出可用密钥", reason=str(exc)) from exc


def _load_or_create_key(path: Path) -> bytes:
    """从密钥文件加载密钥；文件不存在时生成并持久化。

    Args:
        path: 密钥文件路径。

    Returns:
        Fernet 密钥字节串。

    Raises:
        SecurityError: 密钥文件存在但不可读或内容非法。
    """
    if path.exists():
        try:
            return _normalize_key(path.read_bytes())
        except SecurityError as exc:
            raise SecurityError(
                "密钥文件内容非法，请检查或删除后重建", path=str(path)
            ) from exc

    key = Fernet.generate_key()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with os.fdopen(
            os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "wb"
        ) as fh:
            fh.write(key)
        logger.debug("已生成新的加密密钥文件: %s", path)
    except OSError as exc:
        logger.warning("无法写入密钥文件 %s（将仅在本次进程内有效）: %s", path, exc)
    return key


class CryptoManager:
    """应用级加解密管理器。

    Args:
        key: 显式指定的密钥（Fernet key 或口令）。为 ``None`` 时按环境变量
            与密钥文件的顺序解析。
        key_file: 自定义密钥文件路径。

    Raises:
        SecurityError: 密钥无法解析。
    """

    def __init__(
        self, key: str | bytes | None = None, key_file: str | Path | None = None
    ) -> None:
        self.logger = get_logger(__name__)
        resolved = key
        if resolved is None:
            resolved = os.environ.get(ENV_KEY)
        if resolved is None:
            path = Path(key_file).expanduser() if key_file else default_key_file()
            self._key_file: Path | None = path
            self._key = _load_or_create_key(path)
        else:
            self._key_file = Path(key_file).expanduser() if key_file else None
            self._key = _normalize_key(resolved)
        self._fernet = Fernet(self._key)

    @property
    def key_file(self) -> Path | None:
        """当前使用的密钥文件路径（显式指定密钥时为 ``None``）。"""
        return self._key_file

    def encrypt(self, data: str) -> str:
        """加密字符串。

        Args:
            data: 明文。

        Returns:
            URL-safe base64 编码的密文。

        Raises:
            SecurityError: 加密过程失败。
        """
        try:
            return self._fernet.encrypt(data.encode("utf-8")).decode("ascii")
        except Exception as exc:  # pragma: no cover - Fernet 极少失败
            raise SecurityError("加密失败", reason=str(exc)) from exc

    def decrypt(self, encrypted_data: str) -> str:
        """解密字符串。

        Args:
            encrypted_data: :meth:`encrypt` 产出的密文。

        Returns:
            解密后的明文。

        Raises:
            SecurityError: 密文被篡改、密钥不匹配或格式非法。
        """
        try:
            return self._fernet.decrypt(encrypted_data.encode("ascii")).decode("utf-8")
        except (InvalidToken, ValueError, TypeError) as exc:
            raise SecurityError("解密失败：数据无效或密钥不匹配") from exc

    def encrypt_bytes(self, data: bytes) -> bytes:
        """加密字节串。

        Args:
            data: 明文字节串。

        Returns:
            Fernet 密文字节串。

        Raises:
            SecurityError: 加密失败。
        """
        try:
            return self._fernet.encrypt(data)
        except Exception as exc:  # pragma: no cover
            raise SecurityError("加密失败", reason=str(exc)) from exc

    def decrypt_bytes(self, token: bytes) -> bytes:
        """解密字节串。

        Args:
            token: Fernet 密文字节串。

        Returns:
            解密后的明文字节串。

        Raises:
            SecurityError: 解密失败。
        """
        try:
            return self._fernet.decrypt(token)
        except (InvalidToken, ValueError, TypeError) as exc:
            raise SecurityError("解密失败：数据无效或密钥不匹配") from exc

    def get_key(self) -> str:
        """返回当前密钥的字符串形式。

        Returns:
            URL-safe base64 编码的 Fernet 密钥。
        """
        return self._key.decode("ascii")

    def rotate(self, key_file: str | Path | None = None) -> str:
        """轮换密钥并（可选）写回密钥文件。

        已有密文将无法用新密钥解密，调用方需自行迁移数据。

        Args:
            key_file: 写回路径；为 ``None`` 时沿用当前密钥文件。

        Returns:
            新的 Fernet 密钥字符串。

        Raises:
            SecurityError: 写回密钥文件失败。
        """
        new_key = Fernet.generate_key()
        self._key = new_key
        self._fernet = Fernet(new_key)
        target = Path(key_file).expanduser() if key_file else self._key_file
        if target is not None:
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                with os.fdopen(
                    os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "wb"
                ) as fh:
                    fh.write(new_key)
            except OSError as exc:
                raise SecurityError("写入新密钥失败", path=str(target)) from exc
            self._key_file = target
        return new_key.decode("ascii")


# --------------------------------------------------------------------------- #
# 模块级便捷函数（进程内单例）
# --------------------------------------------------------------------------- #

_manager: CryptoManager | None = None


def get_crypto_manager() -> CryptoManager:
    """获取进程内共享的 :class:`CryptoManager` 单例。

    Returns:
        加密管理器实例。
    """
    global _manager
    if _manager is None:
        _manager = CryptoManager()
    return _manager


def reset_crypto_manager() -> None:
    """清除进程内缓存的加密管理器（主要供测试使用）。"""
    global _manager
    _manager = None


def encrypt_data(data: str) -> str:
    """使用应用密钥加密字符串。

    Args:
        data: 明文。

    Returns:
        密文。
    """
    return get_crypto_manager().encrypt(data)


def decrypt_data(encrypted_data: str) -> str:
    """使用应用密钥解密字符串。

    Args:
        encrypted_data: 密文。

    Returns:
        明文。

    Raises:
        SecurityError: 解密失败。
    """
    return get_crypto_manager().decrypt(encrypted_data)


def _derive_key_from_password(password: str, salt: bytes) -> bytes:
    """由口令与随机盐派生 Fernet 密钥。

    Args:
        password: 用户口令。
        salt: 随机盐值。

    Returns:
        Fernet 可用的密钥字节串。
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))


def encrypt_with_password(data: str, password: str) -> str:
    """使用口令（而非应用密钥）加密字符串。

    密文自带随机盐，格式为 ``<salt_hex>$<fernet_token>``，因此同一条明文
    每次加密结果都不同，且解密时只需要同一口令。

    Args:
        data: 明文。
        password: 用于派生密钥的口令。

    Returns:
        形如 ``<salt_hex>$<token>`` 的密文串。

    Raises:
        SecurityError: 加密失败。
    """
    salt = os.urandom(16)
    key = _derive_key_from_password(password, salt)
    try:
        token = Fernet(key).encrypt(data.encode("utf-8")).decode("ascii")
    except Exception as exc:  # pragma: no cover - Fernet 极少失败
        raise SecurityError("加密失败", reason=str(exc)) from exc
    return f"{salt.hex()}${token}"


def decrypt_with_password(token: str, password: str) -> str:
    """使用口令解密 :func:`encrypt_with_password` 产出的密文。

    Args:
        token: 形如 ``<salt_hex>$<fernet_token>`` 的密文串。
        password: 与该密文匹配的口令。

    Returns:
        解密后的明文；口令错误或密文损坏时返回空字符串。

    Notes:
        出于安全考虑，解密失败时不区分「口令错误」与「数据损坏」，
        统一返回空串，避免向调用方泄露可区分的错误信息。
    """
    try:
        salt_hex, payload = token.split("$", 1)
        key = _derive_key_from_password(password, bytes.fromhex(salt_hex))
        return Fernet(key).decrypt(payload.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, TypeError, binascii.Error):
        return ""


def hash_password(password: str, salt: str | None = None) -> str:
    """使用 PBKDF2-HMAC-SHA256 派生密码哈希。

    Args:
        password: 明文密码。
        salt: 十六进制盐值；为 ``None`` 时随机生成。

    Returns:
        形如 ``<salt>$<hex-digest>`` 的哈希串。
    """
    if salt is None:
        salt = os.urandom(32).hex()
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ITERATIONS
    )
    return f"{salt}${digest.hex()}"


def verify_password(password: str, hashed_password: str) -> bool:
    """校验密码是否与哈希串匹配。

    Args:
        password: 待校验的明文密码。
        hashed_password: :func:`hash_password` 产出的哈希串。

    Returns:
        匹配返回 ``True``，否则 ``False``（包括哈希串格式非法的情况）。
    """
    try:
        salt, expected = hashed_password.split("$", 1)
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ITERATIONS
    )
    return hmac.compare_digest(digest.hex(), expected)


__all__ = [
    "CryptoManager",
    "DEFAULT_KEY_FILE",
    "ENV_KEY",
    "ENV_KEY_FILE",
    "decrypt_data",
    "decrypt_with_password",
    "default_key_file",
    "encrypt_data",
    "encrypt_with_password",
    "generate_key",
    "get_crypto_manager",
    "hash_password",
    "reset_crypto_manager",
    "verify_password",
]

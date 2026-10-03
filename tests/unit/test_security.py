"""
安全模块单元测试

覆盖 :mod:`dwrg_manager.security.crypto` 的加解密、口令加密、密钥管理与密码哈希，
以及 :mod:`dwrg_manager.security.validation` 的全部输入校验函数。
"""

from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from dwrg_manager.exceptions import SecurityError
from dwrg_manager.exceptions import ValidationError as DWRGValidationError
from dwrg_manager.security import crypto as crypto_module
from dwrg_manager.security.crypto import (
    CryptoManager,
    decrypt_data,
    decrypt_with_password,
    encrypt_data,
    encrypt_with_password,
    generate_key,
    hash_password,
    verify_password,
)
from dwrg_manager.security.validation import (
    validate_account_id,
    validate_language,
    validate_password,
    validate_path,
    validate_server_name,
    validate_username,
    validate_version,
)


@pytest.mark.unit
class TestKeyGeneration:
    """密钥生成与解析。"""

    def test_generate_key_returns_valid_fernet_key(self) -> None:
        """生成的密钥应能被 Fernet 接受。"""
        key = generate_key()

        Fernet(key.encode("ascii"))

    def test_normalize_key_accepts_fernet_key(self) -> None:
        """合法 Fernet 密钥应原样返回。"""
        key = generate_key()

        assert crypto_module._normalize_key(key) == key.encode("ascii")

    def test_normalize_key_derives_from_passphrase(self) -> None:
        """非 Fernet 输入应被当作口令派生为合法密钥。"""
        derived = crypto_module._normalize_key("my-passphrase")

        Fernet(derived)


@pytest.mark.unit
class TestStringEncryption:
    """字符串与字节串的加解密。"""

    def test_encrypt_decrypt_roundtrip_with_explicit_key(self) -> None:
        """显式密钥下明文应可往返。"""
        manager = CryptoManager(key=generate_key())

        token = manager.encrypt("secret")

        assert token != "secret"
        assert manager.decrypt(token) == "secret"

    def test_encrypt_decrypt_roundtrip_with_passphrase(self) -> None:
        """口令派生密钥同样应可往返。"""
        manager = CryptoManager(key="a-strong-passphrase")

        assert manager.decrypt(manager.encrypt("secret")) == "secret"

    def test_encrypt_bytes_roundtrip(self) -> None:
        """字节串应可往返。"""
        manager = CryptoManager(key=generate_key())

        token = manager.encrypt_bytes(b"\x00\x01\x02")

        assert manager.decrypt_bytes(token) == b"\x00\x01\x02"

    def test_decrypt_with_tampered_token_raises_security_error(self) -> None:
        """被篡改的密文应抛出 :class:`SecurityError`。"""
        manager = CryptoManager(key=generate_key())

        with pytest.raises(SecurityError):
            manager.decrypt("not-a-valid-token")

    def test_decrypt_with_wrong_key_raises_security_error(self) -> None:
        """密钥不匹配时应抛出 :class:`SecurityError`。"""
        first = CryptoManager(key=generate_key())
        second = CryptoManager(key=generate_key())

        with pytest.raises(SecurityError):
            second.decrypt(first.encrypt("secret"))

    def test_get_key_returns_base64_string(self) -> None:
        """``get_key`` 应返回可再次使用的密钥字符串。"""
        manager = CryptoManager(key=generate_key())
        other = CryptoManager(key=manager.get_key())

        assert other.decrypt(manager.encrypt("secret")) == "secret"


@pytest.mark.unit
class TestKeyFileManagement:
    """密钥文件的创建、复用与轮换。"""

    def test_key_file_is_created_when_absent(self, tmp_path: Path) -> None:
        """密钥文件不存在时应被创建。"""
        key_file = tmp_path / "nested" / "keyfile"

        manager = CryptoManager(key_file=key_file)

        assert key_file.exists()
        assert manager.key_file == key_file

    def test_key_file_is_reused_across_instances(self, tmp_path: Path) -> None:
        """同一密钥文件应可跨实例解密既有密文。"""
        key_file = tmp_path / "keyfile"
        first = CryptoManager(key_file=key_file)
        token = first.encrypt("secret")

        second = CryptoManager(key_file=key_file)

        assert second.decrypt(token) == "secret"

    def test_explicit_key_has_no_key_file(self) -> None:
        """显式密钥时不应关联密钥文件。"""
        manager = CryptoManager(key=generate_key())

        assert manager.key_file is None

    def test_environment_key_takes_precedence(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """环境变量 ``DWRG_ENCRYPTION_KEY`` 应优先于密钥文件。"""
        env_key = generate_key()
        monkeypatch.setenv(crypto_module.ENV_KEY, env_key)

        manager = CryptoManager()

        assert manager.get_key() == env_key

    def test_rotate_changes_key_and_invalidates_old_ciphertext(
        self, tmp_path: Path
    ) -> None:
        """轮换密钥后旧密文应无法解密。"""
        key_file = tmp_path / "keyfile"
        manager = CryptoManager(key_file=key_file)
        old_key = manager.get_key()
        old_token = manager.encrypt("secret")

        new_key = manager.rotate()

        assert new_key != old_key
        assert manager.get_key() == new_key
        with pytest.raises(SecurityError):
            manager.decrypt(old_token)


@pytest.mark.unit
class TestPasswordBasedEncryption:
    """口令加密（自带随机盐）。"""

    def test_password_roundtrip_succeeds(self) -> None:
        """正确口令应还原明文。"""
        token = encrypt_with_password("secret", "passphrase")

        assert decrypt_with_password(token, "passphrase") == "secret"

    def test_same_plaintext_produces_different_tokens(self) -> None:
        """同一明文两次加密结果应不同（随机盐）。"""
        first = encrypt_with_password("secret", "passphrase")
        second = encrypt_with_password("secret", "passphrase")

        assert first != second

    def test_wrong_password_returns_empty_string(self) -> None:
        """口令错误时返回空串而非抛异常。"""
        token = encrypt_with_password("secret", "passphrase")

        assert decrypt_with_password(token, "wrong") == ""

    def test_malformed_token_returns_empty_string(self) -> None:
        """格式非法的密文应返回空串。"""
        assert decrypt_with_password("not-a-token", "passphrase") == ""


@pytest.mark.unit
class TestPasswordHashing:
    """PBKDF2 密码哈希与校验。"""

    def test_hash_password_has_salt_and_digest(self) -> None:
        """哈希串应形如 ``<salt>$<digest>``。"""
        hashed = hash_password("secret")

        salt, digest = hashed.split("$", 1)
        assert salt
        assert digest

    def test_hash_password_with_explicit_salt_is_deterministic(self) -> None:
        """显式盐值时结果应可复现。"""
        first = hash_password("secret", salt="deadbeef")
        second = hash_password("secret", salt="deadbeef")

        assert first == second

    def test_verify_password_accepts_correct_value(self) -> None:
        """正确密码校验通过。"""
        hashed = hash_password("secret")

        assert verify_password("secret", hashed) is True

    def test_verify_password_rejects_wrong_value(self) -> None:
        """错误密码校验失败。"""
        hashed = hash_password("secret")

        assert verify_password("wrong", hashed) is False

    def test_verify_password_rejects_malformed_hash(self) -> None:
        """格式非法的哈希串应返回 ``False``。"""
        assert verify_password("secret", "malformed") is False


@pytest.mark.unit
class TestModuleLevelHelpers:
    """进程级便捷函数与单例管理。"""

    def test_encrypt_data_roundtrip_uses_singleton(self) -> None:
        """模块级函数应基于同一单例往返。"""
        token = encrypt_data("secret")

        assert decrypt_data(token) == "secret"

    def test_reset_crypto_manager_drops_cached_instance(self) -> None:
        """重置后应重新构建单例。"""
        first = crypto_module.get_crypto_manager()
        crypto_module.reset_crypto_manager()
        second = crypto_module.get_crypto_manager()

        assert first is not second


@pytest.mark.unit
class TestValidateUsername:
    """``validate_username``。"""

    def test_accepts_valid_username_and_strips_whitespace(self) -> None:
        """合法用户名应被去空白后返回。"""
        assert validate_username("  hero  ") == "hero"

    @pytest.mark.parametrize("value", ["ab", "a" * 21])
    def test_rejects_out_of_range_length(self, value: str) -> None:
        """长度越界应被拒绝。"""
        with pytest.raises(DWRGValidationError):
            validate_username(value)

    def test_rejects_illegal_characters(self) -> None:
        """非法字符应被拒绝。"""
        with pytest.raises(DWRGValidationError):
            validate_username("bad name")

    def test_rejects_non_string(self) -> None:
        """非字符串应被拒绝。"""
        with pytest.raises(DWRGValidationError):
            validate_username(123)  # type: ignore[arg-type]


@pytest.mark.unit
class TestValidatePassword:
    """``validate_password``。"""

    def test_accepts_valid_password(self) -> None:
        """合法密码原样返回。"""
        assert validate_password("secret123") == "secret123"

    @pytest.mark.parametrize("value", ["12345", "a" * 129])
    def test_rejects_out_of_range_length(self, value: str) -> None:
        """长度越界应被拒绝。"""
        with pytest.raises(DWRGValidationError):
            validate_password(value)

    def test_rejects_whitespace_only(self) -> None:
        """全空白密码应被拒绝。"""
        with pytest.raises(DWRGValidationError):
            validate_password("        ")

    def test_rejects_non_string(self) -> None:
        """非字符串应被拒绝。"""
        with pytest.raises(DWRGValidationError):
            validate_password(None)  # type: ignore[arg-type]


@pytest.mark.unit
class TestValidateAccountId:
    """``validate_account_id``。"""

    def test_accepts_long_enough_id(self) -> None:
        """足够长的 ID 原样返回。"""
        assert validate_account_id("acc-0001") == "acc-0001"

    def test_rejects_short_id(self) -> None:
        """过短的 ID 应被拒绝。"""
        with pytest.raises(DWRGValidationError):
            validate_account_id("short")

    def test_rejects_non_string(self) -> None:
        """非字符串应被拒绝。"""
        with pytest.raises(DWRGValidationError):
            validate_account_id(1)  # type: ignore[arg-type]


@pytest.mark.unit
class TestValidateServerName:
    """``validate_server_name``。"""

    def test_accepts_valid_name(self) -> None:
        """合法名称原样返回。"""
        assert validate_server_name("official") == "official"

    @pytest.mark.parametrize("value", ["", "   ", "bad name"])
    def test_rejects_empty_or_illegal(self, value: str) -> None:
        """空或含非法字符应被拒绝。"""
        with pytest.raises(DWRGValidationError):
            validate_server_name(value)

    def test_accepts_name_in_known_set(self) -> None:
        """在已知集合中时应通过。"""
        assert validate_server_name("guild", known=["guild", "official"]) == "guild"

    def test_rejects_name_outside_known_set(self) -> None:
        """不在已知集合中应被拒绝。"""
        with pytest.raises(DWRGValidationError):
            validate_server_name("guild", known=["official"])


@pytest.mark.unit
class TestValidateVersion:
    """``validate_version``。"""

    def test_accepts_dotted_version(self) -> None:
        """形如 ``1.0.0`` 的版本应通过。"""
        assert validate_version(" 1.0.0 ") == "1.0.0"

    def test_rejects_invalid_version(self) -> None:
        """非数字点分格式应被拒绝。"""
        with pytest.raises(DWRGValidationError):
            validate_version("v1")

    def test_rejects_non_string(self) -> None:
        """非字符串应被拒绝。"""
        with pytest.raises(DWRGValidationError):
            validate_version(1.0)  # type: ignore[arg-type]


@pytest.mark.unit
class TestValidateLanguage:
    """``validate_language``。"""

    def test_accepts_supported_language(self) -> None:
        """受支持语言应通过。"""
        assert validate_language("en-US") == "en-US"

    def test_rejects_unsupported_language(self) -> None:
        """不受支持语言应被拒绝。"""
        with pytest.raises(DWRGValidationError):
            validate_language("xx-XX")

    def test_rejects_non_string(self) -> None:
        """非字符串应被拒绝。"""
        with pytest.raises(DWRGValidationError):
            validate_language(1)  # type: ignore[arg-type]


@pytest.mark.unit
class TestValidatePath:
    """``validate_path`` 的规范化与越界防护。"""

    def test_returns_resolved_absolute_path(self, tmp_path: Path) -> None:
        """返回值应为解析后的绝对路径。"""
        result = validate_path(tmp_path / "sub" / "file")

        assert result.is_absolute()
        assert result.name == "file"

    def test_accepts_path_inside_base(self, tmp_path: Path) -> None:
        """位于允许目录之内应通过。"""
        result = validate_path(tmp_path / "sub" / "file", base=tmp_path)

        assert tmp_path in result.parents

    def test_rejects_path_outside_base(self, tmp_path: Path) -> None:
        """越出允许目录应被拒绝。"""
        with pytest.raises(DWRGValidationError):
            validate_path(tmp_path.parent / "elsewhere", base=tmp_path)

    def test_rejects_missing_path_when_required(self, tmp_path: Path) -> None:
        """要求存在但缺失时应被拒绝。"""
        with pytest.raises(DWRGValidationError):
            validate_path(tmp_path / "missing", must_exist=True)

    def test_rejects_invalid_type(self) -> None:
        """非字符串/Path 应被拒绝。"""
        with pytest.raises(DWRGValidationError):
            validate_path(123)  # type: ignore[arg-type]

"""
安全模块

本模块是项目内**唯一**的加密与输入校验实现来源：

* :mod:`dwrg_manager.security.crypto` —— 应用级密钥管理与对称加密、
  密码哈希与校验。
* :mod:`dwrg_manager.security.validation` —— 用户名/密码/渠道服/路径等
  业务输入的校验。

``dwrg_manager.utils.crypto`` 与 ``dwrg_manager.utils.security`` 仅作为
向后兼容的再导出层存在，请在新代码中直接使用本包。
"""

from .crypto import (
    CryptoManager,
    decrypt_data,
    decrypt_with_password,
    encrypt_data,
    encrypt_with_password,
    generate_key,
    hash_password,
    verify_password,
)
from .validation import (
    validate_account_id,
    validate_language,
    validate_password,
    validate_path,
    validate_server_name,
    validate_username,
    validate_version,
)

__all__ = [
    "CryptoManager",
    "encrypt_data",
    "decrypt_data",
    "encrypt_with_password",
    "decrypt_with_password",
    "generate_key",
    "hash_password",
    "verify_password",
    "validate_account_id",
    "validate_language",
    "validate_password",
    "validate_path",
    "validate_server_name",
    "validate_username",
    "validate_version",
]

"""
加密工具（向后兼容再导出层）

实现已迁移至 :mod:`dwrg_manager.security.crypto`。请在新代码中直接
``from dwrg_manager.security import encrypt_data``。
"""

from ..security.crypto import (
    CryptoManager,
    decrypt_data,
    encrypt_data,
    generate_key,
    get_crypto_manager,
    hash_password,
    reset_crypto_manager,
    verify_password,
)

__all__ = [
    "CryptoManager",
    "encrypt_data",
    "decrypt_data",
    "generate_key",
    "get_crypto_manager",
    "hash_password",
    "reset_crypto_manager",
    "verify_password",
]

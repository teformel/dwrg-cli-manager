"""
安全工具
"""

import base64
import hashlib
import os

from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


def hash_password(password: str, salt: str | None = None) -> str:
    """哈希密码"""
    if salt is None:
        salt = os.urandom(32).hex()

    key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    )

    return f"{salt}${key.hex()}"


def verify_password(password: str, hashed_password: str) -> bool:
    """验证密码"""
    try:
        salt, key = hashed_password.split('$')
        new_key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000
        )
        return new_key.hex() == key
    except:
        return False


def generate_key(password: str, salt: str = None) -> bytes:
    """生成加密密钥"""
    if salt is None:
        salt = os.urandom(16)

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
        backend=default_backend()
    )

    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key


def encrypt_data(data: str, password: str) -> str:
    """加密数据"""
    salt = os.urandom(16)
    key = generate_key(password, salt)
    f = Fernet(key)
    encrypted = f.encrypt(data.encode())
    return f"{salt.hex()}${encrypted.decode('utf-8')}"


def decrypt_data(encrypted_data: str, password: str) -> str:
    """解密数据"""
    try:
        salt_hex, encrypted = encrypted_data.split('$')
        salt = bytes.fromhex(salt_hex)
        key = generate_key(password, salt)
        f = Fernet(key)
        decrypted = f.decrypt(encrypted.encode('utf-8'))
        return decrypted.decode('utf-8')
    except:
        return ""

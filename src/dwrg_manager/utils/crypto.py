"""
加密工具
"""

import base64
import logging
import os

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


def get_logger(name: str = "dwrg") -> logging.Logger:
    """获取日志器"""
    return logging.getLogger(name)


class CryptoManager:
    """加密管理器"""

    def __init__(self, key: bytes | None = None):
        self.logger = get_logger(__name__)
        self.key = key or self._generate_key()
        self.fernet = Fernet(self.key)

    def _generate_key(self) -> bytes:
        """生成加密密钥"""
        # 从环境变量获取密钥，如果没有则生成新的
        env_key = os.environ.get('DWRG_ENCRYPTION_KEY')
        if env_key:
            try:
                # 如果是base64编码的，解码它
                if len(env_key) > 32:
                    return base64.urlsafe_b64decode(env_key)
                else:
                    # 如果是短密钥，使用PBKDF2派生
                    password = env_key.encode()
                    salt = b'dwrg_salt'  # 在实际应用中应该使用随机盐
                    kdf = PBKDF2HMAC(
                        algorithm=hashes.SHA256(),
                        length=32,
                        salt=salt,
                        iterations=100000,
                    )
                    return base64.urlsafe_b64encode(kdf.derive(password))
            except Exception as e:
                self.logger.warning(f"环境变量密钥无效，使用默认密钥: {e}")

        # 生成新的密钥
        return Fernet.generate_key()

    def encrypt_data(self, data: str) -> str:
        """加密数据"""
        try:
            encrypted = self.fernet.encrypt(data.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception as e:
            self.logger.error(f"加密失败: {e}")
            raise

    def decrypt_data(self, encrypted_data: str) -> str:
        """解密数据"""
        try:
            # 解码base64
            encrypted = base64.urlsafe_b64decode(encrypted_data.encode())
            # 解密
            decrypted = self.fernet.decrypt(encrypted)
            return decrypted.decode()
        except Exception as e:
            self.logger.error(f"解密失败: {e}")
            raise

    def generate_key(self) -> str:
        """生成新的加密密钥"""
        new_key = Fernet.generate_key()
        return base64.urlsafe_b64encode(new_key).decode()

    def get_key(self) -> str:
        """获取当前密钥"""
        return base64.urlsafe_b64encode(self.key).decode()


# 全局加密管理器实例
crypto_manager = CryptoManager()


def encrypt_data(data: str) -> str:
    """加密数据（便捷函数）"""
    return crypto_manager.encrypt_data(data)


def decrypt_data(encrypted_data: str) -> str:
    """解密数据（便捷函数）"""
    return crypto_manager.decrypt_data(encrypted_data)

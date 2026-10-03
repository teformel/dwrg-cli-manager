"""
账号管理器
"""

import uuid
from datetime import datetime

from ..config.manager import ConfigManager
from ..utils.logger import get_logger
from ..utils.security import encrypt_data, verify_password
from .models import Account

logger = get_logger(__name__)


class AccountManager:
    """账号管理器"""

    def __init__(self):
        self.config_manager = ConfigManager()

    def create_account(self, username: str, server: str, password: str,
                      account_id: str | None = None) -> Account:
        """创建账号"""
        # 检查用户名是否已存在
        existing_accounts = self.list_accounts()
        if any(acc.username == username for acc in existing_accounts):
            raise ValueError("用户名已存在")

        # 生成账号ID
        if not account_id:
            account_id = str(uuid.uuid4())

        # 加密密码
        encrypted_password = encrypt_data(password, password)

        # 创建账号
        account = Account(
            id=account_id,
            username=username,
            server=server,
            encrypted_password=encrypted_password,
            created_at=datetime.now(),
            last_login=datetime.now()
        )

        # 保存到配置
        self.config_manager.add_account(
            username=account.username,
            server=account.server,
            password=account.encrypted_password,
            account_id=account.id
        )
        self.config_manager.save_config()

        logger.info(f"创建账号: {username}")
        return account

    def list_accounts(self, server: str | None = None) -> list[Account]:
        """列出账号"""
        try:
            accounts_data = self.config_manager.list_accounts(server)
            accounts = []

            for acc_data in accounts_data:
                account = Account(
                id=acc_data.id,
                username=acc_data.username,
                server=acc_data.server,
                encrypted_password=acc_data.encrypted_password,
                created_at=acc_data.created_at,
                last_login=acc_data.last_login,
                is_current=acc_data.is_current
            )
                accounts.append(account)

            return accounts

        except Exception as e:
            logger.error(f"列出账号失败: {e}")
            raise

    def get_account(self, account_id: str) -> Account | None:
        """获取账号"""
        try:
            acc_data = self.config_manager.get_account_config(account_id)
            if not acc_data:
                return None

            return Account(
                id=acc_data.id,
                username=acc_data.username,
                server=acc_data.server,
                encrypted_password=acc_data.encrypted_password,
                created_at=acc_data.created_at,
                last_login=acc_data.last_login,
                is_current=acc_data.is_current
            )

        except Exception as e:
            logger.error(f"获取账号失败: {e}")
            raise

    def update_account(self, account_id: str, **kwargs) -> bool:
        """更新账号"""
        try:
            # 这里需要实现更新逻辑
            # 由于配置管理器目前不支持更新单个账号，需要先删除再添加
            current_account = self.get_account(account_id)
            if not current_account:
                return False

            # 更新字段
            for key, value in kwargs.items():
                if hasattr(current_account, key):
                    setattr(current_account, key, value)

            # 删除旧账号
            self.config_manager.remove_account(account_id)

            # 添加更新后的账号
            self.config_manager.add_account(current_account)
            self.config_manager.save_config()

            logger.info(f"更新账号: {account_id}")
            return True

        except Exception as e:
            logger.error(f"更新账号失败: {e}")
            return False

    def remove_account(self, account_id: str) -> bool:
        """删除账号"""
        try:
            success = self.config_manager.remove_account(account_id)
            if success:
                logger.info(f"删除账号: {account_id}")
            return success

        except Exception as e:
            logger.error(f"删除账号失败: {e}")
            return False

    def switch_account(self, account_id: str) -> bool:
        """切换当前账号"""
        try:
            success = self.config_manager.switch_account(account_id)
            if success:
                # 更新最后登录时间
                self.update_account(account_id, last_login=datetime.now())
            return success

        except Exception as e:
            logger.error(f"切换账号失败: {e}")
            return False

    def get_current_account(self) -> Account | None:
        """获取当前账号"""
        try:
            acc_data = self.config_manager.get_current_account()
            if not acc_data:
                return None

            return Account(
                id=acc_data.id,
                username=acc_data.username,
                server=acc_data.server,
                encrypted_password=acc_data.encrypted_password,
                created_at=acc_data.created_at,
                last_login=acc_data.last_login,
                is_current=acc_data.is_current
            )

        except Exception as e:
            logger.error(f"获取当前账号失败: {e}")
            return None

    def authenticate(self, username: str, password: str) -> Account | None:
        """验证账号"""
        try:
            accounts = self.list_accounts()
            for acc in accounts:
                if acc.username == username and verify_password(password, acc.password_hash):
                    return acc
            return None

        except Exception as e:
            logger.error(f"验证账号失败: {e}")
            return None

"""
账号管理模块

对外暴露账号管理器、运行时模型、登录态与账号迁移能力：

* :class:`~dwrg_manager.accounts.manager.AccountManager` —— 账号业务入口；
* :class:`~dwrg_manager.accounts.models.Account` /
  :class:`~dwrg_manager.accounts.models.LoginResult` —— 运行时模型；
* :class:`~dwrg_manager.accounts.session.Session` —— 登录态模型及读写；
* :class:`~dwrg_manager.accounts.transfer.ExportedAccount` —— 导出/导入材料。
"""

from .gacha import GachaScanResult, scan_gacha_logs
from .manager import AccountManager
from .models import Account, LoginResult
from .session import Session, get_active_session
from .transfer import ExportedAccount, ImportReport

__all__ = [
    "Account",
    "AccountManager",
    "ExportedAccount",
    "GachaScanResult",
    "ImportReport",
    "LoginResult",
    "Session",
    "get_active_session",
    "scan_gacha_logs",
]

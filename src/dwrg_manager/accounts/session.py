"""
登录态管理

把「当前登录的账号」从主配置中独立出来，落到 ``~/.dwrg/session.json``
（权限 ``0600``，原子写入）。启动器通过 :func:`get_active_session` 读取
登录态并注入子进程环境变量，因此本模块只负责读写，不感知启动细节。

与主配置的关系：

* ``login`` 同时更新配置里的 ``app.account``（保持既有行为）并写登录态；
* ``logout`` 清除登录态文件与配置中的当前账号；
* 登录态文件损坏时视为「未登录」并记录日志，不让 CLI 直接崩溃。
"""

import json
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..exceptions import AccountError
from ..utils.atomic import atomic_write_text
from ..utils.logger import get_logger

logger = get_logger(__name__)

#: 登录态文件相对于用户主目录的位置
_SESSION_RELATIVE_PATH: Path = Path(".dwrg") / "session.json"

#: 登录态文件中的格式版本号
SESSION_VERSION: int = 1

#: 令牌占位符：本地尚未接入真实登录协议
TOKEN_PLACEHOLDER: str = "pending"

__all__ = [
    "SESSION_VERSION",
    "Session",
    "TOKEN_PLACEHOLDER",
    "clear_session",
    "default_session_path",
    "get_active_session",
    "read_session",
    "session_env_vars",
    "write_session",
]


def default_session_path() -> Path:
    """返回登录态文件的默认路径。

    路径在调用时才解析（而非导入时），以便测试通过重定向 ``HOME`` /
    ``USERPROFILE`` 环境变量把登录态隔离到临时目录。

    Returns:
        ``~/.dwrg/session.json``。
    """
    return Path.home() / _SESSION_RELATIVE_PATH


class Session(BaseModel):
    """当前登录态。

    Attributes:
        account_id: 已登录的账号 ID。
        server: 登录时使用的渠道服。
        username: 账号用户名（便于展示，不用于鉴权）。
        logged_in_at: 登录时间。
        token: 登录令牌占位，待接入真实协议后替换。
        version: 登录态文件格式版本。
    """

    model_config = ConfigDict(validate_assignment=True)

    account_id: str = Field(..., description="账号ID")
    server: str = Field("", description="渠道服")
    username: str = Field("", description="用户名")
    logged_in_at: datetime = Field(default_factory=datetime.now, description="登录时间")
    token: str = Field(TOKEN_PLACEHOLDER, description="登录令牌占位")
    version: int = Field(SESSION_VERSION, description="登录态格式版本")

    @field_validator("account_id")
    @classmethod
    def _check_account_id(cls, v: str) -> str:
        """校验账号 ID 非空且长度足够。

        Args:
            v: 待校验的账号 ID。

        Returns:
            去除首尾空白后的账号 ID。

        Raises:
            ValueError: ID 为空或长度不足 8 个字符。
        """
        value = v.strip()
        if len(value) < 8:
            raise ValueError("账号ID长度不能少于8个字符")
        return value

    def to_dict(self) -> dict[str, object]:
        """导出为可 JSON 序列化的字典。

        Returns:
            ``datetime`` 已转为 ISO 8601 字符串的字典。
        """
        return self.model_dump(mode="json")


def write_session(session: Session, path: str | Path | None = None) -> Path:
    """把登录态原子写入磁盘。

    Args:
        session: 待保存的登录态。
        path: 目标文件路径；为 ``None`` 时使用 :func:`default_session_path`。

    Returns:
        实际写入的文件路径。

    Raises:
        OSError: 写入失败（磁盘已满、权限不足等）。
    """
    target = Path(path).expanduser() if path else default_session_path()
    payload = json.dumps(session.to_dict(), ensure_ascii=False, indent=2) + "\n"
    written = atomic_write_text(target, payload)
    logger.debug("已写入登录态: %s", written)
    return written


def read_session(path: str | Path | None = None) -> Session | None:
    """从磁盘读取登录态。

    文件不存在、内容损坏或字段不合法时都视为「未登录」，返回 ``None``
    并记录日志，不会向调用方抛异常。

    Args:
        path: 登录态文件路径；为 ``None`` 时使用 :func:`default_session_path`。

    Returns:
        :class:`Session` 实例；未登录或读取失败时返回 ``None``。
    """
    target = Path(path).expanduser() if path else default_session_path()
    if not target.exists():
        return None
    try:
        raw = target.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("登录态读取失败 %s: %s", target, exc)
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("登录态解析失败 %s: %s", target, exc)
        return None
    if not isinstance(data, dict):
        logger.warning("登录态顶层应为对象: %s", target)
        return None
    try:
        return Session(**data)
    except Exception as exc:  # pydantic.ValidationError
        logger.warning("登录态字段不合法 %s: %s", target, exc)
        return None


def clear_session(path: str | Path | None = None) -> bool:
    """删除登录态文件（登出）。

    Args:
        path: 登录态文件路径；为 ``None`` 时使用 :func:`default_session_path`。

    Returns:
        文件此前是否存在（幂等删除，重复调用返回 ``False``）。

    Raises:
        AccountError: 文件存在但删除失败。
    """
    target = Path(path).expanduser() if path else default_session_path()
    try:
        target.unlink()
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise AccountError("删除登录态失败", path=str(target), reason=str(exc)) from exc
    logger.debug("已清除登录态: %s", target)
    return True


def get_active_session(path: str | Path | None = None) -> Session | None:
    """读取当前生效的登录态（供启动器注入环境变量）。

    Args:
        path: 登录态文件路径；为 ``None`` 时使用 :func:`default_session_path`。

    Returns:
        :class:`Session` 实例；未登录时返回 ``None``。
    """
    return read_session(path)


def session_env_vars(session: Session | None) -> dict[str, str]:
    """把登录态转换为启动器可注入的环境变量。

    Args:
        session: 当前登录态；为 ``None`` 时返回空字典。

    Returns:
        形如 ``{"DWRG_ACCOUNT": ..., "DWRG_SERVER": ...}`` 的字典。
    """
    if session is None:
        return {}
    env: dict[str, str] = {"DWRG_ACCOUNT": session.account_id}
    if session.server:
        env["DWRG_SERVER"] = session.server
    if session.username:
        env["DWRG_ACCOUNT_NAME"] = session.username
    return env

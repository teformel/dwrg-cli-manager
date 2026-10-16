"""
原子文件写入

为「写入中断不应留下半个文件」的场景提供统一 helper：先写同目录临时文件，
再通过 :func:`os.replace` 覆盖目标。密钥文件、登录态、账号导出包等敏感
文件还要求 ``0600`` 权限，因此临时文件同样以目标权限创建，避免替换之前
被同机其他用户读取。

Example:
    >>> from dwrg_manager.utils.atomic import atomic_write_text  # doctest: +SKIP
    >>> atomic_write_text("/tmp/demo.txt", "hello")  # doctest: +SKIP
    PosixPath('/tmp/demo.txt')
"""

import os
import tempfile
from pathlib import Path

#: 敏感文件（密钥、登录态、导出包）的默认权限：仅所有者可读写
SECURE_FILE_MODE: int = 0o600

__all__ = ["SECURE_FILE_MODE", "atomic_write_text"]


def atomic_write_text(
    path: str | Path,
    text: str,
    *,
    mode: int = SECURE_FILE_MODE,
    encoding: str = "utf-8",
) -> Path:
    """以原子方式把文本写入文件。

    写入流程为「同目录临时文件 -> ``fsync`` -> ``os.replace``」，因此要么
    得到完整的旧内容，要么得到完整的新内容，不会出现半截文件。临时文件
    以 ``mode`` 权限创建并显式 ``chmod``，保证替换前也不可被他人读取。

    Args:
        path: 目标文件路径，``~`` 会被展开，父目录不存在时自动创建。
        text: 待写入的文本内容。
        mode: 文件权限位，默认为 :data:`SECURE_FILE_MODE`（``0600``）。
        encoding: 文本编码，默认为 UTF-8。

    Returns:
        实际写入的文件路径（展开后的路径）。

    Raises:
        OSError: 创建临时文件、写入或替换失败。
    """
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(
        prefix=target.name + ".", suffix=".tmp", dir=str(target.parent)
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp_path, mode)
        os.replace(tmp_path, target)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise
    return target

"""
资源校验器

提供分块流式哈希、整文件校验、抽样快速校验与人类可读体积格式化。

设计要点：
    - :meth:`Validator.hash_file` 使用分块流式读取，避免整文件读入内存。
    - :meth:`Validator.quick_check` 只有在「文件大小一致」且「清单单独提供了
      抽样哈希字段」时才启用抽样校验；否则返回 ``False``，由调用方回退到
      :meth:`Validator.verify` 做全量校验。
    - 所有校验方法在失败时只记录日志并返回 ``False``，不抛异常。
"""

import hashlib
from pathlib import Path

from ..utils.logger import get_logger

logger = get_logger(__name__)

#: 流式哈希读取块大小（1 MiB）。
_CHUNK_SIZE = 1 << 20

#: 抽样校验时头/尾各采样的字节数。
_SAMPLE_SIZE = 1024

#: 体积格式化使用的单位序列。
_SIZE_UNITS: tuple[str, ...] = ("B", "KB", "MB", "GB", "TB")


class Validator:
    """资源文件校验器。"""

    def hash_file(self, path: Path, algorithm: str = "md5") -> str:
        """分块流式计算文件哈希。

        Args:
            path: 目标文件路径。
            algorithm: ``hashlib`` 支持的算法名，默认为 ``md5``。

        Returns:
            十六进制小写哈希字符串。

        Raises:
            FileNotFoundError: 文件不存在。
            ValueError: ``algorithm`` 不受支持。

        Example:
            >>> Validator().hash_file(Path("a.bin")) == hashlib.md5(b"...").hexdigest()
            True
        """
        digest = hashlib.new(algorithm)
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(_CHUNK_SIZE), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def sample_hash(self, path: Path, sample_size: int = _SAMPLE_SIZE) -> str:
        """对文件头、尾各采样固定字节数求 MD5（抽样哈希）。

        该算法是清单 ``partial_hash`` 字段的生产/消费约定：文件小于等于
        ``sample_size`` 时只取头部；否则取「头部 ``sample_size`` 字节 + 尾部
        ``sample_size`` 字节」，两段不重叠。

        Args:
            path: 目标文件路径。
            sample_size: 头尾各采样字节数，默认 1024。

        Returns:
            抽样内容的 MD5 十六进制字符串。

        Raises:
            FileNotFoundError: 文件不存在。
        """
        digest = hashlib.md5()
        size = path.stat().st_size
        with open(path, "rb") as handle:
            digest.update(handle.read(sample_size))
            if size > sample_size:
                handle.seek(max(size - sample_size, sample_size))
                digest.update(handle.read(sample_size))
        return digest.hexdigest()

    def verify(
        self,
        path: Path,
        *,
        size: int | None = None,
        md5: str | None = None,
        sha256: str | None = None,
    ) -> bool:
        """全量校验文件的大小与哈希。

        Args:
            path: 目标文件路径。
            size: 期望文件大小（字节）；``None`` 表示不校验大小。
            md5: 期望的整文件 MD5；``None`` 或空串表示不校验。
            sha256: 期望的整文件 SHA256；``None`` 或空串表示不校验。

        Returns:
            校验通过返回 ``True``，任一条件不符或读取失败返回 ``False``。

        Example:
            >>> Validator().verify(Path("a.bin"), size=3, md5="900150983cd24fb0d6963f7d28e17f72")
            True
        """
        try:
            if not path.is_file():
                logger.warning("校验失败，文件不存在: %s", path)
                return False
            actual_size = path.stat().st_size
            if size is not None and actual_size != size:
                logger.warning(
                    "校验失败，大小不符: %s (实际 %d, 期望 %d)",
                    path,
                    actual_size,
                    size,
                )
                return False
            if md5 and self.hash_file(path, "md5") != md5:
                logger.warning("校验失败，MD5 不符: %s", path)
                return False
            if sha256 and self.hash_file(path, "sha256") != sha256:
                logger.warning("校验失败，SHA256 不符: %s", path)
                return False
            return True
        except OSError as exc:
            logger.warning("校验失败，读取异常: %s (%s)", path, exc)
            return False

    def quick_check(
        self,
        path: Path,
        size: int,
        partial_hash: str | None = None,
    ) -> bool:
        """基于抽样哈希的快速校验。

        仅在「文件存在且大小与期望一致」且「提供了抽样哈希」时才比较抽样哈希；
        当 ``partial_hash`` 为 ``None``（清单未提供该字段）时，不做抽样，直接返回
        ``False``，提示调用方改用 :meth:`verify` 进行全量校验。

        Args:
            path: 目标文件路径。
            size: 期望文件大小（字节）。
            partial_hash: 清单单独提供的抽样哈希；``None`` 表示不可用。

        Returns:
            抽样校验通过返回 ``True``，否则返回 ``False``。

        Example:
            >>> validator.quick_check(Path("a.bin"), 2048, partial_hash="...")
            True
        """
        try:
            if not path.is_file():
                return False
            if path.stat().st_size != size:
                return False
            if partial_hash is None:
                logger.debug("清单未提供抽样哈希，quick_check 不适用: %s", path)
                return False
            return self.sample_hash(path) == partial_hash
        except OSError as exc:
            logger.warning("快速校验异常: %s (%s)", path, exc)
            return False

    @staticmethod
    def human_size(num_bytes: int) -> str:
        """将字节数格式化为人类可读字符串。

        Args:
            num_bytes: 字节数，允许为 0。

        Returns:
            形如 ``"1.23 MB"`` 的字符串（1024 进制，保留两位小数）。

        Example:
            >>> Validator.human_size(0)
            '0.00 B'
            >>> Validator.human_size(1024)
            '1.00 KB'
        """
        value = float(num_bytes)
        for unit in _SIZE_UNITS:
            if value < 1024.0 or unit == _SIZE_UNITS[-1]:
                return f"{value:.2f} {unit}"
            value /= 1024.0
        return f"{value:.2f} PB"

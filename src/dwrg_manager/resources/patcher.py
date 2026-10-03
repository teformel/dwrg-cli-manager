"""
资源补丁器

职责：
    - :meth:`Patcher.plan` 对比本地清单与远端清单，区分新增 / 更新 / 删除 / 未变化。
    - :meth:`Patcher.apply` 执行下载、删除失效文件，并在**全部成功**后把远端清单
      落盘到 ``data_dir/manifest.json``（供 :meth:`Patcher.load_manifest` 读回）。
"""

import json
from datetime import datetime
from pathlib import Path

from ..utils.logger import get_logger
from .downloader import Downloader
from .models import (
    DownloadResult,
    DownloadTask,
    PatchPlan,
    PatchResult,
    ProgressCallback,
    ResourceFile,
    ResourceManifest,
)
from .validator import Validator

logger = get_logger(__name__)


class Patcher:
    """负责清单比对、下载编排与清单落盘。"""

    def __init__(
        self,
        *,
        manifest_path: Path,
        game_dir: Path,
        validator: Validator | None = None,
    ) -> None:
        """初始化补丁器。

        Args:
            manifest_path: 本地清单落盘路径（通常为 ``data_dir/manifest.json``）。
            game_dir: 游戏资源根目录。
            validator: 校验器实例，缺省自行创建。
        """
        self.manifest_path = Path(manifest_path)
        self.game_dir = Path(game_dir)
        self._validator = validator or Validator()

    def plan(
        self,
        local_manifest: ResourceManifest | None,
        remote_manifest: ResourceManifest,
    ) -> PatchPlan:
        """生成增量更新计划。

        以 ``path`` 作为文件身份标识；本地缺失视为「新增」，大小或 MD5 变化视为
        「更新」，完全一致视为「未变化」，远端不再包含的本地文件视为「删除」。

        Args:
            local_manifest: 本地已记录清单；``None`` 表示本地无记录（全部视为新增）。
            remote_manifest: 远端目标清单。

        Returns:
            分类后的 :class:`PatchPlan`。
        """
        local_files = {
            f.path: f for f in (local_manifest.files if local_manifest else [])
        }
        remote_files = {f.path: f for f in remote_manifest.files}

        added: list[ResourceFile] = []
        updated: list[ResourceFile] = []
        unchanged: list[ResourceFile] = []
        for path, remote_file in remote_files.items():
            local_file = local_files.get(path)
            if local_file is None:
                added.append(remote_file)
            elif (
                local_file.size != remote_file.size or local_file.md5 != remote_file.md5
            ):
                updated.append(remote_file)
            else:
                unchanged.append(remote_file)

        removed = [
            local_file
            for path, local_file in local_files.items()
            if path not in remote_files
        ]
        return PatchPlan(
            download_url=remote_manifest.download_url,
            remote_manifest=remote_manifest,
            added=added,
            updated=updated,
            removed=removed,
            unchanged=unchanged,
        )

    def load_manifest(self) -> ResourceManifest | None:
        """读取本地清单。

        Returns:
            解析成功返回 :class:`ResourceManifest`；文件不存在或损坏返回 ``None``。
        """
        if not self.manifest_path.exists():
            return None
        try:
            data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            return ResourceManifest(**data)
        except (OSError, ValueError) as exc:
            logger.warning("读取本地清单失败: %s (%s)", self.manifest_path, exc)
            return None

    def save_manifest(self, manifest: ResourceManifest) -> bool:
        """原子落盘本地清单。

        Args:
            manifest: 待保存的清单。

        Returns:
            保存成功返回 ``True``，失败返回 ``False``。
        """
        try:
            self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
            payload = manifest.model_dump(mode="json")
            tmp_path = self.manifest_path.with_name(self.manifest_path.name + ".tmp")
            tmp_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            tmp_path.replace(self.manifest_path)
            logger.info(
                "已保存资源清单: %s (version=%s)",
                self.manifest_path,
                manifest.version,
            )
            return True
        except OSError as exc:
            logger.error("保存本地清单失败: %s (%s)", self.manifest_path, exc)
            return False

    def _build_tasks(self, plan: PatchPlan) -> list[DownloadTask]:
        """根据计划构建下载任务（顺序与 :meth:`PatchPlan.files_to_download` 一致）。"""
        base = plan.download_url.rstrip("/")
        return [
            DownloadTask(
                url=f"{base}/{file_info.name}",
                dest=self.game_dir / file_info.path,
                name=file_info.name,
                expected_size=file_info.size,
                expected_md5=file_info.md5,
                resume=True,
            )
            for file_info in plan.files_to_download()
        ]

    async def apply(
        self,
        plan: PatchPlan,
        downloader: Downloader,
        *,
        on_progress: ProgressCallback | None = None,
    ) -> PatchResult:
        """执行增量更新计划。

        Args:
            plan: 由 :meth:`plan` 生成的更新计划。
            downloader: 下载器实例。
            on_progress: 每完成一个下载文件回调一次。

        Returns:
            :class:`PatchResult`；仅当全部下载成功时才落盘远端清单。
        """
        start_time = datetime.now()
        tasks = self._build_tasks(plan)
        results: list[DownloadResult] = []
        failed_files: list[str] = []
        if tasks:
            results = await downloader.download_many(tasks, on_progress=on_progress)
            for task, result in zip(tasks, results, strict=True):
                if not result.success:
                    failed_files.append(task.name or task.dest.name)

        removed_count = 0
        for file_info in plan.removed:
            target = self.game_dir / file_info.path
            try:
                target.unlink(missing_ok=True)
                removed_count += 1
            except OSError as exc:
                logger.warning("删除失效文件失败: %s (%s)", target, exc)

        added_count = 0
        updated_count = 0
        for index, result in enumerate(results):
            if not result.success:
                continue
            if index < len(plan.added):
                added_count += 1
            else:
                updated_count += 1

        success = not failed_files
        if success:
            self.save_manifest(plan.remote_manifest)

        elapsed = (datetime.now() - start_time).total_seconds()
        return PatchResult(
            success=success,
            added=added_count,
            updated=updated_count,
            removed=removed_count,
            failed_files=failed_files,
            results=results,
            error=None if success else f"{len(failed_files)} 个文件下载失败",
            elapsed_time=elapsed,
        )

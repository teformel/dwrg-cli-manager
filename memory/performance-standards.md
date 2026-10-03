---
name: performance-standards-dwrg
description: 第五人格命令行管理器的性能标准和规范
metadata:
  node_type: memory
  type: project
  created_date: 2026-09-21
  status: active
  originSessionId: sess_30048853-8656-4451-96f5-dd221dfd42ae
---

# 性能标准和规范 - 第五人格命令行管理器

## 性能理念

基于Vibe Coding理念，我们将性能作为项目设计的关键要素，确保工具在各种环境下都能提供流畅的用户体验。采用性能驱动开发方法，在功能实现的同时关注性能优化。

## 性能架构

### 1. 性能层次模型

```
┌─────────────────────────────────────────────────────┐
│                   应用层性能                         │
│  • 响应时间  • 内存使用  • CPU占用  • 并发处理     │
├─────────────────────────────────────────────────────┤
│                   业务逻辑性能                       │
│  • 账号管理  • 渠道服切换  • 资源下载  • 游戏启动     │
├─────────────────────────────────────────────────────┤
│                   数据层性能                         │
│  • 文件IO  • 缓存机制  • 数据库查询  • 网络请求     │
├─────────────────────────────────────────────────────┤
│                   系统层性能                         │
│  • 进程管理  • 线程池  • 内存管理  • 垃圾回收     │
└─────────────────────────────────────────────────────┘
```

### 2. 性能目标

| 指标 | 目标值 | 测试条件 |
|------|--------|----------|
| 命令响应时间 | < 100ms | 常规命令 |
| 账号切换时间 | < 500ms | 本地账号 |
| 渠道服切换时间 | < 2s | 标准网络 |
| 文件下载速度 | > 1MB/s | 标准网络 |
| 内存占用 | < 100MB | 空闲状态 |
| CPU占用 | < 5% | 空闲状态 |
| 启动时间 | < 3s | 冷启动 |

## 性能优化规范

### 1. 异步编程规范

```python
# src/dwrg_manager/utils/async_utils.py
import asyncio
import aiofiles
import aiohttp
from typing import List, Dict, Any, Optional, AsyncGenerator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime

@dataclass
class PerformanceMetrics:
    """性能指标"""
    operation: str
    start_time: datetime
    end_time: datetime
    duration: float
    memory_usage: float
    cpu_usage: float
    success: bool
    error_message: Optional[str] = None

class AsyncPerformanceManager:
    """异步性能管理器"""
    
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.metrics: List[PerformanceMetrics] = []
        self.lock = asyncio.Lock()
    
    async def measure_performance(self, operation: str, coro) -> Any:
        """测量异步操作性能"""
        import psutil
        import time
        
        start_time = datetime.now()
        start_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        start_cpu = psutil.Process().cpu_percent()
        
        try:
            result = await coro
            success = True
            error_message = None
        except Exception as e:
            result = None
            success = False
            error_message = str(e)
        
        end_time = datetime.now()
        end_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        end_cpu = psutil.Process().cpu_percent()
        
        duration = (end_time - start_time).total_seconds()
        memory_usage = end_memory - start_memory
        cpu_usage = end_cpu - start_cpu
        
        metrics = PerformanceMetrics(
            operation=operation,
            start_time=start_time,
            end_time=end_time,
            duration=duration,
            memory_usage=memory_usage,
            cpu_usage=cpu_usage,
            success=success,
            error_message=error_message
        )
        
        async with self.lock:
            self.metrics.append(metrics)
        
        return result, metrics
    
    def get_performance_report(self) -> Dict[str, Any]:
        """生成性能报告"""
        if not self.metrics:
            return {"message": "No performance data available"}
        
        # 按操作类型分组
        operation_stats = {}
        for metric in self.metrics:
            if metric.operation not in operation_stats:
                operation_stats[metric.operation] = []
            operation_stats[metric.operation].append(metric)
        
        # 计算统计信息
        report = {}
        for operation, metrics in operation_stats.items():
            durations = [m.duration for m in metrics]
            memory_usages = [m.memory_usage for m in metrics]
            cpu_usages = [m.cpu_usage for m in metrics]
            
            report[operation] = {
                "total_operations": len(metrics),
                "success_rate": sum(1 for m in metrics if m.success) / len(metrics),
                "avg_duration": sum(durations) / len(durations),
                "max_duration": max(durations),
                "min_duration": min(durations),
                "avg_memory": sum(memory_usages) / len(memory_usages),
                "avg_cpu": sum(cpu_usages) / len(cpu_usages),
                "recent_metrics": [
                    {
                        "operation": m.operation,
                        "duration": m.duration,
                        "memory": m.memory_usage,
                        "cpu": m.cpu_usage,
                        "success": m.success,
                        "timestamp": m.start_time.isoformat()
                    }
                    for m in metrics[-10:]  # 最近10个操作
                ]
            }
        
        return report
    
    async def batch_operations(self, operations: List[str], coroutines: List) -> List[Any]:
        """批量异步操作"""
        tasks = []
        for op, coro in zip(operations, coroutines):
            task = self.measure_performance(op, coro)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results

class AsyncFileHandler:
    """异步文件处理器"""
    
    def __init__(self, chunk_size: int = 8192):
        self.chunk_size = chunk_size
    
    async def async_read_file(self, file_path: str) -> str:
        """异步读取文件"""
        async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
            return await f.read()
    
    async def async_write_file(self, file_path: str, content: str) -> bool:
        """异步写入文件"""
        try:
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(content)
            return True
        except Exception:
            return False
    
    async def async_copy_file(self, src: str, dst: str) -> bool:
        """异步复制文件"""
        try:
            async with aiofiles.open(src, 'rb') as src_file:
                async with aiofiles.open(dst, 'wb') as dst_file:
                    while True:
                        chunk = await src_file.read(self.chunk_size)
                        if not chunk:
                            break
                        await dst_file.write(chunk)
            return True
        except Exception:
            return False
    
    async def async_read_lines(self, file_path: str) -> AsyncGenerator[str, None]:
        """异步逐行读取文件"""
        async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
            async for line in f:
                yield line.strip()

class AsyncDownloadManager:
    """异步下载管理器"""
    
    def __init__(self, max_concurrent: int = 4, timeout: int = 30):
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        self.session = aiohttp.ClientSession(timeout=timeout)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.session:
            await self.session.close()
    
    async def download_file(self, url: str, save_path: str, chunk_size: int = 8192) -> bool:
        """异步下载文件"""
        async with self.semaphore:
            try:
                async with self.session.get(url) as response:
                    if response.status == 200:
                        async with aiofiles.open(save_path, 'wb') as f:
                            async for chunk in response.content.iter_chunked(chunk_size):
                                await f.write(chunk)
                        return True
                    else:
                        return False
            except Exception:
                return False
    
    async def download_multiple_files(self, url_list: List[str], save_dir: str) -> Dict[str, bool]:
        """异步下载多个文件"""
        results = {}
        tasks = []
        
        for url in url_list:
            filename = url.split('/')[-1]
            save_path = f"{save_dir}/{filename}"
            task = self.download_file(url, save_path)
            tasks.append((url, task))
        
        # 并发执行所有下载任务
        url_task_pairs = await asyncio.gather(*[task for _, task in tasks], return_exceptions=True)
        
        for (url, _), result in zip(tasks, url_task_pairs):
            results[url] = bool(result) if not isinstance(result, Exception) else False
        
        return results
```

### 2. 缓存管理规范

```python
# src/dwrg_manager/utils/cache_manager.py
import asyncio
import time
import pickle
import hashlib
from typing import Any, Optional, Dict, List, Callable
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

class CacheType(Enum):
    """缓存类型"""
    MEMORY = "memory"
    FILE = "file"
    HYBRID = "hybrid"

@dataclass
class CacheConfig:
    """缓存配置"""
    cache_type: CacheType = CacheType.HYBRID
    max_memory_size: int = 100 * 1024 * 1024  # 100MB
    max_file_size: int = 500 * 1024 * 1024  # 500MB
    default_ttl: int = 3600  # 1小时
    cleanup_interval: int = 300  # 5分钟

@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    value: Any
    created_at: float
    ttl: int
    access_count: int = 0
    last_accessed: float = 0

class CacheManager:
    """缓存管理器"""
    
    def __init__(self, config: CacheConfig, cache_dir: Optional[Path] = None):
        self.config = config
        self.cache_dir = cache_dir or Path.home() / '.dwrg-cli' / 'cache'
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 内存缓存
        self.memory_cache: Dict[str, CacheEntry] = {}
        self.memory_size = 0
        
        # 文件缓存
        self.file_cache: Dict[str, Path] = {}
        
        # 清理任务
        self.cleanup_task: Optional[asyncio.Task] = None
        self.start_cleanup_task()
    
    def start_cleanup_task(self):
        """启动清理任务"""
        if self.cleanup_task is None or self.cleanup_task.done():
            self.cleanup_task = asyncio.create_task(self._cleanup_expired_cache())
    
    async def _cleanup_expired_cache(self):
        """清理过期缓存"""
        while True:
            try:
                await asyncio.sleep(self.config.cleanup_interval)
                await self._cleanup_memory_cache()
                await self._cleanup_file_cache()
            except asyncio.CancelledError:
                break
    
    async def _cleanup_memory_cache(self):
        """清理内存缓存"""
        current_time = time.time()
        expired_keys = []
        
        for key, entry in self.memory_cache.items():
            if current_time - entry.created_at > entry.ttl:
                expired_keys.append(key)
        
        for key in expired_keys:
            self._remove_from_memory_cache(key)
    
    async def _cleanup_file_cache(self):
        """清理文件缓存"""
        current_time = time.time()
        expired_keys = []
        
        for key, file_path in self.file_cache.items():
            if file_path.exists():
                # 检查文件是否过期
                stat = file_path.stat()
                if current_time - stat.st_mtime > self.config.default_ttl:
                    expired_keys.append(key)
        
        for key in expired_keys:
            self._remove_from_file_cache(key)
    
    def _get_cache_key(self, key: str) -> str:
        """生成缓存键"""
        return hashlib.md5(key.encode()).hexdigest()
    
    def _is_memory_cache_full(self) -> bool:
        """检查内存缓存是否已满"""
        return self.memory_size >= self.config.max_memory_size
    
    def _remove_from_memory_cache(self, key: str):
        """从内存缓存中移除"""
        if key in self.memory_cache:
            entry = self.memory_cache.pop(key)
            self.memory_size -= len(pickle.dumps(entry.value))
    
    def _remove_from_file_cache(self, key: str):
        """从文件缓存中移除"""
        if key in self.file_cache:
            file_path = self.file_cache.pop(key)
            if file_path.exists():
                file_path.unlink()
    
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        cache_key = self._get_cache_key(key)
        current_time = time.time()
        
        # 检查内存缓存
        if cache_key in self.memory_cache:
            entry = self.memory_cache[cache_key]
            if current_time - entry.created_at <= entry.ttl:
                entry.access_count += 1
                entry.last_accessed = current_time
                return entry.value
            else:
                self._remove_from_memory_cache(cache_key)
        
        # 检查文件缓存
        if cache_key in self.file_cache:
            file_path = self.file_cache[cache_key]
            if file_path.exists():
                try:
                    with open(file_path, 'rb') as f:
                        entry = pickle.load(f)
                    
                    if current_time - entry.created_at <= entry.ttl:
                        # 加载到内存缓存
                        await self.set(key, entry.value, entry.ttl)
                        entry.access_count += 1
                        entry.last_accessed = current_time
                        return entry.value
                    else:
                        self._remove_from_file_cache(cache_key)
                except Exception:
                    self._remove_from_file_cache(cache_key)
        
        return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存值"""
        if ttl is None:
            ttl = self.config.default_ttl
        
        cache_key = self._get_cache_key(key)
        current_time = time.time()
        
        # 创建缓存条目
        entry = CacheEntry(
            key=cache_key,
            value=value,
            created_at=current_time,
            ttl=ttl
        )
        
        # 存储到内存缓存
        if self.config.cache_type in [CacheType.MEMORY, CacheType.HYBRID]:
            # 如果内存缓存已满，移除最旧的条目
            if self._is_memory_cache_full():
                await self._evict_oldest_memory_entry()
            
            self.memory_cache[cache_key] = entry
            self.memory_size += len(pickle.dumps(value))
        
        # 存储到文件缓存
        if self.config.cache_type in [CacheType.FILE, CacheType.HYBRID]:
            file_path = self.cache_dir / f"{cache_key}.cache"
            try:
                with open(file_path, 'wb') as f:
                    pickle.dump(entry, f)
                self.file_cache[cache_key] = file_path
            except Exception:
                return False
        
        return True
    
    async def _evict_oldest_memory_entry(self):
        """移除最旧的内存缓存条目"""
        if not self.memory_cache:
            return
        
        # 找到最旧的条目
        oldest_key = min(
            self.memory_cache.keys(),
            key=lambda k: self.memory_cache[k].last_accessed
        )
        
        self._remove_from_memory_cache(oldest_key)
    
    async def delete(self, key: str) -> bool:
        """删除缓存"""
        cache_key = self._get_cache_key(key)
        success = True
        
        # 从内存缓存删除
        if cache_key in self.memory_cache:
            self._remove_from_memory_cache(cache_key)
        
        # 从文件缓存删除
        if cache_key in self.file_cache:
            self._remove_from_file_cache(cache_key)
        
        return success
    
    async def clear(self) -> bool:
        """清空所有缓存"""
        # 清空内存缓存
        self.memory_cache.clear()
        self.memory_size = 0
        
        # 清空文件缓存
        for file_path in self.file_cache.values():
            if file_path.exists():
                file_path.unlink()
        self.file_cache.clear()
        
        return True
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        memory_count = len(self.memory_cache)
        file_count = len(self.file_cache)
        
        # 计算内存缓存大小
        memory_size = sum(len(pickle.dumps(entry.value)) for entry in self.memory_cache.values())
        
        # 计算文件缓存大小
        file_size = sum(file_path.stat().st_size for file_path in self.file_cache.values())
        
        return {
            "memory_cache": {
                "entries": memory_count,
                "size_bytes": memory_size,
                "size_mb": memory_size / (1024 * 1024)
            },
            "file_cache": {
                "entries": file_count,
                "size_bytes": file_size,
                "size_mb": file_size / (1024 * 1024)
            },
            "total_size_mb": (memory_size + file_size) / (1024 * 1024)
        }
    
    async def close(self):
        """关闭缓存管理器"""
        if self.cleanup_task and not self.cleanup_task.done():
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
```

### 3. 内存管理规范

```python
# src/dwrg_manager/utils/memory_manager.py
import gc
import psutil
import tracemalloc
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
import weakref

@dataclass
class MemorySnapshot:
    """内存快照"""
    timestamp: datetime
    current_memory: float
    peak_memory: float
    objects_count: int
    garbage_collected: bool = False

class MemoryManager:
    """内存管理器"""
    
    def __init__(self, max_memory_mb: int = 500):
        self.max_memory_mb = max_memory_mb
        self.snapshots: List[MemorySnapshot] = []
        self.tracking_objects: Dict[str, weakref.ref] = {}
        self.tracking_enabled = False
        
        # 启动内存跟踪
        tracemalloc.start()
    
    def enable_tracking(self):
        """启用内存跟踪"""
        self.tracking_enabled = True
        tracemalloc.start()
    
    def disable_tracking(self):
        """禁用内存跟踪"""
        self.tracking_enabled = False
        tracemalloc.stop()
    
    def take_snapshot(self) -> MemorySnapshot:
        """获取内存快照"""
        if not self.tracking_enabled:
            return MemorySnapshot(
                timestamp=datetime.now(),
                current_memory=self._get_current_memory(),
                peak_memory=self._get_peak_memory(),
                objects_count=self._get_objects_count(),
                garbage_collected=False
            )
        
        # 获取内存跟踪信息
        current, peak = tracemalloc.get_traced_memory()
        snapshot = MemorySnapshot(
            timestamp=datetime.now(),
            current_memory=current / 1024 / 1024,  # MB
            peak_memory=peak / 1024 / 1024,  # MB
            objects_count=self._get_objects_count(),
            garbage_collected=False
        )
        
        self.snapshots.append(snapshot)
        
        # 限制快照数量
        if len(self.snapshots) > 100:
            self.snapshots = self.snapshots[-100:]
        
        return snapshot
    
    def _get_current_memory(self) -> float:
        """获取当前内存使用量（MB）"""
        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024
    
    def _get_peak_memory(self) -> float:
        """获取峰值内存使用量（MB）"""
        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024
    
    def _get_objects_count(self) -> int:
        """获取对象数量"""
        return len(gc.get_objects())
    
    def check_memory_usage(self) -> Dict[str, Any]:
        """检查内存使用情况"""
        current_memory = self._get_current_memory()
        peak_memory = self._get_peak_memory()
        
        # 检查是否超过内存限制
        memory_warning = current_memory > self.max_memory_mb * 0.8  # 80%警告
        memory_critical = current_memory > self.max_memory_mb * 0.95  # 95%严重
        
        return {
            "current_memory_mb": current_memory,
            "peak_memory_mb": peak_memory,
            "max_memory_mb": self.max_memory_mb,
            "memory_warning": memory_warning,
            "memory_critical": memory_critical,
            "memory_usage_percent": (current_memory / self.max_memory_mb) * 100,
            "objects_count": self._get_objects_count()
        }
    
    def force_garbage_collection(self) -> Dict[str, Any]:
        """强制垃圾回收"""
        # 回收前快照
        before_snapshot = self.take_snapshot()
        
        # 执行垃圾回收
        collected = gc.collect()
        
        # 回收后快照
        after_snapshot = self.take_snapshot()
        after_snapshot.garbage_collected = True
        
        return {
            "collected_objects": collected,
            "memory_before_mb": before_snapshot.current_memory,
            "memory_after_mb": after_snapshot.current_memory,
            "memory_freed_mb": before_snapshot.current_memory - after_snapshot.current_memory
        }
    
    def track_object(self, obj_id: str, obj: Any) -> None:
        """跟踪对象"""
        self.tracking_objects[obj_id] = weakref.ref(obj)
    
    def get_tracked_objects(self) -> Dict[str, Any]:
        """获取跟踪的对象"""
        alive_objects = {}
        for obj_id, obj_ref in self.tracking_objects.items():
            obj = obj_ref()
            if obj is not None:
                alive_objects[obj_id] = obj
        return alive_objects
    
    def get_memory_leak_candidates(self) -> List[str]:
        """获取潜在的内存泄漏候选对象"""
        candidates = []
        for obj_id, obj_ref in self.tracking_objects.items():
            obj = obj_ref()
            if obj is None:
                candidates.append(obj_id)
        
        return candidates
    
    def get_memory_report(self) -> Dict[str, Any]:
        """生成内存报告"""
        if not self.snapshots:
            return {"message": "No memory snapshots available"}
        
        # 计算统计信息
        current_memory = self._get_current_memory()
        peak_memory = max(snapshot.current_memory for snapshot in self.snapshots)
        avg_memory = sum(snapshot.current_memory for snapshot in self.snapshots) / len(self.snapshots)
        
        # 计算内存增长趋势
        if len(self.snapshots) >= 2:
            recent_growth = (self.snapshots[-1].current_memory - self.snapshots[-2].current_memory)
        else:
            recent_growth = 0
        
        return {
            "current_memory_mb": current_memory,
            "peak_memory_mb": peak_memory,
            "average_memory_mb": avg_memory,
            "recent_growth_mb": recent_growth,
            "snapshots_count": len(self.snapshots),
            "tracking_enabled": self.tracking_enabled,
            "tracked_objects_count": len(self.get_tracked_objects()),
            "memory_leak_candidates": len(self.get_memory_leak_candidates()),
            "snapshots": [
                {
                    "timestamp": snapshot.timestamp.isoformat(),
                    "memory_mb": snapshot.current_memory,
                    "peak_memory_mb": snapshot.peak_memory,
                    "objects_count": snapshot.objects_count,
                    "garbage_collected": snapshot.garbage_collected
                }
                for snapshot in self.snapshots[-10:]  # 最近10个快照
            ]
        }
```

## 性能测试规范

### 1. 性能测试框架

```python
# tests/performance/test_performance.py
import pytest
import asyncio
import time
import tempfile
from pathlib import Path
from dwrg_manager.utils.async_utils import AsyncPerformanceManager
from dwrg_manager.utils.cache_manager import CacheManager, CacheConfig
from dwrg_manager.utils.memory_manager import MemoryManager

class TestPerformanceManager:
    """性能管理器测试"""
    
    def setup_method(self):
        """测试前设置"""
        self.performance_manager = AsyncPerformanceManager(max_workers=2)
    
    def test_performance_measurement(self):
        """测试性能测量"""
        async def sample_operation():
            await asyncio.sleep(0.1)
            return "success"
        
        # 测量性能
        result, metrics = asyncio.run(
            self.performance_manager.measure_performance("test_operation", sample_operation())
        )
        
        assert result == "success"
        assert metrics.success is True
        assert metrics.duration > 0
        assert metrics.operation == "test_operation"
    
    def test_batch_operations(self):
        """测试批量操作"""
        async def operation1():
            await asyncio.sleep(0.1)
            return "result1"
        
        async def operation2():
            await asyncio.sleep(0.1)
            return "result2"
        
        operations = ["op1", "op2"]
        coroutines = [operation1, operation2]
        
        results = asyncio.run(self.performance_manager.batch_operations(operations, coroutines))
        
        assert len(results) == 2
        assert results[0][0] == "result1"  # 第一个操作的结果
        assert results[1][0] == "result2"  # 第二个操作的结果
    
    def test_performance_report(self):
        """测试性能报告"""
        async def test_operation():
            await asyncio.sleep(0.1)
            return "test"
        
        # 执行多个操作
        for i in range(3):
            asyncio.run(self.performance_manager.measure_performance(f"op_{i}", test_operation()))
        
        # 生成报告
        report = self.performance_manager.get_performance_report()
        
        assert "op_0" in report
        assert "op_1" in report
        assert "op_2" in report
        assert report["op_0"]["success_rate"] == 1.0
        assert report["op_0"]["avg_duration"] > 0

class TestCacheManager:
    """缓存管理器测试"""
    
    def setup_method(self):
        """测试前设置"""
        self.cache_dir = Path(tempfile.mkdtemp())
        self.cache_config = CacheConfig(
            cache_type=CacheType.MEMORY,
            max_memory_size=10 * 1024 * 1024,  # 10MB
            default_ttl=60  # 60秒
        )
        self.cache_manager = CacheManager(self.cache_config, self.cache_dir)
    
    def test_cache_operations(self):
        """测试缓存操作"""
        # 设置缓存
        result = asyncio.run(self.cache_manager.set("key1", "value1", 60))
        assert result is True
        
        # 获取缓存
        value = asyncio.run(self.cache_manager.get("key1"))
        assert value == "value1"
        
        # 删除缓存
        result = asyncio.run(self.cache_manager.delete("key1"))
        assert result is True
        
        # 验证缓存已删除
        value = asyncio.run(self.cache_manager.get("key1"))
        assert value is None
    
    def test_cache_ttl(self):
        """测试缓存TTL"""
        # 设置短TTL缓存
        asyncio.run(self.cache_manager.set("key_ttl", "value_ttl", 1))
        
        # 立即获取
        value = asyncio.run(self.cache_manager.get("key_ttl"))
        assert value == "value_ttl"
        
        # 等待过期
        time.sleep(1.1)
        
        # 再次获取
        value = asyncio.run(self.cache_manager.get("key_ttl"))
        assert value is None
    
    def test_cache_stats(self):
        """测试缓存统计"""
        # 设置一些缓存
        asyncio.run(self.cache_manager.set("key1", "value1"))
        asyncio.run(self.cache_manager.set("key2", "value2"))
        
        # 获取统计信息
        stats = asyncio.run(self.cache_manager.get_cache_stats())
        
        assert stats["memory_cache"]["entries"] == 2
        assert stats["total_size_mb"] > 0

class TestMemoryManager:
    """内存管理器测试"""
    
    def setup_method(self):
        """测试前设置"""
        self.memory_manager = MemoryManager(max_memory_mb=100)
    
    def test_memory_snapshot(self):
        """测试内存快照"""
        snapshot = self.memory_manager.take_snapshot()
        
        assert snapshot.current_memory > 0
        assert snapshot.peak_memory >= snapshot.current_memory
        assert snapshot.objects_count > 0
        assert snapshot.timestamp is not None
    
    def test_memory_usage_check(self):
        """测试内存使用检查"""
        usage = self.memory_manager.check_memory_usage()
        
        assert "current_memory_mb" in usage
        assert "peak_memory_mb" in usage
        assert "memory_usage_percent" in usage
        assert 0 <= usage["memory_usage_percent"] <= 100
    
    def test_garbage_collection(self):
        """测试垃圾回收"""
        # 创建一些对象
        objects = [object() for _ in range(100)]
        
        # 执行垃圾回收
        result = self.memory_manager.force_garbage_collection()
        
        assert "collected_objects" in result
        assert "memory_before_mb" in result
        assert "memory_after_mb" in result
        assert "memory_freed_mb" in result
    
    def test_memory_report(self):
        """测试内存报告"""
        # 获取内存报告
        report = self.memory_manager.get_memory_report()
        
        assert "current_memory_mb" in report
        assert "peak_memory_mb" in report
        assert "snapshots_count" in report
        assert "snapshots" in report
```

### 2. 基准测试规范

```python
# tests/performance/test_benchmarks.py
import pytest
import asyncio
import time
import statistics
from pathlib import Path
from dwrg_manager.utils.async_utils import AsyncFileHandler, AsyncDownloadManager
from dwrg_manager.utils.cache_manager import CacheManager, CacheConfig

class TestBenchmarks:
    """基准测试"""
    
    @pytest.mark.benchmark
    def test_file_read_performance(self, benchmark):
        """测试文件读取性能"""
        # 创建测试文件
        test_file = Path("test_read.txt")
        content = "Hello World\n" * 1000  # 1000行
        
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        try:
            # 测试同步读取
            def sync_read():
                with open(test_file, 'r', encoding='utf-8') as f:
                    return f.read()
            
            result = benchmark(sync_read)
            assert len(result) > 0
            
        finally:
            # 清理测试文件
            if test_file.exists():
                test_file.unlink()
    
    @pytest.mark.benchmark
    def test_file_write_performance(self, benchmark):
        """测试文件写入性能"""
        # 创建测试内容
        content = "Test data\n" * 1000  # 1000行
        
        def sync_write():
            test_file = Path("test_write.txt")
            with open(test_file, 'w', encoding='utf-8') as f:
                f.write(content)
            return test_file
        
        test_file = benchmark(sync_write)
        assert test_file.exists()
        
        # 清理测试文件
        if test_file.exists():
            test_file.unlink()
    
    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_async_file_read_performance(self, benchmark):
        """测试异步文件读取性能"""
        # 创建测试文件
        test_file = Path("test_async_read.txt")
        content = "Async Hello World\n" * 1000  # 1000行
        
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        try:
            # 测试异步读取
            file_handler = AsyncFileHandler()
            
            def async_read():
                return file_handler.async_read_file(str(test_file))
            
            result = benchmark(async_read)
            assert len(result) > 0
            
        finally:
            # 清理测试文件
            if test_file.exists():
                test_file.unlink()
    
    @pytest.mark.benchmark
    def test_cache_performance(self, benchmark):
        """测试缓存性能"""
        cache_config = CacheConfig(
            cache_type=CacheType.MEMORY,
            max_memory_size=100 * 1024 * 1024,  # 100MB
            default_ttl=3600
        )
        cache_manager = CacheManager(cache_config)
        
        # 测试缓存设置和获取
        def cache_operations():
            for i in range(1000):
                cache_manager.set(f"key_{i}", f"value_{i}")
                cache_manager.get(f"key_{i}")
            return True
        
        result = benchmark(cache_operations)
        assert result is True
    
    @pytest.mark.benchmark
    def test_list_operations_performance(self, benchmark):
        """测试列表操作性能"""
        # 创建测试数据
        test_data = list(range(10000))
        
        def list_operations():
            # 列表操作
            result = []
            for item in test_data:
                if item % 2 == 0:
                    result.append(item)
            return len(result)
        
        count = benchmark(list_operations)
        assert count > 0
    
    @pytest.mark.benchmark
    def test_dict_operations_performance(self, benchmark):
        """测试字典操作性能"""
        # 创建测试数据
        test_data = {i: f"value_{i}" for i in range(10000)}
        
        def dict_operations():
            # 字典操作
            result = {}
            for key, value in test_data.items():
                if key % 2 == 0:
                    result[key] = value
            return len(result)
        
        count = benchmark(dict_operations)
        assert count > 0
```

## 性能监控规范

### 1. 性能监控工具

```python
# src/dwrg_manager/monitoring/performance_monitor.py
import asyncio
import time
import psutil
import threading
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import defaultdict, deque

@dataclass
class PerformanceMetrics:
    """性能指标"""
    timestamp: datetime
    operation: str
    duration: float
    memory_usage: float
    cpu_usage: float
    success: bool
    error_message: Optional[str] = None

class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self, max_samples: int = 1000):
        self.max_samples = max_samples
        self.metrics: deque = deque(maxlen=max_samples)
        self.operation_stats: Dict[str, List[float]] = defaultdict(list)
        self.alerts: List[str] = []
        
        # 系统监控
        self.system_metrics: deque = deque(maxlen=100)
        
        # 监控控制
        self.monitoring_active = False
        self.monitoring_thread: Optional[threading.Thread] = None
    
    def start_monitoring(self, interval: float = 1.0):
        """启动性能监控"""
        self.monitoring_active = True
        self.monitoring_thread = threading.Thread(
            target=self._monitor_system,
            args=(interval,),
            daemon=True
        )
        self.monitoring_thread.start()
    
    def stop_monitoring(self):
        """停止性能监控"""
        self.monitoring_active = False
        if self.monitoring_thread:
            self.monitoring_thread.join()
    
    def _monitor_system(self, interval: float):
        """监控系统性能"""
        while self.monitoring_active:
            try:
                # 获取系统指标
                process = psutil.Process()
                memory_info = process.memory_info()
                cpu_percent = process.cpu_percent()
                
                system_metric = {
                    'timestamp': datetime.now(),
                    'memory_mb': memory_info.rss / 1024 / 1024,
                    'cpu_percent': cpu_percent,
                    'threads': process.num_threads(),
                    'open_files': len(process.open_files()),
                    'connections': len(process.connections())
                }
                
                self.system_metrics.append(system_metric)
                
                # 检查系统资源使用情况
                self._check_system_resources(system_metric)
                
                time.sleep(interval)
                
            except Exception as e:
                print(f"System monitoring error: {e}")
                time.sleep(interval)
    
    def _check_system_resources(self, metric: Dict[str, Any]):
        """检查系统资源使用情况"""
        # 内存使用超过80%警告
        if metric['memory_mb'] > psutil.virtual_memory().total * 0.8 / 1024 / 1024:
            self.alerts.append(f"High memory usage: {metric['memory_mb']:.2f}MB")
        
        # CPU使用超过90%警告
        if metric['cpu_percent'] > 90:
            self.alerts.append(f"High CPU usage: {metric['cpu_percent']:.2f}%")
        
        # 限制警报数量
        if len(self.alerts) > 100:
            self.alerts = self.alerts[-100:]
    
    def record_operation(self, operation: str, duration: float, 
                        memory_usage: float, cpu_usage: float, 
                        success: bool, error_message: Optional[str] = None):
        """记录操作性能"""
        metric = PerformanceMetrics(
            timestamp=datetime.now(),
            operation=operation,
            duration=duration,
            memory_usage=memory_usage,
            cpu_usage=cpu_usage,
            success=success,
            error_message=error_message
        )
        
        self.metrics.append(metric)
        self.operation_stats[operation].append(duration)
        
        # 检查操作性能
        self._check_operation_performance(metric)
    
    def _check_operation_performance(self, metric: PerformanceMetrics):
        """检查操作性能"""
        # 操作时间超过1秒警告
        if metric.duration > 1.0:
            self.alerts.append(f"Slow operation: {metric.operation} took {metric.duration:.2f}s")
        
        # 操作失败警告
        if not metric.success:
            self.alerts.append(f"Failed operation: {metric.operation} - {metric.error_message}")
        
        # 限制警报数量
        if len(self.alerts) > 100:
            self.alerts = self.alerts[-100:]
    
    def get_performance_report(self) -> Dict[str, Any]:
        """生成性能报告"""
        if not self.metrics:
            return {"message": "No performance data available"}
        
        # 按操作类型统计
        operation_stats = {}
        for operation, durations in self.operation_stats.items():
            operation_stats[operation] = {
                'count': len(durations),
                'avg_duration': statistics.mean(durations),
                'max_duration': max(durations),
                'min_duration': min(durations),
                'total_duration': sum(durations)
            }
        
        # 系统性能统计
        system_stats = {}
        if self.system_metrics:
            memory_values = [m['memory_mb'] for m in self.system_metrics]
            cpu_values = [m['cpu_percent'] for m in self.system_metrics]
            
            system_stats = {
                'avg_memory_mb': statistics.mean(memory_values),
                'max_memory_mb': max(memory_values),
                'avg_cpu_percent': statistics.mean(cpu_values),
                'max_cpu_percent': max(cpu_values),
                'total_threads': sum(m['threads'] for m in self.system_metrics),
                'total_open_files': sum(m['open_files'] for m in self.system_metrics)
            }
        
        return {
            'timestamp': datetime.now().isoformat(),
            'total_operations': len(self.metrics),
            'success_rate': sum(1 for m in self.metrics if m.success) / len(self.metrics),
            'operation_stats': operation_stats,
            'system_stats': system_stats,
            'recent_alerts': self.alerts[-10:],  # 最近10个警报
            'recent_metrics': [
                {
                    'timestamp': m.timestamp.isoformat(),
                    'operation': m.operation,
                    'duration': m.duration,
                    'memory_mb': m.memory_usage,
                    'cpu_percent': m.cpu_usage,
                    'success': m.success
                }
                for m in self.metrics[-20:]  # 最近20个操作
            ]
        }
    
    def get_performance_trends(self) -> Dict[str, Any]:
        """获取性能趋势"""
        if len(self.metrics) < 2:
            return {"message": "Not enough data for trends"}
        
        # 计算最近1小时的趋势
        cutoff_time = datetime.now() - timedelta(hours=1)
        recent_metrics = [m for m in self.metrics if m.timestamp >= cutoff_time]
        
        if not recent_metrics:
            return {"message": "No data for the last hour"}
        
        # 按小时分组
        hourly_stats = defaultdict(list)
        for metric in recent_metrics:
            hour_key = metric.timestamp.strftime("%Y-%m-%d %H:00")
            hourly_stats[hour_key].append(metric.duration)
        
        # 计算每小时统计
        trends = {}
        for hour, durations in hourly_stats.items():
            trends[hour] = {
                'count': len(durations),
                'avg_duration': statistics.mean(durations),
                'max_duration': max(durations),
                'min_duration': min(durations)
            }
        
        return {
            'period': 'last_hour',
            'hourly_trends': trends,
            'total_operations': len(recent_metrics),
            'avg_duration': statistics.mean([m.duration for m in recent_metrics])
        }
```

这个性能标准文档提供了完整的性能规范和优化指南，确保项目在各个层面都有优秀的性能表现。
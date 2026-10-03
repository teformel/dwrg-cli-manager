---
name: testing-standards-dwrg
description: 第五人格命令行管理器的测试标准和规范
metadata:
  node_type: memory
  type: project
  created_date: 2026-09-21
  status: active
  originSessionId: sess_30048853-8656-4451-96f5-dd221dfd42ae
---

# 测试标准和规范 - 第五人格命令行管理器

## 测试理念

基于Vibe Coding理念，我们采用测试驱动开发(TDD)的方式，确保代码质量和功能可靠性。测试覆盖率达到90%以上，包括单元测试、集成测试、性能测试和端到端测试。

## 测试架构

### 1. 测试目录结构

```
tests/
├── __init__.py
├── conftest.py              # 测试配置和fixtures
├── unit/                    # 单元测试
│   ├── __init__.py
│   ├── test_config.py
│   ├── test_accounts.py
│   ├── test_servers.py
│   ├── test_resources.py
│   ├── test_launcher.py
│   └── test_utils.py
├── integration/             # 集成测试
│   ├── __init__.py
│   ├── test_cli_commands.py
│   ├── test_account_workflow.py
│   ├── test_server_switching.py
│   └── test_resource_management.py
├── performance/             # 性能测试
│   ├── __init__.py
│   ├── test_download_speed.py
│   ├── test_concurrent_operations.py
│   └── test_memory_usage.py
└── fixtures/               # 测试数据
    ├── __init__.py
    ├── sample_accounts.json
    ├── sample_servers.json
    └── sample_configs.json
```

### 2. 测试配置

```python
# tests/conftest.py
import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path
from typing import Generator
from dwrg_manager.config import Settings
from dwrg_manager.accounts import AccountManager
from dwrg_manager.servers import ServerManager

@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """创建事件循环用于异步测试"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """创建临时目录用于测试"""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path)

@pytest.fixture
def test_settings() -> Settings:
    """测试配置"""
    return Settings(
        debug=True,
        config_dir=str(Path(temp_dir) / "config"),
        data_dir=str(Path(temp_dir) / "data"),
        cache_dir=str(Path(temp_dir) / "cache"),
        max_concurrent_downloads=2,
        request_timeout=10,
        retry_attempts=1
    )

@pytest.fixture
def account_manager(test_settings: Settings) -> AccountManager:
    """账号管理器测试实例"""
    return AccountManager(test_settings)

@pytest.fixture
def server_manager(test_settings: Settings) -> ServerManager:
    """渠道服管理器测试实例"""
    return ServerManager(test_settings)
```

## 单元测试规范

### 1. 测试函数命名规范

```python
# 正确的测试函数命名
def test_account_creation_with_valid_data():
    """测试有效数据的账号创建"""
    pass

def test_account_password_encryption_and_decryption():
    """测试账号密码的加密和解密"""
    pass

def test_server_detection_returns_correct_server_type():
    """测试渠道服检测返回正确的服务器类型"""
    pass

# 错误的测试函数命名
def test_account1():  # 不够描述性
    pass

def test_account_creation():  # 缺少测试场景
    pass
```

### 2. 测试用例结构

```python
import pytest
from dwrg_manager.accounts import Account, AccountError
from dwrg_manager.utils.crypto import encrypt_data, decrypt_data

class TestAccountManagement:
    """账号管理测试类"""
    
    def test_create_account_with_valid_data(self, account_manager):
        """测试使用有效数据创建账号"""
        # Arrange
        username = "test_user"
        server = "official"
        password = "test_password_123"
        
        # Act
        account = account_manager.create_account(username, server, password)
        
        # Assert
        assert account.username == username
        assert account.server == server
        assert account.encrypted_password is not None
        assert account.created_at is not None
    
    def test_create_account_with_invalid_data(self, account_manager):
        """测试使用无效数据创建账号"""
        # Arrange
        invalid_cases = [
            ("", "official", "password"),  # 空用户名
            ("user", "", "password"),      # 空服务器
            ("user", "server", ""),        # 空密码
            ("user" * 100, "server", "password")  # 过长用户名
        ]
        
        # Act & Assert
        for username, server, password in invalid_cases:
            with pytest.raises(AccountError):
                account_manager.create_account(username, server, password)
    
    def test_account_password_encryption(self):
        """测试账号密码加密"""
        # Arrange
        password = "test_password_123"
        key = b"test_encryption_key_32_bytes_long_123"
        
        # Act
        encrypted = encrypt_data(password, key)
        decrypted = decrypt_data(encrypted, key)
        
        # Assert
        assert encrypted != password
        assert decrypted == password
    
    @pytest.mark.asyncio
    async def test_account_login_simulation(self, account_manager):
        """测试账号登录模拟"""
        # Arrange
        account = account_manager.create_account("test_user", "official", "password")
        
        # Act
        login_result = await account_manager.simulate_login(account)
        
        # Assert
        assert login_result.success is True
        assert login_result.account_id == account.id
```

### 3. 异步测试规范

```python
import pytest
from asyncio import TimeoutError

@pytest.mark.asyncio
async def test_async_download_operation():
    """测试异步下载操作"""
    # Arrange
    download_manager = DownloadManager()
    urls = ["http://example.com/file1.zip", "http://example.com/file2.zip"]
    
    # Act
    results = await asyncio.gather(
        *[download_manager.download(url) for url in urls],
        return_exceptions=True
    )
    
    # Assert
    for result in results:
        assert not isinstance(result, Exception)
        assert result is not None

@pytest.mark.asyncio
async def test_async_timeout_handling():
    """测试异步超时处理"""
    # Arrange
    download_manager = DownloadManager()
    slow_url = "http://example.com/slow_file.zip"
    
    # Act & Assert
    with pytest.raises(TimeoutError):
        await download_manager.download(slow_url, timeout=1)
```

## 集成测试规范

### 1. CLI命令集成测试

```python
import pytest
from typer.testing import CliRunner
from dwrg_manager.main import app

class TestCLICommands:
    """CLI命令集成测试"""
    
    def setup_method(self):
        """测试前设置"""
        self.runner = CliRunner()
    
    def test_version_command(self):
        """测试版本命令"""
        # Act
        result = self.runner.invoke(app, ["--version"])
        
        # Assert
        assert result.exit_code == 0
        assert "1.0.0" in result.stdout
    
    def test_help_command(self):
        """测试帮助命令"""
        # Act
        result = self.runner.invoke(app, ["--help"])
        
        # Assert
        assert result.exit_code == 0
        assert "Usage: dwrg [OPTIONS] COMMAND [ARGS]..." in result.stdout
    
    def test_account_add_command(self):
        """测试添加账号命令"""
        # Act
        result = self.runner.invoke(app, [
            "account", "add",
            "--username", "test_user",
            "--server", "official",
            "--password", "test_password"
        ])
        
        # Assert
        assert result.exit_code == 0
        assert "账号添加成功" in result.stdout
    
    def test_account_list_command(self):
        """测试列出账号命令"""
        # 先添加一个账号
        self.runner.invoke(app, [
            "account", "add",
            "--username", "test_user",
            "--server", "official",
            "--password", "test_password"
        ])
        
        # Act
        result = self.runner.invoke(app, ["account", "list"])
        
        # Assert
        assert result.exit_code == 0
        assert "test_user" in result.stdout
```

### 2. 工作流集成测试

```python
import pytest
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_account_server_switching_workflow():
    """测试账号渠道服切换工作流"""
    # Arrange
    account_manager = AccountManager(test_settings)
    server_manager = ServerManager(test_settings)
    
    # 创建测试账号
    account = account_manager.create_account("test_user", "official", "password")
    
    # Act
    # 1. 切换到B服
    await server_manager.switch_server("bserver")
    # 2. 使用账号登录
    login_result = await account_manager.login(account, "bserver")
    # 3. 验证切换结果
    server_info = await server_manager.get_current_server()
    
    # Assert
    assert login_result.success is True
    assert server_info.name == "bserver"
    assert account.last_login is not None

@pytest.mark.asyncio
async def test_resource_update_workflow():
    """测试资源更新工作流"""
    # Arrange
    resource_manager = ResourceManager(test_settings)
    
    # Act
    # 1. 检查资源状态
    status = await resource_manager.check_resource_status()
    # 2. 执行更新
    update_result = await resource_manager.update_resources()
    # 3. 验证更新结果
    final_status = await resource_manager.check_resource_status()
    
    # Assert
    assert status.needs_update is True
    assert update_result.success is True
    assert final_status.needs_update is False
```

## 性能测试规范

### 1. 下载性能测试

```python
import pytest
import asyncio
import time
from dwrg_manager.resources import DownloadManager

class TestPerformance:
    """性能测试类"""
    
    @pytest.mark.asyncio
    async def test_concurrent_download_performance(self):
        """测试并发下载性能"""
        # Arrange
        download_manager = DownloadManager()
        urls = [f"http://example.com/file{i}.zip" for i in range(10)]
        
        # Act
        start_time = time.time()
        await download_manager.download_batch(urls, max_workers=4)
        end_time = time.time()
        
        # Assert
        duration = end_time - start_time
        assert duration < 60  # 60秒内完成
        assert download_manager.success_count == len(urls)
    
    @pytest.mark.asyncio
    async def test_memory_usage_during_operations(self):
        """测试操作期间的内存使用"""
        # Arrange
        import psutil
        process = psutil.Process()
        
        # Act
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        await self._perform_memory_intensive_operations()
        peak_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Assert
        memory_increase = peak_memory - initial_memory
        assert memory_increase < 100  # 内存增长不超过100MB
    
    async def _perform_memory_intensive_operations(self):
        """执行内存密集型操作"""
        # 模拟大量数据处理
        data = [f"test_data_{i}" * 1000 for i in range(1000)]
        # 模拟处理延迟
        await asyncio.sleep(0.1)
```

## 测试数据管理

### 1. 测试数据规范

```python
# tests/fixtures/sample_accounts.json
[
    {
        "id": "acc_001",
        "username": "test_user_1",
        "server": "official",
        "encrypted_password": "encrypted_data_here",
        "created_at": "2026-09-21T10:00:00Z",
        "last_login": "2026-09-21T10:30:00Z"
    },
    {
        "id": "acc_002", 
        "username": "test_user_2",
        "server": "bserver",
        "encrypted_password": "encrypted_data_here",
        "created_at": "2026-09-21T11:00:00Z",
        "last_login": null
    }
]

# tests/fixtures/sample_servers.json
[
    {
        "name": "official",
        "display_name": "官方服",
        "endpoint": "https://game.official.com",
        "version": "1.0.0",
        "is_active": true
    },
    {
        "name": "bserver",
        "display_name": "B服",
        "endpoint": "https://game.bserver.com", 
        "version": "1.0.0",
        "is_active": true
    }
]
```

### 2. 测试数据工厂

```python
# tests/factories.py
import factory
from datetime import datetime
from dwrg_manager.accounts import Account
from dwrg_manager.servers import Server

class ServerFactory(factory.Factory):
    """渠道服数据工厂"""
    class Meta:
        model = Server
    
    name = "official"
    display_name = "官方服"
    endpoint = "https://game.official.com"
    version = "1.0.0"
    is_active = True

class AccountFactory(factory.Factory):
    """账号数据工厂"""
    class Meta:
        model = Account
    
    username = factory.Sequence(lambda n: f"test_user_{n}")
    server = "official"
    created_at = datetime.now()
    last_login = None
```

## 测试覆盖率要求

### 1. 覆盖率目标

```python
# pytest配置
[tool.pytest.ini_options]
# 测试覆盖率要求
addopts = [
    "--cov=dwrg_manager",
    "--cov-report=html:htmlcov",
    "--cov-report=term-missing",
    "--cov-report=xml",
    "--cov-fail-under=90",  # 最低覆盖率90%
    "--cov-branch",         # 分支覆盖率
    "--cov-context"        # 上下文信息
]

# 指定要测试的模块
python_files = ["test_*.py", "*_test.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
```

### 2. 覆盖率分析

```python
# tests/coverage_analysis.py
import coverage
import subprocess

def analyze_test_coverage():
    """分析测试覆盖率"""
    # 生成覆盖率报告
    cov = coverage.Coverage()
    cov.start()
    
    # 运行测试
    subprocess.run(["pytest", "--cov=dwrg_manager"], check=True)
    
    cov.stop()
    cov.save()
    
    # 生成HTML报告
    cov.html_report()
    
    # 打印覆盖率摘要
    report = cov.report()
    print(f"覆盖率报告: {report}")
    
    return report
```

## 测试最佳实践

### 1. 测试隔离原则

```python
# 每个测试应该是独立的
def test_account_creation_isolated():
    """测试账号创建应该是独立的"""
    # Arrange - 每个测试应该有自己的数据
    test_data = get_fresh_test_data()
    
    # Act
    result = create_account(test_data)
    
    # Assert
    assert result.success
    
    # 清理 - 确保不影响其他测试
    cleanup_test_data(test_data)

# 避免测试间的相互影响
def test_account_1():
    # 不要修改全局状态
    pass

def test_account_2():
    # 不要依赖test_account_1的执行结果
    pass
```

### 2. 测试可读性

```python
# 好的测试示例
def test_account_login_with_valid_credentials():
    """测试使用有效凭据登录账号"""
    # Given: 准备测试数据
    account = create_test_account("user1", "password123")
    
    # When: 执行登录操作
    login_result = account.login("password123")
    
    # Then: 验证结果
    assert login_result.success
    assert login_result.account_id == account.id
    assert login_result.timestamp is not None

# 避免复杂的测试逻辑
def test_complex_scenario():
    """避免复杂的测试场景"""
    # 不要在一个测试中测试太多功能
    pass
```

### 3. 测试性能考虑

```python
# 使用pytest.mark.slow标记耗时测试
@pytest.mark.slow
def test_large_file_download():
    """测试大文件下载（慢速测试）"""
    # Arrange
    large_file_url = "http://example.com/large_file.zip"
    
    # Act
    result = download_file(large_file_url)
    
    # Assert
    assert result.success
    assert result.file_size > 100 * 1024 * 1024  # > 100MB

# 使用pytest.mark.parametrize参数化测试
@pytest.mark.parametrize("server_name,expected_status", [
    ("official", "active"),
    ("bserver", "active"),
    ("unofficial", "inactive")
])
def test_server_status_check(server_name, expected_status):
    """测试不同服务器状态检查"""
    # Arrange
    server = get_server(server_name)
    
    # Act
    status = check_server_status(server)
    
    # Assert
    assert status == expected_status
```

这个测试标准文档提供了完整的测试框架和规范，确保项目的代码质量和功能可靠性。
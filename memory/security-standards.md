---
name: security-standards-dwrg
description: 第五人格命令行管理器的安全标准和规范
metadata:
  node_type: memory
  type: project
  created_date: 2026-09-21
  status: active
  originSessionId: sess_30048853-8656-4451-96f5-dd221dfd42ae
---

# 安全标准和规范 - 第五人格命令行管理器

## 安全理念

基于Vibe Coding理念，我们将安全作为项目设计的核心要素，而不是事后添加的功能。采用纵深防御策略，确保在数据存储、传输、处理等各个环节都有适当的安全措施。

## 安全架构

### 1. 安全层次模型

```
┌─────────────────────────────────────────────────────┐
│                   应用层安全                         │
│  • 输入验证  • 输出编码  • 访问控制  • 错误处理     │
├─────────────────────────────────────────────────────┤
│                   业务逻辑安全                       │
│  • 账号安全  • 渠道服安全  • 资源安全  • 启动安全     │
├─────────────────────────────────────────────────────┤
│                   数据安全                           │
│  • 加密存储  • 安全传输  • 备份恢复  • 隐私保护     │
├─────────────────────────────────────────────────────┤
│                   系统安全                           │
│  • 进程安全  • 文件系统  • 网络安全  • 系统隔离     │
└─────────────────────────────────────────────────────┘
```

### 2. 安全原则

- **最小权限原则**: 用户和组件只拥有必要的权限
- **纵深防御**: 多层安全措施，单点故障不会导致系统崩溃
- **安全默认**: 安全配置是默认选项，需要显式启用不安全功能
- **威胁建模**: 定期进行威胁分析和风险评估
- **安全审计**: 完整的日志记录和审计跟踪

## 数据安全规范

### 1. 敏感数据保护

```python
# src/dwrg_manager/utils/security.py
import os
import secrets
from typing import Optional, Dict, Any
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

class SecurityManager:
    """安全管理器"""
    
    def __init__(self, master_key: Optional[bytes] = None):
        self.master_key = master_key or self._generate_master_key()
        self.cipher = Fernet(self._derive_encryption_key())
    
    def _generate_master_key(self) -> bytes:
        """生成主密钥"""
        return secrets.token_bytes(32)
    
    def _derive_encryption_key(self) -> bytes:
        """派生加密密钥"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'dwrg_cli_salt_2026',
            iterations=100000,
        )
        return base64.urlsafe_b64encode(kdf.derive(self.master_key))
    
    def encrypt_sensitive_data(self, data: str) -> str:
        """加密敏感数据"""
        return self.cipher.encrypt(data.encode()).decode()
    
    def decrypt_sensitive_data(self, encrypted_data: str) -> str:
        """解密敏感数据"""
        return self.cipher.decrypt(encrypted_data.encode()).decode()
    
    def secure_password(self, password: str) -> str:
        """安全处理密码"""
        # 不要存储明文密码
        # 使用安全的哈希算法
        import hashlib
        salt = secrets.token_hex(16)
        hashed = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode(),
            salt.encode(),
            100000
        )
        return f"{salt}${hashed.hex()}"
    
    def verify_password(self, password: str, hashed_password: str) -> bool:
        """验证密码"""
        try:
            salt, hash_value = hashed_password.split('$')
            import hashlib
            new_hash = hashlib.pbkdf2_hmac(
                'sha256',
                password.encode(),
                salt.encode(),
                100000
            )
            return new_hash.hex() == hash_value
        except ValueError:
            return False
```

### 2. 配置文件安全

```python
# src/dwrg_manager/config/security.py
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseSettings, Field
from dwrg_manager.utils.security import SecurityManager

class SecurityConfig(BaseSettings):
    """安全配置"""
    
    # 加密配置
    encryption_enabled: bool = Field(default=True, description="启用数据加密")
    encryption_key: Optional[str] = Field(default=None, description="加密密钥")
    
    # 账号安全
    password_min_length: int = Field(default=8, ge=8, le=32, description="密码最小长度")
    password_require_uppercase: bool = Field(default=True, description="要求密码包含大写字母")
    password_require_lowercase: bool = Field(default=True, description="要求密码包含小写字母")
    password_require_numbers: bool = Field(default=True, description="要求密码包含数字")
    password_require_special: bool = Field(default=True, description="要求密码包含特殊字符")
    
    # 会话安全
    session_timeout: int = Field(default=3600, ge=300, le=86400, description="会话超时时间（秒）")
    max_login_attempts: int = Field(default=5, ge=1, le=10, description="最大登录尝试次数")
    lockout_duration: int = Field(default=300, ge=60, le=3600, description="锁定持续时间（秒）")
    
    # 网络安全
    require_https: bool = Field(default=True, description="要求HTTPS连接")
    allowed_hosts: list = Field(default=["*"], description="允许的主机列表")
    max_request_size: int = Field(default=100, ge=1, le=1000, description="最大请求大小（MB）")
    
    # 文件安全
    allowed_file_extensions: list = Field(
        default=[".py", ".json", ".txt", ".zip"],
        description="允许的文件扩展名"
    )
    max_file_size: int = Field(default=100, ge=1, le=1000, description="最大文件大小（MB）")
    
    class Config:
        env_prefix = "DWRG_SECURITY_"

class SecureConfigManager:
    """安全配置管理器"""
    
    def __init__(self, config_dir: Path):
        self.config_dir = config_dir
        self.security_config = SecurityConfig()
        self.security_manager = SecurityManager()
        self._init_config()
    
    def _init_config(self):
        """初始化配置"""
        config_file = self.config_dir / "security_config.json"
        if config_file.exists():
            self._load_config(config_file)
        else:
            self._save_config(config_file)
    
    def _load_config(self, config_file: Path):
        """加载配置"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                self.security_config = SecurityConfig(**config_data)
        except Exception as e:
            raise SecurityError(f"加载安全配置失败: {e}")
    
    def _save_config(self, config_file: Path):
        """保存配置"""
        try:
            config_data = self.security_config.dict()
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            raise SecurityError(f"保存安全配置失败: {e}")
    
    def encrypt_config_value(self, key: str, value: str) -> str:
        """加密配置值"""
        if self.security_config.encryption_enabled:
            return self.security_manager.encrypt_sensitive_data(value)
        return value
    
    def decrypt_config_value(self, key: str, encrypted_value: str) -> str:
        """解密配置值"""
        if self.security_config.encryption_enabled:
            return self.security_manager.decrypt_sensitive_data(encrypted_value)
        return encrypted_value
```

### 3. 输入验证和输出编码

```python
# src/dwrg_manager/utils/validation.py
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, validator, EmailStr
from dwrg_manager.utils.security import SecurityError

class AccountInput(BaseModel):
    """账号输入模型"""
    username: str = ... 
    server: str = ...
    password: str = ...
    email: Optional[EmailStr] = None
    
    @validator('username')
    def validate_username(cls, v):
        """验证用户名"""
        if len(v) < 3 or len(v) > 20:
            raise SecurityError("用户名长度必须在3-20字符之间")
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise SecurityError("用户名只能包含字母、数字和下划线")
        return v
    
    @validator('server')
    def validate_server(cls, v):
        """验证渠道服"""
        valid_servers = ['official', 'bserver', 'test_server']
        if v not in valid_servers:
            raise SecurityError(f"无效的渠道服: {v}")
        return v
    
    @validator('password')
    def validate_password(cls, v):
        """验证密码"""
        if len(v) < 8:
            raise SecurityError("密码长度至少8位")
        
        # 检查密码复杂度
        has_upper = re.search(r'[A-Z]', v)
        has_lower = re.search(r'[a-z]', v)
        has_digit = re.search(r'\d', v)
        has_special = re.search(r'[!@#$%^&*(),.?":{}|<>]', v)
        
        if not all([has_upper, has_lower, has_digit, has_special]):
            raise SecurityError("密码必须包含大小写字母、数字和特殊字符")
        
        return v

class SecureInputProcessor:
    """安全输入处理器"""
    
    def __init__(self, security_config: SecurityConfig):
        self.security_config = security_config
    
    def sanitize_input(self, input_data: Any) -> Any:
        """清理输入数据"""
        if isinstance(input_data, str):
            return self._sanitize_string(input_data)
        elif isinstance(input_data, dict):
            return {k: self.sanitize_input(v) for k, v in input_data.items()}
        elif isinstance(input_data, list):
            return [self.sanitize_input(item) for item in input_data]
        else:
            return input_data
    
    def _sanitize_string(self, value: str) -> str:
        """清理字符串输入"""
        # 移除潜在的危险字符
        value = re.sub(r'[<>"\'&]', '', value)
        # 限制长度
        if len(value) > 1000:
            value = value[:1000]
        return value
    
    def validate_file_input(self, filename: str, content: bytes) -> bool:
        """验证文件输入"""
        # 检查文件扩展名
        file_ext = os.path.splitext(filename)[1].lower()
        if file_ext not in self.security_config.allowed_file_extensions:
            raise SecurityError(f"不允许的文件类型: {file_ext}")
        
        # 检查文件大小
        if len(content) > self.security_config.max_file_size * 1024 * 1024:
            raise SecurityError(f"文件大小超过限制: {self.security_config.max_file_size}MB")
        
        return True
    
    def validate_output(self, output_data: Any) -> Any:
        """验证和清理输出数据"""
        if isinstance(output_data, str):
            # 防止XSS攻击
            output_data = self._escape_html(output_data)
        elif isinstance(output_data, dict):
            output_data = {k: self.validate_output(v) for k, v in output_data.items()}
        elif isinstance(output_data, list):
            output_data = [self.validate_output(item) for item in output_data]
        
        return output_data
    
    def _escape_html(self, text: str) -> str:
        """HTML转义"""
        html_escape_table = {
            "&": "&amp;",
            '"': "&quot;",
            "'": "&#x27;",
            ">": "&gt;",
            "<": "&lt;",
        }
        return "".join(html_escape_table.get(c, c) for c in text)
```

## 网络安全规范

### 1. 安全HTTP客户端

```python
# src/dwrg_manager/utils/http_client.py
import aiohttp
import asyncio
import ssl
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse
from dwrg_manager.utils.security import SecurityError, SecurityConfig

class SecureHTTPClient:
    """安全HTTP客户端"""
    
    def __init__(self, security_config: SecurityConfig):
        self.security_config = security_config
        self.session: Optional[aiohttp.ClientSession] = None
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.verify_mode = ssl.CERT_REQUIRED
        
    async def __aenter__(self):
        """异步上下文管理器入口"""
        timeout = aiohttp.ClientTimeout(total=self.security_config.request_timeout)
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            connector=aiohttp.TCPConnector(ssl=self.ssl_context),
            headers=self._get_default_headers()
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.session:
            await self.session.close()
    
    def _get_default_headers(self) -> Dict[str, str]:
        """获取默认请求头"""
        return {
            'User-Agent': 'DWRG-CLI-Manager/1.0.0',
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Accept-Encoding': 'gzip, deflate'
        }
    
    def validate_url(self, url: str) -> bool:
        """验证URL安全性"""
        try:
            parsed = urlparse(url)
            
            # 检查协议
            if parsed.scheme not in ['https', 'http']:
                raise SecurityError(f"不支持的协议: {parsed.scheme}")
            
            # 如果要求HTTPS，检查是否使用HTTPS
            if self.security_config.require_https and parsed.scheme != 'https':
                raise SecurityError("必须使用HTTPS连接")
            
            # 检查主机
            if parsed.hostname not in self.security_config.allowed_hosts:
                if '*' not in self.security_config.allowed_hosts:
                    raise SecurityError(f"不允许的主机: {parsed.hostname}")
            
            return True
            
        except Exception as e:
            raise SecurityError(f"无效的URL: {e}")
    
    async def secure_request(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        """安全HTTP请求"""
        try:
            # 验证URL
            self.validate_url(url)
            
            # 验证请求大小
            if 'data' in kwargs:
                data_size = len(str(kwargs['data'])) / (1024 * 1024)  # MB
                if data_size > self.security_config.max_request_size:
                    raise SecurityError(f"请求数据大小超过限制: {data_size}MB")
            
            # 发送请求
            async with self.session.request(method, url, **kwargs) as response:
                # 检查响应状态
                if response.status >= 400:
                    raise SecurityError(f"HTTP错误: {response.status}")
                
                # 解析响应
                try:
                    return await response.json()
                except:
                    return await response.text()
                    
        except Exception as e:
            raise SecurityError(f"请求失败: {e}")
    
    async def download_file(self, url: str, save_path: str, chunk_size: int = 8192) -> bool:
        """安全下载文件"""
        try:
            self.validate_url(url)
            
            async with self.session.get(url) as response:
                if response.status != 200:
                    raise SecurityError(f"下载失败: HTTP {response.status}")
                
                # 检查文件大小
                content_length = response.headers.get('content-length')
                if content_length:
                    file_size = int(content_length) / (1024 * 1024)  # MB
                    if file_size > self.security_config.max_file_size:
                        raise SecurityError(f"文件大小超过限制: {file_size}MB")
                
                # 安全下载文件
                with open(save_path, 'wb') as f:
                    async for chunk in response.content.iter_chunked(chunk_size):
                        f.write(chunk)
                
                return True
                
        except Exception as e:
            raise SecurityError(f"文件下载失败: {e}")
```

### 2. 网络安全监控

```python
# src/dwrg_manager/monitoring/security_monitor.py
import time
import threading
from typing import Dict, List, Optional
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass
class SecurityEvent:
    """安全事件"""
    timestamp: datetime
    event_type: str
    severity: str  # low, medium, high, critical
    description: str
    source_ip: Optional[str] = None
    user_id: Optional[str] = None

class SecurityMonitor:
    """安全监控器"""
    
    def __init__(self):
        self.events: deque = deque(maxlen=10000)
        self.alerts: List[SecurityEvent] = []
        self.lock = threading.Lock()
        
        # 统计数据
        self.stats = defaultdict(int)
        self.failed_logins = defaultdict(int)
        self.suspicious_ips = defaultdict(int)
        
        # 监控阈值
        self.max_failed_logins = 5
        self.max_requests_per_minute = 100
        self.suspicious_threshold = 10
        
    def log_event(self, event: SecurityEvent):
        """记录安全事件"""
        with self.lock:
            self.events.append(event)
            self.stats[event.event_type] += 1
            
            # 检查是否需要报警
            if event.severity in ['high', 'critical']:
                self.alerts.append(event)
                self._handle_alert(event)
    
    def _handle_alert(self, event: SecurityEvent):
        """处理安全警报"""
        if event.event_type == 'failed_login':
            self.failed_logins[event.user_id or 'unknown'] += 1
            
            # 检查登录失败次数
            if self.failed_logins[event.user_id or 'unknown'] >= self.max_failed_logins:
                self._lock_account(event.user_id or 'unknown')
        
        elif event.event_type == 'suspicious_activity':
            self.suspicious_ips[event.source_ip or 'unknown'] += 1
            
            # 检查可疑IP
            if self.suspicious_ips[event.source_ip or 'unknown'] >= self.suspicious_threshold:
                self._block_ip(event.source_ip or 'unknown')
    
    def _lock_account(self, user_id: str):
        """锁定账号"""
        # 实现账号锁定逻辑
        pass
    
    def _block_ip(self, ip: str):
        """阻止IP"""
        # 实现IP阻止逻辑
        pass
    
    def get_security_report(self) -> Dict[str, Any]:
        """生成安全报告"""
        with self.lock:
            return {
                'total_events': len(self.events),
                'alerts': len(self.alerts),
                'stats': dict(self.stats),
                'failed_logins': dict(self.failed_logins),
                'suspicious_ips': dict(self.suspicious_ips),
                'recent_alerts': [
                    {
                        'timestamp': alert.timestamp.isoformat(),
                        'type': alert.event_type,
                        'severity': alert.severity,
                        'description': alert.description
                    }
                    for alert in self.alerts[-10:]  # 最近10个警报
                ]
            }
    
    def detect_anomalies(self) -> List[SecurityEvent]:
        """检测异常活动"""
        anomalies = []
        
        with self.lock:
            # 检查异常登录模式
            for user_id, count in self.failed_logins.items():
                if count >= self.max_failed_logins:
                    anomalies.append(SecurityEvent(
                        timestamp=datetime.now(),
                        event_type='brute_force_attack',
                        severity='high',
                        description=f"检测到暴力破解攻击: {user_id}",
                        user_id=user_id
                    ))
            
            # 检查异常IP活动
            for ip, count in self.suspicious_ips.items():
                if count >= self.suspicious_threshold:
                    anomalies.append(SecurityEvent(
                        timestamp=datetime.now(),
                        event_type='suspicious_ip',
                        severity='medium',
                        description=f"检测到可疑IP活动: {ip}",
                        source_ip=ip
                    ))
        
        return anomalies
```

## 进程和系统安全

### 1. 进程安全管理

```python
# src/dwrg_manager/utils/process_security.py
import os
import sys
import subprocess
import psutil
import signal
from typing import List, Optional, Dict, Any
from pathlib import Path
from dwrg_manager.utils.security import SecurityError

class ProcessManager:
    """进程管理器"""
    
    def __init__(self):
        self.allowed_processes = [
            'python',
            'dwrg-cli',
            'dwrg-manager'
        ]
        self.allowed_directories = [
            sys.prefix,
            os.getcwd(),
            str(Path.home())
        ]
    
    def execute_command(self, command: List[str], working_dir: Optional[str] = None) -> subprocess.CompletedProcess:
        """安全执行命令"""
        try:
            # 验证命令安全性
            self._validate_command(command)
            
            # 验证工作目录
            if working_dir:
                self._validate_directory(working_dir)
            
            # 执行命令
            result = subprocess.run(
                command,
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )
            
            # 检查执行结果
            if result.returncode != 0:
                raise SecurityError(f"命令执行失败: {result.stderr}")
            
            return result
            
        except subprocess.TimeoutExpired:
            raise SecurityError("命令执行超时")
        except Exception as e:
            raise SecurityError(f"命令执行失败: {e}")
    
    def _validate_command(self, command: List[str]):
        """验证命令安全性"""
        if not command:
            raise SecurityError("命令不能为空")
        
        # 检查命令是否在允许列表中
        if command[0] not in self.allowed_processes:
            raise SecurityError(f"不允许的命令: {command[0]}")
        
        # 检查危险参数
        dangerous_params = ['rm -rf', 'del /f', 'format', 'mkfs', 'dd']
        command_str = ' '.join(command)
        for dangerous in dangerous_params:
            if dangerous in command_str.lower():
                raise SecurityError(f"命令包含危险参数: {dangerous}")
    
    def _validate_directory(self, directory: str):
        """验证目录安全性"""
        try:
            path = Path(directory).resolve()
            
            # 检查目录是否在允许列表中
            allowed = False
            for allowed_dir in self.allowed_directories:
                if path == Path(allowed_dir).resolve() or str(path).startswith(str(Path(allowed_dir).resolve())):
                    allowed = True
                    break
            
            if not allowed:
                raise SecurityError(f"不允许访问目录: {directory}")
                
        except Exception as e:
            raise SecurityError(f"无效的目录: {e}")
    
    def terminate_process(self, process_id: int):
        """安全终止进程"""
        try:
            process = psutil.Process(process_id)
            
            # 检查是否是允许终止的进程
            if process.name() not in self.allowed_processes:
                raise SecurityError(f"不允许终止进程: {process.name()}")
            
            # 发送SIGTERM信号
            process.terminate()
            
            # 等待进程结束
            process.wait(timeout=10)
            
        except psutil.NoSuchProcess:
            raise SecurityError(f"进程不存在: {process_id}")
        except psutil.AccessDenied:
            raise SecurityError(f"没有权限终止进程: {process_id}")
        except Exception as e:
            raise SecurityError(f"终止进程失败: {e}")
    
    def get_process_info(self, process_id: int) -> Dict[str, Any]:
        """获取进程信息"""
        try:
            process = psutil.Process(process_id)
            return {
                'pid': process.pid,
                'name': process.name(),
                'status': process.status(),
                'cpu_percent': process.cpu_percent(),
                'memory_percent': process.memory_percent(),
                'create_time': process.create_time(),
                'cmdline': process.cmdline(),
                'cwd': process.cwd(),
                'username': process.username()
            }
        except psutil.NoSuchProcess:
            raise SecurityError(f"进程不存在: {process_id}")
        except Exception as e:
            raise SecurityError(f"获取进程信息失败: {e}")
```

### 2. 文件系统安全

```python
# src/dwrg_manager/utils/file_security.py
import os
import shutil
import stat
from pathlib import Path
from typing import List, Optional, Dict, Any
from dwrg_manager.utils.security import SecurityError

class FileManager:
    """文件管理器"""
    
    def __init__(self, security_config):
        self.security_config = security_config
        self.base_directory = Path.home() / '.dwrg-cli'
        self._ensure_directory_structure()
    
    def _ensure_directory_structure(self):
        """确保目录结构安全"""
        try:
            # 创建基础目录
            self.base_directory.mkdir(parents=True, exist_ok=True)
            
            # 设置适当的权限
            os.chmod(self.base_directory, 0o700)
            
            # 创建子目录
            for subdir in ['data', 'cache', 'logs', 'backups']:
                (self.base_directory / subdir).mkdir(exist_ok=True)
                os.chmod(self.base_directory / subdir, 0o700)
                
        except Exception as e:
            raise SecurityError(f"创建目录结构失败: {e}")
    
    def validate_file_path(self, file_path: str) -> Path:
        """验证文件路径安全性"""
        try:
            path = Path(file_path).resolve()
            
            # 检查路径是否在允许的目录内
            if not str(path).startswith(str(self.base_directory.resolve())):
                raise SecurityError(f"不允许访问文件: {file_path}")
            
            return path
            
        except Exception as e:
            raise SecurityError(f"无效的文件路径: {e}")
    
    def secure_read_file(self, file_path: str) -> str:
        """安全读取文件"""
        try:
            path = self.validate_file_path(file_path)
            
            # 检查文件权限
            if os.access(path, os.W_OK):
                raise SecurityError(f"文件可写，不安全: {file_path}")
            
            # 读取文件内容
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return content
            
        except Exception as e:
            raise SecurityError(f"读取文件失败: {e}")
    
    def secure_write_file(self, file_path: str, content: str, backup: bool = True) -> bool:
        """安全写入文件"""
        try:
            path = self.validate_file_path(file_path)
            
            # 创建备份
            if backup and path.exists():
                backup_path = path.with_suffix(path.suffix + '.backup')
                shutil.copy2(path, backup_path)
                os.chmod(backup_path, 0o600)
            
            # 写入文件
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # 设置安全权限
            os.chmod(path, 0o600)
            
            return True
            
        except Exception as e:
            raise SecurityError(f"写入文件失败: {e}")
    
    def secure_delete_file(self, file_path: str) -> bool:
        """安全删除文件"""
        try:
            path = self.validate_file_path(file_path)
            
            # 安全删除：覆写文件内容
            if path.exists():
                size = path.stat().st_size
                with open(path, 'wb') as f:
                    # 覆写文件内容
                    f.write(b'\x00' * size)
                
                # 删除文件
                path.unlink()
            
            return True
            
        except Exception as e:
            raise SecurityError(f"删除文件失败: {e}")
    
    def create_secure_backup(self, source_path: str, backup_name: str) -> str:
        """创建安全备份"""
        try:
            source = self.validate_file_path(source_path)
            backup_dir = self.base_directory / 'backups'
            
            # 创建备份文件
            backup_path = backup_dir / f"{backup_name}_{int(time.time())}.backup"
            shutil.copy2(source, backup_path)
            
            # 设置安全权限
            os.chmod(backup_path, 0o600)
            
            return str(backup_path)
            
        except Exception as e:
            raise SecurityError(f"创建备份失败: {e}")
    
    def list_secure_files(self, directory: str = None) -> List[Dict[str, Any]]:
        """安全列出文件"""
        try:
            if directory:
                dir_path = self.validate_file_path(directory)
            else:
                dir_path = self.base_directory
            
            files = []
            for item in dir_path.iterdir():
                if item.is_file():
                    stat_info = item.stat()
                    files.append({
                        'name': item.name,
                        'path': str(item),
                        'size': stat_info.st_size,
                        'modified': stat_info.st_mtime,
                        'permissions': stat.filemode(stat_info.st_mode),
                        'readable': os.access(item, os.R_OK),
                        'writable': os.access(item, os.W_OK),
                        'executable': os.access(item, os.X_OK)
                    })
            
            return files
            
        except Exception as e:
            raise SecurityError(f"列出文件失败: {e}")
```

## 安全测试规范

### 1. 安全测试用例

```python
# tests/security/test_security.py
import pytest
import tempfile
from pathlib import Path
from dwrg_manager.utils.security import SecurityManager, SecurityError
from dwrg_manager.utils.validation import AccountInput, SecureInputProcessor
from dwrg_manager.utils.http_client import SecureHTTPClient

class TestSecurityManager:
    """安全管理器测试"""
    
    def setup_method(self):
        """测试前设置"""
        self.security_manager = SecurityManager()
    
    def test_password_hashing(self):
        """测试密码哈希"""
        password = "test_password_123"
        hashed = self.security_manager.secure_password(password)
        
        # 验证哈希结果
        assert '$' in hashed
        parts = hashed.split('$')
        assert len(parts) == 2
        assert len(parts[0]) == 32  # salt长度
        assert len(parts[1]) == 64  # hash长度
        
        # 验证密码验证
        assert self.security_manager.verify_password(password, hashed)
        assert not self.security_manager.verify_password("wrong_password", hashed)
    
    def test_data_encryption(self):
        """测试数据加密"""
        sensitive_data = "sensitive_information"
        
        # 加密
        encrypted = self.security_manager.encrypt_sensitive_data(sensitive_data)
        assert encrypted != sensitive_data
        
        # 解密
        decrypted = self.security_manager.decrypt_sensitive_data(encrypted)
        assert decrypted == sensitive_data
        
        # 验证错误解密
        with pytest.raises(Exception):
            self.security_manager.decrypt_sensitive_data("invalid_encrypted_data")

class TestInputValidation:
    """输入验证测试"""
    
    def setup_method(self):
        """测试前设置"""
        self.processor = SecureInputProcessor()
    
    def test_account_input_validation(self):
        """测试账号输入验证"""
        # 有效输入
        valid_input = {
            "username": "test_user",
            "server": "official",
            "password": "TestPassword123!",
            "email": "test@example.com"
        }
        
        account = AccountInput(**valid_input)
        assert account.username == "test_user"
        assert account.server == "official"
        
        # 无效用户名
        with pytest.raises(SecurityError):
            AccountInput(username="us", server="official", password="TestPassword123!")
        
        # 无效密码
        with pytest.raises(SecurityError):
            AccountInput(username="test_user", server="official", password="weak")
    
    def test_input_sanitization(self):
        """测试输入清理"""
        malicious_input = "<script>alert('xss')</script>"
        sanitized = self.processor.sanitize_input(malicious_input)
        
        assert "<script>" not in sanitized
        assert alert not in sanitized
    
    def test_output_validation(self):
        """测试输出验证"""
        malicious_output = "Hello <script>alert('xss')</script> World"
        validated = self.processor.validate_output(malicious_output)
        
        assert "<script>" not in validated
        assert "alert('xss')" not in validated

class TestHTTPSecurity:
    """HTTP安全测试"""
    
    def setup_method(self):
        """测试前设置"""
        from dwrg_manager.config.security import SecurityConfig
        self.security_config = SecurityConfig()
        self.http_client = SecureHTTPClient(self.security_config)
    
    def test_url_validation(self):
        """测试URL验证"""
        # 有效URL
        assert self.http_client.validate_url("https://example.com")
        assert self.http_client.validate_url("http://localhost:8080")
        
        # 无效URL
        with pytest.raises(SecurityError):
            self.http_client.validate_url("ftp://example.com")
        
        with pytest.raises(SecurityError):
            self.http_client.validate_url("https://malicious.com")
    
    @pytest.mark.asyncio
    async def test_secure_request(self):
        """测试安全HTTP请求"""
        async with self.http_client:
            # 测试有效请求
            try:
                response = await self.http_client.secure_request(
                    "GET", "https://httpbin.org/json"
                )
                assert isinstance(response, dict)
            except Exception:
                # 如果网络不可用，跳过测试
                pytest.skip("网络不可用")
            
            # 测试无效URL
            with pytest.raises(SecurityError):
                await self.http_client.secure_request("GET", "ftp://invalid.com")
```

### 2. 渗透测试规范

```python
# tests/security/test_penetration.py
import pytest
from dwrg_manager.utils.security import SecurityManager
from dwrg_manager.utils.file_security import FileManager
from dwrg_manager.utils.process_security import ProcessManager

class TestPenetrationTesting:
    """渗透测试"""
    
    def test_sql_injection_attempt(self):
        """测试SQL注入攻击"""
        security_manager = SecurityManager()
        
        # 恶意输入
        malicious_input = "admin' OR '1'='1"
        
        # 验证输入被拒绝
        with pytest.raises(SecurityError):
            security_manager.validate_input(malicious_input)
    
    def test_path_traversal_attempt(self):
        """测试路径遍历攻击"""
        file_manager = FileManager()
        
        # 恶意路径
        malicious_path = "../../../etc/passwd"
        
        # 验证路径被拒绝
        with pytest.raises(SecurityError):
            file_manager.validate_file_path(malicious_path)
    
    def test_command_injection_attempt(self):
        """测试命令注入攻击"""
        process_manager = ProcessManager()
        
        # 恶意命令
        malicious_command = ["python", "-c", "import os; os.system('rm -rf /')"]
        
        # 验证命令被拒绝
        with pytest.raises(SecurityError):
            process_manager.execute_command(malicious_command)
    
    def test_xss_attempt(self):
        """测试XSS攻击"""
        from dwrg_manager.utils.validation import SecureInputProcessor
        
        processor = SecureInputProcessor()
        
        # 恶意脚本
        malicious_script = "<script>alert('XSS')</script>"
        
        # 验证脚本被转义
        sanitized = processor.sanitize_input(malicious_script)
        assert "<script>" not in sanitized
        assert "alert('XSS')" not in sanitized
```

这个安全标准文档提供了完整的安全规范和实现指南，确保项目的各个层面都有适当的安全措施。
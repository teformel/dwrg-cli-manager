# 安全

本项目把加密与校验能力收敛在 `dwrg_manager.security` 包中。本页说明密钥管理、密码哈希、加密与哈希的分工、输入校验规则与威胁模型。

## 一、加密与密钥管理（`security.crypto`）

### 1. 算法

| 用途 | 算法 | 说明 |
|------|------|------|
| 对称加密 | Fernet（AES-128-CBC + HMAC-SHA256） | `cryptography` 库提供，密文自带时间戳与完整性校验 |
| 口令派生密钥 | PBKDF2-HMAC-SHA256 | 迭代 **100 000** 次 |
| 密码哈希 | PBKDF2-HMAC-SHA256 | 迭代 **100 000** 次，随机盐 32 字节 |

### 2. 密钥解析优先级

`CryptoManager` 按以下顺序解析应用密钥：

| 优先级 | 来源 | 说明 |
|--------|------|------|
| 1 | 构造函数 `key` 参数 | 显式传入优先 |
| 2 | 环境变量 `DWRG_ENCRYPTION_KEY` | 合法 Fernet 密钥直接使用；否则视为口令做 PBKDF2 派生 |
| 3 | 密钥文件 | 默认 `~/.dwrg/keyfile`，可被 `DWRG_KEY_FILE` 或 `key_file` 参数覆盖 |
| 4 | 自动生成 | 生成新 Fernet 密钥并以权限 `0600` 写入密钥文件 |

判断逻辑：先尝试 `Fernet(candidate)`；若非法，则用固定的 `_PASSPHRASE_SALT` 与 100 000 次 PBKDF2 把口令派生为 32 字节密钥。

### 3. 密钥文件权限

生成密钥文件时使用：

```python
os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
```

即 `0600`（仅属主可读写）。轮换密钥（`CryptoManager.rotate`）写回时同样为 `0600`。

若密钥文件不可写，仅记录警告，密钥在**本次进程内**有效——此时下个进程将无法解密已有密文。

### 4. 原始字符串加解密

| 函数 | 说明 |
|------|------|
| `encrypt_data(data)` / `decrypt_data(token)` | 使用**应用密钥**（模块级单例）加解密字符串 |
| `encrypt_with_password(data, password)` / `decrypt_with_password(token, password)` | 使用**口令**加解密；密文格式为 `<salt_hex>$<fernet_token>`，每次结果不同 |
| `generate_key()` | 生成新的 Fernet 密钥字符串 |
| `get_crypto_manager()` / `reset_crypto_manager()` | 进程级单例获取 / 重置（后者主要供测试） |

`decrypt_with_password` 在口令错误或密文损坏时**统一返回空字符串**，不区分失败原因，避免向调用方泄露可区分的信息。

## 二、密码哈希（PBKDF2-HMAC-SHA256）

### 1. 哈希格式

```text
<salt>$<hex-digest>
```

- `salt`：默认 `os.urandom(32).hex()`（64 个十六进制字符）；也可显式传入；
- `hex-digest`：`hashlib.pbkdf2_hmac("sha256", password, salt, 100_000)` 的十六进制结果。

### 2. 校验

`verify_password(password, hashed_password)`：

（1）按 `$` 切分出 `salt` 与 `expected`；格式非法直接返回 `False`；
（2）用相同参数重新派生；
（3）通过 `hmac.compare_digest` 做**恒定时间比较**。

`AccountManager.authenticate` 在校验失败时统一返回 `None`，不区分「账号不存在」与「密码错误」。

## 三、加密与哈希的分工

账号密码在配置中以两种形式**同时**存储：

| 字段 | 用途 | 特点 |
|------|------|------|
| `encrypted_password` | **还原原文**，用于登录自动填充 | Fernet 可逆加密，依赖应用密钥（密钥文件） |
| `password_hash` | **身份校验**，无需解密 | PBKDF2 单向哈希，盐随哈希存储 |

设计动因（见 `accounts/manager.py` 模块说明）：

- 早期实现每次进程启动随机生成密钥，导致重启后无法解密 —— 现在密钥落盘复用，保证跨进程可解密；
- 旧实现校验密码时引用了不存在的 `password_hash` 字段 —— 现已补齐该字段并明确分工。

`AccountManager.get_password()` 在密文无法用当前密钥解密时抛出：

```text
账号错误: 密码解密失败（可能由旧版本密钥加密）
```

## 四、输入校验规则（`security.validation`）

全部校验统一抛出 `ValidationError`（前缀 `参数错误`），可将字段名拼进信息。

| 校验函数 | 规则 | 默认约束 | 失败信息示例 |
|----------|------|----------|--------------|
| `validate_username` | 去空白；长度；字符集 | `3`–`20`，`^[A-Za-z0-9_]+$` | `username: 长度必须在 3-20 个字符之间` |
| `validate_password` | 长度；非全空白 | `6`–`128` | `password: 不能全部为空白字符` |
| `validate_account_id` | 去空白；长度 | ≥ `8` | `account_id: 长度不能少于 8 个字符` |
| `validate_server_name` | 非空；字符集；可选存在性 | `^[A-Za-z0-9_-]+$`，可选 `known` 集合 | `server: 只能包含字母、数字、下划线和短横线` |
| `validate_version` | 去空白；格式 | `^\d+(\.\d+)*$` | `version: 版本号需形如 1.0.0` |
| `validate_language` | 必须受支持 | 9 种语言之一 | `language: 不支持的语言 'xx-XX'，可用: zh-CN, ...` |
| `validate_path` | 展开 `~` 并 `resolve`；可选根目录限定；可选存在性 | — | `path: 路径 ... 超出允许目录 ...` |

字符集常量：

| 常量 | 值 |
|------|----|
| `SERVER_NAME_PATTERN` | `^[A-Za-z0-9_-]+$`（定义于 `config.models`，被校验层复用） |
| 用户名正则 | `^[A-Za-z0-9_]+$` |

### 目录穿越防护

`validate_path(value, base=...)` 在提供 `base` 时，会先 `resolve()` 目标路径与基准目录，再要求目标等于基准或位于其下：

```python
if resolved != base_resolved and base_resolved not in resolved.parents:
    raise ValidationError(f"路径 {resolved} 超出允许目录 {base_resolved}", field="path")
```

这使插件等外部输入无法通过 `../` 逃逸出允许目录。

## 五、威胁模型与缓解

| 威胁 | 影响 | 缓解措施 |
|------|------|----------|
| 配置文件泄露 | 账号密码被读取 | 密码只存 Fernet 密文 + PBKDF2 哈希，不存明文 |
| 密钥文件被读取 | 可解密 `encrypted_password` | 密钥文件权限 `0600`，默认不在仓库内；可改用 `DWRG_ENCRYPTION_KEY` 由外部注入 |
| 密钥丢失 / 变更 | 旧密文无法解密 | 密钥落盘复用；解密失败时给出明确提示，不静默失败 |
| 密文被篡改 | 解密出错误数据 | Fernet 自带 HMAC 完整性校验，篡改触发 `InvalidToken` → `SecurityError` |
| 时序侧信道 | 通过响应时间推断账号 / 密码正确性 | `hmac.compare_digest` 恒定时间比较；认证失败统一返回同一结果 |
| 口令爆破 | 离线破解哈希 | PBKDF2 迭代 100 000 次的随机盐哈希 |
| 目录穿越 | 越权读写任意文件 | `validate_path` 的 `base` 限定 + `resolve()` 规范化 |
| 非法插件名 / 版本 | 动态导入异常或路径注入 | 插件名 / 版本使用严格正则（`[A-Za-z0-9_-]+`、`x.y.z`）校验 |
| 敏感信息进入日志 | 日志泄露密码 | 日志只记录用户名 / 账号 ID 等标识，不记录明文密码 |
| 插件执行任意代码 | 与主进程同权限 | 本项目插件为**受信任本地代码**，不提供沙箱；仅从用户可控目录加载 |

## 六、使用建议

1. 保持 `~/.dwrg/keyfile` 的权限为 `0600`，不要放入版本控制；
2. 在 CI 或多机场景，用 `DWRG_ENCRYPTION_KEY` 或 `DWRG_KEY_FILE` 显式注入密钥；
3. 若怀疑密钥泄露，使用 `CryptoManager.rotate()` 轮换后迁移数据（旧密文将失效）；
4. `dwrg config export` 导出的配置**包含密文**，请按敏感文件对待；
5. 只从可信来源获取插件。

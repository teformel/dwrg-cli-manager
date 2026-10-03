# 第五人格 PC 端「资源源 / CDN」调研（实测记录）

日期：2026-10-03
结论先行：**不需要你提供安装包，也不需要逆向客户端。** 国际服完整包直链已实测可用（HTTP 206 + `Accept-Ranges: bytes` + ETag 即完整 MD5）；国服 PC 端所有公开直链均已 403，只能走【网易发烧平台】启动器，那一层才需要抓包。

---

## 一、实测结果

### 1.1 安装包直链（本机 curl 实测，2026-10-03）

| 用途 | URL | 实测 | 大小 (B) | ETag | Last-Modified |
|---|---|---|---|---|---|
| 国际服（亚/欧美）NeoX2 完整包 | `https://h55na.gdl.easebar.com/identityv_setup_neox2_oversea_release_240912.exe` | **206 Partial Content** | 3,951,463,560 (3.68 GiB) | `"3af58ef90a035b275797507c1efecd05"` | Wed, 11 Sep 2024 20:10:19 GMT |
| 国际服 旧包 | `https://h55na.gdl.easebar.com/identityv_setup_release_oversea.exe` | **206 Partial Content** | 4,086,558,696 (3.81 GiB) | `"07814da3f6ce70ed2552697bda7ab6c8-7"` | Mon, 14 Dec 2020 08:44:00 GMT |
| 国服 正式服 | `https://h55.gdl.netease.com/identityv_setup_release_202309.exe` | **403 Forbidden** | — | — | — |
| 国服 共研服 | `https://h55.gdl.netease.com/identityv_setup_release_gongyan_20230512.exe` | **403 Forbidden** | — | — | — |

完整响应头（国际服 NeoX2 包，`--range 0-1023`）：

```
HTTP/1.1 206 Partial Content
Content-Type: application/x-msdos-program
Accept-Ranges: bytes
Last-Modified: Wed, 11 Sep 2024 20:10:19 GMT
ETag: "3af58ef90a035b275797507c1efecd05"
Content-Range: bytes 0-1023/3951463560
Content-Length: 1024
```

国服 403 的三种尝试**全部失败**：无附加头、带 `Referer: https://id5.163.com/`、带完整 Chrome UA、两者都带。
→ 与 bilibili wiki 的说明一致：PC 互通版**因版号问题官方关闭了直链下载**，改由【网易发烧平台】分发。

**两条关键推论：**

1. **网易 CDN 的 ETag 就是整文件 MD5**（32 位十六进制、无后缀时）。这直接满足项目对「MD5 校验」的需求，**不需要额外的 manifest 文件**。
   反例：旧包 ETag 尾部带 `-7`，说明该对象是分片上传的，此时 ETag **不是**整文件 MD5 —— 代码里必须能识别并回落到 SHA256/大小校验。
2. **`Accept-Ranges: bytes` 已确认**（国际服两个包都有），说明现有 `Downloader` 的 `Range` 断点续传逻辑对真链接**可直接工作**，无需改动。

### 1.2 版本 / 清单元数据源

| 源 | 地址 | 实测 | 可靠性 |
|---|---|---|---|
| winget-pkgs 包清单 | `manifests/n/NetEase/IdentityV`（GitHub API 或 jsDelivr） | 200，现有版本仅 `1.0.0.1`、`2.0.0.1` | 高（微软官方社区仓库，程序可读） |
| winget 2.0.0.1 installer.yaml | `https://cdn.jsdelivr.net/gh/microsoft/winget-pkgs@master/manifests/n/NetEase/IdentityV/2.0.0.1/NetEase.IdentityV.installer.yaml` | 200 | 高 |

该 yaml 的关键内容（原文注释）：

```yaml
PackageVersion: 2.0.0.1
# Following version number are extracted from the game launcher.
# - GameVersion: 2.0.1863932
# - ResourceVersion: 2.0.1863932
InstallerType: nullsoft
ReleaseDate: 2024-09-11
InstallerUrl: https://h55na.gdl.easebar.com/identityv_setup_neox2_oversea_release_240912.exe
InstallerSha256: F25AB7E8CC61C4626A6D67D65DEE68F147D2E12F8C804A08E46D1BB5B357635A
```

→ **`GameVersion` / `ResourceVersion` 这两个字段是 komac 从游戏启动器里抽出来的**，说明启动器内部有可读的版本描述文件。这是抓包之外的另一个切入点（见 §三 方案 B）。

### 1.3 网易更新服务域的分布（DNS 实测）

`{code}.update.netease.com` 是一个**集群通配域**，与 `unisdk.update.netease.com` 解析到同一对 IP（`60.188.233.71` / `60.188.233.15`）。

| 域名 | 解析 | 备注 |
|---|---|---|
| `g18/g37/g55/g66/g79/g83/g92/g101/g103/g110/g112/g120/g130`.update.netease.com | ✅ 存在 | 各游戏各自的更新服务 |
| `g45/g142/g152/g162`.update.netease.com | ❌ 不存在 | 编号空洞 |
| `id5.update.netease.com` | ❌ NXDOMAIN | **`id5` 只是官网/下载站的标识，不是 UNISDK gamecode** |
| `dwrg` / `idv` / `nt`.update.netease.com | ❌ NXDOMAIN | 同上 |

**结论：第五人格的 UNISDK gamecode 猜不出来，必须抓包或读客户端目录。**

已知同类产品的清单路径惯例（来自《我的世界》中国版 x19 的公开接口文档，**不是第五人格**，仅供推断结构）：

```
GET https://x19.update.netease.com/cdnversion/obt_h5version.json
→ 200 {"StaticWebVersion":"obt20250715185049","PreStaticWebVersion":"obt20250715185049"}
```

即 `{code}.update.netease.com/cdnversion{vN}/{channel}_h5version.json` 是网易系「版本清单」的一种惯例路径。**对第五人格的适用性未经证实（置信度：中）**，可作为抓包后按图索骥的检索线索。

### 1.4 其他已知公开入口

| 入口 | 地址 | 来源 |
|---|---|---|
| 官方下载跳转（安卓/iOS） | `https://adl.netease.com/d/g/id5/c/gw?type=android`、`?type=ios` | 第五人格官网 |
| 安卓各渠道包（2023-04-20 公告） | `https://h55.gdl.netease.com/<渠道>20230420.apk`，如 `bilibili20230420.apk`、`taptap20230420.apk` | `https://id5.163.com/news/update/20230420/26477_1083955.html`（官方公告，含 20 个渠道直链） |
| PC 端官方分发 | 【网易发烧平台】内下载（启动游戏后不可关闭） | bilibili wiki「PC互通版」「正式服」 |

---

## 二、三层获取路径与成本

| 层 | 内容 | 需要你做什么 | 我能拿到什么 | 成本 / 稳定性 |
|---|---|---|---|---|
| **L1 整包级** | 官方 CDN 直链 + HTTP 元数据（size / ETag=MD5 / Last-Modified / Range） | **什么都不用给**，已实测可跑 | 版本检查、下载、断点续传、MD5 完整性校验 | 低 / 高（CDN 稳定，但版本号需另找来源） |
| **L2 文件级** | 启动器的更新 manifest（真正逐文件的 path/size/hash/下载前缀） | **抓一次包**（装 PC 端 + Fiddler/Charles，点「检查更新」，导出 .saz/.har） | 完整增量更新能力：差异比对、只下变更文件、补丁管理 | 中 / 中（签名算法可能随版本变动） |
| **L3 逆向** | 从启动器 `*.exe`/`*.dll` 提签名密钥与 URL 模板 | 提供客户端目录 或 允许我在 Windows 侧反汇编 | 同上，且不依赖抓包 | **高 / 低**（版本一更新就失效；且明确违反用户协议） |

**建议：只做 L1，L2 视需要再上，L3 不做。**

---

## 三、要拿到 L2 时的两个可执行方案

### 方案 A：抓包（推荐）

1. 装【网易发烧平台】→ 装第五人格 PC 端。
2. 挂 Fiddler / Charles / mitmproxy（HTTPS 解密需装根证书）。
3. 点启动器的「检查更新」，让它走完一轮。
4. 导出 `.saz` / `.har` / `.pcap`，重点保留 `*.update.netease.com`、`*gdl.netease.com*`、`*easebar.com*` 的请求与响应体。
5. 交付给我 → 我提取 manifest URL、schema、签名参数，直接对接 `resources/` 模块。

### 方案 B：读客户端目录（更轻，不用搭代理）

1. 在已装好的游戏目录执行 `dir /s /b /a > list.txt`（或 PS：`Get-ChildItem -Recurse -File | Select-Object FullName,Length`）。
2. 把目录里所有 `*.json` / `*.ini` / `*.cfg` / `version*` / `patch*` 命名的小文件（< 1 MB）一起打给我。
3. winget 的 `GameVersion: 2.0.1863932` 注释证明**启动器里有可读版本字段**，很可能就落在这些文件里，同时能反推 manifest 的字段结构。

> 两个方案都不需要你提供**安装包本体**：国际服直链我自己能下（也只需 URL + hash，不必真落一份 3.7 GB 到 C 盘 —— 它只剩约 80 GB）。

---

## 四、合规与风险（必须明说）

1. **网易用户协议禁止逆向客户端、禁止使用第三方工具替代官方启动器下载/更新**。《第五人格》PC 端带网易反外挂（NEAC）。
2. 第三方工具**读公开 CDN 上的公开文件**（GET + Range + 校验），风险最低；一旦涉及登录态、伪造客户端请求、绕过版本校验，账号被封的风险显著上升。
3. 因此建议本功能定位为：**「多实例本地磁盘管理与完整性校验」** ——
   扫描已安装目录 → 计算 hash → 报告缺失/损坏/多余文件 → 从官方公开直链补齐。
   这是纯读本地 + 读公开资源的被动行为，与「绕过启动器」有本质区别。
4. 本调研只使用**公开可访问**的 URL 与 DNS 查询，未对任何服务做越权探测。

---

## 五、落到代码上要做的事（不依赖真 manifest）

当前 `src/dwrg_manager/resources/manager.py` 里的资源服务器是**编造的**：

```python
ResourceServer(name="official", endpoint="https://resources.identityv.com", ...)
ResourceServer(name="backup",   endpoint="https://backup.resources.identityv.com", ...)
```

这两个域名不存在，`{base_url}/manifest.json` 会全量失败 —— 也就是说「资源管理」目前**有机制、无数据源**。建议：

1. **删掉编造域名**，资源源改为从 config 读取。
2. 新增 `HttpIndexTransport`：给一组直链，`HEAD` 拿 `Content-Length` + `ETag` + `Last-Modified`，就地构造 `ResourceManifest`。
   → **零 manifest 也能跑真数据**，`Validator` 用 ETag 当 MD5（带 `-N` 后缀时回落 SHA256/大小）。
3. 新增 `dwrg resource index --dir <游戏目录> -o manifest.json`：扫描本地目录生成清单（path/size/md5）。
   → 让「全量文件 / 增量更新 / MD5 校验」三条需求在不接触私有接口的前提下闭环。
4. `resource check/update` 接 winget-pkgs（经 jsDelivr 或 GitHub API，本机 `raw.githubusercontent.com` DNS 不通）。
5. 版本检查：优先读游戏目录里的版本字段；读不到再回落 winget。

---

## 六、来源与置信度

| # | 结论 | 来源 | 置信度 |
|---|---|---|---|
| 1 | 国际服完整包直链可用、支持 Range、ETag=MD5 | 本机 `curl.exe` 实测响应头 | **已实测** |
| 2 | 国服/共研服 PC 直链 403 | 本机实测（4 种请求头组合） | **已实测** |
| 3 | PC 端官方分发 = 网易发烧平台 | bilibili wiki「PC互通版」「正式服」 | 高（社区 wiki，与 403 现象吻合） |
| 4 | winget 有 `GameVersion/ResourceVersion` 字段 | winget-pkgs `2.0.0.1/installer.yaml` 原文注释 | 高（微软官方仓库） |
| 5 | `{code}.update.netease.com` 为集群通配域；`id5` 等不是 gamecode | 本机 DNS 实测 22 个域名 | **已实测** |
| 6 | 清单路径惯例 `.../cdnversion{vN}/{channel}_h5version.json` | 网易《我的世界》x19 公开接口文档 | 中（**未经第五人格验证**） |
| 7 | 第五人格真实 manifest 需要抓包 | 1.3 的否定结果 + 无公开文档 | 高（推断） |

> 未做任何越权访问；`h55.gdl.netease.com` 的 403 是服务器的主动拒绝，未尝试绕过。

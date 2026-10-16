"""
基础用法示例（以库的形式调用 ``dwrg_manager``）

演示如何不走 CLI、直接在 Python 里使用配置 / 渠道服 / 账号三个管理器：
列出渠道服、新增渠道服、创建与切换账号、校验密码、读取当前状态。

运行::

    python examples/basic_usage.py

示例全程使用**临时配置文件与临时密钥**，不会读写 ``~/.config/dwrg`` 与 ``~/.dwrg``。
"""

import os
import sys
import tempfile
from pathlib import Path

try:  # 已通过 pip install -e . 安装时直接导入
    from dwrg_manager.accounts.manager import AccountManager
    from dwrg_manager.config.manager import ConfigManager
    from dwrg_manager.servers.manager import ServerManager
except ModuleNotFoundError:  # 未安装时回退到源码目录
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
    from dwrg_manager.accounts.manager import AccountManager
    from dwrg_manager.config.manager import ConfigManager
    from dwrg_manager.servers.manager import ServerManager

#: 示例账号的用户名（3-20 位字母 / 数字 / 下划线）
DEMO_USERNAME = "demo_player"

#: 示例账号的密码（6-128 位）
DEMO_PASSWORD = "demo_password_123"

#: 示例中自定义的渠道服名称（仅允许字母 / 数字 / 下划线 / 短横线）
DEMO_SERVER = "demo-cdn"


def main() -> int:
    """跑完整示例。

    Returns:
        进程退出码，``0`` 表示全部步骤正常完成。
    """
    with tempfile.TemporaryDirectory(prefix="dwrg-example-") as tmp_dir:
        tmp = Path(tmp_dir)
        # 隔离环境：密钥文件与配置文件都落在临时目录
        os.environ["DWRG_KEY_FILE"] = str(tmp / "keyfile")

        config = ConfigManager(tmp / "config.yaml")
        servers = ServerManager(config)
        accounts = AccountManager(config)

        print("=== 第五人格命令行管理器 —— 基础用法示例 ===\n")

        print("1. 预置渠道服")
        for server in servers.list_servers():
            mark = " ★默认" if server.is_default else ""
            print(f"   - {server.name:<12} {server.region}  {server.endpoint}{mark}")

        print("\n2. 新增一个自定义渠道服")
        servers.add_server(
            name=DEMO_SERVER, endpoint="https://demo.example.com", region="CN"
        )
        print(f"   现有渠道服 {len(servers.list_servers())} 个")

        print("\n3. 创建账号")
        account = accounts.create_account(
            username=DEMO_USERNAME,
            server="official",
            password=DEMO_PASSWORD,
        )
        print(
            f"   ✓ {account.username}  id={account.display_id()}  server={account.server}"
        )

        print("\n4. 校验密码")
        passed = accounts.authenticate(DEMO_USERNAME, DEMO_PASSWORD)
        rejected = accounts.authenticate(DEMO_USERNAME, "wrong-password")
        print(f"   正确密码 -> {'通过' if passed else '失败'}")
        print(f"   错误密码 -> {'通过（不符合预期）' if rejected else '按预期拒绝'}")

        print("\n5. 切换当前账号与渠道服")
        print(
            f"   切换账号:   {'成功' if accounts.switch_account(account.id) else '失败'}"
        )
        print(
            f"   切换渠道服: {'成功' if servers.switch_server('bserver') else '失败'}"
        )

        print("\n6. 读取当前状态")
        current_account = accounts.get_current_account()
        current_server = servers.get_current_server()
        print(
            f"   当前账号:   {current_account.username if current_account else '未设置'}"
        )
        print(f"   当前渠道服: {current_server.name if current_server else '未设置'}")

        print("\n7. 配置落盘位置（临时目录，退出后自动清理）")
        print(f"   {config.config_path}")

        print("\n=== 示例完成 ===")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""
CLI 命令定义

本模块组装 ``dwrg`` 的全部命令与子命令组，并作为 Typer 应用的唯一定义处
（``main.py`` 仅做入口转发）。

约定：

* 所有子命令组使用 :func:`typer.Typer` 的 ``no_args_is_help=True``，直接执行
  ``dwrg account`` 会打印帮助而不是报错。
* 业务异常统一为 :class:`~dwrg_manager.exceptions.DWRGError`，通过
  :func:`_cli_errors` 上下文管理器转换成用户可读的单行提示，退出码为 1。
* 面向用户的文案统一经 :func:`dwrg_manager.i18n.t` 输出，便于多语言切换。
"""

import asyncio
import json
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, NoReturn

import typer
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .accounts import AccountManager
from .config.manager import ConfigManager
from .exceptions import DWRGError
from .i18n import set_language, t
from .launcher import LauncherManager
from .resources.manager import ResourceManager
from .servers import ServerManager
from .utils.logger import get_logger, setup_logging
from .utils.version import get_version

logger = get_logger(__name__)
console = Console()

# --------------------------------------------------------------------------- #
# 应用与子命令组
# --------------------------------------------------------------------------- #

app = typer.Typer(
    name="dwrg",
    help=t("cli.app.help", default="第五人格游戏多渠道服和多账号管理工具"),
    add_completion=False,
    no_args_is_help=True,
)
account_app = typer.Typer(
    help=t("cli.group.account", default="账号管理"), no_args_is_help=True
)
server_app = typer.Typer(
    help=t("cli.group.server", default="渠道服管理"), no_args_is_help=True
)
resource_app = typer.Typer(
    help=t("cli.group.resource", default="资源管理"), no_args_is_help=True
)
launch_app = typer.Typer(help=t("cli.group.launch", default="启动管理"))
config_app = typer.Typer(
    help=t("cli.group.config", default="配置管理"), no_args_is_help=True
)
plugin_app = typer.Typer(
    help=t("cli.group.plugin", default="插件管理"), no_args_is_help=True
)

app.add_typer(account_app, name="account")
app.add_typer(server_app, name="server")
app.add_typer(resource_app, name="resource")
app.add_typer(launch_app, name="launch")
app.add_typer(config_app, name="config")
app.add_typer(plugin_app, name="plugin")


# --------------------------------------------------------------------------- #
# 通用工具
# --------------------------------------------------------------------------- #


def _ok(message: str) -> None:
    """打印成功提示。

    Args:
        message: 提示内容。
    """
    rprint(f"[green]✓[/green] {message}")


def _warn(message: str) -> None:
    """打印警告提示。

    Args:
        message: 提示内容。
    """
    rprint(f"[yellow]![/yellow] {message}")


def _fail(message: str, code: int = 1) -> NoReturn:
    """打印错误并终止进程。

    Args:
        message: 错误内容。
        code: 退出码。

    Raises:
        typer.Exit: 始终抛出，携带给定退出码。
    """
    rprint(f"[red]✗[/red] {message}")
    raise typer.Exit(code)


@contextmanager
def _cli_errors(action: str) -> Iterator[None]:
    """把业务异常转换为用户可读的提示。

    Args:
        action: 正在执行的动作描述，用于日志前缀。

    Yields:
        None：业务代码块。
    """
    try:
        yield
    except DWRGError as exc:
        logger.error("%s 失败: %s", action, exc.user_message())
        rprint(
            f"[red]✗[/red] {action}"
            f"{t('cli.common.failed_suffix', default='失败')}: {exc.user_message()}"
        )
        raise typer.Exit(1) from None
    except KeyboardInterrupt:  # pragma: no cover - 交互中断
        rprint(t("cli.common.cancelled", default="已取消"))
        raise typer.Exit(130) from None


def _json_out(data: Any) -> None:
    """以 JSON 形式输出数据。

    直接写标准输出而不经 Rich，避免长行被按终端宽度折行而破坏 JSON 结构
    （折行后的内容无法被 ``jq`` 等工具解析）。

    Args:
        data: 支持 ``model_dump`` 的对象、对象列表或普通可序列化对象。
    """
    if hasattr(data, "model_dump"):
        data = data.model_dump(mode="json")
    elif isinstance(data, (list, tuple)):
        data = [
            item.model_dump(mode="json") if hasattr(item, "model_dump") else item
            for item in data
        ]
    sys.stdout.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _table(*columns: str) -> Table:
    """创建一个带表头的 Rich 表格。

    Args:
        *columns: 列标题。

    Returns:
        配置好的 :class:`rich.table.Table`。
    """
    table = Table(show_header=True, header_style="bold magenta")
    for column in columns:
        table.add_column(column)
    return table


# --------------------------------------------------------------------------- #
# 顶层回调
# --------------------------------------------------------------------------- #


@app.callback(invoke_without_command=True)
def main(
    version: bool = typer.Option(
        False, "--version", "-V", help="显示版本信息", is_eager=True
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="详细输出"),
    lang: str | None = typer.Option(
        None, "--lang", help="输出语言，例如 zh-CN / en-US"
    ),
) -> None:
    """第五人格命令行管理器。

    Args:
        version: 是否只打印版本号。
        verbose: 是否把日志同时输出到终端。
        lang: 覆盖配置中的输出语言。
    """
    if version:
        rprint(f"[bold green]DWRG CLI Manager[/bold green] {get_version()}")
        raise typer.Exit()

    manager = ConfigManager()
    try:
        set_language(lang or manager.get_app_config().language)
    except DWRGError as exc:  # pragma: no cover - 配置损坏时仍然可用
        logger.warning("语言初始化失败，回退默认: %s", exc)

    if verbose:
        setup_logging(level="DEBUG", console=True, force=True)
        _warn(t("cli.common.verbose_on", default="详细输出模式已启用"))


@app.command("help")
def help_command() -> None:
    """显示命令总览。"""
    table = Table(show_header=False, box=None)
    table.add_column("命令", style="cyan")
    table.add_column("描述", style="white")
    for cmd, desc in (
        ("account", "账号管理"),
        ("server", "渠道服管理"),
        ("resource", "资源管理"),
        ("launch", "启动管理"),
        ("config", "配置管理"),
        ("plugin", "插件管理"),
        ("diagnose", "系统诊断"),
        ("status", "状态检查"),
    ):
        table.add_row(f"[bold]{cmd}[/bold]", desc)
    console.print(
        Panel(table, title=t("cli.help.title", default="可用命令"), border_style="blue")
    )


# --------------------------------------------------------------------------- #
# 账号管理
# --------------------------------------------------------------------------- #


@account_app.command("add")
def account_add(
    username: str = typer.Option(..., "--username", "-u", help="用户名"),
    password: str = typer.Option(
        ..., "--password", "-p", help="密码", prompt=True, hide_input=True
    ),
    server: str = typer.Option("official", "--server", "-s", help="渠道服"),
    config: str | None = typer.Option(None, "--config", help="自定义配置文件路径"),
) -> None:
    """添加账号。"""
    with _cli_errors("账号添加"):
        manager = AccountManager(ConfigManager(config) if config else ConfigManager())
        account = manager.create_account(username, server, password)
        _ok(f"账号添加成功: {account.username} ({account.display_id()})")


@account_app.command("list")
def account_list(
    server: str | None = typer.Option(None, "--server", "-s", help="仅显示该渠道服"),
    fmt: str = typer.Option("table", "--format", "-f", help="输出格式: table | json"),
    config: str | None = typer.Option(None, "--config", help="自定义配置文件路径"),
) -> None:
    """列出账号。"""
    with _cli_errors("列出账号"):
        manager = AccountManager(ConfigManager(config) if config else ConfigManager())
        accounts = manager.list_accounts(server)
        if fmt == "json":
            _json_out(accounts)
            return
        if not accounts:
            _warn("暂无账号")
            return
        table = _table("账号ID", "用户名", "渠道服", "当前", "最后登录")
        for acc in accounts:
            table.add_row(
                acc.display_id(),
                acc.username,
                acc.server,
                "★" if acc.is_current else "",
                acc.last_login.strftime("%Y-%m-%d %H:%M")
                if acc.last_login
                else "从未登录",
            )
        console.print(table)


@account_app.command("switch")
def account_switch(
    account_id: str = typer.Argument(..., help="账号ID"),
    config: str | None = typer.Option(None, "--config", help="自定义配置文件路径"),
) -> None:
    """切换当前账号。"""
    with _cli_errors("账号切换"):
        manager = AccountManager(ConfigManager(config) if config else ConfigManager())
        if manager.switch_account(account_id):
            _ok("账号切换成功")
        else:
            _fail(f"账号不存在: {account_id}")


@account_app.command("remove")
def account_remove(
    account_id: str = typer.Argument(..., help="账号ID"),
    force: bool = typer.Option(False, "--force", "-f", help="跳过确认"),
    config: str | None = typer.Option(None, "--config", help="自定义配置文件路径"),
) -> None:
    """删除账号。"""
    if not force and not typer.confirm(f"确定要删除账号 {account_id} 吗？"):
        raise typer.Exit(0)
    with _cli_errors("账号删除"):
        manager = AccountManager(ConfigManager(config) if config else ConfigManager())
        if manager.remove_account(account_id):
            _ok("账号删除成功")
        else:
            _fail(f"账号不存在: {account_id}")


@account_app.command("status")
def account_status(
    account_id: str | None = typer.Argument(None, help="账号ID，省略则显示当前账号"),
    config: str | None = typer.Option(None, "--config", help="自定义配置文件路径"),
) -> None:
    """查看账号状态。"""
    with _cli_errors("查询账号状态"):
        manager = AccountManager(ConfigManager(config) if config else ConfigManager())
        account = (
            manager.get_account(account_id)
            if account_id
            else manager.get_current_account()
        )
        if account is None:
            _fail("未找到账号")
        panel = Panel(
            f"[cyan]账号ID:[/cyan] {account.id}\n"
            f"[green]用户名:[/green] {account.username}\n"
            f"[yellow]渠道服:[/yellow] {account.server}\n"
            f"[white]当前账号:[/white] {'是' if account.is_current else '否'}\n"
            f"[blue]最后登录:[/blue] "
            f"{account.last_login.strftime('%Y-%m-%d %H:%M:%S') if account.last_login else '从未登录'}",
            title="账号状态",
            border_style="blue",
        )
        console.print(panel)


@account_app.command("login")
def account_login(
    account_id: str = typer.Argument(..., help="账号ID"),
    server: str | None = typer.Option(None, "--server", "-s", help="目标渠道服"),
    config: str | None = typer.Option(None, "--config", help="自定义配置文件路径"),
) -> None:
    """登录账号（写入登录态供启动器使用）。"""
    with _cli_errors("账号登录"):
        manager = AccountManager(ConfigManager(config) if config else ConfigManager())
        result = manager.login(account_id, server)
        if result.success:
            _ok(f"{result.username} 登录 {result.server} 成功")
        else:
            _fail(result.message or "登录失败")


@account_app.command("logout")
def account_logout(
    config: str | None = typer.Option(None, "--config", help="自定义配置文件路径"),
) -> None:
    """登出当前账号。"""
    with _cli_errors("账号登出"):
        manager = AccountManager(ConfigManager(config) if config else ConfigManager())
        account = manager.get_current_account()
        if account is None:
            _warn("当前没有登录的账号")
            return
        manager.config_manager.get_config().app.account = None
        for acc in manager.config_manager.get_config().accounts.values():
            acc.is_current = False
        manager.config_manager.save_config()
        _ok(f"已登出账号: {account.username}")


# --------------------------------------------------------------------------- #
# 渠道服管理
# --------------------------------------------------------------------------- #


@server_app.command("list")
def server_list(
    fmt: str = typer.Option("table", "--format", "-f", help="输出格式: table | json"),
    config: str | None = typer.Option(None, "--config", help="自定义配置文件路径"),
) -> None:
    """列出渠道服。"""
    with _cli_errors("列出渠道服"):
        manager = ServerManager(ConfigManager(config) if config else ConfigManager())
        servers = manager.list_servers()
        if fmt == "json":
            _json_out(servers)
            return
        if not servers:
            _warn("暂无渠道服")
            return
        table = _table("名称", "状态", "版本", "地区", "默认", "地址")
        for srv in servers:
            color = "green" if srv.status == "active" else "red"
            table.add_row(
                srv.name,
                f"[{color}]{srv.status}[/{color}]",
                srv.version,
                srv.region,
                "★" if srv.is_default else "",
                srv.endpoint or "-",
            )
        console.print(table)


@server_app.command("current")
def server_current(
    config: str | None = typer.Option(None, "--config", help="自定义配置文件路径"),
) -> None:
    """显示当前渠道服。"""
    with _cli_errors("查询当前渠道服"):
        manager = ServerManager(ConfigManager(config) if config else ConfigManager())
        current = manager.get_current_server()
        if current is None:
            _warn("未设置当前渠道服")
            return
        rprint(f"[cyan]当前渠道服:[/cyan] {current.name} ({current.version})")


@server_app.command("detect")
def server_detect(
    config: str | None = typer.Option(None, "--config", help="自定义配置文件路径"),
) -> None:
    """探测各渠道服延迟并推荐最优。"""
    with _cli_errors("探测渠道服"):
        manager = ServerManager(ConfigManager(config) if config else ConfigManager())
        results = asyncio.run(manager.probe_all())
        if not results:
            _warn("没有可探测的渠道服")
            return
        table = _table("名称", "状态", "延迟(ms)", "在线玩家")
        for name, status in sorted(results.items()):
            ping = "超时" if status.ping == float("inf") else f"{status.ping:.1f}"
            color = "green" if status.status != "offline" else "red"
            table.add_row(
                name, f"[{color}]{status.status}[/{color}]", ping, str(status.players)
            )
        console.print(table)
        best = asyncio.run(manager.detect_current_server())
        if best:
            _ok(f"推荐渠道服: {best}")
        else:
            _warn("未能探测到可用渠道服（离线环境下属正常）")


@server_app.command("switch")
def server_switch(
    server_name: str = typer.Argument(..., help="渠道服名称"),
    force: bool = typer.Option(False, "--force", "-f", help="跳过确认"),
    config: str | None = typer.Option(None, "--config", help="自定义配置文件路径"),
) -> None:
    """切换当前渠道服。"""
    if not force and not typer.confirm(f"确定要切换到 {server_name} 吗？"):
        raise typer.Exit(0)
    with _cli_errors("渠道服切换"):
        manager = ServerManager(ConfigManager(config) if config else ConfigManager())
        if manager.switch_server(server_name):
            _ok(f"已切换到 {server_name}")
        else:
            _fail(f"渠道服不存在: {server_name}")


def _show_server(manager: ServerManager, server_name: str) -> None:
    """打印单个渠道服的详情面板。

    Args:
        manager: 渠道服管理器。
        server_name: 渠道服名称。
    """
    server = manager.get_server(server_name)
    if server is None:
        _fail(f"未找到渠道服: {server_name}")
    last_check = (
        server.last_check.strftime("%Y-%m-%d %H:%M:%S")
        if server.last_check
        else "尚未探测"
    )
    ping = "未知" if server.ping is None else f"{server.ping:.1f} ms"
    console.print(
        Panel(
            f"[cyan]名称:[/cyan] {server.name}\n"
            f"[green]状态:[/green] {server.status}\n"
            f"[yellow]版本:[/yellow] {server.version}\n"
            f"[white]地区:[/white] {server.region}\n"
            f"[blue]地址:[/blue] {server.endpoint or '-'}\n"
            f"[magenta]延迟:[/magenta] {ping}\n"
            f"[magenta]最近探测:[/magenta] {last_check}",
            title=f"渠道服信息 - {server.name}",
            border_style="blue",
        )
    )


@server_app.command("show")
def server_show(
    server_name: str = typer.Argument(..., help="渠道服名称"),
    config: str | None = typer.Option(None, "--config", help="自定义配置文件路径"),
) -> None:
    """显示渠道服详情。"""
    with _cli_errors("显示渠道服信息"):
        _show_server(
            ServerManager(ConfigManager(config) if config else ConfigManager()),
            server_name,
        )


@server_app.command("info")
def server_info(
    server_name: str = typer.Argument(..., help="渠道服名称"),
    config: str | None = typer.Option(None, "--config", help="自定义配置文件路径"),
) -> None:
    """``server show`` 的别名。"""
    server_show(server_name, config)


@server_app.command("add")
def server_add(
    name: str = typer.Argument(..., help="渠道服名称"),
    endpoint: str = typer.Option("", "--endpoint", "-e", help="接口地址"),
    region: str = typer.Option("CN", "--region", "-r", help="地区"),
    version: str = typer.Option("1.0.0", "--version", help="版本号"),
    is_default: bool = typer.Option(False, "--default", help="设为默认渠道服"),
    config: str | None = typer.Option(None, "--config", help="自定义配置文件路径"),
) -> None:
    """新增渠道服。"""
    with _cli_errors("新增渠道服"):
        manager = ServerManager(ConfigManager(config) if config else ConfigManager())
        server = manager.add_server(
            name=name,
            endpoint=endpoint,
            region=region,
            version=version,
            is_default=is_default,
        )
        _ok(f"渠道服已添加: {server.name}")


@server_app.command("remove")
def server_remove(
    name: str = typer.Argument(..., help="渠道服名称"),
    force: bool = typer.Option(False, "--force", "-f", help="跳过确认"),
    config: str | None = typer.Option(None, "--config", help="自定义配置文件路径"),
) -> None:
    """删除渠道服。"""
    if not force and not typer.confirm(f"确定要删除渠道服 {name} 吗？"):
        raise typer.Exit(0)
    with _cli_errors("删除渠道服"):
        manager = ServerManager(ConfigManager(config) if config else ConfigManager())
        if manager.remove_server(name):
            _ok(f"渠道服已删除: {name}")
        else:
            _fail(f"渠道服不存在: {name}")


@server_app.command("set-default")
def server_set_default(
    name: str = typer.Argument(..., help="渠道服名称"),
    config: str | None = typer.Option(None, "--config", help="自定义配置文件路径"),
) -> None:
    """设置默认渠道服。"""
    with _cli_errors("设置默认渠道服"):
        manager = ServerManager(ConfigManager(config) if config else ConfigManager())
        if manager.set_default(name):
            _ok(f"默认渠道服已设置为 {name}")
        else:
            _fail(f"渠道服不存在: {name}")


# --------------------------------------------------------------------------- #
# 资源管理
# --------------------------------------------------------------------------- #


@resource_app.command("check")
def resource_check(
    server: str | None = typer.Option(None, "--server", "-s", help="渠道服"),
    config: str | None = typer.Option(None, "--config", help="自定义配置文件路径"),
) -> None:
    """检查游戏资源完整性。"""
    with _cli_errors("检查资源"):
        manager = ResourceManager(ConfigManager(config) if config else ConfigManager())
        result = asyncio.run(manager.check_resources(server))
        console.print(
            Panel(
                f"[white]文件总数:[/white] {result.total_files}\n"
                f"[green]正常文件:[/green] {result.healthy_files}\n"
                f"[red]损坏文件:[/red] {result.corrupted_files}\n"
                f"[yellow]缺失文件:[/yellow] {result.missing_files}",
                title="资源检查结果",
                border_style="blue",
            )
        )


@resource_app.command("verify")
def resource_verify(
    server: str | None = typer.Option(None, "--server", "-s", help="渠道服"),
    config: str | None = typer.Option(None, "--config", help="自定义配置文件路径"),
) -> None:
    """``resource check`` 的别名。"""
    resource_check(server, config)


@resource_app.command("update")
def resource_update(
    server: str | None = typer.Option(None, "--server", "-s", help="渠道服"),
    force: bool = typer.Option(False, "--force", "-f", help="强制全量更新"),
    config: str | None = typer.Option(None, "--config", help="自定义配置文件路径"),
) -> None:
    """下载/更新游戏资源。"""
    with _cli_errors("更新资源"):
        manager = ResourceManager(ConfigManager(config) if config else ConfigManager())
        result = asyncio.run(manager.update_resources(server, force))
        if result.success:
            _ok(f"资源更新完成：下载 {result.downloaded_files} 个文件")
        else:
            _fail(result.error or "资源更新失败")


@resource_app.command("clean")
def resource_clean(
    all_files: bool = typer.Option(False, "--all", "-a", help="清理全部缓存"),
    config: str | None = typer.Option(None, "--config", help="自定义配置文件路径"),
) -> None:
    """清理缓存与临时文件。"""
    with _cli_errors("清理缓存"):
        manager = ResourceManager(ConfigManager(config) if config else ConfigManager())
        if manager.clean_cache(all_files):
            _ok("缓存清理完成")
        else:
            _fail("缓存清理失败")


@resource_app.command("info")
def resource_info(
    config: str | None = typer.Option(None, "--config", help="自定义配置文件路径"),
) -> None:
    """显示缓存与游戏目录信息。"""
    with _cli_errors("读取缓存信息"):
        manager = ResourceManager(ConfigManager(config) if config else ConfigManager())
        info = manager.get_cache_info()
        table = _table("项目", "值")
        table.add_row("缓存目录", str(info.get("cache_dir", "-")))
        table.add_row("缓存文件数", str(info.get("cache_files", 0)))
        table.add_row(
            "缓存大小", str(info.get("cache_size_human", info.get("cache_size", 0)))
        )
        table.add_row("游戏目录", str(info.get("game_dir", "-")))
        table.add_row("游戏文件数", str(info.get("game_files", 0)))
        table.add_row(
            "游戏大小", str(info.get("game_size_human", info.get("game_size", 0)))
        )
        console.print(table)


# --------------------------------------------------------------------------- #
# 启动管理
# --------------------------------------------------------------------------- #


@launch_app.callback(invoke_without_command=True)
def launch_entry(
    ctx: typer.Context,
    account: str | None = typer.Option(None, "--account", "-a", help="账号ID"),
    server: str | None = typer.Option(None, "--server", "-s", help="渠道服"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="透传游戏输出"),
    config: str | None = typer.Option(None, "--config", help="自定义配置文件路径"),
) -> None:
    """启动游戏；不带子命令时直接执行 ``dwrg launch``。

    Args:
        ctx: Typer 上下文，用于判断是否指定了子命令。
        account: 账号 ID。
        server: 渠道服。
        verbose: 是否透传子进程输出。
        config: 自定义配置文件路径。
    """
    if ctx.invoked_subcommand is not None:
        return
    _do_launch(account, server, verbose, config)


@launch_app.command("start")
def launch_start(
    account: str | None = typer.Option(None, "--account", "-a", help="账号ID"),
    server: str | None = typer.Option(None, "--server", "-s", help="渠道服"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="透传游戏输出"),
    config: str | None = typer.Option(None, "--config", help="自定义配置文件路径"),
) -> None:
    """启动游戏（等价于 ``dwrg launch``）。"""
    _do_launch(account, server, verbose, config)


def _do_launch(
    account: str | None, server: str | None, verbose: bool, config: str | None
) -> None:
    """执行启动逻辑。

    Args:
        account: 账号 ID。
        server: 渠道服。
        verbose: 是否透传子进程输出。
        config: 自定义配置文件路径。
    """
    with _cli_errors("启动游戏"):
        launcher = LauncherManager(ConfigManager(config) if config else ConfigManager())
        result = launcher.launch(account, server, verbose)
        if result.success:
            _ok(f"游戏已启动，进程ID: {result.process_id}")
        else:
            _fail(result.error_message or "游戏启动失败")


@launch_app.command("stop")
def launch_stop(
    force: bool = typer.Option(False, "--force", "-f", help="强制终止"),
    config: str | None = typer.Option(None, "--config", help="自定义配置文件路径"),
) -> None:
    """停止游戏进程。"""
    with _cli_errors("停止游戏"):
        launcher = LauncherManager(ConfigManager(config) if config else ConfigManager())
        if launcher.stop_game(force):
            _ok("游戏进程已停止")
        else:
            _fail("停止游戏失败")


@launch_app.command("status")
def launch_status(
    config: str | None = typer.Option(None, "--config", help="自定义配置文件路径"),
) -> None:
    """显示本次会话中游戏进程的状态。"""
    with _cli_errors("查询游戏状态"):
        launcher = LauncherManager(ConfigManager(config) if config else ConfigManager())
        status = launcher.get_game_status()
        if status.is_running:
            _ok(
                f"游戏运行中：PID {status.process_id}，"
                f"CPU {status.cpu_usage:.1f}%，内存 {status.memory_usage / 1024 / 1024:.1f} MB，"
                f"已运行 {status.running_time:.0f}s"
            )
        else:
            _warn("游戏未在本会话中运行")


# --------------------------------------------------------------------------- #
# 配置管理
# --------------------------------------------------------------------------- #


@config_app.command("show")
def config_show(
    key: str | None = typer.Option(None, "--key", "-k", help="仅显示指定配置项"),
    fmt: str = typer.Option("table", "--format", "-f", help="输出格式: table | json"),
    config: str | None = typer.Option(None, "--config", help="自定义配置文件路径"),
) -> None:
    """显示配置。"""
    with _cli_errors("显示配置"):
        manager = ConfigManager(config) if config else ConfigManager()
        data = manager.get_config_dict()
        if key:
            node: Any = data
            # 支持三种写法：顶层键（servers/accounts）、带前缀的全路径（app.log_level）、
            # 以及省略 ``app.`` 的裸字段名（log_level）。
            parts = key.split(".")
            if parts[0] != "app" and key not in data:
                parts = ["app", *parts]
            for part in parts:
                if isinstance(node, dict) and part in node:
                    node = node[part]
                else:
                    _fail(f"配置项不存在: {key}")
            rprint(f"[cyan]{key}:[/cyan] {node}")
            return
        if fmt == "json":
            _json_out(data)
            return
        table = _table("配置项", "值")
        for field, value in data["app"].items():
            table.add_row(f"app.{field}", str(value))
        table.add_row("servers", f"{len(data['servers'])} 个渠道服")
        table.add_row("accounts", f"{len(data['accounts'])} 个账号")
        console.print(table)


@config_app.command("set")
def config_set(
    key: str = typer.Argument(..., help="配置键，例如 log_level"),
    value: str = typer.Argument(..., help="配置值"),
    config: str | None = typer.Option(None, "--config", help="自定义配置文件路径"),
) -> None:
    """设置配置项。"""
    with _cli_errors("设置配置"):
        manager = ConfigManager(config) if config else ConfigManager()
        manager.set_config(key, value)
        _ok(f"配置已更新: {key} = {value}")


@config_app.command("unset")
def config_unset(
    key: str = typer.Argument(..., help="配置键"),
    config: str | None = typer.Option(None, "--config", help="自定义配置文件路径"),
) -> None:
    """把配置项恢复为默认值。"""
    with _cli_errors("重置配置"):
        manager = ConfigManager(config) if config else ConfigManager()
        manager.unset_config(key)
        _ok(f"配置项已重置: {key}")


@config_app.command("reset")
def config_reset(
    force: bool = typer.Option(False, "--force", "-f", help="跳过确认"),
    config: str | None = typer.Option(None, "--config", help="自定义配置文件路径"),
) -> None:
    """重置全部配置为默认值。"""
    if not force and not typer.confirm("确定要重置全部配置吗？"):
        raise typer.Exit(0)
    with _cli_errors("重置配置"):
        from .config.models import default_config

        manager = ConfigManager(config) if config else ConfigManager()
        manager.config = default_config()
        manager.save_config()
        _ok("配置已重置为默认值")


@config_app.command("export")
def config_export(
    path: str = typer.Argument(..., help="导出目标路径"),
    fmt: str = typer.Option("yaml", "--format", "-f", help="导出格式: yaml | json"),
    config: str | None = typer.Option(None, "--config", help="自定义配置文件路径"),
) -> None:
    """导出配置。"""
    with _cli_errors("导出配置"):
        manager = ConfigManager(config) if config else ConfigManager()
        target = manager.export_config(path, fmt)
        _ok(f"配置已导出到 {target}")


@config_app.command("import")
def config_import(
    path: str = typer.Argument(..., help="待导入的配置文件路径"),
    config: str | None = typer.Option(None, "--config", help="自定义配置文件路径"),
) -> None:
    """导入配置。"""
    with _cli_errors("导入配置"):
        manager = ConfigManager(config) if config else ConfigManager()
        manager.import_config(path)
        _ok(f"配置已从 {path} 导入")


# --------------------------------------------------------------------------- #
# 插件管理
# --------------------------------------------------------------------------- #


def _plugin_manager(plugin_dir: str | None = None) -> Any:
    """惰性构造插件管理器。

    Args:
        plugin_dir: 自定义插件目录；为 ``None`` 时使用 ``~/.dwrg/plugins``。

    Returns:
        :class:`dwrg_manager.plugins.PluginManager` 实例。
    """
    from .plugins import PluginManager

    return PluginManager(plugin_dir) if plugin_dir else PluginManager()


@plugin_app.command("list")
def plugin_list(
    fmt: str = typer.Option("table", "--format", "-f", help="输出格式: table | json"),
    plugin_dir: str | None = typer.Option(None, "--plugin-dir", help="插件目录"),
) -> None:
    """列出已安装插件。"""
    with _cli_errors("列出插件"):
        manager = _plugin_manager(plugin_dir)
        plugins = manager.list_plugins() if hasattr(manager, "list_plugins") else []
        if fmt == "json":
            _json_out(
                [
                    p.model_dump(mode="json") if hasattr(p, "model_dump") else p
                    for p in plugins
                ]
            )
            return
        if not plugins:
            _warn("未发现插件")
            return
        table = _table("名称", "版本", "状态", "描述")
        for plugin in plugins:
            table.add_row(
                getattr(plugin, "name", "-"),
                getattr(plugin, "version", "-"),
                "启用" if getattr(plugin, "enabled", False) else "禁用",
                getattr(plugin, "description", ""),
            )
        console.print(table)


@plugin_app.command("info")
def plugin_info(
    name: str = typer.Argument(..., help="插件名称"),
    plugin_dir: str | None = typer.Option(None, "--plugin-dir", help="插件目录"),
) -> None:
    """显示插件详情。"""
    with _cli_errors("读取插件信息"):
        manager = _plugin_manager(plugin_dir)
        plugin = manager.get_plugin(name)
        if plugin is None:
            _fail(f"插件不存在: {name}")
        _json_out(plugin)


@plugin_app.command("enable")
def plugin_enable(
    name: str = typer.Argument(..., help="插件名称"),
    plugin_dir: str | None = typer.Option(None, "--plugin-dir", help="插件目录"),
) -> None:
    """启用插件。"""
    with _cli_errors("启用插件"):
        if _plugin_manager(plugin_dir).enable_plugin(name):
            _ok(f"插件已启用: {name}")
        else:
            _fail(f"启用失败: {name}")


@plugin_app.command("disable")
def plugin_disable(
    name: str = typer.Argument(..., help="插件名称"),
    plugin_dir: str | None = typer.Option(None, "--plugin-dir", help="插件目录"),
) -> None:
    """禁用插件。"""
    with _cli_errors("禁用插件"):
        if _plugin_manager(plugin_dir).disable_plugin(name):
            _ok(f"插件已禁用: {name}")
        else:
            _fail(f"禁用失败: {name}")


# --------------------------------------------------------------------------- #
# 系统命令
# --------------------------------------------------------------------------- #


@app.command("diagnose")
def diagnose_system(
    output: str | None = typer.Option(
        None, "--output", "-o", help="把诊断结果写入文件"
    ),
    config: str | None = typer.Option(None, "--config", help="自定义配置文件路径"),
) -> None:
    """系统诊断：环境、配置与启动条件。"""
    with _cli_errors("系统诊断"):
        from .utils.system import SystemManager

        manager = ConfigManager(config) if config else ConfigManager()
        system = SystemManager()
        launcher = LauncherManager(manager, system)

        report: dict[str, Any] = {
            "version": get_version(),
            "system": system.get_system_info(),
            "config_path": str(manager.config_path),
            "servers": len(manager.list_servers()),
            "accounts": len(manager.list_accounts()),
            "launch": launcher.diagnose_launch(),
            "memory": system.get_memory_info(),
        }

        if output:
            from pathlib import Path

            Path(output).expanduser().write_text(
                json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            _ok(f"诊断报告已写入 {output}")
            return

        table = _table("检查项", "结果")
        for field, value in report["system"].items():
            table.add_row(f"system.{field}", str(value))
        for field, value in report["launch"].items():
            if field == "recommendations":
                continue
            table.add_row(f"launch.{field}", str(value))
        console.print(table)
        recommendations = report["launch"].get("recommendations") or []
        for advice in recommendations:
            _warn(str(advice))


@app.command("status")
def show_status(
    config: str | None = typer.Option(None, "--config", help="自定义配置文件路径"),
) -> None:
    """显示当前渠道服、账号与游戏运行状态。"""
    with _cli_errors("显示状态"):
        manager = ConfigManager(config) if config else ConfigManager()
        server = manager.get_current_server()
        account = manager.get_current_account()

        table = _table("项目", "值")
        table.add_row("版本", get_version())
        table.add_row("配置文件", str(manager.config_path))
        table.add_row(
            "当前渠道服",
            f"{server.name} ({server.version})" if server else "未设置",
        )
        table.add_row(
            "当前账号",
            f"{account.username} ({account.display_id()})" if account else "未设置",
        )
        table.add_row("渠道服数量", str(len(manager.list_servers())))
        table.add_row("账号数量", str(len(manager.list_accounts())))
        console.print(table)

        game = LauncherManager(manager).get_game_status()
        if game.is_running:
            _ok(f"游戏运行中：PID {game.process_id}")
        else:
            _warn("游戏未运行")


__all__ = ["app"]

if __name__ == "__main__":  # pragma: no cover
    sys.exit(app())

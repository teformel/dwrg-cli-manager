"""
账号管理单元测试

覆盖 :mod:`dwrg_manager.accounts.models` 的 ``Account`` / ``LoginResult`` 以及
:class:`dwrg_manager.accounts.manager.AccountManager` 的 CRUD、切换与登录。
"""

import pytest
from pydantic import ValidationError as PydanticValidationError

from dwrg_manager.accounts import AccountManager, LoginResult
from dwrg_manager.accounts.models import Account
from dwrg_manager.config import ConfigManager
from dwrg_manager.exceptions import AccountError, ValidationError

VALID_ID = "acc-00000001"


@pytest.mark.unit
class TestAccountModel:
    """``Account`` 运行时模型。"""

    def test_create_with_valid_data_strips_whitespace(self) -> None:
        """合法的用户名与渠道服应被规范化。"""
        account = Account(id=VALID_ID, username="  hero  ", server=" official ")

        assert account.username == "hero"
        assert account.server == "official"

    def test_create_with_short_id_raises_validation_error(self) -> None:
        """过短的 ID 应被拒绝。"""
        with pytest.raises(PydanticValidationError):
            Account(id="short", username="hero", server="official")

    def test_create_with_illegal_username_raises_validation_error(self) -> None:
        """含非法字符的用户名应被拒绝。"""
        with pytest.raises(PydanticValidationError):
            Account(id=VALID_ID, username="bad name", server="official")

    def test_create_with_illegal_server_raises_validation_error(self) -> None:
        """含非法字符的渠道服名应被拒绝。"""
        with pytest.raises(PydanticValidationError):
            Account(id=VALID_ID, username="hero", server="bad name")

    def test_display_id_truncates_long_identifier(self) -> None:
        """超长 ID 截断为前 8 位加省略号。"""
        account = Account(id="0123456789abcdef", username="hero", server="official")

        assert account.display_id() == "01234567..."


@pytest.mark.unit
class TestLoginResult:
    """``LoginResult`` 默认值。"""

    def test_defaults_fill_optional_fields(self) -> None:
        """除 ``success`` 外均有默认值。"""
        result = LoginResult(success=False)

        assert result.account_id == ""
        assert result.username == ""
        assert result.server == ""
        assert result.message == ""


@pytest.mark.unit
class TestCreateAccount:
    """``AccountManager.create_account``。"""

    def test_create_with_valid_data_returns_account(
        self, account_manager: AccountManager
    ) -> None:
        """合法输入应返回带密文与哈希的账号。"""
        account = account_manager.create_account("hero", "official", "secret123")

        assert account.username == "hero"
        assert account.server == "official"
        assert account.encrypted_password
        assert account.password_hash

    def test_create_with_short_username_raises_validation_error(
        self, account_manager: AccountManager
    ) -> None:
        """用户名过短应抛出校验异常。"""
        with pytest.raises(ValidationError):
            account_manager.create_account("ab", "official", "secret123")

    def test_create_with_short_password_raises_validation_error(
        self, account_manager: AccountManager
    ) -> None:
        """密码过短应抛出校验异常。"""
        with pytest.raises(ValidationError):
            account_manager.create_account("hero", "official", "123")

    def test_create_with_unknown_server_raises_account_error(
        self, account_manager: AccountManager
    ) -> None:
        """渠道服不存在时抛出 :class:`AccountError`。"""
        with pytest.raises(AccountError):
            account_manager.create_account("hero", "nope", "secret123")

    def test_create_with_duplicate_username_raises_account_error(
        self, account_manager: AccountManager
    ) -> None:
        """重复用户名应被拒绝。"""
        account_manager.create_account("hero", "official", "secret123")

        with pytest.raises(AccountError):
            account_manager.create_account("hero", "bserver", "secret456")

    def test_create_with_explicit_id_is_respected(
        self, account_manager: AccountManager
    ) -> None:
        """显式 ID 应被采用。"""
        account = account_manager.create_account(
            "hero", "official", "secret123", account_id=VALID_ID
        )

        assert account.id == VALID_ID


@pytest.mark.unit
class TestQuery:
    """账号查询。"""

    def test_list_accounts_returns_all_created(
        self, account_manager: AccountManager
    ) -> None:
        """新增的账号应全部出现在列表中。"""
        account_manager.create_account("hero", "official", "secret123")
        account_manager.create_account("mage", "bserver", "secret456")

        assert len(account_manager.list_accounts()) == 2

    def test_list_accounts_filters_by_server(
        self, account_manager: AccountManager
    ) -> None:
        """按渠道服过滤只返回匹配项。"""
        account_manager.create_account("hero", "official", "secret123")
        account_manager.create_account("mage", "bserver", "secret456")

        assert [a.username for a in account_manager.list_accounts("bserver")] == [
            "mage"
        ]

    def test_get_account_returns_none_for_unknown(
        self, account_manager: AccountManager
    ) -> None:
        """未知 ID 返回 ``None``。"""
        assert account_manager.get_account("nope") is None

    def test_find_by_username_returns_match(
        self, account_manager: AccountManager
    ) -> None:
        """按用户名可查到账号。"""
        created = account_manager.create_account("hero", "official", "secret123")

        assert account_manager.find_by_username("hero").id == created.id

    def test_find_by_username_returns_none_when_absent(
        self, account_manager: AccountManager
    ) -> None:
        """用户名不存在时返回 ``None``。"""
        assert account_manager.find_by_username("ghost") is None


@pytest.mark.unit
class TestUpdateAccount:
    """账号字段更新与密码重设。"""

    def test_update_account_changes_username(
        self, account_manager: AccountManager
    ) -> None:
        """更新用户名后应持久化到配置。"""
        account = account_manager.create_account("hero", "official", "secret123")

        assert account_manager.update_account(account.id, username="hero2") is True
        assert account_manager.get_account(account.id).username == "hero2"

    def test_update_unknown_account_returns_false(
        self, account_manager: AccountManager
    ) -> None:
        """更新不存在的账号返回 ``False``。"""
        assert account_manager.update_account("nope", username="hero2") is False

    def test_update_with_illegal_username_raises_validation_error(
        self, account_manager: AccountManager
    ) -> None:
        """非法用户名应抛出校验异常。"""
        account = account_manager.create_account("hero", "official", "secret123")

        with pytest.raises(ValidationError):
            account_manager.update_account(account.id, username="bad name")

    def test_update_with_invalid_field_raises_account_error(
        self, account_manager: AccountManager
    ) -> None:
        """无法通过模型校验的字段应抛出 :class:`AccountError`。"""
        account = account_manager.create_account("hero", "official", "secret123")

        with pytest.raises(AccountError):
            account_manager.update_account(account.id, is_current=object())

    def test_set_password_refreshes_hash_and_ciphertext(
        self, account_manager: AccountManager
    ) -> None:
        """重设密码后旧密码失效、新密码生效。"""
        account = account_manager.create_account("hero", "official", "secret123")

        account_manager.set_password(account.id, "brandnew1")

        assert account_manager.authenticate("hero", "brandnew1") is not None
        assert account_manager.authenticate("hero", "secret123") is None

    def test_set_password_with_short_value_raises_validation_error(
        self, account_manager: AccountManager
    ) -> None:
        """过短的新密码应被拒绝。"""
        account = account_manager.create_account("hero", "official", "secret123")

        with pytest.raises(ValidationError):
            account_manager.set_password(account.id, "123")


@pytest.mark.unit
class TestRemoveAndSwitch:
    """删除、切换与当前账号。"""

    def test_remove_account_returns_true_then_false(
        self, account_manager: AccountManager
    ) -> None:
        """删除返回布尔结果。"""
        account = account_manager.create_account("hero", "official", "secret123")

        assert account_manager.remove_account(account.id) is True
        assert account_manager.remove_account(account.id) is False

    def test_switch_account_marks_current_and_last_login(
        self, account_manager: AccountManager
    ) -> None:
        """切换后应设置当前账号与最后登录时间。"""
        account = account_manager.create_account("hero", "official", "secret123")

        assert account_manager.switch_account(account.id) is True
        current = account_manager.get_current_account()
        assert current.id == account.id
        assert current.last_login is not None

    def test_switch_unknown_account_returns_false(
        self, account_manager: AccountManager
    ) -> None:
        """未知账号切换失败。"""
        assert account_manager.switch_account("nope") is False

    def test_get_current_account_returns_none_initially(
        self, account_manager: AccountManager
    ) -> None:
        """初始没有当前账号。"""
        assert account_manager.get_current_account() is None


@pytest.mark.unit
class TestPasswordRecovery:
    """``get_password`` 的解密行为。"""

    def test_get_password_roundtrips_and_verifies(
        self, account_manager: AccountManager
    ) -> None:
        """密文可还原为原始明文。"""
        account = account_manager.create_account("hero", "official", "secret123")

        assert account_manager.get_password(account.id) == "secret123"

    def test_get_password_for_unknown_account_raises(
        self, account_manager: AccountManager
    ) -> None:
        """未知账号应抛出 :class:`AccountError`。"""
        with pytest.raises(AccountError):
            account_manager.get_password("nope")

    def test_get_password_without_ciphertext_raises(
        self, account_manager: AccountManager, config_manager: ConfigManager
    ) -> None:
        """缺少密文时应抛出 :class:`AccountError`。"""
        account = account_manager.create_account("hero", "official", "secret123")
        stored = config_manager.get_account_config(account.id)
        stored.encrypted_password = ""
        config_manager.save_account(stored)

        with pytest.raises(AccountError):
            account_manager.get_password(account.id)

    def test_get_password_with_tampered_ciphertext_raises(
        self, account_manager: AccountManager, config_manager: ConfigManager
    ) -> None:
        """密文被篡改时应抛出 :class:`AccountError`。"""
        account = account_manager.create_account("hero", "official", "secret123")
        stored = config_manager.get_account_config(account.id)
        stored.encrypted_password = "not-a-valid-token"
        config_manager.save_account(stored)

        with pytest.raises(AccountError):
            account_manager.get_password(account.id)


@pytest.mark.unit
class TestAuthenticate:
    """``authenticate`` 的身份校验。"""

    def test_authenticate_with_correct_password_returns_account(
        self, account_manager: AccountManager
    ) -> None:
        """正确密码返回对应账号。"""
        account_manager.create_account("hero", "official", "secret123")

        assert account_manager.authenticate("hero", "secret123") is not None

    def test_authenticate_with_wrong_password_returns_none(
        self, account_manager: AccountManager
    ) -> None:
        """错误密码返回 ``None``。"""
        account_manager.create_account("hero", "official", "secret123")

        assert account_manager.authenticate("hero", "wrongpass") is None

    def test_authenticate_with_unknown_username_returns_none(
        self, account_manager: AccountManager
    ) -> None:
        """未知用户名返回 ``None``。"""
        assert account_manager.authenticate("ghost", "secret123") is None

    def test_authenticate_without_hash_returns_none(
        self, account_manager: AccountManager, config_manager: ConfigManager
    ) -> None:
        """缺少密码哈希时无法校验，返回 ``None``。"""
        account = account_manager.create_account("hero", "official", "secret123")
        stored = config_manager.get_account_config(account.id)
        stored.password_hash = ""
        config_manager.save_account(stored)

        assert account_manager.authenticate("hero", "secret123") is None


@pytest.mark.unit
class TestLogin:
    """``login`` 与 ``simulate_login``。"""

    def test_login_with_valid_account_succeeds(
        self, account_manager: AccountManager
    ) -> None:
        """合法账号登录应返回成功结果并刷新最后登录。"""
        account = account_manager.create_account("hero", "official", "secret123")

        result = account_manager.login(account.id)

        assert result.success is True
        assert result.username == "hero"
        assert result.server == "official"
        assert account_manager.get_account(account.id).last_login is not None

    def test_login_with_unknown_account_reports_failure(
        self, account_manager: AccountManager
    ) -> None:
        """未知账号登录失败并给出原因。"""
        result = account_manager.login("nope")

        assert result.success is False
        assert result.message == "账号不存在"

    def test_login_with_unknown_server_reports_failure(
        self, account_manager: AccountManager
    ) -> None:
        """目标渠道服不存在时登录失败。"""
        account = account_manager.create_account("hero", "official", "secret123")

        result = account_manager.login(account.id, server="nope")

        assert result.success is False
        assert "渠道服不存在" in result.message

    def test_login_with_explicit_server_switches_account(
        self, account_manager: AccountManager
    ) -> None:
        """指定渠道服登录后账号应绑定到该渠道服。"""
        account = account_manager.create_account("hero", "official", "secret123")

        result = account_manager.login(account.id, server="bserver")

        assert result.success is True
        assert account_manager.get_account(account.id).server == "bserver"

    def test_simulate_login_delegates_to_login(
        self, account_manager: AccountManager
    ) -> None:
        """``simulate_login`` 应复用 ``login`` 的逻辑。"""
        account = account_manager.create_account("hero", "official", "secret123")

        result = account_manager.simulate_login(account)

        assert result.success is True
        assert result.account_id == account.id

"""Test cho gui.model.account_prompt.AccountPrompt."""

from gui.model.account_prompt import AccountPrompt


def test_open_as_guest_starts_with_empty_username_field() -> None:
    prompt = AccountPrompt()
    prompt.open(None)
    assert prompt.is_open and prompt.username == "" and prompt.active_field == 0
    assert "guest" in prompt.info


def test_open_with_a_user_prefills_name_and_focuses_password() -> None:
    prompt = AccountPrompt()
    prompt.open("an")
    assert prompt.username == "an" and prompt.active_field == 1


def test_type_char_accepts_letters_digits_underscore_dash() -> None:
    prompt = AccountPrompt()
    prompt.open(None)
    for ch in "a_b-1":
        prompt.type_char(ch)
    assert prompt.username == "a_b-1"


def test_type_char_ignores_symbols_and_multi_character_input() -> None:
    prompt = AccountPrompt()
    prompt.open(None)
    for ch in ["!", " ", "ab", ""]:
        prompt.type_char(ch)
    assert prompt.username == ""


def test_each_field_respects_max_length() -> None:
    prompt = AccountPrompt(max_length=3)
    prompt.open(None)
    for ch in "abcdef":
        prompt.type_char(ch)
    prompt.switch_field()
    for ch in "123456":
        prompt.type_char(ch)
    assert (prompt.username, prompt.password) == ("abc", "123")


def test_switch_field_toggles_and_clears_error() -> None:
    prompt = AccountPrompt()
    prompt.open(None)
    prompt.fail("lỗi")
    prompt.switch_field()
    assert prompt.active_field == 1 and prompt.error == ""
    prompt.switch_field()
    assert prompt.active_field == 0


def test_backspace_edits_only_the_active_field() -> None:
    prompt = AccountPrompt()
    prompt.open(None)
    prompt.type_char("a")
    prompt.type_char("b")
    prompt.switch_field()
    prompt.type_char("x")
    prompt.backspace()
    prompt.backspace()  # ô mật khẩu đã rỗng, không lỗi
    prompt.switch_field()
    prompt.backspace()
    assert (prompt.username, prompt.password) == ("a", "")


def test_fail_sets_error_and_typing_clears_it() -> None:
    prompt = AccountPrompt()
    prompt.open(None)
    prompt.fail("Sai mật khẩu")
    assert prompt.error == "Sai mật khẩu"
    prompt.type_char("a")
    assert prompt.error == ""


def test_close_hides_and_wipes_the_password() -> None:
    prompt = AccountPrompt()
    prompt.open("an")
    prompt.type_char("x")
    prompt.close()
    assert not prompt.is_open and prompt.password == ""

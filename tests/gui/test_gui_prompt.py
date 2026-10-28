import pygame

from gui.model.passcode_prompt import PasscodePrompt, digit_from_key


def test_digit_from_key_uses_the_real_character_first():
    assert (
        digit_from_key(pygame.K_a, "7") == "7"
    )  # bố cục AZERTY: phím hàng số sinh ra ký tự khác
    assert digit_from_key(pygame.K_5) == "5"
    assert digit_from_key(pygame.K_KP3) == "3"
    assert digit_from_key(pygame.K_KP0) == "0"


def test_digit_from_key_rejects_everything_else():
    assert digit_from_key(pygame.K_a, "a") is None
    assert digit_from_key(pygame.K_RETURN) is None
    assert digit_from_key(0, "٣") is None  # chữ số không phải ASCII


def test_every_digit_key_and_keypad_key_maps_to_its_digit():
    top_row = [
        pygame.K_0,
        pygame.K_1,
        pygame.K_2,
        pygame.K_3,
        pygame.K_4,
        pygame.K_5,
        pygame.K_6,
        pygame.K_7,
        pygame.K_8,
        pygame.K_9,
    ]
    keypad = [
        pygame.K_KP0,
        pygame.K_KP1,
        pygame.K_KP2,
        pygame.K_KP3,
        pygame.K_KP4,
        pygame.K_KP5,
        pygame.K_KP6,
        pygame.K_KP7,
        pygame.K_KP8,
        pygame.K_KP9,
    ]
    for i in range(10):
        assert digit_from_key(top_row[i]) == str(i)
        assert digit_from_key(keypad[i]) == str(i)


def test_prompt_accepts_only_digits_up_to_max_length():
    prompt = PasscodePrompt(max_length=6)
    prompt.open(4, "Stage 05")
    for ch in "12a3 456789":
        prompt.type_digit(ch)
    assert prompt.text == "123456"
    assert prompt.is_open and prompt.target == 4 and prompt.title == "Stage 05"


def test_backspace_and_fail_clear_text_and_errors():
    prompt = PasscodePrompt()
    prompt.open(1, "Stage 02")
    prompt.type_digit("1")
    prompt.type_digit("2")
    prompt.backspace()
    assert prompt.text == "1"
    prompt.backspace()
    prompt.backspace()
    assert prompt.text == ""
    prompt.type_digit("9")
    prompt.fail("Sai mật khẩu")
    assert prompt.text == "" and prompt.error == "Sai mật khẩu"
    prompt.type_digit("3")
    assert prompt.error == "" and prompt.text == "3"


def test_open_resets_previous_input_and_close_hides():
    prompt = PasscodePrompt()
    prompt.open(1, "Stage 02")
    prompt.type_digit("7")
    prompt.fail("Sai mật khẩu")
    prompt.open(2, "Stage 03")
    assert prompt.text == "" and prompt.error == "" and prompt.target == 2
    prompt.close()
    assert not prompt.is_open


def test_multi_character_input_is_ignored():
    prompt = PasscodePrompt()
    prompt.open(0, "x")
    prompt.type_digit("12")
    prompt.type_digit("")
    assert prompt.text == ""

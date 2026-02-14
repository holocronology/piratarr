"""Tests for the pirate speak translation engine."""

from piratarr.translator import translate


def test_basic_word_substitution():
    result = translate("hello friend", seed=0)
    assert "ahoy" in result.lower()
    assert "matey" in result.lower()


def test_yes_no_translation():
    assert "aye" in translate("yes", seed=0).lower()
    assert "nay" in translate("no", seed=0).lower()


def test_pronoun_substitution():
    result = translate("my your you", seed=0)
    assert "me" in result.lower()
    assert "yer" in result.lower()
    assert "ye" in result.lower()


def test_phrase_substitution():
    result = translate("I am here", seed=0)
    assert "I be" in result


def test_are_you_phrase():
    result = translate("are you ready", seed=0)
    assert "be ye" in result.lower()


def test_preserves_capitalization():
    result = translate("Hello", seed=0)
    assert result[0].isupper()


def test_empty_string():
    assert translate("", seed=0) == ""


def test_preserves_punctuation():
    result = translate("hello!", seed=0)
    assert "!" in result


def test_money_translation():
    result = translate("I need money", seed=0)
    assert "doubloons" in result.lower()


def test_seed_reproducibility():
    text = "Hello my friend, how are you doing today?"
    result1 = translate(text, seed=42)
    result2 = translate(text, seed=42)
    assert result1 == result2


def test_food_translation():
    result = translate("let us eat food", seed=0)
    assert "grub" in result.lower()


def test_multiline_text():
    text = "Hello friend.\nHow are you?"
    result = translate(text, seed=0)
    assert "\n" in result

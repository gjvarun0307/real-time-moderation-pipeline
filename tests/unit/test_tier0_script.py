from classifier.tier0.script import detect_dominant_script


def test_pure_latin():
    assert detect_dominant_script("hello world") == "latin"


def test_pure_cyrillic():
    assert detect_dominant_script("привет мир") == "cyrillic"


def test_pure_greek():
    assert detect_dominant_script("γεια σου") == "greek"


def test_pure_japanese_hiragana_and_kanji():
    assert detect_dominant_script("おはようございます") == "cjk"


def test_mixed_script_picks_the_plurality():
    # mostly Latin with one stray Cyrillic character
    assert detect_dominant_script("hello wоrld hello world") == "latin"


def test_empty_text_is_other():
    assert detect_dominant_script("") == "other"


def test_no_alphabetic_characters_is_other():
    assert detect_dominant_script("123 !!! 🎉") == "other"

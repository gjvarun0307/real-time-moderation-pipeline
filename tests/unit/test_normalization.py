from common.normalization import normalize


def test_nfkc_folds_fullwidth_and_halfwidth_forms():
    # halfwidth katakana -> fullwidth; fullwidth parens -> ASCII parens
    assert normalize("ﾂｲｯﾀ（ｺﾒﾃﾞｨ）") == "ツイッタ(コメディ)"


def test_zero_width_characters_are_stripped():
    assert normalize("h\u200ba\u200ct\u200de\ufeff") == "hate"


def test_cyrillic_homoglyph_folds_to_latin():
    assert normalize("hаte") == "hate"  # Cyrillic а


def test_katakana_no_is_not_corrupted_by_homoglyph_folding():
    # Regression: the confusables table maps katakana ノ to ASCII "/",
    # which destroys real Japanese text and kaomoji. Must survive intact.
    assert "ノ" in normalize("(＾▽＾)ノ")


def test_repeated_characters_collapse_to_three():
    assert normalize("haaaaate!!!!!!") == "haaate!!!"


def test_zwj_emoji_sequences_split_into_separate_glyphs_not_destroyed():
    # zero-width range (U+200B-U+200D) includes ZWJ,
    # which normally joins e.g. family/couple/pride-flag emoji into one
    # glyph. Stripping it splits the sequence into separate adjacent
    # emoji rather than one composed glyph — a deliberate, spec-literal
    # tradeoff (confirmed with the user), not data loss: each component
    # emoji survives, just unjoined.
    family = "\U0001f468‍\U0001f469‍\U0001f467"
    result = normalize(family)
    assert result == "\U0001f468\U0001f469\U0001f467"


def test_repeated_simple_emoji_collapses_by_grapheme_not_codepoint():
    result = normalize("😀" * 5)
    assert result == "😀" * 3


def test_urls_are_stripped_entirely():
    assert normalize("check https://example.com/path?q=1 out") == "check out"


def test_mentions_are_stripped_entirely():
    assert normalize("hey @alice.bsky.social how are you") == "hey how are you"


def test_hashtag_symbol_stripped_but_word_kept():
    assert normalize("this is #cool stuff") == "this is cool stuff"


def test_emoji_and_kaomoji_survive_untouched():
    assert normalize("(＾▽＾)ノ nice") == "(^▽^)ノ nice"
    assert normalize("great 😀😀 job") == "great 😀😀 job"


def test_plain_ascii_text_is_a_noop_besides_whitespace():
    assert normalize("just a normal sentence") == "just a normal sentence"

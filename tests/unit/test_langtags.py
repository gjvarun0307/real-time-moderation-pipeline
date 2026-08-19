from common.langtags import canonicalize_lang, canonicalize_langs


def test_regional_variants_collapse_to_primary_subtag():
    assert canonicalize_lang("ja-JP") == "ja"
    assert canonicalize_lang("en-US") == "en"
    assert canonicalize_lang("en-GB") == "en"


def test_iso_639_3_maps_to_639_1_when_it_exists():
    assert canonicalize_lang("cat") == "ca"
    assert canonicalize_lang("ca") == "ca"


def test_case_is_normalized():
    assert canonicalize_lang("JA") == "ja"
    assert canonicalize_lang("Ja-JP") == "ja"


def test_639_3_only_language_has_no_639_1_to_fall_back_to():
    # Yue Chinese has no ISO 639-1 code at all
    assert canonicalize_lang("yue") == "yue"


def test_unknown_tag_passes_through_rather_than_crashing():
    assert canonicalize_lang("xx-YY") == "xx"
    assert canonicalize_lang("") == ""


def test_canonicalize_langs_dedupes_after_canonicalization():
    assert canonicalize_langs(["en-US", "en-GB"]) == ["en"]


def test_canonicalize_langs_preserves_order_of_first_occurrence():
    assert canonicalize_langs(["ja", "en", "ja-JP"]) == ["ja", "en"]


def test_canonicalize_langs_handles_none_and_empty():
    assert canonicalize_langs(None) == []
    assert canonicalize_langs([]) == []

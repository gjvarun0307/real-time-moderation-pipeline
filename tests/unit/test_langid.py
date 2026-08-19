from pathlib import Path

import pytest

from common.metrics import ingest_lang_disagreement_total
from ingest.langid import DEFAULT_MODEL_PATH, LanguageIdentifier, record_disagreement

pytestmark = pytest.mark.skipif(
    not Path(DEFAULT_MODEL_PATH).exists(),
    reason="fastText model not downloaded — run scripts/download_fasttext_model.sh",
)


@pytest.fixture(scope="module")
def identifier() -> LanguageIdentifier:
    return LanguageIdentifier()


def test_predicts_clear_english_with_high_confidence(identifier: LanguageIdentifier):
    lang, conf = identifier.predict(
        "This is a completely ordinary English sentence about the weather today."
    )
    assert lang == "en"
    assert conf > 0.8


def test_predicts_clear_japanese_with_high_confidence(identifier: LanguageIdentifier):
    lang, conf = identifier.predict(
        "今日はとても良い天気です。散歩に出かけようと思っています。公園には桜が咲いていました。"
    )
    assert lang == "ja"
    assert conf > 0.8


def test_predict_canonicalizes_output_label(identifier: LanguageIdentifier):
    # fastText's raw labels come out as "__label__xx" — predict() should
    # already strip and canonicalize, never leak the raw label format.
    lang, _ = identifier.predict("Bonjour tout le monde, comment allez-vous ?")
    assert lang == "fr"
    assert not lang.startswith("__label__")


def test_predict_on_empty_text_does_not_raise(identifier: LanguageIdentifier):
    _lang, conf = identifier.predict("")
    assert 0.0 <= conf <= 1.0


def _counter_value(declared: str, predicted: str) -> float:
    metric = ingest_lang_disagreement_total.labels(declared=declared, predicted=predicted)
    return metric._value.get()


def test_record_disagreement_increments_on_mismatch():
    before = _counter_value("fr", "en")
    record_disagreement(["fr"], "en")
    assert _counter_value("fr", "en") == before + 1


def test_record_disagreement_does_not_increment_on_agreement():
    before = _counter_value("ja", "ja")
    record_disagreement(["ja"], "ja")
    assert _counter_value("ja", "ja") == before


def test_record_disagreement_missing_declared_uses_missing_label():
    before = _counter_value("missing", "es")
    record_disagreement([], "es")
    assert _counter_value("missing", "es") == before + 1

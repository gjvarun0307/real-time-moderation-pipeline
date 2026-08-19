"""fastText language identification.
"""

from pathlib import Path

import fasttext

from common.langtags import canonicalize_lang
from common.metrics import ingest_lang_disagreement_total

DEFAULT_MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "fasttext" / "lid.176.ftz"


class LanguageIdentifier:
    def __init__(self, model_path: Path | str = DEFAULT_MODEL_PATH) -> None:
        self._model = fasttext.load_model(str(model_path))

    def predict(self, text: str) -> tuple[str, float]:
        line = text.replace("\n", " ").replace("\r", " ") + "\n"
        predictions = self._model.f.predict(line, 1, 0.0, "strict")
        if not predictions:
            return "", 0.0
        prob, label = predictions[0]
        raw_lang = label.removeprefix("__label__")
        return canonicalize_lang(raw_lang), float(prob)


def record_disagreement(declared: list[str], predicted: str) -> None:
    declared_label = declared[0] if declared else "missing"
    if declared_label != predicted:
        ingest_lang_disagreement_total.labels(declared=declared_label, predicted=predicted).inc()

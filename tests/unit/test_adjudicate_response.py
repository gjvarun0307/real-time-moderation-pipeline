import pytest
from pydantic import ValidationError

from common.schemas import AdjudicateResponse


def _valid(**overrides) -> dict:
    defaults = {
        "decision": "ALLOW",
        "score_toxic": 0.1,
        "score_severe": 0.1,
        "score_obscene": 0.1,
        "score_threat": 0.1,
        "score_insult": 0.1,
        "score_identity": 0.1,
        "rationale": "civil disagreement, no toxicity",
    }
    defaults.update(overrides)
    return defaults


def test_valid_response_parses():
    response = AdjudicateResponse.model_validate(_valid())
    assert response.decision == "ALLOW"
    assert response.score_toxic == 0.1


def test_score_above_one_is_rejected():
    with pytest.raises(ValidationError):
        AdjudicateResponse.model_validate(_valid(score_toxic=1.5))


def test_score_below_zero_is_rejected():
    with pytest.raises(ValidationError):
        AdjudicateResponse.model_validate(_valid(score_threat=-0.1))


def test_invalid_decision_literal_is_rejected():
    with pytest.raises(ValidationError):
        AdjudicateResponse.model_validate(_valid(decision="MAYBE"))


def test_missing_field_is_rejected():
    data = _valid()
    del data["rationale"]
    with pytest.raises(ValidationError):
        AdjudicateResponse.model_validate(data)


def test_boundary_scores_zero_and_one_are_valid():
    response = AdjudicateResponse.model_validate(_valid(score_obscene=0.0, score_insult=1.0))
    assert response.score_obscene == 0.0
    assert response.score_insult == 1.0

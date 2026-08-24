from classifier.budget_guard import BudgetDecision
from classifier.decision import decide, resolve_thresholds
from classifier.tier0.lexicon import Lexicon, LexiconEntry
from classifier.tier1.model import Tier1Result
from common.config import ClassifierSettings
from common.schemas import EscalateMessage, PostsRawMessage, Verdict

_EN_LEXICON = Lexicon(
    lang="en",
    match_mode="word",
    entries=[LexiconEntry(id="en-block-001", term="badword", type="hard_block", notes="")],
)


def _message(
    text: str = "hello world this is a longer ordinary post",
    lang_predicted: str = "en",
    post_id: str = "msg-1",
) -> PostsRawMessage:
    return PostsRawMessage(
        id=post_id,
        post_uri="at://did:plc:abc/app.bsky.feed.post/xyz",
        author_hash="a" * 32,
        text=text,
        text_normalized=text,
        lang_declared=lang_predicted,
        lang_declared_raw=lang_predicted,
        lang_predicted=lang_predicted,
        lang_confidence=0.9,
        event_time_us=1_000_000,
        ingest_time_us=1_000_100,
        char_len=len(text),
        has_emoji=False,
        source="live",
    )


def _settings(**overrides) -> ClassifierSettings:
    defaults = {"database_url": "postgresql://fake/db", "r2_secret_access_key": "fake"}
    defaults.update(overrides)
    return ClassifierSettings(**defaults)


class FakeTier1:
    def __init__(self, toxic_score: float, other_scores: float = 0.01) -> None:
        self.model_version = "tier1-onnx-fake"
        self._toxic_score = toxic_score
        self._other = other_scores
        self.calls: list[str] = []

    def infer(self, text: str) -> Tier1Result:
        self.calls.append(text)
        return Tier1Result(
            scores={
                "toxic": self._toxic_score,
                "severe_toxic": self._other,
                "obscene": self._other,
                "threat": self._other,
                "insult": self._other,
                "identity_hate": self._other,
            },
            seq_len=10,
        )


class FakeBudgetGuard:
    def __init__(self, escalate: bool) -> None:
        self._escalate = escalate
        self.decide_calls: list[str] = []

    async def decide(self, post_id: str, now=None) -> BudgetDecision:
        self.decide_calls.append(post_id)
        return BudgetDecision(escalate=self._escalate, budget_exhausted=False)


def test_resolve_thresholds_falls_back_to_global_defaults():
    settings = _settings()
    thresholds = resolve_thresholds("en", settings)
    assert thresholds.tau_lo == settings.tau_lo
    assert thresholds.tau_hi == settings.tau_hi
    assert thresholds.tau_mid == settings.tau_mid


def test_resolve_thresholds_uses_per_language_override():
    settings = _settings(lang_threshold_overrides={"ja": {"tau_lo": 0.05}})
    thresholds = resolve_thresholds("ja", settings)
    assert thresholds.tau_lo == 0.05
    assert thresholds.tau_hi == settings.tau_hi  # unset keys fall back to global


async def test_tier0_hard_block_short_circuits_before_tier1_is_called():
    message = _message(text="that is a badword right there")
    tier1 = FakeTier1(toxic_score=0.5)

    result = await decide(
        message,
        lexicons={"en": _EN_LEXICON},
        tier1=tier1,
        budget_guard=FakeBudgetGuard(escalate=False),
        settings=_settings(),
    )

    assert isinstance(result, Verdict)
    assert result.decision == "BLOCK"
    assert result.resolved_tier == 0
    assert tier1.calls == []


async def test_tier0_hard_allow_short_circuits():
    message = _message(text="ok")

    result = await decide(
        message,
        lexicons={},
        tier1=FakeTier1(toxic_score=0.9),
        budget_guard=FakeBudgetGuard(escalate=False),
        settings=_settings(),
    )

    assert isinstance(result, Verdict)
    assert result.decision == "ALLOW"
    assert result.resolved_tier == 0


async def test_tier1_low_score_allows_without_consulting_budget_guard():
    message = _message()
    budget_guard = FakeBudgetGuard(escalate=True)

    result = await decide(
        message,
        lexicons={},
        tier1=FakeTier1(toxic_score=0.05),
        budget_guard=budget_guard,
        settings=_settings(),
    )

    assert isinstance(result, Verdict)
    assert result.decision == "ALLOW"
    assert result.resolved_tier == 1
    assert result.score_toxic == 0.05
    assert budget_guard.decide_calls == []


async def test_tier1_high_score_blocks_without_consulting_budget_guard():
    message = _message()
    budget_guard = FakeBudgetGuard(escalate=True)

    result = await decide(
        message,
        lexicons={},
        tier1=FakeTier1(toxic_score=0.95),
        budget_guard=budget_guard,
        settings=_settings(),
    )

    assert isinstance(result, Verdict)
    assert result.decision == "BLOCK"
    assert result.resolved_tier == 1
    assert budget_guard.decide_calls == []


async def test_escalation_band_with_budget_available_produces_escalate_message():
    message = _message(post_id="msg-escalate")

    result = await decide(
        message,
        lexicons={},
        tier1=FakeTier1(toxic_score=0.5),
        budget_guard=FakeBudgetGuard(escalate=True),
        settings=_settings(),
    )

    assert isinstance(result, EscalateMessage)
    assert result.tier1_score_toxic == 0.5
    assert result.text == message.text
    assert result.tier1_model_version == "tier1-onnx-fake"


async def test_escalation_band_sampled_out_above_tau_mid_blocks():
    message = _message()

    result = await decide(
        message,
        lexicons={},
        tier1=FakeTier1(toxic_score=0.6),  # > default tau_mid of 0.5
        budget_guard=FakeBudgetGuard(escalate=False),
        settings=_settings(),
    )

    assert isinstance(result, Verdict)
    assert result.decision == "BLOCK"
    assert result.resolved_tier == 1
    assert result.low_confidence is True
    assert result.escalation_sampled_out is True


async def test_escalation_band_sampled_out_below_tau_mid_allows():
    message = _message()

    result = await decide(
        message,
        lexicons={},
        tier1=FakeTier1(toxic_score=0.4),  # < default tau_mid of 0.5
        budget_guard=FakeBudgetGuard(escalate=False),
        settings=_settings(),
    )

    assert isinstance(result, Verdict)
    assert result.decision == "ALLOW"
    assert result.resolved_tier == 1
    assert result.low_confidence is True
    assert result.escalation_sampled_out is True

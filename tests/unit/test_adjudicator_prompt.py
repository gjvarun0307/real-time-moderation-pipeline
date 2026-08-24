from pathlib import Path

from adjudicator.prompt import PROMPT_VERSION, PromptBuilder
from common.schemas import EscalateMessage

_TEMPLATE = "lang={lang} text={text} score={tier1_score_toxic} literal={{not a slot}}"


def _message(text: str = "hello world", lang_predicted: str = "en") -> EscalateMessage:
    return EscalateMessage(
        id="01a01982-4c32-7782-9857-43f3fff3a7ec",
        post_uri="at://did:plc:abc/app.bsky.feed.post/xyz",
        author_hash="a" * 32,
        text=text,
        text_normalized=text,
        lang_predicted=lang_predicted,
        lang_declared=lang_predicted,
        lang_confidence=0.9,
        tier1_score_toxic=0.5,
        tier1_model_version="tier1-onnx-fake",
        source="live",
        event_time_us=1,
        escalated_time_us=2,
    )


def test_build_substitutes_lang_text_and_score(tmp_path: Path):
    template_path = tmp_path / "adjudicate_v1.txt"
    template_path.write_text(_TEMPLATE, encoding="utf-8")
    builder = PromptBuilder(template_path)

    prompt = builder.build(_message(text="say hi", lang_predicted="en"))

    assert "lang=en" in prompt
    assert "text=say hi" in prompt
    assert "score=0.5" in prompt
    assert "literal={not a slot}" in prompt


def test_version_matches_constant(tmp_path: Path):
    template_path = tmp_path / "adjudicate_v1.txt"
    template_path.write_text(_TEMPLATE, encoding="utf-8")
    builder = PromptBuilder(template_path)

    assert builder.version == PROMPT_VERSION == "adjudicate_v1"


def test_build_repair_includes_base_prompt_and_error_context(tmp_path: Path):
    template_path = tmp_path / "adjudicate_v1.txt"
    template_path.write_text(_TEMPLATE, encoding="utf-8")
    builder = PromptBuilder(template_path)

    repair_prompt = builder.build_repair(_message(), "not json", "invalid literal")

    assert "lang=en" in repair_prompt  # base prompt still present
    assert "not json" in repair_prompt
    assert "invalid literal" in repair_prompt


def test_real_template_file_renders_without_error():
    real_path = (
        Path(__file__).resolve().parents[2] / "prompts" / "adjudicate_v1.txt"
    )
    builder = PromptBuilder(real_path)

    prompt = builder.build(_message())

    assert "hello world" in prompt
    assert '"decision"' in prompt

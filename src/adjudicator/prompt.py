"""Loading and rendering the versioned adjudication prompt template.
"""

from pathlib import Path

from common.schemas import EscalateMessage

PROMPT_VERSION = "adjudicate_v1"


class PromptBuilder:
    def __init__(self, template_path: Path) -> None:
        self._template = template_path.read_text(encoding="utf-8")

    @property
    def version(self) -> str:
        return PROMPT_VERSION

    def build(self, message: EscalateMessage) -> str:
        return self._template.format(
            lang=message.lang_predicted,
            text=message.text,
            tier1_score_toxic=message.tier1_score_toxic,
        )

    def build_repair(
        self, message: EscalateMessage, invalid_output: str, validation_error: str
    ) -> str:
        """Appends a repair instruction to the base prompt for the one
        allowed re-ask after a structured-output validation failure."""
        base = self.build(message)
        return (
            f"{base}\n\n"
            "--- Repair ---\n"
            "Your previous response did not match the required JSON schema.\n"
            f"Previous response: {invalid_output}\n"
            f"Validation error: {validation_error}\n"
            "Respond again with ONLY a valid JSON object matching the schema above."
        )

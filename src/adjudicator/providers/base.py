"""Common interface and exception hierarchy every LLM provider adapter
implements.
"""

from dataclasses import dataclass
from typing import Protocol


class ProviderError(Exception):
    """Base for every error a provider adapter can raise."""


class ProviderClientError(ProviderError):
    """4xx other than 429 — a bad request on our side. Never retried,
    never counted against the circuit breaker."""


class ProviderRateLimited(ProviderError):
    """429 — retryable, counts against the circuit breaker."""


class ProviderServerError(ProviderError):
    """5xx, timeout, or connection error — retryable, counts against the
    circuit breaker."""


@dataclass(frozen=True)
class AdjudicationUsage:
    prompt_tokens: int
    completion_tokens: int


@dataclass(frozen=True)
class ProviderResult:
    raw_text: str
    usage: AdjudicationUsage


class AdjudicationProvider(Protocol):
    name: str

    async def complete(self, *, prompt: str, timeout: float) -> ProviderResult: ...


def raise_for_status(status: int, body: str) -> None:
    """Maps an HTTP status code to the right ProviderError subclass, if any."""
    if status == 429:
        raise ProviderRateLimited(body)
    if 500 <= status:
        raise ProviderServerError(f"status={status} body={body}")
    if 400 <= status < 500:
        raise ProviderClientError(f"status={status} body={body}")

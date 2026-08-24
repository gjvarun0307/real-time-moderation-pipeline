"""Orchestrates one escalated post through provider failover, rate
limiting, circuit breaking, retry, and structured-output validation.
"""

import time
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import ValidationError

from adjudicator.circuit_breaker import CircuitBreaker
from adjudicator.prompt import PromptBuilder
from adjudicator.providers.base import (
    AdjudicationProvider,
    AdjudicationUsage,
    ProviderClientError,
    ProviderError,
    ProviderRateLimited,
    ProviderResult,
    ProviderServerError,
)
from adjudicator.retry import call_with_retry
from adjudicator.token_bucket import TokenBucket
from common.config import AdjudicatorSettings
from common.metrics import (
    adjudicator_cost_usd_total,
    adjudicator_latency_seconds,
    adjudicator_rate_limited_total,
    adjudicator_requests_total,
    adjudicator_validation_repair_total,
)
from common.schemas import AdjudicateResponse, EscalateMessage


@dataclass(frozen=True)
class AdjudicateOutcome:
    kind: Literal["verdict", "dlq"]
    response: AdjudicateResponse | None = None
    provider: str | None = None
    reason: str | None = None
    context: dict[str, Any] | None = None


class AdjudicatorClient:
    def __init__(
        self,
        providers: list[AdjudicationProvider],
        breakers: dict[str, CircuitBreaker],
        buckets: dict[str, TokenBucket],
        prompt_builder: PromptBuilder,
        settings: AdjudicatorSettings,
    ) -> None:
        self._providers = providers
        self._breakers = breakers
        self._buckets = buckets
        self._prompt_builder = prompt_builder
        self._settings = settings

    def _timeout_for(self, provider: AdjudicationProvider) -> float:
        return float(getattr(self._settings, f"{provider.name}_timeout_seconds"))

    def _record_cost(self, provider_name: str, usage: AdjudicationUsage) -> None:
        prompt_rate = getattr(self._settings, f"{provider_name}_cost_per_1k_prompt_tokens_usd")
        completion_rate = getattr(
            self._settings, f"{provider_name}_cost_per_1k_completion_tokens_usd"
        )
        cost = (usage.prompt_tokens / 1000) * prompt_rate
        cost += (usage.completion_tokens / 1000) * completion_rate
        adjudicator_cost_usd_total.labels(provider=provider_name).inc(cost)

    def _try_validate(self, raw_text: str) -> tuple[AdjudicateResponse | None, str | None]:
        try:
            return AdjudicateResponse.model_validate_json(raw_text), None
        except ValidationError as exc:
            return None, str(exc)

    async def _call(self, provider: AdjudicationProvider, prompt: str) -> ProviderResult:
        return await call_with_retry(
            lambda: provider.complete(prompt=prompt, timeout=self._timeout_for(provider)),
            max_retries=self._settings.retry_max,
            base_delay=self._settings.retry_base_delay_seconds,
            max_delay=self._settings.retry_max_delay_seconds,
        )

    async def adjudicate(self, message: EscalateMessage) -> AdjudicateOutcome:
        prompt = self._prompt_builder.build(message)

        for provider in self._providers:
            breaker = self._breakers[provider.name]
            if not breaker.allow_request(time.monotonic()):
                continue

            await self._buckets[provider.name].acquire()

            start = time.perf_counter()
            try:
                result = await self._call(provider, prompt)
            except ProviderClientError:
                adjudicator_latency_seconds.labels(provider=provider.name).observe(
                    time.perf_counter() - start
                )
                adjudicator_requests_total.labels(
                    provider=provider.name, outcome="client_error"
                ).inc()
                continue
            except ProviderRateLimited:
                adjudicator_latency_seconds.labels(provider=provider.name).observe(
                    time.perf_counter() - start
                )
                adjudicator_rate_limited_total.labels(provider=provider.name).inc()
                adjudicator_requests_total.labels(provider=provider.name, outcome="error").inc()
                breaker.record_failure(time.monotonic())
                continue
            except ProviderServerError:
                adjudicator_latency_seconds.labels(provider=provider.name).observe(
                    time.perf_counter() - start
                )
                adjudicator_requests_total.labels(provider=provider.name, outcome="error").inc()
                breaker.record_failure(time.monotonic())
                continue

            adjudicator_latency_seconds.labels(provider=provider.name).observe(
                time.perf_counter() - start
            )
            breaker.record_success()
            self._record_cost(provider.name, result.usage)

            validated, error = self._try_validate(result.raw_text)
            if validated is None:
                repair_prompt = self._prompt_builder.build_repair(
                    message, result.raw_text, error or "unknown validation error"
                )
                try:
                    repair_result = await provider.complete(
                        prompt=repair_prompt, timeout=self._timeout_for(provider)
                    )
                except ProviderError:
                    adjudicator_validation_repair_total.labels(outcome="call_failed").inc()
                    return AdjudicateOutcome(
                        kind="dlq",
                        reason="repair_call_failed",
                        context={"provider": provider.name},
                    )
                self._record_cost(provider.name, repair_result.usage)
                validated, _error = self._try_validate(repair_result.raw_text)
                if validated is None:
                    adjudicator_validation_repair_total.labels(outcome="still_invalid").inc()
                    return AdjudicateOutcome(
                        kind="dlq",
                        reason="validation_failed_after_repair",
                        context={"provider": provider.name},
                    )
                adjudicator_validation_repair_total.labels(outcome="fixed").inc()

            adjudicator_requests_total.labels(provider=provider.name, outcome="success").inc()
            return AdjudicateOutcome(kind="verdict", response=validated, provider=provider.name)

        return AdjudicateOutcome(kind="dlq", reason="all_providers_failed")

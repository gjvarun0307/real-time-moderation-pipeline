"""Groq adapter — OpenAI-compatible chat/completions endpoint.
"""

import aiohttp

from adjudicator.providers.base import (
    AdjudicationUsage,
    ProviderResult,
    ProviderServerError,
    raise_for_status,
)


class GroqProvider:
    name = "groq"

    def __init__(
        self, session: aiohttp.ClientSession, api_key: str, model: str, base_url: str
    ) -> None:
        self._session = session
        self._api_key = api_key
        self._model = model
        self._base_url = base_url

    async def complete(self, *, prompt: str, timeout: float) -> ProviderResult:
        body = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            # Explicit, not left to aiohttp's auto-negotiation: avoids
            # depending on a working Brotli decompressor being installed
            # (aiohttp advertises "br" whenever brotli/brotlicffi is
            # present, and a version mismatch there breaks decoding —
            # gzip is plenty for a small JSON payload).
            "Accept-Encoding": "gzip, deflate",
        }
        try:
            async with self._session.post(
                self._base_url,
                json=body,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as response:
                text = await response.text()
                raise_for_status(response.status, text)
                data = await response.json()
        except (TimeoutError, aiohttp.ClientError) as exc:
            raise ProviderServerError(str(exc)) from exc

        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        return ProviderResult(
            raw_text=content,
            usage=AdjudicationUsage(
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
            ),
        )

"""Gemini adapter — generateContent endpoint with JSON response mode.
"""

import aiohttp

from adjudicator.providers.base import (
    AdjudicationUsage,
    ProviderResult,
    ProviderServerError,
    raise_for_status,
)


class GeminiProvider:
    name = "gemini"

    def __init__(
        self, session: aiohttp.ClientSession, api_key: str, model: str, base_url: str
    ) -> None:
        self._session = session
        self._api_key = api_key
        self._model = model
        self._base_url = base_url

    async def complete(self, *, prompt: str, timeout: float) -> ProviderResult:
        url = f"{self._base_url}/{self._model}:generateContent?key={self._api_key}"
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        }
        # Explicit, not left to aiohttp's auto-negotiation — see groq.py's
        # comment on the same header.
        headers = {"Accept-Encoding": "gzip, deflate"}
        try:
            async with self._session.post(
                url, json=body, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout)
            ) as response:
                text = await response.text()
                raise_for_status(response.status, text)
                data = await response.json()
        except (TimeoutError, aiohttp.ClientError) as exc:
            raise ProviderServerError(str(exc)) from exc

        content = data["candidates"][0]["content"]["parts"][0]["text"]
        usage = data.get("usageMetadata", {})
        return ProviderResult(
            raw_text=content,
            usage=AdjudicationUsage(
                prompt_tokens=usage.get("promptTokenCount", 0),
                completion_tokens=usage.get("candidatesTokenCount", 0),
            ),
        )

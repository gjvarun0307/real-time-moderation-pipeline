import json

import aiohttp
import pytest

from adjudicator.providers.base import (
    ProviderClientError,
    ProviderRateLimited,
    ProviderServerError,
)
from adjudicator.providers.gemini import GeminiProvider
from adjudicator.providers.groq import GroqProvider


class FakeResponse:
    def __init__(self, status: int, json_body: dict | None = None) -> None:
        self.status = status
        self._json_body = json_body or {}

    async def text(self) -> str:
        return json.dumps(self._json_body)

    async def json(self) -> dict:
        return self._json_body

    async def __aenter__(self) -> "FakeResponse":
        return self

    async def __aexit__(self, *args) -> bool:
        return False


class FakeClientSession:
    def __init__(self, response: FakeResponse | None = None, raise_error: Exception | None = None):
        self._response = response
        self._raise_error = raise_error
        self.last_url: str | None = None
        self.last_kwargs: dict | None = None

    def post(self, url, **kwargs):
        self.last_url = url
        self.last_kwargs = kwargs
        if self._raise_error is not None:
            raise self._raise_error
        assert self._response is not None
        return self._response


# --- Groq ---

_GROQ_SUCCESS_BODY = {
    "choices": [{"message": {"content": '{"decision": "ALLOW"}'}}],
    "usage": {"prompt_tokens": 10, "completion_tokens": 5},
}


async def test_groq_parses_success_response():
    session = FakeClientSession(FakeResponse(200, _GROQ_SUCCESS_BODY))
    provider = GroqProvider(session, api_key="k", model="m", base_url="https://api.groq.com/x")

    result = await provider.complete(prompt="p", timeout=5.0)

    assert result.raw_text == '{"decision": "ALLOW"}'
    assert result.usage.prompt_tokens == 10
    assert result.usage.completion_tokens == 5


async def test_groq_sends_bearer_token_and_model():
    session = FakeClientSession(FakeResponse(200, _GROQ_SUCCESS_BODY))
    provider = GroqProvider(session, api_key="secret-key", model="m", base_url="https://x")

    await provider.complete(prompt="the prompt", timeout=5.0)

    assert session.last_kwargs["headers"]["Authorization"] == "Bearer secret-key"
    assert session.last_kwargs["json"]["model"] == "m"
    assert session.last_kwargs["json"]["messages"] == [{"role": "user", "content": "the prompt"}]


async def test_groq_pins_accept_encoding_to_avoid_brotli():
    session = FakeClientSession(FakeResponse(200, _GROQ_SUCCESS_BODY))
    provider = GroqProvider(session, api_key="k", model="m", base_url="https://x")

    await provider.complete(prompt="p", timeout=5.0)

    assert session.last_kwargs["headers"]["Accept-Encoding"] == "gzip, deflate"


async def test_groq_429_raises_rate_limited():
    session = FakeClientSession(FakeResponse(429))
    provider = GroqProvider(session, api_key="k", model="m", base_url="https://x")

    with pytest.raises(ProviderRateLimited):
        await provider.complete(prompt="p", timeout=5.0)


async def test_groq_400_raises_client_error():
    session = FakeClientSession(FakeResponse(400))
    provider = GroqProvider(session, api_key="k", model="m", base_url="https://x")

    with pytest.raises(ProviderClientError):
        await provider.complete(prompt="p", timeout=5.0)


async def test_groq_500_raises_server_error():
    session = FakeClientSession(FakeResponse(500))
    provider = GroqProvider(session, api_key="k", model="m", base_url="https://x")

    with pytest.raises(ProviderServerError):
        await provider.complete(prompt="p", timeout=5.0)


async def test_groq_connection_error_raises_server_error():
    session = FakeClientSession(raise_error=aiohttp.ClientConnectionError("boom"))
    provider = GroqProvider(session, api_key="k", model="m", base_url="https://x")

    with pytest.raises(ProviderServerError):
        await provider.complete(prompt="p", timeout=5.0)


# --- Gemini ---

_GEMINI_SUCCESS_BODY = {
    "candidates": [{"content": {"parts": [{"text": '{"decision": "BLOCK"}'}]}}],
    "usageMetadata": {"promptTokenCount": 20, "candidatesTokenCount": 8},
}


async def test_gemini_parses_success_response():
    session = FakeClientSession(FakeResponse(200, _GEMINI_SUCCESS_BODY))
    provider = GeminiProvider(session, api_key="k", model="m", base_url="https://gemini.x/models")

    result = await provider.complete(prompt="p", timeout=5.0)

    assert result.raw_text == '{"decision": "BLOCK"}'
    assert result.usage.prompt_tokens == 20
    assert result.usage.completion_tokens == 8


async def test_gemini_url_includes_model_and_api_key():
    session = FakeClientSession(FakeResponse(200, _GEMINI_SUCCESS_BODY))
    provider = GeminiProvider(session, api_key="secret", model="my-model", base_url="https://gemini.x")

    await provider.complete(prompt="p", timeout=5.0)

    assert session.last_url == "https://gemini.x/my-model:generateContent?key=secret"


async def test_gemini_pins_accept_encoding_to_avoid_brotli():
    session = FakeClientSession(FakeResponse(200, _GEMINI_SUCCESS_BODY))
    provider = GeminiProvider(session, api_key="k", model="m", base_url="https://x")

    await provider.complete(prompt="p", timeout=5.0)

    assert session.last_kwargs["headers"]["Accept-Encoding"] == "gzip, deflate"


async def test_gemini_429_raises_rate_limited():
    session = FakeClientSession(FakeResponse(429))
    provider = GeminiProvider(session, api_key="k", model="m", base_url="https://x")

    with pytest.raises(ProviderRateLimited):
        await provider.complete(prompt="p", timeout=5.0)


async def test_gemini_500_raises_server_error():
    session = FakeClientSession(FakeResponse(500))
    provider = GeminiProvider(session, api_key="k", model="m", base_url="https://x")

    with pytest.raises(ProviderServerError):
        await provider.complete(prompt="p", timeout=5.0)

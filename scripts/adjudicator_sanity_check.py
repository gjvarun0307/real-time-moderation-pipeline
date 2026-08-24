#!/usr/bin/env python3
"""
Manual sanity check for the provider adapters against the
real APIs

Usage:

    export GROQ_API_KEY=...
    export GEMINI_API_KEY=...
    python scripts/adjudicator_sanity_check.py
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

import aiohttp

sys.path.insert(0, "src")

from adjudicator.prompt import PromptBuilder  # noqa: E402
from adjudicator.providers.gemini import GeminiProvider  # noqa: E402
from adjudicator.providers.groq import GroqProvider  # noqa: E402
from common.schemas import AdjudicateResponse, EscalateMessage  # noqa: E402

_NORMAL_MESSAGE = EscalateMessage(
    id="sanity-check-1",
    post_uri="at://did:plc:sanity/app.bsky.feed.post/1",
    author_hash="a" * 32,
    text="I disagree with your take but you make a fair point.",
    text_normalized="I disagree with your take but you make a fair point.",
    lang_predicted="en",
    lang_declared="en",
    lang_confidence=0.9,
    tier1_score_toxic=0.5,
    tier1_model_version="tier1-onnx-sanity-check",
    source="live",
    event_time_us=int(time.time() * 1_000_000),
    escalated_time_us=int(time.time() * 1_000_000),
)


async def _check_provider(name: str, provider, prompt: str) -> None:
    print(f"\n--- {name}: real prompt ---")
    start = time.perf_counter()
    result = await provider.complete(prompt=prompt, timeout=15.0)
    elapsed = time.perf_counter() - start
    print(f"latency: {elapsed:.2f}s")
    print(f"raw_text: {result.raw_text!r}")
    print(f"usage: {result.usage}")
    try:
        parsed = json.loads(result.raw_text)
        response = AdjudicateResponse.model_validate(parsed)
        print(f"validated OK: {response}")
    except Exception as exc:
        print(f"FAILED to parse/validate: {exc}")


async def main() -> None:
    groq_key = os.environ["GROQ_API_KEY"]
    gemini_key = os.environ["GEMINI_API_KEY"]

    builder = PromptBuilder(Path("prompts/adjudicate_v1.txt"))
    prompt = builder.build(_NORMAL_MESSAGE)

    async with aiohttp.ClientSession() as session:
        groq = GroqProvider(
            session, api_key=groq_key, model="openai/gpt-oss-20b",
            base_url="https://api.groq.com/openai/v1/chat/completions",
        )
        gemini = GeminiProvider(
            session, api_key=gemini_key, model="gemini-3.5-flash-lite",
            base_url="https://generativelanguage.googleapis.com/v1beta/models",
        )
        await _check_provider("groq", groq, prompt)
        await _check_provider("gemini", gemini, prompt)


if __name__ == "__main__":
    asyncio.run(main())

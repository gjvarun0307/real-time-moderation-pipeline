# syntax=docker/dockerfile:1
# linux/arm64 target (Ampere A1) — build on an arm64 host or with buildx
# --platform linux/arm64, no cross-compilation handled here.

FROM python:3.12-slim AS builder

# build-essential covers the C toolchain
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN python -m venv /venv
ENV PATH="/venv/bin:$PATH"

COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --no-cache-dir .


FROM python:3.12-slim AS runtime

RUN groupadd --system app && useradd --system --gid app --no-create-home app

COPY --from=builder /venv /venv

ENV PATH="/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    ADJUDICATOR_PROMPT_PATH=/app/prompts/adjudicate_v1.txt

WORKDIR /app
COPY --chown=app:app prompts/ /app/prompts/

USER app

EXPOSE 8000

CMD ["python", "-m", "adjudicator.main"]

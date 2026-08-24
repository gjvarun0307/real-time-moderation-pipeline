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
    CLASSIFIER_TIER1_MODEL_CACHE_DIR=/app/models/tier1 \
    CLASSIFIER_LEXICON_DIR=/app/models/lexicons

WORKDIR /app

# Tier 1's model.onnx/tokenizer are fetched from R2 at startup, not baked
# in here — this just needs to be writable by the non-root app user.
RUN mkdir -p /app/models/tier1 && chown -R app:app /app/models

COPY --chown=app:app models/lexicons/ /app/models/lexicons/

USER app

EXPOSE 8000

CMD ["python", "-m", "classifier.main"]

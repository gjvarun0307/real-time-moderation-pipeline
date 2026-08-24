# Real-Time Multilingual Moderation Pipeline

**Status: in progress.** This is a research/portfolio project, not
production moderation infrastructure. No verdict produced by this
pipeline results in any action against any real Bluesky account, post,
or user — nothing here reports to Bluesky, blocks content, or notifies
anyone. Full policy: [`docs/PRIVACY.md`](docs/PRIVACY.md).

## What this is

A three-tier moderation cascade running against Bluesky's live public
firehose (Jetstream): cheap script-aware heuristics, then a distilled
multilingual transformer, then LLM adjudication kept inside a free-tier
budget by a deterministic sampling guard — designed so the vast majority
of traffic never needs an LLM call at all. Deployed on real
infrastructure (k3s, Redpanda, Postgres, Redis, Prometheus/Grafana) on
an Oracle Cloud Always-Free ARM instance, at **$0 infrastructure cost**.

## Architecture

```
Bluesky Jetstream (live firehose)
        │
        ▼
 ingest-service ──► posts.raw (Redpanda)
                         │
                         ▼
                 classifier-service
      ┌──────────────────────────────────┐
      │ Tier 0 — script-aware lexicons    │
      ├──────────────────────────────────┤
      │ Tier 1 — distilled XLM-R,         │
      │ 6-layer, int8 ONNX                │
      ├──────────────────────────────────┤
      │ Budget guard — deterministic      │
      │ sample + overflow protection      │
      └────────────┬──────────┬──────────┘
             escalate│        │ verdict
                     ▼        ▼
       moderation.escalate  moderation.verdicts ──► Postgres (selective)
                     │
                     ▼
             adjudicator-service
      ┌──────────────────────────────────┐
      │ Tier 2 — Groq (primary) /         │
      │ Gemini (failover)                 │
      └────────────┬─────────────────────┘
                     ▼
             moderation.verdicts
```

## What's done

- Live ingestion from the real Jetstream firehose — language
  canonicalization, language ID, dedup, backpressure.
- Toxicity model trained (teacher + distilled student), calibrated, and
  quantized to int8 ONNX.
- Tier 0 (lexicon heuristics) and Tier 1 (ONNX model) live and serving
  real traffic in `classifier-service`.
- Budget guard and overflow protection between `classifier-service` and
  `adjudicator-service`.
- Tier 2 (`adjudicator-service` — Groq primary, Gemini failover) built.
- Full infra deployed: k3s, Redpanda, Redis, Postgres, Prometheus,
  Grafana.

## What's left

- Expand Tier 0 lexicon coverage.
- Threshold sweep for routing decisions.
- Load testing and resilience scenarios.
- Adversarial and bias evaluation suites.
- Dashboards and drift monitoring.
- Final cost comparison and headline numbers.

## Measured numbers

| Metric | Value |
|---|---|
| Live ingest (5-run average) | 39.00 posts/sec (3.37M/day) |
| Student PR-AUC, toxic (English) | 0.8755 (99.5% of teacher's 0.8801) |
| Student PR-AUC, zero-shot es/it/tr | 0.5610 combined (64% retention) |
| ONNX export size | 236 MB int8 (from 942 MB fp32) |
| Tier 1 ARM inference throughput | ~9.5 items/sec per replica (2 threads) |
| Tier 0 resolution rate (live) | ~3.3% of traffic |
| Unit tests | 280 passing, `ruff` + `mypy --strict` clean |

## Repo layout

```
src/
  ingest/        live Jetstream ingestion → posts.raw
  classifier/    Tier 0 + Tier 1 + budget guard
  adjudicator/   Tier 2 — LLM adjudication
  common/        shared schemas, config, metrics
training/        Colab notebooks: data prep → teacher → student → export
infra/k8s/       k3s manifests, one directory per service
docker/          one Dockerfile per service
docs/            BUDGET.md, MEASURED_BASELINE.md, PRIVACY.md
```

## Running it

Each service is `python -m {service}.main`, configured via env vars
(`{SERVICE}_*` prefix). No service starts with a placeholder secret.
Deployment is via `kubectl apply -f infra/k8s/base/` (Kustomize), images
built locally (`docker build` + `k3s ctr images import`).

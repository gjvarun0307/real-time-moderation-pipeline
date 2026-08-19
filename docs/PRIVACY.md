# Privacy

This project ingests a live public social firehose (Bluesky Jetstream) that
contains real people's speech, including explicit sexual content. This
document is the policy that governs what gets stored, for how long, and why
— treated as non-negotiable for this project. It applies to every service
that touches post data, from `ingest-service` onward, and to the local probe
captures already sitting in this repo.

## What this system is not

- Not a moderation system with any enforcement power. No verdict produced by
  this pipeline results in any action against any Bluesky account, post, or
  user. Nothing here reports to Bluesky, blocks a post, or notifies anyone.
- This is a research/portfolio system. The README states this plainly so a
  reader never mistakes it for production moderation infrastructure.
- Bluesky's own Terms of Service win over anything in this document. If a
  conflict is ever found, the ToS is followed and this doc is corrected.

## Identity handling

- **Raw `did` is never stored.** Every author identifier is hashed —
  `sha256(salt + did)`, truncated to 32 hex chars — before it reaches
  `posts.raw` or Postgres (the `author_hash` field on the ingest message
  and on the `verdicts` table). The salt lives in env config, never in
  the repo.
- The hash is one-way. There is no stored mapping back to the original
  `did` anywhere in the system. Given the same salt, the same account
  always hashes to the same value — that's what makes partitioning by
  `author_hash` and dedup work — but the hash cannot be reversed to
  recover the account.

## What gets displayed publicly

- **No individual post text, on any public surface, ever.** Not in the
  README, not on the public Grafana dashboards, not in `/stats/*` API
  responses.
- Public surfaces show aggregates only: rates, language mix, score
  distributions, rollup counts. If a metric can only be illustrated with a
  real example, it's paraphrased or fabricated for illustration and labeled
  as such — never a real captured post.

## What gets persisted, and for how long

Per the selective-persistence design (persisting every verdict would be
1.35 GB/day and kill the Postgres free tier), a full row is only written
when at least one of these is true:

- decision is `BLOCK` or `REVIEW`
- resolved at Tier 2 (LLM-adjudicated)
- flagged `low_confidence = true`
- it lands in the deterministic ~1% sample of `ALLOW` decisions

Everything else becomes a 1-minute rollup counter (`verdict_rollups`) —
counts and score sums, no text, no per-post identity.

For rows that are persisted:

| Data | Retention |
|---|---|
| `text` column | **24 hours**, then set to `NULL` by the daily retention cronjob |
| Full row, `persist_reason = 'sample'` | 30 days, then deleted |
| Full row, `source = 'replay'` | 7 days, then deleted regardless of reason |
| Full row, any other `persist_reason` (block/review/tier2/low_conf) | Kept — needed for eval and postmortems, but text is still nulled at 24h like every other row |
| Rollup counters | Not time-limited by this policy; they contain no per-post or per-author identity |

Target steady-state size for the `verdicts` table is **<500 MB**; if
actual growth exceeds that, the `ALLOW` sample rate is the first knob to
turn down, not the retention windows.

## Local probe captures (current state, pre-pipeline)

The Phase 1 measurement work (`scripts/probe_firehose.py`) writes raw
`.jsonl` captures to `scripts/data/samples/` containing **unhashed `did`s
and full, unmodified post text** — this is intentional for local
measurement (computing lang distribution, text-length percentiles, tokenizer
fertility) but the same rules apply as soon as anything derived from them
is shared:

- Raw `.jsonl` captures are `.gitignore`d (`scripts/data/samples/*.jsonl`)
  and must never be committed. Confirmed 2026-08-17.
- Only aggregated output — the `.md` / `.json` summaries already in
  `scripts/data/samples/` and written up in `docs/MEASURED_BASELINE.md` —
  is safe to check in, because it contains counts and percentiles, not
  identities or raw text.
- The 2-hour replay corpus that will be captured for load testing is
  subject to the same rule: it stays local/private storage, is never
  committed, and any derived numbers published in `BENCHMARKS.md` are
  aggregates only.

## Why this is designed this way

Hashing at ingest rather than at query time means an unhashed `did` never
exists anywhere past the first few lines of `ingest-service` — there's no
downstream table or log line that could leak it even by mistake. Nulling
`text` after 24h rather than deleting the whole row keeps the verdict,
scores, and language data available for long-term drift analysis and
`POSTMORTEM.md` while bounding how long any actual post content sits in the
database. Selective persistence and the 1% `ALLOW` sample exist primarily
for the free-tier storage budget, but they also mean the vast
majority of ordinary, unremarkable posts are never persisted at all —
rollup counters can't be attributed back to a person even in principle.

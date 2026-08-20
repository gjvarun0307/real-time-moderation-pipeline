# Budget — free-tier capacity math

Done 5 probe runs across different times of day (`docs/MEASURED_BASELINE.md`).
This doc plans capacity with these data.

## 1. Actual measured ingest rate

| Probe run | Usable posts/sec | Projected daily |
|---|---|---|
| 2026-08-11 05:55Z | 37.46 | 3,236,848 |
| 2026-08-11 13:04Z | 42.09 | 3,636,350 |
| 2026-08-11 18:38Z | 31.30 | 2,704,596 |
| 2026-08-11 23:44Z | 44.49 | 3,843,705 |
| 2026-08-13 06:01Z | 39.68 | 3,428,018 |
| **Average** | **39.00 /sec** | **3,369,903 /day** |
| **Range** | 31.30 – 44.49 /sec | 2,704,596 – 3,843,705 /day |


## 2. LLM adjudication budget

The cascade design assumes Tier 0 resolves ~60% (40% reach Tier 1) and 6%
of what reaches Tier 1 lands in the escalation band. **Those percentages
are design targets, not measurements — Tier 0 and Tier 1 don't exist yet,
so there's no real decision mix to measure.** Applying them to our actual
average rate rather than the original single-sample one:

```
3,369,903 posts/day (avg, actual)
  × 40% reaching Tier 1        = 1,347,961/day
  × 6% escalation band          = 80,878/day
```

At the peak observed run (3,843,705/day) that's **92,249/day** in the
escalation band — use this as the sizing ceiling, not the average.

Free LLM tiers realistically allow 1k–15k requests/day (candidate
providers: Groq, Gemini, OpenRouter, Cerebras). Against an ~81k–92k/day
band, that's still **~5–90× over budget** — smaller than the original
10–100×, but the budget-guard mechanism (deterministic sampling of the
escalation band down to what the quota can afford) is just as mandatory
as before; this only changes the exact multiplier, not the conclusion.

### `ADJUDICATION_SAMPLE_BPS` — resolved

**Providers chosen (§3.4):**

| Role | Provider / model | Free-tier quota (confirmed live) | Structured output |
|---|---|---|---|
| **Primary** | Groq `openai/gpt-oss-20b` | 30 RPM · **1,000 RPD** · 8K TPM · 200K TPD (org-level) | Strict mode — constrained decoding, guaranteed schema match |
| **Secondary / failover** | Gemini 3.5 Flash-Lite | 15 RPM · 250K TPM · **500 RPD** (peak limits, per AI Studio in my account) | `responseSchema` (Gemini 3-series structured output) |

The sampling formula: `bps = quota × 0.8 / band × 10,000` (quota with a
20% safety margin, band = escalation volume/day). **Sized off the primary
provider's quota only** — Gemini is failover for when Groq's circuit
breaker is open (§4.3), not additional steady-state daily throughput, so
it doesn't get added into the budget-guard denominator. Summing them would
overstate what the system can actually adjudicate on an ordinary day when
Groq is healthy.

| Quota basis | BPS @ avg band (80,878) | BPS @ peak band (92,249) |
|---|---|---|
| Groq 1,000 RPD | 99 (~1.0%) | **87 (~0.9%)** |

Per §1's own guidance — peak, not average, is the right basis for
anything where under-sizing is the expensive mistake, and exceeding a
free-tier RPD cap (account throttling/suspension risk) is exactly that —
so:

```
ADJUDICATION_SAMPLE_BPS = 87
```

i.e. **~0.87% of the uncertain band gets a real LLM verdict on a live
day**; the rest take the Tier 1 verdict flagged `low_confidence=true`
per §4.3.1. Full escalation (`sample_bps=10000`) is reserved for the
bounded load-test slice in scenario 7 (§8), never live traffic.

## 3. Postgres storage (selective persistence)

A row is persisted only when: `BLOCK`/`REVIEW`, Tier-2-resolved,
`low_confidence`, or the deterministic 1% `ALLOW` sample. The `ALLOW`
sample is the one component computable now, since it doesn't depend on
classifier behavior — it's a flat 1% of whatever fraction of daily volume
ends up `ALLOW`:

| Assumed ALLOW share | Rows/day (1% sample, avg volume) | Rows accumulated over 30d retention | Approx size @ 300B/row |
|---|---|---|---|
| 70% | 23,589 | 707,679 | 212 MB |
| 85% | 28,644 | 859,315 | 258 MB |
| 95% | 32,014 | 960,415 | 288 MB |

So **the `ALLOW` sample alone is likely to consume roughly half the
500 MB steady-state target** within its own 30-day retention window,
*before counting a single `BLOCK`/`REVIEW`/Tier-2/`low_confidence` row*.
The `BLOCK`/`REVIEW`/Tier-2/`low_confidence` share can't be estimated at
all yet — it's `___` until Tier 0/1 exist and there's a real score
distribution to sample from.

**Open question, not yet answered anywhere in this repo:** the retention
cronjob (see `docs/PRIVACY.md`) only deletes rows where `persist_reason =
'sample'` (after 30d) or `source = 'replay'` (after 7d). Rows persisted
because they were `BLOCK`/`REVIEW`/Tier-2-resolved/`low_confidence` have
**no deletion rule at all** — only their `text` column gets nulled at 24h;
the row itself (scores, decision, timestamps) stays forever. Given that,
"<500 MB steady state" is only true if that category's daily volume stays
small relative to the `ALLOW` sample — worth deciding now whether that's
an acceptable gap, or whether those categories need their own retention
window before Phase 3, since retrofitting a retention policy onto rows
you've decided to keep is a harder conversation than deciding it upfront.

## 4. In-process bloom filter (dedup)

Original worked example: ~190k items in a 1h rotating window at 52/sec,
~330 KB at 0.1% false-positive rate. At our actual average rate:

```
39.00/sec × 3,600s = 140,400 items in a rotating 1h window
```

Bloom filter size scales ~linearly with item count at a fixed FP rate, so
scaling the original reference point: `140,400 / 190,000 × 330 KB ≈ 244 KB`.
Confirm this against whatever bloom filter library is actually chosen in
`ingest-service` (parameters depend on the specific implementation) — this
is a sizing estimate, not a substitute for computing `m` and `k` directly
from the library's own formula once that code exists.

## Summary vs. the original single-sample estimate

| Quantity | Original (52.2/sec single sample) | This doc (39.0/sec, 5-run avg) |
|---|---|---|
| Daily posts | 4.5M | 3.37M (range 2.70M–3.84M) |
| Escalation band/day | ~108k | ~81k (avg) / ~92k (peak) |
| Over free LLM quota | 10–100× | ~5–90× |
| Bloom filter window size | ~190k items / 330 KB | ~140k items / ~244 KB |
| `ADJUDICATION_SAMPLE_BPS` | worked example only (~1,100 @ 12k quota) | **87**, sized off Groq `openai/gpt-oss-20b` (1,000 RPD primary); Gemini 3.5 Flash-Lite (500 RPD) as failover only |
| Postgres selective persistence | target <500 MB, arithmetic not shown | ALLOW-sample alone ≈ 212–288 MB/30d; block/review/tier2/low-conf share and retention policy still open |

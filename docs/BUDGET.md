# Budget — free-tier capacity math

The original capacity planning for this project was done against a single
52.2/sec probe run from 2026-08-10. We now have 5 runs across different
times of day (`docs/MEASURED_BASELINE.md`) — this doc redoes that
arithmetic against the actual repeated-sample data. **Numbers below marked
`___` are genuinely unresolved** — either because they depend on a service
that isn't built yet (Tier 0/1 resolution rates, decision mix) or on a
provider choice that hasn't been made. This doc gets updated as those land.

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

That's **~25% below the original single-sample 4.5M/day figure** — every
downstream number in this doc is smaller as a direct result.
It's still a 5-sample average taken over 3 days, all in the same week;
treat 39/sec as the planning midpoint and **3.84M/day (the observed peak
run) as the conservative design number** for anything where under-sizing
is the expensive mistake (queue capacity, LLM budget headroom).

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

### `ADJUDICATION_SAMPLE_BPS` — provisional, pending provider choice

The sampling formula: `bps = quota × 0.8 / band × 10,000` (quota with a
20% safety margin, band = escalation volume/day). Using the actual band
(81k/day average, 92k/day peak):

| Candidate daily quota | BPS @ avg band (80,878) | BPS @ peak band (92,249) |
|---|---|---|
| 1,000 | 99 (~1.0%) | 87 (~0.9%) |
| 5,000 | 495 (~4.9%) | 434 (~4.3%) |
| 12,000 | 1,187 (~11.9%) | 1,041 (~10.4%) |
| 15,000 | 1,484 (~14.8%) | 1,301 (~13.0%) |

`ADJUDICATION_SAMPLE_BPS = ___` — **not set yet.** The Phase 1 exit
criteria call for this to be chosen from measured data, but choosing it for
real means picking a provider and confirming its *current* free-tier RPD
first — free-tier limits change over time, so this needs verifying against
the provider's own docs, not assumed from anything written down here.
That's a Phase 3 task (building `adjudicator-service` against one
provider). This table exists so that choice is a one-line lookup once a
provider is picked, not a re-derivation.

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
| `ADJUDICATION_SAMPLE_BPS` | worked example only (~1,100 @ 12k quota) | table above, still `___` until provider chosen |
| Postgres selective persistence | target <500 MB, arithmetic not shown | ALLOW-sample alone ≈ 212–288 MB/30d; block/review/tier2/low-conf share and retention policy still open |

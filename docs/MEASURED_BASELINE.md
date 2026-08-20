# Measured Baselines
Ran across different time per day to measure traffic for target language.

## Probe run — 2026-08-11 05:55:09Z

- **Local time:** 2026-08-11 00:55:09 (CDT)
- **Endpoint:** `wss://jetstream2.us-east.bsky.network/subscribe`
- **Duration:** 600s requested 600s
- **Events:** 25,460 (22,467 usable posts)

### Rate

| Metric | Value |
|---|---|
| All events | **42.45 /sec** |
| Usable posts | **37.46 /sec** |
| Projected daily | **3,236,848 posts/day** |

### Event kinds / operations

| Kind | Count | Share |
|---|---|---|
| commit | 24,965 | 98.1% |
| account | 291 | 1.1% |
| identity | 204 | 0.8% |

| Operation | Count | Share |
|---|---|---|
| create | 23,434 | 93.9% |
| delete | 1,521 | 6.1% |
| update | 10 | 0.0% |

### Languages (canonicalized — see spec §4.1)

| Lang | Count | Share |
|---|---|---|
| en | 11,291 | 50.26% |
| ja | 3,967 | 17.66% |
| <missing> | 2,759 | 12.28% |
| de | 970 | 4.32% |
| ko | 538 | 2.39% |
| ne | 463 | 2.06% |
| es | 445 | 1.98% |
| fr | 370 | 1.65% |
| pt | 217 | 0.97% |
| nl | 208 | 0.93% |
| tr | 140 | 0.62% |
| it | 100 | 0.45% |
| zh | 97 | 0.43% |
| fi | 95 | 0.42% |
| th | 93 | 0.41% |
| ro | 83 | 0.37% |
| pl | 81 | 0.36% |
| ru | 71 | 0.32% |
| sv | 61 | 0.27% |
| cs | 52 | 0.23% |

- `langs` missing: **12.28%** of posts
- multi-language declared: 2.19% of posts

- raw variant tags collapsed by canonicalization: `da-DK, de-DE, en-AU, en-GB, en-UK, en-US, en-us, es-ES, et-EE, fi-FI, fr-FR, it-IT`

### Text length (chars)

| Lang | n | p50 | p90 | p95 | p99 | max |
|---|---|---|---|---|---|---|
| **ALL** | 22,467 | 70 | 253 | 291 | 300 | 409 |
| en | 11,291 | 75 | 265 | 293 | 300 | 303 |
| ja | 3,967 | 35 | 139 | 189 | 266 | 311 |
| <missing> | 2,759 | 118 | 290 | 300 | 300 | 409 |
| de | 970 | 60 | 272 | 294 | 299 | 303 |
| ko | 538 | 30 | 134 | 214 | 298 | 303 |
| ne | 463 | 155 | 159 | 161 | 163 | 196 |
| es | 445 | 81 | 266 | 290 | 299 | 299 |
| fr | 370 | 78 | 269 | 293 | 300 | 302 |
| pt | 217 | 83 | 254 | 287 | 299 | 300 |
| nl | 208 | 56 | 224 | 275 | 295 | 301 |

> Chars are not tokens. Run the tokenizer-fertility script (spec §4.2) before choosing `max_seq_len` — CJK runs far denser per character than Latin script.

## Probe run — 2026-08-11 13:04:18Z

- **Local time:** 2026-08-11 08:04:18 (CDT)
- **Endpoint:** `wss://jetstream1.us-east.bsky.network/subscribe`
- **Duration:** 600s requested 600s
- **Events:** 28,091 (25,239 usable posts)

### Rate

| Metric | Value |
|---|---|
| All events | **46.84 /sec** |
| Usable posts | **42.09 /sec** |
| Projected daily | **3,636,350 posts/day** |

### Event kinds / operations

| Kind | Count | Share |
|---|---|---|
| commit | 27,732 | 98.7% |
| account | 201 | 0.7% |
| identity | 158 | 0.6% |

| Operation | Count | Share |
|---|---|---|
| create | 26,415 | 95.3% |
| delete | 1,302 | 4.7% |
| update | 15 | 0.1% |

### Languages (canonicalized — see spec §4.1)

| Lang | Count | Share |
|---|---|---|
| en | 13,362 | 52.94% |
| ja | 4,193 | 16.61% |
| <missing> | 2,824 | 11.19% |
| de | 825 | 3.27% |
| es | 816 | 3.23% |
| pt | 785 | 3.11% |
| ko | 558 | 2.21% |
| fr | 533 | 2.11% |
| nl | 204 | 0.81% |
| tr | 187 | 0.74% |
| ne | 144 | 0.57% |
| it | 98 | 0.39% |
| zh | 59 | 0.23% |
| ca | 56 | 0.22% |
| sv | 53 | 0.21% |
| ar | 53 | 0.21% |
| ru | 51 | 0.2% |
| cs | 50 | 0.2% |
| pl | 48 | 0.19% |
| th | 46 | 0.18% |

- `langs` missing: **11.19%** of posts
- multi-language declared: 0.88% of posts

- raw variant tags collapsed by canonicalization: `ca-ES, de-DE, en-AU, en-GB, en-UK, en-US, en-us, fr-FR, ja-JP, nl-NL, pt-BR, sv-FI`

### Text length (chars)

| Lang | n | p50 | p90 | p95 | p99 | max |
|---|---|---|---|---|---|---|
| **ALL** | 25,239 | 73 | 259 | 293 | 300 | 594 |
| en | 13,362 | 82 | 269 | 294 | 300 | 594 |
| ja | 4,193 | 36 | 115 | 153 | 284 | 334 |
| <missing> | 2,824 | 127 | 294 | 300 | 300 | 306 |
| de | 825 | 75 | 284 | 296 | 300 | 303 |
| es | 816 | 74 | 259 | 289 | 300 | 305 |
| pt | 785 | 70 | 258 | 288 | 300 | 301 |
| ko | 558 | 33 | 169 | 203 | 293 | 300 |
| fr | 533 | 88 | 278 | 295 | 299 | 308 |
| nl | 204 | 60 | 243 | 279 | 298 | 300 |
| tr | 187 | 55 | 211 | 249 | 298 | 300 |

> Chars are not tokens. Run the tokenizer-fertility script (spec §4.2) before choosing `max_seq_len` — CJK runs far denser per character than Latin script.

## Probe run — 2026-08-11 18:38:19Z

- **Local time:** 2026-08-11 13:38:19 (CDT)
- **Endpoint:** `wss://jetstream2.us-east.bsky.network/subscribe`
- **Duration:** 600s requested 600s
- **Events:** 20,799 (18,769 usable posts)

### Rate

| Metric | Value |
|---|---|
| All events | **34.69 /sec** |
| Usable posts | **31.3 /sec** |
| Projected daily | **2,704,596 posts/day** |

### Event kinds / operations

| Kind | Count | Share |
|---|---|---|
| commit | 20,564 | 98.9% |
| account | 129 | 0.6% |
| identity | 106 | 0.5% |

| Operation | Count | Share |
|---|---|---|
| create | 19,569 | 95.2% |
| delete | 986 | 4.8% |
| update | 9 | 0.0% |

### Languages (canonicalized — see spec §4.1)

| Lang | Count | Share |
|---|---|---|
| en | 12,054 | 64.22% |
| <missing> | 1,871 | 9.97% |
| ja | 1,420 | 7.57% |
| es | 600 | 3.2% |
| de | 538 | 2.87% |
| pt | 520 | 2.77% |
| fr | 358 | 1.91% |
| ko | 244 | 1.3% |
| ne | 192 | 1.02% |
| nl | 176 | 0.94% |
| tr | 110 | 0.59% |
| th | 87 | 0.46% |
| it | 82 | 0.44% |
| sv | 60 | 0.32% |
| pl | 56 | 0.3% |
| zh | 53 | 0.28% |
| ru | 48 | 0.26% |
| cs | 42 | 0.22% |
| fi | 32 | 0.17% |
| ar | 27 | 0.14% |

- `langs` missing: **9.97%** of posts
- multi-language declared: 1.53% of posts

- raw variant tags collapsed by canonicalization: `de-DE, en-AU, en-GB, en-US, en-us, es-ES, et-EE, fi-FI, fr-FR, it-IT, ja-JP, lt-LT`

### Text length (chars)

| Lang | n | p50 | p90 | p95 | p99 | max |
|---|---|---|---|---|---|---|
| **ALL** | 18,769 | 80 | 266 | 292 | 300 | 411 |
| en | 12,054 | 81 | 270 | 293 | 300 | 411 |
| <missing> | 1,871 | 127 | 280 | 295 | 299 | 304 |
| ja | 1,420 | 38 | 156 | 195 | 289 | 300 |
| es | 600 | 74 | 275 | 294 | 300 | 301 |
| de | 538 | 67 | 274 | 294 | 300 | 301 |
| pt | 520 | 71 | 233 | 272 | 297 | 304 |
| fr | 358 | 94 | 287 | 295 | 300 | 300 |
| ko | 244 | 31 | 128 | 209 | 299 | 301 |
| ne | 192 | 157 | 161 | 162 | 163 | 164 |
| nl | 176 | 59 | 203 | 268 | 300 | 301 |

> Chars are not tokens. Run the tokenizer-fertility script (spec §4.2) before choosing `max_seq_len` — CJK runs far denser per character than Latin script.

## Probe run — 2026-08-11 23:44:34Z

- **Local time:** 2026-08-11 18:44:34 (CDT)
- **Endpoint:** `wss://jetstream2.us-east.bsky.network/subscribe`
- **Duration:** 600s requested 600s
- **Events:** 30,027 (26,677 usable posts)

### Rate

| Metric | Value |
|---|---|
| All events | **50.07 /sec** |
| Usable posts | **44.49 /sec** |
| Projected daily | **3,843,705 posts/day** |

### Event kinds / operations

| Kind | Count | Share |
|---|---|---|
| commit | 29,635 | 98.7% |
| account | 214 | 0.7% |
| identity | 178 | 0.6% |

| Operation | Count | Share |
|---|---|---|
| create | 27,911 | 94.2% |
| delete | 1,705 | 5.8% |
| update | 19 | 0.1% |

### Languages (canonicalized — see spec §4.1)

| Lang | Count | Share |
|---|---|---|
| en | 18,397 | 68.96% |
| <missing> | 2,854 | 10.7% |
| de | 959 | 3.59% |
| es | 861 | 3.23% |
| pt | 832 | 3.12% |
| ja | 648 | 2.43% |
| fr | 488 | 1.83% |
| nl | 356 | 1.33% |
| ne | 331 | 1.24% |
| tr | 169 | 0.63% |
| it | 113 | 0.42% |
| ru | 72 | 0.27% |
| ar | 67 | 0.25% |
| sv | 58 | 0.22% |
| ko | 56 | 0.21% |
| cs | 45 | 0.17% |
| ca | 42 | 0.16% |
| nb | 40 | 0.15% |
| pl | 39 | 0.15% |
| fi | 35 | 0.13% |

- `langs` missing: **10.7%** of posts
- multi-language declared: 0.87% of posts

- raw variant tags collapsed by canonicalization: `ca-ES, da-DK, de-DE, en-AU, en-GB, en-UK, en-US, es-ES, ja-JP, nl-NL, pt-BR`

### Text length (chars)

| Lang | n | p50 | p90 | p95 | p99 | max |
|---|---|---|---|---|---|---|
| **ALL** | 26,677 | 78 | 264 | 294 | 300 | 372 |
| en | 18,397 | 72 | 259 | 291 | 300 | 335 |
| <missing> | 2,854 | 143 | 300 | 300 | 300 | 372 |
| de | 959 | 57 | 252 | 291 | 300 | 303 |
| es | 861 | 68 | 242 | 282 | 299 | 302 |
| pt | 832 | 64 | 228 | 284 | 299 | 300 |
| ja | 648 | 55 | 176 | 229 | 297 | 300 |
| fr | 488 | 65 | 260 | 290 | 300 | 307 |
| nl | 356 | 59 | 227 | 289 | 300 | 300 |
| ne | 331 | 157 | 160 | 161 | 163 | 164 |
| tr | 169 | 60 | 183 | 236 | 300 | 300 |

> Chars are not tokens. Run the tokenizer-fertility script (spec §4.2) before choosing `max_seq_len` — CJK runs far denser per character than Latin script.

## Probe run — 2026-08-13 06:01:41Z

- **Local time:** 2026-08-13 01:01:41 (CDT)
- **Endpoint:** `wss://jetstream2.us-east.bsky.network/subscribe`
- **Duration:** 600s requested 600s
- **Events:** 26,114 (23,789 usable posts)

### Rate

| Metric | Value |
|---|---|
| All events | **43.55 /sec** |
| Usable posts | **39.68 /sec** |
| Projected daily | **3,428,018 posts/day** |

### Event kinds / operations

| Kind | Count | Share |
|---|---|---|
| commit | 25,731 | 98.5% |
| account | 222 | 0.9% |
| identity | 161 | 0.6% |

| Operation | Count | Share |
|---|---|---|
| create | 24,750 | 96.2% |
| delete | 909 | 3.5% |
| update | 72 | 0.3% |

### Languages (canonicalized — see spec §4.1)

| Lang | Count | Share |
|---|---|---|
| en | 16,139 | 67.84% |
| ja | 2,526 | 10.62% |
| <missing> | 2,264 | 9.52% |
| pt | 976 | 4.1% |
| es | 454 | 1.91% |
| ne | 334 | 1.4% |
| ko | 221 | 0.93% |
| fr | 217 | 0.91% |
| de | 197 | 0.83% |
| ru | 82 | 0.34% |
| tr | 43 | 0.18% |
| th | 42 | 0.18% |
| ca | 39 | 0.16% |
| nl | 39 | 0.16% |
| zh | 32 | 0.13% |
| it | 29 | 0.12% |
| ar | 28 | 0.12% |
| pl | 27 | 0.11% |
| sv | 14 | 0.06% |
| da | 11 | 0.05% |

- `langs` missing: **9.52%** of posts
- multi-language declared: 1.59% of posts

- raw variant tags collapsed by canonicalization: `de-DE, en-AU, en-GB, en-UK, en-US, en-us, es-ES, et-EE, fr-FR, it-IT, ja-JP, lt-LT`

### Text length (chars)

| Lang | n | p50 | p90 | p95 | p99 | max |
|---|---|---|---|---|---|---|
| **ALL** | 23,789 | 71 | 246 | 289 | 300 | 385 |
| en | 16,139 | 70 | 248 | 288 | 299 | 385 |
| ja | 2,526 | 38 | 147 | 192 | 276 | 300 |
| <missing> | 2,264 | 125 | 296 | 300 | 300 | 369 |
| pt | 976 | 61 | 218 | 270 | 297 | 303 |
| es | 454 | 82 | 264 | 295 | 300 | 306 |
| ne | 334 | 155 | 161 | 162 | 164 | 165 |
| ko | 221 | 25 | 93 | 177 | 295 | 300 |
| fr | 217 | 69 | 274 | 295 | 300 | 300 |
| de | 197 | 80 | 291 | 297 | 300 | 301 |
| ru | 82 | 73 | 254 | 293 | 300 | 300 |

> Chars are not tokens. Run the tokenizer-fertility script (spec §4.2) before choosing `max_seq_len` — CJK runs far denser per character than Latin script.

---

## Cross-run summary (5 runs, 2026-08-11 to 2026-08-13)

| Probe run | Usable posts/sec | Projected daily | en share | ja share | missing share |
|---|---|---|---|---|---|
| 08-11 05:55Z | 37.46 | 3,236,848 | 50.26% | 17.66% | 12.28% |
| 08-11 13:04Z | 42.09 | 3,636,350 | 52.94% | 16.61% | 11.19% |
| 08-11 18:38Z | 31.30 | 2,704,596 | 64.22% | 7.57% | 9.97% |
| 08-11 23:44Z | 44.49 | 3,843,705 | 68.96% | 2.43% | 10.70% |
| 08-13 06:01Z | 39.68 | 3,428,018 | 67.84% | 10.62% | 9.52% |
| **Average** | **39.00 /sec** | **3,369,903 /day** | **60.84%** | **10.98%** | **10.73%** |
| **Range** | 31.30 – 44.49 /sec | 2,704,596 – 3,843,705 | 50.26 – 68.96% | 2.43 – 17.66% | 9.52 – 12.28% |

This is the dataset `docs/BUDGET.md` averages against — see that file for the capacity arithmetic. Two things worth noting from the spread rather than the average alone:

- **Japanese share swings 2.4%–17.7% run to run** — much wider variance than English. At only 5 samples across 3 days (all within one week), this reads as time-of-day sensitivity rather than noise, consistent with spec §4.5's note that Japanese traffic peaks at JST evening. Not enough runs yet to plot the diurnal curve properly (that's the Phase 6 24h language-mix plot, §11), but it's the reason to treat any single run's language mix as unrepresentative.
- **`langs` missing stays tight (9.5%–12.3%)** across all 5 runs regardless of rate or language mix — more stable than the original single-run 12.5% figure suggested, which is reassuring for sizing fastText LID load (§4.1 step 8) since it isn't swinging with traffic volume.

**Still only 3 distinct days, all in the same week.** Re-run at a few more times of day/week before treating 39/sec or the 60/11/11 en/ja/missing split as final — the spec calls for "3–4 times of day," not 3–4 total, so weekday/weekend and more evening-JST-hour coverage would strengthen this before it's cited as a headline number.

## Tokenizer fertility → `max_seq_len` (spec §4.2.1)

Ran `scripts/tokenizer_fertility.py` (`xlm-roberta-base`) against all 5 probe captures combined — 95,932 usable posts, 31 languages with n≥30.

| Lang | n | p50 | p90 | p95 | p99 | max | tokens/char |
|---|---|---|---|---|---|---|---|
| en | 69,436 | 23 | 70 | 79 | 95 | 596 | 0.30 |
| ja | 12,198 | 25 | 78 | 104 | 161 | 252 | 0.62 |
| \<missing\> | 12,039 | 38 | 83 | 94 | 121 | 307 | 0.30 |
| pt | 3,235 | 20 | 65 | 76 | 103 | 152 | 0.30 |
| es | 3,066 | 23 | 70 | 77 | 91 | 138 | 0.30 |
| ko | 1,551 | 21 | 87 | 123 | 191 | 203 | 0.64 |
| zh | 254 | 26 | 104 | 131 | 267 | 299 | 0.65 |

(Full 31-language table is reproducible via the script — not all rows pasted here.)

**`max_seq_len = 192`**, from Japanese's p99 (161 tokens, rounded up to the nearest 32). Chosen over the literal all-language worst case (`zh` at p99=267 → 288) deliberately: `zh` is 0.13% of traffic and explicitly long-tail/untuned per §2.2, while `ja` is the spec's designated hard-language story (§4.2.1, §5.2) and one of the four languages the FPR table and lexicons actually target. CJK's tokens/char (~0.62–0.65) running roughly double Latin script (~0.30) is the mechanistic confirmation of §4.2.1's warning — the same 300-char Bluesky cap produces very different token counts depending on script.

Tail languages above 192 tokens at p99 (`zh`, and to a lesser extent `ko` at 191) will see occasional truncation under this setting. Under dynamic batch padding this costs nothing for the other 99%+ of traffic — `max_seq_len` is a truncation ceiling, not a fixed pad target — so it's a bounded, known tradeoff rather than a silent one.

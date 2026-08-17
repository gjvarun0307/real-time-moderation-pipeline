#!/usr/bin/env python3
"""
Jetstream probe — captures live traffic and persists a full report.

Every run writes THREE files to --out-dir, named by UTC timestamp so runs
never clobber each other:

    probe_20260811T143000Z.jsonl[.gz]   raw events (replay + re-analysis)
    probe_20260811T143000Z.json         machine-readable summary
    probe_20260811T143000Z.md           paste-ready for MEASURED_BASELINE.md

Usage:
    pip install websockets

    # single capture
    python probe_firehose.py --duration 600

    # 2h replay corpus at peak, compressed
    python probe_firehose.py --duration 7200 --compress

    # after 3-4 runs at different times of day:
    python probe_firehose.py --compare data/samples

The --compare mode reads every summary JSON in a directory and prints the
diurnal table: posts/sec and language mix by local hour. That table is what
justifies the language-mix-over-time plot the spec asks for in §4.5, and it
is the evidence that drift-monitor's chi-square fires for a known reason.
"""

import argparse
import asyncio
import gzip
import json
import signal
import statistics
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

try:
    import websockets
except ImportError:
    sys.exit("pip install websockets")

SCRIPT_VERSION = "2.0"

ENDPOINTS = [
    "wss://jetstream2.us-east.bsky.network/subscribe",
    "wss://jetstream1.us-east.bsky.network/subscribe",
    "wss://jetstream2.us-west.bsky.network/subscribe",
    "wss://jetstream1.us-west.bsky.network/subscribe",
]
PARAMS = "?wantedCollections=app.bsky.feed.post"

_stop = False


def _sigint(*_):
    global _stop
    _stop = True
    print("\ninterrupt — finalising report...", file=sys.stderr)


def canon_lang(tag: str) -> str:
    """Canonicalize BCP-47 to primary subtag. See spec §4.1 step 6.

    ja-JP -> ja, en-US -> en, cat -> ca.  Without this your per-language
    metrics fragment across variant tags.
    """
    if not tag:
        return "<missing>"
    primary = tag.split("-")[0].lower()
    iso3_to_1 = {
        "cat": "ca", "eng": "en", "jpn": "ja", "por": "pt", "spa": "es",
        "deu": "de", "ger": "de", "fra": "fr", "fre": "fr", "kor": "ko",
        "nep": "ne", "ara": "ar", "rus": "ru", "zho": "zh", "chi": "zh",
        "tam": "ta", "hin": "hi", "mal": "ml", "tha": "th", "ind": "id",
    }
    return iso3_to_1.get(primary, primary)


class Stats:
    def __init__(self):
        self.kinds = Counter()
        self.ops = Counter()
        self.langs_raw = Counter()
        self.langs_canon = Counter()
        self.lang_missing = 0
        self.lang_multi = 0
        self.posts = 0
        self.total = 0
        self.lengths = []
        self.lengths_by_lang = {}
        self.samples = []
        self.first_ts = None
        self.last_ts = None

    def add(self, ev: dict):
        self.total += 1
        now = time.time()
        if self.first_ts is None:
            self.first_ts = now
        self.last_ts = now

        kind = ev.get("kind", "?")
        self.kinds[kind] += 1
        if kind != "commit":
            return

        commit = ev.get("commit") or {}
        op = commit.get("operation", "?")
        self.ops[op] += 1
        if op != "create" or commit.get("collection") != "app.bsky.feed.post":
            return

        rec = commit.get("record") or {}
        text = (rec.get("text") or "").strip()
        if not text:
            return

        self.posts += 1
        n = len(text)
        self.lengths.append(n)

        langs = rec.get("langs")
        if not langs:
            self.lang_missing += 1
            self.langs_raw["<missing>"] += 1
            self.langs_canon["<missing>"] += 1
            self.lengths_by_lang.setdefault("<missing>", []).append(n)
        else:
            if len(langs) > 1:
                self.lang_multi += 1
            for l in langs:
                self.langs_raw[l] += 1
            primary = canon_lang(langs[0])
            self.langs_canon[primary] += 1
            self.lengths_by_lang.setdefault(primary, []).append(n)
            if primary != "en" and len(self.samples) < 40:
                self.samples.append({"lang": primary, "text": text[:160]})

    # ---------- reporting ----------

    @staticmethod
    def _pcts(v):
        if not v:
            return {}
        s = sorted(v)

        def p(q):
            return s[min(int(len(s) * q), len(s) - 1)]

        return {"n": len(s), "p50": p(.50), "p90": p(.90), "p95": p(.95),
                "p99": p(.99), "max": s[-1], "mean": round(statistics.fmean(s), 1)}

    def summary(self, meta: dict) -> dict:
        elapsed = max((self.last_ts or 0) - (self.first_ts or 0), 1e-9)
        tot_l = sum(self.langs_canon.values()) or 1
        return {
            "script_version": SCRIPT_VERSION,
            "meta": meta,
            "elapsed_sec": round(elapsed, 1),
            "rates": {
                "all_events_per_sec": round(self.total / elapsed, 2),
                "usable_posts_per_sec": round(self.posts / elapsed, 2),
                "posts_per_day_projected": int(self.posts / elapsed * 86400),
            },
            "counts": {"total_events": self.total, "usable_posts": self.posts},
            "kinds": dict(self.kinds),
            "operations": dict(self.ops),
            "languages_raw": dict(self.langs_raw.most_common()),
            "languages_canonical": dict(self.langs_canon.most_common()),
            "language_share_canonical": {
                k: round(100 * v / tot_l, 2)
                for k, v in self.langs_canon.most_common()
            },
            "lang_missing_pct": round(100 * self.lang_missing / max(self.posts, 1), 2),
            "lang_multi_pct": round(100 * self.lang_multi / max(self.posts, 1), 2),
            "text_length_chars": self._pcts(self.lengths),
            "text_length_by_lang": {
                k: self._pcts(v)
                for k, v in sorted(self.lengths_by_lang.items(),
                                   key=lambda x: -len(x[1]))[:10]
            },
            "non_english_samples": self.samples,
        }

    def to_markdown(self, s: dict) -> str:
        m = s["meta"]
        L = []
        A = L.append
        A(f"## Probe run — {m['started_utc']}")
        A("")
        A(f"- **Local time:** {m['started_local']} ({m['timezone']})")
        A(f"- **Endpoint:** `{m['endpoint']}`")
        A(f"- **Duration:** {s['elapsed_sec']:.0f}s requested {m['duration_requested']}s")
        A(f"- **Events:** {s['counts']['total_events']:,} "
          f"({s['counts']['usable_posts']:,} usable posts)")
        A("")
        A("### Rate")
        A("")
        A("| Metric | Value |")
        A("|---|---|")
        A(f"| All events | **{s['rates']['all_events_per_sec']} /sec** |")
        A(f"| Usable posts | **{s['rates']['usable_posts_per_sec']} /sec** |")
        A(f"| Projected daily | **{s['rates']['posts_per_day_projected']:,} posts/day** |")
        A("")
        A("### Event kinds / operations")
        A("")
        A("| Kind | Count | Share |")
        A("|---|---|---|")
        for k, n in sorted(s["kinds"].items(), key=lambda x: -x[1]):
            A(f"| {k} | {n:,} | {100*n/max(s['counts']['total_events'],1):.1f}% |")
        A("")
        tot_ops = sum(s["operations"].values()) or 1
        A("| Operation | Count | Share |")
        A("|---|---|---|")
        for k, n in sorted(s["operations"].items(), key=lambda x: -x[1]):
            A(f"| {k} | {n:,} | {100*n/tot_ops:.1f}% |")
        A("")
        A("### Languages (canonicalized — see spec §4.1)")
        A("")
        A("| Lang | Count | Share |")
        A("|---|---|---|")
        for k, n in list(s["languages_canonical"].items())[:20]:
            A(f"| {k} | {n:,} | {s['language_share_canonical'][k]}% |")
        A("")
        A(f"- `langs` missing: **{s['lang_missing_pct']}%** of posts")
        A(f"- multi-language declared: {s['lang_multi_pct']}% of posts")
        A("")
        raw_variants = [k for k in s["languages_raw"] if "-" in k]
        if raw_variants:
            A(f"- raw variant tags collapsed by canonicalization: "
              f"`{', '.join(sorted(raw_variants)[:12])}`")
            A("")
        A("### Text length (chars)")
        A("")
        t = s["text_length_chars"]
        if t:
            A("| Lang | n | p50 | p90 | p95 | p99 | max |")
            A("|---|---|---|---|---|---|---|")
            A(f"| **ALL** | {t['n']:,} | {t['p50']} | {t['p90']} | "
              f"{t['p95']} | {t['p99']} | {t['max']} |")
            for lang, v in s["text_length_by_lang"].items():
                A(f"| {lang} | {v['n']:,} | {v['p50']} | {v['p90']} | "
                  f"{v['p95']} | {v['p99']} | {v['max']} |")
        A("")
        A("> Chars are not tokens. Run the tokenizer-fertility script "
          "(spec §4.2) before choosing `max_seq_len` — CJK runs far denser "
          "per character than Latin script.")
        A("")
        return "\n".join(L)

    def print_terminal(self, s: dict):
        print("\n" + "=" * 68)
        print(f"CAPTURED {s['counts']['total_events']:,} events "
              f"over {s['elapsed_sec']:.0f}s")
        print("=" * 68)
        print("\nRATE")
        print(f"  all events    {s['rates']['all_events_per_sec']:8.1f} /sec")
        print(f"  usable posts  {s['rates']['usable_posts_per_sec']:8.1f} /sec"
              f"   <-- real input rate")
        print(f"  projected     {s['rates']['posts_per_day_projected']:,} posts/day")

        print("\nEVENT KINDS")
        for k, n in sorted(s["kinds"].items(), key=lambda x: -x[1]):
            print(f"  {k:<12} {n:>8}  "
                  f"{100*n/max(s['counts']['total_events'],1):5.1f}%")

        print("\nCOMMIT OPERATIONS")
        tot_ops = sum(s["operations"].values()) or 1
        for k, n in sorted(s["operations"].items(), key=lambda x: -x[1]):
            print(f"  {k:<12} {n:>8}  {100*n/tot_ops:5.1f}%")

        print("\nLANGUAGES (canonicalized)  <-- DECIDES TIER 0 LEXICONS")
        top = max(s["languages_canonical"].values()) if s["languages_canonical"] else 1
        for k, n in list(s["languages_canonical"].items())[:20]:
            bar = "#" * int(55 * n / top)
            print(f"  {k:<10} {n:>7}  {s['language_share_canonical'][k]:5.1f}%  {bar}")
        print(f"\n  langs missing:  {s['lang_missing_pct']}% of posts")
        print(f"  multi-lang:     {s['lang_multi_pct']}% of posts")

        t = s["text_length_chars"]
        if t:
            print("\nTEXT LENGTH (chars, by language)")
            print(f"  {'lang':<8} {'n':>7} {'p50':>5} {'p90':>5} {'p95':>5} {'p99':>5}")
            print(f"  {'ALL':<8} {t['n']:>7} {t['p50']:>5} {t['p90']:>5} "
                  f"{t['p95']:>5} {t['p99']:>5}")
            for lang, v in s["text_length_by_lang"].items():
                print(f"  {lang:<8} {v['n']:>7} {v['p50']:>5} {v['p90']:>5} "
                      f"{v['p95']:>5} {v['p99']:>5}")

        if s["non_english_samples"]:
            print("\nNON-ENGLISH SAMPLES  <-- eyeball for code-switching / noise")
            for smp in s["non_english_samples"][:15]:
                print(f"  [{smp['lang']}] {smp['text']}")

        print("\n" + "=" * 68)
        print("DECISION CHECK:")
        print("  1. Enough traffic in your target languages to demo live?")
        print("  2. Does usable-post rate match the spec's assumption?")
        print("  3. Run tokenizer fertility before fixing max_seq_len.")
        print("  4. Re-run at 3-4 times of day, then: --compare <dir>")
        print("=" * 68)


# ---------- capture ----------

async def capture(duration: int, out_dir: Path, compress: bool):
    out_dir.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)
    stamp = started.strftime("%Y%m%dT%H%M%SZ")
    local = datetime.now().astimezone()

    raw_path = out_dir / f"probe_{stamp}.jsonl{'.gz' if compress else ''}"
    json_path = out_dir / f"probe_{stamp}.json"
    md_path = out_dir / f"probe_{stamp}.md"

    stats = Stats()
    deadline = time.time() + duration
    used_endpoint = None

    opener = (lambda p: gzip.open(p, "wt", encoding="utf-8")) if compress \
        else (lambda p: p.open("w", encoding="utf-8"))

    for ep in ENDPOINTS:
        url = ep + PARAMS
        print(f"connecting: {url}", file=sys.stderr)
        try:
            async with websockets.connect(url, max_size=None) as ws:
                used_endpoint = ep
                print(f"connected. capturing {duration}s "
                      f"(ctrl-c to stop early)\n", file=sys.stderr)
                with opener(raw_path) as fh:
                    while not _stop and time.time() < deadline:
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=30)
                        except asyncio.TimeoutError:
                            print("  [30s no data]", file=sys.stderr)
                            continue
                        line = raw if isinstance(raw, str) else raw.decode()
                        fh.write(line)
                        fh.write("\n")
                        try:
                            stats.add(json.loads(line))
                        except json.JSONDecodeError:
                            continue
                        if stats.total % 5000 == 0:
                            print(f"  {stats.total:>8,} events "
                                  f"({stats.posts:,} posts)", file=sys.stderr)
                break
        except Exception as e:
            print(f"  failed: {type(e).__name__}: {e} — next endpoint...",
                  file=sys.stderr)
            continue
    else:
        sys.exit("all endpoints failed")

    meta = {
        "started_utc": started.strftime("%Y-%m-%d %H:%M:%SZ"),
        "started_local": local.strftime("%Y-%m-%d %H:%M:%S"),
        "local_hour": local.hour,
        "timezone": str(local.tzinfo),
        "endpoint": used_endpoint,
        "duration_requested": duration,
        "interrupted": _stop,
        "raw_file": raw_path.name,
    }

    s = stats.summary(meta)
    json_path.write_text(json.dumps(s, ensure_ascii=False, indent=2),
                         encoding="utf-8")
    md_path.write_text(stats.to_markdown(s), encoding="utf-8")

    stats.print_terminal(s)
    size_mb = raw_path.stat().st_size / 1e6
    print(f"\nwritten:")
    print(f"  raw      {raw_path}  ({size_mb:.1f} MB)")
    print(f"  summary  {json_path}")
    print(f"  report   {md_path}   <-- paste into docs/MEASURED_BASELINE.md")


# ---------- compare ----------

def compare(dir_: Path):
    files = sorted(dir_.glob("probe_*.json"))
    if not files:
        sys.exit(f"no probe_*.json found in {dir_}")

    runs = []
    for f in files:
        try:
            runs.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception as e:
            print(f"skipping {f.name}: {e}", file=sys.stderr)

    langs = Counter()
    for r in runs:
        for k, v in r["languages_canonical"].items():
            langs[k] += v
    cols = [k for k, _ in langs.most_common(7)]

    print("\n" + "=" * 78)
    print(f"DIURNAL COMPARISON — {len(runs)} runs")
    print("=" * 78)
    header = f"{'local time':<18}{'hr':>3}{'posts/s':>9}  " + \
             "".join(f"{c:>8}" for c in cols)
    print(header)
    print("-" * len(header))
    for r in sorted(runs, key=lambda x: x["meta"]["local_hour"]):
        m, sh = r["meta"], r["language_share_canonical"]
        row = (f"{m['started_local']:<18}{m['local_hour']:>3}"
               f"{r['rates']['usable_posts_per_sec']:>9.1f}  ")
        row += "".join(f"{sh.get(c, 0.0):>7.1f}%" for c in cols)
        print(row)

    rates = [r["rates"]["usable_posts_per_sec"] for r in runs]
    print("-" * len(header))
    print(f"{'min / max / mean':<18}{'':>3}"
          f"{min(rates):>9.1f}  (max {max(rates):.1f}, "
          f"mean {statistics.fmean(rates):.1f})")

    print("\nPEAK-TO-TROUGH RATIO: "
          f"{max(rates)/max(min(rates), 1e-9):.2f}x")
    print("\nUse the PEAK rate to size queues, replica counts, and the")
    print("free-tier quota arithmetic in docs/BUDGET.md (spec §2.4).")
    print("Language columns shifting across hours IS the natural drift your")
    print("chi-square will fire on — plot it and put it in the README.")
    print("=" * 78)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, _sigint)
    ap = argparse.ArgumentParser(description="Jetstream probe + report")
    ap.add_argument("--duration", type=int, default=600, help="seconds (default 600)")
    ap.add_argument("--out-dir", type=Path, default=Path("data/samples"))
    ap.add_argument("--compress", action="store_true",
                    help="gzip raw capture (use for long runs)")
    ap.add_argument("--compare", type=Path, metavar="DIR",
                    help="skip capture; print diurnal table from saved summaries")
    args = ap.parse_args()

    if args.compare:
        compare(args.compare)
    else:
        asyncio.run(capture(args.duration, args.out_dir, args.compress))

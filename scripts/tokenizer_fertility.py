#!/usr/bin/env python3
"""
Tokenizer fertility per language — decides `max_seq_len` for Tier 1.

Aggregates probe captures (scripts/data/samples/probe_*.jsonl), tokenizes
each post's raw text with the XLM-R tokenizer, and reports tokens/char and
token-count percentiles per declared language. `max_seq_len` should be set
from the worst language's p99, not English's — a length tuned to English
will silently truncate whichever language tokenizes densest.

Needs transformers package installed (pip install transformers).

Usage:

    # aggregate every captured probe run
    python scripts/tokenizer_fertility.py

    # a specific run or a custom glob
    python scripts/tokenizer_fertility.py --files "scripts/data/samples/probe_20260813*.jsonl"
"""

import argparse
import glob
import json
import sys
from collections import defaultdict

from transformers import AutoTokenizer

DEFAULT_GLOB = "scripts/data/samples/probe_*.jsonl"
TOKENIZER_NAME = "xlm-roberta-base"


def canon_lang(tag: str) -> str:
    """Canonicalize all lang to its primary subtag ."""
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


def iter_texts(paths: list[str]):
    """Yield (lang, text) for every usable create/post record across the given probe files."""
    for path in paths:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                ev = json.loads(line)
                if ev.get("kind") != "commit":
                    continue
                commit = ev.get("commit") or {}
                if (
                    commit.get("operation") != "create"
                    or commit.get("collection") != "app.bsky.feed.post"
                ):
                    continue
                rec = commit.get("record") or {}
                text = (rec.get("text") or "").strip()
                if not text:
                    continue
                langs = rec.get("langs")
                lang = canon_lang(langs[0]) if langs else "<missing>"
                yield lang, text


def pct(values: list[int], p: float) -> int:
    """Nearest-rank percentile over a list of ints."""
    v = sorted(values)
    idx = min(int(len(v) * p), len(v) - 1)
    return v[idx]


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--files",
        default=DEFAULT_GLOB,
        help=f"glob of probe .jsonl files (default: {DEFAULT_GLOB})",
    )
    ap.add_argument(
        "--min-lang-n",
        type=int,
        default=30,
        help="drop languages with fewer than N samples from the table",
    )
    args = ap.parse_args()

    paths = sorted(glob.glob(args.files))
    if not paths:
        sys.exit(f"no files matched {args.files!r}")

    print(f"loading {TOKENIZER_NAME} tokenizer...", file=sys.stderr)
    tok = AutoTokenizer.from_pretrained(TOKENIZER_NAME)

    token_lens: dict[str, list[int]] = defaultdict(list)
    char_lens: dict[str, list[int]] = defaultdict(list)
    for lang, text in iter_texts(paths):
        token_lens[lang].append(len(tok.encode(text)))
        char_lens[lang].append(len(text))

    rows = []
    for lang, lens in token_lens.items():
        if len(lens) < args.min_lang_n:
            continue
        chars = char_lens[lang]
        fertility = sum(lens) / sum(chars)
        rows.append(
            (
                lang,
                len(lens),
                pct(lens, 0.50),
                pct(lens, 0.90),
                pct(lens, 0.95),
                pct(lens, 0.99),
                max(lens),
                fertility,
            )
        )
    rows.sort(key=lambda r: -r[1])

    print(f"\n{len(paths)} probe file(s), {TOKENIZER_NAME}\n")
    print("| Lang | n | p50 | p90 | p95 | p99 | max | tokens/char |")
    print("|---|---|---|---|---|---|---|---|")
    for lang, n, p50, p90, p95, p99, mx, fert in rows:
        print(f"| {lang} | {n} | {p50} | {p90} | {p95} | {p99} | {mx} | {fert:.2f} |")

    if rows:
        worst = max(rows, key=lambda r: r[5])  # highest p99
        recommended = ((worst[5] + 31) // 32) * 32
        print(
            f"\nWorst language by p99: **{worst[0]}** (p99={worst[5]} tokens, "
            f"fertility={worst[7]:.2f} tokens/char)"
        )
        print(f"Recommended max_seq_len: **{recommended}** (p99 rounded up to nearest 32)")


if __name__ == "__main__":
    main()

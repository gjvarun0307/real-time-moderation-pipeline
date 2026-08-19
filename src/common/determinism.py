import hashlib


def deterministic_fraction(key: str) -> float:
    """Maps a key to a stable float in [0, 1), reproducible across runs
    and processes — unlike Python's built-in hash(), which is randomized
    per-process for strings.
    """
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    as_int = int.from_bytes(digest[:8], "big")
    return as_int / 2**64

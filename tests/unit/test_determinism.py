from common.determinism import deterministic_fraction


def test_same_key_always_gives_same_fraction():
    assert deterministic_fraction("post-123") == deterministic_fraction("post-123")


def test_different_keys_usually_give_different_fractions():
    values = {deterministic_fraction(f"post-{i}") for i in range(100)}
    assert len(values) == 100


def test_fraction_is_in_unit_interval():
    for i in range(1000):
        f = deterministic_fraction(f"key-{i}")
        assert 0.0 <= f < 1.0


def test_fractions_are_roughly_uniform():
    # coarse sanity check, not a rigorous statistical test
    buckets = [0, 0]
    for i in range(10_000):
        buckets[deterministic_fraction(f"key-{i}") < 0.5] += 1
    ratio = buckets[1] / sum(buckets)
    assert 0.45 < ratio < 0.55

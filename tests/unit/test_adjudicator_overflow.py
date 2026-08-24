from adjudicator.overflow import should_activate_overflow


def test_lag_below_threshold_is_not_overflow():
    assert should_activate_overflow(lag=100, threshold=200) is False


def test_lag_above_threshold_is_overflow():
    assert should_activate_overflow(lag=300, threshold=200) is True


def test_lag_exactly_at_threshold_is_not_overflow():
    assert should_activate_overflow(lag=200, threshold=200) is False

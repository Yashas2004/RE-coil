from app.registry import should_promote


def test_below_gate_is_rejected():
    assert should_promote(0.60, None) is False


def test_first_good_model_is_promoted():
    assert should_promote(0.70, None) is True


def test_slightly_worse_is_tolerated_much_worse_is_not():
    current = {"auc": 0.80}
    assert should_promote(0.79, current) is True    # within 0.02
    assert should_promote(0.75, current) is False   # regression

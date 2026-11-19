from app.registry import should_promote


def test_below_gate_is_rejected():
    assert should_promote(0.60, None) is False


def test_first_good_model_is_promoted():
    assert should_promote(0.70, None) is True


def test_compared_against_champion_on_same_data():
    assert should_promote(0.760, 0.758) is True    # better
    assert should_promote(0.756, 0.758) is True    # within 0.005: tie goes to the fresher model
    assert should_promote(0.740, 0.758) is False   # genuinely worse

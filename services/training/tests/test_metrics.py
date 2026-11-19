from app.metrics import auc


def test_perfect_ranking():
    assert auc([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9]) == 1.0


def test_backwards_ranking():
    assert auc([1, 1, 0, 0], [0.1, 0.2, 0.8, 0.9]) == 0.0


def test_all_ties_is_coin_flip():
    assert auc([0, 1, 0, 1], [0.5, 0.5, 0.5, 0.5]) == 0.5


def test_partial():
    # Pairs (pos, neg): (0.7,0.2) ok, (0.7,0.8) wrong, (0.9,0.2) ok, (0.9,0.8) ok -> 3/4
    assert auc([1, 0, 1, 0], [0.7, 0.2, 0.9, 0.8]) == 0.75

"""
AUC (area under the ROC curve), written out by hand so you can see what it means.

AUC answers one question: if I pick one random WATCHED example and one random
SKIPPED example, how often does the model give the watched one a higher score?

    1.0  = always ranks watched above skipped (perfect)
    0.5  = coin flip (the model learned nothing)
    0.0  = always wrong (perfectly backwards)

We compute it with ranks instead of comparing every pair (which would be slow):
sort all scores, give each a rank 1..N, and count how high the positives sit.
"""


def auc(labels: list[int], scores: list[float]) -> float:
    pairs = []
    for label, score in zip(labels, scores):
        pairs.append((score, label))
    pairs.sort(key=lambda pair: pair[0])

    # Assign ranks 1..N. Tied scores share the average of their ranks.
    ranks = [0.0] * len(pairs)
    i = 0
    while i < len(pairs):
        j = i
        while j + 1 < len(pairs) and pairs[j + 1][0] == pairs[i][0]:
            j += 1
        average_rank = (i + 1 + j + 1) / 2
        for k in range(i, j + 1):
            ranks[k] = average_rank
        i = j + 1

    num_pos = 0
    rank_sum_pos = 0.0
    for index, (score, label) in enumerate(pairs):
        if label == 1:
            num_pos += 1
            rank_sum_pos += ranks[index]
    num_neg = len(pairs) - num_pos

    if num_pos == 0 or num_neg == 0:
        return 0.5  # undefined; treat as "no skill"

    # How far the positives' ranks are above the smallest they could possibly be.
    return (rank_sum_pos - num_pos * (num_pos + 1) / 2) / (num_pos * num_neg)

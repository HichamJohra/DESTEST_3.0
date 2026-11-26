"""The accuracy grade: closeness to target, 0-100, one number per submission.

As the summary Accuracy Grade of the DESTEST comparison tool (Johra et al., 2021): for each
compared item (an aggregate, a physics check, or a comparison metric of a series), the
submission closest to the item's reference scores 100, the furthest 0, the others linearly
in between by their distance. The grade is the weighted mean of the item scores.

The reference of an item depends on its kind: the median of all submissions (aggregates),
the target given in the CME spec file (physics checks), or the metric's value for a
perfect fit, e.g. 0 for MBE and CVRMSE, 1 for r (comparison metrics).

Reference: H. Johra et al. (2021). Evaluating different metrics for inter-model comparison
of urban-scale building energy simulation time series. Building Simulation 2021.
https://doi.org/10.26868/25222708.2021.30410
"""

import math
from collections.abc import Sequence


def closeness_scores(
    values: dict[str, float | None], reference: float | None
) -> dict[str, float | None]:
    """Score (0-100) of each submission on one item, from its distance to the reference.

    The closest submission gets 100, the furthest 0, the others in between,
    linearly in their distance: 100 * (worst - d) / (worst - best). If all are
    equally close, all get 100. A missing value (or reference) gets `None`.

    >>> closeness_scores({"a": 10.0, "b": 12.0, "c": 11.0, "d": None}, 10.0)
    {'a': 100.0, 'b': 0.0, 'c': 50.0, 'd': None}
    """
    if reference is None:
        return dict.fromkeys(values)
    dist = {k: abs(v - reference) for k, v in values.items() if v is not None and math.isfinite(v)}
    if not dist:
        return dict.fromkeys(values)
    best, worst = min(dist.values()), max(dist.values())
    span = worst - best
    return {
        k: (None if k not in dist else 100.0 if span == 0 else 100 * (worst - dist[k]) / span)
        for k in values
    }


def closeness_grade(
    scores: Sequence[float | None], weights: Sequence[float] | None = None
) -> float | None:
    """Weighted mean of the item scores of one submission (missing scores left out).

    `weights`: one per score (default: all 1).

    >>> closeness_grade([100.0, 50.0, None])
    75.0
    >>> closeness_grade([100.0, 50.0], [3.0, 1.0])
    87.5
    """
    w = list(weights) if weights is not None else [1.0] * len(scores)
    if len(w) != len(scores):
        raise ValueError("closeness_grade: one weight per score")
    pairs = [(s, wi) for s, wi in zip(scores, w, strict=True) if s is not None and wi > 0]
    total = sum(wi for _, wi in pairs)
    return sum(s * wi for s, wi in pairs) / total if total else None

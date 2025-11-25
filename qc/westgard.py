"""Quality control helpers: Westgard rules and Levey–Jennings charting."""
from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass
class ControlResult:
    run: int
    value: float
    mean: float
    sd: float

    @property
    def z_score(self) -> float:
        return (self.value - self.mean) / self.sd if self.sd else 0.0


def check_westgard(results: List[ControlResult]) -> Dict[str, List[int]]:
    """Evaluate a sequence of control results against Westgard rules.

    The returned dictionary maps rule names to a list of indices in ``results``
    where the rule is breached.

    Rules implemented:
    - ``1_2s``: a single control is >= 2 SD from the mean (either direction).
    - ``1_3s``: a single control is >= 3 SD from the mean (either direction).
    - ``2_2s``: two consecutive controls are each >= 2 SD from the mean.
    - ``r_4s``: two consecutive controls differ by at least 4 SD and are on
      opposite sides of the mean.
    - ``4_1s``: four consecutive controls are each >= 1 SD from the mean.
    - ``10_x``: ten consecutive controls fall on the same side of the mean.
    """

    breaches: Dict[str, List[int]] = {"1_2s": [], "1_3s": [], "2_2s": [], "r_4s": [], "4_1s": [], "10_x": []}
    z_scores = [r.z_score for r in results]

    for idx, z in enumerate(z_scores):
        if abs(z) >= 2:
            breaches["1_2s"].append(idx)
        if abs(z) >= 3:
            breaches["1_3s"].append(idx)
        if idx >= 1:
            separation = abs(z - z_scores[idx - 1])
            if separation >= 4 and z * z_scores[idx - 1] < 0:
                breaches["r_4s"].append(idx)
        if idx >= 1 and abs(z) >= 2 and abs(z_scores[idx - 1]) >= 2:
            breaches["2_2s"].append(idx)
        if idx >= 3 and all(abs(z_scores[j]) >= 1 for j in range(idx - 3, idx + 1)):
            breaches["4_1s"].append(idx)
        if idx >= 9:
            window = z_scores[idx - 9 : idx + 1]
            if all(score > 0 for score in window) or all(score < 0 for score in window):
                breaches["10_x"].append(idx)
    return breaches


def levey_jennings_points(results: List[ControlResult]) -> List[Tuple[int, float, float]]:
    return [(r.run, r.value, r.z_score) for r in results]

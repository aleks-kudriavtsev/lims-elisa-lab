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
    breaches: Dict[str, List[int]] = {"1_2s": [], "1_3s": [], "2_2s": [], "r_4s": [], "4_1s": [], "10_x": []}
    z_scores = [r.z_score for r in results]

    for idx, z in enumerate(z_scores):
        if abs(z) >= 2:
            breaches["1_2s"].append(idx)
        if abs(z) >= 3:
            breaches["1_3s"].append(idx)
        if idx >= 1 and z * z_scores[idx - 1] < -4:  # opposite sides totaling >4 SD
            breaches["r_4s"].append(idx)
        if idx >= 1 and abs(z) >= 2 and abs(z_scores[idx - 1]) >= 2:
            breaches["2_2s"].append(idx)
        if idx >= 3 and all(abs(z_scores[j]) >= 1 for j in range(idx - 3, idx + 1)):
            breaches["4_1s"].append(idx)
        if idx >= 9 and all(z_scores[j] > 0 for j in range(idx - 9, idx + 1)):
            breaches["10_x"].append(idx)
    return breaches


def levey_jennings_points(results: List[ControlResult]) -> List[Tuple[int, float, float]]:
    return [(r.run, r.value, r.z_score) for r in results]

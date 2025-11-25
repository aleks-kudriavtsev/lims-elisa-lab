from qc.westgard import ControlResult, check_westgard, levey_jennings_points


def test_westgard_rules_detect_breaches():
    results = [
        ControlResult(run=i, value=10 + i, mean=10, sd=1) for i in range(1, 6)
    ]
    breaches = check_westgard(results)
    assert breaches["1_2s"]
    assert breaches["4_1s"]


def test_levey_jennings_points_include_z_scores():
    results = [ControlResult(run=1, value=11, mean=10, sd=1)]
    points = levey_jennings_points(results)
    assert points[0][2] == 1.0

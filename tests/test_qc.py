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


def test_westgard_10x_detects_positive_and_negative_trends():
    positive_results = [ControlResult(run=i, value=1, mean=0, sd=1) for i in range(1, 11)]
    negative_results = [ControlResult(run=i, value=-1, mean=0, sd=1) for i in range(1, 11)]

    positive_breaches = check_westgard(positive_results)
    negative_breaches = check_westgard(negative_results)

    assert positive_breaches["10_x"] == [9]
    assert negative_breaches["10_x"] == [9]


def test_westgard_rules_ignore_mixed_direction_runs_for_10x():
    mixed_results = [
        ControlResult(run=i, value=1 if i % 2 else -1, mean=0, sd=1) for i in range(1, 11)
    ]

    breaches = check_westgard(mixed_results)

    assert not breaches["10_x"]


def test_r_4s_detects_large_opposite_shifts():
    results = [
        ControlResult(run=1, value=2.5, mean=0, sd=1),
        ControlResult(run=2, value=-2, mean=0, sd=1),
    ]

    breaches = check_westgard(results)

    assert breaches["r_4s"] == [1]

import pytest

from analytics.curve_fitting import fit_4pl, fit_5pl, four_parameter_logistic, plot_curve


def test_fit_4pl_returns_parameters_and_predictions():
    xs = [0.1, 0.5, 1.0, 2.0, 5.0]
    ys = [four_parameter_logistic(x, 0.05, 1.2, 2.0, 1.0) for x in xs]
    result = fit_4pl(xs, ys)
    assert result.model == "4PL"
    assert set(result.parameters.keys()) == {"a", "b", "c", "d"}
    assert len(result.predictions) == len(xs)
    assert result.r_squared > 0.95
    assert result.converged is True
    assert "converged" in result.status.lower()
    curve = plot_curve(result, points=5)
    assert len(curve) == 5


def test_fit_5pl_handles_asymmetry():
    xs = [0.1, 0.5, 1.0, 2.0, 5.0]
    ys = [
        1.0 + (0.05 - 1.0) / ((1 + (x / 2.0) ** 1.1) ** 0.9)
        for x in xs
    ]
    result = fit_5pl(xs, ys)
    assert result.model == "5PL"
    assert "g" in result.parameters
    assert result.r_squared > 0.9
    assert result.converged is True


def test_fit_4pl_rejects_empty_inputs():
    with pytest.raises(ValueError, match="non-empty"):
        fit_4pl([], [])


def test_fit_4pl_requires_matching_lengths():
    with pytest.raises(ValueError, match="same length"):
        fit_4pl([0.1, 0.2], [1.0])


def test_fit_4pl_rejects_non_positive_concentrations():
    with pytest.raises(ValueError, match="positive"):
        fit_4pl([0.0, 0.5], [1.0, 1.2])
    with pytest.raises(ValueError, match="positive"):
        fit_4pl([-1.0, 0.5], [1.0, 1.2])


def test_fit_handles_repeated_points():
    xs = [1.0, 1.0, 1.0]
    ys = [four_parameter_logistic(x, 0.1, 1.0, 1.5, 2.0) for x in xs]
    result = fit_4pl(xs, ys, backend="gradient")
    assert len(result.predictions) == len(xs)
    assert result.status


def test_fit_reports_non_convergence():
    xs = [0.5, 1.0, 2.0]
    ys = [1.0, 1.1, 1.2]
    result = fit_4pl(xs, ys, backend="gradient", max_iterations=1, tolerance=1e-12)
    assert result.converged is False
    assert "maximum iterations" in result.status.lower()

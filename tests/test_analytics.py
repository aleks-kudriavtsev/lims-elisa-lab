from analytics.curve_fitting import fit_4pl, fit_5pl, four_parameter_logistic, plot_curve


def test_fit_4pl_returns_parameters_and_predictions():
    xs = [0.1, 0.5, 1.0, 2.0, 5.0]
    ys = [four_parameter_logistic(x, 0.05, 1.2, 2.0, 1.0) for x in xs]
    result = fit_4pl(xs, ys)
    assert result.model == "4PL"
    assert set(result.parameters.keys()) == {"a", "b", "c", "d"}
    assert len(result.predictions) == len(xs)
    assert result.r_squared > 0.95
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

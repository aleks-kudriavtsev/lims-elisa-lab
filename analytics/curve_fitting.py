"""Curve fitting utilities for ELISA calibration."""
import math
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Tuple


@dataclass
class FitResult:
    model: str
    parameters: Dict[str, float]
    r_squared: float
    predictions: List[Tuple[float, float]]


def four_parameter_logistic(x: float, a: float, b: float, c: float, d: float) -> float:
    return d + (a - d) / (1 + (x / c) ** b)


def five_parameter_logistic(x: float, a: float, b: float, c: float, d: float, g: float) -> float:
    return d + (a - d) / ((1 + (x / c) ** b) ** g)


def _r_squared(observed: List[float], predicted: List[float]) -> float:
    mean_obs = sum(observed) / len(observed)
    ss_tot = sum((o - mean_obs) ** 2 for o in observed)
    ss_res = sum((o - p) ** 2 for o, p in zip(observed, predicted))
    return 1 - ss_res / ss_tot if ss_tot else 0.0


def _finite_difference(func: Callable[[List[float]], float], params: List[float], epsilon: float = 1e-4) -> List[float]:
    gradients = []
    for idx, value in enumerate(params):
        params[idx] = value + epsilon
        plus = func(params)
        params[idx] = value - epsilon
        minus = func(params)
        params[idx] = value
        gradients.append((plus - minus) / (2 * epsilon))
    return gradients


def _gradient_descent(
    loss_fn: Callable[[List[float]], float],
    initial_params: List[float],
    learning_rate: float = 1e-3,
    iterations: int = 500,
) -> List[float]:
    params = list(initial_params)
    for _ in range(iterations):
        grads = _finite_difference(loss_fn, params)
        params = [p - learning_rate * g for p, g in zip(params, grads)]
    return params


def fit_4pl(xs: Iterable[float], ys: Iterable[float]) -> FitResult:
    x_list = list(xs)
    y_list = list(ys)
    a0 = min(y_list)
    d0 = max(y_list)
    c0 = sum(x_list) / len(x_list)
    b0 = 1.0

    def loss(params: List[float]) -> float:
        a, b, c, d = params
        preds = [four_parameter_logistic(x, a, b, c, d) for x in x_list]
        return sum((p - y) ** 2 for p, y in zip(preds, y_list))

    a, b, c, d = _gradient_descent(
        loss,
        [a0, b0, c0, d0],
        learning_rate=5e-4,
        iterations=1500,
    )
    predictions = [(x, four_parameter_logistic(x, a, b, c, d)) for x in x_list]
    r2 = _r_squared(y_list, [p for _, p in predictions])
    return FitResult(model="4PL", parameters={"a": a, "b": b, "c": c, "d": d}, r_squared=r2, predictions=predictions)


def fit_5pl(xs: Iterable[float], ys: Iterable[float]) -> FitResult:
    x_list = list(xs)
    y_list = list(ys)
    a0 = min(y_list)
    d0 = max(y_list)
    c0 = sum(x_list) / len(x_list)
    b0 = 1.0
    g0 = 1.0

    def loss(params: List[float]) -> float:
        a, b, c, d, g = params
        preds = [five_parameter_logistic(x, a, b, c, d, g) for x in x_list]
        return sum((p - y) ** 2 for p, y in zip(preds, y_list))

    a, b, c, d, g = _gradient_descent(
        loss,
        [a0, b0, c0, d0, g0],
        learning_rate=2e-4,
        iterations=1800,
    )
    predictions = [(x, five_parameter_logistic(x, a, b, c, d, g)) for x in x_list]
    r2 = _r_squared(y_list, [p for _, p in predictions])
    return FitResult(
        model="5PL",
        parameters={"a": a, "b": b, "c": c, "d": d, "g": g},
        r_squared=r2,
        predictions=predictions,
    )


def plot_curve(result: FitResult, points: int = 20) -> List[Tuple[float, float]]:
    xs = [p[0] for p in result.predictions]
    min_x, max_x = min(xs), max(xs)
    span = max_x - min_x if max_x != min_x else 1.0
    curve_points = []
    for i in range(points):
        x = min_x + span * i / (points - 1)
        if result.model == "4PL":
            params = result.parameters
            y = four_parameter_logistic(x, params["a"], params["b"], params["c"], params["d"])
        else:
            params = result.parameters
            y = five_parameter_logistic(
                x, params["a"], params["b"], params["c"], params["d"], params["g"]
            )
        curve_points.append((x, y))
    return curve_points

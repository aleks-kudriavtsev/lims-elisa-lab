"""Curve fitting utilities for ELISA calibration."""
import math
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Tuple

import importlib.util


@dataclass
class FitResult:
    model: str
    parameters: Dict[str, float]
    r_squared: float
    predictions: List[Tuple[float, float]]
    converged: bool
    status: str


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
    max_iterations: int = 500,
    tolerance: float = 1e-6,
) -> Tuple[List[float], bool, str]:
    params = list(initial_params)
    previous_loss = loss_fn(params)
    for iteration in range(max_iterations):
        grads = _finite_difference(loss_fn, params)
        if max(abs(g) for g in grads) < tolerance:
            return params, True, "Converged by gradient tolerance"
        params = [p - learning_rate * g for p, g in zip(params, grads)]
        current_loss = loss_fn(params)
        if abs(previous_loss - current_loss) < tolerance:
            return params, True, "Converged by tolerance"
        previous_loss = current_loss
    return params, False, "Maximum iterations reached"


def _validate_inputs(xs: Iterable[float], ys: Iterable[float]) -> Tuple[List[float], List[float]]:
    x_list = list(xs)
    y_list = list(ys)
    if not x_list or not y_list:
        raise ValueError("xs and ys must be non-empty")
    if len(x_list) != len(y_list):
        raise ValueError("xs and ys must have the same length")
    if any(x <= 0 for x in x_list):
        raise ValueError("Concentrations must be positive for logistic fitting")
    return x_list, y_list


def _maybe_import_scipy_optimize():
    if importlib.util.find_spec("scipy") is None:
        return None
    from scipy import optimize  # type: ignore

    return optimize


def fit_4pl(
    xs: Iterable[float],
    ys: Iterable[float],
    *,
    backend: str = "auto",
    learning_rate: float = 5e-4,
    max_iterations: int = 4000,
    tolerance: float = 1e-6,
) -> FitResult:
    x_list, y_list = _validate_inputs(xs, ys)
    a0 = min(y_list)
    d0 = max(y_list)
    c0 = sum(x_list) / len(x_list)
    b0 = 1.0

    optimize = _maybe_import_scipy_optimize()
    use_scipy = backend == "scipy" or (backend == "auto" and optimize is not None)

    if use_scipy and optimize is not None:
        try:
            params, _ = optimize.curve_fit(
                four_parameter_logistic,
                x_list,
                y_list,
                p0=[a0, b0, max(c0, 1e-6), d0],
                bounds=(
                    [-math.inf, 0.0, 1e-6, -math.inf],
                    [math.inf, math.inf, math.inf, math.inf],
                ),
                maxfev=5000,
            )
            status = "SciPy backend converged"
            converged = True
        except Exception as exc:  # pragma: no cover - error path depends on SciPy availability
            params = [a0, b0, c0, d0]
            status = f"SciPy backend failed: {exc}"
            converged = False
    else:
        params, converged, status = _gradient_descent(
            loss_fn=lambda p: sum(
                (
                    four_parameter_logistic(x, p[0], p[1], p[2], p[3])
                    - y
                )
                ** 2
                for x, y in zip(x_list, y_list)
            ),
            initial_params=[a0, b0, max(c0, 1e-6), d0],
            learning_rate=learning_rate,
            max_iterations=max_iterations,
            tolerance=tolerance,
        )
    a, b, c, d = params
    predictions = [(x, four_parameter_logistic(x, a, b, c, d)) for x in x_list]
    r2 = _r_squared(y_list, [p for _, p in predictions])
    return FitResult(
        model="4PL",
        parameters={"a": a, "b": b, "c": c, "d": d},
        r_squared=r2,
        predictions=predictions,
        converged=converged,
        status=status,
    )


def fit_5pl(
    xs: Iterable[float],
    ys: Iterable[float],
    *,
    backend: str = "auto",
    learning_rate: float = 5e-4,
    max_iterations: int = 8000,
    tolerance: float = 1e-6,
) -> FitResult:
    x_list, y_list = _validate_inputs(xs, ys)
    a0 = min(y_list)
    d0 = max(y_list)
    c0 = sum(x_list) / len(x_list)
    b0 = 1.0
    g0 = 1.0

    optimize = _maybe_import_scipy_optimize()
    use_scipy = backend == "scipy" or (backend == "auto" and optimize is not None)

    if use_scipy and optimize is not None:
        try:
            params, _ = optimize.curve_fit(
                five_parameter_logistic,
                x_list,
                y_list,
                p0=[a0, b0, max(c0, 1e-6), d0, g0],
                bounds=(
                    [-math.inf, 0.0, 1e-6, -math.inf, 1e-6],
                    [math.inf, math.inf, math.inf, math.inf, math.inf],
                ),
                maxfev=7000,
            )
            status = "SciPy backend converged"
            converged = True
        except Exception as exc:  # pragma: no cover - error path depends on SciPy availability
            params = [a0, b0, max(c0, 1e-6), d0, g0]
            status = f"SciPy backend failed: {exc}"
            converged = False
    else:
        params, converged, status = _gradient_descent(
            loss_fn=lambda p: sum(
                (
                    five_parameter_logistic(x, p[0], p[1], p[2], p[3], p[4])
                    - y
                )
                ** 2
                for x, y in zip(x_list, y_list)
            ),
            initial_params=[a0, b0, max(c0, 1e-6), d0, g0],
            learning_rate=learning_rate,
            max_iterations=max_iterations,
            tolerance=tolerance,
        )
    a, b, c, d, g = params
    predictions = [(x, five_parameter_logistic(x, a, b, c, d, g)) for x in x_list]
    r2 = _r_squared(y_list, [p for _, p in predictions])
    return FitResult(
        model="5PL",
        parameters={"a": a, "b": b, "c": c, "d": d, "g": g},
        r_squared=r2,
        predictions=predictions,
        converged=converged,
        status=status,
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

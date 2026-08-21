"""Finite decision calculus for representations.

The central object is a finite statistical experiment: a row-stochastic
channel ``E[y][r]`` from world states ``y`` to representation symbols ``r``.
This module keeps the decision problem explicit instead of assigning an
intrinsic quality score to a representation.

Implemented exactly with :class:`fractions.Fraction` for small finite spaces:

* Bayes decision engine for arbitrary finite loss matrices;
* Blackwell garbling feasibility and classification;
* directed deficiency and symmetric Le Cam distance;
* task-sufficient quotients and multi-task quotients;
* epsilon-sufficient partition search;
* a small representation compiler and transformation certificates.

The LP routines use exact vertex enumeration.  That gives auditable rational
certificates for small instances.  Standard LP algorithms have polynomial
worst-case complexity, while this deliberately dependency-free implementation
has an exponential enumeration limit and reports that distinction.
"""

from __future__ import annotations

import argparse
from fractions import Fraction
from itertools import combinations, product
import json
from math import comb, log2
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Iterable, Sequence


ROOT = Path(__file__).resolve().parents[2]
Number = int | float | str | Fraction
Matrix = list[list[Fraction]]


class ExactSolverLimit(RuntimeError):
    """The exact finite solver refused an instance above its audit limit."""


def frac(value: Number) -> Fraction:
    """Convert a finite numeric input without introducing binary float noise."""
    if isinstance(value, Fraction):
        return value
    if isinstance(value, bool):
        return Fraction(int(value), 1)
    if isinstance(value, float):
        return Fraction(str(value))
    return Fraction(value)


def _matrix(values: Sequence[Sequence[Number]]) -> Matrix:
    return [[frac(value) for value in row] for row in values]


def _shape(matrix: Matrix) -> tuple[int, int]:
    rows = len(matrix)
    cols = len(matrix[0]) if rows else 0
    if rows == 0 or cols == 0 or any(len(row) != cols for row in matrix):
        raise ValueError("matrix must be non-empty and rectangular")
    return rows, cols


def _validate_distribution(values: Sequence[Number], name: str) -> list[Fraction]:
    result = [frac(value) for value in values]
    if not result or any(value < 0 for value in result):
        raise ValueError(f"{name} must be a non-negative non-empty vector")
    if sum(result) != 1:
        raise ValueError(f"{name} must sum exactly to 1")
    return result


def validate_experiment(values: Sequence[Sequence[Number]]) -> Matrix:
    experiment = _matrix(values)
    states, symbols = _shape(experiment)
    if any(value < 0 for row in experiment for value in row):
        raise ValueError("experiment probabilities must be non-negative")
    if any(sum(row) != 1 for row in experiment):
        raise ValueError("each experiment state row must sum to 1")
    return experiment


def validate_losses(values: Sequence[Sequence[Number]], states: int) -> Matrix:
    losses = _matrix(values)
    loss_states, actions = _shape(losses)
    if loss_states != states:
        raise ValueError("loss rows must match experiment states")
    return losses


def _float(value: Fraction | None) -> float | None:
    return float(value) if value is not None else None


def _fraction_text(value: Fraction | None) -> str | None:
    return str(value) if value is not None else None


def _serialize_matrix(matrix: Matrix) -> list[list[str]]:
    return [[str(value) for value in row] for row in matrix]


def _matmul(left: Matrix, right: Matrix) -> Matrix:
    left_rows, left_cols = _shape(left)
    right_rows, right_cols = _shape(right)
    if left_cols != right_rows:
        raise ValueError("matrix dimensions do not compose")
    return [
        [sum(left[i][k] * right[k][j] for k in range(left_cols)) for j in range(right_cols)]
        for i in range(left_rows)
    ]


def _matrix_residual(left: Matrix, right: Matrix) -> Matrix:
    if _shape(left) != _shape(right):
        raise ValueError("residual matrices must have equal shape")
    return [[left[i][j] - right[i][j] for j in range(len(left[0]))] for i in range(len(left))]


def _max_abs(matrix: Matrix) -> Fraction:
    return max((abs(value) for row in matrix for value in row), default=Fraction(0))


def bayes_decision_engine(
    prior: Sequence[Number],
    experiment: Sequence[Sequence[Number]],
    losses: Sequence[Sequence[Number]],
    actions: Sequence[Any] | None = None,
) -> dict[str, Any]:
    """Compute exact posterior, Bayes action sets, policy, and Bayes risk.

    ``experiment[y][r]`` is ``P(R=r | Y=y)`` and ``losses[y][a]`` is
    ``L(y,a)``.  All finite losses are allowed, including negative or tied
    values.  A zero-probability symbol has no posterior and all actions are
    reported as ties because it contributes no risk.
    """
    pi = _validate_distribution(prior, "prior")
    channel = validate_experiment(experiment)
    states, symbols = _shape(channel)
    if len(pi) != states:
        raise ValueError("prior length must match experiment states")
    loss = validate_losses(losses, states)
    action_count = len(loss[0])
    action_labels = list(actions) if actions is not None else list(range(action_count))
    if len(action_labels) != action_count:
        raise ValueError("action labels must match loss columns")

    joint = [[pi[y] * channel[y][r] for r in range(symbols)] for y in range(states)]
    signal_masses = [sum(joint[y][r] for y in range(states)) for r in range(symbols)]
    posteriors: list[list[Fraction] | None] = []
    policy: list[list[Any]] = []
    signal_details = []
    bayes_risk = Fraction(0)
    for r in range(symbols):
        mass = signal_masses[r]
        posterior = [joint[y][r] / mass for y in range(states)] if mass else None
        posteriors.append(posterior)
        action_risks = [
            sum(joint[y][r] * loss[y][a] for y in range(states))
            for a in range(action_count)
        ]
        minimum = min(action_risks)
        optimal_indices = [a for a, value in enumerate(action_risks) if value == minimum]
        optimal_labels = [action_labels[a] for a in optimal_indices]
        policy.append(optimal_labels)
        bayes_risk += minimum
        signal_details.append({
            "symbol": r,
            "marginal": _fraction_text(mass),
            "marginal_float": _float(mass),
            "posterior": (
                [_fraction_text(value) for value in posterior] if posterior is not None else None
            ),
            "posterior_float": (
                [_float(value) for value in posterior] if posterior is not None else None
            ),
            "action_risks": [_fraction_text(value) for value in action_risks],
            "action_risks_float": [_float(value) for value in action_risks],
            "optimal_actions": optimal_labels,
        })
    return {
        "prior": [_fraction_text(value) for value in pi],
        "experiment": _serialize_matrix(channel),
        "losses": _serialize_matrix(loss),
        "actions": action_labels,
        "posteriors": signal_details,
        "policy": policy,
        "bayes_risk": _fraction_text(bayes_risk),
        "bayes_risk_float": _float(bayes_risk),
        "internal": {
            "prior": pi,
            "experiment": channel,
            "losses": loss,
            "optimal_action_indices": [
                [action_labels.index(action) for action in labels] for labels in policy
            ],
            "signal_masses": signal_masses,
            "bayes_risk": bayes_risk,
        },
    }


def mutual_information(
    prior: Sequence[Number], experiment: Sequence[Sequence[Number]]
) -> float:
    """Compute I(Y;R) for a finite experiment in bits.

    This quantity is reported only as a contrast.  It is not used to replace
    task-specific Bayes risk or Blackwell comparison.
    """
    pi = _validate_distribution(prior, "prior")
    channel = validate_experiment(experiment)
    states, symbols = _shape(channel)
    if len(pi) != states:
        raise ValueError("prior length must match experiment states")
    masses = [sum(pi[y] * channel[y][r] for y in range(states)) for r in range(symbols)]
    information = 0.0
    for y in range(states):
        for r in range(symbols):
            joint = pi[y] * channel[y][r]
            if joint and masses[r]:
                information += float(joint) * log2(float(joint / (pi[y] * masses[r])))
    return information


def _rref_solve(equations: list[list[Fraction]], variables: int) -> tuple[list[Fraction], int] | None:
    """Solve an overdetermined exact linear system, requiring a unique solution."""
    if not equations:
        return None
    table = [[frac(value) for value in row] for row in equations]
    rows = len(table)
    cols = variables
    pivot_row = 0
    pivots: list[int] = []
    for col in range(cols):
        pivot = next((row for row in range(pivot_row, rows) if table[row][col] != 0), None)
        if pivot is None:
            continue
        table[pivot_row], table[pivot] = table[pivot], table[pivot_row]
        divisor = table[pivot_row][col]
        table[pivot_row] = [value / divisor for value in table[pivot_row]]
        for row in range(rows):
            if row != pivot_row and table[row][col] != 0:
                factor = table[row][col]
                table[row] = [
                    table[row][j] - factor * table[pivot_row][j]
                    for j in range(cols + 1)
                ]
        pivots.append(col)
        pivot_row += 1
        if pivot_row == rows:
            break
    for row in table:
        if all(row[col] == 0 for col in range(cols)) and row[cols] != 0:
            return None
    if len(pivots) < cols:
        return None
    solution = [Fraction(0) for _ in range(cols)]
    for row, col in enumerate(pivots[:cols]):
        solution[col] = table[row][cols]
    return solution, len(pivots)


def _rank(equations: list[list[Fraction]], variables: int) -> int:
    if not equations:
        return 0
    table = [[frac(value) for value in row[:-1]] + [frac(row[-1])] for row in equations]
    rows = len(table)
    pivot_row = 0
    for col in range(variables):
        pivot = next((row for row in range(pivot_row, rows) if table[row][col] != 0), None)
        if pivot is None:
            continue
        table[pivot_row], table[pivot] = table[pivot], table[pivot_row]
        divisor = table[pivot_row][col]
        table[pivot_row] = [value / divisor for value in table[pivot_row]]
        for row in range(pivot_row + 1, rows):
            if table[row][col] != 0:
                factor = table[row][col]
                table[row] = [
                    table[row][j] - factor * table[pivot_row][j]
                    for j in range(variables + 1)
                ]
        pivot_row += 1
    return pivot_row


def _vertex_lp(
    variables: int,
    equalities: list[list[Fraction]],
    inequalities: list[list[Fraction]],
    objective: list[Fraction],
    *,
    maximize: bool = False,
    max_combinations: int = 250_000,
) -> tuple[list[Fraction], Fraction] | None:
    """Minimize a small rational LP by exact vertex enumeration.

    Every inequality is represented as ``a*x <= b``.  Non-negativity must be
    supplied by the caller.  A feasible bounded LP has an optimum at a vertex;
    active inequality subsets are enumerated until the equality system is
    full-rank.  This is an audit-grade method for small spaces, not the claim
    that all LPs should be solved this way.
    """
    equality_rank = _rank(equalities, variables)
    needed = variables - equality_rank
    if needed < 0:
        return None
    available = len(inequalities)
    combinations_count = comb(available, needed) if needed <= available else 0
    if combinations_count > max_combinations:
        raise ExactSolverLimit(
            f"vertex LP needs {combinations_count} active sets; limit={max_combinations}"
        )
    best_solution: list[Fraction] | None = None
    best_value: Fraction | None = None
    for active_indices in combinations(range(available), needed):
        equations = equalities + [inequalities[index] for index in active_indices]
        solved = _rref_solve(equations, variables)
        if solved is None:
            continue
        solution, _ = solved
        if any(value < 0 for value in solution):
            continue
        if any(
            sum(row[index] * solution[index] for index in range(variables)) > row[-1]
            for row in inequalities
        ):
            continue
        value = sum(objective[index] * solution[index] for index in range(variables))
        if maximize:
            better = best_value is None or value > best_value
        else:
            better = best_value is None or value < best_value
        if better:
            best_solution, best_value = solution, value
    if best_solution is None or best_value is None:
        return None
    return best_solution, best_value


def _nonnegative_constraints(variables: int) -> list[list[Fraction]]:
    return [[Fraction(-1 if index == variable else 0) for index in range(variables)] + [Fraction(0)] for variable in range(variables)]


def _channel_variable_index(source_signal: int, target_signal: int, target_count: int) -> int:
    return source_signal * target_count + target_signal


def _channel_from_vector(vector: list[Fraction], source_count: int, target_count: int) -> Matrix:
    return [
        [frac(vector[_channel_variable_index(source, target, target_count)]) for target in range(target_count)]
        for source in range(source_count)
    ]


def _garbling_constraints(
    source: Matrix,
    target: Matrix,
    *,
    equality_mode: bool,
) -> tuple[int, list[list[Fraction]], list[list[Fraction]]]:
    states, source_count = _shape(source)
    target_states, target_count = _shape(target)
    if states != target_states:
        raise ValueError("experiments must have equal state counts")
    variables = source_count * target_count
    equalities: list[list[Fraction]] = []
    for source_signal in range(source_count):
        row = [Fraction(0) for _ in range(variables + 1)]
        for target_signal in range(target_count):
            row[_channel_variable_index(source_signal, target_signal, target_count)] = 1
        row[-1] = 1
        equalities.append(row)
    if equality_mode:
        for state in range(states):
            for target_signal in range(target_count):
                row = [Fraction(0) for _ in range(variables + 1)]
                for source_signal in range(source_count):
                    row[_channel_variable_index(source_signal, target_signal, target_count)] = source[state][source_signal]
                row[-1] = target[state][target_signal]
                equalities.append(row)
        return variables, equalities, _nonnegative_constraints(variables)
    return variables, equalities, []


def find_blackwell_garbling(
    source_experiment: Sequence[Sequence[Number]],
    target_experiment: Sequence[Sequence[Number]],
    *,
    max_combinations: int = 250_000,
) -> dict[str, Any]:
    """Find an exact stochastic channel ``K`` with ``source*K = target``."""
    source = validate_experiment(source_experiment)
    target = validate_experiment(target_experiment)
    variables, equalities, inequalities = _garbling_constraints(source, target, equality_mode=True)
    objective = [Fraction(0) for _ in range(variables)]
    solved = _vertex_lp(
        variables,
        equalities,
        inequalities,
        objective,
        max_combinations=max_combinations,
    )
    source_count = len(source[0])
    target_count = len(target[0])
    if solved is None:
        return {
            "exists": False,
            "channel": None,
            "residual": None,
            "residual_linf": None,
            "certificate": "no feasible stochastic channel satisfies source*K=target",
        }
    vector, _ = solved
    channel = _channel_from_vector(vector, source_count, target_count)
    residual = _matrix_residual(_matmul(source, channel), target)
    return {
        "exists": _max_abs(residual) == 0,
        "channel": _serialize_matrix(channel),
        "residual": _serialize_matrix(residual),
        "residual_linf": _fraction_text(_max_abs(residual)),
        "certificate": "K is row-stochastic and source*K equals target exactly",
        "internal_channel": channel,
    }


def compare_blackwell(
    first: Sequence[Sequence[Number]],
    second: Sequence[Sequence[Number]],
    *,
    max_combinations: int = 250_000,
) -> dict[str, Any]:
    """Classify two finite experiments from the first experiment's viewpoint."""
    try:
        first_matrix = validate_experiment(first)
        second_matrix = validate_experiment(second)
        if len(first_matrix) != len(second_matrix):
            raise ValueError("state counts differ")
        forward = find_blackwell_garbling(first_matrix, second_matrix, max_combinations=max_combinations)
        reverse = find_blackwell_garbling(second_matrix, first_matrix, max_combinations=max_combinations)
    except (ValueError, ExactSolverLimit) as error:
        return {"classification": "INVALID", "reason": str(error)}
    if forward["exists"] and reverse["exists"]:
        classification = "EQUIVALENT"
    elif forward["exists"]:
        classification = "DOMINATES"
    elif reverse["exists"]:
        classification = "DOMINATED_BY"
    else:
        classification = "INCOMPARABLE"
    return {
        "classification": classification,
        "first_to_second": forward,
        "second_to_first": reverse,
        "reverse_only_dominance": reverse["exists"] and not forward["exists"],
        "meaning": {
            "DOMINATES": "the second representation is a garbling of the first",
            "DOMINATED_BY": "the first representation is a garbling of the second",
            "EQUIVALENT": "both directions have stochastic garbling witnesses",
            "INCOMPARABLE": "neither direction has a stochastic garbling witness",
            "INVALID": "input is not a pair of compatible finite experiments",
        }[classification],
    }


def _deficiency_lp(
    source: Matrix,
    target: Matrix,
    *,
    max_combinations: int = 250_000,
) -> dict[str, Any]:
    """Solve directed deficiency via an exact finite LP."""
    states, source_count = _shape(source)
    target_states, target_count = _shape(target)
    if states != target_states:
        raise ValueError("experiments must have equal state counts")

    # For a binary target alphabet, total variation between two row
    # distributions is exactly the absolute difference of the first cell.
    # Eliminating the second channel column and all cell-wise slacks reduces
    # the LP to source_count channel variables plus t.
    if target_count == 2:
        variables = source_count + 1
        t_index = source_count
        inequalities: list[list[Fraction]] = []
        for state in range(states):
            plus = [Fraction(0) for _ in range(variables + 1)]
            minus = [Fraction(0) for _ in range(variables + 1)]
            for source_signal in range(source_count):
                plus[source_signal] = -source[state][source_signal]
                minus[source_signal] = source[state][source_signal]
            plus[t_index] = -1
            minus[t_index] = -1
            plus[-1] = -target[state][0]
            minus[-1] = target[state][0]
            inequalities.extend([plus, minus])
        for source_signal in range(source_count):
            upper = [Fraction(0) for _ in range(variables + 1)]
            lower = [Fraction(0) for _ in range(variables + 1)]
            upper[source_signal] = 1
            upper[-1] = 1
            lower[source_signal] = -1
            inequalities.extend([upper, lower])
        nonnegative_t = [Fraction(0) for _ in range(variables + 1)]
        nonnegative_t[t_index] = -1
        inequalities.append(nonnegative_t)
        objective = [Fraction(0) for _ in range(variables)]
        objective[t_index] = 1
        solved = _vertex_lp(
            variables,
            [],
            inequalities,
            objective,
            max_combinations=max_combinations,
        )
        if solved is None:
            raise ValueError("binary-target deficiency LP is infeasible")
        vector, value = solved
        channel = [[vector[source_signal], 1 - vector[source_signal]] for source_signal in range(source_count)]
        simulated = _matmul(source, channel)
        residual = _matrix_residual(simulated, target)
        return {
            "deficiency": _fraction_text(value),
            "deficiency_float": _float(value),
            "channel": _serialize_matrix(channel),
            "simulated_target": _serialize_matrix(simulated),
            "residual": _serialize_matrix(residual),
            "residual_linf": _fraction_text(_max_abs(residual)),
            "certificate": "binary-target reduction: TV equals the absolute first-cell residual",
            "internal_channel": channel,
        }

    # Eliminate the final column of every row of K.  For larger target
    # alphabets, enumerate residual sign patterns and solve the resulting
    # linear pieces.  This is exact for small finite spaces and is much smaller
    # than introducing one slack variable per residual cell.
    free_channel_count = source_count * (target_count - 1)
    t_index = free_channel_count
    variables = free_channel_count + 1
    residuals: list[tuple[Fraction, list[Fraction]]] = []
    for state in range(states):
        for target_signal in range(target_count):
            coefficients = [Fraction(0) for _ in range(variables)]
            if target_signal < target_count - 1:
                constant = target[state][target_signal]
                for source_signal in range(source_count):
                    coefficients[source_signal * (target_count - 1) + target_signal] = -source[state][source_signal]
            else:
                constant = target[state][target_signal] - 1
                for source_signal in range(source_count):
                    for free_target in range(target_count - 1):
                        coefficients[source_signal * (target_count - 1) + free_target] = source[state][source_signal]
            residuals.append((constant, coefficients))
    base_inequalities = _nonnegative_constraints(variables)
    for source_signal in range(source_count):
        row = [Fraction(0) for _ in range(variables + 1)]
        for free_target in range(target_count - 1):
            row[source_signal * (target_count - 1) + free_target] = 1
        row[-1] = 1
        base_inequalities.append(row)
    objective = [Fraction(0) for _ in range(variables)]
    objective[t_index] = 1
    best_solution: list[Fraction] | None = None
    best_value: Fraction | None = None
    for signs in product((-1, 1), repeat=len(residuals)):
        inequalities = [row[:] for row in base_inequalities]
        for sign, (constant, coefficients) in zip(signs, residuals):
            # sign * residual >= 0
            row = [-sign * coefficient for coefficient in coefficients] + [sign * constant]
            inequalities.append(row)
        for state in range(states):
            row = [Fraction(0) for _ in range(variables + 1)]
            constant_sum = Fraction(0)
            for offset in range(target_count):
                constant, coefficients = residuals[state * target_count + offset]
                sign = signs[state * target_count + offset]
                constant_sum += sign * constant
                for variable in range(variables):
                    row[variable] += sign * coefficients[variable]
            row[t_index] -= 2
            row[-1] = -constant_sum
            inequalities.append(row)
        solved = _vertex_lp(
            variables,
            [],
            inequalities,
            objective,
            max_combinations=max_combinations,
        )
        if solved is None:
            continue
        solution, value = solved
        if best_value is None or value < best_value:
            best_solution, best_value = solution, value
    if best_solution is None or best_value is None:
        raise ValueError("reduced deficiency LP is infeasible")
    channel = []
    for source_signal in range(source_count):
        free = [best_solution[source_signal * (target_count - 1) + target_signal] for target_signal in range(target_count - 1)]
        channel.append(free + [1 - sum(free)])
    simulated = _matmul(source, channel)
    residual = _matrix_residual(simulated, target)
    return {
        "deficiency": _fraction_text(best_value),
        "deficiency_float": _float(best_value),
        "channel": _serialize_matrix(channel),
        "simulated_target": _serialize_matrix(simulated),
        "residual": _serialize_matrix(residual),
        "residual_linf": _fraction_text(_max_abs(residual)),
        "certificate": "reduced exact LP: final channel columns eliminated and residual signs enumerated",
        "internal_channel": channel,
    }

    channel_variables = source_count * target_count
    slack_offset = channel_variables
    slack_variables = states * target_count
    t_index = slack_offset + slack_variables
    variables = t_index + 1
    equalities: list[list[Fraction]] = []
    for source_signal in range(source_count):
        row = [Fraction(0) for _ in range(variables + 1)]
        for target_signal in range(target_count):
            row[_channel_variable_index(source_signal, target_signal, target_count)] = 1
        row[-1] = 1
        equalities.append(row)
    inequalities: list[list[Fraction]] = []
    for state in range(states):
        for target_signal in range(target_count):
            slack_index = slack_offset + state * target_count + target_signal
            plus = [Fraction(0) for _ in range(variables + 1)]
            minus = [Fraction(0) for _ in range(variables + 1)]
            for source_signal in range(source_count):
                index = _channel_variable_index(source_signal, target_signal, target_count)
                plus[index] = -source[state][source_signal]
                minus[index] = source[state][source_signal]
            plus[slack_index] = -1
            minus[slack_index] = -1
            plus[-1] = -target[state][target_signal]
            minus[-1] = target[state][target_signal]
            inequalities.extend([plus, minus])
        row = [Fraction(0) for _ in range(variables + 1)]
        for target_signal in range(target_count):
            row[slack_offset + state * target_count + target_signal] = 1
        row[t_index] = -2
        row[-1] = 0
        inequalities.append(row)
    inequalities.extend(_nonnegative_constraints(variables))
    objective = [Fraction(0) for _ in range(variables)]
    objective[t_index] = 1
    solved = _vertex_lp(
        variables,
        equalities,
        inequalities,
        objective,
        max_combinations=max_combinations,
    )
    if solved is None:
        raise ValueError("deficiency LP is infeasible")
    vector, value = solved
    channel = _channel_from_vector(vector, source_count, target_count)
    simulated = _matmul(source, channel)
    residual = _matrix_residual(simulated, target)
    return {
        "deficiency": _fraction_text(value),
        "deficiency_float": _float(value),
        "channel": _serialize_matrix(channel),
        "simulated_target": _serialize_matrix(simulated),
        "residual": _serialize_matrix(residual),
        "residual_linf": _fraction_text(_max_abs(residual)),
        "certificate": "K is stochastic; 1/2 * max_state L1 residual is minimized",
        "internal_channel": channel,
    }


def directed_deficiency(
    source_experiment: Sequence[Sequence[Number]],
    target_experiment: Sequence[Sequence[Number]],
    *,
    max_combinations: int = 250_000,
) -> dict[str, Any]:
    """Compute ``delta(source,target)``: simulate target from source."""
    try:
        source = validate_experiment(source_experiment)
        target = validate_experiment(target_experiment)
        # Exact Blackwell simulation is already a zero-deficiency certificate.
        # This avoids solving the larger absolute-residual LP a second time.
        exact = find_blackwell_garbling(source, target, max_combinations=max_combinations)
        if exact["exists"]:
            return {
                "status": "EXACT",
                "direction": "source_to_target",
                "deficiency": "0",
                "deficiency_float": 0.0,
                "channel": exact["channel"],
                "simulated_target": _serialize_matrix(target),
                "residual": exact["residual"],
                "residual_linf": exact["residual_linf"],
                "certificate": "Blackwell garbling witness; deficiency is exactly zero",
                "internal_channel": exact["internal_channel"],
            }
        result = _deficiency_lp(source, target, max_combinations=max_combinations)
    except (ValueError, ExactSolverLimit) as error:
        return {"status": "INVALID", "reason": str(error)}
    result["status"] = "EXACT"
    result["direction"] = "source_to_target"
    return result


def le_cam_distance(
    first: Sequence[Sequence[Number]],
    second: Sequence[Sequence[Number]],
    *,
    max_combinations: int = 250_000,
) -> dict[str, Any]:
    """Return both deficiencies and their max symmetrization."""
    forward = directed_deficiency(first, second, max_combinations=max_combinations)
    reverse = directed_deficiency(second, first, max_combinations=max_combinations)
    if forward.get("status") != "EXACT" or reverse.get("status") != "EXACT":
        return {"status": "INVALID", "forward": forward, "reverse": reverse}
    value = max(frac(forward["deficiency"]), frac(reverse["deficiency"]))
    return {
        "status": "EXACT",
        "forward": forward,
        "reverse": reverse,
        "le_cam_distance": _fraction_text(value),
        "le_cam_distance_float": _float(value),
        "meaning": "max of directed deficiencies; symmetric pseudometric on finite experiments",
    }


def _partitions(n: int, *, max_count: int = 250_000) -> Iterable[tuple[tuple[int, ...], ...]]:
    """Generate canonical set partitions in restricted-growth order."""
    if n < 1:
        return
    yielded = 0
    blocks: list[list[int]] = []
    assignment = [0] * n

    def visit(index: int):
        nonlocal yielded
        if yielded >= max_count:
            raise ExactSolverLimit(f"partition enumeration exceeded limit={max_count}")
        if index == n:
            yielded += 1
            yield tuple(tuple(block) for block in blocks)
            return
        for block_index in range(len(blocks)):
            blocks[block_index].append(index)
            yield from visit(index + 1)
            blocks[block_index].pop()
        blocks.append([index])
        yield from visit(index + 1)
        blocks.pop()

    yield from visit(0)


def partition_channel(signal_count: int, blocks: Sequence[Sequence[int]]) -> Matrix:
    if not blocks or sorted(index for block in blocks for index in block) != list(range(signal_count)):
        raise ValueError("blocks must partition every signal exactly once")
    channel = [[Fraction(0) for _ in blocks] for _ in range(signal_count)]
    for block_index, block in enumerate(blocks):
        for signal in block:
            channel[signal][block_index] = 1
    return channel


def quotient_experiment(experiment: Sequence[Sequence[Number]], blocks: Sequence[Sequence[int]]) -> Matrix:
    source = validate_experiment(experiment)
    return _matmul(source, partition_channel(len(source[0]), blocks))


def _optimal_masks(engine: dict[str, Any]) -> list[int]:
    masks = []
    for signal in engine["posteriors"]:
        mask = 0
        for action in signal["optimal_actions"]:
            index = engine["actions"].index(action)
            mask |= 1 << index
        masks.append(mask)
    return masks


def _minimum_cover(
    universe_size: int,
    candidates: Sequence[tuple[Any, int]],
) -> tuple[list[Any], int]:
    """Exact minimum set cover over small signal universes."""
    full = (1 << universe_size) - 1
    dp: list[tuple[Any, ...] | None] = [None] * (1 << universe_size)
    dp[0] = ()
    unique: dict[int, Any] = {}
    for label, mask in candidates:
        if mask:
            unique.setdefault(mask, label)
    candidates = [(label, mask) for mask, label in unique.items()]
    for covered in range(1 << universe_size):
        if dp[covered] is None:
            continue
        for label, mask in candidates:
            new_covered = covered | mask
            proposed = dp[covered] + (label,)
            current = dp[new_covered]
            if current is None or (len(proposed), proposed) < (len(current), current):
                dp[new_covered] = proposed
    if dp[full] is None:
        raise ValueError("optimal-action candidates do not cover all signals")
    chosen = list(dp[full])
    return chosen, len(chosen)


def _greedy_cover_bounds(
    universe_size: int,
    candidates: Sequence[tuple[Any, int]],
) -> dict[str, Any]:
    """Return a feasible cover and elementary certified bounds.

    The lower bound is the usual cardinality bound
    ``ceil(|U| / max_j |S_j|)``.  It is intentionally reported as a bound,
    never as an optimum claim.  This is the fallback used when exact
    bit-mask search is too large.
    """
    full = (1 << universe_size) - 1
    unique: dict[int, Any] = {}
    for label, mask in candidates:
        if mask:
            unique.setdefault(mask, label)
    reduced = [(label, mask) for mask, label in unique.items()]
    uncovered = full
    chosen: list[Any] = []
    while uncovered:
        feasible = [(label, mask) for label, mask in reduced if mask & uncovered]
        if not feasible:
            raise ValueError("candidate family does not cover the universe")
        label, mask = max(feasible, key=lambda item: (item[1] & uncovered).bit_count())
        chosen.append(label)
        uncovered &= ~mask
    maximum = max((mask.bit_count() for _, mask in reduced), default=0)
    lower = (universe_size + maximum - 1) // maximum if maximum else None
    return {
        "chosen": chosen,
        "upper_bound": len(chosen),
        "lower_bound": lower,
        "optimality_gap": None if lower is None else len(chosen) - lower,
        "guarantee": f"greedy set cover cardinality <= H_{universe_size} * optimum; observed upper/lower is reported separately",
    }


def _solve_degree_two_cover(
    masks: Sequence[int],
    action_labels: Sequence[Any],
) -> dict[str, Any]:
    """Solve a cover whose ambiguity hyperedges have size at most two.

    A singleton hyperedge forces its action.  Every remaining hyperedge is
    an edge between two candidate actions, so the residual problem is Vertex
    Cover.  Branching on an uncovered edge is exact and auditable.
    """
    forced: set[int] = set()
    edges: list[tuple[int, int]] = []
    for mask in masks:
        indices = [index for index in range(len(action_labels)) if mask & (1 << index)]
        if not indices:
            raise ValueError("an ambiguity hyperedge has no admissible action")
        if len(indices) == 1:
            forced.add(indices[0])
        else:
            edges.append((indices[0], indices[1]))
    remaining = [edge for edge in edges if not (edge[0] in forced or edge[1] in forced)]
    best: set[int] | None = None
    explored = 0

    def visit(chosen: set[int], pending: list[tuple[int, int]]) -> None:
        nonlocal best, explored
        explored += 1
        if best is not None and len(chosen) >= len(best):
            return
        edge = next((item for item in pending if item[0] not in chosen and item[1] not in chosen), None)
        if edge is None:
            best = set(chosen)
            return
        for endpoint in edge:
            visit(chosen | {endpoint}, pending)

    visit(set(forced), remaining)
    if best is None:
        best = set(forced)
    chosen_labels = [action_labels[index] for index in sorted(best)]
    return {
        "chosen_indices": sorted(best),
        "chosen": chosen_labels,
        "state_count": len(best),
        "nodes_explored": explored,
        "algorithm": "exact Vertex-Cover branching on degree-2 ambiguity hypergraph",
        "complexity": "O(2^|A|) worst case; polynomial verification per branch",
    }


def analyze_decision_ambiguity(
    engine_or_experiment: dict[str, Any] | Sequence[Sequence[Number]],
    prior: Sequence[Number] | None = None,
    losses: Sequence[Sequence[Number]] | None = None,
    actions: Sequence[Any] | None = None,
) -> dict[str, Any]:
    """Build the ambiguity hypergraph induced by Bayes-optimal actions.

    A signal is a hyperedge containing every action that is optimal at that
    signal.  The hypergraph, rather than a domain label, determines whether
    a direct grouping, degree-2 brancher, or general set-cover solver is
    appropriate.
    """
    if isinstance(engine_or_experiment, dict):
        engine = engine_or_experiment
    else:
        if prior is None or losses is None:
            raise ValueError("prior and losses are required for a raw experiment")
        engine = bayes_decision_engine(prior, engine_or_experiment, losses, actions)
    masks = _optimal_masks(engine)
    action_labels = list(engine["actions"])
    action_masks = [0] * len(action_labels)
    hyperedges = []
    for signal, mask in enumerate(masks):
        indices = [index for index in range(len(action_labels)) if mask & (1 << index)]
        hyperedges.append({"signal": signal, "actions": [action_labels[index] for index in indices], "arity": len(indices)})
        for index in indices:
            action_masks[index] |= 1 << signal

    parent = list(range(len(action_labels)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left, right = find(left), find(right)
        if left != right:
            parent[right] = left

    for mask in masks:
        indices = [index for index in range(len(action_labels)) if mask & (1 << index)]
        for index in indices[1:]:
            union(indices[0], index)
    components: dict[int, list[Any]] = {}
    for index, label in enumerate(action_labels):
        components.setdefault(find(index), []).append(label)
    component_indices: dict[int, list[int]] = {}
    for index in range(len(action_labels)):
        component_indices.setdefault(find(index), []).append(index)
    equal_actions = [
        [action_labels[index] for index in range(len(action_labels)) if action_masks[index] == action_masks[representative]]
        for representative in range(len(action_labels))
        if representative == min(
            (index for index in range(len(action_labels)) if action_masks[index] == action_masks[representative]),
            default=representative,
        )
    ]
    dominated_actions = []
    for left in range(len(action_labels)):
        for right in range(len(action_labels)):
            if left != right and action_masks[left] & ~action_masks[right] == 0:
                dominated_actions.append({"dominated": action_labels[left], "by": action_labels[right]})
    maximum_arity = max((mask.bit_count() for mask in masks), default=0)
    maximum_coverage = max((mask.bit_count() for mask in action_masks), default=0)
    lower_bound = (len(masks) + maximum_coverage - 1) // maximum_coverage if maximum_coverage else None
    unique_symbols = [signal for signal, mask in enumerate(masks) if mask.bit_count() == 1]
    ambiguous_symbols = [signal for signal, mask in enumerate(masks) if mask.bit_count() > 1]
    overlap = [
        [
            (action_masks[left] & action_masks[right]).bit_count()
            for right in range(len(action_labels))
        ]
        for left in range(len(action_labels))
    ]
    redundant_symbols = []
    for left in range(len(masks)):
        for right in range(left):
            if masks[left] == masks[right]:
                redundant_symbols.append({"symbol": left, "same_optimal_set_as": right})
    if maximum_arity <= 1:
        regime = "UNIQUE_OPTIMUM"
        recommended = "direct grouping by unique optimal action"
        reason = "every hyperedge is a singleton, so no covering choice remains"
        reductions = ["polynomial direct grouping"]
    elif maximum_arity <= 2:
        regime = "DEGREE_2_AMBIGUITY"
        recommended = "exact Vertex-Cover branching"
        reason = "every ambiguity hyperedge is an edge or forced singleton"
        reductions = ["Vertex-Cover-equivalent degree-2 solver", "forced singleton kernelization"]
    elif len(components) > 1:
        regime = "DECOMPOSABLE_HYPERGRAPH"
        recommended = "component-wise exact set cover"
        reason = "the action-overlap hypergraph splits into independent components"
        reductions = ["component decomposition", "exact set cover per component"]
    else:
        regime = "GENERAL_SET_COVER"
        recommended = "exact bitmask cover or greedy bounded fallback"
        reason = "the incidence hypergraph has general overlapping hyperedges"
        reductions = ["equivalent-action symmetry breaking", "dominated-action pruning"]
    return {
        "symbols": list(range(len(masks))),
        "actions": action_labels,
        "unique_optimum_symbols": unique_symbols,
        "ambiguous_symbols": ambiguous_symbols,
        "ambiguity_cardinalities": [mask.bit_count() for mask in masks],
        "signal_count": len(masks),
        "action_count": len(action_labels),
        "hyperedges": hyperedges,
        "maximum_ambiguity_arity": maximum_arity,
        "action_coverage": {str(label): mask.bit_count() for label, mask in zip(action_labels, action_masks)},
        "action_overlap": overlap,
        "components": list(components.values()),
        "component_indices": list(component_indices.values()),
        "equivalent_action_classes": equal_actions,
        "dominated_actions": dominated_actions,
        "dominated_candidates": dominated_actions,
        "redundant_symbols": redundant_symbols,
        "lower_bound": lower_bound,
        "regime": regime,
        "recommended_algorithm": recommended,
        "reason": reason,
        "exact_easy_reductions": reductions,
        "parameters": {
            "ambiguous_symbol_count": len(ambiguous_symbols),
            "maximum_ambiguity": maximum_arity,
            "action_count": len(action_labels),
            "component_count": len(components),
            "maximum_action_frequency": maximum_coverage,
        },
        "interpretation": "ambiguity is a hypergraph; selector complexity is its minimum action cover",
    }


def adaptive_task_quotient(
    experiment: Sequence[Sequence[Number]],
    prior: Sequence[Number],
    losses: Sequence[Sequence[Number]],
    *,
    actions: Sequence[Any] | None = None,
    exact_signal_limit: int = 22,
) -> dict[str, Any]:
    """Select an exact algorithm from ambiguity structure and report bounds."""
    source = validate_experiment(experiment)
    engine = bayes_decision_engine(prior, source, losses, actions)
    profile = analyze_decision_ambiguity(engine)
    masks = _optimal_masks(engine)
    labels = list(engine["actions"])
    if profile["regime"] == "UNIQUE_OPTIMUM":
        chosen_indices = sorted({index for mask in masks for index in range(len(labels)) if mask & (1 << index)})
        algorithm = "direct grouping by unique optimal action"
        nodes = 1
    elif profile["regime"] == "DEGREE_2_AMBIGUITY":
        result = _solve_degree_two_cover(masks, labels)
        chosen_indices = result["chosen_indices"]
        algorithm = result["algorithm"]
        nodes = result["nodes_explored"]
    elif profile["regime"] == "DECOMPOSABLE_HYPERGRAPH":
        chosen_set: set[int] = set()
        component_nodes = 0
        for component in profile["component_indices"]:
            component_signals = [
                signal for signal, mask in enumerate(masks)
                if any(mask & (1 << action) for action in component)
            ]
            local_index = {signal: offset for offset, signal in enumerate(component_signals)}
            candidates = [
                (
                    action,
                    sum(1 << local_index[signal] for signal in component_signals if masks[signal] & (1 << action)),
                )
                for action in component
            ]
            local_chosen, _ = _minimum_cover(len(component_signals), candidates)
            chosen_set.update(local_chosen)
            component_nodes += 1
        chosen_indices = sorted(chosen_set)
        algorithm = "component-wise exact set-cover dynamic programming"
        nodes = component_nodes
    elif len(masks) <= exact_signal_limit:
        candidates = [
            (index, sum(1 << signal for signal, mask in enumerate(masks) if mask & (1 << index)))
            for index in range(len(labels))
        ]
        chosen, _ = _minimum_cover(len(masks), candidates)
        chosen_indices = list(chosen)
        algorithm = "exact bitmask set-cover dynamic programming"
        nodes = None
    else:
        candidates = [
            (index, sum(1 << signal for signal, mask in enumerate(masks) if mask & (1 << index)))
            for index in range(len(labels))
        ]
        bound = _greedy_cover_bounds(len(masks), candidates)
        chosen_indices = list(bound["chosen"])
        algorithm = "greedy set-cover fallback under exact resource limit"
        nodes = None
    chosen_labels = [labels[index] for index in chosen_indices]
    blocks = _blocks_from_cover(
        len(masks),
        chosen_indices,
        lambda action_index, signal: bool(masks[signal] & (1 << action_index)),
    )
    verification = verify_task_partition(source, prior, losses, blocks)
    exact = algorithm != "greedy set-cover fallback under exact resource limit"
    state_count = len(blocks)
    bounds = {
        "lower_bound": state_count if exact else profile["lower_bound"],
        "upper_bound": state_count,
        "optimality_gap": 0 if exact else state_count - profile["lower_bound"],
        "theoretical_guarantee": (
            "exact certificate"
            if exact
            else f"greedy cover cardinality <= H_{len(masks)} * optimum"
        ),
    }
    return {
        "status": "EXACT" if exact else "BOUNDED_APPROXIMATION",
        "algorithm": algorithm,
        "complexity_regime": profile["regime"],
        "ambiguity": profile,
        "chosen_actions": chosen_labels,
        "chosen_action_indices": chosen_indices,
        "blocks": [list(block) for block in blocks],
        "state_count": state_count,
        "bounds": bounds,
        "nodes_explored": nodes,
        "verification": verification,
    }


def set_cover_reduction_instance(
    universe: Sequence[Any],
    subsets: Sequence[Sequence[Any]],
    k: int,
) -> dict[str, Any]:
    """Construct the polynomial reduction Set-Cover -> task quotient.

    The source experiment is the identity channel on universe elements.  An
    action is a subset, with zero loss exactly on the elements it covers.
    Thus a risk-zero quotient with at most ``k`` blocks exists iff the input
    Set-Cover instance has a cover of size at most ``k``.
    """
    elements = list(universe)
    if not elements or len(set(elements)) != len(elements):
        raise ValueError("universe must contain distinct non-empty elements")
    if k < 0:
        raise ValueError("k must be non-negative")
    element_index = {element: index for index, element in enumerate(elements)}
    normalized: list[list[Any]] = []
    for subset in subsets:
        values = list(dict.fromkeys(subset))
        if any(value not in element_index for value in values):
            raise ValueError("every subset element must belong to universe")
        normalized.append(values)
    covered = set(value for subset in normalized for value in subset)
    if covered != set(elements):
        raise ValueError("subsets must cover the universe for the reduction")
    states = len(elements)
    actions = list(range(len(normalized)))
    losses = [
        [0 if element in subset else 1 for subset in normalized]
        for element in elements
    ]
    identity = [[1 if state == symbol else 0 for symbol in range(states)] for state in range(states)]
    return {
        "universe": elements,
        "subsets": normalized,
        "k": k,
        "experiment": identity,
        "prior": [Fraction(1, states) for _ in range(states)],
        "losses": losses,
        "actions": actions,
        "reduction": {
            "source": "SET-COVER",
            "target": "minimum risk-zero task-sufficient quotient",
            "iff": "cover of size <= k iff quotient of at most k blocks preserves Bayes risk 0",
            "membership": "partition plus one common optimal action per block is a polynomial certificate",
            "hardness": "NP-complete decision problem because Set Cover reduces in polynomial time",
        },
    }


def verify_set_cover_reduction(instance: dict[str, Any]) -> dict[str, Any]:
    """Verify the reduction and solve its small target instance exactly."""
    result = adaptive_task_quotient(instance["experiment"], instance["prior"], instance["losses"])
    cover = result["chosen_actions"]
    return {
        "cover": cover,
        "cover_size": len(cover),
        "k": instance["k"],
        "quotient_blocks": result["blocks"],
        "risk_zero": result["verification"]["preserved"],
        "quotient_yes": result["verification"]["preserved"] and len(cover) <= instance["k"],
        "minimum_cover_certificate": result,
        "theorem_status": "PROVED_FOR_REDUCTION",
    }


def vertex_cover_reduction_instance(
    vertices: Sequence[Any],
    edges: Sequence[tuple[Any, Any]],
    k: int,
) -> dict[str, Any]:
    """Specialize the reduction to Vertex Cover (degree-2 ambiguity)."""
    vertex_list = list(dict.fromkeys(vertices))
    if any(left not in vertex_list or right not in vertex_list for left, right in edges):
        raise ValueError("edge endpoint is absent from vertices")
    if any(left == right for left, right in edges):
        raise ValueError("self-loops are not supported in the simple-graph fixture")
    subsets = [[edge for edge in edges if vertex in edge] for vertex in vertex_list]
    instance = set_cover_reduction_instance(list(edges), subsets, k)
    instance["vertices"] = vertex_list
    instance["edges"] = [list(edge) for edge in edges]
    instance["actions"] = vertex_list
    instance["losses"] = [
        [0 if vertex in edge else 1 for vertex in vertex_list]
        for edge in edges
    ]
    instance["reduction"] = {
        "source": "VERTEX-COVER",
        "target": "minimum risk-zero task quotient with ambiguity arity <= 2",
        "iff": "vertex cover of size <= k iff quotient of at most k blocks preserves Bayes risk 0",
        "hardness": "NP-complete decision problem by the degree-2 Set-Cover specialization",
    }
    return instance


def vertex_cover_reduction_certificate(instance: dict[str, Any]) -> dict[str, Any]:
    result = adaptive_task_quotient(
        instance["experiment"], instance["prior"], instance["losses"], actions=instance["actions"]
    )
    return {
        "chosen_vertices": result["chosen_actions"],
        "cover_size": len(result["chosen_actions"]),
        "k": instance["k"],
        "quotient_blocks": result["blocks"],
        "risk_zero": result["verification"]["preserved"],
        "quotient_yes": result["verification"]["preserved"] and len(result["chosen_actions"]) <= instance["k"],
        "solver": result,
        "theorem_status": "PROVED_FOR_DEGREE_2_REDUCTION",
    }


def find_separation_witnesses(
    first: Sequence[Sequence[Number]],
    second: Sequence[Sequence[Number]],
    *,
    prior_denominator: int = 4,
    max_candidates: int = 100_000,
) -> dict[str, Any]:
    """Search a finite rational loss/prior grid for Blackwell separators."""
    left = validate_experiment(first)
    right = validate_experiment(second)
    if _shape(left) != _shape(right):
        raise ValueError("experiments must have equal shape")
    states, _ = _shape(left)
    if prior_denominator < 1:
        raise ValueError("prior_denominator must be positive")

    def compositions(total: int, parts: int) -> Iterable[tuple[int, ...]]:
        if parts == 1:
            yield (total,)
            return
        for first_part in range(total + 1):
            for tail in compositions(total - first_part, parts - 1):
                yield (first_part,) + tail

    first_witness = None
    second_witness = None
    examined = 0
    for numerators in compositions(prior_denominator, states):
        prior = [Fraction(value, prior_denominator) for value in numerators]
        for bits in product((0, 1), repeat=2 * states):
            losses = [list(bits[2 * state:2 * state + 2]) for state in range(states)]
            left_engine = bayes_decision_engine(prior, left, losses)
            right_engine = bayes_decision_engine(prior, right, losses)
            left_risk = left_engine["internal"]["bayes_risk"]
            right_risk = right_engine["internal"]["bayes_risk"]
            examined += 1
            if left_risk < right_risk and first_witness is None:
                first_witness = {
                    "prior": [_fraction_text(value) for value in prior],
                    "losses": losses,
                    "first_risk": _fraction_text(left_risk),
                    "second_risk": _fraction_text(right_risk),
                }
            if right_risk < left_risk and second_witness is None:
                second_witness = {
                    "prior": [_fraction_text(value) for value in prior],
                    "losses": losses,
                    "first_risk": _fraction_text(left_risk),
                    "second_risk": _fraction_text(right_risk),
                }
            if first_witness is not None and second_witness is not None:
                return {
                    "status": "SEPARATED",
                    "first_better": first_witness,
                    "second_better": second_witness,
                    "examined": examined,
                    "grid": {"prior_denominator": prior_denominator, "loss_values": [0, 1]},
                    "complete": False,
                    "meaning": "finite witnesses show neither experiment uniformly dominates the other",
                }
            if examined >= max_candidates:
                return {
                    "status": "BOUNDED_SEARCH",
                    "first_better": first_witness,
                    "second_better": second_witness,
                    "examined": examined,
                    "grid": {"prior_denominator": prior_denominator, "loss_values": [0, 1]},
                    "complete": False,
                }
    return {
        "status": "NO_GRID_WITNESS",
        "first_better": first_witness,
        "second_better": second_witness,
        "examined": examined,
        "grid": {"prior_denominator": prior_denominator, "loss_values": [0, 1]},
        "complete": True,
    }


def _blocks_from_cover(
    signal_count: int,
    chosen_labels: Sequence[Any],
    compatible: Callable[[Any, int], bool],
) -> list[list[int]]:
    blocks = [[] for _ in chosen_labels]
    for signal in range(signal_count):
        candidate = next(
            (index for index, label in enumerate(chosen_labels) if compatible(label, signal)),
            None,
        )
        if candidate is None:
            raise ValueError("cover reconstruction left a signal uncovered")
        blocks[candidate].append(signal)
    return [block for block in blocks if block]


def verify_task_partition(
    experiment: Sequence[Sequence[Number]],
    prior: Sequence[Number],
    losses: Sequence[Sequence[Number]],
    blocks: Sequence[Sequence[int]],
) -> dict[str, Any]:
    """Verify that a quotient partition preserves exact Bayes risk."""
    original = bayes_decision_engine(prior, experiment, losses)
    quotient = quotient_experiment(experiment, blocks)
    compressed = bayes_decision_engine(prior, quotient, losses)
    delta = compressed["internal"]["bayes_risk"] - original["internal"]["bayes_risk"]
    masks = _optimal_masks(original)
    witnesses = []
    for block in blocks:
        common = (1 << len(losses[0])) - 1
        for signal in block:
            common &= masks[signal]
        actions = [original["actions"][index] for index in range(len(losses[0])) if common & (1 << index)]
        witnesses.append({"block": list(block), "common_optimal_actions": actions})
    return {
        "preserved": delta == 0,
        "blocks": [list(block) for block in blocks],
        "original_bayes_risk": original["bayes_risk"],
        "quotient_bayes_risk": compressed["bayes_risk"],
        "risk_delta": _fraction_text(delta),
        "witnesses": witnesses,
        "quotient_experiment": _serialize_matrix(quotient),
        "original_engine": original,
        "quotient_engine": compressed,
    }


def task_sufficient_quotient(
    experiment: Sequence[Sequence[Number]],
    prior: Sequence[Number],
    losses: Sequence[Sequence[Number]],
) -> dict[str, Any]:
    """Find the minimum deterministic quotient preserving one task's risk."""
    source = validate_experiment(experiment)
    engine = bayes_decision_engine(prior, source, losses)
    masks = _optimal_masks(engine)
    action_labels = engine["actions"]
    candidates = [
        (action_labels[action], sum(1 << signal for signal, mask in enumerate(masks) if mask & (1 << action)))
        for action in range(len(action_labels))
    ]
    chosen, count = _minimum_cover(len(source[0]), candidates)
    blocks = _blocks_from_cover(
        len(source[0]),
        chosen,
        lambda action, signal: masks[signal] & (1 << action_labels.index(action)) != 0,
    )
    verification = verify_task_partition(source, prior, losses, blocks)
    return {
        "status": "EXACT",
        "minimum_quotient_states": count,
        "chosen_action_cover": chosen,
        "blocks": [list(block) for block in blocks],
        "verification": verification,
        "reduction": "minimum set cover over signal sets sharing a Bayes-optimal action",
        "complexity": "O(2^m * k) dynamic programming for m signals and k actions",
    }


def multi_task_sufficient_quotient(
    experiment: Sequence[Sequence[Number]],
    prior: Sequence[Number],
    tasks: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    """Find a minimum quotient preserving Bayes risk for every task."""
    source = validate_experiment(experiment)
    if not tasks:
        raise ValueError("at least one task is required")
    engines = [bayes_decision_engine(prior, source, task["losses"], task.get("actions")) for task in tasks]
    masks = [_optimal_masks(engine) for engine in engines]
    action_ranges = [range(len(engine["actions"])) for engine in engines]
    candidates: list[tuple[tuple[int, ...], int]] = []
    for action_tuple in product(*action_ranges):
        compatible_mask = 0
        for signal in range(len(source[0])):
            if all(masks[task_index][signal] & (1 << action) for task_index, action in enumerate(action_tuple)):
                compatible_mask |= 1 << signal
        candidates.append((tuple(action_tuple), compatible_mask))
    chosen, count = _minimum_cover(len(source[0]), candidates)
    blocks = _blocks_from_cover(
        len(source[0]),
        chosen,
        lambda action_tuple, signal: all(
            masks[task_index][signal] & (1 << action)
            for task_index, action in enumerate(action_tuple)
        ),
    )
    verification = []
    for task in tasks:
        verification.append(verify_task_partition(source, prior, task["losses"], blocks))
    return {
        "status": "EXACT",
        "task_count": len(tasks),
        "minimum_quotient_states": count,
        "chosen_action_tuple_cover": [list(item) for item in chosen],
        "blocks": [list(block) for block in blocks],
        "verification": verification,
        "monotonicity": "adding tasks can only preserve or increase the minimum quotient state count",
        "reduction": "minimum set cover over joint task-optimal action tuples",
        "complexity": "O(2^m * product_i |A_i|) dynamic programming",
    }


def epsilon_sufficient_compression(
    experiment: Sequence[Sequence[Number]],
    prior: Sequence[Number],
    tasks: Sequence[dict[str, Any]],
    epsilons: Sequence[Number],
    *,
    max_partitions: int = 250_000,
) -> dict[str, Any]:
    """Find the smallest enumerated partition with per-task risk tolerance."""
    source = validate_experiment(experiment)
    if len(tasks) != len(epsilons) or not tasks:
        raise ValueError("tasks and epsilons must have equal non-zero length")
    epsilon_values = [frac(value) for value in epsilons]
    if any(value < 0 for value in epsilon_values):
        raise ValueError("epsilons must be non-negative")
    originals = [bayes_decision_engine(prior, source, task["losses"], task.get("actions")) for task in tasks]
    best: dict[str, Any] | None = None
    feasible_count = 0
    checked = 0
    pruned = 0
    try:
        for blocks in _partitions(len(source[0]), max_count=max_partitions):
            checked += 1
            # The first feasible incumbent is an upper bound.  Any partition
            # with at least as many blocks cannot improve the objective; this
            # is a genuine branch-and-bound pruning rule even though the
            # canonical partition generator remains the auditable traversal.
            if best is not None and len(blocks) >= best["state_count"]:
                pruned += 1
                continue
            quotient = quotient_experiment(source, blocks)
            compressed = [bayes_decision_engine(prior, quotient, task["losses"], task.get("actions")) for task in tasks]
            deltas = [
                compressed[index]["internal"]["bayes_risk"] - originals[index]["internal"]["bayes_risk"]
                for index in range(len(tasks))
            ]
            if any(delta > epsilon_values[index] for index, delta in enumerate(deltas)):
                continue
            feasible_count += 1
            candidate = {
                "blocks": [list(block) for block in blocks],
                "state_count": len(blocks),
                "risk_deltas": [_fraction_text(delta) for delta in deltas],
                "risk_deltas_float": [_float(delta) for delta in deltas],
                "quotient_experiment": _serialize_matrix(quotient),
                "quotient_engines": compressed,
            }
            if best is None or (candidate["state_count"], candidate["blocks"]) < (best["state_count"], best["blocks"]):
                best = candidate
    except ExactSolverLimit:
        if best is None:
            return {
                "status": "RESOURCE_LIMIT",
                "partitions_checked": checked,
                "feasible_partition_count": feasible_count,
                "lower_bound": 1,
                "upper_bound": None,
                "optimality_gap": None,
                "pruned": pruned,
                "complexity": "branch-and-bound over canonical partitions; Bell(m) worst case",
            }
        return {
            "status": "RESOURCE_LIMIT",
            "partitions_checked": checked,
            "feasible_partition_count": feasible_count,
            "minimum": best,
            "lower_bound": 1,
            "upper_bound": best["state_count"],
            "optimality_gap": best["state_count"] - 1,
            "pruned": pruned,
            "complexity": "branch-and-bound over canonical partitions; Bell(m) worst case",
        }
    if best is None:
        return {
            "status": "NO_FEASIBLE_PARTITION",
            "partitions_checked": checked,
            "feasible_partition_count": 0,
            "lower_bound": None,
            "upper_bound": None,
            "optimality_gap": None,
            "pruned": pruned,
            "complexity": "branch-and-bound over canonical partitions; Bell(m) worst case",
        }
    return {
        "status": "EXACT",
        "partitions_checked": checked,
        "feasible_partition_count": feasible_count,
        "minimum": best,
        "epsilons": [_fraction_text(value) for value in epsilon_values],
        "lower_bound": best["state_count"],
        "upper_bound": best["state_count"],
        "optimality_gap": 0,
        "pruned": pruned,
        "complexity": "branch-and-bound over canonical partitions; Bell(m) worst case",
        "optimality": "lower bound equals feasible upper bound after all smaller partitions are ruled out",
    }


def decision_spectrum(
    experiment: Sequence[Sequence[Number]],
    prior: Sequence[Number],
    tasks: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Report how many representation states each decision task requires."""
    spectrum = []
    for index, task in enumerate(tasks):
        quotient = task_sufficient_quotient(experiment, prior, task["losses"])
        spectrum.append({
            "task": task.get("id", index),
            "minimum_states": quotient["minimum_quotient_states"],
            "risk_before": quotient["verification"]["original_bayes_risk"],
            "risk_after": quotient["verification"]["quotient_bayes_risk"],
            "posterior_action_structure": quotient["verification"]["witnesses"],
        })
    return spectrum


def stochastic_compression_search(
    experiment: Sequence[Sequence[Number]],
    prior: Sequence[Number],
    tasks: Sequence[dict[str, Any]],
    epsilons: Sequence[Number],
    *,
    target_symbols: int,
    denominator: int = 2,
    max_channels: int = 100_000,
) -> dict[str, Any]:
    """Search a small rational grid for a stochastic-compression advantage.

    The function is deliberately a falsification tool, not a universal
    optimizer.  It compares every grid channel against the exact deterministic
    partition result on the same finite fixture and records when the grid is
    insufficient to decide the general question.
    """
    source = validate_experiment(experiment)
    states, source_symbols = _shape(source)
    if target_symbols < 1 or denominator < 1:
        raise ValueError("target_symbols and denominator must be positive")
    if len(tasks) != len(epsilons):
        raise ValueError("tasks and epsilons must have equal length")

    def compositions(total: int, parts: int) -> Iterable[tuple[int, ...]]:
        if parts == 1:
            yield (total,)
            return
        for first_part in range(total + 1):
            for tail in compositions(total - first_part, parts - 1):
                yield (first_part,) + tail

    row_grid = list(compositions(denominator, target_symbols))
    channels = 0
    stochastic_feasible = None
    for rows in product(row_grid, repeat=source_symbols):
        channels += 1
        if channels > max_channels:
            break
        channel = [[Fraction(value, denominator) for value in row] for row in rows]
        compressed_experiment = _matmul(source, channel)
        originals = [bayes_decision_engine(prior, source, task["losses"], task.get("actions")) for task in tasks]
        compressed = [bayes_decision_engine(prior, compressed_experiment, task["losses"], task.get("actions")) for task in tasks]
        deltas = [
            compressed[index]["internal"]["bayes_risk"] - originals[index]["internal"]["bayes_risk"]
            for index in range(len(tasks))
        ]
        if all(delta <= frac(epsilons[index]) for index, delta in enumerate(deltas)):
            stochastic_feasible = {
                "channel": _serialize_matrix(channel),
                "risk_deltas": [_fraction_text(delta) for delta in deltas],
            }
            break

    deterministic = epsilon_sufficient_compression(
        source, prior, tasks, epsilons, max_partitions=250_000
    )
    deterministic_feasible = (
        deterministic.get("status") == "EXACT"
        and deterministic["minimum"]["state_count"] <= target_symbols
    )
    exact_zero = all(frac(value) == 0 for value in epsilons)
    return {
        "status": "SEARCHED" if channels <= max_channels else "BOUNDED_SEARCH",
        "target_symbols": target_symbols,
        "denominator": denominator,
        "channels_examined": channels,
        "stochastic_feasible": stochastic_feasible,
        "deterministic_feasible": deterministic_feasible,
        "deterministic_result": deterministic,
        "strict_stochastic_advantage_found": stochastic_feasible is not None and not deterministic_feasible,
        "exact_zero_theorem": (
            "For epsilon=0, a stochastic decoder's supported actions are optimal at every source symbol; "
            "choosing one supported output per symbol gives a deterministic quotient with no more symbols."
            if exact_zero else None
        ),
        "general_epsilon_status": "UNKNOWN outside this finite grid" if not exact_zero else "PROVED_NO_ADVANTAGE",
    }


def _identity_hypergraph_instance(
    hyperedges: Sequence[Sequence[int]],
    action_count: int,
) -> tuple[Matrix, list[Fraction], Matrix, list[int]]:
    """Make a controlled identity experiment from an ambiguity hypergraph."""
    if not hyperedges or action_count < 1:
        raise ValueError("controlled hypergraph must be non-empty")
    if any(not edge or any(action < 0 or action >= action_count for action in edge) for edge in hyperedges):
        raise ValueError("hyperedges must contain valid non-empty action indices")
    symbols = len(hyperedges)
    experiment = [[1 if state == symbol else 0 for symbol in range(symbols)] for state in range(symbols)]
    losses = [[0 if action in hyperedges[state] else 1 for action in range(action_count)] for state in range(symbols)]
    return experiment, [Fraction(1, symbols) for _ in range(symbols)], losses, list(range(action_count))


def complexity_experiment_suite() -> list[dict[str, Any]]:
    """Run a compact synthetic suite that changes structure, not corpus."""
    cases = {
        "unique_optimum": ([[0], [1], [2], [3]], 4),
        "degree_2_cycle": ([[0, 1], [1, 2], [2, 3], [3, 0]], 4),
        "decomposable": ([[0, 1, 2], [0], [3, 4, 5], [3]], 6),
        "high_symmetry": ([[0, 1], [0, 1], [0, 1], [0, 1]], 2),
        "dense_general": ([[0, 1, 2], [0, 2, 3], [1, 2, 3], [0, 1, 3], [0, 1, 2, 3]], 4),
        "large_general_bounded": (
            [sorted({index % 11, (index + 1) % 11, (index + 4) % 11}) for index in range(23)],
            11,
        ),
    }
    rows = []
    for name, (hyperedges, action_count) in cases.items():
        experiment, prior, losses, actions = _identity_hypergraph_instance(hyperedges, action_count)
        start = perf_counter()
        result = adaptive_task_quotient(experiment, prior, losses, actions=actions, exact_signal_limit=8)
        elapsed = perf_counter() - start
        bounds = result["bounds"]
        lower = bounds["lower_bound"]
        upper = bounds["upper_bound"]
        rows.append({
            "case": name,
            "symbols": len(hyperedges),
            "actions": action_count,
            "ambiguous_symbols": result["ambiguity"]["ambiguous_symbols"],
            "maximum_ambiguity": result["ambiguity"]["maximum_ambiguity_arity"],
            "components": len(result["ambiguity"]["components"]),
            "regime": result["complexity_regime"],
            "algorithm": result["algorithm"],
            "states_explored": result["nodes_explored"],
            "runtime_seconds": elapsed,
            "status": result["status"],
            "optimum": result["state_count"] if result["status"] == "EXACT" else None,
            "lower_bound": lower,
            "upper_bound": upper,
            "optimality_gap": bounds["optimality_gap"],
            "theoretical_guarantee": bounds["theoretical_guarantee"],
            "observed_upper_over_lower": (
                None if not lower else upper / lower
            ),
            "certificate": "partition + common optimal actions" if result["verification"]["preserved"] else "bounded cover only",
        })
    return rows


def representation_compiler(
    experiment: Sequence[Sequence[Number]],
    prior: Sequence[Number],
    tasks: Sequence[dict[str, Any]],
    epsilons: Sequence[Number],
) -> dict[str, Any]:
    """Compile an experiment to a task-preserving or epsilon-preserving quotient."""
    source = validate_experiment(experiment)
    compression = epsilon_sufficient_compression(source, prior, tasks, epsilons)
    if compression["status"] != "EXACT":
        return {
            "status": "NO_FEASIBLE_COMPRESSION",
            "compression": compression,
        }
    blocks = compression["minimum"]["blocks"]
    quotient = quotient_experiment(source, blocks)
    task_checks = []
    for task in tasks:
        task_checks.append(verify_task_partition(source, prior, task["losses"], blocks))
    blackwell = compare_blackwell(source, quotient)
    forward_deficiency = directed_deficiency(source, quotient)
    reverse_deficiency = directed_deficiency(quotient, source)
    if forward_deficiency.get("status") == "EXACT" and reverse_deficiency.get("status") == "EXACT":
        symmetric_distance = max(
            frac(forward_deficiency["deficiency"]),
            frac(reverse_deficiency["deficiency"]),
        )
        symmetric = {
            "status": "EXACT",
            "value": _fraction_text(symmetric_distance),
            "value_float": _float(symmetric_distance),
            "meaning": "max(forward simulation loss, reverse reconstruction deficiency)",
        }
    else:
        symmetric = {"status": "INVALID", "meaning": "one directed deficiency was not solved"}
    return {
        "status": "COMPILED",
        "original_experiment": _serialize_matrix(source),
        "compressed_experiment": _serialize_matrix(quotient),
        "quotient_blocks": [list(block) for block in blocks],
        "compression": compression,
        "task_checks": task_checks,
        "blackwell_relation": blackwell,
        "blackwell_original_to_compressed": blackwell["first_to_second"],
        "forward_simulation_loss": forward_deficiency,
        "reverse_reconstruction_deficiency": reverse_deficiency,
        "symmetric_decision_distance": symmetric,
        # Backwards-compatible aliases retained for existing consumers.
        "deficiency_original_to_compressed": forward_deficiency,
        "preserved_tasks": [
            task.get("id", index)
            for index, (task, check) in enumerate(zip(tasks, task_checks))
            if check["preserved"]
        ],
        "lost_tasks": [
            task.get("id", index)
            for index, (task, check) in enumerate(zip(tasks, task_checks))
            if not check["preserved"]
        ],
        "complexity_certificate": {
            "quotient_search": compression["complexity"],
            "garbling_check": "finite rational LP; this implementation uses exact vertices",
            "direction_convention": "forward source->compressed is simulation loss; reverse compressed->source is reconstruction deficiency",
        },
    }


def identify_decision(
    supplied_assumptions: Iterable[str],
    required_assumptions: Iterable[str],
) -> dict[str, Any]:
    """Make identification assumptions explicit instead of hiding them.

    This is deliberately only an interface: MAT-SI records which assumptions
    were supplied, which are still missing, and never promotes a missing
    assumption to a discovered fact.
    """
    supplied = set(supplied_assumptions)
    required = set(required_assumptions)
    missing = sorted(required - supplied)
    return {
        "identified": not missing,
        "supplied": sorted(supplied),
        "required": sorted(required),
        "missing": missing,
        "status": "IDENTIFIED" if not missing else "NOT_IDENTIFIED",
    }


def compose_garblings(first: Sequence[Sequence[Number]], second: Sequence[Sequence[Number]]) -> Matrix:
    """Compose two compatible row-stochastic channels exactly."""
    return _matmul(_matrix(first), _matrix(second))


def transformation_certificate(
    source_experiment: Sequence[Sequence[Number]],
    target_experiment: Sequence[Sequence[Number]],
    prior: Sequence[Number],
    tasks: Sequence[dict[str, Any]],
    *,
    transformation_id: str = "T",
) -> dict[str, Any]:
    """Record what one representation transformation preserves or loses."""
    source = validate_experiment(source_experiment)
    target = validate_experiment(target_experiment)
    blackwell = compare_blackwell(source, target)
    deficiency = directed_deficiency(source, target)
    task_changes = []
    for task in tasks:
        before = bayes_decision_engine(prior, source, task["losses"], task.get("actions"))
        after = bayes_decision_engine(prior, target, task["losses"], task.get("actions"))
        delta = after["internal"]["bayes_risk"] - before["internal"]["bayes_risk"]
        task_changes.append({
            "task": task.get("id", len(task_changes)),
            "risk_before": before["bayes_risk"],
            "risk_after": after["bayes_risk"],
            "risk_delta": _fraction_text(delta),
            "preserved": delta == 0,
        })
    return {
        "transformation": transformation_id,
        "blackwell": blackwell,
        "deficiency": deficiency,
        "task_changes": task_changes,
        "decisions_preserved": [item["task"] for item in task_changes if item["preserved"]],
        "decisions_changed": [item["task"] for item in task_changes if not item["preserved"]],
    }


def representation_path(
    experiments: Sequence[Sequence[Sequence[Number]]],
    prior: Sequence[Number],
    tasks: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    """Evaluate a chain and propagate a deficiency upper bound by composition."""
    if len(experiments) < 2:
        raise ValueError("a path needs at least two experiments")
    steps = []
    cumulative_bound = Fraction(0)
    for index in range(len(experiments) - 1):
        step = transformation_certificate(
            experiments[index],
            experiments[index + 1],
            prior,
            tasks,
            transformation_id=f"T{index + 1}",
        )
        steps.append(step)
        if step["deficiency"].get("status") == "EXACT":
            cumulative_bound += frac(step["deficiency"]["deficiency"])
    return {
        "steps": steps,
        "deficiency_upper_bound_by_triangle": _fraction_text(cumulative_bound),
        "bound_meaning": "directed deficiency of the composite path is at most the sum of step deficiencies",
        "all_steps_exact_blackwell": all(
            step["blackwell"]["classification"] in {"DOMINATES", "EQUIVALENT"}
            for step in steps
        ),
    }


def _fixtures() -> dict[str, Matrix | list[Fraction]]:
    return {
        "prior_binary": [Fraction(1, 2), Fraction(1, 2)],
        "fully_revealing": [[1, 0], [0, 1]],
        "permuted_revealing": [[0, 1], [1, 0]],
        "strict_garbling": [[Fraction(3, 4), Fraction(1, 4)], [Fraction(1, 4), Fraction(3, 4)]],
        "useless": [[Fraction(1, 2), Fraction(1, 2)], [Fraction(1, 2), Fraction(1, 2)]],
        "incomparable_left": [[1, 0], [1, 0], [0, 1]],
        "incomparable_right": [[1, 0], [0, 1], [0, 1]],
        "three_signal_task": [[Fraction(1, 2), Fraction(1, 4), Fraction(1, 4)], [0, Fraction(1, 3), Fraction(2, 3)]],
    }


def run_calculus() -> dict[str, Any]:
    """Execute the compact mathematical program on exact finite fixtures."""
    fixtures = _fixtures()
    prior = fixtures["prior_binary"]
    binary_loss = [[0, 1], [1, 0]]
    revealing = fixtures["fully_revealing"]
    strict = fixtures["strict_garbling"]
    useless = fixtures["useless"]
    tasks = [
        {"id": "binary_classification", "losses": binary_loss, "actions": [False, True]},
        {"id": "asymmetric_action", "losses": [[0, 2], [1, 0]], "actions": ["safe", "risky"]},
    ]
    engine = bayes_decision_engine(prior, revealing, binary_loss, actions=[False, True])
    blackwell_cases = {
        "identical": compare_blackwell(revealing, revealing),
        "permuted": compare_blackwell(revealing, fixtures["permuted_revealing"]),
        "strict_garbling": compare_blackwell(revealing, strict),
        "reverse_only": compare_blackwell(strict, revealing),
        "useless": compare_blackwell(revealing, useless),
        "incomparable": compare_blackwell(fixtures["incomparable_left"], fixtures["incomparable_right"]),
    }
    deficiency_cases = {
        "exact_garbling": le_cam_distance(revealing, strict),
        "incomparable_pair": le_cam_distance(fixtures["incomparable_left"], fixtures["incomparable_right"]),
    }
    single_task = task_sufficient_quotient(fixtures["three_signal_task"], prior, binary_loss)
    multi_task = multi_task_sufficient_quotient(fixtures["three_signal_task"], prior, tasks)
    epsilon = epsilon_sufficient_compression(
        fixtures["three_signal_task"], prior, tasks, [0, Fraction(1, 4)]
    )
    spectrum = decision_spectrum(fixtures["three_signal_task"], prior, tasks)
    compiler = representation_compiler(
        fixtures["three_signal_task"], prior, tasks, [0, Fraction(1, 4)]
    )
    path = representation_path([revealing, strict, useless], prior, tasks[:1])
    identification = identify_decision(
        ["labels", "calibration_observations"],
        ["labels", "calibration_observations", "monotonicity"],
    )
    information_prior = [Fraction(1, 3)] * 3
    irrelevant_information = [[1, 0], [0, 1], [1, 0]]
    task_targeted_information = [
        [Fraction(9, 10), Fraction(1, 10)],
        [Fraction(1, 10), Fraction(9, 10)],
        [Fraction(1, 10), Fraction(9, 10)],
    ]
    target_loss = [[0, 1], [1, 0], [1, 0]]
    irrelevant_engine = bayes_decision_engine(information_prior, irrelevant_information, target_loss)
    targeted_engine = bayes_decision_engine(information_prior, task_targeted_information, target_loss)
    mutual_information_case = {
        "status": "CONSTRUCTED",
        "prior": ["1/3", "1/3", "1/3"],
        "task": "action 0 is correct only for state 0; action 1 is correct for states 1 and 2",
        "irrelevant_information": {
            "mutual_information_bits": mutual_information(information_prior, irrelevant_information),
            "bayes_risk": irrelevant_engine["bayes_risk"],
            "experiment": _serialize_matrix(validate_experiment(irrelevant_information)),
        },
        "task_targeted_information": {
            "mutual_information_bits": mutual_information(information_prior, task_targeted_information),
            "bayes_risk": targeted_engine["bayes_risk"],
            "experiment": _serialize_matrix(validate_experiment(task_targeted_information)),
        },
        "finding": "The higher-MI experiment has worse task Bayes risk; MI and decision usefulness do not induce the same order.",
    }
    ambiguity = analyze_decision_ambiguity(fixtures["three_signal_task"], prior, binary_loss)
    adaptive = adaptive_task_quotient(fixtures["three_signal_task"], prior, binary_loss)
    set_cover_fixture = set_cover_reduction_instance(
        ["u1", "u2", "u3", "u4"],
        [["u1", "u2"], ["u2", "u3"], ["u3", "u4"], ["u1", "u4"]],
        2,
    )
    set_cover_certificate = verify_set_cover_reduction(set_cover_fixture)
    vertex_cover_fixture = vertex_cover_reduction_instance(
        ["a", "b", "c", "d"], [("a", "b"), ("b", "c"), ("c", "d")], 2
    )
    vertex_cover_certificate = vertex_cover_reduction_certificate(vertex_cover_fixture)
    separation = find_separation_witnesses(
        fixtures["incomparable_left"], fixtures["incomparable_right"], prior_denominator=4
    )
    stochastic = stochastic_compression_search(
        fixtures["three_signal_task"], prior, tasks[:1], [0], target_symbols=1, denominator=2
    )
    complexity_suite = complexity_experiment_suite()
    return {
        "protocol": "agent1-decision-representation-calculus-v1",
        "corpus_policy": "no new corpus; exact finite mathematical fixtures only",
        "object": {
            "experiment": "E[y][r] = P(R=r | Y=y)",
            "decision_problem": "D=(A,L)",
            "bayes_value": "V(E,D,pi) = min_decoder E[L(Y,decoder(R))]",
        },
        "bayes_engine": {
            "status": "EXECUTABLE",
            "risk": engine["bayes_risk"],
            "policy": engine["policy"],
            "posterior_by_symbol": engine["posteriors"],
            "arbitrary_loss_supported": True,
        },
        "blackwell": {
            "status": "EXECUTABLE",
            "cases": blackwell_cases,
            "criterion": "E1 dominates E2 iff a row-stochastic K exists with E1*K=E2",
            "invalid_state": "INVALID",
        },
        "deficiency": {
            "status": "EXECUTABLE",
            "cases": deficiency_cases,
            "criterion": "delta(E1,E2)=min_K max_y TV(E1_y*K,E2_y)",
            "symmetric": "max(delta(E1,E2),delta(E2,E1))",
        },
        "task_sufficient_quotient": {
            "status": "EXECUTABLE",
            "result": single_task,
            "criterion": "a block is valid iff its symbols share at least one Bayes-optimal action",
        },
        "multi_task": {
            "status": "EXECUTABLE",
            "result": multi_task,
            "monotonicity": "minimum multi-task quotient size is at least each single-task minimum",
        },
        "epsilon_compression": {
            "status": "EXECUTABLE",
            "result": epsilon,
            "criterion": "per-task quotient Bayes-risk increase <= epsilon_i",
        },
        "decision_spectrum": spectrum,
        "representation_path": path,
        "identification_interface": identification,
        "representation_compiler": compiler,
        "ambiguity_hypergraph": {
            "status": "EXECUTABLE",
            "profile": ambiguity,
            "adaptive_solver": adaptive,
            "principle": "minimum quotient = minimum action cover of optimal-action hyperedges",
        },
        "complexity_reductions": {
            "set_cover": set_cover_certificate,
            "vertex_cover_degree_2": vertex_cover_certificate,
            "claims": {
                "minimum_task_quotient_decision": "NP-COMPLETE by explicit polynomial Set-Cover reduction",
                "degree_2_ambiguity_decision": "NP-HARD by explicit Vertex-Cover reduction",
                "unique_optimum": "polynomial direct grouping",
            },
        },
        "blackwell_separation": separation,
        "stochastic_compression": stochastic,
        "complexity_experiment_suite": complexity_suite,
        "complexity": {
            "bayes_engine": {
                "decision_version": "is V(E,D,pi) <= q?",
                "algorithm": "posterior enumeration and minimum over actions",
                "worst_case": "O(|Y||R||A|) arithmetic operations",
                "status": "POLYNOMIAL",
            },
            "blackwell": {
                "decision_version": "does a row-stochastic K satisfy E1*K=E2?",
                "search_version": "return K",
                "standard_algorithm": "linear-program feasibility",
                "this_implementation": "exact rational vertex enumeration for small dimensions",
                "hardness_status": "no hardness claim; LP formulation is explicit",
            },
            "deficiency": {
                "decision_version": "is delta(E1,E2) <= epsilon?",
                "search_version": "return approximately optimal K",
                "standard_algorithm": "linear program with absolute-residual slack variables",
                "this_implementation": "exact rational LP vertices for small dimensions",
                "hardness_status": "no hardness claim; LP formulation is explicit",
            },
            "task_quotient": {
                "decision_version": "does a partition with <=q blocks preserve Bayes risk?",
                "search_version": "return minimum partition",
                "reduction": "minimum set cover over Bayes-optimal action incidence",
                "this_implementation": "bitmask dynamic programming",
                "worst_case": "O(2^|R|*|A|) after optimal-action computation",
                "hardness_status": "NP-complete decision problem by explicit Set-Cover reduction",
            },
            "multi_task_quotient": {
                "reduction": "set cover over joint optimal-action tuples",
                "worst_case": "O(2^|R|*product_i |A_i|)",
                "hardness_status": "NP-hard degree-2 specialization by Vertex-Cover reduction",
            },
            "epsilon_compression": {
                "algorithm": "branch-and-bound over canonical set partitions with rational risk checks",
                "worst_case": "O(Bell(|R|)*sum_i decision_engine_i)",
                "bounds": "lower_bound <= optimum <= feasible upper_bound; exact runs close the gap",
                "hardness_status": "NP-hard already at epsilon=0 via the task-quotient reduction",
            },
            "stochastic_compression": {
                "exact_epsilon_zero": "randomization cannot reduce the number of output symbols for a fixed task",
                "positive_epsilon": "finite grid search only; general multi-task question remains UNKNOWN",
            },
        },
        "counterexamples": {
            "mutual_information_not_decision_order": {
                "status": "CONSTRUCTED",
                "statement": mutual_information_case["finding"],
                "fixture": mutual_information_case,
            },
            "incomparable_representations": {
                "status": "CONSTRUCTED",
                "statement": "Each experiment separates a different pair of three world states; neither can garble to the other.",
            },
            "task_dependence": {
                "status": "CONSTRUCTED",
                "statement": "The minimum quotient is computed per task and can change when a second loss matrix is added.",
            },
            "stochastic_no_advantage_at_zero_tolerance": {
                "status": "PROVED",
                "statement": "For epsilon=0, every action used with positive probability after a stochastic compressor must be optimal at the source signal; selecting one supported output gives a deterministic quotient with no more output symbols.",
            },
            "finite_blackwell_separation_witnesses": {
                "status": separation["status"],
                "statement": "The incomparable fixture has bounded rational decision witnesses in both directions; this is a witness search, not a replacement for the Blackwell theorem.",
                "fixture": separation,
            },
        },
        "literature": [
            {
                "author": "David Blackwell",
                "title": "Equivalent Comparisons of Experiments",
                "year": 1953,
                "url": "https://projecteuclid.org/journals/annals-of-mathematical-statistics/volume-24/issue-2/Equivalent-Comparisons-of-Experiments/10.1214/aoms/1177729032.full",
                "used_for": "Blackwell comparison and garbling criterion",
            },
            {
                "author": "Lucien Le Cam",
                "title": "Sufficiency and Approximate Sufficiency",
                "year": 1964,
                "url": "https://projecteuclid.org/journals/annals-of-mathematical-statistics/volume-35/issue-4/Sufficiency-and-Approximate-Sufficiency/10.1214/aoms/1177700372.full",
                "used_for": "deficiency and approximate experiment simulation",
            },
        ],
        "status_summary": {
            "PROVED": [
                "finite Bayes engine computes exact value and all optimal-action ties",
                "task quotient validity is equivalent to a common Bayes-optimal action per block",
                "multi-task quotient minimum cannot be smaller than a single-task quotient",
                "Blackwell witness implies zero deficiency in the same direction",
                "Set-Cover reduces to minimum risk-zero task quotient",
                "Vertex-Cover reduces to degree-2 ambiguity quotient",
                "forward simulation loss is zero for a deterministic quotient; reverse reconstruction deficiency can be positive",
                "exact-zero stochastic compression has no representation-size advantage over deterministic compression",
            ],
            "KNOWN_RESULT": [
                "finite Blackwell comparison is a stochastic-channel feasibility problem",
                "finite deficiency is an LP over channel and TV slack variables",
            ],
            "CONJECTURE": [],
            "DISPROVED": [
                "representation quality can be summarized independently of a decision family",
            ],
            "UNKNOWN": [
                "whether stochastic compression can improve a multi-task positive-epsilon frontier outside the searched finite grid",
                "scalable approximation guarantees for epsilon compression beyond the reported bounds",
            ],
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the finite MAT-SI decision representation calculus")
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args(argv)
    result = run_calculus()
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(result, indent=2, sort_keys=True, default=str) + "\n",
            encoding="utf-8",
        )
    print(json.dumps({
        "protocol": result["protocol"],
        "bayes_risk": result["bayes_engine"]["risk"],
        "blackwell": {name: value["classification"] for name, value in result["blackwell"]["cases"].items()},
        "task_quotient_states": result["task_sufficient_quotient"]["result"]["minimum_quotient_states"],
        "multi_task_quotient_states": result["multi_task"]["result"]["minimum_quotient_states"],
        "compiled": result["representation_compiler"]["status"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

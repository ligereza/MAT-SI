"""Sequential decision machinery: detection, stopping, bandits, recurrence."""

from .changepoint import (
    ChangeDetection,
    cusum,
    page_hinkley,
    sliding_window_mean_shift,
)
from .cycles import cycle_report, detect_cycle, recurrence_rate
from .returns import diminishing_returns, marginal_gains, plateau_length
from .stopping import (
    StoppingPolicy,
    optimal_stopping_threshold,
    run_stopping_policy,
    secretary_stopping,
)
from .bandits import BanditRun, epsilon_greedy, regret_curve, ucb1, sliding_ucb

__all__ = [
    "BanditRun",
    "ChangeDetection",
    "StoppingPolicy",
    "cusum",
    "cycle_report",
    "detect_cycle",
    "diminishing_returns",
    "epsilon_greedy",
    "marginal_gains",
    "optimal_stopping_threshold",
    "page_hinkley",
    "plateau_length",
    "recurrence_rate",
    "regret_curve",
    "run_stopping_policy",
    "secretary_stopping",
    "sliding_ucb",
    "sliding_window_mean_shift",
    "ucb1",
]

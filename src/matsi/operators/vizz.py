"""VIZZ: choose the next experiment.

FORMAL OBJECT.  Bayesian experimental design on a finite hypothesis space.  Given
a belief ``p`` over hypotheses ``Theta``, a decision-relevant projection
``T = target(Theta)``, and a set of priced deterministic experiments ``E``, choose
``e in E`` to make next, or decline.

ACTION SPACE.  A single experiment (or nothing).  This is what distinguishes VIZZ
from the other three operators: it does not transform the representation, it does
not decide about a trajectory, and it does not branch.  It buys an observation.

LITERATURE AUDIT.
* Expected information gain as a design criterion -- ESTABLISHED (Lindley,
  *On a measure of the information provided by an experiment*, Ann. Math. Statist.
  1956; Chaloner & Verdinelli, *Bayesian experimental design*, Statist. Sci. 1995).
* Greedy maximisation of a monotone submodular set function is within ``1 - 1/e``
  of the optimum under a cardinality constraint -- KNOWN_RESULT (Nemhauser, Wolsey
  & Fisher 1978).
* Information gain is submodular when observations are conditionally independent
  given the target, and is **not** submodular in general -- KNOWN_RESULT (Krause &
  Guestrin, *Near-optimal nonmyopic value of information in graphical models*,
  UAI 2005).
* Adaptive greedy retains a logarithmic guarantee for adaptive submodular
  objectives -- KNOWN_RESULT (Golovin & Krause, JAIR 2011).  Not used here: the
  worlds are noiseless, and the guarantee we care about is the one that *fails*.
* Bayesian surprise as KL from prior to posterior -- IMPORTED (Itti & Baldi 2009).

WHAT REMAINS SPECIFIC TO MAT-SI.  Nothing in the criterion.  What is specific is
(a) refusing to assume submodularity and instead *testing* it on the instance and
reporting the guarantee status in the certificate, and (b) returning
``INCOMPARABLE`` instead of inventing an exchange rate between bits and cost.

FAILURE REGIME.  When the objective is not submodular, greedy has no
constant-factor guarantee; ``worlds.decoy_parity_world`` drives the greedy/optimal
ratio to zero.  VIZZ detects the violation but cannot repair it: with a
cardinality budget it still acts greedily, and it says so.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Hashable, Sequence

from ..information.divergence import kl_divergence
from ..information.entropy import entropy
from ..substrate import Candidate, Declaration, Decision, Observation, State
from ..worlds.hypothesis_world import HypothesisWorld

RARITY_NOTE = "expected rarity H(Y) is not information about the target"


@dataclass
class VizzConfig:
    """Explicit preferences.  Nothing is defaulted into a universal score."""

    bits_per_cost_unit: float | None = None
    """Exchange rate supplied by the task.  ``None`` means the task refused to
    supply one, so VIZZ must return INCOMPARABLE rather than invent it."""

    minimum_gain_bits: float = 1e-9
    test_submodularity: bool = True


def belief_of(state: State) -> dict[Hashable, Fraction]:
    return dict(state.representation["belief"])


def _restrict(belief: dict[Hashable, Fraction], world: HypothesisWorld, key: str, outcome: Hashable) -> dict[Hashable, Fraction]:
    experiment = world.experiment(key)
    surviving = {
        theta: weight
        for theta, weight in belief.items()
        if experiment.observe(theta) == outcome and weight > 0
    }
    total = sum(surviving.values())
    if total <= 0:
        raise ValueError("observed outcome is impossible under the current belief")
    return {theta: weight / total for theta, weight in surviving.items()}


def _target_distribution(belief: dict[Hashable, Fraction], world: HypothesisWorld) -> dict[Hashable, Fraction]:
    out: dict[Hashable, Fraction] = {}
    for theta, weight in belief.items():
        if weight <= 0:
            continue
        cell = world.target(theta)
        out[cell] = out.get(cell, Fraction(0)) + weight
    return out


def _outcome_distribution(belief: dict[Hashable, Fraction], world: HypothesisWorld, key: str) -> dict[Hashable, Fraction]:
    experiment = world.experiment(key)
    out: dict[Hashable, Fraction] = {}
    for theta, weight in belief.items():
        if weight <= 0:
            continue
        cell = experiment.observe(theta)
        out[cell] = out.get(cell, Fraction(0)) + weight
    return out


def expected_information_gain(
    belief: dict[Hashable, Fraction], world: HypothesisWorld, key: str, about: str = "target"
) -> float:
    """``I(T;Y_e)`` (or ``I(Theta;Y_e)``) under the current belief, in bits.

    Computed as ``H(T) - sum_y P(y) H(T|y)``, which is exact for deterministic
    experiments because each outcome partitions the surviving hypotheses.
    """
    projection = world.target if about == "target" else (lambda theta: theta)
    before = entropy(
        _target_distribution(belief, world) if about == "target" else {k: v for k, v in belief.items() if v > 0}
    )
    outcomes = _outcome_distribution(belief, world, key)
    after = 0.0
    for outcome, probability in outcomes.items():
        posterior = _restrict(belief, world, key, outcome)
        conditional = (
            _target_distribution(posterior, world)
            if about == "target"
            else {k: v for k, v in posterior.items() if v > 0}
        )
        after += float(probability) * entropy(conditional)
    gain = before - after
    return 0.0 if abs(gain) < 1e-12 else gain


def expected_bayesian_surprise(
    belief: dict[Hashable, Fraction], world: HypothesisWorld, key: str
) -> float:
    """``E_y[ KL(posterior_y || belief) ]`` about Theta, in bits.

    This equals ``I(Theta;Y_e)``, so it is reported next to the *target* gain to
    make the difference between "surprising about the world" and "useful for the
    decision" visible in the certificate.
    """
    outcomes = _outcome_distribution(belief, world, key)
    total = 0.0
    for outcome, probability in outcomes.items():
        posterior = _restrict(belief, world, key, outcome)
        total += float(probability) * kl_divergence(posterior, belief)
    return total


def expected_rarity(belief: dict[Hashable, Fraction], world: HypothesisWorld, key: str) -> float:
    """``H(Y_e)``: how unpredictable the outcome is.  Not information about T."""
    return entropy(_outcome_distribution(belief, world, key))


def pareto_frontier(candidates: Sequence[Candidate]) -> list[Candidate]:
    """Keep candidates not dominated on (more target bits, less cost).

    ``x`` dominates ``y`` when ``gain(x) >= gain(y)`` and ``cost(x) <= cost(y)``
    with at least one strict inequality.  No weights are used, so the frontier is
    preference-free.
    """
    frontier: list[Candidate] = []
    for candidate in candidates:
        gain = candidate.declared.information_gain or 0.0
        cost = candidate.declared.cost
        dominated = False
        for other in candidates:
            if other is candidate:
                continue
            other_gain = other.declared.information_gain or 0.0
            if other_gain >= gain - 1e-12 and other.declared.cost <= cost + 1e-12 and (
                other_gain > gain + 1e-12 or other.declared.cost < cost - 1e-12
            ):
                dominated = True
                break
        if not dominated:
            frontier.append(candidate)
    return frontier


class Vizz:
    """The discovery operator over the shared substrate."""

    name = "VIZZ"

    def __init__(self, world: HypothesisWorld, config: VizzConfig | None = None) -> None:
        self.world = world
        self.config = config or VizzConfig()
        self.certificates: list[dict[str, object]] = []
        self._submodularity: dict[str, object] | None = None

    # --- substrate contract ----------------------------------------------
    def observe(self, state: State) -> State:
        belief = belief_of(state)
        representation = dict(state.representation)
        representation["target_entropy"] = entropy(_target_distribution(belief, self.world))
        representation["hypotheses_alive"] = sum(1 for weight in belief.values() if weight > 0)
        return state.with_representation(representation)

    def propose(self, state: State) -> list[Candidate]:
        belief = belief_of(state)
        done = {item.key for item in state.observations}
        candidates: list[Candidate] = []
        for experiment in self.world.experiments:
            if experiment.key in done:
                continue
            target_gain = expected_information_gain(belief, self.world, experiment.key, "target")
            candidates.append(
                Candidate(
                    name=experiment.key,
                    operator=self.name,
                    declared=Declaration(
                        cost=experiment.cost,
                        evidence=tuple(sorted(done)),
                        uncertainty=state.representation.get("target_entropy"),
                        information_gain=target_gain,
                        residue={
                            "expected_rarity_bits": expected_rarity(belief, self.world, experiment.key),
                            "expected_surprise_about_theta_bits": expected_bayesian_surprise(
                                belief, self.world, experiment.key
                            ),
                            "information_about_theta_bits": expected_information_gain(
                                belief, self.world, experiment.key, "hypothesis"
                            ),
                            "note": RARITY_NOTE,
                        },
                        invariants=("belief is updated by Bayes on a deterministic partition",),
                    ),
                    payload={"experiment": experiment.key},
                )
            )
        return candidates

    def select(self, state: State, candidates: Sequence[Candidate]) -> Candidate | None:
        budget = state.budget.remaining()
        affordable = [item for item in candidates if item.declared.cost <= budget]
        informative = [
            item
            for item in affordable
            if (item.declared.information_gain or 0.0) > self.config.minimum_gain_bits
        ]
        if self.config.test_submodularity and self._submodularity is None:
            self._submodularity = self.world.submodularity_report("target")
        certificate: dict[str, object] = {
            "turn": len(self.certificates),
            "budget_remaining": budget,
            "candidates": [
                {
                    "experiment": item.name,
                    "target_information_bits": item.declared.information_gain,
                    "theta_information_bits": item.declared.residue["information_about_theta_bits"],
                    "expected_rarity_bits": item.declared.residue["expected_rarity_bits"],
                    "cost": item.declared.cost,
                    "affordable": item.declared.cost <= budget,
                }
                for item in candidates
            ],
            "submodularity": self._submodularity,
            "greedy_guarantee": (
                "1 - 1/e applies on this instance"
                if (self._submodularity or {}).get("greedy_guarantee_applies")
                else "no constant-factor guarantee: objective is not submodular here"
            ),
        }
        if not candidates:
            certificate["decision"] = "no unperformed experiment"
            self.certificates.append(certificate)
            return None
        if not affordable:
            certificate["decision"] = "ABSTAIN: nothing affordable within budget"
            self.certificates.append(certificate)
            return None
        if not informative:
            certificate["decision"] = "ABSTAIN: no affordable experiment has positive target information"
            self.certificates.append(certificate)
            return None
        frontier = pareto_frontier(informative)
        certificate["pareto_frontier"] = [item.name for item in frontier]
        if len(frontier) > 1 and self.config.bits_per_cost_unit is None:
            certificate["decision"] = "INCOMPARABLE: frontier has several points and no exchange rate was supplied"
            certificate["incomparable"] = True
            self.certificates.append(certificate)
            return None
        if len(frontier) == 1:
            chosen = frontier[0]
            certificate["reason"] = "unique Pareto-optimal experiment"
        else:
            rate = self.config.bits_per_cost_unit or 0.0
            chosen = max(
                frontier,
                key=lambda item: (
                    (item.declared.information_gain or 0.0) - rate * item.declared.cost,
                    -item.declared.cost,
                    item.name,
                ),
            )
            certificate["reason"] = f"maximised bits minus {rate} x cost, an explicitly supplied preference"
        certificate["decision"] = f"SELECT {chosen.name}"
        certificate["rejected"] = [
            {
                "experiment": item.name,
                "why": (
                    "dominated on (bits, cost)"
                    if item in informative and item not in frontier
                    else "zero target information"
                    if item in affordable
                    else "unaffordable"
                ),
            }
            for item in candidates
            if item is not chosen
        ]
        certificate["falsified_by"] = (
            "observing an outcome that leaves the target distribution unchanged"
        )
        self.certificates.append(certificate)
        return chosen

    def apply(self, state: State, candidate: Candidate) -> State:
        belief = belief_of(state)
        key = candidate.payload["experiment"]
        if self.world.truth is None:
            raise ValueError("world has no ground truth to observe")
        outcome = self.world.experiment(key).observe(self.world.truth)
        posterior = _restrict(belief, self.world, key, outcome)
        representation = dict(state.representation)
        representation["belief"] = posterior
        representation["target_entropy"] = entropy(_target_distribution(posterior, self.world))
        surprise = kl_divergence(posterior, belief)
        after = state.with_representation(representation).with_observations(
            [Observation(key=key, value=outcome, source=f"experiment:{key}")]
        )
        after = after.charge(int(round(candidate.declared.cost)))
        self.certificates[-1]["observed"] = {
            "experiment": key,
            "outcome": outcome,
            "realised_surprise_bits": surprise,
            "realised_rarity_bits": -float(
                entropy({outcome: Fraction(1)})
            )
            + expected_rarity(belief, self.world, key),
            "target_entropy_after": representation["target_entropy"],
        }
        return after

    def validate(self, state: State, candidate: Candidate, after: State) -> bool | None:
        before = entropy(_target_distribution(belief_of(state), self.world))
        now = entropy(_target_distribution(belief_of(after), self.world))
        return now <= before + 1e-12

    def conclude(self, state: State, turn_index: int, validated: bool | None) -> tuple[Decision, str]:
        belief = belief_of(state)
        remaining = entropy(_target_distribution(belief, self.world))
        if remaining <= 1e-12:
            return Decision.STOP, "target identified: no residual entropy"
        if validated is False:
            return Decision.ABSTAIN, "belief update did not reduce target entropy"
        done = {item.key for item in state.observations}
        left = [item for item in self.world.experiments if item.key not in done]
        affordable = [item for item in left if item.cost <= state.budget.remaining()]
        if not affordable:
            return Decision.SWITCH, "target still uncertain but no affordable experiment remains"
        return Decision.CONTINUE, f"{remaining:.4f} bits of target entropy remain"


# --- research experiment: greedy versus the exhaustive optimum -------------
def greedy_versus_optimal(world: HypothesisWorld, budget_size: int) -> dict[str, object]:
    """Run non-adaptive greedy design and compare with the exhaustive optimum.

    Non-adaptive (choose a set before seeing outcomes) is the setting where the
    ``1 - 1/e`` submodular guarantee is stated, so it is the honest comparison for
    testing whether the guarantee's precondition holds.
    """
    keys = [item.key for item in world.experiments]
    chosen: list[str] = []
    trace: list[dict[str, object]] = []
    for _ in range(min(budget_size, len(keys))):
        best: tuple[float, str] | None = None
        current = world.information_about_target(chosen)
        for key in keys:
            if key in chosen:
                continue
            gain = world.information_about_target(chosen + [key]) - current
            if best is None or gain > best[0] + 1e-12:
                best = (gain, key)
        if best is None:
            break
        trace.append({"picked": best[1], "marginal_gain_bits": best[0]})
        chosen.append(best[1])
    greedy_value = world.information_about_target(chosen)
    optimal = world.best_subset(budget_size, "target")
    submodularity = world.submodularity_report("target")
    ratio = None if optimal["value"] <= 1e-12 else greedy_value / float(optimal["value"])
    return {
        "world": world.name,
        "budget_size": budget_size,
        "greedy_subset": chosen,
        "greedy_value_bits": greedy_value,
        "greedy_trace": trace,
        "optimal_subset": list(optimal["subset"]),
        "optimal_value_bits": optimal["value"],
        "approximation_ratio": ratio,
        "submodularity_status": submodularity["status"],
        "greedy_guarantee_applies": submodularity["greedy_guarantee_applies"],
        "one_minus_1_over_e": 0.6321205588285577,
        "guarantee_respected": (
            None if ratio is None else (ratio >= 0.6321205588285577 - 1e-9)
        ),
        "interpretation": (
            "guarantee precondition holds and is respected"
            if submodularity["greedy_guarantee_applies"]
            else "precondition fails; the observed ratio is not bounded by 1 - 1/e"
        ),
    }

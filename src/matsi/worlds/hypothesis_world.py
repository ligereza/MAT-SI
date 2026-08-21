"""Finite hypothesis worlds for VIZZ, with an exhaustive design oracle.

A world is a finite hypothesis set with a prior, a set of deterministic
experiments, and a *target projection* ``target(theta)``.  The target is the
decision-relevant part of the hypothesis: it is what makes
"information about the world" and "information for the decision" different
quantities rather than synonyms.

The oracle enumerates every experiment subset of a given size, so the greedy
policy can be compared with the exact optimum.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations
from typing import Callable, Hashable, Mapping, Sequence

from ..information.entropy import entropy, mutual_information


@dataclass(frozen=True)
class Experiment:
    """A deterministic, repeatable measurement with a price."""

    key: str
    cost: float
    outcome: Callable[[Hashable], Hashable]

    def observe(self, hypothesis: Hashable) -> Hashable:
        return self.outcome(hypothesis)


@dataclass(frozen=True)
class HypothesisWorld:
    """Everything an experimental-design problem needs, and nothing else."""

    name: str
    hypotheses: tuple[Hashable, ...]
    prior: Mapping[Hashable, Fraction]
    experiments: tuple[Experiment, ...]
    target: Callable[[Hashable], Hashable] = lambda theta: theta
    truth: Hashable | None = None
    note: str = ""

    def joint_with(self, keys: Sequence[str], projection: Callable[[Hashable], Hashable]) -> dict:
        """Joint distribution of ``(projection(theta), outcomes of keys)``."""
        chosen = [self.experiment(key) for key in keys]
        joint: dict[Hashable, Fraction] = {}
        for theta in self.hypotheses:
            outcome = tuple(item.observe(theta) for item in chosen)
            cell = (projection(theta), outcome)
            joint[cell] = joint.get(cell, Fraction(0)) + Fraction(self.prior[theta])
        return joint

    def experiment(self, key: str) -> Experiment:
        for item in self.experiments:
            if item.key == key:
                return item
        raise KeyError(f"no experiment named {key!r}")

    def information_about_hypothesis(self, keys: Sequence[str]) -> float:
        """I(Theta ; Y_keys) in bits."""
        if not keys:
            return 0.0
        return mutual_information(self.joint_with(keys, lambda theta: theta))

    def information_about_target(self, keys: Sequence[str]) -> float:
        """I(T ; Y_keys) in bits, with T the decision-relevant projection."""
        if not keys:
            return 0.0
        return mutual_information(self.joint_with(keys, self.target))

    def prior_entropy(self) -> float:
        return entropy({theta: Fraction(self.prior[theta]) for theta in self.hypotheses})

    def target_entropy(self) -> float:
        weights: dict[Hashable, Fraction] = {}
        for theta in self.hypotheses:
            key = self.target(theta)
            weights[key] = weights.get(key, Fraction(0)) + Fraction(self.prior[theta])
        return entropy(weights)

    def total_cost(self, keys: Sequence[str]) -> float:
        return sum(self.experiment(key).cost for key in keys)

    # --- oracles ---------------------------------------------------------
    def best_subset(
        self, size: int, objective: str = "target", budget: float | None = None
    ) -> dict[str, object]:
        """Exhaustive optimum over subsets of ``size`` experiments.

        ``objective`` selects the value being maximised: ``target`` uses
        ``I(T;Y_A)``, ``hypothesis`` uses ``I(Theta;Y_A)``.  This is the ground
        truth the greedy policy is measured against.
        """
        value_of = (
            self.information_about_target
            if objective == "target"
            else self.information_about_hypothesis
        )
        best: tuple[float, tuple[str, ...]] | None = None
        evaluated = 0
        for combo in combinations([item.key for item in self.experiments], size):
            if budget is not None and self.total_cost(combo) > budget:
                continue
            evaluated += 1
            value = value_of(combo)
            if best is None or value > best[0] + 1e-12:
                best = (value, combo)
        if best is None:
            return {"subset": (), "value": 0.0, "evaluated": evaluated, "feasible": False}
        return {
            "subset": best[1],
            "value": best[0],
            "evaluated": evaluated,
            "feasible": True,
            "objective": objective,
        }

    def submodularity_report(self, objective: str = "target", max_experiments: int = 7) -> dict[str, object]:
        """Test the diminishing-returns inequality on this instance.

        Submodularity of ``f(A) = I(T;Y_A)`` requires, for all ``A subset B`` and
        ``e not in B``:  ``f(A+e) - f(A) >= f(B+e) - f(B)``.  This enumerates all
        such triples, so the verdict is exact for the instance.

        KNOWN_RESULT: mutual information is submodular when the observations are
        conditionally independent given the target (Krause & Guestrin 2005), and is
        *not* submodular in general.  A violation found here is therefore expected
        behaviour of the objective, not a bug -- and it invalidates the
        ``1 - 1/e`` greedy guarantee (Nemhauser, Wolsey & Fisher 1978).
        """
        keys = [item.key for item in self.experiments]
        if len(keys) > max_experiments:
            return {
                "status": "UNKNOWN",
                "reason": f"{len(keys)} experiments exceeds the exhaustive limit {max_experiments}",
            }
        value_of = (
            self.information_about_target
            if objective == "target"
            else self.information_about_hypothesis
        )
        cache: dict[frozenset[str], float] = {}

        def value(subset: frozenset[str]) -> float:
            if subset not in cache:
                cache[subset] = value_of(tuple(sorted(subset)))
            return cache[subset]

        violations: list[dict[str, object]] = []
        checked = 0
        universe = frozenset(keys)
        subsets = [frozenset(combo) for size in range(len(keys) + 1) for combo in combinations(keys, size)]
        for smaller in subsets:
            for larger in subsets:
                if not smaller <= larger:
                    continue
                for element in sorted(universe - larger):
                    checked += 1
                    small_gain = value(smaller | {element}) - value(smaller)
                    large_gain = value(larger | {element}) - value(larger)
                    if large_gain > small_gain + 1e-9:
                        violations.append(
                            {
                                "subset": sorted(smaller),
                                "superset": sorted(larger),
                                "element": element,
                                "small_gain": small_gain,
                                "large_gain": large_gain,
                            }
                        )
        return {
            "status": "COUNTEREXAMPLE" if violations else "VERIFIED_FINITE_CASE",
            "objective": objective,
            "triples_checked": checked,
            "violations": violations[:4],
            "violation_count": len(violations),
            "greedy_guarantee_applies": not violations,
            "guarantee": "1 - 1/e for cardinality-constrained monotone submodular maximisation",
        }


def _uniform(items: Sequence[Hashable]) -> dict[Hashable, Fraction]:
    return {item: Fraction(1, len(items)) for item in items}


# --- world A: rarity is not surprise -------------------------------------
def rare_but_uninformative_world() -> HypothesisWorld:
    """An experiment with a very rare outcome that carries zero information.

    ``coin`` returns ``"rare"`` for one hypothesis out of eight, so observing it
    is surprising in the *rarity* sense (-log2 p = 3 bits) -- but the outcome is
    a deterministic function of a variable independent of the target, so the
    posterior over the target does not move at all.

    Distinction demonstrated: RARITY != BAYESIAN SURPRISE about the target.
    """
    hypotheses = tuple((flag, index) for flag in (0, 1) for index in range(4))
    return HypothesisWorld(
        name="rare_but_uninformative",
        hypotheses=hypotheses,
        prior=_uniform(hypotheses),
        experiments=(
            # Outcome is rare (only theta with index 0 and flag 1) but depends on
            # `index`, which the target ignores.
            Experiment("rare_nuisance", 1.0, lambda theta: "rare" if theta[1] == 0 else "common"),
            Experiment("decisive", 1.0, lambda theta: theta[0]),
        ),
        target=lambda theta: theta[0],
        truth=(1, 0),
        note="rarity of an outcome is not information about the target",
    )


# --- world B: surprise about a nuisance ----------------------------------
def nuisance_surprise_world() -> HypothesisWorld:
    """Positive Bayesian surprise with zero target information.

    ``nuisance`` fully determines the second component of the hypothesis, so it
    moves the posterior over Theta a lot (surprise > 0) while ``I(T;Y) = 0``.

    Distinction demonstrated: SURPRISE ABOUT THETA != INFORMATION FOR THE DECISION.
    """
    hypotheses = tuple((flag, index) for flag in (0, 1) for index in range(4))
    return HypothesisWorld(
        name="nuisance_surprise",
        hypotheses=hypotheses,
        prior=_uniform(hypotheses),
        experiments=(
            Experiment("nuisance", 1.0, lambda theta: theta[1]),
            Experiment("decisive", 3.0, lambda theta: theta[0]),
        ),
        target=lambda theta: theta[0],
        truth=(0, 2),
        note="an experiment can be surprising about Theta and useless for T",
    )


# --- world D: greedy is optimal ------------------------------------------
def conditionally_independent_world() -> HypothesisWorld:
    """Three noisy-but-independent probes of a 3-bit target.

    Each experiment reveals one bit of the target and nothing else, so the
    observations are conditionally independent given ``T`` and the objective is
    submodular -- the regime where the greedy guarantee is valid.
    """
    hypotheses = tuple(
        (a, b, c) for a in (0, 1) for b in (0, 1) for c in (0, 1)
    )
    return HypothesisWorld(
        name="conditionally_independent",
        hypotheses=hypotheses,
        prior=_uniform(hypotheses),
        experiments=(
            Experiment("bit0", 1.0, lambda theta: theta[0]),
            Experiment("bit1", 1.0, lambda theta: theta[1]),
            Experiment("bit2", 1.0, lambda theta: theta[2]),
        ),
        target=lambda theta: theta,
        truth=(1, 0, 1),
        note="conditionally independent observations: submodular, greedy has a guarantee",
    )


# --- world E: the greedy counterexample ----------------------------------
def decoy_parity_world(decoy_bits: Fraction = Fraction(1, 8)) -> HypothesisWorld:
    """The VIZZ anti-world: greedy information gain is arbitrarily suboptimal.

    The target is the parity ``a XOR b``.  Experiments ``probe_a`` and ``probe_b``
    each reveal one input, so *individually* they carry **zero** information about
    the parity; together they determine it exactly (1 bit).  A third experiment
    ``decoy`` reveals a variable correlated with the parity only weakly.

    With a budget of two experiments, greedy on marginal information gain picks
    ``decoy`` first (the only strictly positive marginal), and afterwards the
    remaining marginals are still smaller than the decoy's, so greedy collects
    only the decoy's few bits.  The exhaustive optimum picks ``{probe_a, probe_b}``
    and gets the full bit.

    Making the decoy's information smaller drives the greedy/optimal ratio to
    zero, so no constant-factor guarantee can hold.  This is the standard
    non-submodularity of mutual information (Krause & Guestrin 2005) instantiated
    so it can be executed and measured.
    """
    # theta = (a, b, d) with d a weak indicator of the parity.
    hypotheses: list[Hashable] = []
    for a in (0, 1):
        for b in (0, 1):
            for d in (0, 1):
                hypotheses.append((a, b, d))
    # P(d = parity) = 1/2 + epsilon so that I(d; parity) is small but positive.
    weight_agree = Fraction(1, 8) + decoy_bits / 8
    weight_disagree = Fraction(1, 8) - decoy_bits / 8
    prior: dict[Hashable, Fraction] = {}
    for a, b, d in hypotheses:
        parity = a ^ b
        prior[(a, b, d)] = weight_agree if d == parity else weight_disagree
    return HypothesisWorld(
        name="decoy_parity",
        hypotheses=tuple(hypotheses),
        prior=prior,
        experiments=(
            Experiment("probe_a", 1.0, lambda theta: theta[0]),
            Experiment("probe_b", 1.0, lambda theta: theta[1]),
            Experiment("decoy", 1.0, lambda theta: theta[2]),
        ),
        target=lambda theta: theta[0] ^ theta[1],
        truth=(1, 0, 1),
        note="parity target: individual probes are useless, the pair is decisive",
    )


# --- world C: informative but unaffordable -------------------------------
def expensive_information_world() -> HypothesisWorld:
    """A decisive experiment priced out of the budget.

    ``decisive`` resolves the target completely but costs more than the budget the
    operator is given, so the correct answer is to take the cheap partial
    experiment or to ABSTAIN -- not to select the highest-information option.
    """
    hypotheses = tuple((a, b) for a in (0, 1) for b in (0, 1))
    return HypothesisWorld(
        name="expensive_information",
        hypotheses=hypotheses,
        prior=_uniform(hypotheses),
        experiments=(
            Experiment("decisive", 100.0, lambda theta: theta),
            Experiment("cheap_partial", 1.0, lambda theta: theta[0]),
        ),
        target=lambda theta: theta,
        truth=(1, 1),
        note="highest information gain is not affordable",
    )

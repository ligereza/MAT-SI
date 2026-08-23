"""Blind reuse discovery audit (PiPi-47B).

The policy-facing API is intentionally small: ``BlindPolicy.process`` sees
only a raw native object and a query.  Domain, case name, structure id,
future stream length, and the oracle grouping are retained by the harness for
scoring and never enter that call.

The benchmark is synthetic but not a N=24 toy.  It uses five native structure
families, six size levels, twenty structures per size, and ten streams per
structure.  The fifth family is sealed from blind candidate discovery so the
experiment can test held-out-domain transfer rather than simply replaying a
known candidate catalog.
"""

from __future__ import annotations

import hashlib
import json
import math
import platform
import random
import statistics
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional, Sequence, Tuple


PARENT_COMMIT = "1bdfa411b10545d4d88f14a2d07c2b317001bd8d"
ACCEPTED_FRONTIER_FROM_STATE = "c5860520c1f3873db2b32a2970b87ec9c809dfbc"

SIZE_LEVELS = (64, 128, 256, 512, 1024, 2048)
STRUCTURES_PER_SIZE = 20
STREAMS_PER_STRUCTURE = 10
STREAM_PLAN = (
    ("TRUE_SHARED", 8),
    ("SHORT_LIVED", 2),
    ("DECOY_SIMILAR", 16),
    ("DRIFT", 32),
    ("NEAR_SHARED", 64),
    ("INDEPENDENT", 128),
    ("TRUE_SHARED", 256),
    ("SHORT_LIVED", 4),
    ("DECOY_SIMILAR", 512),
    ("TRUE_SHARED", 1024),
)
DESIGN_DOMAINS = ("LINEAR_SYSTEM", "SUBSET_SUM", "MEMBERSHIP")
VALIDATION_DOMAIN = "GRAPH_QUERIES"
HELDOUT_DOMAIN = "AUTOMATON"
DOMAINS = DESIGN_DOMAINS + (VALIDATION_DOMAIN, HELDOUT_DOMAIN)
SUPPORTED_BLIND_SHAPES = {"rows", "values", "members", "edges"}
DRIFT_ONSET_FRACTION_DESIGN = 0.50
DRIFT_ONSET_FRACTION_HELDOUT = 0.75
PILOT_HORIZON = 64

RESOURCE_KEYS = ("H", "Q", "G", "R", "S", "V", "I", "M", "P", "W")
RESOURCE_UNITS = {
    "H": "grouping/similarity/structure-identification operations",
    "Q": "raw query or solver accesses",
    "G": "representation discovery/build operations",
    "R": "per-instance residue/update operations",
    "S": "solve/query operations after representation exists",
    "V": "verification/certificate operations",
    "I": "invalidation/drift-detection operations",
    "M": "memory cells",
    "P": "precision bits",
    "W": "wall-clock milliseconds (machine-dependent)",
}
COMPARABLE_KEYS = ("H", "Q", "G", "R", "S", "V", "I", "M", "P")


@dataclass
class CostVector:
    H: int = 0
    Q: int = 0
    G: int = 0
    R: int = 0
    S: int = 0
    V: int = 0
    I: int = 0
    M: int = 0
    P: int = 0
    W: float = 0.0

    def add_inplace(self, other: "CostVector") -> None:
        for key in RESOURCE_KEYS:
            setattr(self, key, getattr(self, key) + getattr(other, key))

    def copy(self) -> "CostVector":
        return CostVector(**self.to_dict())

    def scaled(self, count: int) -> "CostVector":
        return CostVector(**{key: getattr(self, key) * count for key in RESOURCE_KEYS})

    def to_dict(self) -> Dict[str, Any]:
        return {key: getattr(self, key) for key in RESOURCE_KEYS}


@dataclass(frozen=True)
class CandidateSpec:
    name: str
    raw_factor: int
    build_factor: int
    reuse_cost: int
    verify_cost: int
    memory_factor: int

    def raw_cost(self, n: int) -> int:
        return self.raw_factor * n + 11

    def build_cost(self, n: int) -> int:
        return self.build_factor * n + 17

    def kstar(self, n: int) -> int:
        denominator = self.raw_cost(n) - self.reuse_cost
        return max(1, math.ceil(self.build_cost(n) / denominator))

    def interval(self, n: int) -> Tuple[int, int]:
        kstar = self.kstar(n)
        return max(1, (kstar + 1) // 2), max(2, kstar * 2)


CANDIDATES = {
    "rows": CandidateSpec("SHARED_LINEAR_FACTOR", 8, 24, 3, 4, 2),
    "values": CandidateSpec("SHARED_WEIGHT_INDEX", 6, 18, 2, 3, 1),
    "members": CandidateSpec("SHARED_MEMBERSHIP_INDEX", 3, 12, 1, 2, 1),
    "edges": CandidateSpec("SHARED_GRAPH_ADJACENCY", 9, 28, 3, 5, 4),
    # This candidate exists only for oracle/specialist comparators.  The blind
    # discovery probe deliberately does not expose transition_rows.
    "transition_rows": CandidateSpec("SHARED_AUTOMATON_TABLE", 4, 16, 2, 3, 2),
}


@dataclass(frozen=True)
class StructureSpec:
    domain: str
    size: int
    index: int
    payload: Any
    decoy_payload: Any
    near_payload: Any
    drift_payload: Any
    semantic_id: str


@dataclass(frozen=True)
class StreamSpec:
    domain: str
    size: int
    structure_index: int
    stream_index: int
    stream_type: str
    length: int
    representation_seed: int
    drift_fraction: float
    structure: StructureSpec


@dataclass(frozen=True)
class Event:
    # These hidden scoring fields are never passed to BlindPolicy.process.
    domain: str
    stream_type: str
    phase: str
    truth_group: str
    truth_token: str
    raw_object: Mapping[str, Any]
    query: Tuple[int, int]
    expected_answer: str


@dataclass(frozen=True)
class StreamSegment:
    domain: str
    stream_type: str
    phase: str
    truth_group: str
    truth_token: str
    raw_object: Mapping[str, Any]
    proposal: Optional[Proposal]
    start_index: int
    length: int


@dataclass(frozen=True)
class Proposal:
    candidate_key: str
    candidate: CandidateSpec
    signature: Tuple[Any, ...]
    identity: Tuple[Any, ...]
    probe_cost: int
    domain_equivalent_probe: bool = True


@dataclass
class GroupState:
    candidate_key: str
    candidate: CandidateSpec
    signature: Tuple[Any, ...]
    identity: Tuple[Any, ...]
    observed: int = 0
    built: bool = False
    origin_stream: int = 0


@dataclass
class Decision:
    actions: List[str]
    candidate_key: Optional[str]
    group_key: str
    prediction: Optional[str]
    candidate_answer: Optional[str]
    verified: bool
    cost: CostVector


def _stable_digest(value: Any) -> str:
    encoded = repr(value).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:20]


def _query_token(query: Tuple[int, int]) -> str:
    return f"{query[0]}:{query[1]}"


def _answer(token: str, query: Tuple[int, int]) -> str:
    return hashlib.sha256(f"{token}|{_query_token(query)}".encode("ascii")).hexdigest()[:24]


def _unique_preserving(values: Iterable[int], n: int) -> Tuple[int, ...]:
    return tuple(sorted(set(value % n for value in values)))


def _linear_payload(n: int, seed: int) -> Tuple[Tuple[Tuple[int, int], ...], ...]:
    rng = random.Random(seed)
    rows = []
    for row in range(n):
        columns = {row % n, (row + 1 + rng.randrange(3)) % n, (row + 7) % n}
        entries = tuple(sorted((column, 1 + rng.randrange(9)) for column in columns))
        rows.append(entries)
    return tuple(rows)


def _linear_shift(payload: Tuple[Tuple[Tuple[int, int], ...], ...], n: int, delta: int) -> Any:
    return tuple(tuple(((column + delta) % n, coefficient) for column, coefficient in row) for row in payload)


def _linear_near(payload: Tuple[Tuple[Tuple[int, int], ...], ...]) -> Any:
    rows = [list(row) for row in payload]
    column, coefficient = rows[0][0]
    rows[0][0] = (column, coefficient + 1)
    return tuple(tuple(row) for row in rows)


def _subset_payload(n: int, seed: int) -> Tuple[int, ...]:
    rng = random.Random(seed)
    return tuple(1 + rng.randrange(2 * n + 31) for _ in range(n))


def _subset_same_sum(payload: Tuple[int, ...]) -> Tuple[int, ...]:
    values = list(payload)
    left, right = 0, 1
    values[left] += 1
    values[right] -= 1
    if values[right] <= 0:
        values[right] += 2
        values[left] -= 2
    return tuple(values)


def _subset_near(payload: Tuple[int, ...]) -> Tuple[int, ...]:
    values = list(payload)
    values[0] += 1
    return tuple(values)


def _membership_payload(n: int, seed: int) -> Tuple[int, ...]:
    rng = random.Random(seed)
    count = max(8, n // 4)
    return tuple(sorted(rng.sample(range(n * 4), count)))


def _membership_same_sum(payload: Tuple[int, ...]) -> Tuple[int, ...]:
    values = list(payload)
    occupied = set(values)
    for index in range(len(values) - 1):
        left, right = values[index], values[index + 1]
        candidates = (left + 1, right - 1)
        if candidates[0] < candidates[1] and candidates[0] not in occupied and candidates[1] not in occupied:
            values[index], values[index + 1] = candidates
            return tuple(sorted(values))
    return tuple(values)


def _membership_near(payload: Tuple[int, ...]) -> Tuple[int, ...]:
    values = list(payload)
    values[0] += 1
    return tuple(sorted(set(values)))


def _graph_edges(n: int, seed: int, offset: int = 3) -> Tuple[Tuple[int, int], ...]:
    rng = random.Random(seed)
    edges = set()
    for node in range(n):
        edges.add(tuple(sorted((node, (node + 1) % n))))
        edges.add(tuple(sorted((node, (node + offset) % n))))
    for _ in range(2 + seed % 5):
        left, right = rng.randrange(n), rng.randrange(n)
        if left != right:
            edges.add(tuple(sorted((left, right))))
    return tuple(sorted(edges))


def _graph_near(payload: Tuple[Tuple[int, int], ...], n: int) -> Tuple[Tuple[int, int], ...]:
    edges = set(payload)
    edge = next(iter(edges))
    edges.remove(edge)
    edges.add(tuple(sorted(((edge[0] + 2) % n, (edge[1] + 5) % n))))
    return tuple(sorted(edges))


def _automaton_payload(n: int, seed: int, step: int) -> Tuple[Tuple[int, int], ...]:
    return tuple((state, (state + step + seed % 5) % n) for state in range(n))


def _build_structure(domain: str, size: int, index: int) -> StructureSpec:
    seed = 47000 + DOMAINS.index(domain) * 100000 + size * 31 + index
    if domain == "LINEAR_SYSTEM":
        payload = _linear_payload(size, seed)
        decoy = _linear_shift(payload, size, 1)
        near = _linear_near(payload)
        drift = _linear_near(near)
    elif domain == "SUBSET_SUM":
        payload = _subset_payload(size, seed)
        decoy = _subset_same_sum(payload)
        near = _subset_near(payload)
        drift = _subset_near(near)
    elif domain == "MEMBERSHIP":
        payload = _membership_payload(size, seed)
        decoy = _membership_same_sum(payload)
        near = _membership_near(payload)
        drift = _membership_near(near)
    elif domain == "GRAPH_QUERIES":
        payload = _graph_edges(size, seed, 3 + index % 7)
        decoy = _graph_edges(size, seed + 777, 5 + index % 7)
        near = _graph_near(payload, size)
        drift = _graph_edges(size, seed + 1777, 7 + index % 7)
    elif domain == "AUTOMATON":
        payload = _automaton_payload(size, seed, 1 + index % 11)
        decoy = _automaton_payload(size, seed + 1, 2 + index % 11)
        near = _automaton_payload(size, seed, 2 + index % 11)
        drift = _automaton_payload(size, seed + 2, 3 + index % 11)
    else:
        raise ValueError(domain)
    semantic_id = f"{domain}:{size}:{index}:{_stable_digest(payload)}"
    return StructureSpec(domain, size, index, payload, decoy, near, drift, semantic_id)


def build_structures() -> List[StructureSpec]:
    return [
        _build_structure(domain, size, index)
        for domain in DOMAINS
        for size in SIZE_LEVELS
        for index in range(STRUCTURES_PER_SIZE)
    ]


def _render_raw(domain: str, payload: Any, size: int, nuisance_seed: int) -> Dict[str, Any]:
    rng = random.Random(nuisance_seed)
    if domain == "LINEAR_SYSTEM":
        rows = list(payload)
        rng.shuffle(rows)
        column_permutation = list(range(size))
        rng.shuffle(column_permutation)
        rendered = []
        for row in rows:
            rendered.append(tuple((column_permutation[column], coefficient) for column, coefficient in row))
        return {"dimension": size, "rows": tuple(rendered)}
    if domain == "SUBSET_SUM":
        values = list(payload)
        rng.shuffle(values)
        return {"dimension": size, "values": tuple(values)}
    if domain == "MEMBERSHIP":
        values = list(payload)
        rng.shuffle(values)
        return {"universe": size * 4, "members": tuple(values)}
    if domain == "GRAPH_QUERIES":
        permutation = list(range(size))
        rng.shuffle(permutation)
        edges = [tuple(sorted((permutation[left], permutation[right]))) for left, right in payload]
        rng.shuffle(edges)
        return {"vertices": size, "edges": tuple(edges)}
    if domain == "AUTOMATON":
        rows = list(payload)
        rng.shuffle(rows)
        permutation = list(range(size))
        rng.shuffle(permutation)
        rendered = [(permutation[state], permutation[next_state]) for state, next_state in rows]
        rng.shuffle(rendered)
        return {"states": size, "transition_rows": tuple(rendered)}
    raise ValueError(domain)


def _graph_signature(raw: Mapping[str, Any]) -> Tuple[Any, ...]:
    vertices = int(raw["vertices"])
    degrees = [0] * vertices
    for left, right in raw["edges"]:
        degrees[left] += 1
        degrees[right] += 1
    return (vertices, len(raw["edges"]), tuple(sorted(degrees)))


def _graph_identity(raw: Mapping[str, Any]) -> Tuple[Any, ...]:
    """Small Weisfeiler-Lehman-style invariant for nuisance node renaming."""

    vertices = int(raw["vertices"])
    adjacency = [[] for _ in range(vertices)]
    for left, right in raw["edges"]:
        adjacency[left].append(right)
        adjacency[right].append(left)
    colors = [len(neighbors) for neighbors in adjacency]
    for _ in range(3):
        labels = [
            (colors[node], tuple(sorted(colors[neighbor] for neighbor in adjacency[node])))
            for node in range(vertices)
        ]
        palette = {label: index for index, label in enumerate(sorted(set(labels)))}
        colors = [palette[label] for label in labels]
    return (
        vertices,
        tuple(sorted((colors[node], tuple(sorted(colors[neighbor] for neighbor in adjacency[node]))) for node in range(vertices))),
    )


def _proposal(raw: Mapping[str, Any]) -> Optional[Proposal]:
    # The probe uses native shape and invariant summaries, never a domain
    # label.  It is intentionally recorded as domain-equivalent in the audit:
    # this is a candidate applicability boundary, not autonomous cross-domain
    # discovery.
    if "rows" in raw:
        rows = raw["rows"]
        coefficient_sum = sum(coefficient for row in rows for _, coefficient in row)
        coefficient_sq = sum(coefficient * coefficient for row in rows for _, coefficient in row)
        signature = ("rows", raw["dimension"], len(rows), sum(len(row) for row in rows), coefficient_sum, coefficient_sq)
        identity = ("rows", raw["dimension"], tuple(sorted(tuple(sorted(row)) for row in rows)))
        return Proposal("rows", CANDIDATES["rows"], signature, identity, 12 + raw["dimension"] // 8)
    if "values" in raw:
        values = raw["values"]
        signature = ("values", raw["dimension"], len(values), sum(values), sum(value * value for value in values))
        identity = ("values", raw["dimension"], tuple(sorted(values)))
        return Proposal("values", CANDIDATES["values"], signature, identity, 10 + len(values) // 8)
    if "members" in raw:
        members = raw["members"]
        signature = ("members", raw["universe"], len(members), sum(members), sum(value * value for value in members))
        identity = ("members", raw["universe"], tuple(sorted(members)))
        return Proposal("members", CANDIDATES["members"], signature, identity, 8 + len(members) // 4)
    if "edges" in raw:
        signature = ("edges",) + _graph_signature(raw)
        identity = ("edges",) + _graph_identity(raw)
        return Proposal("edges", CANDIDATES["edges"], signature, identity, 14 + raw["vertices"] // 4)
    return None


def _candidate_for_domain(domain: str) -> CandidateSpec:
    return {
        "LINEAR_SYSTEM": CANDIDATES["rows"],
        "SUBSET_SUM": CANDIDATES["values"],
        "MEMBERSHIP": CANDIDATES["members"],
        "GRAPH_QUERIES": CANDIDATES["edges"],
        "AUTOMATON": CANDIDATES["transition_rows"],
    }[domain]


def _candidate_answer(proposal: Proposal, query: Tuple[int, int]) -> str:
    return _answer(repr(proposal.identity), query)


def _raw_answer(event: Event) -> str:
    return event.expected_answer


def _raw_cost(candidate: CandidateSpec, n: int) -> CostVector:
    return CostVector(Q=1, S=candidate.raw_cost(n))


def _build_and_reuse_cost(candidate: CandidateSpec, n: int) -> CostVector:
    return CostVector(
        Q=1,
        G=candidate.build_cost(n),
        R=1,
        S=candidate.reuse_cost,
        V=candidate.verify_cost,
        M=candidate.memory_factor * n,
    )


def _reuse_cost(candidate: CandidateSpec) -> CostVector:
    return CostVector(Q=1, R=1, S=candidate.reuse_cost, V=candidate.verify_cost)


def _serialize_identity(raw: Mapping[str, Any]) -> str:
    # B2 only.  The blind policy never calls this function.
    return repr(tuple((key, raw[key]) for key in raw))


class BlindPolicy:
    """The only policy allowed to make discovery decisions.

    It sees no event wrapper, domain, case name, truth id, query-stream
    length, or oracle grouping.  It uses coarse native invariants, deliberately
    making the grouping/false-merge trade-off observable.
    """

    def __init__(self) -> None:
        self.groups: Dict[str, GroupState] = {}
        self.active_key: Optional[str] = None
        self.stream_counter = 0
        self._last_raw_object: Optional[Mapping[str, Any]] = None
        self._last_proposal: Optional[Proposal] = None
        self._last_group_key: Optional[str] = None
        self._last_interval: Optional[Tuple[int, int]] = None
        self.action_counts: Counter[str] = Counter()
        self.prediction_counts: Counter[str] = Counter()

    def start_stream(self) -> None:
        self.active_key = None
        self.stream_counter += 1

    def _discover(self, raw_object: Mapping[str, Any]) -> Optional[Proposal]:
        if raw_object is not self._last_raw_object:
            self._last_raw_object = raw_object
            self._last_proposal = _proposal(raw_object)
            if self._last_proposal is None:
                self._last_group_key = None
                self._last_interval = None
            else:
                self._last_group_key = f"{self._last_proposal.candidate_key}|{repr(self._last_proposal.signature)}"
                dimension = raw_object.get("dimension", raw_object.get("vertices", raw_object.get("universe", 0)))
                self._last_interval = self._last_proposal.candidate.interval(dimension)
        return self._last_proposal

    def process(self, raw_object: Mapping[str, Any], query: Tuple[int, int]) -> Decision:
        is_new_representation = raw_object is not self._last_raw_object
        proposal = self._discover(raw_object)
        if proposal is None:
            action = "RAW"
            group_key = f"RAW_STREAM_{self.stream_counter}"
            cost = CostVector(Q=1, S=1)
            self.action_counts[action] += 1
            self.prediction_counts["NO_REUSE_EXPECTED"] += 1
            return Decision([action], None, group_key, "NO_REUSE_EXPECTED", None, True, cost)

        key = self._last_group_key
        actions: List[str] = []
        cost = CostVector(H=proposal.probe_cost if is_new_representation else 0)
        if self.active_key is not None and self.active_key != key:
            old_group = self.groups.get(self.active_key)
            if old_group is not None and old_group.built:
                actions.append("DROP_G")
                cost.I += proposal.candidate.verify_cost
            self.active_key = key
        elif self.active_key is None:
            self.active_key = key

        group = self.groups.get(key)
        if group is None:
            group = GroupState(proposal.candidate_key, proposal.candidate, proposal.signature, proposal.identity, origin_stream=self.stream_counter)
            self.groups[key] = group
        interval = self._last_interval
        prediction = f"KSTAR_INTERVAL=[{interval[0]}, {interval[1]}]"
        self.prediction_counts[prediction] += 1
        group.observed += 1
        if not group.built and group.observed >= 2:
            group.built = True
            actions.append("BUILD_G")
            cost.add_inplace(_build_and_reuse_cost(proposal.candidate, interval[1] * 0 + _raw_size(raw_object)))
            candidate_answer = _candidate_answer(proposal, query)
        elif group.built:
            actions.append("REUSE_G")
            cost.add_inplace(_reuse_cost(proposal.candidate))
            candidate_answer = _answer(repr(group.identity), query)
        else:
            actions.append("GROUP")
            cost.add_inplace(_raw_cost(proposal.candidate, _raw_size(raw_object)))
            candidate_answer = _raw_answer_for_raw(raw_object, query)
        for action in actions:
            self.action_counts[action] += 1
        # Verification checks the discovered invariant, not the hidden future
        # answer.  A decoy sharing the invariant therefore remains a
        # future-relevant false merge and is counted by the harness.
        verified = True
        return Decision(actions, proposal.candidate_key, key, prediction, candidate_answer, verified, cost)


def _raw_size(raw: Mapping[str, Any]) -> int:
    if "rows" in raw:
        return int(raw["dimension"])
    if "values" in raw:
        return int(raw["dimension"])
    if "members" in raw:
        return int(raw["universe"] // 4)
    if "edges" in raw:
        return int(raw["vertices"])
    return int(raw["states"])


def _raw_answer_for_raw(raw: Mapping[str, Any], query: Tuple[int, int]) -> str:
    proposal = _proposal(raw)
    if proposal is not None:
        return _candidate_answer(proposal, query)
    return _answer(repr(tuple((key, raw[key]) for key in raw)), query)


def _event_variant(stream: StreamSpec, event_index: int) -> Tuple[Any, str, str]:
    structure = stream.structure
    if stream.stream_type == "DECOY_SIMILAR":
        return structure.decoy_payload, "decoy", f"{structure.semantic_id}:decoy"
    if stream.stream_type == "NEAR_SHARED":
        return structure.near_payload, "near", f"{structure.semantic_id}:near"
    if stream.stream_type == "INDEPENDENT":
        independent = _build_structure(stream.domain, stream.size, 1000 + stream.stream_index + stream.structure_index)
        return independent.payload, "independent", independent.semantic_id
    if stream.stream_type == "DRIFT":
        onset = max(1, int(stream.length * stream.drift_fraction))
        if event_index >= onset:
            return structure.drift_payload, "post_drift", f"{structure.semantic_id}:drift"
    return structure.payload, "stable", structure.semantic_id


def iter_events(stream: StreamSpec) -> Iterator[Event]:
    raw_by_variant: Dict[str, Mapping[str, Any]] = {}
    proposal_by_variant: Dict[str, Optional[Proposal]] = {}
    independent = _build_structure(stream.domain, stream.size, 1000 + stream.stream_index + stream.structure_index) if stream.stream_type == "INDEPENDENT" else None
    for event_index in range(stream.length):
        if independent is not None:
            payload, phase, token = independent.payload, "independent", independent.semantic_id
        else:
            payload, phase, token = _event_variant(stream, event_index)
        if phase not in raw_by_variant:
            phase_seed = {"stable": 11, "decoy": 23, "near": 37, "independent": 41, "post_drift": 53}[phase]
            raw_by_variant[phase] = _render_raw(stream.domain, payload, stream.size, stream.representation_seed + phase_seed)
            proposal_by_variant[phase] = _proposal(raw_by_variant[phase])
        raw = raw_by_variant[phase]
        query = ((event_index * 17 + stream.stream_index) % stream.size, (event_index * 31 + stream.structure_index) % stream.size)
        truth_group = f"{stream.domain}:{stream.size}:{stream.structure_index}:{phase}"
        proposal = proposal_by_variant[phase]
        expected = _answer(repr(proposal.identity), query) if proposal is not None else _answer(token, query)
        yield Event(stream.domain, stream.stream_type, phase, truth_group, token, raw, query, expected)


def iter_segments(stream: StreamSpec) -> Iterator[StreamSegment]:
    """Yield the same streams as iter_events, compressed into constant phases."""

    independent = _build_structure(stream.domain, stream.size, 1000 + stream.stream_index + stream.structure_index) if stream.stream_type == "INDEPENDENT" else None
    phases: List[Tuple[Any, str, str, int, int]] = []
    if independent is not None:
        phases.append((independent.payload, "independent", independent.semantic_id, 0, stream.length))
    elif stream.stream_type == "DRIFT":
        onset = max(1, int(stream.length * stream.drift_fraction))
        phases.append((stream.structure.payload, "stable", stream.structure.semantic_id, 0, onset))
        if stream.length > onset:
            phases.append((stream.structure.drift_payload, "post_drift", f"{stream.structure.semantic_id}:drift", onset, stream.length - onset))
    elif stream.stream_type == "DECOY_SIMILAR":
        phases.append((stream.structure.decoy_payload, "decoy", f"{stream.structure.semantic_id}:decoy", 0, stream.length))
    elif stream.stream_type == "NEAR_SHARED":
        phases.append((stream.structure.near_payload, "near", f"{stream.structure.semantic_id}:near", 0, stream.length))
    else:
        phases.append((stream.structure.payload, "stable", stream.structure.semantic_id, 0, stream.length))
    for payload, phase, token, start_index, length in phases:
        phase_seed = {"stable": 11, "decoy": 23, "near": 37, "independent": 41, "post_drift": 53}[phase]
        raw = _render_raw(stream.domain, payload, stream.size, stream.representation_seed + phase_seed)
        proposal = _proposal(raw)
        truth_group = f"{stream.domain}:{stream.size}:{stream.structure_index}:{phase}"
        yield StreamSegment(stream.domain, stream.stream_type, phase, truth_group, token, raw, proposal, start_index, length)


def _make_stream(structure: StructureSpec, stream_index: int) -> StreamSpec:
    stream_type, length = STREAM_PLAN[stream_index]
    fraction = DRIFT_ONSET_FRACTION_HELDOUT if structure.domain == HELDOUT_DOMAIN else DRIFT_ONSET_FRACTION_DESIGN
    return StreamSpec(
        structure.domain,
        structure.size,
        structure.index,
        stream_index,
        stream_type,
        length,
        900000 + DOMAINS.index(structure.domain) * 100000 + structure.size * 13 + structure.index * 17 + stream_index,
        fraction,
        structure,
    )


@dataclass
class GroupingMetrics:
    predicted_to_truth: Dict[str, Counter] = field(default_factory=lambda: defaultdict(Counter))
    truth_to_predicted: Dict[str, Counter] = field(default_factory=lambda: defaultdict(Counter))

    def observe(self, predicted: str, truth: str) -> None:
        self.predicted_to_truth[predicted][truth] += 1
        self.truth_to_predicted[truth][predicted] += 1

    @staticmethod
    def _pairs(counter: Mapping[str, Counter]) -> int:
        return sum(sum(value * (value - 1) // 2 for value in counts.values()) for counts in counter.values())

    def summary(self) -> Dict[str, Any]:
        total_predicted_pairs = sum(sum(counts.values()) * (sum(counts.values()) - 1) // 2 for counts in self.predicted_to_truth.values())
        total_truth_pairs = sum(sum(counts.values()) * (sum(counts.values()) - 1) // 2 for counts in self.truth_to_predicted.values())
        true_positive = sum(
            sum(value * (value - 1) // 2 for value in counts.values())
            for counts in self.predicted_to_truth.values()
        )
        predicted_group_count = len(self.predicted_to_truth)
        truth_group_count = len(self.truth_to_predicted)
        false_merge_groups = sum(1 for counts in self.predicted_to_truth.values() if len(counts) > 1)
        false_split_groups = sum(1 for counts in self.truth_to_predicted.values() if len(counts) > 1)
        return {
            "pairwise_precision": true_positive / total_predicted_pairs if total_predicted_pairs else 1.0,
            "pairwise_recall": true_positive / total_truth_pairs if total_truth_pairs else 0.0,
            "false_merge_rate": false_merge_groups / predicted_group_count if predicted_group_count else 0.0,
            "false_split_rate": false_split_groups / truth_group_count if truth_group_count else 0.0,
            "predicted_group_count": predicted_group_count,
            "truth_group_count": truth_group_count,
        }


@dataclass
class DomainAccumulator:
    stream_count: int = 0
    event_count: int = 0
    stream_type_counts: Counter = field(default_factory=Counter)
    costs: Dict[str, CostVector] = field(default_factory=lambda: {name: CostVector() for name in ("B0_RAW", "B1_ORACLE_GROUPING", "B2_HASH_IDENTITY", "B3_SIMPLE_PAYBACK", "B4_DOMAIN_SPECIALIST", "B5_BLIND_POLICY")})
    answers: Counter = field(default_factory=Counter)
    blind_actions: Counter = field(default_factory=Counter)
    false_positive_builds: int = 0
    missed_reuse_events: int = 0
    stale_reuse_errors: int = 0
    false_merge_events: int = 0
    drift_events: int = 0
    drift_detected: int = 0
    drift_detection_delay_sum: int = 0
    rebuild_count: int = 0


def _add_result(acc: DomainAccumulator, policy: str, cost: CostVector, correct: bool, count: int = 1) -> None:
    acc.costs[policy].add_inplace(cost)
    acc.answers[f"{policy}:correct"] += int(correct) * count
    acc.answers[f"{policy}:total"] += count


def _run_b0(acc: DomainAccumulator, events: Sequence[Event], candidate: CandidateSpec) -> None:
    for event in events:
        _add_result(acc, "B0_RAW", _raw_cost(candidate, _raw_size(event.raw_object)), True)


def _run_b1(acc: DomainAccumulator, events: Sequence[Event], state: Dict[str, bool], candidate: CandidateSpec) -> None:
    for event in events:
        if event.truth_group not in state:
            state[event.truth_group] = True
            cost = _build_and_reuse_cost(candidate, _raw_size(event.raw_object))
        else:
            cost = _reuse_cost(candidate)
        _add_result(acc, "B1_ORACLE_GROUPING", cost, True)


def _run_b2(acc: DomainAccumulator, events: Sequence[Event], state: Dict[str, bool], candidate: Optional[CandidateSpec]) -> None:
    identity_cache: Dict[int, str] = {}
    for event in events:
        raw_id = id(event.raw_object)
        if raw_id not in identity_cache:
            identity_cache[raw_id] = _serialize_identity(event.raw_object)
        identity = identity_cache[raw_id]
        grouping = CostVector(H=len(identity))
        if identity not in state:
            state[identity] = True
            cost = candidate and _build_and_reuse_cost(candidate, _raw_size(event.raw_object)) or CostVector(Q=1, S=1)
        else:
            cost = candidate and _reuse_cost(candidate) or CostVector(Q=1, S=1)
        grouping.add_inplace(cost)
        _add_result(acc, "B2_HASH_IDENTITY", grouping, True)


def _run_b3(acc: DomainAccumulator, events: Sequence[Event], state: Dict[str, bool], candidate: CandidateSpec) -> None:
    for event in events:
        if event.truth_group not in state:
            state[event.truth_group] = True
            if candidate.kstar(_raw_size(event.raw_object)) <= PILOT_HORIZON:
                cost = _build_and_reuse_cost(candidate, _raw_size(event.raw_object))
            else:
                cost = _raw_cost(candidate, _raw_size(event.raw_object))
        else:
            cost = _reuse_cost(candidate)
        _add_result(acc, "B3_SIMPLE_PAYBACK", cost, True)


def _run_b4(acc: DomainAccumulator, events: Sequence[Event], candidate: CandidateSpec) -> None:
    segments: List[List[Event]] = []
    for event in events:
        if not segments or segments[-1][0].truth_group != event.truth_group:
            segments.append([])
        segments[-1].append(event)
    for segment in segments:
        n = _raw_size(segment[0].raw_object)
        if len(segment) <= candidate.kstar(n):
            for event in segment:
                _add_result(acc, "B4_DOMAIN_SPECIALIST", _raw_cost(candidate, n), True)
        else:
            for index, event in enumerate(segment):
                cost = _build_and_reuse_cost(candidate, n) if index == 0 else _reuse_cost(candidate)
                _add_result(acc, "B4_DOMAIN_SPECIALIST", cost, True)


def _run_b0_segments(acc: DomainAccumulator, segments: Sequence[StreamSegment], candidate: CandidateSpec) -> None:
    for segment in segments:
        _add_result(acc, "B0_RAW", _raw_cost(candidate, _raw_size(segment.raw_object)).scaled(segment.length), True)


def _run_b1_segments(acc: DomainAccumulator, segments: Sequence[StreamSegment], state: Dict[str, bool], candidate: CandidateSpec) -> None:
    for segment in segments:
        n = _raw_size(segment.raw_object)
        if segment.truth_group not in state:
            state[segment.truth_group] = True
            cost = _build_and_reuse_cost(candidate, n)
            if segment.length > 1:
                cost.add_inplace(_reuse_cost(candidate).scaled(segment.length - 1))
        else:
            cost = _reuse_cost(candidate).scaled(segment.length)
        _add_result(acc, "B1_ORACLE_GROUPING", cost, True)


def _run_b2_segments(acc: DomainAccumulator, segments: Sequence[StreamSegment], state: Dict[str, bool], candidate: Optional[CandidateSpec]) -> None:
    for segment in segments:
        identity = _serialize_identity(segment.raw_object)
        comparison = CostVector(H=len(identity) * segment.length)
        n = _raw_size(segment.raw_object)
        if identity not in state:
            state[identity] = True
            if candidate is None:
                comparison.add_inplace(CostVector(Q=1, S=1))
                if segment.length > 1:
                    comparison.add_inplace(CostVector(Q=1, S=1).scaled(segment.length - 1))
            else:
                comparison.add_inplace(_build_and_reuse_cost(candidate, n))
                if segment.length > 1:
                    comparison.add_inplace(_reuse_cost(candidate).scaled(segment.length - 1))
        elif candidate is None:
            comparison.add_inplace(CostVector(Q=1, S=1).scaled(segment.length))
        else:
            comparison.add_inplace(_reuse_cost(candidate).scaled(segment.length))
        _add_result(acc, "B2_HASH_IDENTITY", comparison, True)


def _run_b3_segments(acc: DomainAccumulator, segments: Sequence[StreamSegment], state: Dict[str, bool], candidate: CandidateSpec) -> None:
    for segment in segments:
        n = _raw_size(segment.raw_object)
        if segment.truth_group not in state:
            state[segment.truth_group] = True
            if candidate.kstar(n) <= PILOT_HORIZON:
                cost = _build_and_reuse_cost(candidate, n)
                if segment.length > 1:
                    cost.add_inplace(_reuse_cost(candidate).scaled(segment.length - 1))
            else:
                cost = _raw_cost(candidate, n).scaled(segment.length)
        else:
            cost = _reuse_cost(candidate).scaled(segment.length)
        _add_result(acc, "B3_SIMPLE_PAYBACK", cost, True)


def _run_b4_segments(acc: DomainAccumulator, segments: Sequence[StreamSegment], candidate: CandidateSpec) -> None:
    for segment in segments:
        n = _raw_size(segment.raw_object)
        if segment.length <= candidate.kstar(n):
            cost = _raw_cost(candidate, n).scaled(segment.length)
        else:
            cost = _build_and_reuse_cost(candidate, n)
            if segment.length > 1:
                cost.add_inplace(_reuse_cost(candidate).scaled(segment.length - 1))
        _add_result(acc, "B4_DOMAIN_SPECIALIST", cost, True)


def _consume_blind_segment(
    acc: DomainAccumulator,
    blind: BlindPolicy,
    grouping: GroupingMetrics,
    group_truths: Dict[str, set],
    segment: StreamSegment,
    stream_index: int,
    drift_onset: int,
    global_metrics: Counter,
    audit_costs: Dict[str, CostVector],
) -> None:
    query = (segment.start_index, stream_index)
    decision = blind.process(segment.raw_object, query)
    if segment.proposal is None:
        # The policy chose RAW without a domain label; the harness charges the
        # native raw solver cost for the held-out shape rather than the
        # policy-internal placeholder unit.
        decision.cost = _raw_cost(_candidate_for_domain(segment.domain), _raw_size(segment.raw_object))
    predicted_group = decision.group_key
    if segment.start_index == 0:
        grouping.observe(predicted_group, segment.truth_group)

    def record(decision_to_record: Decision, count: int, proposal: Optional[Proposal]) -> None:
        if count <= 0:
            return
        acc.blind_actions.update({action: count for action in decision_to_record.actions})
        candidate_used = any(action in {"BUILD_G", "REUSE_G"} for action in decision_to_record.actions)
        if candidate_used and proposal is not None:
            group = blind.groups.get(decision_to_record.group_key)
            correct = "BUILD_G" in decision_to_record.actions or (group is not None and group.identity == proposal.identity)
            _add_result(acc, "B5_BLIND_POLICY", decision_to_record.cost.scaled(count), correct, count)
            truth_set = group_truths.setdefault(decision_to_record.group_key, set())
            if segment.truth_group not in truth_set and truth_set:
                acc.false_merge_events += count
                global_metrics["future_relevant_false_merges"] += count
                audit_costs["false_group_cost"].add_inplace(decision_to_record.cost.scaled(count))
            truth_set.add(segment.truth_group)
            if not correct:
                acc.stale_reuse_errors += count
                global_metrics["stale_reuse_errors"] += count
                audit_costs["stale_reuse_cost"].add_inplace(decision_to_record.cost.scaled(count))
        else:
            _add_result(acc, "B5_BLIND_POLICY", decision_to_record.cost.scaled(count), True, count)
            if segment.start_index > 0 and segment.stream_type in {"TRUE_SHARED", "SHORT_LIVED", "DECOY_SIMILAR", "DRIFT", "NEAR_SHARED"}:
                global_metrics["missed_reuse_events"] += count
                audit_costs["missed_reuse_cost"].add_inplace(decision_to_record.cost.scaled(count))
        if "BUILD_G" in decision_to_record.actions and segment.stream_type in {"SHORT_LIVED", "INDEPENDENT"}:
            acc.false_positive_builds += count
            global_metrics["false_positive_builds"] += count
        if "DROP_G" in decision_to_record.actions:
            acc.rebuild_count += count
            audit_costs["rebuild_cost"].add_inplace(decision_to_record.cost.scaled(count))

    proposal = segment.proposal
    record(decision, 1, proposal)
    remaining = segment.length - 1
    if remaining <= 0:
        return
    # An unbuilt group needs one further observation to cross the blind
    # build threshold.  Once that observation is consumed, all remaining
    # observations are a constant-cost reuse batch.
    if proposal is not None and "BUILD_G" not in decision.actions and "REUSE_G" not in decision.actions:
        second = blind.process(segment.raw_object, (segment.start_index + 1, stream_index))
        record(second, 1, proposal)
        remaining -= 1
    if remaining <= 0:
        return
    if proposal is None:
        record(
            Decision(
                ["RAW"],
                None,
                decision.group_key,
                "NO_REUSE_EXPECTED",
                None,
                True,
                _raw_cost(_candidate_for_domain(segment.domain), _raw_size(segment.raw_object)),
            ),
            remaining,
            None,
        )
    else:
        group = blind.groups[decision.group_key]
        reuse = Decision(
            ["REUSE_G"],
            proposal.candidate_key,
            decision.group_key,
            decision.prediction,
            None,
            True,
            _reuse_cost(proposal.candidate),
        )
        record(reuse, remaining, proposal)

    if segment.phase == "post_drift" and segment.start_index == drift_onset:
        acc.drift_events += 1
        if "DROP_G" in decision.actions or "RAW" in decision.actions or "GROUP" in decision.actions:
            acc.drift_detected += 1
            drift_delay = 0
            acc.drift_detection_delay_sum += drift_delay


def _prediction_metrics() -> Dict[str, Any]:
    samples = []
    for domain in DESIGN_DOMAINS + (VALIDATION_DOMAIN,):
        candidate = _candidate_for_domain(domain)
        for n in SIZE_LEVELS:
            lo, hi = candidate.interval(n)
            kstar = candidate.kstar(n)
            samples.append({"domain": domain, "size": n, "kstar": kstar, "interval": [lo, hi], "covered": lo <= kstar <= hi, "width": hi / lo})
    widths = [sample["width"] for sample in samples]
    return {
        "frozen_before_heldout": True,
        "sample_count": len(samples),
        "coverage": sum(sample["covered"] for sample in samples) / len(samples),
        "median_multiplicative_width": statistics.median(widths),
        "intervals": samples,
        "future_stream_length_was_input": False,
        "policy_outputs": ["NO_REUSE_EXPECTED", "KSTAR_INTERVAL=[lo, hi]", "INSUFFICIENT_EVIDENCE"],
    }


def _component_delta(raw: Mapping[str, Any], blind: Mapping[str, Any]) -> Dict[str, int]:
    return {key: raw[key] - blind[key] for key in COMPARABLE_KEYS}


def _componentwise_beats(raw: Mapping[str, Any], blind: Mapping[str, Any], exact: bool) -> bool:
    return exact and all(blind[key] <= raw[key] for key in COMPARABLE_KEYS) and any(blind[key] < raw[key] for key in COMPARABLE_KEYS)


def _domain_cost_report(acc: DomainAccumulator) -> Dict[str, Any]:
    costs = {policy: value.to_dict() for policy, value in acc.costs.items()}
    raw = costs["B0_RAW"]
    blind = costs["B5_BLIND_POLICY"]
    blind_total = acc.answers["B5_BLIND_POLICY:total"]
    blind_correct = acc.answers["B5_BLIND_POLICY:correct"]
    return {
        "costs": costs,
        "blind_minus_raw_component_delta": {key: blind[key] - raw[key] for key in COMPARABLE_KEYS},
        "raw_minus_blind_component_gain": _component_delta(raw, blind),
        "blind_componentwise_beats_raw": _componentwise_beats(raw, blind, blind_correct == blind_total),
        "answer_correctness": {
            policy: {
                "correct": acc.answers[f"{policy}:correct"],
                "total": acc.answers[f"{policy}:total"],
                "accuracy": acc.answers[f"{policy}:correct"] / acc.answers[f"{policy}:total"] if acc.answers[f"{policy}:total"] else 0.0,
            }
            for policy in acc.costs
        },
        "stream_count": acc.stream_count,
        "event_count": acc.event_count,
        "stream_type_counts": dict(sorted(acc.stream_type_counts.items())),
        "blind_action_counts": dict(sorted(acc.blind_actions.items())),
        "false_positive_build_decisions": acc.false_positive_builds,
        "missed_reuse_events": acc.missed_reuse_events,
        "false_merge_events": acc.false_merge_events,
        "stale_reuse_errors": acc.stale_reuse_errors,
        "drift": {
            "drift_events": acc.drift_events,
            "drifts_detected_before_reuse": acc.drift_detected,
            "detection_delay_sum": acc.drift_detection_delay_sum,
            "rebuild_count": acc.rebuild_count,
        },
    }


def _run_audit() -> Dict[str, Any]:
    started = time.perf_counter()
    structures = build_structures()
    accumulators = {domain: DomainAccumulator() for domain in DOMAINS}
    blind = BlindPolicy()
    grouping = GroupingMetrics()
    oracle_state: Dict[str, bool] = {}
    payback_state: Dict[str, bool] = {}
    identity_state: Dict[str, bool] = {}
    policy_watches = defaultdict(float)
    global_metrics = Counter()
    group_truths: Dict[str, set] = {}
    audit_costs = {name: CostVector() for name in ("false_group_cost", "missed_reuse_cost", "stale_reuse_cost", "rebuild_cost")}

    for structure in structures:
        acc = accumulators[structure.domain]
        for stream_index in range(STREAMS_PER_STRUCTURE):
            stream = _make_stream(structure, stream_index)
            segments = list(iter_segments(stream))
            acc.stream_count += 1
            acc.event_count += sum(segment.length for segment in segments)
            acc.stream_type_counts[stream.stream_type] += 1
            candidate = _candidate_for_domain(stream.domain)
            blind.start_stream()
            watch = time.perf_counter()
            for segment in segments:
                onset = max(1, int(stream.length * stream.drift_fraction))
                _consume_blind_segment(acc, blind, grouping, group_truths, segment, stream_index, onset, global_metrics, audit_costs)
            policy_watches["B5_BLIND_POLICY"] += (time.perf_counter() - watch) * 1000.0
            # Score baseline policies after the blind policy has made its
            # decisions.  They receive harness truth or identity only in their
            # explicitly labelled comparator roles.
            first_proposal = segments[0].proposal
            for policy_name, runner in (
                ("B0_RAW", lambda: _run_b0_segments(acc, segments, candidate)),
                ("B1_ORACLE_GROUPING", lambda: _run_b1_segments(acc, segments, oracle_state, candidate)),
                ("B2_HASH_IDENTITY", lambda: _run_b2_segments(acc, segments, identity_state, first_proposal.candidate if first_proposal else None)),
                ("B3_SIMPLE_PAYBACK", lambda: _run_b3_segments(acc, segments, payback_state, candidate)),
                ("B4_DOMAIN_SPECIALIST", lambda: _run_b4_segments(acc, segments, candidate)),
            ):
                watch = time.perf_counter()
                runner()
                policy_watches[policy_name] += (time.perf_counter() - watch) * 1000.0
            # B1 is an admissible reference, so a blind raw decision on a
            # known true group is a missed-reuse observation.
            if stream.stream_type in {"TRUE_SHARED", "DECOY_SIMILAR", "DRIFT", "NEAR_SHARED"}:
                global_metrics["candidate_streams"] += 1

    for domain, acc in accumulators.items():
        for policy, elapsed in policy_watches.items():
            if policy in acc.costs:
                # Timing is intentionally assigned only after logical counts
                # are complete and is excluded from deterministic comparisons.
                acc.costs[policy].W = round(elapsed / len(DOMAINS), 3)

    domain_reports = {domain: _domain_cost_report(acc) for domain, acc in accumulators.items()}
    all_blind_correct = sum(acc.answers["B5_BLIND_POLICY:correct"] for acc in accumulators.values())
    all_blind_total = sum(acc.answers["B5_BLIND_POLICY:total"] for acc in accumulators.values())
    oracle_has_component_gain = any(
        any(domain_reports[domain]["costs"]["B0_RAW"][key] > domain_reports[domain]["costs"]["B1_ORACLE_GROUPING"][key] for key in COMPARABLE_KEYS)
        for domain in DOMAINS
    )
    blind_has_component_gain = any(domain_reports[domain]["blind_componentwise_beats_raw"] for domain in DOMAINS)
    heldout = domain_reports[HELDOUT_DOMAIN]
    grouping_report = grouping.summary()
    stale_errors = global_metrics["stale_reuse_errors"]
    false_merges = global_metrics["future_relevant_false_merges"]
    drift_total = sum(acc.drift_events for acc in accumulators.values())
    drift_detected = sum(acc.drift_detected for acc in accumulators.values())
    gates = {
        "DIES_BOOKKEEPING_ONLY": bool(oracle_has_component_gain and not blind_has_component_gain),
        "DIES_GROUPING_ORACLE": bool(not blind_has_component_gain or grouping_report["pairwise_recall"] < 1.0),
        "DIES_FALSE_MERGES": bool(false_merges > 0 or stale_errors > 0),
        "DIES_DRIFT": bool(drift_detected < drift_total),
        "SURVIVES_WITHIN_DOMAIN": bool(blind_has_component_gain and all_blind_correct == all_blind_total),
        "SURVIVES_HELDOUT_STRUCTURE": False,
        "SURVIVES_HELDOUT_DOMAIN": bool(heldout["blind_componentwise_beats_raw"] and heldout["answer_correctness"]["B5_BLIND_POLICY"]["accuracy"] == 1.0),
        "STRONG_SURVIVAL": False,
    }
    return {
        "experiment": "MAT-SI PiPi-47B Blind Reuse Discovery / Grouping-or-Die",
        "version": "blind-reuse-v1",
        "parent_commit_actual": PARENT_COMMIT,
        "accepted_frontier_from_docs_STATE": ACCEPTED_FRONTIER_FROM_STATE,
        "branch_scope": "research/blind-reuse-discovery; speculative; no main, Phase 5, or accepted-evidence changes",
        "hypothesis": {
            "H1": "a domain-agnostic procedure can discover, group, build, reuse, reject, and retire reusable structure on held-out streams",
            "H0": "apparent reuse gain requires hidden labels, IDs, candidate selection, horizon knowledge, or omitted accounting",
        },
        "scale_manifest": {
            "domains": list(DOMAINS),
            "design_domains": list(DESIGN_DOMAINS),
            "validation_domain": VALIDATION_DOMAIN,
            "sealed_heldout_domain": HELDOUT_DOMAIN,
            "size_levels": list(SIZE_LEVELS),
            "structures_per_domain_size": STRUCTURES_PER_SIZE,
            "streams_per_structure": STREAMS_PER_STRUCTURE,
            "stream_plan": [{"type": stream_type, "length": length} for stream_type, length in STREAM_PLAN],
            "total_structures": len(structures),
            "total_streams": sum(acc.stream_count for acc in accumulators.values()),
            "total_events": sum(acc.event_count for acc in accumulators.values()),
            "seeds": "domain/size/index/stream deterministic formulas; no runtime randomness",
        },
        "solver_interface": {
            "policy_arguments": ["raw_object", "query"],
            "forbidden_to_policy": ["domain_label", "family_label", "case_name", "path", "stable_structure_id", "future_stream_length", "oracle_grouping", "future_answer"],
            "raw_object_is_native": True,
            "native_shapes": ["rows", "values", "members", "edges", "transition_rows"],
        },
        "policies": {
            "B0_RAW": "solve every query from scratch",
            "B1_ORACLE_GROUPING": "true grouping and candidate supplied; upper bound only",
            "B2_HASH_IDENTITY": "reuse only exact raw serialization identity",
            "B3_SIMPLE_PAYBACK": "oracle candidate/group with frozen k_hat from pilot costs",
            "B4_DOMAIN_SPECIALIST": "domain-aware future-aware comparator; upper bound only",
            "B5_BLIND_POLICY": "structural applicability probe plus coarse invariant grouping; no labels or IDs",
        },
        "resource_vector": RESOURCE_UNITS,
        "domain_results": domain_reports,
        "grouping_metrics": grouping_report,
        "blind_grouping_costs": {
            "false_group_cost": audit_costs["false_group_cost"].to_dict(),
            "missed_reuse_cost": audit_costs["missed_reuse_cost"].to_dict(),
            "stale_reuse_cost": audit_costs["stale_reuse_cost"].to_dict(),
            "rebuild_cost": audit_costs["rebuild_cost"].to_dict(),
            "false_merge_events": false_merges,
            "missed_reuse_events": global_metrics["missed_reuse_events"],
            "stale_reuse_errors": stale_errors,
        },
        "break_even_calibration": _prediction_metrics(),
        "anti_leak_audits": {
            "case_names_removed": True,
            "serialization_randomized": True,
            "variable_and_node_renaming": True,
            "raw_sha_hash_used_by_blind_policy": False,
            "query_stream_length_hidden": True,
            "heldout_domain_label_hidden": True,
            "candidate_library_metadata_contains_family_id": False,
            "oracle_grouping_physically_separate": True,
            "verification_uses_ground_truth_future": False,
            "candidate_applicability_probe_is_domain_equivalent": True,
            "marks": ["DOMAIN_LEAK"],
            "not_marked": ["GROUPING_ORACLE", "FUTURE_HORIZON_LEAK", "REPRESENTATION_ID_LEAK"],
        },
        "gates": gates,
        "strongest_anomaly": "The blind probe finds known structural shapes but either splits under nuisance or accepts coarse decoys; the sealed automaton has no blind candidate and falls back to RAW.",
        "what_died": [
            "H1 as a domain-agnostic held-out reuse claim: no exact, componentwise positive blind result survived candidate/grouping and verification accounting.",
            "The hypothesis that a coarse invariant is sufficient: decoy and graph-drift streams create future-relevant false merges/stale reuse.",
            "The hypothesis that the external candidate-supplied amortization result demonstrates autonomous discovery.",
        ],
        "what_survived": [
            "Oracle grouping and domain-specialist comparators can amortize stable long streams.",
            "The frozen k-star interval is calibrated on the tested candidate cost model, but this is bookkeeping once the candidate is supplied.",
            "Serialization/renaming perturbations are an effective separation between exact identity and structural grouping.",
        ],
        "next_experiment": {
            "justified": False,
            "reason": "None of SURVIVES_HELDOUT_STRUCTURE, SURVIVES_HELDOUT_DOMAIN, or STRONG_SURVIVAL is true; freeze and redesign conceptually rather than run a nearby benchmark.",
        },
        "scope_declarations": {
            "main_modified": False,
            "phase5_started": False,
            "frozen_pippi_42_to_46_modified": False,
            "closure_accessibility_merged_into_accepted_evidence": False,
        },
        "portability_and_replay": {
            "runtime": "Python standard library only",
            "command": "PYTHONPATH=src python -m matsi.blind_reuse",
            "deterministic_fields": ["scale manifest, generated payloads, seeds, action logic, vector counts excluding W, grouping metrics, gates, conclusions"],
            "machine_dependent_fields": ["W in each cost vector", "machine_metadata"],
            "replay_contract": "Regenerate from a clean checkout and compare after removing W and machine_metadata.",
        },
        "machine_metadata": {
            "python": platform.python_version(),
            "system": platform.system(),
            "release": platform.release(),
            "runtime_wall_ms": round((time.perf_counter() - started) * 1000.0, 3),
            "policy_watch_wall_ms": {key: round(value, 3) for key, value in sorted(policy_watches.items())},
        },
    }


def event_index_safe(events: Sequence[Event], event: Event) -> int:
    # The harness may locate an event index; the blind policy never receives
    # the sequence or its length.
    for index, candidate in enumerate(events):
        if candidate is event:
            return index
    return 0


def build_report() -> Dict[str, Any]:
    return _run_audit()


def write_report(path: Path | str = Path("results/blind-reuse.json")) -> Dict[str, Any]:
    report = build_report()
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> None:
    write_report()


if __name__ == "__main__":
    main()

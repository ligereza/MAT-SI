"""An e-graph with equality saturation and cost-parametrised extraction.

An e-graph stores a congruence relation over terms compactly: each e-class is a
set of equivalent e-nodes, and an e-node's children are e-class ids, so one graph
represents exponentially many equivalent terms (Nelson 1980; Willsey et al.,
*egg: Fast and Extensible Equality Saturation*, POPL 2021).

Three properties matter for X-ANA-X and each is labelled honestly:

* **Soundness of merging** -- PROVED for the rules supplied: ``apply_rules`` only
  merges classes related by an instance of a supplied rewrite rule, so if every
  rule is a valid equation in the intended semantics, every merged pair is
  semantically equal.  Validity of the *rules themselves* is not assumed; the
  rule set used in the experiments is checked by an independent verifier.
* **Saturation** -- may not terminate in general, since a rule set can generate
  infinitely many terms (associativity plus commutativity over an unbounded
  signature).  ``saturate`` therefore reports whether it reached a fixpoint or hit
  a limit.  It never pretends a truncated run is saturated.
* **Extraction** -- for a monotone cost function this computes the least fixpoint
  of the cost equations, which is the minimum *tree* cost. Minimising cost with
  shared subexpressions (DAG cost) is NP-hard -- KNOWN_RESULT (Stepp 2011;
  discussed in the egg paper) -- and is not attempted here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Hashable, Iterator, Sequence

from .terms import CostFunction, Pattern, Term, children, head_key, is_hole, is_leaf

ENode = tuple[Hashable, tuple[int, ...]]


@dataclass
class SaturationReport:
    """What a saturation run actually did."""

    iterations: int = 0
    saturated: bool = False
    stopped_by: str = "fixpoint"
    merges: int = 0
    nodes_added: int = 0
    rule_applications: dict[str, int] = field(default_factory=dict)
    class_count: int = 0
    node_count: int = 0
    match_truncated: bool = False
    dropped_directions: tuple[str, ...] = ()

    def as_measurement(self) -> dict[str, Any]:
        return {
            "iterations": self.iterations,
            "saturated": self.saturated,
            "stopped_by": self.stopped_by,
            "merges": self.merges,
            "nodes_added": self.nodes_added,
            "rule_applications": dict(sorted(self.rule_applications.items())),
            "class_count": self.class_count,
            "node_count": self.node_count,
            "match_truncated": self.match_truncated,
            "dropped_directions": list(self.dropped_directions),
        }


@dataclass(frozen=True)
class Rule:
    """One oriented or bidirectional rewrite rule between patterns."""

    name: str
    lhs: Pattern
    rhs: Pattern
    bidirectional: bool = True

    def instances(self) -> tuple[tuple[Pattern, Pattern], ...]:
        """Usable directions of this rule.

        A direction whose left-hand side is a bare hole is dropped: it matches
        every e-class, so applying it would merge unrelated classes and destroy
        the congruence.  Identity-introduction directions such as ``a -> a + 0``
        fall in this category, so the congruence the e-graph generates is the one
        induced by the *kept* directions only.  ``dropped_directions`` names them
        so the limitation is visible rather than silent.
        """
        directions = [(self.lhs, self.rhs)]
        if self.bidirectional:
            directions.append((self.rhs, self.lhs))
        return tuple((lhs, rhs) for lhs, rhs in directions if not is_hole(lhs))

    def dropped_directions(self) -> tuple[str, ...]:
        directions = [(self.lhs, self.rhs)]
        if self.bidirectional:
            directions.append((self.rhs, self.lhs))
        return tuple(
            f"{self.name}:{'forward' if index == 0 else 'reverse'}"
            for index, (lhs, _rhs) in enumerate(directions)
            if is_hole(lhs)
        )


class EGraph:
    """Congruence-closed union-find over e-nodes."""

    def __init__(self) -> None:
        self._parent: dict[int, int] = {}
        self._classes: dict[int, set[ENode]] = {}
        self._hashcons: dict[ENode, int] = {}
        self._pending: list[int] = []
        self._next_id = 0
        # A read-only snapshot installed during one rewrite pass, so matching does
        # not pay for recomputing the class index at every pattern node.
        self._snapshot: dict[int, set[ENode]] | None = None
        self._match_truncated = False
        self._dropped_directions: set[str] = set()

    # --- union-find -------------------------------------------------------
    def find(self, class_id: int) -> int:
        root = class_id
        while self._parent[root] != root:
            root = self._parent[root]
        while self._parent[class_id] != root:
            self._parent[class_id], class_id = root, self._parent[class_id]
        return root

    def _new_class(self, node: ENode) -> int:
        class_id = self._next_id
        self._next_id += 1
        self._parent[class_id] = class_id
        self._classes[class_id] = {node}
        return class_id

    def _canonical(self, node: ENode) -> ENode:
        head, kids = node
        return (head, tuple(self.find(kid) for kid in kids))

    # --- construction -----------------------------------------------------
    def add_node(self, head: Hashable, kids: Sequence[int]) -> int:
        node = self._canonical((head, tuple(kids)))
        existing = self._hashcons.get(node)
        if existing is not None:
            return self.find(existing)
        class_id = self._new_class(node)
        self._hashcons[node] = class_id
        return class_id

    def add_term(self, term: Term) -> int:
        kids = [self.add_term(child) for child in children(term)]
        return self.add_node(head_key(term), kids)

    def merge(self, left: int, right: int) -> bool:
        left, right = self.find(left), self.find(right)
        if left == right:
            return False
        # Union by size keeps the tree shallow deterministically.
        if len(self._classes[left]) < len(self._classes[right]):
            left, right = right, left
        self._parent[right] = left
        self._classes[left] |= self._classes.pop(right)
        self._pending.append(left)
        return True

    def rebuild(self) -> int:
        """Restore congruence: equal nodes with equal children share a class."""
        merges = 0
        while self._pending:
            todo = {self.find(class_id) for class_id in self._pending}
            self._pending.clear()
            for class_id in todo:
                nodes = self._classes.get(class_id)
                if nodes is None:
                    continue
                canonical = {self._canonical(node) for node in nodes}
                self._classes[class_id] = canonical
                for node in canonical:
                    previous = self._hashcons.get(node)
                    self._hashcons[node] = class_id
                    if previous is not None and self.find(previous) != self.find(class_id):
                        if self.merge(previous, class_id):
                            merges += 1
        return merges

    # --- inspection -------------------------------------------------------
    def classes(self) -> dict[int, set[ENode]]:
        if self._snapshot is not None:
            return self._snapshot
        result: dict[int, set[ENode]] = {}
        for class_id, nodes in self._classes.items():
            root = self.find(class_id)
            result.setdefault(root, set()).update(self._canonical(node) for node in nodes)
        return result

    def _index_by_head(
        self, snapshot: dict[int, set[ENode]]
    ) -> dict[tuple[Hashable, int], list[tuple[int, ENode]]]:
        """Group nodes by ``(head, arity)`` so matching does not rescan everything."""
        index: dict[tuple[Hashable, int], list[tuple[int, ENode]]] = {}
        for class_id, nodes in snapshot.items():
            for node in nodes:
                index.setdefault((node[0], len(node[1])), []).append((class_id, node))
        return index

    def class_count(self) -> int:
        return len(self.classes())

    def node_count(self) -> int:
        return sum(len(nodes) for nodes in self.classes().values())

    def equivalent(self, left: Term, right: Term) -> bool:
        """Whether the two terms are already in the same class of this e-graph.

        This is a statement about the congruence generated by the rules applied so
        far, not a semantic claim.  A ``False`` here means "not proved equal by
        these rules", never "different".
        """
        return self.find(self.add_term(left)) == self.find(self.add_term(right))

    # --- e-matching -------------------------------------------------------
    def match(self, pattern: Pattern, class_id: int) -> Iterator[dict[str, int]]:
        yield from self._match(pattern, self.find(class_id), {})

    def _match(self, pattern: Pattern, class_id: int, subst: dict[str, int]) -> Iterator[dict[str, int]]:
        if is_hole(pattern):
            name = pattern[1]
            bound = subst.get(name)
            if bound is None:
                yield {**subst, name: class_id}
            elif self.find(bound) == class_id:
                yield subst
            return
        target_head = head_key(pattern)
        arity = 0 if is_leaf(pattern) else len(pattern) - 1
        for node in self.classes().get(class_id, set()):
            if node[0] != target_head or len(node[1]) != arity:
                continue
            yield from self._match_node(pattern, node, subst)

    def _match_node(self, pattern: Pattern, node: ENode, subst: dict[str, int]) -> Iterator[dict[str, int]]:
        """Match a non-hole pattern against one specific e-node."""
        _head, kids = node
        arity = 0 if is_leaf(pattern) else len(pattern) - 1
        partial = [subst]
        for index in range(arity):
            nxt: list[dict[str, int]] = []
            for candidate in partial:
                nxt.extend(self._match(pattern[index + 1], self.find(kids[index]), candidate))
            partial = nxt
            if not partial:
                break
        yield from partial

    def instantiate(self, pattern: Pattern, subst: dict[str, int]) -> int:
        if is_hole(pattern):
            name = pattern[1]
            if name not in subst:
                raise KeyError(f"unbound pattern hole ?{name}")
            return self.find(subst[name])
        kids = [] if is_leaf(pattern) else [
            self.instantiate(child, subst) for child in pattern[1:]
        ]
        return self.add_node(head_key(pattern), kids)

    # --- saturation -------------------------------------------------------
    def apply_rules(self, rules: Sequence[Rule], match_limit: int = 20_000) -> tuple[int, int, dict[str, int]]:
        """One rewrite pass: match against a frozen snapshot, merge, rebuild.

        Matching runs against a snapshot taken before any merge, so a rule cannot
        cascade within its own pass; that keeps one pass deterministic and makes
        the iteration count meaningful.
        """
        before_nodes = self.node_count()
        found: list[tuple[str, int, Pattern, dict[str, int]]] = []
        self._snapshot = self.classes()
        index = self._index_by_head(self._snapshot)
        truncated = False
        try:
            for rule in rules:
                for dropped in rule.dropped_directions():
                    self._dropped_directions.add(dropped)
                for lhs, rhs in rule.instances():
                    key = (head_key(lhs), 0 if is_leaf(lhs) else len(lhs) - 1)
                    for class_id, node in index.get(key, ()):
                        for subst in self._match_node(lhs, node, {}):
                            found.append((rule.name, class_id, rhs, dict(subst)))
                            if len(found) >= match_limit:
                                truncated = True
                                raise StopIteration
        except StopIteration:
            pass
        finally:
            self._snapshot = None
        merges = 0
        if truncated:
            self._match_truncated = True
        applications: dict[str, int] = {}
        for name, class_id, rhs, subst in found:
            new_id = self.instantiate(rhs, subst)
            applications[name] = applications.get(name, 0) + 1
            if self.merge(class_id, new_id):
                merges += 1
        merges += self.rebuild()
        return merges, self.node_count() - before_nodes, applications

    def saturate(
        self,
        rules: Sequence[Rule],
        max_iterations: int = 30,
        node_limit: int = 20_000,
    ) -> SaturationReport:
        report = SaturationReport()
        for iteration in range(1, max_iterations + 1):
            report.iterations = iteration
            merges, added, applications = self.apply_rules(rules)
            report.merges += merges
            report.nodes_added += max(0, added)
            for name, count in applications.items():
                report.rule_applications[name] = report.rule_applications.get(name, 0) + count
            if merges == 0 and added <= 0:
                report.saturated = True
                report.stopped_by = "fixpoint"
                break
            if self.node_count() > node_limit:
                report.stopped_by = "node_limit"
                break
            if self._match_truncated:
                report.stopped_by = "match_limit"
                break
        else:
            report.stopped_by = "iteration_limit"
        report.class_count = self.class_count()
        report.node_count = self.node_count()
        report.match_truncated = self._match_truncated
        report.dropped_directions = tuple(sorted(self._dropped_directions))
        return report

    # --- extraction -------------------------------------------------------
    def extract(self, cost: CostFunction, class_id: int) -> tuple[Term | None, float]:
        """Least-cost tree in ``class_id`` under a monotone cost function.

        Computes the least fixpoint of
        ``c(class) = min over nodes of cost(head, c(children))``
        by relaxation.  Each pass is monotone non-increasing and the number of
        e-classes is finite, so the iteration terminates; the pass cap is
        ``class_count + 1``, matching the longest possible improvement chain.
        This is the shortest-hyperpath problem, solvable exactly for superior cost
        functions -- KNOWN_RESULT (Knuth, *A generalization of Dijkstra's
        algorithm*, 1977).
        """
        classes = self.classes()
        best_cost: dict[int, float] = {cid: float("inf") for cid in classes}
        best_node: dict[int, ENode | None] = {cid: None for cid in classes}
        for _ in range(len(classes) + 1):
            changed = False
            for cid in sorted(classes):
                for head, kids in sorted(classes[cid], key=repr):
                    child_costs = tuple(best_cost[self.find(kid)] for kid in kids)
                    if any(value == float("inf") for value in child_costs):
                        continue
                    candidate = cost(head, child_costs)
                    if candidate < best_cost[cid] - 1e-12:
                        best_cost[cid] = candidate
                        best_node[cid] = (head, kids)
                        changed = True
            if not changed:
                break
        root = self.find(class_id)
        if best_node.get(root) is None:
            return None, float("inf")

        def build(cid: int) -> Term:
            head, kids = best_node[self.find(cid)]  # type: ignore[misc]
            if not kids:
                return head if isinstance(head, tuple) else (head,)
            return (head, *(build(kid) for kid in kids))

        return build(root), best_cost[root]

    def enumerate_terms(self, class_id: int, max_depth: int = 4, limit: int = 4000) -> list[Term]:
        """Every term of bounded depth in a class; the extraction ground truth.

        Exponential by nature, so it is only ever used on small e-graphs to check
        that ``extract`` really returns a minimum.
        """
        classes = self.classes()
        memo: dict[tuple[int, int], list[Term]] = {}

        def build(cid: int, depth: int) -> list[Term]:
            key = (self.find(cid), depth)
            if key in memo:
                return memo[key]
            if depth <= 0:
                memo[key] = []
                return []
            out: list[Term] = []
            for head, kids in sorted(classes.get(self.find(cid), set()), key=repr):
                if not kids:
                    out.append(head if isinstance(head, tuple) else (head,))
                    continue
                options = [build(kid, depth - 1) for kid in kids]
                if any(not option for option in options):
                    continue
                combos: list[tuple[Term, ...]] = [()]
                for option in options:
                    combos = [combo + (item,) for combo in combos for item in option]
                    if len(combos) > limit:
                        combos = combos[:limit]
                for combo in combos:
                    out.append((head, *combo))
                    if len(out) >= limit:
                        break
                if len(out) >= limit:
                    break
            memo[key] = out
            return out

        return build(class_id, max_depth)

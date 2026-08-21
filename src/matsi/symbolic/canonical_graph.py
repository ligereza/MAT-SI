"""Canonical labelling of small graphs by refinement plus bounded search.

Colour refinement (1-dimensional Weisfeiler-Leman) is computed first, then the
canonical form is the lexicographically least adjacency encoding over the
permutations that respect the stable colouring.

Correctness and limits:

* refinement is isomorphism invariant -- KNOWN_RESULT, so restricting the search
  to colour-respecting permutations loses no isomorphism (Weisfeiler & Leman
  1968; see also Grohe & Schweitzer, *The graph isomorphism problem*, CACM 2020).
* the canonical form returned is therefore exact whenever the permutation search
  is not truncated; ``canonical_form`` reports ``exact=False`` when it is.
* colour refinement alone does **not** decide isomorphism -- KNOWN_RESULT: it
  fails on regular graphs, and ``tests/test_symbolic.py`` includes the standard
  counterexample C6 versus 2*C3, which refinement cannot separate but the
  permutation stage can.
* graph isomorphism is in quasipolynomial time -- KNOWN_RESULT (Babai 2016); no
  polynomial algorithm is known and none is claimed here.
"""

from __future__ import annotations

from itertools import permutations, product
from typing import Any, Hashable, Iterable, Sequence

Graph = dict[Hashable, frozenset[Hashable]]

PERMUTATION_LIMIT = 50_000


def normalise_graph(edges: Iterable[tuple[Hashable, Hashable]], vertices: Iterable[Hashable] = ()) -> Graph:
    """Build an undirected adjacency map, tolerating isolated vertices."""
    graph: Graph = {vertex: frozenset() for vertex in vertices}
    for left, right in edges:
        graph.setdefault(left, frozenset())
        graph.setdefault(right, frozenset())
        graph[left] = graph[left] | {right}
        graph[right] = graph[right] | {left}
    return graph


def refine(graph: Graph, initial: dict[Hashable, Hashable] | None = None) -> dict[Hashable, int]:
    """Stable 1-WL colouring as integer colours, deterministic across runs."""
    colours: dict[Hashable, Hashable] = (
        dict(initial) if initial else {vertex: len(graph[vertex]) for vertex in graph}
    )
    for _ in range(len(graph) + 1):
        signatures = {
            vertex: (colours[vertex], tuple(sorted(repr(colours[n]) for n in graph[vertex])))
            for vertex in graph
        }
        ordered = sorted(set(signatures.values()), key=repr)
        index = {signature: position for position, signature in enumerate(ordered)}
        updated = {vertex: index[signatures[vertex]] for vertex in graph}
        if updated == colours:
            break
        colours = updated
    return {vertex: int(colour) for vertex, colour in colours.items()}


def _encode(graph: Graph, order: Sequence[Hashable]) -> str:
    position = {vertex: index for index, vertex in enumerate(order)}
    bits = []
    for i, left in enumerate(order):
        for j in range(i + 1, len(order)):
            bits.append("1" if order[j] in graph[left] else "0")
    return "".join(bits)


def canonical_form(graph: Graph) -> dict[str, Any]:
    """Return the canonical encoding, the witnessing order and exactness."""
    colours = refine(graph)
    cells: dict[int, list[Hashable]] = {}
    for vertex, colour in colours.items():
        cells.setdefault(colour, []).append(vertex)
    for colour in cells:
        cells[colour].sort(key=repr)
    colour_order = sorted(cells)
    counts = [len(cells[colour]) for colour in colour_order]
    total = 1
    for count in counts:
        total *= _factorial(count)
    exact = total <= PERMUTATION_LIMIT
    best: str | None = None
    best_order: tuple[Hashable, ...] = ()
    considered = 0
    for choice in product(*(permutations(cells[colour]) for colour in colour_order)):
        order: list[Hashable] = []
        for block in choice:
            order.extend(block)
        considered += 1
        encoded = _encode(graph, order)
        if best is None or encoded < best:
            best, best_order = encoded, tuple(order)
        if considered >= PERMUTATION_LIMIT:
            break
    return {
        "canonical_encoding": best or "",
        "canonical_order": best_order,
        "colour_partition": [counts[index] for index in range(len(counts))],
        "vertices": len(graph),
        "permutations_considered": considered,
        "exact": exact,
    }


def canonical_labels(graph: Graph) -> dict[Hashable, int]:
    """Map each vertex to its canonical position."""
    form = canonical_form(graph)
    return {vertex: index for index, vertex in enumerate(form["canonical_order"])}


def is_isomorphic(left: Graph, right: Graph) -> tuple[bool, dict[str, Any]]:
    """Decide isomorphism via canonical forms; reports whether it was exact."""
    if len(left) != len(right):
        return False, {"reason": "different vertex counts", "exact": True}
    left_form = canonical_form(left)
    right_form = canonical_form(right)
    same = left_form["canonical_encoding"] == right_form["canonical_encoding"]
    return same, {
        "exact": left_form["exact"] and right_form["exact"],
        "left_permutations": left_form["permutations_considered"],
        "right_permutations": right_form["permutations_considered"],
        "refinement_separated": left_form["colour_partition"] != right_form["colour_partition"],
    }


def _factorial(value: int) -> int:
    result = 1
    for item in range(2, value + 1):
        result *= item
    return result

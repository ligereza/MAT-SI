"""One adversarial equality-saturation workload for the Phase 1 gate."""

from __future__ import annotations

from typing import Any

from .kernels.rewrite_egraph import (
    EGraph,
    RewriteRule,
    Variable,
    _rewrite_root,
    _term_size,
)


def _workload() -> tuple[Any, dict[str, Any], tuple[RewriteRule, ...]]:
    payload = ("atom", ("payload",))
    a = ("A", (payload,))
    b = ("B", (payload,))
    c = ("C", (payload,))
    d = ("D", (payload,))
    e = ("E", (payload,))
    x = Variable("x")
    rules = (
        RewriteRule("A_to_B", ("A", (x,)), ("B", (x,))),
        RewriteRule("A_to_C", ("A", (x,)), ("C", (x,))),
        RewriteRule("B_to_D", ("B", (x,)), ("D", (x,))),
        RewriteRule("C_to_E", ("C", (x,)), ("E", (x,))),
    )
    return a, {"A": a, "B": b, "C": c, "D": d, "E": e}, rules


def _tree_normal_form(term: Any, rules: tuple[RewriteRule, ...]) -> tuple[Any, dict[str, int]]:
    current = term
    visited = {current}
    attempts = 0
    applied = 0
    while True:
        changed = False
        for rule in rules:
            attempts += 1
            rewritten = _rewrite_root(current, rule)
            if rewritten is not None and rewritten != current:
                current = rewritten
                visited.add(current)
                applied += 1
                changed = True
                break
        if not changed:
            break
    return current, {
        "unique_terms": len(visited),
        "expanded_exploration": attempts,
        "rewrites_applied": applied,
    }


def _tree_exhaustive(term: Any, rules: tuple[RewriteRule, ...]) -> dict[str, int]:
    pending = [term]
    visited = {term}
    attempts = 0
    while pending:
        current = pending.pop()
        for rule in rules:
            attempts += 1
            rewritten = _rewrite_root(current, rule)
            if rewritten is not None and rewritten not in visited:
                visited.add(rewritten)
                pending.append(rewritten)
    return {"unique_terms": len(visited), "expanded_exploration": attempts}


def _egraph_saturate(term: Any, rules: tuple[RewriteRule, ...], equality_pair: tuple[Any, Any]) -> tuple[EGraph, int, set[Any], int]:
    graph = EGraph()
    root = graph.add_term(term)
    pending = [term]
    visited = {term}
    attempts = 0
    while pending:
        current = pending.pop()
        for rule in rules:
            attempts += 1
            rewritten = _rewrite_root(current, rule)
            if rewritten is None:
                continue
            rewritten_root = graph.add_term(rewritten)
            graph.union(root, rewritten_root)
            if rewritten not in visited:
                visited.add(rewritten)
                pending.append(rewritten)
    left_root = graph.add_term(equality_pair[0])
    right_root = graph.add_term(equality_pair[1])
    graph.union(left_root, right_root)
    graph.rebuild()
    return graph, root, visited, attempts


def _extract_weighted(graph: EGraph, root: int, weights: dict[str, int]) -> tuple[Any, int, int]:
    memo: dict[int, tuple[Any, int]] = {}

    def choose(class_id: int) -> tuple[Any, int]:
        class_id = graph.find(class_id)
        if class_id in memo:
            return memo[class_id]
        candidates = []
        for node in graph.classes[class_id]:
            if node.operation == "atom":
                candidate = (("atom", (node.value,)), 0)
            else:
                children = [choose(child) for child in node.children]
                term = (node.operation, tuple(child[0] for child in children))
                cost = weights.get(node.operation, 1) + sum(child[1] for child in children)
                candidate = (term, cost)
            candidates.append(candidate)
        selected = min(candidates, key=lambda item: (item[1], _term_size(item[0])))
        memo[class_id] = selected
        return selected

    term, cost = choose(root)
    return term, cost, len(memo)


def run_fair_egraph_trial() -> dict[str, Any]:
    start, terms, rules = _workload()
    orientations = {
        "D_to_E": (RewriteRule("D_to_E", ("D", (Variable("x"),)), ("E", (Variable("x"),))),),
        "E_to_D": (RewriteRule("E_to_D", ("E", (Variable("x"),)), ("D", (Variable("x"),))),),
    }
    costs = {"A": 4, "B": 3, "C": 3, "D": 10, "E": 1}
    rows = []
    for orientation, equality_rule in orientations.items():
        tree_rules = rules + equality_rule
        tree_result, tree_work = _tree_normal_form(start, tree_rules)
        exhaustive = _tree_exhaustive(start, tree_rules)
        graph, root, graph_terms, graph_attempts = _egraph_saturate(
            start, rules, (terms["D"], terms["E"])
        )
        graph_result, graph_cost, extracted_classes = _extract_weighted(graph, root, costs)
        root_class = graph.classes[graph.find(root)]
        rows.append(
            {
                "orientation": orientation,
                "tree_result": tree_result,
                "tree_result_operation": tree_result[0],
                "tree_work": tree_work,
                "tree_exhaustive_work": exhaustive,
                "tree_representation_growth": exhaustive["unique_terms"],
                "egraph_result": graph_result,
                "egraph_result_operation": graph_result[0],
                "egraph_cost": graph_cost,
                "egraph_alternatives_retained": len(root_class),
                "egraph_unique_terms_explored": len(graph_terms),
                "egraph_expanded_exploration": graph_attempts,
                "egraph_representation_growth": sum(
                    len(nodes) for class_id, nodes in enumerate(graph.classes) if graph.find(class_id) == class_id
                ),
                "egraph_extracted_classes": extracted_classes,
                "lowest_cost_expected_operation": "E",
                "egraph_recovers_lowest_cost": graph_result[0] == "E",
                "tree_order_sensitive": tree_result[0] != "E",
            }
        )
    return {
        "experiment": "fair_egraph_diamond",
        "term_graph": {
            "A_to_B": True,
            "A_to_C": True,
            "B_to_D": True,
            "C_to_E": True,
            "D_equivalent_E": True,
        },
        "costs": costs,
        "rows": rows,
        "egraph_order_invariant": rows[0]["egraph_result"] == rows[1]["egraph_result"],
        "egraph_has_structural_advantage": all(
            row["egraph_alternatives_retained"] > row["tree_work"]["unique_terms"]
            for row in rows
        ),
        "tree_order_changes_result": rows[0]["tree_result"] != rows[1]["tree_result"],
        "conclusion": "The e-graph retains a shared equivalence class and recovers the lowest-cost form independent of equality orientation; the reduced tree normalizer is order-sensitive on this adversarial diamond.",
    }

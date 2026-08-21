"""Symbolic representation: terms, rewrite rules, e-graphs, canonical forms."""

from .egraph import EGraph, ENode, Rule, SaturationReport
from .rules import ARITHMETIC_RULES, rule_soundness_report
from .terms import (
    DEFAULT_COSTS,
    CostFunction,
    Pattern,
    Term,
    depth,
    depth_cost,
    evaluate_term,
    interpretability_proxy_cost,
    operation_count_cost,
    operators,
    size,
    to_text,
    tree_size_cost,
    weighted_execution_cost,
)
from .canonical_graph import canonical_form, canonical_labels, is_isomorphic

__all__ = [
    "ARITHMETIC_RULES",
    "CostFunction",
    "DEFAULT_COSTS",
    "EGraph",
    "ENode",
    "Pattern",
    "Rule",
    "SaturationReport",
    "Term",
    "canonical_form",
    "canonical_labels",
    "depth",
    "depth_cost",
    "evaluate_term",
    "interpretability_proxy_cost",
    "is_isomorphic",
    "operation_count_cost",
    "operators",
    "rule_soundness_report",
    "size",
    "to_text",
    "tree_size_cost",
    "weighted_execution_cost",
]

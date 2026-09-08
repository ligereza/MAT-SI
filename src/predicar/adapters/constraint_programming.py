from ..contracts import ResearchArea

AREA = ResearchArea(
    area_id="constraint_programming",
    title="Constraint programming and weighted discrete inference",
    mapping="Exact cardinality and structural validity are enforced as first-class constraints.",
    imported_concepts=("Boolean constraints", "CP-SAT", "weighted model counting", "exact support"),
    planned_adapters=("constraint_weighted", "feasibility_oracle", "weighted_sampling"),
    source_refs=("OR-TOOLS-CP-SAT", "WMC-2022"),
    data_boundary="Use solver-generated small supports first; no optimizer is invoked during setup.",
)

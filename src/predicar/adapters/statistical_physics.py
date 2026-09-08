from ..contracts import ResearchArea

AREA = ResearchArea(
    area_id="statistical_physics",
    title="Fixed-magnetization Ising and Gibbs systems",
    mapping="The exact-cardinality binary state is a fixed-magnetization spin configuration.",
    imported_concepts=("energy", "partition function", "MCMC", "mean field", "phase behavior"),
    planned_adapters=("conditional_cardinality", "pairwise_gibbs", "complex_amplitude"),
    source_refs=("ISING-FIXED-MAGNETIZATION-2021",),
    data_boundary="Synthetic controlled generators are sufficient for the first protocol; no external data is required.",
)

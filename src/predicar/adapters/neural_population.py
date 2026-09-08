from ..contracts import ResearchArea

AREA = ResearchArea(
    area_id="neural_population",
    title="Neural population coding and maximum entropy",
    mapping="A binary population pattern is treated as a finite state with optional fixed population activity.",
    imported_concepts=("maximum entropy", "pairwise interactions", "population count", "stimulus-conditioned likelihood"),
    planned_adapters=("pairwise_gibbs", "k_pairwise", "pattern_likelihood"),
    source_refs=("NEURAL-ME-2017", "NEURO-ALLEN-SDK"),
    data_boundary="Use public event matrices or synthetic binary patterns; no biological data is bundled.",
)

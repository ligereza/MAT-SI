from ..contracts import ResearchArea

AREA = ResearchArea(
    area_id="point_processes",
    title="Temporal point processes and memory kernels",
    mapping="Past events modify a future intensity or latent state through an explicit temporal kernel.",
    imported_concepts=("Hawkes process", "self-excitation", "decay kernel", "latent intensity"),
    planned_adapters=("memory_kernel", "self_exciting_transition", "kernel_ablation"),
    source_refs=("HAWKES-REVIEW-2025", "HAWKES-STOCHASTIC-2016"),
    data_boundary="Start with synthetic event streams and fixed future-only folds; external event data is optional.",
)

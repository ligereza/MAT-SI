from ..contracts import ResearchArea

AREA = ResearchArea(
    area_id="rfs_tracking",
    title="Random finite sets and multi-object tracking",
    mapping="A finite set-valued state is forecast and updated from noisy, incomplete detections.",
    imported_concepts=("Bayesian filtering", "cardinality", "data association", "GLMB/LMB/PMBM"),
    planned_adapters=("finite_set_bayes", "multi_hypothesis_update", "set_metrics"),
    source_refs=("RFS-GLMB-2018", "STONE-SOUP", "MOTCHALLENGE"),
    data_boundary="Use public detections or synthetic observations first; do not download video by default.",
)

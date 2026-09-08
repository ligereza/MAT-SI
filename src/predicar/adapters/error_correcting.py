from ..contracts import ResearchArea

AREA = ResearchArea(
    area_id="error_correcting",
    title="Error-correcting codes and probabilistic decoding",
    mapping="A latent valid state is recovered from noisy observations through likelihood and message passing.",
    imported_concepts=("channel model", "belief propagation", "syndrome", "decoding confidence"),
    planned_adapters=("noisy_channel", "belief_propagation", "recovery_calibration"),
    source_refs=("AFF3CT", "LDPC-DOCS"),
    data_boundary="Use generated channels and small public code examples; no telecommunications capture is bundled.",
)

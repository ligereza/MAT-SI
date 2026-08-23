# PiPi-46: quantum query/order stress test

PiPi-46 is branched from PiPi-45 commit `81be791` on
`research/quantum-order-stress`. It does not modify any earlier PiPi result,
`main`, CODEINE, or the kernel.

## Model boundary

The experiments use small idealized query models, not quantum hardware and not
a full gate simulator. Oracle construction is reported as a truth-table-entry
proxy and is never silently counted as a query. Full gate/circuit cost is
`NOT_MEASURED` and is excluded from conclusions. Query count, classical
postprocessing, repetitions/amplification, success probability, memory/state
dimension, and candidate-space evolution remain separate fields.

Controls:

* Grover-style unstructured search: amplitude amplification reduces ideal
  query count while producing no classical global candidate constraint.
* Simon: classical observations wait for a collision; ideal quantum samples
  produce homogeneous GF2 constraints `y·s=0`, and the secret candidate set is
  tracked after every sample.
* Toy period finding: an ideal Fourier sample is followed by an explicit
  rational-reconstruction proxy; the small control is intentionally allowed to
  expose postprocessing/model mismatch.
* Bernstein--Vazirani: calibration for a single global linear observation, not
  held-out evidence.

## Held-out prediction

The prediction rule is frozen before actual category labels are attached. It
uses the profile fields inherited from the earlier experiments: raw candidate
space, candidate quotient after one observation, observation width/message
description, discovery/transform/postprocessing work, and independent
constraints per query. Grover and BV are training controls; Simon and toy
period finding are held out.

The held-out accuracy is deliberately reported, not optimized after inspection:
Simon is classified correctly as structural, while the toy period control is a
mismatch. This is evidence that a simple interface-profile rule is not yet a
reliable predictor across even these idealized query models.

## Reproduction and field classes

```text
$env:PYTHONPATH="src"
python -m unittest discover -s tests -v
python -m matsi.quantum_order_stress --json-out results/quantum-order-stress.json
```

Candidate traces, GF2 ranks, query counts, candidate-space partitions, state
dimensions, oracle table entries, and prediction rule digest are deterministic.
`wall_ms` is machine-dependent. Actual category labels and prediction accuracy
are post-hoc evaluation fields. A tensor/contraction-width bridge is explicitly
`NOT_RUN`; no conclusion about query complexity versus tensor width is licensed.

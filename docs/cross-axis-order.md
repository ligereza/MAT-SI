# PiPi-44: minimal order interface

PiPi-44 is a result object on branch `research/cross-axis-order`, parent
`1d5a1d9`. It does not modify the MAT-SI kernel, PiPi-42, PiPi-43, or their
JSON files.

## Same-domain process

Every case is a layered binary factor process:

```text
past history variables -> integer boundary message -> future factor queries
```

For a raw past assignment, the implementation enumerates any latent past
variables and produces an exact message table over all binary boundary
assignments. A future query fixes a future assignment and contracts the message
with future factors. Thus `Q`, `W`, and `M` are measured in one semantics.

* `Q` is the number of distinct full future-response signatures.
* `W` is the number of boundary variables.
* `D` is the boundary domain size, exactly `2**W`.
* `M` is deliberately a vector: distinct messages, exact table bytes, value
  range, nonzero cells, and exact rational matrix rank.

No equality between these quantities and no universal scalar dimension is
declared.

## Minimality attack

The fixed discovery split uses the first half of future queries and records
counterexamples in the held-out half. Only after that freeze does the audit
enumerate every natural message pair and compare their complete future
signatures. Safe fusions are retained until the future-sufficient partition is
reached. The result reports natural message classes, minimal sufficient
messages, pair counts, safe/unsafe fusions, and both message-class and byte
slack. This is an exhaustive finite-case sufficiency result, not a claim that
the separator is globally minimal.

## What the controlled cases show

The four controlled quadrant cases include small/small, small/large,
large/small, and large/large `(Q,W)` combinations in this weighted finite-state
domain. The same-`W`, same-`Q` controls then vary message magnitude or raw
history/solve work. In particular, `W=1, Q=2` appears with Boolean messages,
large weighted messages, and many ignored raw histories. This is a direct
counterexample to using separator width alone as a complete interface profile.

The audit also verifies the finite-domain relation `Q <= distinct_messages`:
future behaviour is a deterministic function of the exact message. This is an
observed/reasoned bound for this process semantics, not a universal theorem
about arbitrary representations.

## Reproduction and field classes

```text
$env:PYTHONPATH="src"
python -m unittest discover -s tests -v
python -m matsi.cross_axis_order --json-out results/cross-axis-order.json
```

Raw factor tables, digests, quotient partitions, message tables, exact ranks,
fusion decisions, and resource counts are deterministic. `wall_ms` fields are
machine-dependent and descriptive. `future_signatures`, `future_quotient_size`,
and `minimality_attack` are post-hoc oracle/reference fields and never change
the frozen discovery decision. No stable `OrderProfile` is declared yet.

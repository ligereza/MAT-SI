# Agent 1 continuation: coverage is not prediction

The corrected Phase 4A audit changed the reported predictive gain from `1/6` to
`0` when the relation and its no-relation baseline were scored on the same
matched windows. The next mathematical question is narrower:

> Can a trajectory relation that selects observations be distinguished from one
> that predicts an observed continuation?

## Minimal representation

Each evaluation row is `(outcome, prediction-or-abstention)`. The represented
prediction is either `true`, `false`, or absent. We report two independent
coordinates:

`coverage = covered / total`

`conditional_accuracy = correct / covered`

For the same covered set, the baseline is the best constant label (the modal
outcome). Its difference from the predictor is the same-opportunity gain. The
comparison is a Pareto comparison over coverage and conditional accuracy; no
weighted score chooses between the axes.

## Falsification result

If all covered rows receive one label, the correct count is the count of that
label. The modal constant is at least as correct, so selection-only relations
cannot have positive same-opportunity gain. This is a direct counting proof,
not a statistical assumption.

The existing Phase 4A `G` becomes exactly such a partial predictor: it covers
three of four held-out windows and emits `true` on all three. Its conditional
accuracy is `2/3`, coverage is `3/4`, and same-opportunity gain is `0`.
Therefore that experiment demonstrated structural selection and a mixed
continuation, not predictive transfer.

A controlled counterexample changes only the represented predictions on the
same three covered rows to `true, false, true`. Accuracy becomes `1`, gain
becomes `1/3`, and the exact fixed-prediction outcome permutation null has
`p = 1/6` for this four-row example. This is evidence of a different object:
the relation now predicts varying outcomes. It is not evidence of causation.

The Pareto experiment retains both a full-coverage lower-accuracy constant and
a lower-coverage higher-accuracy varying predictor. A one-row perfect predictor
is strictly dominated by the latter. No single winner follows without an
external decision policy.

## Limits and next question

The exact null enumerates `C(n,t)` binary outcome arrangements and is therefore
an audit for small samples, not a scalable estimator. The current corpus is
too small to support a cross-domain claim. The minimum missing relation for a
future transfer test is a represented prediction that varies within the
covered population, together with a precommitted treatment of abstention.

No causal interpretation is inferred: the null rearranges outcomes while
holding predictions and abstentions fixed.

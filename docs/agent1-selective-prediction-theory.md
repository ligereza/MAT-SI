# Selectors, predictors, and abstention

This note continues the result from Phase 4A without adding a corpus. The
held-out relation `G` covered three windows and emitted the same represented
label on all three. Its coverage was `3/4`, conditional accuracy `2/3`, and
same-opportunity gain `0`. The question is therefore about types and policies,
not about searching for another positive example.

## 1. Three formal objects

Let `X` be an observation space and `Y` a label space.

* A selector is `s : X -> {0,1}`. It chooses a subset and emits no element of
  `Y`.
* A predictor is `f : X -> Y`. It emits one label everywhere.
* A selective predictor is `(s,f)`, or equivalently the partial map
  `g : X -> Y union {bottom}` with `g(x)=f(x)` when `s(x)=1` and `bottom`
  otherwise.

Coverage is `C = P[s(X)=1]`. Selective risk is

`R_A = P[f(X) != Y | s(X)=1]`.

The rejected subset has its own risk

`R_R = P[f(X) != Y | s(X)=0]`,

provided the underlying total predictor `f` is defined there. This last
quantity is essential: a low accepted risk can otherwise hide all errors in
the rejected set.

## 2. When can a relation predict non-constantly?

Suppose a discovered relation produces a represented state `r(x)` and a
decoder `d` produces labels. On the covered set `A={x:s(x)=1}`, predictions
are variable exactly when

`|d(r(A))| >= 2`.

This is both necessary and sufficient. If the relation only returns a Boolean
match and the decoder maps every match to `true`, its prediction image has size
one regardless of how many cases it selects. A selector alone cannot become a
predictor without a decoder; two decoder-distinguishable represented states
are the minimum structural requirement. This condition is about variability,
not usefulness: it does not establish that the labels correspond to future
outcomes.

## 3. Risk, abstention, and non-hiding constraints

For a finite population, with coverage `C`, accepted risk `R_A`, and rejected
risk `R_R`, the total error of the underlying predictor is

`R_full = C*R_A + (1-C)*R_R`.

Therefore, for `0<C<1`, abstention lowers conditional risk exactly when
`R_A < R_R`. This is a theorem about partitioning errors; it does not say the
system improved globally.

If abstention has an externally specified action cost `a`, the system action
risk is

`L_a = C*R_A + (1-C)*a`.

Against the same total predictor, selective action risk improves exactly when
`a < R_R`. The cost is not invented by MAT-SI; it must come from the external
action being modeled. Without that cost, the correct object is the whole
risk–coverage set, not a selected scalar.

Policies are compared by dominance: policy `p` dominates `q` when it has at
least as much coverage and no greater accepted risk, with one strict
inequality. A minimum coverage or maximum rejected-risk requirement is a
constraint, not a weight. The exact solver enumerates every accept/reject mask
for small finite instances and returns the non-dominated frontier.

## 4. Counterexamples

On outcomes `[true,false,true,false]`, a total constant predictor `true` has
coverage `1` and risk `1/2`. Accepting only the first row has conditional risk
`0`, but coverage `1/4`; if abstention counts as one unit of action loss, its
global risk is `3/4`, worse than the full predictor's `1/2`.

The Phase 4A-shaped policy accepts the first three rows. Its accepted risk is
`1/3`, below the full risk `1/2`, but rejected risk is `1`. The conditional
improvement is exactly compatible with concentrating the error in the hidden
row. Reporting rejected risk and imposing a coverage/rejected-risk constraint
prevents that fact from disappearing.

## 5. Calibration and coverage

For a confidence value `q(x)` intended to estimate correctness, exact group
calibration means `P[f(X)=Y | q(X)=q] = q`. Under this condition, a threshold
policy `s_t=1[q>=t]` has risk equal to the average of `1-q` among accepted
cases. Thus a calibrated threshold curve can relate confidence to risk, but
calibration does not choose a target coverage and does not prove that a
discovered relation caused the outcome.

Selective classification is the same partial-map object above. The reject
option is the same object with an externally specified abstention loss. A
conformal prediction set can provide a coverage guarantee for a set-valued
prediction or abstention policy; it does not replace the representation/decoder
condition and does not turn Phase 4A's selector into a predictor.

## 6. Status of the mathematical claims

`PROVED`: the type distinction, image condition for variable predictions,
selection-only non-positive gain, risk decomposition, abstention-cost
boundary, and Pareto dominance rule.

`KNOWN_RESULT`: Phase 4A `G` is selection-only; calibration and
risk–coverage are distinct quantities.

`DISPROVED`: higher conditional precision by itself implies a better global
system.

`UNKNOWN`: whether a future MAT-SI-discovered decoder can produce calibrated
variable predictions without label leakage, and whether these finite
conditions survive a larger held-out domain. No new corpus was created here.

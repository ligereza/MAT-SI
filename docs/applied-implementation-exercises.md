# Applied implementation exercises

These exercises turn the recent MAT-SI orientations into implementation work for
three external systems:

1. FARMAKSIA/VIZZ: eye tracking, camera pose, and multi-monitor projection.
2. SVG: hierarchical reconstruction, animation grouping, and Blender export.
3. MAK: Linux/Windows cursor handoff and virtual-desktop coordinates.

They are specifications and falsifiable implementation exercises, not benchmark
results. A solution must keep the original evidence, coordinate space, authority,
configuration, and uncertainty explicit. A convenient output is not a certified
claim when coverage or provenance is missing.

## Shared MAT-SI contract

Every exercise should record:

```text
contract = (Q, P, A, K)
Q = human question
P = formal predicate actually evaluated
A = permitted authority/provenance
K = completeness and coverage conditions
```

The implementation must distinguish `YES`, `NO`, and `UNKNOWN`. `UNKNOWN` means
that the current representation or authority cannot certify the predicate; it is
not permission to guess. Derived values must retain their source representation,
configuration hash, timestamps, and invalidation conditions.

---

## Exercise A — FARMAKSIA/VIZZ eye-to-screen geometry

### Mathematical foundation

Use the chain

```text
camera image → landmarks/head pose → eye-frame gaze direction
→ world-frame ray → monitor-plane intersection → local screen point
```

For a ray with origin `o` and unit direction `d`, and a monitor plane with origin
`O`, unit normal `n`, horizontal/vertical axes `u,v`, width `W` and height `H`:

```text
r(λ) = o + λd
λ = ((O - o) · n)/(d · n)
X = o + λd
x_local = ((X - O) · u)/W
y_local = ((X - O) · v)/H
```

The monitor is a geometric candidate only when `λ > 0` and both local coordinates
are in `[0,1]`. If `|d·n|` is below a threshold, the intersection is unstable and
must be `UNKNOWN`.

For a camera with intrinsics `K` and extrinsics `X_cam = R X_world + t`, the camera
center is `C = -Rᵀt` and a pixel ray is:

```text
X(λ) = C + λ Rᵀ K⁻¹ p
```

This pixel ray is not automatically the eye gaze ray. The eye origin and visual-axis
offset must remain explicit.

For a target sequence `r(t)` and a preliminary gaze estimate `q(t)`, estimate lag
with normalized cross-correlation:

```text
τ̂ = argmaxτ C(τ)
C(τ) = <q(t)-q̄, r(t-τ)-r̄> / (||q-q̄|| ||rτ-r̄||)
```

The temporal sample window should minimize `Bias² + Variance + discard_cost`. Frames
after a detected fixation exit must not inherit the previous target label.

For a model with parameters `θ`, use empirical Fisher information:

```text
I(θ) = Σ Jᵀ Σ⁻¹ J,       J = ∂fθ/∂θ
```

Compare calibration trajectories using `log det(I)`, the smallest eigenvalue, and
the condition number. Static points identify planar geometry; smooth diagonals or
Lissajous motion identify dynamics and lag. No one trajectory should be treated as
universally optimal.

### Implementation tasks

1. Implement a typed coordinate pipeline with explicit `camera`, `eye`, `world`,
   `monitor-local`, and `desktop` spaces.
2. Implement ray-plane intersection with rejection for negative `λ`, near-parallel
   rays, out-of-rectangle hits, stale monitor poses, and missing coverage.
3. Implement fixation-window selection using timestamps, target intervals, gaze
   velocity/dispersion, blink flags, and saccade flags. Mouse position may schedule a
   task but cannot be the gaze label.
4. Implement lag estimation on valid pursuit segments and return confidence plus a
   bootstrap interval. A broad or multimodal correlation peak is `UNKNOWN`.
5. Implement a baseline affine/ridge model, then compare homography and a small
   nonlinear model only with session-held-out validation.
6. Implement multi-monitor selection by intersecting the ray with every physical
   monitor plane. Return zero, one, or multiple candidates; do not silently select a
   monitor under ambiguity.

### Pseudocode

```text
valid = stable_fixation(frame)
if not valid or frame.blink or frame.stale_pose:
    return UNKNOWN

candidates = []
for monitor in active_monitors:
    hit = intersect(ray(frame), monitor.plane)
    if hit.λ > 0 and hit.condition < κ_max and inside(hit, monitor.rect):
        candidates.append(hit)

if len(candidates) != 1:
    return UNKNOWN
return CERTIFIED_POINT(candidates[0], contract, provenance)
```

### Acceptance and falsification

The baseline must be a ridge/affine model. A learned model is accepted only when
the improvement is measured on complete held-out sessions, not random frames, and
does not worsen P95 error, rejection rate, latency, or calibration cost beyond
pre-registered limits. Report median/P95 error in pixels and visual degrees,
monitor accuracy, `UNKNOWN` rate, pose robustness, blink robustness, and drift.

The hypothesis is falsified if the explicit 3-D pipeline does not improve or
stabilize monitor assignment under changed monitor pose, changed head pose, or
held-out sessions relative to the fixed 2-D baseline.

---

## Exercise B — SVG hierarchy, grouping, and Blender reconstruction

### Mathematical foundation

Represent an SVG as a scene tree whose nodes carry local geometry, style, parent,
paint order, provenance, and affine transform. World geometry is:

```text
G_world = T_parent · ... · T_local · G_local
```

Preserve the original path commands. A cubic Bézier is:

```text
B(u)=(1-u)³P0 + 3(1-u)²uP1 + 3(1-u)u²P2 + u³P3
```

Its bounding box requires endpoints plus roots of `dBx/du=0` and `dBy/du=0` in
`(0,1)`, after applying the complete affine transform. Arcs should be converted to
center/angle form, with extrema evaluated on the restricted arc; a non-similarity
affine may require a parametric or Bézier representation.

For a filled region, define centroid from signed area, not an unqualified average:

```text
A  = 1/2 ∮(x dy - y dx)
Cx = 1/(6A) ∮(x² dy - xy dx)
Cy = 1/(6A) ∮(xy dx - y² dx)
```

Holes retain their orientation/sign. Fill centroid, stroke centroid, bounding-box
center, and user pivot are distinct quantities.

Use an R-tree/STRtree or BVH for broad-phase adjacency. Narrow phase computes exact
or tolerance-controlled intersection, minimum distance, shared boundary, IoU, and
overlap. A merge score can be:

```text
score(i,j) = wC C + wO O + wS S + wH H + wZ Z + wA A + wT T
             - wD distance_penalty - wK topology_penalty
```

The weights and thresholds must be versioned. A visually adjacent background and
object are not automatically one animation unit.

For SVG-to-Blender conversion, choose one affine map and apply it to every vertex,
control point, and pivot. If Blender uses centered XY coordinates with upward Y:

```text
x_b = s (x_s - cx)
y_b = s (cy - y_s)
z_b = layer_z
```

The `viewBox`, `preserveAspectRatio`, viewport, unit scale, and conversion matrix
must be recorded.

### Implementation tasks

1. Parse the SVG into a typed intermediate graph without discarding commands,
   controls, styles, `defs`, `use`, clips, masks, or paint order.
2. Implement affine composition and exact candidate extrema for cubic/quadratic
   Béziers and arcs.
3. Implement spatial indexing and a narrow-phase geometry adapter.
4. Generate candidate animation groups with must-link/cannot-link constraints.
5. Fuse only compatible fills; preserve holes and map each merged region back to
   source IDs. Record every tolerance and operation.
6. Import editable Bézier curves into Blender. Use meshes only for declared
   operations such as fill tessellation, boolean, or extrusion.
7. Compare original and reconstructed frame 0 with raster, mask, contour, and
   topology metrics.
8. Add a manifest-driven human override layer for merge, split, reparent, pivot,
   and style corrections.

### Pseudocode

```text
scene = parse_svg_preserving_commands(svg)
world = compose_transforms(scene)
index = STRtree([bbox(n) for n in world.nodes])

for pair in candidate_pairs(index):
    if cannot_link(pair):
        continue
    G.add_edge(pair, score(pair_features(pair)))

groups = constrained_cluster(G, must_link, cannot_link)
groups = repair_holes_and_topology(groups)
groups = apply_manifest_overrides(groups, manifest)
export_blender_curves(groups, original_controls=True)
assert validate_frame_zero(svg, reconstruction, tolerances)
```

### Acceptance and falsification

Acceptance requires exact or declared-tolerance agreement for topology, plus
pre-registered bounds for symmetric Hausdorff/P95 contour error, IoU/Dice, centroid
error, raster difference, style/alpha error, and paint-order changes. Raster similarity
alone is insufficient: the control-point structure and source mapping must also be
auditable.

The grouping hypothesis is falsified if automatic merges repeatedly break holes,
paint order, animation semantics, or frame-0 equivalence, even when the aggregate
pixel error looks small.

---

## Exercise C — MAK Linux/Windows cursor handoff

### Mathematical foundation

Use one canonical physical virtual-desktop space. For a virtual rectangle
`[Xmin,Xmax] × [Ymin,Ymax]`, convert to the absolute integer space only at the
protocol boundary:

```text
u = round(clip((x-Xmin)/(Xmax-Xmin),0,1) · 65535)
v = round(clip((y-Ymin)/(Ymax-Ymin),0,1) · 65535)
```

For a 3926-pixel width, the pixel-center step is approximately
`3925/65535 = 0.05989 px`; rounded quantization error is at most about `0.02995 px`.
It cannot turn a normal interior point into 0 or 65535. Endpoint collisions indicate
an origin/scale error, clamp, truncation, overflow, or mixed logical/physical space.

Per-monitor DPI requires a piecewise transform:

```text
physical = monitor_origin + dpi_scale · logical_local
```

The logical primary width near `2560/1.5 = 1706.67` must not be treated as a physical
gap before the physical monitor rectangles are known.

For a right-edge transfer with outward normal `n`, use:

```text
distance_to_edge ≤ M_enter
n · v ≥ v_min
```

If sampling and acknowledgement take total time `T`, an outward displacement bound is:

```text
d_max = v_n T + 1/2 a_max T²
M_min ≥ d_max + q + ε
```

The three margins `M_enter=200`, `M_reactivate=200`, `M_return=64` are not safe if
64 means “reappear 64 px from the same activating edge”: 64 lies inside the 200-pixel
reactivation band. A safe design needs a latch or:

```text
M_return_safe ≥ M_reactivate + d_max + q + ε
```

For a diagonal movement, calculate the crossing point with the shared border and
accept only when it lies inside the destination monitor rectangle. A tangent or
corner movement without a valid destination is not a transfer.

### Implementation tasks

1. Define a coordinate-space type and reject messages with an unexpected space,
   monitor configuration, DPI version, or stale sequence.
2. Implement reversible logical↔physical↔absolute conversions with endpoint tests,
   negative monitor origins, mixed DPI, and real gaps.
3. Implement velocity/acceleration-based edge gates and explicit corner policy.
4. Implement transfer IDs, epochs, monotonic sequence numbers, ACK idempotence,
   timeout, retry, and stale-message rejection.
5. Maintain `remoteX` only in canonical destination space and verify its agreement
   with the last dequantized absolute coordinate within tolerance.
6. Implement the four-state machine below and assert ownership uniqueness.

### Formal state machine

State fields:

```text
phase ∈ {LOCAL, TRANSFERRING, REMOTE, RETURNING}
owner ∈ {LINUX, WINDOWS}
epoch, transfer_id, sequence, deadline, configuration_id, armed
```

Valid transitions:

```text
LOCAL → TRANSFERRING
  edge gate + outward velocity + destination valid + armed + cooldown

TRANSFERRING → REMOTE
  matching ACK before deadline; commit exactly once

TRANSFERRING → LOCAL
  timeout, NACK, invalid destination, or configuration mismatch

REMOTE → RETURNING
  correct return edge + outward velocity + valid aperture + cooldown

RETURNING → LOCAL
  matching ACK; place cursor in safe interior and disarm

RETURNING → REMOTE
  timeout/NACK; keep Windows as owner and invalidate the attempt
```

No direct `LOCAL↔REMOTE` transition is allowed. Duplicated ACKs are no-ops when
`(source,target,transfer_id,epoch)` has already committed. Older epochs and sequence
numbers are ignored.

### Pseudocode and safety property

```text
if msg.epoch < state.epoch or msg.sequence <= state.last_sequence:
    ignore_stale()
elif state.phase == TRANSFERRING and valid_ack(msg):
    commit_once(msg)
elif state.phase == REMOTE and valid_return(msg):
    begin_return(msg)
else:
    reject()
```

After each commit set `armed=false`. Set it true only after the cursor enters a
declared safe interior region, has moved at least the reactivation margin plus the
dynamic bound, and the cooldown expires. Therefore an event sequence
`enter → reappear → enter` without safe rearm cannot create two commits. Legitimate
repeated transfers after deliberate movement remain possible; the claim is only that
there is no spontaneous infinite rebounce.

### Acceptance and falsification

Test properties, not only example traces:

- round-trip coordinate conversion stays within the quantization bound;
- no two owners are active after any message ordering;
- duplicate, delayed, and out-of-order packets are idempotent or rejected;
- every accepted return has the correct edge, direction, configuration, and epoch;
- no transfer occurs through a real monitor gap or invalid corner;
- no spontaneous cycle occurs without movement into the safe region and cooldown.

Use property-based tests over DPI, monitor rectangles, velocities, latencies, packet
duplication, and negative coordinates. A timeout or missing monitor must produce a
recoverable state or `UNKNOWN`, never an inferred teleport.

---

## Required exercise outputs

Each implementation should produce:

1. a versioned schema for inputs and coordinate/representation spaces;
2. deterministic unit and property tests for the mathematical invariants;
3. an audit record containing source/configuration hashes, tolerances, timestamps,
   rejected cases, and `UNKNOWN` reasons;
4. a minimal reproduction script for every accepted result;
5. a list of assumptions that remain hypotheses rather than certified facts.

These exercises are intentionally complementary. VIZZ tests physical projection,
SVG tests hierarchical geometry and reversible representation, and MAK tests
distributed state/coordinate correctness. None of them turns an approximate model,
learned grouping, or unverified adapter into a certified claim without explicit
coverage and provenance.

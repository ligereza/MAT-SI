# WACHUMA — Geometry Nodes Audit and MAT-SI Handoff

**Date:** 2026-08-27
**Status:** blocking audit; implementation claims must be downgraded until the
listed gaps are repaired and re-tested.

This note records the audit supplied by the WACHUMA agent and the local static
checks performed from MAT-SI. The route, source paths, socket definitions and
web shader behavior were checked locally. The Blender topology counts below
are recorded from the agent's direct evaluation and should be rerun after any
repair; they are not being promoted to a theorem merely because they appear in
a report.

## 1. Canonical production path

The active web route is:

```text
apps/web/app/preview/svg-loft/page.tsx
    -> apps/web/app/components/GeometryNodesPachanoiPreview.tsx
    -> apps/web/public/models/pachanoi-sequence/frame-*.glb
```

The canonical geometry source is:

```text
integrations/blender/generate_pachanoi_geometry_nodes.py
```

The editable Blender artifact is:

```text
integrations/blender/projects/wachuma-pachanoi-geometry-nodes.blend
```

The active sequence manifest is:

```text
apps/web/public/models/pachanoi-sequence/sequence.manifest.json
```

`SvgLoftPreview.tsx`, `svg_to_cactus_mesh.py`,
`generate_pachanoi_growth_simulation.py` and the older frame manifests are not
used by the active route. They must be labelled as legacy or reconciled in the
documentation so that they cannot silently become alternate sources of truth.

## 2. Findings that change the claims

### 2.1 Modular geometry is spatial, not yet semantic

The Blender group contains rib-related grids and instances. `Rib Count` is
linked to the number of generated modules and the current reference is `n=7`.
This supports a claim of *spatial modular construction*, not yet a claim of
persistent module identity.

No `rib_id` or `areola_id` named attributes were found. The temporary indices
used by `Mesh Line`, `Input Index`, `birth_index`, `birth_row` and
`birth_rib` are generation indices, not durable identities across frames or
exports.

Required downgrade:

```text
“modules exist in the evaluated graph”
    is supported;
“the same biological rib/areola persists across frames”
    is not supported.
```

### 2.2 Topology is not established by the active GLB validator

The agent reports for the evaluated body at frame 180:

```text
V = 40495, E = 79800, F = 40208
boundary-edge usages != 2: 1680
Euler characteristic: χ = 903
```

The reported boundary edges come from open modular `Mesh Grid` boundaries.
This means the instances can coincide visually while remaining topologically
unwelded. `validate-glb.mjs` returning zero errors and zero warnings is only a
glTF structural validation; it does not establish manifoldness, C² continuity,
or absence of self-intersection.

Topology must be measured separately for the connected cactus body and for any
disjoint areola/spine components. A total-scene Euler characteristic cannot be
compared with `χ=2` unless the tested object is a single closed connected
surface.

For the body, the generative construction should share boundary vertices (or
use an exact, tested weld) around the cyclic angular domain. “Looks joined” is
not a substitute for shared topology.

### 2.3 The radial field is not currently auditable as a field

The implementation contains calculations named `base_radius`, `valley_radius`,
`profile_factor`, `phase` and `taper`, which is evidence of a related
construction. But `R(u)`, `A(u)` and `Phi(u)` do not survive as explicit audit
data. Therefore the equation

```text
r(u,theta) = R(u) + A(u) f_n(theta - Phi(u))
```

is an implementation interpretation, not yet a verifiable exported contract.
The generator should expose either deterministic diagnostic samples or a sidecar
record sufficient to reconstruct these fields for the tested frame.

### 2.4 Apical C0/C1/C2 is not proven on the active surface

The use of `meristem_mask`, `GREATER_THAN`, `clamp` and taper parameters does not
imply C². A full test must compare the rendered/exported surface at several
angles, including `X`, `X_u`, `X_theta`, `X_uu`, `X_u_theta` and `X_theta_theta`,
at the actual transition. A meridian or a helper curve is insufficient.

The requirement also remains ambiguous until the implementation declares one
of these cases:

1. a finite-radius meristem region with a smooth terminal boundary; or
2. a coordinate pole where the angular chart degenerates but the geometric
   surface has a compatible regular chart.

Neither case is a biological proof. It is a geometric contract that must be
tested on the actual exported body.

### 2.5 `Spine Scale` is not yet a single scale parameter

The generator multiplies spine length once in `controlled_spine_length` and
again in the per-instance fan scale. The web shader also applies a vertex
deformation for `uSpineScale`.

Thus the current system has at least three possible scale operations. The
invariant should be:

```text
base_after == base_before
direction_after == direction_before
length_after / length_before == requested_scale
```

within declared tolerance. Implement exactly one canonical scale in Geometry
Nodes. The web layer must not apply a second geometric scale to an artifact that
claims to be a presentation of the GLB.

### 2.6 The web preview currently changes geometry

`GeometryNodesPachanoiPreview.tsx` modifies vertex positions in
`onBeforeCompile` for both `Inner Rib Roundness` and `Spine Scale`. Therefore it
is not currently “GLB-only presentation” for those controls. A material shader
may change color and lighting; a vertex shader is a second geometry generator
unless explicitly labelled as a non-canonical preview approximation.

The architecture must choose and document one of two valid contracts:

```text
canonical mode:
  web does not change vertex positions;
  geometry controls select/reload regenerated GN artifacts;

preview-approximation mode:
  web vertex deformation is allowed;
  it is labelled as an approximation and cannot be used as evidence
  for the exported GN geometry.
```

For the current handoff, canonical mode is the recommended default. The pulp
color controls may remain shader-only because they are explicitly appearance
controls. If pulp coordinates/attributes are claimed as semantic GLB data, the
export must be checked; Blender named attributes alone are insufficient.

### 2.7 Manifests and source claims need reconciliation

The active sequence uses `sequence.manifest.json`, while older frame manifests
still identify an older algorithm and SVG-calibrated source. This is a
provenance hazard even when the active route does not load them. The active
manifest should record the exact generator version, `.blend` hash, frame,
parameters and whether the artifact contains semantic identity data. Legacy
manifests should be marked legacy or removed from active documentation after a
separate review.

## 3. Required correction order

The agent must not begin with visual tuning. The order is:

1. **Freeze the source map.** Trace route, generator, `.blend`, GLB and active
   manifest; label legacy generators and manifests.
2. **Repair body topology.** Generate one connected cyclic body surface or
   perform an exact tested weld. Validate boundary edges and manifoldness on the
   body component, not the aggregate scene.
3. **Expose the field contract.** Add deterministic diagnostics or a sidecar
   for `R`, `A`, `Phi`, `n`, frame and parameters.
4. **Test the actual apical surface.** Check C0/C1/C2, normals, curvature,
   Jacobian and self-intersection at multiple angles on the exported result.
5. **Add identity.** Preserve `rib_id` and areola/spine identity in GN and in a
   validated export sidecar or GLB representation. Do not call temporary indices
   persistent IDs.
6. **Collapse spine scaling to one operation.** Test base invariance and exact
   length ratio.
7. **Separate web geometry from web appearance.** Remove or explicitly demote
   vertex shaders that change canonical geometry; retain color-only shaders for
   appearance controls.
8. **Regenerate artifacts and manifests.** Only after these checks may visual
   comparison or further controls be judged.

## 4. Minimum acceptance tests after repair

```text
body_boundary_edges == 0
body_manifold == true
body_orientation_consistent == true
```

For the full body parameterization at the join:

```text
max_theta ||X_body - X_apex||       <= eps0
max_theta ||X_u_body - X_u_apex||   <= eps1
max_theta ||X_uu_body - X_uu_apex|| <= eps2
```

Also test angular and mixed derivatives, normals, curvature, positive
pre-pole Jacobian and no self-intersections under a declared tolerance.

For identity:

```text
same rib_id/areola_id -> same module and birth record across frames
same seed + same inputs -> same sidecar and geometry hash
```

For controls:

```text
Inner Rib Roundness -> profile only
Pulp Core Radius    -> appearance/declared pulp field only
Pulp Contrast       -> appearance only
Spine Scale         -> length only, base fixed
Branch Development=0 -> no branch
```

For web/source separation:

```text
material-only change -> GLB vertex positions unchanged
GN geometry change   -> regenerated GLB and manifest change
```

## 5. Current MAT-SI verdict

The audit is valuable because it falsifies several earlier claims:

- modular spatial construction is not yet persistent semantic identity;
- glTF validity is not manifold or geometric soundness;
- local C0/C1/C2 tests are not proof for the rendered surface;
- a smooth animation is not growth with entity identity;
- a named Blender attribute is not automatically an exported GLB attribute;
- a web vertex shader violates strict source/presentation separation;
- one slider applied at multiple layers is not a single mathematical control.

The most important surviving architectural claim is narrower:

```text
WACHUMA has a procedural Geometry Nodes source with a spatial rib-related
construction and a web route that loads baked snapshots.
```

Everything stronger must remain `NOT DEMONSTRATED` until the correction order
and acceptance tests pass.

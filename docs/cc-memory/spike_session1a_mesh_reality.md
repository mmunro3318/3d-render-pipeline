---
name: spike_session1a_mesh_reality
description: Session 1A spike findings — real mesh topology is far rougher than input contract assumes
type: project
---

# Session 1A Data Spike — Real Mesh Inspection
> Date: 2026-04-04 | Branch: feature/cold-start

## Meshes Inspected

All from `data/pilot-patient-scan-assets/blender-processed/`.

### combined-limb-final.obj (merged foot+leg)
- Faces: 10,448 | Vertices: 6,963
- Watertight: NO | Boundary edges: 3,148
- Connected components: 252 (largest=4,446 faces, ~160 single-face fragments)
- Euler number: 166 (should be 2 for closed genus-0)
- Bounding box: 0.19 x 0.65 x 0.23 (METERS — longest Y=650mm)
- Orientation: Y-up (Blender OBJ default)

### leg-cleaned.obj (isolated leg)
- Faces: 12,916 | Vertices: 8,181 | Watertight: NO
- Boundary edges: 3,230 | Euler: 108
- Bounding box: 0.25 x 0.81 x 0.24 (longest Y=810mm)

### prosthetic-cleaned.obj (hardware)
- Faces: 33,199 | Vertices: 23,069 | Watertight: NO
- Boundary edges: 12,035 | Euler: 452
- Bounding box: 0.28 x 0.82 x 0.23
- DIFFERENT coordinate space from limb meshes

### foot-cleaned.obj
- Faces: 2,752 | Watertight: NO
- Bounding box: 0.10 x 0.11 x 0.23

## Critical Findings

1. Scale is METERS not mm. Need 1000x or axis-swap aware scaling.
2. Orientation is Y-up (Blender OBJ default). Pipeline expects Z-up.
3. ALL meshes severely non-watertight. Open surfaces with fragments.
4. 252 components in combined-limb — highly fragmented.
5. Prosthetic in different coordinate space than limb.

## GO/NO-GO: Hole-Fill

- trimesh fill_holes: 3148 -> 2623 boundary edges. Still not watertight. NO-GO.
- Open3D Poisson (depth=8): 33K faces, still not watertight. NO-GO.
- VERDICT: Automated watertight closure not viable on these meshes.

## Implications

- Phase A (Blender) cleanup needs major improvement before Phase B works end-to-end
- Validator should be built as designed — it will correctly reject these meshes
- Validator should AUTO-FIX: Y-up to Z-up axis swap, meters to mm scale
- No architecture changes needed

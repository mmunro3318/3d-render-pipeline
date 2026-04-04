# Next Session Seed — Session 1A: Foundation + Data Spike
> Written: 2026-04-04 | Branch: feature/cold-start | Housekeeping DONE (9b1e1d2)

## Paste this into the next session

```
We're building a mesh processing pipeline for prosthetic covers. Structure Sensor scan → Blender cleanup (Phase A, separate tool) → Python pipeline (Phase B, this repo) → two print-ready STL clamshell halves for Stratasys PolyJet.

Housekeeping is DONE (commit 9b1e1d2). COLMAP code deleted, config swapped to mesh processing, docs updated, 29/29 tests pass. CEO + eng reviews CLEARED. Ready to implement Session 1A.

Key files to read first:
- CLAUDE.md (dev guide, soul, constraints)
- ROADMAP.md (sprint plan, input contract, architecture diagram)
- TODOS.md (deferred items from reviews)
- Eng review plan: ~/.claude/plans/curried-doodling-mccarthy.md (THE implementation plan — has session breakdown, test plan, file list, all decisions)
- docs/input-contract.md (Phase A → B handshake spec, validation report format)
- Design doc: ~/.gstack/projects/mmunro3318-3d-render-pipeline/admin-feature-cold-start-design-20260404-004721.md

PREREQUISITE: Python 3.12 venv must exist at .venv/ with deps installed. Verify:
  python -c "import open3d; import trimesh; import manifold3d; print('OK')"
If this fails, see docs/Python 3-12 Setup Instructions.md.

SESSION 1A IMPLEMENTATION (from eng review plan):

Step 1 — SPIKE FIRST: Load real meshes from data/pilot-patient-scan-assets/blender-processed/
  - combined-limb-final/combined-limb-final.obj (merged foot+leg)
  - leg-cleaned/leg-cleaned.obj (isolated leg)
  - prosthetic-cleaned/prosthetic-cleaned.obj (hardware)
  Note face count, watertight status, scale, orientation, component count.
  Document findings in docs/cc-memory/. DO NOT adjust architecture — just ground in reality.

Step 2 — GO/NO-GO spike: Test hole-fill on the combined limb mesh's proximal opening.
  Fallback if NO-GO: manual cap in Blender (notify founder), or geometric planar cap.

Step 3 — Config schema finalization (already mostly done in housekeeping):
  - Create StageResult dataclass in src/common/types.py
    Fields: mesh (trimesh.Trimesh), report_dict (dict), warnings (list[str]), stage_name (str)

Step 4 — Input contract validator (src/intake/validator.py):
  - Check sequence: format → loadable → single component → watertight (with repair loop) → scale → orientation → triangle count (with decimate) → manifold + self-intersection (via manifold3d)
  - Returns ContractReport with per-check status (PASS/AUTO-FIXED/FAIL) and validation_level
  - Standalone CLI: python -m src.intake.validator mesh.obj

Step 5 — Tests for types + validator (~15 test cases):
  - New fixtures in conftest.py: repairable_mesh, multi_component_mesh, synthetic_limb_mesh, oversized_mesh
  - test_types.py: StageResult creation, field access
  - test_validator.py: each contract check as separate test

Key decisions already locked (do NOT re-litigate):
- Coordinate convention: Z-up (+Z proximal, +Y anterior)
- Split axis for above_knee: sagittal (Y-axis)
- Pydantic ConfigDict(extra='forbid') on PipelineConfig
- Per-stage invariants (not universal validation on every stage)
- Boolean fallback: manifold3d → repair+retry → trimesh → ABORT
- Debug mesh exports to output/debug/
- Scale/triangle count are KNOWN ISSUES handled by founder + Cowork separately

What already exists and should be reused:
- src/common/config.py — IntakeConfig, RepairConfig, BooleanConfig, ExportConfig, LimbProfile, load_config()
- src/common/mesh_utils.py — validate_mesh(), repair_mesh(), export_stl/ply/obj()
- config/pipeline.yaml — fully updated for mesh processing
- tests/conftest.py — cube_mesh, cylinder_mesh, sphere_mesh, open_mesh, zero_face_mesh fixtures
- docs/input-contract.md — canonical contract spec with JSON report format
```

## What the next session should do

1. Read CLAUDE.md, ROADMAP.md, TODOS.md, eng review plan, input-contract.md
2. Verify Python 3.12 venv works (fail fast if not)
3. Spike: load real meshes, document findings
4. Implement StageResult + validator + tests
5. Commit Session 1A work

## Blockers the founder must resolve BEFORE next session

1. **Install Python 3.12** — see docs/Python 3-12 Setup Instructions.md. Without this, we cannot load meshes or run the real pipeline. (~5 min)
2. **Verify real mesh data exists** — data/pilot-patient-scan-assets/blender-processed/ should contain combined-limb-final/, leg-cleaned/, prosthetic-cleaned/ with .obj files from Blender Cowork sessions.

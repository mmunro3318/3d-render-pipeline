# ROADMAP — HyperReal 3D Render Pipeline
> Last updated: 2026-04-04 | Branch: feature/cold-start

## Product

CLI pipeline: Structure Sensor 3D scan of residual limb + prosthetic hardware mesh → two print-ready binary STL files (clamshell halves) for Stratasys PolyJet printing.

## Two-Phase Architecture

```
Phase A (Blender + Cowork)          Phase B (Python Pipeline)
========================            ========================
Raw Structure Sensor scan           Validated mesh (meets input contract)
        |                                   |
  [Manual/scripted cleanup]          [Intake: load + validate contract]
  - Remove artifacts                        |
  - Segment limb from background     [Repair: smooth, close holes, fix topology]
  - Fill holes / cap openings               |
  - Scale to real-world mm           [Mirror: reflect for contralateral limb]
  - Align with hardware mesh                |
        |                            [Boolean: subtract hardware from limb]
        v                                   |
  Export OBJ meeting ──────────────> [Split: planar cut → two halves]
  input contract                            |
                                     [Magnets: subtract pocket cylinders]
                                            |
                                     [Validate: watertight, wall, tri count]
                                            |
                                     [Export: 2x binary STL + QC report JSON]
```

## Input Contract (Phase A → Phase B handshake)

A mesh entering Phase B must satisfy:

| Property | Requirement |
|----------|-------------|
| Format | OBJ (primary) or STL |
| Watertight | `mesh.is_watertight == True` |
| Scale | Real-world millimeters (longest axis 200-500mm for above-knee) |
| Orientation | Proximal up (+Z), anterior forward (+Y) — matches Blender native |
| Triangles | 10K-500K faces |
| Manifold | No self-intersections, consistent winding |
| Single body | One connected component |
| Hardware aligned | Same coordinate frame as hardware mesh |

## Sprint Plan

### Pre-Work: Housekeeping (~30 min)
- [ ] Archive COLMAP-era docs to `docs/archive/colmap-era/`
- [ ] Delete dead COLMAP code (~1,474 lines)
- [ ] Update config schema for mesh processing
- [x] Write ROADMAP.md

### Sprint 1: Phase B Pipeline — Cleaned Mesh → STLs (2-3 sessions)

**Goal:** `python scripts/run_mesh_to_cover.py --input limb.obj --hardware hardware.obj` → two print-ready STLs

| Session | Modules | Key risk |
|---------|---------|----------|
| 1A | Config schema, StageResult, input contract validator, intake loader | Hole-fill on large opening |
| 1B | Repair, mirror, cavity boolean (manifold3d) | Boolean fails on real mesh topology |
| 1C | Seam split, magnets, export, CLI orchestrator | Non-watertight after split |

### Sprint 2: Input Quality + Automation
- Real wall thickness validation (ray-casting)
- Auto-scale detection
- ICP auto-registration (limb ↔ hardware alignment)
- Begin automating Phase A cleanup

### Sprint 3: Robustness + Second Patient
- Test on second patient data
- Generalize for different limb types
- Improve diagnostics and error messages

### Future (not scoped)
- Phase A full automation
- Capture device comparison (Structure Sensor vs Polycam vs photos)
- Texture/color for realistic covers
- COLMAP integration (photos-only path)
- Clinician-facing app

## Key Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Pipeline phase split | Phase A (Blender) + Phase B (Python) | Raw scans need heavy cleanup; automate the easy part first |
| Sprint 1 input | Founder's cleaned mesh | Already exists, skip the hard cleanup problem for now |
| Boolean engine | manifold3d | Best-in-class for mesh boolean, pip-installable |
| Scale strategy (MVP) | Manual measurement + config | Auto-detection is Sprint 2 |
| Split geometry | Planar cut, posterior midline | Simplest approach, proven in prosthetics |
| Magnets | Configured coordinates, no auto-placement | Smart placement deferred |

## What's NOT in scope

- Raw scan cleanup automation (Sprint 2+)
- Auto-alignment of limb/hardware meshes (Sprint 2+)
- Wall thickness validation beyond stub (Sprint 2)
- Web UI, API, cloud services
- Multi-patient concurrency
- CI/CD pipeline
- SAM2 segmentation / PyTorch3D refinement
- Texture/color preservation

## Design Docs

| Doc | Location | Status |
|-----|----------|--------|
| Design v2 (current) | `~/.gstack/projects/.../admin-feature-cold-start-design-20260404-004721.md` | DRAFT |
| Design v1 | `~/.gstack/projects/.../admin-feature-cold-start-design-20260403-185347.md` | SUPERSEDED |
| Eng review | `~/.claude/plans/curried-doodling-mccarthy.md` | CLEARED -- 0 unresolved |

## Patient Data

Located in `data/pilot-patient-scan-assets/` (gitignored):
- `foot-scan/` — Structure Sensor foot OBJ + texture
- `full-limb-scan/` — Structure Sensor full limb OBJ + texture
- `prosthetic-scan/` — Structure Sensor prosthetic hardware OBJ + texture
- `blender-processed/` — Founder's cleaned mesh exports from Blender (combined-limb-final, leg-cleaned, prosthetic-cleaned)
- 10 photos (various angles)

# Project Plan — Forearm Prototype MVP
> HyperReal | April 2026 | Clean Slate Rebuild

## Planning Philosophy

This plan is designed for **5-8 hours/week of part-time work**. Every sprint is 2 weeks (10-16 hours of work). Every sprint ends with something **testable and demonstrable** — a screenshot, a file, a printed object, or a passing test suite. No sprint is "just research" or "just planning."

The rule: **if you can't show it, you didn't ship it.**

---

## Phase 0: Foundation (Sprints 1-2)
> Goal: Working dev environment + validated capture protocol

### Sprint 1 — Environment + First Capture (Week 1-2)
**Hours budget:** ~6-8 hrs

**Deliverables:**
1. Clean repo initialized with directory structure, requirements.txt, CLAUDE.md
2. COLMAP installed and verified (reconstruct a test object — coffee mug, shoe, anything)
3. First forearm photo set captured (40-60 photos following protocol below)

**Tasks:**
- [ ] Create new repo (clean slate). Set up virtualenv, install trimesh, pycolmap, open3d, torch, pytorch3d
- [ ] Install COLMAP (binary or build from source). Run `colmap automatic_reconstructor` on a test dataset to verify it works
- [ ] Write and follow the capture protocol on a simple object (NOT the forearm yet — practice first)
- [ ] Capture forearm: 40-60 photos, color card in 5 shots, consistent lighting

**Capture Protocol (v1):**
```
Equipment: iPad Pro camera (main camera, not LiDAR)
Lighting: Well-lit room, diffuse light, no harsh shadows
Color card: In frame for 5 photos (front, back, left, right, top)
Distance: 30-50cm from limb
Coverage: Circle the forearm at 3 heights:
  - Wrist level (15-20 photos, every ~20°)
  - Mid-forearm (15-20 photos, every ~20°)
  - Elbow level (10-15 photos, every ~25°)
Overlap: Each photo shares ~60% content with neighbors
Total: 40-55 photos
Time: <10 minutes
```

**Demo checkpoint:** Screenshot of COLMAP sparse reconstruction of test object. Photo set of forearm in a folder.

---

### Sprint 2 — COLMAP on Forearm + Baseline Mesh (Week 3-4)
**Hours budget:** ~6-8 hrs

**Deliverables:**
1. COLMAP sparse reconstruction of forearm (camera poses + sparse points)
2. Dense reconstruction → Poisson mesh (first rough forearm mesh)
3. Basic Python orchestration script that runs the full pipeline

**Tasks:**
- [ ] Run COLMAP on forearm photos. Verify reprojection error < 2px
- [ ] If COLMAP fails: diagnose (too few features? bad overlap?). Re-capture if needed
- [ ] Dense reconstruction: COLMAP dense or OpenMVS
- [ ] Poisson surface reconstruction (Open3D or trimesh)
- [ ] Write `scripts/run_stage1.py` — takes a photo directory, outputs an STL
- [ ] Visual inspection: open mesh in a viewer (trimesh.show() or MeshLab). Does it look like an arm?

**Demo checkpoint:** STL file of forearm mesh. Screenshot of mesh in viewer. Script that reproduces it from photos.

**Go/no-go gate:** If the mesh is recognizably a forearm (even if rough), proceed. If COLMAP failed entirely, re-capture with more photos/better lighting before moving on.

---

## Phase 1: Pipeline Core (Sprints 3-5)
> Goal: Printable forearm cover with basic cavity

### Sprint 3 — Mesh Cleanup + Watertight Validation (Week 5-6)
**Hours budget:** ~6-8 hrs

**Deliverables:**
1. Mesh repair pipeline (hole filling, normal fixing, decimation)
2. Watertight validation function
3. Accuracy measurement (if Structure Sensor scan available: compare meshes)
4. Unit tests for mesh utilities

**Tasks:**
- [ ] Write `src/common/mesh_utils.py`: repair, validate watertight, decimate, export
- [ ] Write `src/stage1/validate.py`: bounds check, vertex count, watertight assert
- [ ] If you have a Structure Sensor scan: compute Hausdorff/Chamfer distance to COLMAP mesh
- [ ] Write tests: `tests/test_mesh_utils.py` (synthetic cube/cylinder fixtures)
- [ ] Run cleanup on the forearm mesh. Export cleaned STL.

**Demo checkpoint:** Cleaned, watertight STL. Test suite passing. Accuracy measurement if available.

---

### Sprint 4 — Mirroring + Cavity Subtraction (Week 7-8)
**Hours budget:** ~6-8 hrs

**Deliverables:**
1. Mirror function (flip mesh across sagittal plane)
2. Cavity Boolean subtraction (shell - dummy hardware = cover)
3. Wall thickness validation

**Tasks:**
- [ ] Write `src/stage2/mirror.py`: reflect mesh, fix normals, verify watertight
- [ ] Create a dummy "prosthetic hardware" mesh (simple cylinder, ~80% of forearm diameter)
- [ ] Write `src/stage2/cavity_boolean.py`: offset shell inward for clearance, subtract hardware
- [ ] Write `src/stage2/validate.py`: minimum wall thickness check (≥1.5mm everywhere)
- [ ] Tests: `tests/test_mirror.py`, `tests/test_cavity.py`

**Demo checkpoint:** Two meshes side by side — original forearm + mirrored cover with hollow interior. Cross-section screenshot showing cavity.

---

### Sprint 5 — Clamshell Split + Print Prep (Week 9-10)
**Hours budget:** ~6-8 hrs

**Deliverables:**
1. Clamshell split function (bisect mesh along a plane)
2. Magnet pocket subtraction
3. Print-ready STL files (two halves)
4. Full Stage 1+2 pipeline script

**Tasks:**
- [ ] Write `src/stage2/seam_split.py`: split mesh along configurable plane
- [ ] Write `src/stage2/magnets.py`: parametric magnet pocket geometry, subtract from split faces
- [ ] Update `scripts/run_full_pipeline.py`: photos → mesh → mirror → cavity → split → export
- [ ] Final validation: both halves watertight, wall thickness ≥ 1.5mm, bounds sensible
- [ ] Export print-ready files

**Demo checkpoint:** Two STL files ready to send to Stratasys. Full pipeline script that reproduces everything from photos.

**MILESTONE: Print decision.** If the STLs look good, send to Stratasys for a test print (~$50-100). This is the first physical proof of concept.

---

## Phase 2: Refinement (Sprints 6-8)
> Goal: Improve accuracy, add texture, iterate on fit

### Sprint 6 — Differentiable Refinement (Week 11-12)
**Hours budget:** ~6-8 hrs

**Deliverables:**
1. PyTorch3D silhouette refinement module
2. Before/after accuracy comparison
3. Refined mesh STL

**Tasks:**
- [ ] Write `src/stage1/differentiable_refine.py`:
  - Load COLMAP cameras → PyTorch3D cameras
  - Load Poisson mesh → PyTorch3D Meshes
  - Silhouette loss + Laplacian smoothing
  - 100-300 iterations, coarse-to-fine schedule
- [ ] Generate SAM2 masks for all forearm photos (silhouette targets)
- [ ] Run refinement. Compare to pre-refinement mesh (Hausdorff distance)
- [ ] If improvement is measurable: integrate into pipeline. If not: skip it (COLMAP alone is fine)

**Demo checkpoint:** Side-by-side render of COLMAP-only vs. refined mesh. Accuracy numbers.

**Decision gate:** Is differentiable refinement worth the complexity? If COLMAP alone hits ±3mm, skip this module and move on.

---

### Sprint 7 — Texture Mapping (Week 13-14)
**Hours budget:** ~6-8 hrs

**Deliverables:**
1. Per-vertex color extraction from photos
2. Color-calibrated mesh (OBJ with vertex colors)
3. Visual comparison to reference photos

**Tasks:**
- [ ] Write `src/stage1/texture.py`:
  - Project each vertex onto each photo using COLMAP cameras
  - Sample pixel color at projection point
  - Median-blend across views (reject outliers)
  - Optional: color correction using calibration card
- [ ] Export as OBJ with vertex colors
- [ ] Render from multiple angles, compare to reference photos

**Demo checkpoint:** Colored mesh that looks like a real forearm. Render comparison images.

---

### Sprint 8 — Second Print + Iteration (Week 15-16)
**Hours budget:** ~6-8 hrs

**Deliverables:**
1. Revised STL files incorporating all improvements
2. Second print order (with color if available on printer)
3. Fit test documentation (photos of cover on forearm)
4. Lessons learned document

**Tasks:**
- [ ] Incorporate texture into print files (if Stratasys J750/J850 available)
- [ ] Re-run full pipeline with any improvements from Sprints 6-7
- [ ] Export final print files
- [ ] If first print arrived: fit test, document gaps/issues, photograph results
- [ ] Update INSIGHTS.md with lessons learned

**Demo checkpoint:** Photos of printed cover on Mike's forearm. Documented fit issues and next steps.

**MILESTONE: Forearm prototype complete.** You now have a working pipeline from photos → printed prosthetic cover.

---

## Phase 3: Scale to Patient (Sprints 9-12)
> Goal: Adapt pipeline for above-knee amputee

### Sprint 9 — Above-Knee Capture + Reconstruction (Week 17-18)
- Adapt capture protocol for above-knee (larger surface, more concavity)
- Run pipeline on patient data (or Mike's thigh as proxy)
- Identify accuracy gaps vs. forearm

### Sprint 10 — Socket Interface + Real Hardware (Week 19-20)
- Integrate actual prosthetic hardware scan
- Solve alignment (ICP or semi-manual)
- Validate cavity fit with real hardware dimensions

### Sprint 11 — Internal Flex Structures (Week 21-22)
- Implement knee band detection
- Simple accordion ribs (6-8 internal walls)
- Validate watertight + min thickness

### Sprint 12 — Patient Print + Clinical Feedback (Week 23-24)
- Full pipeline on patient geometry
- Print and deliver to patient/clinic
- Document feedback, iterate

---

## Sprint Cadence

Each 2-week sprint follows the same rhythm:

```
Day 1 (session 1, ~2 hrs):
  - Review sprint goals
  - Set up any new dependencies
  - Write skeleton code + tests (red)

Day 2 (session 2, ~2 hrs):
  - Implement core functionality (green)
  - Run tests, fix failures

Day 3 (session 3, ~2 hrs):
  - Polish, edge cases, validation
  - Generate demo artifacts (screenshots, STLs, test results)

Day 4 (session 4, ~2 hrs — if available):
  - Documentation update
  - Prep for next sprint
  - Buffer for debugging
```

**If you only have 5 hours in a week:** Cut session 4. The demo artifact from session 3 is your sprint deliverable.

**If you have a good week (8+ hours):** Use the extra time for capture practice or exploring the next sprint's unknowns.

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| COLMAP fails on forearm photos | Medium | HIGH | Re-capture with more photos, better lighting. Test on simple object first. |
| PyTorch3D won't install on RTX 5060 Ti | Medium | Medium | Fall back to CPU-only, or skip refinement entirely (COLMAP alone may be sufficient) |
| Boolean operations fail | Low | Medium | Manifold3D is reliable with clean inputs. Fallback: offset-based cavity |
| Burnout / time crunch | HIGH | HIGH | Every sprint has a hard stop. Ship what you have. No "one more feature." |
| Stratasys print turnaround too slow | Medium | Medium | Order prints early (Sprint 5). Don't block on receiving them. |
| Forearm results don't transfer to above-knee | Medium | Medium | Address in Phase 3. Forearm proves the pipeline; above-knee proves the product. |

---

## Definition of Done — Forearm MVP (End of Phase 2)

- [ ] Pipeline script: `python run_pipeline.py --photos ./forearm_photos/ --output ./cover.stl`
- [ ] Output: Two watertight STL files (clamshell halves) with cavity
- [ ] Accuracy: ±3mm or better vs. reference (visual or measured)
- [ ] Print: At least one physical print completed and fit-tested
- [ ] Tests: Core mesh utilities have passing unit tests
- [ ] Documented: Capture protocol, pipeline steps, known limitations
- [ ] Reproducible: Another person could follow the docs and get a result

---

## What This Plan Does NOT Include (Intentionally)

- API / web interface (not needed until you have paying customers)
- Automated job queue / workers (run locally for now)
- Multi-patient support (one patient at a time is fine)
- Perfect color matching (good enough is good enough)
- Stage 3 internal flex for forearm (forearms don't need knee flex)
- CI/CD pipeline (overkill for solo dev)

These are all Phase 3+ concerns.

---

## Repo Structure (Clean Slate)

```
hyperreal-v2/
├── CLAUDE.md                  # AI dev guide
├── README.md                  # Setup + usage
├── requirements.txt           # Pinned dependencies
├── config/
│   └── pipeline.yaml          # All hyperparameters
├── src/
│   ├── common/
│   │   ├── config.py          # Pydantic config loader
│   │   └── mesh_utils.py      # Repair, validate, export
│   ├── stage1/
│   │   ├── colmap_runner.py   # COLMAP orchestration
│   │   ├── poisson_mesh.py    # Dense cloud → watertight mesh
│   │   ├── segment.py         # SAM2 mask generation
│   │   ├── refine.py          # PyTorch3D silhouette refinement
│   │   └── texture.py         # Per-vertex color from photos
│   └── stage2/
│       ├── mirror.py          # Sagittal reflection
│       ├── cavity_boolean.py  # Hardware subtraction
│       ├── seam_split.py      # Clamshell bisection
│       └── magnets.py         # Magnet pocket geometry
├── scripts/
│   ├── run_stage1.py          # Photos → mesh
│   ├── run_stage2.py          # Mesh → print-ready cover
│   └── run_full_pipeline.py   # End to end
├── tests/
│   ├── conftest.py
│   ├── test_mesh_utils.py
│   ├── test_colmap.py
│   ├── test_cavity.py
│   └── test_mirror.py
└── docs/
    └── CAPTURE_PROTOCOL.md
```

Flat, simple, one dev. No nested packages until you need them.

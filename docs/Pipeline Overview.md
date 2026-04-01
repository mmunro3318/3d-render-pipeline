# Pipeline Overview
> What goes in, what comes out, what's on disk at every step.

---

## Full Pipeline (end state)

```
Photos (40-55 JPEGs)
  │
  ▼
┌─────────────────────────────────────────────────────────┐
│  STAGE 1 — Reconstruction                               │
│                                                         │
│  COLMAP SfM ──▶ Dense MVS ──▶ Poisson Mesh              │
│       ↓              ↓              ↓                   │
│  cameras.bin    dense.ply     forearm_raw.stl            │
│  images.bin                                             │
│  points3D.bin                                           │
│                                                         │
│  (optional) SAM2 masks + PyTorch3D refinement           │
│       ↓                    ↓                            │
│  masks/*.png         forearm_refined.stl                 │
│                                                         │
│  Texture projection ──▶ forearm_colored.obj              │
└─────────────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────────────┐
│  STAGE 2 — Print Prep                                    │
│                                                         │
│  Mirror ──▶ Cavity Boolean ──▶ Clamshell Split           │
│    ↓              ↓                  ↓                  │
│  cover_shell.stl  cover_hollow.stl   cover_top.stl      │
│                                      cover_bottom.stl   │
│                                                         │
│  Magnet pockets + registration pins                      │
│       ↓                                                 │
│  cover_top_final.stl                                    │
│  cover_bottom_final.stl                                 │
└─────────────────────────────────────────────────────────┘
  │
  ▼
  Stratasys PolyJet printer
```

---

## Data Capture Protocol

This is the most important part of the pipeline. Bad photos = bad mesh. No algorithm fixes bad input.

### Equipment
- iPad Pro (main camera, NOT the LiDAR sensor)
- Color calibration card (X-Rite ColorChecker Passport or printed equivalent)
- Well-lit room with diffuse light — no harsh directional shadows

### Setup (forearm self-scan)
1. Rest forearm on a table with hand relaxed, palm down
2. Place color card flat next to the forearm
3. Mark three height rings with small stickers or tape: **wrist**, **mid-forearm**, **elbow**
4. Keep arm completely still for the entire capture (~5 min)

### Capture Pattern
```
Ring 1 — Wrist:       15-20 photos, ~20° apart, camera 30-40cm away
Ring 2 — Mid-forearm:  15-20 photos, ~20° apart, camera 30-40cm away
Ring 3 — Elbow:       10-15 photos, ~25° apart, camera 30-40cm away
Color card shots:     5 photos (include card in frame, one per quadrant + top)
```

**Total: 40-55 photos. Time: <5 minutes.**

### Rules
- **60% overlap** between adjacent photos (each photo shares >half its content with the next)
- Keep the same distance from the limb — don't zoom in and out
- Don't move the limb between shots
- Shoot in landscape orientation
- Avoid reflective surfaces in background (confuses feature matching)
- No motion blur — hold still or use burst mode and pick the sharpest

### Clinic Version (future — for patients)
Same protocol, but:
- Patient seated, limb resting on a padded support
- Clinician or Mike walks around the patient (patient stays still)
- Target: **under 3 minutes** of capture time
- Color card taped to the support, always visible
- Capture both the sound limb AND the residual limb + hardware in one session

---

## Sprint-by-Sprint: Files on Disk

### After Sprint 1 — Environment + First Capture

```
hyperreal-v2/
├── requirements.txt
├── CLAUDE.md
├── config/
│   └── pipeline.yaml
└── data/
    ├── test_object/          ◄── practice photos (mug, shoe, etc.)
    │   └── *.jpg
    └── forearm_v1/           ◄── first forearm capture
        └── *.jpg
```

**What you should have:** COLMAP installed and working. A folder of 40-55 forearm photos. A test reconstruction of a simple object proving COLMAP works.

**What you verify:** `colmap automatic_reconstructor` completes on the test object without errors.

---

### After Sprint 2 — COLMAP Reconstruction + Baseline Mesh

```
hyperreal-v2/
├── src/
│   └── stage1/
│       ├── colmap_runner.py
│       └── poisson_mesh.py
├── scripts/
│   └── run_stage1.py         ◄── photos → STL in one command
├── data/
│   └── forearm_v1/
│       ├── *.jpg
│       └── colmap_output/
│           ├── sparse/
│           │   ├── cameras.bin
│           │   ├── images.bin
│           │   └── points3D.bin
│           └── dense/
│               ├── fused.ply
│               └── meshed-poisson.ply
└── output/
    └── forearm_raw.stl       ◄── FIRST MESH
```

**What you should have:** A rough but recognizable forearm mesh.

**What you verify:**
- COLMAP reprojection error < 2px
- Mesh opens in MeshLab/trimesh without errors
- Visual sanity: it looks like a forearm, not a blob

---

### After Sprint 3 — Mesh Cleanup

```
hyperreal-v2/
├── src/
│   ├── common/
│   │   └── mesh_utils.py     ◄── repair, validate, decimate, export
│   └── stage1/
│       └── validate.py       ◄── watertight checks, bounds, vertex count
├── tests/
│   ├── conftest.py
│   └── test_mesh_utils.py    ◄── synthetic cube/cylinder tests
└── output/
    ├── forearm_raw.stl
    └── forearm_cleaned.stl   ◄── watertight, repaired, decimated
```

**What you should have:** A watertight mesh with fixed normals, filled holes, and a sensible face count (~100K).

**What you verify:**
- `mesh.is_watertight == True`
- `pytest tests/ -v` all green
- Cleaned mesh volume is within 5% of raw mesh volume (no major geometry loss)

---

### After Sprint 4 — Mirror + Cavity

```
hyperreal-v2/
├── src/
│   └── stage2/
│       ├── mirror.py
│       └── cavity_boolean.py
├── tests/
│   ├── test_mirror.py
│   └── test_cavity.py
└── output/
    ├── forearm_cleaned.stl
    ├── cover_shell.stl       ◄── mirrored outer shell
    └── cover_hollow.stl      ◄── shell with cavity subtracted
```

**What you should have:** A hollow cover that fits over a dummy hardware cylinder.

**What you verify:**
- Mirrored mesh is watertight and volume matches original
- Boolean didn't create holes or inverted faces
- Cross-section shows uniform wall ≥ 1.5mm

---

### After Sprint 5 — Clamshell + Print Ready

```
hyperreal-v2/
├── src/
│   └── stage2/
│       ├── seam_split.py
│       └── magnets.py
├── scripts/
│   └── run_full_pipeline.py  ◄── photos → two print-ready STLs
├── tests/
│   └── test_split.py
└── output/
    ├── cover_top_final.stl   ◄── PRINT THIS
    ├── cover_bottom_final.stl ◄── PRINT THIS
    └── validation_report.txt  ◄── watertight, thickness, dimensions
```

**What you should have:** Two STL files you can email to Stratasys.

**What you verify:**
- Both halves watertight
- Wall thickness ≥ 1.5mm everywhere
- Magnet pockets present and correctly positioned
- Registration pins on one half, holes on the other
- `python scripts/run_full_pipeline.py --photos data/forearm_v1/ --output output/` reproduces everything

**🖨️ MILESTONE: Order first print.**

---

### After Sprint 6 — Differentiable Refinement (optional)

```
hyperreal-v2/
├── src/
│   └── stage1/
│       ├── segment.py        ◄── SAM2 mask generation
│       └── refine.py         ◄── PyTorch3D silhouette refinement
└── output/
    ├── masks/
    │   └── *.png             ◄── binary silhouettes per photo
    ├── forearm_refined.stl   ◄── improved geometry (maybe)
    └── refinement_comparison.txt  ◄── before/after Hausdorff distance
```

**Decision gate:** If Hausdorff distance improved by >1mm, keep the module. If not, delete it and move on. COLMAP alone may be good enough.

---

### After Sprint 7 — Texture

```
hyperreal-v2/
├── src/
│   └── stage1/
│       └── texture.py        ◄── per-vertex color from photos
└── output/
    ├── forearm_colored.obj   ◄── mesh with vertex colors
    └── renders/
        └── *.png             ◄── multi-angle renders for visual QC
```

---

### After Sprint 8 — Second Print + Fit Test

```
output/
├── cover_top_final_v2.stl
├── cover_bottom_final_v2.stl
├── forearm_colored.obj
├── fit_test/
│   └── *.jpg                 ◄── photos of print on your forearm
└── INSIGHTS.md               ◄── what worked, what didn't, what to fix
```

**🖨️ MILESTONE: Forearm prototype complete. Working pipeline from photos to printed cover.**

---

## What I Need From You (Mike) at Each Sprint

| Sprint | Your job | Time |
|--------|----------|------|
| 1 | Install COLMAP. Capture test object + forearm photos. | ~2 hrs manual |
| 2 | Verify mesh looks right. Re-capture if COLMAP failed. | ~30 min |
| 3 | Visual check of cleaned mesh. | ~15 min |
| 4 | Look at cross-sections. Confirm cavity looks reasonable. | ~15 min |
| 5 | Review STLs. Approve and order print. | ~30 min |
| 6 | Compare before/after. Decide: keep refinement or skip. | ~15 min |
| 7 | Compare colored mesh to reference photos. | ~15 min |
| 8 | Receive print. Fit test. Photograph. Write up notes. | ~1 hr |

Everything else is code — that's what the coding agent handles with the implementation guides.

---

## File Format Reference

| Format | Used for | Viewer |
|--------|----------|--------|
| `.stl` (binary) | Print-ready geometry, no color | MeshLab, trimesh, Stratasys |
| `.obj` | Geometry + vertex colors | MeshLab, Blender |
| `.ply` | Dense point clouds from COLMAP | MeshLab, Open3D |
| `.bin` | COLMAP internal (cameras, images, points) | pycolmap |
| `.png` | SAM2 masks, renders | any image viewer |
| `.yaml` | Pipeline config | text editor |

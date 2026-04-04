> April 2026 | HyperReal Prosthetic Cover Pipeline

## Board Members
- **CEO Advisor** — Business viability, scope, go-to-market
- **CTO Advisor** — Architecture, tech stack, build decisions
- **Math/Algorithm Expert** — Optimization theory, convergence, loss design
- **3D Manufacturing Guru** — Mesh quality, printability, Stratasys requirements

---

## Unanimous Consensus

All four advisors agreed on these points:

1. **The sphere/rectangle initialization idea is dead.** Silhouette-only optimization from a cold start will converge to wrong local minima. The loss landscape between "sphere" and "anatomically correct limb" is riddled with degenerate solutions.

2. **Use COLMAP (photogrammetry) as the backbone.** It's proven, battle-tested, achieves 1.13mm accuracy, and gives you camera poses for free. Differentiable rendering should be a refinement step, not the primary reconstruction method.

3. **The capture protocol is the product.** 10 photos will never work. You need 30-40 minimum, 50-100 for production quality. Designing and validating the capture protocol is as important as the algorithm.

4. **The forearm prototype is the right move.** Fast iteration, no patient data concerns, proves the pipeline end-to-end. But it must have clear success criteria and a hard deadline (4 weeks).

5. **Ship Stage 1 before building Stages 2-3.** The stages are sequential dependencies. Don't build in parallel.

---

## CEO Perspective — Key Takeaways

### MVP Definition
v0.1 is: One patient, one cover, one time. COLMAP + manual alignment + Boolean cavity subtraction. No internal flex structures. No API. No automation.

### The Hard Truths
- **Unpaid work doesn't scale.** Mike will hit burnout around week 8-12. The founders need to either pay him, bring in a co-founder, or accept that the project stalls.
- **The competitive advantage is the capture protocol and clinical relationships, not the algorithm.** A clinic that trusts you and sends 5 patients/month beats a perfect algorithm with no customers.
- **iPad LiDAR is a dead end for primary capture.** Fix the photo capture protocol or abandon the iPad as a geometry source.
- **You have ~6 months before this needs to show revenue or attract funding.** Stratasys is a vendor, not an investor.

### Go-to-Market Timeline
- Month 1-2: Forearm prototype + capture protocol validation
- Month 2-3: First real patient (volunteer, not paying)
- Month 3-4: Iterate on fit/finish
- Month 4-6: 3-5 paying customers, validate unit economics
- Production-ready product: Not before month 4

### Business Model
- Insurance doesn't cover cosmetic covers (dead end for now)
- Likely customer: clinic buys covers or patient pays out of pocket ($500-1000/unit)
- Need 10-20 covers/month for $10K MRR
- Critical question: Do you have a clinic ready to buy 5 covers this month?

---

## CTO Perspective — Key Takeaways

### Architecture: COLMAP-First Hybrid

```
Photos (40-100, iPad camera)
  → COLMAP (SfM → camera poses + sparse points)
    → OpenMVS or Poisson reconstruction (dense mesh)
      → [Optional] PyTorch3D differentiable refinement
        → Watertight mesh validation
          → Export STL
```

### Build vs. Integrate
- **Wrap (don't rewrite):** COLMAP, OpenMVS, Poisson reconstruction, PyTorch3D renderers
- **Build:** Orchestration/state machine, validation layer, QC + logging, post-processing (repairs, export)

### Tech Stack
```
Core:        trimesh, open3d, numpy
Photogram:   pycolmap (0.9.1+), opencv-python (4.8+)
ML:          torch (2.1+, CUDA 12.1), pytorch3d (0.7.6+)
Config:      pydantic v2, PyYAML
Segment:     ultralytics (8.0+) — SAM2
Test:        pytest, pytest-cov
```

### The Sensor Fusion Path (Worth Pursuing)
Use Structure Sensor scan as weak supervision alongside COLMAP:
- COLMAP gives geometry from photos (strong signal)
- Structure Sensor gives rough initialization (weak supervision)
- Fuse via Chamfer loss in PyTorch3D refinement
- But: get COLMAP baseline working FIRST, sensor fusion is Phase 2

### Top 5 Technical Landmines
1. COLMAP alignment fails silently → validate reprojection error < 2px
2. Poisson produces non-watertight mesh → repair + voxel fallback
3. PyTorch3D optimization diverges → clamp vertex displacement, monitor loss
4. Boolean ops timeout/fail → Manifold3D + timeout + manual fallback
5. GPU OOM → decimate to 20K verts, render at 512x512

### Phase Timeline
- Phase 0 (Weeks 1-3): Stage 1 proof of concept — COLMAP → Poisson → printable STL
- Phase 1 (Weeks 4-5): Stage 2 basic — hardware cavity + clamshell split
- Phase 2 (Weeks 6-8): Stage 3 — internal flex structures

---

## Math Expert Perspective — Key Takeaways

### Why Sphere Init Fails (Formally)
Silhouette loss is uninformative in the interior of the rendered silhouette. Only vertices near the silhouette boundary receive meaningful gradients. A sphere → leg optimization must cross a vast non-convex landscape where degenerate shapes (flat discs, bowties, pretzels) produce good silhouette loss but wrong 3D geometry.

### Basin of Attraction
For silhouette-based refinement on limb geometry:
- Within ±10mm: Refinement is reliable
- ±15-25mm: May work with multi-view + photometric losses
- Beyond ±25mm: Unreliable without additional priors

Structure Sensor gives ±2-5mm → safely inside the basin.

### Camera Poses: Solve Separately
Joint optimization of camera poses + mesh vertices has gauge freedom (mesh shift ↔ camera shift are indistinguishable). COLMAP solves poses first via bundle adjustment (well-conditioned), then lock them during refinement.

### Loss Function Stack (Recommended)
```
Phase 1 (iter 0-100):   1.0 × silhouette + 0.1 × Laplacian smoothing
Phase 2 (iter 100-300): 1.0 × silhouette + 0.05 × Laplacian + 0.05 × photometric
Phase 3 (iter 300-500): 1.0 × silhouette + 0.01 × Laplacian + 0.1 × photometric + 0.01 × normal consistency
```

### Minimum Photo Count
- Theoretical minimum: 15-20 (with Structure Sensor init)
- Recommended: 30-40
- Optimal: 50-100
- Below 15: Risk missing coverage on curved regions

### Forearm vs. Above-Knee
Forearm is easier: lower curvature, fewer concavities, better feature tracking (arm hair, freckles). Above-knee has deep concavity at socket interface, scarring that confuses feature matchers, and more anatomical variation.

### Texture Strategy
Per-vertex color via spherical harmonics lighting model:
1. Estimate light direction from color calibration card
2. Solve for intrinsic diffuse color per vertex across all views
3. Export as OBJ with per-vertex color
Target: ΔE < 5 (perceptually similar)

---

## 3D Manufacturing Guru Perspective — Key Takeaways

### PolyJet Requirements (Non-Negotiable)
- **Watertightness:** Must be perfect. Single open edge kills the print.
- **Wall thickness:** ≥1.5mm for Agilus 30A, ≥1mm for VeroUltra. Target 2-2.5mm for flex areas.
- **File format:** Binary STL or OBJ with MTL (for color)
- **Triangle count:** 100K-300K is fine. Above 500K adds no value.
- **Manifoldness:** No flipped normals, no T-junctions, no duplicate verts

### Mirroring Gotchas
- Human limbs aren't symmetric — the mirrored sound limb won't perfectly match the residual limb's socket interface
- Need a SEPARATE scan of the residual limb to anchor the socket interface
- Mirror for external shape, warp/adjust internal surface to match residual anatomy
- Texture/color won't mirror (freckles, scars, hair distribution)

### Boolean Operations
- Manifold3D succeeds 95%+ of the time IF inputs are clean
- Failure causes: non-watertight inputs, scale mismatches, degenerate triangles, excessive complexity
- Always validate inputs before Boolean; implement offset-based manual fallback

### Clamshell Split Design
- Cut along natural plane (mid-forearm typically)
- Add registration pins (6mm Ø, 3mm long) at diagonal corners
- Carve magnet pockets (6mm Ø, 4mm deep) into split face
- Offset cut faces 1-2mm inward for mating ledge

### Internal Flex (Accordion Ribs)
- 6-8 vertical ribs in the knee band (50-80mm axial section)
- 1.5mm thick, 20mm tall, spaced 20-25mm apart
- Must be internal only — never disturb outer surface
- Print and physically test; don't trust simulation alone

### Common Failure Modes (Top 5)
1. Socket interface doesn't match residual limb anatomy
2. Wall thickness eroded by mesh operations (plan 0.5mm buffer)
3. Boolean operations fail with no fallback
4. Clamshell halves don't align (missing registration features)
5. Support material trapped in internal cavities

### Forearm Prototype Acceptance Criteria
- Cover fits snugly without gaps or pinching
- Clamshell snaps on/off cleanly 10+ times
- Survives 2+ hours of wear
- External surface smooth (no visible faceting)
- Minimum wall thickness ≥ 1.5mm everywhere

---

## Synthesized Strategy

### Phase 0: Forearm Prototype (Weeks 1-4)
**Goal:** Prove the pipeline works end-to-end on real anatomy.

**Capture Protocol:**
- 40-60 photos of Mike's forearm with iPad Pro camera
- Freehand, every 10-15° around the limb
- Multiple heights (wrist level, mid-forearm, elbow)
- Color calibration card in 5+ photos
- Consistent lighting (diffuse, no harsh shadows)

**Pipeline:**
```
Photos → COLMAP (SfM) → Dense reconstruction (Poisson) → Watertight mesh
  → [Optional: PyTorch3D silhouette refinement]
  → Mirror → Cavity Boolean (subtract dummy hardware)
  → Clamshell split + magnets → Validate → Export STL
```

**Success Criteria:**
- COLMAP reconstructs camera poses with <2px reprojection error
- Mesh is watertight and within ±3mm of reference scan
- Printed cover fits Mike's forearm
- Clamshell assembles/disassembles cleanly
- Pipeline completes with <2 hours manual intervention

### Phase 1: Refinement + Stage 2 (Weeks 5-8)
- Add differentiable rendering refinement (if COLMAP alone isn't accurate enough)
- Add sensor fusion (Structure Sensor as weak supervision)
- Implement full Stage 2: real hardware ingest, proper alignment, magnet pockets
- Iterate on the forearm prototype (v2, v3)

### Phase 2: Above-Knee + Flex Structures (Weeks 9-14)
- Scale pipeline to above-knee geometry
- Implement Stage 3: internal flex structures around knee
- Test on actual prosthetic hardware
- Prepare for first patient trial

### Phase 3: First Patient (Weeks 15-20)
- Full pipeline on real patient data
- Iterate based on clinical feedback
- Validate unit economics

---

## Open Questions for Mike
1. Do you have access to a Stratasys PolyJet printer, or will Stratasys print for you?
2. Can you get a separate scan of a residual limb (even a rough one) for socket interface validation?
3. Do the founders know about the 6-month timeline? Are they aligned?
4. Can you get paid? Even $500/week changes the sustainability equation.
5. Do you have a clinic partner lined up for the first patient trial?

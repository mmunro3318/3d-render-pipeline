
> Reviewed April 2026 | Repo: hyperreal-3d-render-pipeline

## Executive Summary

The codebase is **~20% implemented**. You have a solid foundation (ingest, preprocessing, segmentation) but the core value — turning photos into a 3D mesh — doesn't exist yet. There's a 200-page specification describing an unbuilt system.

**What works:** Polycam zip ingest, image preprocessing (resize + color correction), SAM2 segmentation, config validation, camera parsing.

**What's empty:** Geometry optimization (PyTorch3D), texture optimization, mirroring, QC, all of Stage 2 (cavity/mounting), all of Stage 3 (internal flex), API, workers.

**Code quality of what exists:** A-grade. Clean, typed, tested, well-documented.

**Shipping readiness:** F. Cannot run end-to-end on real data.

---

## Architecture (What's Built vs. Not)

```
src/
├── common/              ✅ COMPLETE — config, cameras, IO (solid)
├── stage1_visual_shell/
│   ├── ingest_polycam/  ✅ COMPLETE — Polycam zip → images + cameras
│   ├── preprocessing/   ✅ COMPLETE — resize + color correction
│   ├── segmentation/    ✅ COMPLETE — SAM2 wrapper + morphology
│   ├── optimization/    ❌ EMPTY — PyTorch3D mesh fitting (THE CORE)
│   ├── mirroring/       ❌ EMPTY — reflection transform
│   ├── texturing/       ❌ EMPTY — UV texture optimization
│   ├── qc/              ❌ EMPTY — quality checks
│   └── pipeline.py      ✅ Orchestrates ingest→preprocess→segment
├── stage2_cavity_mount/ ❌ 0% — all directories empty
├── stage3_internal_flex/ ❌ 0% — all directories empty
├── api/                 ❌ EMPTY
└── workers/             ❌ EMPTY
```

**Total production code:** ~1,750 lines
**Total documentation:** ~200 pages
**Ratio is inverted.** At pre-seed, you want 80% code, 20% docs.

---

## What's Good

1. **Clean separation of concerns** — Common utilities are independent, each stage is modular, data flows through Pydantic models
2. **Good testing habits** — Synthetic Polycam zip fixtures are thoughtful, mocked SAM2, seeded randomness
3. **Documentation culture** — PRD is comprehensive, architecture doc explains choices, INSIGHTS.md captures learnings
4. **Sensible tech choices** — Trimesh (geometry), Pydantic (config), SAM2 (segmentation)

---

## What's Wrong

### 1. Specification Theater
200 pages of beautiful specs describing features that don't exist. The specs are good — but they're not code. At this stage, a working demo on one real limb scan is worth more than perfect documentation.

### 2. The Hard Part Is Unbuilt
The optimization module (PyTorch3D mesh fitting) is the entire value proposition. Everything upstream (ingest, preprocess, segment) is setup. Everything downstream (mirroring, texturing, QC, Stage 2, Stage 3) depends on it. It's empty.

### 3. Missing Dependencies
- `torch` not in requirements.txt (SAM2 needs it)
- `pytorch3d` not in requirements.txt (optimization needs it)
- PyTorch3D has notoriously fragile CUDA version requirements

### 4. Silent Failures in Segmentation
If SAM2 fails on an image, it's skipped silently. For a medical device pipeline, "silently skip" is unacceptable. Needs explicit failure handling.

### 5. No End-to-End Runner
No script to run the full pipeline. Can't demonstrate value to anyone.

### 6. No Operational Readiness
No API, no job queue, no worker system. A clinician can't use this.

---

## Risk Assessment

| Component | Risk | Why |
|-----------|------|-----|
| PyTorch3D optimization | **CRITICAL** | Not implemented. Hardest technical piece. Convergence depends on initialization + loss weights + learning schedule. Will need extensive tuning. |
| PyTorch3D install | **HIGH** | Historically fragile. Requires exact Python + CUDA + PyTorch version alignment. |
| Texture optimization | **HIGH** | Not implemented. Photometric loss is finicky. |
| Boolean mesh ops (Stage 2) | **MEDIUM** | Trimesh + Manifold3D mitigates but non-watertight inputs still fail. |
| Color calibration | **LOW** | Grey-world correction is naive but adequate for MVP. |

---

## Tests

| Area | Tests | Quality |
|------|-------|---------|
| Common (config, cameras, IO) | ~15 | Solid |
| Stage 1 ingest | ~8 | Good (synthetic fixtures) |
| Stage 1 preprocessing | ~5 | Good |
| Stage 1 segmentation | ~6 | OK (mocked, needs negative cases) |
| Stage 1 optimization | 0 | — |
| Stage 2–3 | 0 | — |
| Integration/E2E | 0 | — |

---

## Timeline Estimate (One Engineer)

| Milestone | Weeks |
|-----------|-------|
| Stage 1 optimization (mesh fitting) | 2–3 |
| Mirroring | 0.5 |
| Texturing | 2 |
| QC + E2E runner | 1 |
| **Stage 1 MVP** | **6–8 weeks** |
| Stage 2 (cavity/mounting) | 4–6 |
| Stage 3 (internal flex) | 4–6 |
| API + workers | 3–4 |
| **Full MVP** | **~6 months** |

---

## Bottom Line

The foundation is solid but you're only 20% done. The entire bet rests on whether geometry optimization works. That module is empty. Everything else is setup or downstream.

**Priority #1:** Get one real limb scan through a working mesh optimization loop. Nothing else matters until that works.

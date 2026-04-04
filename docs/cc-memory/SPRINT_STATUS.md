# Sprint 1-2 Status

**Last updated:** 2026-04-02
**Branch:** feature/cold-start
**Conda env:** `hyperreal` (Python 3.12 — Open3D requires <=3.12)

## Completed
- [x] Sub-sprint 0: Tooling Sidequest
  - Created `docs/cc-memory/` directory + session onboarding template
  - Created conda `hyperreal` environment (Python 3.12)
  - COLMAP CLI: NOT YET INSTALLED (user action needed)
- [x] Sub-sprint 1: Foundation (32 tests passing)
  - `config/pipeline.yaml` — all hyperparameters + 2 limb profiles
  - `src/common/config.py` — Pydantic v2 loader (15 tests)
  - `src/common/mesh_utils.py` — validate, repair, export (17 tests)
  - `tests/conftest.py` — synthetic fixtures (cube, cylinder, sphere, open, zero-face)
- [x] Sub-sprint 2: COLMAP Integration (12 tests passing)
  - `src/stage1/colmap_runner.py` — CLI subprocess wrapper with quality gates
  - `tests/test_colmap.py` — fully mocked tests
- [x] Sub-sprint 3: Poisson + Pipeline (7 tests passing)
  - `src/stage1/poisson_mesh.py` — Open3D Poisson reconstruction
  - `scripts/run_stage1.py` — end-to-end orchestrator + metrics JSON
  - `tests/test_poisson.py` — synthetic point cloud tests

**Total: 51 tests, all passing.**

## Not Started (needs real data)
- Sub-sprint 4: Instrumentation (QC viewer, accuracy harness)
- Sub-sprint 5: Validator + Tests (capture_validator, golden mesh)

## Blockers for Next Steps
- **COLMAP CLI not installed on Windows** — needed for real data testing
  - Download from: https://colmap.github.io/install.html (Windows binary)
- **Real photo data** — user capturing with Polycam in parallel
- **PyTorch 2.7 + CUDA 12.8** — not yet installed (not needed until Sprint 6)

## Key Decisions Made
- Python 3.12 (not 3.14) — Open3D has no 3.13+ wheels
- COLMAP CLI is PRIMARY (not pycolmap) — pycolmap is CPU-only on Windows
- scipy added as dep — trimesh repair operations require it

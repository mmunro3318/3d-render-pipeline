# Session Onboarding Template

**Read this first in every new CC session.**

## Quick Context
- **Project:** HyperReal — photogrammetry pipeline for prosthetic covers
- **Repo:** `3d-render-pipeline-core/` on `feature/cold-start` branch
- **Plan:** `~/.claude/plans/merry-brewing-anchor.md` (Sprint 1-2 mega plan)
- **CLAUDE.md:** Root of repo — all code style rules, architecture, constraints

## Environment
- **Conda env:** `hyperreal` (Python 3.12, PyTorch 2.7 + CUDA 12.8) — Python 3.12 required (Open3D has no 3.13+/3.14 wheels)
- **Activate:** `conda activate hyperreal`
- **GPU:** RTX 5060 Ti (Blackwell, sm_120) — requires CUDA 12.8+
- **COLMAP:** CLI-primary architecture (pycolmap is CPU-only on Windows)

## Key Docs
- `docs/` — 10 planning/design docs
- `docs/cc-memory/` — AI persistent memory across sessions
- `CLAUDE.md` — Code style, architecture rules, print constraints
- `TESTING_GUIDELINES.md` — Test philosophy

## Current Sprint Status
Check the plan and git log for latest state:
```bash
git log --oneline -10
cat docs/cc-memory/SPRINT_STATUS.md  # if exists
```

## Sub-sprint Map (from plan)
0. Tooling Sidequest (setup)
1. Foundation (config, mesh_utils, tests)
2. COLMAP Integration (colmap_runner + mocked tests)
3. Poisson + Pipeline (poisson_mesh, run_stage1, metrics)
4. Instrumentation (QC viewer, accuracy harness)
5. Validator + Tests (capture_validator, golden mesh)

## Before You Code
1. Read CLAUDE.md (it overrides defaults)
2. `conda activate hyperreal`
3. Check git status and recent commits
4. Read this file + any SPRINT_STATUS.md
5. Check the plan for your sub-sprint scope

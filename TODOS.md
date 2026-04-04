# TODOS — HyperReal 3D Render Pipeline
> Maintained by CEO + Eng reviews. Items are deferred scope, not forgotten scope.

## Sprint 1 (deferred from CEO review 2026-04-04)

### P1 — Should do soon

- [ ] **Post-boolean output validation** — After any boolean succeeds in the fallback chain, run watertight + manifold check on result before declaring success. If fails, continue to next fallback. ~5 lines in `cavity_boolean.py`.
  - **Why:** manifold3d can "succeed" but produce degenerate geometry (thin slivers, self-intersections). Flagged independently by spec reviewer + Gemini-role.
  - **Effort:** S (CC: ~5 min)
  - **Depends on:** Session 1B (cavity_boolean.py must exist first)

- [ ] **Helpful config validation messages** — When bounding box check fails, suggest which limb profile might match. Need to figure out how to suggest the right profile for arbitrary limb types.
  - **Why:** Bounding box failures WILL be a bottleneck. Founder flagged this.
  - **Effort:** S (CC: ~15 min)
  - **Depends on:** Session 1A (validator must exist first)

- [ ] **Clarify input semantics: which limb is scanned?** — Mirror step assumes the SOUND (healthy, contralateral) limb is scanned and mirrored. Some docs say "residual limb scan." Clarify in `docs/input-contract.md` and ROADMAP.
  - **Why:** Ambiguity could lead to building mirror logic backwards. Codex flagged this.
  - **Effort:** S (CC: ~5 min)
  - **Depends on:** Nothing. Can do anytime.

### P2 — Nice to have

- [ ] **Stage timing in QC report** — `time.perf_counter()` around each stage, included in QC JSON. ~10 lines.
  - **Why:** Useful for profiling, not critical for Sprint 1.
  - **Effort:** S (CC: ~5 min)

- [ ] **Mesh diff summary per stage** — Log face count delta, vertex delta, bounding box change after each stage. ~15 lines in StageResult.
  - **Why:** Good debugging signal. Not load-bearing.
  - **Effort:** S (CC: ~5 min)

### P3 — Future

- [ ] **Output/debug/ cleanup automation** — Auto-delete stale debug OBJs from prior runs.
  - **Why:** output/debug/ will accumulate files over time.
  - **Effort:** S (CC: ~10 min)

- [ ] **Input overwrite guard** — Check if output path resolves to same parent as input mesh. Intelligent output naming should prevent this naturally.
  - **Why:** Edge case. Founder has backups. Low risk.
  - **Effort:** S (CC: ~3 lines)

## Sprint 2+ (from eng review)

- [ ] **Real wall thickness validation (ray-casting)** — Non-negotiable for patient-facing prints. Sprint 2 P1.
- [ ] **Alignment transform storage (4x4 matrix)** — Enable ICP comparison with manual alignment. Sprint 2.
- [ ] **Auto-scale detection** — Reference object or known anatomy dimensions. Sprint 2.
- [ ] **Tighten face count to 100K-300K as hard limits** — After validating on more patient data. Sprint 2.
- [ ] **OBJ export from Phase A** — Currently Phase A exports STL. OBJ preserves normals/UVs for texture pipeline. Future.
- [ ] **Partial seam (snap-fit clamshell)** — Replace full split with single-piece design. Future sprints.

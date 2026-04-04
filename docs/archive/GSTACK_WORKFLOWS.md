# GStack Skill Workflows — HyperReal Pipeline

> Quick reference for leveraging gstack skills across the project lifecycle.
> Not all skills are web-centric — this doc maps them to our CLI/pipeline context.

---

## Skill Inventory (Relevance to HyperReal)

| Skill | Purpose | Relevance | When |
|-------|---------|-----------|------|
| `/office-hours` | YC-style brainstorm + forcing questions | **HIGH** | Before any new sprint or major decision |
| `/plan-ceo-review` | Scope & ambition review | **HIGH** | After office-hours, before eng review |
| `/plan-eng-review` | Architecture lock-in | **HIGH** | Before writing code for a sprint |
| `/plan-design-review` | UI/UX plan critique | LOW | Only if we build a viewer/dashboard |
| `/design-consultation` | Design system creation | LOW | Only if we build UI |
| `/design-review` | Live site visual QA | LOW | Only if we build UI |
| `/design-shotgun` | Rapid design iteration | LOW | Only if we build UI |
| `/design-html` | HTML prototyping | LOW | Only if we build UI |
| `/review` | Pre-merge code review (structural safety) | **HIGH** | Before every merge to main |
| `/ship` | Full deploy pipeline (test, bump, PR) | **HIGH** | End of every sprint |
| `/document-release` | Sync docs post-ship | **HIGH** | After every /ship |
| `/qa` | Test + fix loop | **MEDIUM** | After feature implementation (adapted for CLI testing) |
| `/qa-only` | Report-only QA | **MEDIUM** | When you want a bug report without fixes |
| `/debug` | 4-phase root cause analysis | **HIGH** | COLMAP failures, mesh validation issues, Boolean ops |
| `/codex` | Adversarial second opinion | **HIGH** | Before major architectural commits |
| `/retro` | Weekly engineering retrospective | **HIGH** | End of each sprint (every 2 weeks) |
| `/browse` | Headless browser | **MEDIUM** | Research docs, verify PyPI packages, check COLMAP issues |
| `/freeze` | Restrict edits to one directory | **HIGH** | When debugging stage1 without touching stage2 |
| `/careful` | Destructive command warnings | **MEDIUM** | When working near data/ or output/ |
| `/guard` | Full safety (freeze + careful) | **MEDIUM** | Production pipeline runs |
| `/unfreeze` | Remove edit restrictions | LOW | After /freeze or /guard |
| `/setup-browser-cookies` | Import browser cookies | LOW | Only for authenticated web research |
| `/gstack-upgrade` | Update gstack | LOW | Periodic maintenance |
| `/learn` | Not yet implemented | — | — |
| `/autoplan` | Not yet implemented | — | — |
| `/cso` | Not yet implemented | — | — |

---

## Workflow Chains

### 1. Sprint Kickoff (use at the start of every sprint)

```
/office-hours          → Frame the sprint's goals, surface risks, get forcing questions answered
    ↓
/plan-ceo-review       → Challenge scope: are we building too much or too little?
    ↓
/plan-eng-review       → Lock architecture: file layout, interfaces, edge cases, test plan
    ↓
[optional] /codex      → Adversarial review of the architecture before writing code
    ↓
BEGIN IMPLEMENTATION
```

**When:** Start of Sprint 1-2, 3, 4, 5, etc.
**Why:** Prevents scope creep and architectural dead ends. The 30 minutes spent here saves hours of rework.

---

### 2. Feature Development Cycle (use during implementation)

```
/freeze src/stage1/    → Restrict edits to the module you're working on
    ↓
[write code]
    ↓
/debug                 → When something breaks (COLMAP, Poisson, mesh validation)
    ↓
[iterate until feature works]
    ↓
/unfreeze              → Widen scope for integration
```

**When:** During any focused implementation session.
**Why:** `/freeze` prevents accidental edits to unrelated modules. `/debug` enforces root-cause discipline instead of duct-taping.

---

### 3. Pre-Merge Review (use before every merge to main)

```
/review                → Structural safety audit (SQL injection N/A, but catches: bad error handling,
                         missing validation, config leaks, test gaps)
    ↓
[optional] /codex      → Second opinion on tricky code (mesh Booleans, COLMAP orchestration)
    ↓
/ship                  → Run tests, bump VERSION, update CHANGELOG, create PR
```

**When:** After completing a sprint's deliverables.
**Why:** `/review` catches structural issues that unit tests miss. `/ship` standardizes the release process.

---

### 4. Post-Ship Documentation (use after every /ship)

```
/document-release      → Sync README, CLAUDE.md, docs/ with what actually shipped
    ↓
/retro                 → Sprint retrospective: what shipped, what slipped, what to improve
```

**When:** Immediately after merging a sprint.
**Why:** CLAUDE.md says "Fight Drift." This workflow enforces it. `/retro` captures lessons while they're fresh.

---

### 5. Research & Troubleshooting (use as needed)

```
/browse                → Look up pycolmap docs, COLMAP GitHub issues, Open3D API reference,
                         trimesh examples, PyTorch3D tutorials
    ↓
/debug                 → Systematic root-cause analysis when pipeline stage fails
    ↓
/careful               → Enable when running destructive operations near data/ or output/
```

**When:** When stuck on a library issue, COLMAP failure, or mesh validation problem.
**Why:** `/browse` is faster than leaving the terminal. `/debug` prevents shotgun debugging.

---

### 6. Safety Mode (use for production pipeline runs)

```
/guard                 → Combines /freeze + /careful for maximum safety
    ↓
[run pipeline on real patient data]
    ↓
/unfreeze              → Return to normal mode
```

**When:** When running the full pipeline on real forearm photos (not test data).
**Why:** Protects `data/` and `output/` from accidental deletion. Restricts edits to avoid mid-run code changes.

---

## Full Sprint Lifecycle (All Chains Combined)

```
SPRINT START
  │
  ├─ /office-hours → /plan-ceo-review → /plan-eng-review → [/codex]
  │
  ├─ IMPLEMENT
  │    ├─ /freeze → [code] → /debug → [iterate] → /unfreeze
  │    ├─ /browse (research as needed)
  │    └─ /careful (when near data/)
  │
  ├─ SHIP
  │    ├─ /review → [/codex] → /ship
  │    └─ /document-release
  │
  └─ REFLECT
       └─ /retro
```

---

## Tips

- **`/office-hours` isn't just for new projects.** Use it at the start of each sprint to re-ground on goals and surface blockers. Feed it the sprint's deliverables from the project plan.
- **`/freeze` is your best friend for pipeline work.** When debugging `colmap_runner.py`, freeze to `src/stage1/` so nothing in `stage2/` or `common/` gets accidentally modified.
- **`/codex` before major architectural decisions.** Mesh Boolean strategy, COLMAP parameter tuning, PyTorch3D loss functions — get a second opinion before committing.
- **`/browse` for documentation.** Don't leave the terminal to look up trimesh API, Open3D functions, or COLMAP parameters. Use `/browse` to fetch docs inline.
- **`/retro` every sprint, not just at the end.** It tracks trends over time. Starting early gives you a baseline to measure against.

# HyperReal — 3D Render Pipeline Core

Photos of a residual limb → two print-ready STL files for a Stratasys PolyJet prosthetic cover.

**Status:** Active development — Sprint 1-2 (COLMAP + baseline mesh)

---

## How It Works

```
40-55 iPhone/iPad photos
  → COLMAP (camera poses + point cloud)
    → Poisson surface reconstruction (watertight mesh)
      → [Optional] PyTorch3D silhouette refinement
        → Mirror + cavity Boolean (hollow cover shell)
          → Clamshell split + magnet pockets
            → cover_top_final.stl + cover_bottom_final.stl
```

---

## Requirements

- Python 3.10+
- COLMAP binary (see [install](https://colmap.github.io/install.html)) — add to `PATH`
- CUDA 12.8+ and PyTorch 2.7+ (required for RTX 5060 Ti / Blackwell)
- Windows 11 (primary dev platform) or Linux

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

pip install trimesh numpy open3d pydantic pyyaml pillow opencv-python tqdm loguru pycolmap manifold3d
pip install torch==2.7.0 torchvision==0.19.0 --index-url https://download.pytorch.org/whl/cu128
```

Verify GPU:
```bash
python -c "import torch; print(torch.cuda.is_available(), torch.version.cuda)"
colmap -h
```

---

## Usage

**Stage 1: Photos → mesh**
```bash
python scripts/run_stage1.py --photos data/forearm_v1/ --output output/forearm_raw.stl
```

**Stage 2: Mesh → print-ready cover**
```bash
python scripts/run_stage2.py --mesh output/forearm_cleaned.stl --output output/
```

**Full pipeline (end to end)**
```bash
python scripts/run_full_pipeline.py --photos data/forearm_v1/ --output output/
```

Run tests:
```bash
pytest tests/ -v
```

**AI development (gstack skills):**
```bash
cd .claude/skills/gstack && ./setup
```
Required once after cloning to build the browser automation binaries used by Claude Code.

---

## Capture Protocol

Equipment: iPad Pro (main camera — not LiDAR), diffuse lighting, color calibration card.

```
Ring 1 — Wrist:      15-20 photos, ~20° apart, 30-40cm from limb
Ring 2 — Mid-forearm: 15-20 photos, ~20° apart
Ring 3 — Elbow:       10-15 photos, ~25° apart
Color card:           5 photos (include card in frame)

Total: 40-55 photos. Time: <10 minutes.
60% overlap between adjacent photos.
Keep limb still. Move the camera, not the limb.
```

See `docs/Pipeline Overview.md` for the full protocol.

---

## Output Files

| File | Description |
|------|-------------|
| `output/forearm_raw.stl` | First mesh, uncleaned |
| `output/forearm_cleaned.stl` | Watertight, repaired, decimated |
| `output/cover_shell.stl` | Mirrored outer shell |
| `output/cover_hollow.stl` | Shell with hardware cavity subtracted |
| `output/cover_top_final.stl` | Top clamshell half — send to printer |
| `output/cover_bottom_final.stl` | Bottom clamshell half — send to printer |

---

## Project Docs

| Doc | Contents |
|-----|----------|
| `CLAUDE.md` | AI developer guide — architecture, constraints, rules |
| `docs/Pipeline Overview.md` | Full pipeline spec + file-by-file sprint breakdown |
| `docs/Project Plan - Forearm Prototype.md` | Sprint plan, milestones, risk register |
| `docs/Boardroom Minutes - Strategy Session.md` | Architecture decisions + rationale |
| `docs/Implementation Guide - Sprint 1-2 (COLMAP + Mesh).md` | Sprint 1-2 implementation reference |
| `docs/Implementation Guide - Sprint 3-5 (Mesh Ops + Print Prep).md` | Sprint 3-5 reference |
| `docs/Implementation Guide - Sprint 6-8 (Refinement + Texture).md` | Sprint 6-8 reference |

---

## Sprint Status

| Sprint | Goal | Status |
|--------|------|--------|
| 1 | Environment + first photos | In progress |
| 2 | COLMAP + baseline mesh | Not started |
| 3 | Mesh cleanup + watertight validation | Not started |
| 4 | Mirror + cavity Boolean | Not started |
| 5 | Clamshell split + print prep | Not started |
| 6 | Differentiable refinement (optional) | Not started |
| 7 | Texture mapping | Not started |
| 8 | Second print + fit test | Not started |

Milestone: print-ready STLs after Sprint 5. Full forearm prototype after Sprint 8.

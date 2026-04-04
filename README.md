# HyperReal — 3D Render Pipeline Core

Structure Sensor scan of a residual limb → Blender cleanup → Python pipeline → two print-ready STL files (clamshell prosthetic cover halves) for Stratasys PolyJet printing.

**Status:** Sprint 1 in progress — Phase B pipeline (cleaned mesh → STLs)

---

## Two-Phase Architecture

| Phase | Tool | What happens |
|-------|------|--------------|
| **A** | Blender (manual/scripted) | Raw scan cleanup: artifact removal, hole-fill, segmentation, scale, alignment |
| **B** | Python pipeline (this repo) | Validated mesh → repair → mirror → boolean → split → magnets → 2x binary STL |

Phase A exports an OBJ meeting the **input contract**. Phase B consumes it and produces print-ready covers.

---

## Requirements

- Python 3.12
- Windows 11 (primary dev platform) or Linux
- No GPU required — pipeline is mesh ops only

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

pip install trimesh numpy open3d pydantic pyyaml pillow tqdm loguru manifold3d
pip install pytest pytest-cov  # dev
```

---

## Usage

**Mesh → print-ready cover halves:**
```bash
python scripts/run_mesh_to_cover.py --input limb.obj --hardware hardware.obj --config config/pipeline.yaml
```

**Run tests:**
```bash
pytest tests/ -v
```

**AI development (gstack skills):**
```bash
cd .claude/skills/gstack && ./setup
```
Required once after cloning to build the browser automation binaries used by Claude Code.

---

## Output Files

| File | Description |
|------|-------------|
| `output/cover_top_final.stl` | Top clamshell half — send to printer |
| `output/cover_bottom_final.stl` | Bottom clamshell half — send to printer |
| `output/qc_report.json` | Validation report (watertight, wall thickness, tri count) |

---

## Project Docs

| Doc | Contents |
|-----|----------|
| `CLAUDE.md` | AI developer guide — architecture, constraints, rules |
| `ROADMAP.md` | Sprint plan, key decisions, input contract spec |
| `TESTING_GUIDELINES.md` | Test philosophy and pytest patterns |
| `docs/THE_WHY.md` | Product vision and motivation |

---

## Sprint Status

| Sprint | Goal | Status |
|--------|------|--------|
| 1 | Phase B pipeline — cleaned mesh → two print-ready STLs | In progress |
| 2 | Input quality, auto-scale, ICP alignment | Not started |
| 3 | Robustness, second patient, generalization | Not started |

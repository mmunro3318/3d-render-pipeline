# Input Contract — Phase A → Phase B

A mesh entering Phase B (this Python pipeline) must satisfy all checks below. Phase A (Blender cleanup) is responsible for producing a mesh that meets this contract. The validator in `src/common/` enforces these checks at intake and produces a structured report.

## Required Properties

| Property | Requirement | Check Type | Failure Action |
|----------|-------------|------------|----------------|
| Format | OBJ (preferred) or STL | validated | REJECT |
| Loadable | trimesh can load without errors | validated | REJECT |
| Single component | One connected component (`mesh.split()` returns 1 body) | validated | REJECT |
| Watertight | `mesh.is_watertight == True` | validated (with auto-repair attempt) | REJECT if repair fails |
| Scale | Real-world millimeters. Longest bounding box axis: 200-500mm (`above_knee` profile) | validated | REJECT with suggestion |
| Orientation | Z-up: proximal = +Z, anterior = +Y. Matches Blender native Z-up | validated | REJECT |
| Triangle count | Hard limits: 10K-500K faces. Warning range: 100K-300K | validated (auto-decimate if >500K) | WARN or AUTO-FIX |
| Manifold | No self-intersections, consistent face winding | validated (via manifold3d) | REJECT if unfixable |
| Hardware aligned | Limb and hardware meshes share the same coordinate frame | manual (Sprint 1) | Founder responsibility |

## Validation Levels

- **validated**: Automated check with pass/fail result
- **stub**: Check exists but returns a placeholder (e.g., wall thickness)
- **skipped**: Check not implemented yet
- **manual**: Human responsibility, not checked by pipeline

## Coordinate Convention

Z-up system matching Blender native:
- +Z = proximal (toward body)
- -Z = distal (toward extremity)
- +Y = anterior (front)
- -Y = posterior (back)
- +X = lateral (right side, patient perspective)
- -X = medial (left side / midline)

## Validation Report

The validator outputs a JSON report with per-check results:

```json
{
  "input_file": "limb.obj",
  "timestamp": "2026-04-04T12:00:00Z",
  "overall": "PASS",
  "checks": [
    {
      "name": "format",
      "status": "PASS",
      "validation_level": "validated",
      "detail": "OBJ loaded successfully"
    },
    {
      "name": "watertight",
      "status": "AUTO-FIXED",
      "validation_level": "validated",
      "detail": "Repaired: filled 3 holes"
    }
  ]
}
```

Status values: `PASS`, `AUTO-FIXED`, `WARN`, `FAIL`, `SKIP`

## Known Limitations (Sprint 1)

- Wall thickness is a STUB (always passes, logged as stub)
- Hardware alignment is MANUAL (not checked)
- Scale validation uses bounding box heuristic, not anatomical landmarks
- Orientation check uses simple axis-length heuristic (longest axis should be Z)

## Version History

| Version | Date | Change |
|---------|------|--------|
| 1.0 | 2026-04-04 | Initial contract from eng review |

"""Input contract validator for the HyperReal mesh processing pipeline.

Validates that a mesh from Phase A (Blender cleanup) meets the input contract
before entering Phase B (Python pipeline). Produces a structured JSON report
with per-check status.

Check sequence: format -> loadable -> single component -> watertight (with repair)
-> scale -> orientation -> triangle count (with decimate) -> manifold

Standalone CLI: python -m src.intake.validator mesh.obj
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

import numpy as np
import trimesh
from loguru import logger

from src.common.config import LimbProfile, PipelineConfig, load_config
from src.common.mesh_utils import repair_mesh, validate_mesh
from src.common.types import StageResult


# ---------------------------------------------------------------------------
# Status enum and report types
# ---------------------------------------------------------------------------

class CheckStatus(str, Enum):
    """Status of a single validation check."""

    PASS = "PASS"
    AUTO_FIXED = "AUTO-FIXED"
    WARN = "WARN"
    FAIL = "FAIL"
    SKIP = "SKIP"


class ValidationLevel(str, Enum):
    """How the check was performed."""

    VALIDATED = "validated"
    STUB = "stub"
    SKIPPED = "skipped"
    MANUAL = "manual"


def _check_result(
    name: str,
    status: CheckStatus,
    validation_level: ValidationLevel,
    detail: str,
) -> dict:
    """Build a single check result dict."""
    return {
        "name": name,
        "status": status.value,
        "validation_level": validation_level.value,
        "detail": detail,
    }


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def _check_format(mesh_path: Path, supported_formats: list[str]) -> dict:
    """Check that file extension is a supported mesh format."""
    ext = mesh_path.suffix.lstrip(".").lower()
    if ext in supported_formats:
        return _check_result(
            "format", CheckStatus.PASS, ValidationLevel.VALIDATED,
            f"{ext.upper()} is a supported format",
        )
    return _check_result(
        "format", CheckStatus.FAIL, ValidationLevel.VALIDATED,
        f"Unsupported format '{ext}'. Supported: {supported_formats}",
    )


def _check_loadable(mesh_path: Path) -> tuple[dict, trimesh.Trimesh | None]:
    """Attempt to load the mesh file. Returns (check_result, mesh_or_None)."""
    try:
        mesh = trimesh.load(str(mesh_path), force="mesh")
        if mesh.faces.shape[0] == 0:
            return (
                _check_result(
                    "loadable", CheckStatus.FAIL, ValidationLevel.VALIDATED,
                    "File loaded but contains zero faces",
                ),
                None,
            )
        return (
            _check_result(
                "loadable", CheckStatus.PASS, ValidationLevel.VALIDATED,
                f"Loaded {len(mesh.faces)} faces, {len(mesh.vertices)} vertices",
            ),
            mesh,
        )
    except Exception as exc:
        return (
            _check_result(
                "loadable", CheckStatus.FAIL, ValidationLevel.VALIDATED,
                f"Failed to load: {exc}",
            ),
            None,
        )


def _check_single_component(mesh: trimesh.Trimesh) -> tuple[dict, trimesh.Trimesh]:
    """Check mesh has exactly one connected component.

    Returns the original mesh unchanged (filtering fragments is Phase A's job).
    """
    components = mesh.split(only_watertight=False)
    n_components = len(components)

    if n_components == 1:
        return (
            _check_result(
                "single_component", CheckStatus.PASS, ValidationLevel.VALIDATED,
                "Mesh is a single connected component",
            ),
            mesh,
        )

    if n_components == 0:
        return (
            _check_result(
                "single_component", CheckStatus.FAIL, ValidationLevel.VALIDATED,
                "No connected components found (degenerate mesh)",
            ),
            mesh,
        )

    # Report component breakdown
    face_counts = sorted([len(c.faces) for c in components], reverse=True)
    return (
        _check_result(
            "single_component", CheckStatus.FAIL, ValidationLevel.VALIDATED,
            f"{n_components} components found. "
            f"Largest: {face_counts[0]} faces, total: {sum(face_counts)} faces. "
            f"Top 5: {face_counts[:5]}",
        ),
        mesh,
    )


def _check_watertight(
    mesh: trimesh.Trimesh,
) -> tuple[dict, trimesh.Trimesh]:
    """Check watertight status. Attempts repair if not watertight."""
    if mesh.is_watertight:
        return (
            _check_result(
                "watertight", CheckStatus.PASS, ValidationLevel.VALIDATED,
                "Mesh is watertight",
            ),
            mesh,
        )

    logger.info("Mesh is not watertight, attempting repair...")
    repaired = repair_mesh(mesh)

    if repaired.is_watertight:
        return (
            _check_result(
                "watertight", CheckStatus.AUTO_FIXED, ValidationLevel.VALIDATED,
                f"Repaired to watertight (faces: {len(mesh.faces)} -> {len(repaired.faces)})",
            ),
            repaired,
        )

    boundary_count = _count_boundary_edges(repaired)
    return (
        _check_result(
            "watertight", CheckStatus.FAIL, ValidationLevel.VALIDATED,
            f"Not watertight after repair. {boundary_count} boundary edges remain",
        ),
        repaired,
    )


def _count_boundary_edges(mesh: trimesh.Trimesh) -> int:
    """Count boundary (open) edges in a mesh."""
    edges_sorted = np.sort(mesh.edges, axis=1)
    from trimesh.grouping import group_rows
    return len(group_rows(edges_sorted, require_count=1))


def _check_scale(
    mesh: trimesh.Trimesh,
    profile: LimbProfile,
) -> tuple[dict, trimesh.Trimesh]:
    """Check bounding box scale is in expected mm range.

    Detects meters-scale meshes (Blender OBJ default) and auto-converts to mm.
    """
    bb = mesh.bounding_box.extents
    longest = float(np.max(bb))
    expected_min, expected_max = profile.expected_length_mm

    # Check if already in mm range
    if expected_min <= longest <= expected_max:
        return (
            _check_result(
                "scale", CheckStatus.PASS, ValidationLevel.VALIDATED,
                f"Longest axis: {longest:.1f}mm (expected {expected_min}-{expected_max}mm)",
            ),
            mesh,
        )

    # Detect meters (1000x too small) — Blender OBJ exports in meters
    longest_as_mm = longest * 1000.0
    if expected_min <= longest_as_mm <= expected_max:
        logger.info("Detected meters-scale mesh, converting to mm (x1000)")
        scaled = mesh.copy()
        scaled.apply_scale(1000.0)
        return (
            _check_result(
                "scale", CheckStatus.AUTO_FIXED, ValidationLevel.VALIDATED,
                f"Scaled from meters to mm (longest axis: {longest:.4f}m -> {longest_as_mm:.1f}mm)",
            ),
            scaled,
        )

    return (
        _check_result(
            "scale", CheckStatus.FAIL, ValidationLevel.VALIDATED,
            f"Longest axis: {longest:.2f} (expected {expected_min}-{expected_max}mm). "
            f"Try profile '{profile.limb_type}' or check export units.",
        ),
        mesh,
    )


def _check_orientation(mesh: trimesh.Trimesh) -> tuple[dict, trimesh.Trimesh]:
    """Check Z-up orientation. Auto-fix Y-up (Blender OBJ convention) to Z-up.

    Convention: +Z=proximal, +Y=anterior. Longest axis should be Z.
    Blender OBJ exports Y-up, so longest axis is Y -> need Y-to-Z swap.
    """
    bb = mesh.bounding_box.extents
    longest_axis = int(np.argmax(bb))

    if longest_axis == 2:  # Z is longest -> Z-up
        return (
            _check_result(
                "orientation", CheckStatus.PASS, ValidationLevel.VALIDATED,
                f"Z-up confirmed (longest axis is Z: {bb[2]:.1f})",
            ),
            mesh,
        )

    if longest_axis == 1:  # Y is longest -> likely Y-up from Blender OBJ
        logger.info("Detected Y-up orientation, swapping Y<->Z for Z-up convention")
        rotated = mesh.copy()
        # Rotate -90 degrees around X axis: Y->Z, Z->-Y
        rotation = trimesh.transformations.rotation_matrix(
            -np.pi / 2, [1, 0, 0], point=[0, 0, 0],
        )
        rotated.apply_transform(rotation)
        new_bb = rotated.bounding_box.extents
        return (
            _check_result(
                "orientation", CheckStatus.AUTO_FIXED, ValidationLevel.VALIDATED,
                f"Rotated Y-up to Z-up (X:{new_bb[0]:.1f}, Y:{new_bb[1]:.1f}, Z:{new_bb[2]:.1f})",
            ),
            rotated,
        )

    # X is longest — unusual, reject
    return (
        _check_result(
            "orientation", CheckStatus.FAIL, ValidationLevel.VALIDATED,
            f"Longest axis is X ({bb[0]:.1f}), expected Z. Check mesh alignment.",
        ),
        mesh,
    )


def _check_triangle_count(
    mesh: trimesh.Trimesh,
    intake_config: "IntakeConfig",
) -> tuple[dict, trimesh.Trimesh]:
    """Check face count is within limits. Auto-decimate if over max."""
    from src.common.config import IntakeConfig

    n_faces = len(mesh.faces)

    if n_faces < intake_config.min_faces:
        return (
            _check_result(
                "triangle_count", CheckStatus.FAIL, ValidationLevel.VALIDATED,
                f"Too few faces: {n_faces} (minimum {intake_config.min_faces})",
            ),
            mesh,
        )

    if n_faces > intake_config.max_faces:
        logger.info(
            "Face count {} exceeds max {}, decimating...",
            n_faces, intake_config.max_faces,
        )
        target_ratio = intake_config.max_faces / n_faces
        decimated = mesh.simplify_quadric_decimation(intake_config.max_faces)
        return (
            _check_result(
                "triangle_count", CheckStatus.AUTO_FIXED, ValidationLevel.VALIDATED,
                f"Decimated from {n_faces} to {len(decimated.faces)} faces "
                f"(max {intake_config.max_faces})",
            ),
            decimated,
        )

    # Within limits — check warning thresholds
    warnings = []
    if n_faces > intake_config.warn_faces_high:
        warnings.append(f"high ({n_faces} > {intake_config.warn_faces_high})")
    if n_faces < intake_config.warn_faces_low:
        warnings.append(f"low ({n_faces} < {intake_config.warn_faces_low})")

    if warnings:
        return (
            _check_result(
                "triangle_count", CheckStatus.WARN, ValidationLevel.VALIDATED,
                f"Face count {n_faces} is within limits but {', '.join(warnings)}",
            ),
            mesh,
        )

    return (
        _check_result(
            "triangle_count", CheckStatus.PASS, ValidationLevel.VALIDATED,
            f"Face count: {n_faces} (range {intake_config.min_faces}-{intake_config.max_faces})",
        ),
        mesh,
    )


def _check_manifold(mesh: trimesh.Trimesh) -> dict:
    """Check for self-intersections via manifold3d."""
    try:
        import manifold3d

        manifold = manifold3d.Manifold(
            mesh=manifold3d.Mesh(
                vert_properties=np.array(mesh.vertices, dtype=np.float32),
                tri_verts=np.array(mesh.faces, dtype=np.uint32),
            ),
        )
        status = manifold.status()
        if status == manifold3d.Error.NoError:
            return _check_result(
                "manifold", CheckStatus.PASS, ValidationLevel.VALIDATED,
                "Manifold check passed (no self-intersections)",
            )
        return _check_result(
            "manifold", CheckStatus.FAIL, ValidationLevel.VALIDATED,
            f"Manifold check failed: {status}",
        )
    except Exception as exc:
        return _check_result(
            "manifold", CheckStatus.FAIL, ValidationLevel.VALIDATED,
            f"Manifold check error: {exc}",
        )


def _check_wall_thickness() -> dict:
    """Wall thickness stub — always passes, logged as stub."""
    return _check_result(
        "wall_thickness", CheckStatus.SKIP, ValidationLevel.STUB,
        "Wall thickness check not implemented (Sprint 2 — ray-casting needed)",
    )


# ---------------------------------------------------------------------------
# Main validator
# ---------------------------------------------------------------------------

def validate_contract(
    mesh_path: Path,
    config: PipelineConfig,
) -> tuple[dict, trimesh.Trimesh | None]:
    """Run the full input contract validation sequence.

    Returns (report_dict, validated_mesh_or_None). The mesh may have been
    modified by AUTO-FIX steps (scale, orientation, decimation, repair).
    """
    profile = config.limb_profiles[config.active_profile]
    checks: list[dict] = []
    mesh: trimesh.Trimesh | None = None

    # --- format ---
    fmt_check = _check_format(mesh_path, config.intake.supported_formats)
    checks.append(fmt_check)
    if fmt_check["status"] == CheckStatus.FAIL.value:
        return _build_report(mesh_path, checks), None

    # --- loadable ---
    load_check, mesh = _check_loadable(mesh_path)
    checks.append(load_check)
    if mesh is None:
        return _build_report(mesh_path, checks), None

    # --- single component ---
    comp_check, mesh = _check_single_component(mesh)
    checks.append(comp_check)
    # Don't early-return on FAIL — continue checking to give full report

    # --- watertight (with repair attempt) ---
    water_check, mesh = _check_watertight(mesh)
    checks.append(water_check)

    # --- scale ---
    scale_check, mesh = _check_scale(mesh, profile)
    checks.append(scale_check)

    # --- orientation ---
    orient_check, mesh = _check_orientation(mesh)
    checks.append(orient_check)

    # --- triangle count ---
    tri_check, mesh = _check_triangle_count(mesh, config.intake)
    checks.append(tri_check)

    # --- manifold (self-intersections) ---
    manifold_check = _check_manifold(mesh)
    checks.append(manifold_check)

    # --- wall thickness (stub) ---
    checks.append(_check_wall_thickness())

    report = _build_report(mesh_path, checks)

    # Log summary
    overall = report["overall"]
    logger.info("Contract validation complete: {}", overall)
    for c in checks:
        level = "SUCCESS" if c["status"] in ("PASS", "AUTO-FIXED") else c["status"]
        log_fn = logger.success if level == "SUCCESS" else (
            logger.warning if level in ("WARN", "SKIP") else logger.error
        )
        log_fn("  [{}] {} — {}", c["status"], c["name"], c["detail"])

    return report, mesh if overall != "FAIL" else None


def _build_report(mesh_path: Path, checks: list[dict]) -> dict:
    """Build the contract validation report dict."""
    statuses = [c["status"] for c in checks]

    if CheckStatus.FAIL.value in statuses:
        overall = "FAIL"
    elif CheckStatus.WARN.value in statuses or CheckStatus.AUTO_FIXED.value in statuses:
        overall = "WARN"
    else:
        overall = "PASS"

    return {
        "input_file": str(mesh_path.name),
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "overall": overall,
        "checks": checks,
    }


def validate_and_wrap(
    mesh_path: Path,
    config: PipelineConfig,
) -> StageResult:
    """Run contract validation and wrap result in a StageResult."""
    report, mesh = validate_contract(mesh_path, config)

    warnings = [
        c["detail"]
        for c in report["checks"]
        if c["status"] in (CheckStatus.WARN.value, CheckStatus.SKIP.value)
    ]

    if mesh is None:
        mesh = trimesh.Trimesh()

    return StageResult(
        mesh=mesh,
        report_dict=report,
        warnings=warnings,
        stage_name="intake_validator",
    )


# ---------------------------------------------------------------------------
# Standalone CLI
# ---------------------------------------------------------------------------

def _cli_main() -> None:
    """CLI entry point: python -m src.intake.validator <mesh_path> [--config path]."""
    if len(sys.argv) < 2:
        print("Usage: python -m src.intake.validator <mesh.obj> [--config pipeline.yaml]")
        sys.exit(1)

    mesh_path = Path(sys.argv[1])
    config_path = Path("config/pipeline.yaml")

    if "--config" in sys.argv:
        idx = sys.argv.index("--config")
        if idx + 1 < len(sys.argv):
            config_path = Path(sys.argv[idx + 1])

    if not mesh_path.exists():
        logger.error("Mesh file not found: {}", mesh_path)
        sys.exit(1)

    config = load_config(config_path)
    report, mesh = validate_contract(mesh_path, config)

    print(json.dumps(report, indent=2))

    if report["overall"] == "FAIL":
        sys.exit(1)


if __name__ == "__main__":
    _cli_main()

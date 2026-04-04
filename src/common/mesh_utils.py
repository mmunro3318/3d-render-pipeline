"""Mesh validation, repair, and export utilities for the HyperReal pipeline."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import trimesh
from loguru import logger


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class MeshValidationError(Exception):
    """Raised when a mesh has fatal issues that prevent further processing."""


class MeshValidationWarning(UserWarning):
    """Issued when a mesh has non-fatal issues worth noting."""


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_mesh(mesh: trimesh.Trimesh) -> dict:
    """Return validation report: {is_watertight, face_count, vertex_count, has_normals, extent_mm}."""
    if mesh.faces.shape[0] == 0:
        raise MeshValidationError("Mesh has zero faces — cannot validate.")

    extent_mm = mesh.bounding_box.extents.tolist()
    report = {
        "is_watertight": bool(mesh.is_watertight),
        "face_count": int(mesh.faces.shape[0]),
        "vertex_count": int(mesh.vertices.shape[0]),
        "has_normals": mesh.face_normals is not None and len(mesh.face_normals) > 0,
        "extent_mm": extent_mm,
    }

    logger.info(
        "Mesh validation — watertight={}, faces={}, vertices={}, extent={}",
        report["is_watertight"],
        report["face_count"],
        report["vertex_count"],
        [f"{e:.1f}" for e in report["extent_mm"]],
    )

    if not report["is_watertight"]:
        logger.warning("Mesh is NOT watertight — output will fail print constraints.")

    return report


# ---------------------------------------------------------------------------
# Repair
# ---------------------------------------------------------------------------

def repair_mesh(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    """Attempt to repair non-watertight mesh. Returns repaired copy."""
    repaired = mesh.copy()

    logger.info("Starting mesh repair (faces={}, vertices={})", len(repaired.faces), len(repaired.vertices))

    # Remove duplicate vertices
    repaired.merge_vertices()
    # Remove degenerate (zero-area) faces via boolean mask
    nondegenerate_mask = repaired.nondegenerate_faces()
    if not nondegenerate_mask.all():
        repaired.update_faces(nondegenerate_mask)
        logger.info("Removed {} degenerate faces", (~nondegenerate_mask).sum())
    # Remove unreferenced vertices
    repaired.remove_unreferenced_vertices()
    # Fix face winding / normals
    repaired.fix_normals()
    # Fill holes to attempt watertight closure
    trimesh.repair.fill_holes(repaired)
    # Fix inverted faces
    trimesh.repair.fix_inversion(repaired)
    # Fix winding for consistent normals
    trimesh.repair.fix_winding(repaired)

    if repaired.is_watertight:
        logger.success("Mesh repair succeeded — mesh is now watertight.")
    else:
        logger.warning("Mesh repair completed but mesh is still NOT watertight.")

    return repaired


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------

def _ensure_parent_directory(output_path: Path) -> None:
    """Ensure the parent directory of output_path exists, raise if it cannot."""
    parent = output_path.parent
    if not parent.exists():
        raise FileNotFoundError(
            f"Parent directory does not exist: {parent}"
        )


def export_stl(mesh: trimesh.Trimesh, output_path: Path) -> None:
    """Export binary STL. Raises MeshValidationError if mesh has zero faces."""
    if mesh.faces.shape[0] == 0:
        raise MeshValidationError("Cannot export mesh with zero faces to STL.")

    _ensure_parent_directory(output_path)

    mesh.export(str(output_path), file_type="stl")
    logger.success("Exported binary STL → {}", output_path)


def export_ply(mesh: trimesh.Trimesh, output_path: Path) -> None:
    """Export PLY with vertex colors if available."""
    if mesh.faces.shape[0] == 0:
        raise MeshValidationError("Cannot export mesh with zero faces to PLY.")

    _ensure_parent_directory(output_path)

    mesh.export(str(output_path), file_type="ply")
    logger.success("Exported PLY → {}", output_path)


def export_obj(mesh: trimesh.Trimesh, output_path: Path) -> None:
    """Export OBJ with vertex colors if available."""
    if mesh.faces.shape[0] == 0:
        raise MeshValidationError("Cannot export mesh with zero faces to OBJ.")

    _ensure_parent_directory(output_path)

    mesh.export(str(output_path), file_type="obj")
    logger.success("Exported OBJ → {}", output_path)

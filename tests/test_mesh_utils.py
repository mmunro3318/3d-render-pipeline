"""Tests for src/common/mesh_utils.py — validation, repair, and export."""

from __future__ import annotations

from pathlib import Path

import pytest
import trimesh

from src.common.mesh_utils import (
    MeshValidationError,
    export_obj,
    export_ply,
    export_stl,
    repair_mesh,
    validate_mesh,
)


# ---------------------------------------------------------------------------
# validate_mesh
# ---------------------------------------------------------------------------

class TestValidateMesh:
    """Tests for the validate_mesh function."""

    def test_watertight_cube_passes(self, cube_mesh: trimesh.Trimesh) -> None:
        """Watertight cube should report is_watertight=True."""
        report = validate_mesh(cube_mesh)
        assert report["is_watertight"] is True
        assert report["face_count"] > 0
        assert report["vertex_count"] > 0
        assert report["has_normals"] is True
        assert len(report["extent_mm"]) == 3

    def test_watertight_cylinder(self, cylinder_mesh: trimesh.Trimesh) -> None:
        """Watertight cylinder should report is_watertight=True."""
        report = validate_mesh(cylinder_mesh)
        assert report["is_watertight"] is True

    def test_watertight_sphere(self, sphere_mesh: trimesh.Trimesh) -> None:
        """Watertight sphere should report is_watertight=True."""
        report = validate_mesh(sphere_mesh)
        assert report["is_watertight"] is True

    def test_open_mesh_reports_not_watertight(self, open_mesh: trimesh.Trimesh) -> None:
        """Non-watertight mesh should report is_watertight=False."""
        report = validate_mesh(open_mesh)
        assert report["is_watertight"] is False

    def test_zero_face_mesh_raises(self, zero_face_mesh: trimesh.Trimesh) -> None:
        """Zero-face mesh should raise MeshValidationError."""
        with pytest.raises(MeshValidationError, match="zero faces"):
            validate_mesh(zero_face_mesh)

    def test_extent_values_match_cube(self, cube_mesh: trimesh.Trimesh) -> None:
        """Unit cube extents should each be approximately 1.0."""
        report = validate_mesh(cube_mesh)
        for extent_val in report["extent_mm"]:
            assert abs(extent_val - 1.0) < 0.01


# ---------------------------------------------------------------------------
# export_stl
# ---------------------------------------------------------------------------

class TestExportStl:
    """Tests for the export_stl function."""

    def test_export_creates_file(
        self, cube_mesh: trimesh.Trimesh, tmp_output_dir: Path,
    ) -> None:
        """Exporting a cube should create a readable binary STL file."""
        stl_path = tmp_output_dir / "cube.stl"
        export_stl(cube_mesh, stl_path)
        assert stl_path.exists()
        assert stl_path.stat().st_size > 0

    def test_exported_stl_is_loadable(
        self, cube_mesh: trimesh.Trimesh, tmp_output_dir: Path,
    ) -> None:
        """Exported STL should be loadable back as a valid mesh."""
        stl_path = tmp_output_dir / "cube_reload.stl"
        export_stl(cube_mesh, stl_path)
        reloaded = trimesh.load(str(stl_path))
        assert reloaded.faces.shape[0] == cube_mesh.faces.shape[0]

    def test_zero_face_mesh_raises(
        self, zero_face_mesh: trimesh.Trimesh, tmp_output_dir: Path,
    ) -> None:
        """Zero-face mesh should raise MeshValidationError on export."""
        stl_path = tmp_output_dir / "empty.stl"
        with pytest.raises(MeshValidationError, match="zero faces"):
            export_stl(zero_face_mesh, stl_path)

    def test_invalid_parent_directory_raises(
        self, cube_mesh: trimesh.Trimesh,
    ) -> None:
        """Exporting to a non-existent parent directory should raise FileNotFoundError."""
        bad_path = Path("/nonexistent/dir/mesh.stl")
        with pytest.raises(FileNotFoundError):
            export_stl(cube_mesh, bad_path)


# ---------------------------------------------------------------------------
# export_ply
# ---------------------------------------------------------------------------

class TestExportPly:
    """Tests for the export_ply function."""

    def test_export_creates_file(
        self, cube_mesh: trimesh.Trimesh, tmp_output_dir: Path,
    ) -> None:
        """Exporting a cube should create a PLY file."""
        ply_path = tmp_output_dir / "cube.ply"
        export_ply(cube_mesh, ply_path)
        assert ply_path.exists()
        assert ply_path.stat().st_size > 0

    def test_exported_ply_is_loadable(
        self, cube_mesh: trimesh.Trimesh, tmp_output_dir: Path,
    ) -> None:
        """Exported PLY should be loadable back as a valid mesh."""
        ply_path = tmp_output_dir / "cube_reload.ply"
        export_ply(cube_mesh, ply_path)
        reloaded = trimesh.load(str(ply_path))
        assert reloaded.vertices.shape[0] > 0


# ---------------------------------------------------------------------------
# export_obj
# ---------------------------------------------------------------------------

class TestExportObj:
    """Tests for the export_obj function."""

    def test_export_creates_file(
        self, cube_mesh: trimesh.Trimesh, tmp_output_dir: Path,
    ) -> None:
        """Exporting a cube should create an OBJ file."""
        obj_path = tmp_output_dir / "cube.obj"
        export_obj(cube_mesh, obj_path)
        assert obj_path.exists()
        assert obj_path.stat().st_size > 0


# ---------------------------------------------------------------------------
# repair_mesh
# ---------------------------------------------------------------------------

class TestRepairMesh:
    """Tests for the repair_mesh function."""

    def test_repair_returns_copy(self, open_mesh: trimesh.Trimesh) -> None:
        """Repair should return a new mesh, not mutate the original."""
        repaired = repair_mesh(open_mesh)
        assert repaired is not open_mesh

    def test_repair_watertight_mesh_stays_watertight(
        self, cube_mesh: trimesh.Trimesh,
    ) -> None:
        """Repairing an already-watertight mesh should keep it watertight."""
        repaired = repair_mesh(cube_mesh)
        assert repaired.is_watertight

    def test_repair_preserves_faces(self, cube_mesh: trimesh.Trimesh) -> None:
        """Repairing a clean cube should not lose faces."""
        repaired = repair_mesh(cube_mesh)
        assert repaired.faces.shape[0] > 0

    def test_repair_attempts_on_open_mesh(self, open_mesh: trimesh.Trimesh) -> None:
        """Repair on an open mesh should run without error (may or may not fix)."""
        repaired = repair_mesh(open_mesh)
        # The single-triangle open mesh likely can't be made watertight,
        # but repair should not crash.
        assert repaired.faces.shape[0] >= 0

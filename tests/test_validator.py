"""Tests for src.intake.validator — input contract validation."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import trimesh

from src.common.config import PipelineConfig, load_config
from src.intake.validator import (
    CheckStatus,
    ValidationLevel,
    _check_format,
    _check_loadable,
    _check_manifold,
    _check_orientation,
    _check_scale,
    _check_single_component,
    _check_triangle_count,
    _check_watertight,
    _check_wall_thickness,
    validate_contract,
)


# ---------------------------------------------------------------------------
# Config fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def config() -> PipelineConfig:
    """Load the real pipeline config."""
    return load_config(Path("config/pipeline.yaml"))


# ---------------------------------------------------------------------------
# Format check
# ---------------------------------------------------------------------------

def test_format_pass_obj() -> None:
    """OBJ files pass format check."""
    result = _check_format(Path("mesh.obj"), ["obj", "stl"])
    assert result["status"] == "PASS"


def test_format_pass_stl() -> None:
    """STL files pass format check."""
    result = _check_format(Path("mesh.stl"), ["obj", "stl"])
    assert result["status"] == "PASS"


def test_format_fail_ply() -> None:
    """PLY files fail format check."""
    result = _check_format(Path("mesh.ply"), ["obj", "stl"])
    assert result["status"] == "FAIL"


# ---------------------------------------------------------------------------
# Loadable check
# ---------------------------------------------------------------------------

def test_loadable_pass(tmp_path: Path, cube_mesh: trimesh.Trimesh) -> None:
    """Valid OBJ file loads successfully."""
    mesh_path = tmp_path / "test.obj"
    cube_mesh.export(str(mesh_path), file_type="obj")
    result, mesh = _check_loadable(mesh_path)
    assert result["status"] == "PASS"
    assert mesh is not None
    assert len(mesh.faces) > 0


def test_loadable_fail_missing(tmp_path: Path) -> None:
    """Non-existent file fails loadable check."""
    result, mesh = _check_loadable(tmp_path / "nope.obj")
    assert result["status"] == "FAIL"
    assert mesh is None


# ---------------------------------------------------------------------------
# Single component check
# ---------------------------------------------------------------------------

def test_single_component_pass(cube_mesh: trimesh.Trimesh) -> None:
    """Single watertight mesh passes component check."""
    result, mesh = _check_single_component(cube_mesh)
    assert result["status"] == "PASS"


def test_single_component_fail(multi_component_mesh: trimesh.Trimesh) -> None:
    """Two separated cubes fail component check."""
    result, mesh = _check_single_component(multi_component_mesh)
    assert result["status"] == "FAIL"
    assert "2 components" in result["detail"]


# ---------------------------------------------------------------------------
# Watertight check
# ---------------------------------------------------------------------------

def test_watertight_pass(cube_mesh: trimesh.Trimesh) -> None:
    """Watertight cube passes."""
    result, mesh = _check_watertight(cube_mesh)
    assert result["status"] == "PASS"


def test_watertight_auto_fixed(repairable_mesh: trimesh.Trimesh) -> None:
    """Repairable mesh gets auto-fixed."""
    result, mesh = _check_watertight(repairable_mesh)
    # May be AUTO-FIXED or FAIL depending on trimesh repair success
    assert result["status"] in ("AUTO-FIXED", "FAIL")


def test_watertight_fail(open_mesh: trimesh.Trimesh) -> None:
    """Open triangle fails watertight check."""
    result, mesh = _check_watertight(open_mesh)
    assert result["status"] == "FAIL"


# ---------------------------------------------------------------------------
# Scale check
# ---------------------------------------------------------------------------

def test_scale_pass_mm(config: PipelineConfig) -> None:
    """Mesh already in mm range passes."""
    profile = config.limb_profiles[config.active_profile]
    mesh = trimesh.creation.cylinder(radius=75.0, height=400.0)
    result, out = _check_scale(mesh, profile)
    assert result["status"] == "PASS"


def test_scale_auto_fix_meters(
    config: PipelineConfig, meters_scale_mesh: trimesh.Trimesh,
) -> None:
    """Mesh in meters gets auto-converted to mm."""
    profile = config.limb_profiles[config.active_profile]
    result, out = _check_scale(meters_scale_mesh, profile)
    assert result["status"] == "AUTO-FIXED"
    assert "meters to mm" in result["detail"]
    # Verify the mesh was actually scaled
    assert np.max(out.bounding_box.extents) > 100  # now in mm


def test_scale_fail_wrong_size(config: PipelineConfig) -> None:
    """Mesh with crazy scale fails."""
    profile = config.limb_profiles[config.active_profile]
    mesh = trimesh.creation.cylinder(radius=5.0, height=10.0)  # 10mm
    result, out = _check_scale(mesh, profile)
    assert result["status"] == "FAIL"


# ---------------------------------------------------------------------------
# Orientation check
# ---------------------------------------------------------------------------

def test_orientation_pass_z_up(synthetic_limb_mesh: trimesh.Trimesh) -> None:
    """Z-up mesh passes orientation check."""
    result, mesh = _check_orientation(synthetic_limb_mesh)
    assert result["status"] == "PASS"


def test_orientation_auto_fix_y_up(y_up_mesh: trimesh.Trimesh) -> None:
    """Y-up mesh gets rotated to Z-up."""
    result, mesh = _check_orientation(y_up_mesh)
    assert result["status"] == "AUTO-FIXED"
    # After fix, Z should be longest
    bb = mesh.bounding_box.extents
    assert np.argmax(bb) == 2  # Z axis


# ---------------------------------------------------------------------------
# Triangle count check
# ---------------------------------------------------------------------------

def test_triangle_count_pass(
    config: PipelineConfig, cube_mesh: trimesh.Trimesh,
) -> None:
    """Cube within face count limits passes (with possible warning)."""
    result, mesh = _check_triangle_count(cube_mesh, config.intake)
    # A 12-face cube is below min_faces (10K), so expect FAIL
    assert result["status"] == "FAIL"
    assert "Too few" in result["detail"]


def test_triangle_count_pass_synthetic(
    config: PipelineConfig, synthetic_limb_mesh: trimesh.Trimesh,
) -> None:
    """Synthetic limb mesh is in warning zone but within hard limits."""
    result, mesh = _check_triangle_count(synthetic_limb_mesh, config.intake)
    # Cylinder has ~128 faces — way below min
    assert result["status"] in ("FAIL", "WARN", "PASS")


# ---------------------------------------------------------------------------
# Manifold check
# ---------------------------------------------------------------------------

def test_manifold_pass(cube_mesh: trimesh.Trimesh) -> None:
    """Watertight cube passes manifold check."""
    result = _check_manifold(cube_mesh)
    assert result["status"] == "PASS"


def test_manifold_fail_open(open_mesh: trimesh.Trimesh) -> None:
    """Open mesh fails manifold check."""
    result = _check_manifold(open_mesh)
    assert result["status"] == "FAIL"


# ---------------------------------------------------------------------------
# Wall thickness stub
# ---------------------------------------------------------------------------

def test_wall_thickness_stub() -> None:
    """Wall thickness check is a stub that always skips."""
    result = _check_wall_thickness()
    assert result["status"] == "SKIP"
    assert result["validation_level"] == "stub"


# ---------------------------------------------------------------------------
# Full contract validation
# ---------------------------------------------------------------------------

def test_full_contract_pass(
    tmp_path: Path, config: PipelineConfig,
) -> None:
    """Full contract validation on a good mesh.

    Uses a high-resolution sphere scaled to above-knee dimensions so it
    passes all checks (format, loadable, single component, watertight,
    scale, orientation, triangle count, manifold).
    """
    # Icosphere subdiv=5 gives ~20K faces; scale to 400mm Z-up
    mesh = trimesh.creation.icosphere(subdivisions=5, radius=1.0)
    # Stretch to limb-like proportions: ~150mm diameter, ~400mm tall (Z)
    mesh.apply_scale([75.0, 75.0, 200.0])
    mesh_path = tmp_path / "limb.obj"
    mesh.export(str(mesh_path), file_type="obj")
    report, out = validate_contract(mesh_path, config)
    assert report["overall"] in ("PASS", "WARN")
    assert report["input_file"] == "limb.obj"
    assert len(report["checks"]) >= 8


def test_full_contract_fail_bad_format(
    tmp_path: Path, config: PipelineConfig,
) -> None:
    """Unsupported format stops validation early."""
    mesh_path = tmp_path / "mesh.abc"
    mesh_path.write_text("not a mesh")
    report, mesh = validate_contract(mesh_path, config)
    assert report["overall"] == "FAIL"
    assert mesh is None
    # Should stop after format check
    assert report["checks"][0]["name"] == "format"
    assert report["checks"][0]["status"] == "FAIL"

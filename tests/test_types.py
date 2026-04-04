"""Tests for src.common.types — StageResult dataclass."""

from __future__ import annotations

import trimesh

from src.common.types import StageResult


def test_stage_result_creation(cube_mesh: trimesh.Trimesh) -> None:
    """StageResult can be created with all fields."""
    result = StageResult(
        mesh=cube_mesh,
        report_dict={"status": "PASS"},
        warnings=["test warning"],
        stage_name="test_stage",
    )
    assert result.mesh is cube_mesh
    assert result.report_dict == {"status": "PASS"}
    assert result.warnings == ["test warning"]
    assert result.stage_name == "test_stage"


def test_stage_result_defaults(cube_mesh: trimesh.Trimesh) -> None:
    """StageResult has sensible defaults for optional fields."""
    result = StageResult(mesh=cube_mesh, report_dict={})
    assert result.warnings == []
    assert result.stage_name == ""


def test_stage_result_warnings_are_independent() -> None:
    """Each StageResult gets its own warnings list (no shared mutable default)."""
    mesh = trimesh.creation.box()
    r1 = StageResult(mesh=mesh, report_dict={})
    r2 = StageResult(mesh=mesh, report_dict={})
    r1.warnings.append("only r1")
    assert r2.warnings == []

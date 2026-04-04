"""Shared pytest fixtures using synthetic geometry for mesh utility tests."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import trimesh


@pytest.fixture()
def cube_mesh() -> trimesh.Trimesh:
    """A watertight unit cube centered at origin."""
    return trimesh.creation.box(extents=(1.0, 1.0, 1.0))


@pytest.fixture()
def cylinder_mesh() -> trimesh.Trimesh:
    """A watertight cylinder (radius=0.5, height=2.0)."""
    return trimesh.creation.cylinder(radius=0.5, height=2.0)


@pytest.fixture()
def sphere_mesh() -> trimesh.Trimesh:
    """A watertight UV sphere (radius=1.0)."""
    return trimesh.creation.icosphere(radius=1.0)


@pytest.fixture()
def open_mesh() -> trimesh.Trimesh:
    """A non-watertight mesh — a single triangle (open surface)."""
    vertices = np.array([
        [0.0, 0.0, 0.0],
        [1.0, 0.0, 0.0],
        [0.5, 1.0, 0.0],
    ])
    faces = np.array([[0, 1, 2]])
    return trimesh.Trimesh(vertices=vertices, faces=faces)


@pytest.fixture()
def zero_face_mesh() -> trimesh.Trimesh:
    """A mesh with vertices but zero faces."""
    vertices = np.array([
        [0.0, 0.0, 0.0],
        [1.0, 0.0, 0.0],
        [0.5, 1.0, 0.0],
    ])
    return trimesh.Trimesh(vertices=vertices, faces=[])


@pytest.fixture()
def tmp_output_dir(tmp_path: Path) -> Path:
    """A temporary directory for export tests."""
    output_dir = tmp_path / "mesh_output"
    output_dir.mkdir()
    return output_dir

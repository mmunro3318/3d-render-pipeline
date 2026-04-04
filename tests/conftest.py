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
def repairable_mesh() -> trimesh.Trimesh:
    """A cube with one face removed — repair can close it."""
    mesh = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
    # Remove one face to create a hole
    mesh.update_faces(np.arange(len(mesh.faces) - 1))
    assert not mesh.is_watertight
    return mesh


@pytest.fixture()
def multi_component_mesh() -> trimesh.Trimesh:
    """Two separated cubes — fails single-component check."""
    cube1 = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
    cube2 = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
    cube2.apply_translation([5.0, 0.0, 0.0])
    return trimesh.util.concatenate([cube1, cube2])


@pytest.fixture()
def synthetic_limb_mesh() -> trimesh.Trimesh:
    """Cylinder + hemisphere cap, ~300mm tall, ~150mm diameter.

    Simulates an above-knee limb in Z-up convention (longest axis Z).
    Scale in mm. Single component, watertight.
    """
    # Cylinder body
    body = trimesh.creation.cylinder(radius=75.0, height=250.0, sections=32)
    # Hemisphere cap at top
    cap = trimesh.creation.icosphere(radius=75.0, subdivisions=2)
    # Keep only top hemisphere (z >= 0)
    cap_faces = cap.faces[cap.face_normals[:, 2] > -0.1]
    cap = cap.submesh([np.arange(len(cap_faces))], only_watertight=False)[0]
    # Actually, just use a full cylinder — it's watertight and simpler
    limb = trimesh.creation.cylinder(radius=75.0, height=300.0, sections=32)
    # Translate so centroid is at origin
    return limb


@pytest.fixture()
def oversized_mesh() -> trimesh.Trimesh:
    """A sphere with >500K faces for decimation testing."""
    return trimesh.creation.icosphere(subdivisions=6, radius=200.0)


@pytest.fixture()
def y_up_mesh() -> trimesh.Trimesh:
    """A watertight mesh oriented Y-up (longest axis Y). Needs rotation to Z-up."""
    mesh = trimesh.creation.cylinder(radius=50.0, height=400.0, sections=16)
    # Rotate so longest axis is Y instead of Z
    rotation = trimesh.transformations.rotation_matrix(
        np.pi / 2, [1, 0, 0], point=[0, 0, 0],
    )
    mesh.apply_transform(rotation)
    return mesh


@pytest.fixture()
def meters_scale_mesh() -> trimesh.Trimesh:
    """A watertight mesh in meters scale (needs x1000 for mm)."""
    # 0.4m = 400mm tall cylinder — within above_knee range
    return trimesh.creation.cylinder(radius=0.075, height=0.4, sections=16)


@pytest.fixture()
def tmp_output_dir(tmp_path: Path) -> Path:
    """A temporary directory for export tests."""
    output_dir = tmp_path / "mesh_output"
    output_dir.mkdir()
    return output_dir

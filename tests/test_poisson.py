"""Tests for Poisson surface reconstruction using synthetic point clouds."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import open3d as o3d
import pytest

from src.common.config import (
    CaptureConfig,
    ColmapConfig,
    PipelineConfig,
    PoissonConfig,
    LimbProfile,
)
from src.stage1.poisson_mesh import MeshResult, reconstruct


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(depth: int = 8, min_density_percentile: float = 0.01) -> PipelineConfig:
    """Builds a minimal PipelineConfig for Poisson tests."""
    return PipelineConfig(
        capture=CaptureConfig(
            min_images=40,
            max_images=55,
            min_laplacian_variance=100.0,
            min_resolution=(3024, 4032),
            min_features_per_image=500,
            min_pairwise_matches=50,
        ),
        colmap=ColmapConfig(
            camera_model="PINHOLE",
            max_reprojection_error=2.0,
            min_registered_ratio=0.8,
            min_3d_points=1000,
        ),
        poisson=PoissonConfig(
            depth=depth,
            min_density_percentile=min_density_percentile,
        ),
        colmap_binary=Path("colmap"),
        active_profile="forearm",
        limb_profiles={
            "forearm": LimbProfile(
                limb_type="forearm",
                expected_length_mm=(200, 350),
                expected_diameter_mm=(60, 120),
                split_plane_axis="sagittal",
                wall_thickness_target_mm=2.0,
                wall_thickness_min_mm=1.5,
                magnet_pocket_diameter_mm=6.0,
                magnet_pocket_depth_mm=3.0,
                cavity_clearance_mm=1.0,
            ),
        },
    )


def _write_sphere_cloud(
    path: Path,
    num_points: int = 5000,
    *,
    include_normals: bool = True,
) -> None:
    """Creates a synthetic sphere point cloud PLY at *path*."""
    # Sample points uniformly on a unit sphere
    rng = np.random.default_rng(42)
    phi = rng.uniform(0, 2 * np.pi, num_points)
    cos_theta = rng.uniform(-1, 1, num_points)
    theta = np.arccos(cos_theta)

    x = np.sin(theta) * np.cos(phi)
    y = np.sin(theta) * np.sin(phi)
    z = np.cos(theta)
    points = np.column_stack([x, y, z])

    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points)

    if include_normals:
        # For a unit sphere the outward normal equals the point coordinate
        pcd.normals = o3d.utility.Vector3dVector(points)

    o3d.io.write_point_cloud(str(path), pcd)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestReconstructHappyPath:
    """Poisson reconstruction on a dense sphere cloud."""

    def test_returns_mesh_result(self, tmp_path: Path) -> None:
        """Dense sphere cloud reconstructs into a MeshResult with expected fields."""
        ply = tmp_path / "sphere.ply"
        _write_sphere_cloud(ply, num_points=5000, include_normals=True)
        config = _make_config(depth=6)

        result = reconstruct(ply, config)

        assert isinstance(result, MeshResult)
        assert result.vertex_count > 0
        assert result.face_count > 0
        assert result.density_filtered is True

    def test_watertight(self, tmp_path: Path) -> None:
        """Dense sphere with no density filtering yields a watertight mesh."""
        ply = tmp_path / "sphere.ply"
        _write_sphere_cloud(ply, num_points=10000, include_normals=True)
        # Disable density filtering (percentile=0) to preserve watertightness
        config = _make_config(depth=6, min_density_percentile=0.0)

        result = reconstruct(ply, config)

        assert result.is_watertight is True
        assert result.density_filtered is False

    def test_mesh_has_geometry(self, tmp_path: Path) -> None:
        """Returned trimesh has non-degenerate vertices and faces."""
        ply = tmp_path / "sphere.ply"
        _write_sphere_cloud(ply, num_points=5000, include_normals=True)
        config = _make_config(depth=6)

        result = reconstruct(ply, config)

        assert result.mesh.vertices.shape[1] == 3
        assert result.mesh.faces.shape[1] == 3


class TestSparseCloud:
    """Reconstruction from a minimal but valid point cloud."""

    def test_sparse_produces_mesh(self, tmp_path: Path) -> None:
        """A cloud with few points still produces a mesh (may not be watertight)."""
        ply = tmp_path / "sparse.ply"
        _write_sphere_cloud(ply, num_points=200, include_normals=True)
        config = _make_config(depth=4)

        result = reconstruct(ply, config)

        assert isinstance(result, MeshResult)
        assert result.vertex_count > 0
        assert result.face_count > 0


class TestNoNormals:
    """Point cloud without precomputed normals."""

    def test_estimates_normals_automatically(self, tmp_path: Path) -> None:
        """Cloud without normals should have normals estimated and still reconstruct."""
        ply = tmp_path / "no_normals.ply"
        _write_sphere_cloud(ply, num_points=3000, include_normals=False)
        config = _make_config(depth=6)

        result = reconstruct(ply, config)

        assert isinstance(result, MeshResult)
        assert result.vertex_count > 0
        assert result.face_count > 0


class TestErrorHandling:
    """Edge cases and expected failures."""

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        """Non-existent PLY file raises FileNotFoundError."""
        missing = tmp_path / "does_not_exist.ply"
        config = _make_config()

        with pytest.raises(FileNotFoundError):
            reconstruct(missing, config)

    def test_too_few_points_raises(self, tmp_path: Path) -> None:
        """Point cloud with < 100 points raises ValueError."""
        ply = tmp_path / "tiny.ply"
        _write_sphere_cloud(ply, num_points=50, include_normals=True)
        config = _make_config()

        with pytest.raises(ValueError, match="too few points"):
            reconstruct(ply, config)

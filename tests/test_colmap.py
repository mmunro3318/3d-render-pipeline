"""Fully mocked tests for COLMAP CLI subprocess wrapper."""

from __future__ import annotations

import struct
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.common.config import ColmapConfig, PipelineConfig
from src.stage1.colmap_runner import (
    DenseResult,
    SparseResult,
    _count_images,
    run_dense,
    run_sparse,
    verify_colmap_installation,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def pipeline_config() -> PipelineConfig:
    """Minimal PipelineConfig for COLMAP tests."""
    return PipelineConfig(
        capture={
            "min_images": 40,
            "max_images": 55,
            "min_laplacian_variance": 100.0,
            "min_resolution": [3024, 4032],
            "min_features_per_image": 500,
            "min_pairwise_matches": 50,
        },
        colmap=ColmapConfig(
            camera_model="PINHOLE",
            max_reprojection_error=2.0,
            min_registered_ratio=0.8,
            min_3d_points=1000,
        ),
        poisson={"depth": 9, "min_density_percentile": 0.01},
        limb_profiles={
            "forearm": {
                "limb_type": "forearm",
                "expected_length_mm": [200, 350],
                "expected_diameter_mm": [60, 120],
                "split_plane_axis": "sagittal",
                "wall_thickness_target_mm": 2.0,
                "wall_thickness_min_mm": 1.5,
                "magnet_pocket_diameter_mm": 6.0,
                "magnet_pocket_depth_mm": 3.0,
                "cavity_clearance_mm": 1.0,
            },
        },
        active_profile="forearm",
        colmap_binary=Path("colmap"),
    )


@pytest.fixture()
def image_dir(tmp_path: Path) -> Path:
    """A temp directory with mock image files."""
    img_dir = tmp_path / "images"
    img_dir.mkdir()
    for i in range(50):
        (img_dir / f"photo_{i:03d}.jpg").touch()
    return img_dir


@pytest.fixture()
def empty_image_dir(tmp_path: Path) -> Path:
    """A temp directory with no images."""
    img_dir = tmp_path / "empty_images"
    img_dir.mkdir()
    return img_dir


def _write_mock_colmap_binary_model(
    model_dir: Path,
    num_cameras: int = 1,
    num_images: int = 45,
    num_points: int = 5000,
    mean_error: float = 0.8,
) -> None:
    """Write minimal COLMAP binary model files for testing."""
    model_dir.mkdir(parents=True, exist_ok=True)

    # cameras.bin — 1 PINHOLE camera (model_id=1, 4 params)
    with (model_dir / "cameras.bin").open("wb") as f:
        f.write(struct.pack("<Q", num_cameras))
        for cam_id in range(1, num_cameras + 1):
            f.write(struct.pack("<I", cam_id))       # camera_id
            f.write(struct.pack("<i", 1))             # model_id (PINHOLE)
            f.write(struct.pack("<Q", 4032))          # width
            f.write(struct.pack("<Q", 3024))          # height
            # 4 params for PINHOLE: fx, fy, cx, cy
            f.write(struct.pack("<4d", 3000.0, 3000.0, 2016.0, 1512.0))

    # images.bin — just the count header
    with (model_dir / "images.bin").open("wb") as f:
        f.write(struct.pack("<Q", num_images))

    # points3D.bin — num_points with given mean error
    with (model_dir / "points3D.bin").open("wb") as f:
        f.write(struct.pack("<Q", num_points))
        for i in range(num_points):
            f.write(struct.pack("<Q", i + 1))               # point3D_id
            f.write(struct.pack("<3d", 0.0, 0.0, 0.0))      # xyz
            f.write(struct.pack("<3B", 128, 128, 128))       # rgb
            f.write(struct.pack("<d", mean_error))            # error
            f.write(struct.pack("<Q", 0))                     # track_length=0


# ---------------------------------------------------------------------------
# verify_colmap_installation
# ---------------------------------------------------------------------------

class TestVerifyColmapInstallation:
    """Tests for verify_colmap_installation."""

    @patch("src.stage1.colmap_runner.shutil.which")
    def test_colmap_found(
        self,
        mock_which: MagicMock,
        pipeline_config: PipelineConfig,
    ) -> None:
        """When COLMAP is on PATH, verify passes without error."""
        mock_which.return_value = "/usr/local/bin/colmap"
        verify_colmap_installation(pipeline_config)
        mock_which.assert_called_once_with("colmap")

    @patch("src.stage1.colmap_runner.shutil.which")
    def test_colmap_not_found(
        self,
        mock_which: MagicMock,
        pipeline_config: PipelineConfig,
    ) -> None:
        """When COLMAP is not on PATH, raises FileNotFoundError with install URL."""
        mock_which.return_value = None
        with pytest.raises(FileNotFoundError, match="colmap.github.io/install"):
            verify_colmap_installation(pipeline_config)


# ---------------------------------------------------------------------------
# run_sparse
# ---------------------------------------------------------------------------

class TestRunSparse:
    """Tests for run_sparse."""

    @patch("src.stage1.colmap_runner.subprocess.run")
    def test_happy_path(
        self,
        mock_run: MagicMock,
        pipeline_config: PipelineConfig,
        image_dir: Path,
        tmp_path: Path,
    ) -> None:
        """Successful sparse reconstruction returns SparseResult(success=True)."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # Mock subprocess to succeed
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        # Pre-create mock COLMAP binary output
        model_dir = workspace / "sparse" / "0"
        _write_mock_colmap_binary_model(
            model_dir,
            num_images=45,
            num_points=5000,
            mean_error=0.8,
        )

        result = run_sparse(image_dir, workspace, pipeline_config)

        assert isinstance(result, SparseResult)
        assert result.success is True
        assert result.num_registered == 45
        assert result.num_points == 5000
        assert result.reprojection_error == pytest.approx(0.8, abs=0.01)
        assert result.workspace == workspace
        assert len(result.cameras) == 1
        assert mock_run.call_count == 3  # feature_extractor, matcher, mapper

    @patch("src.stage1.colmap_runner.subprocess.run")
    def test_low_registration_ratio(
        self,
        mock_run: MagicMock,
        pipeline_config: PipelineConfig,
        image_dir: Path,
        tmp_path: Path,
    ) -> None:
        """<80% registered images yields success=False with registration diagnostic."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        # Only 30 registered out of 50 images = 60% < 80%
        model_dir = workspace / "sparse" / "0"
        _write_mock_colmap_binary_model(model_dir, num_images=30, num_points=5000, mean_error=0.8)

        result = run_sparse(image_dir, workspace, pipeline_config)

        assert result.success is False
        assert "registration" in result.diagnostics.lower() or "registered" in result.diagnostics.lower()

    @patch("src.stage1.colmap_runner.subprocess.run")
    def test_too_few_points(
        self,
        mock_run: MagicMock,
        pipeline_config: PipelineConfig,
        image_dir: Path,
        tmp_path: Path,
    ) -> None:
        """<1000 3D points yields success=False."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        model_dir = workspace / "sparse" / "0"
        _write_mock_colmap_binary_model(model_dir, num_images=45, num_points=500, mean_error=0.8)

        result = run_sparse(image_dir, workspace, pipeline_config)

        assert result.success is False
        assert "500" in result.diagnostics or "points" in result.diagnostics.lower()

    @patch("src.stage1.colmap_runner.subprocess.run")
    def test_high_reprojection_error(
        self,
        mock_run: MagicMock,
        pipeline_config: PipelineConfig,
        image_dir: Path,
        tmp_path: Path,
    ) -> None:
        """Reprojection error >2px yields success=False."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        model_dir = workspace / "sparse" / "0"
        _write_mock_colmap_binary_model(model_dir, num_images=45, num_points=5000, mean_error=3.5)

        result = run_sparse(image_dir, workspace, pipeline_config)

        assert result.success is False
        assert "reprojection" in result.diagnostics.lower()

    @patch("src.stage1.colmap_runner.subprocess.run")
    def test_subprocess_crash(
        self,
        mock_run: MagicMock,
        pipeline_config: PipelineConfig,
        image_dir: Path,
        tmp_path: Path,
    ) -> None:
        """COLMAP subprocess crash raises RuntimeError with stderr."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Segmentation fault",
        )

        with pytest.raises(RuntimeError, match="Segmentation fault"):
            run_sparse(image_dir, workspace, pipeline_config)

    def test_empty_image_dir(
        self,
        pipeline_config: PipelineConfig,
        empty_image_dir: Path,
        tmp_path: Path,
    ) -> None:
        """Empty image directory raises ValueError."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        with pytest.raises(ValueError, match="No valid images"):
            run_sparse(empty_image_dir, workspace, pipeline_config)

    def test_nonexistent_image_dir(
        self,
        pipeline_config: PipelineConfig,
        tmp_path: Path,
    ) -> None:
        """Nonexistent image directory raises ValueError."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        fake_dir = tmp_path / "does_not_exist"

        with pytest.raises(ValueError, match="does not exist"):
            run_sparse(fake_dir, workspace, pipeline_config)


# ---------------------------------------------------------------------------
# run_dense
# ---------------------------------------------------------------------------

class TestRunDense:
    """Tests for run_dense."""

    @patch("src.stage1.colmap_runner.trimesh")
    @patch("src.stage1.colmap_runner.subprocess.run")
    def test_happy_path(
        self,
        mock_run: MagicMock,
        mock_trimesh: MagicMock,
        pipeline_config: PipelineConfig,
        tmp_path: Path,
    ) -> None:
        """Successful dense reconstruction returns DenseResult with PLY path."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        sparse_dir = workspace / "sparse" / "0"
        sparse_dir.mkdir(parents=True)
        dense_dir = workspace / "dense"
        dense_dir.mkdir(parents=True)

        # Subprocess succeeds
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        # The PLY file needs to exist after fusion
        fused_ply = dense_dir / "fused.ply"
        fused_ply.touch()

        # Mock trimesh.load to return a point cloud
        mock_cloud = MagicMock()
        mock_vertices = np.array([
            [0.0, 0.0, 0.0],
            [10.0, 20.0, 30.0],
            [5.0, 5.0, 5.0],
        ])
        mock_cloud.vertices = mock_vertices
        mock_trimesh.load.return_value = mock_cloud

        # Create images dir expected by run_dense
        images_dir = workspace / "images"
        images_dir.mkdir()

        result = run_dense(workspace, pipeline_config)

        assert isinstance(result, DenseResult)
        assert result.point_cloud_path == fused_ply
        assert result.num_points == 3
        np.testing.assert_array_equal(result.bounding_box[0], np.array([0.0, 0.0, 0.0]))
        np.testing.assert_array_equal(result.bounding_box[1], np.array([10.0, 20.0, 30.0]))
        assert mock_run.call_count == 3  # undistorter, patch_match, fusion


# ---------------------------------------------------------------------------
# _count_images
# ---------------------------------------------------------------------------

class TestCountImages:
    """Tests for the _count_images helper."""

    def test_counts_valid_extensions(self, tmp_path: Path) -> None:
        """Counts only jpg/jpeg/png files."""
        img_dir = tmp_path / "imgs"
        img_dir.mkdir()
        (img_dir / "a.jpg").touch()
        (img_dir / "b.jpeg").touch()
        (img_dir / "c.png").touch()
        (img_dir / "d.txt").touch()
        (img_dir / "e.bmp").touch()

        assert _count_images(img_dir) == 3

    def test_empty_dir(self, tmp_path: Path) -> None:
        """Returns 0 for an empty directory."""
        img_dir = tmp_path / "empty"
        img_dir.mkdir()
        assert _count_images(img_dir) == 0

"""COLMAP CLI subprocess wrapper for sparse and dense reconstruction."""

from __future__ import annotations

import shutil
import struct
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import trimesh
from loguru import logger

from src.common.config import PipelineConfig

# Valid image extensions for COLMAP input
_IMAGE_EXTENSIONS: frozenset[str] = frozenset({".jpg", ".jpeg", ".png"})


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class SparseResult:
    """Result of COLMAP sparse reconstruction."""

    workspace: Path
    num_registered: int
    num_points: int
    reprojection_error: float
    cameras: dict  # camera intrinsics
    success: bool
    diagnostics: str  # human-readable failure reason if !success


@dataclass
class DenseResult:
    """Result of COLMAP dense reconstruction."""

    point_cloud_path: Path  # PLY file
    num_points: int
    bounding_box: tuple[np.ndarray, np.ndarray]  # (min_xyz, max_xyz)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _count_images(image_dir: Path) -> int:
    """Counts valid image files (jpg/jpeg/png) in *image_dir*."""
    return sum(
        1 for f in image_dir.iterdir()
        if f.is_file() and f.suffix.lower() in _IMAGE_EXTENSIONS
    )


def _run_colmap_command(
    args: list[str],
    config: PipelineConfig,
) -> subprocess.CompletedProcess:
    """Runs a COLMAP CLI command via subprocess with error handling and logging."""
    cmd = [str(config.colmap_binary)] + args
    logger.info("Running COLMAP: {}", " ".join(cmd))

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        logger.error("COLMAP failed (exit {}): {}", result.returncode, result.stderr)
        msg = (
            f"COLMAP command failed (exit {result.returncode}): "
            f"{' '.join(cmd)}\nstderr: {result.stderr}"
        )
        raise RuntimeError(msg)

    logger.debug("COLMAP stdout: {}", result.stdout[:500] if result.stdout else "(empty)")
    return result


def _read_colmap_cameras_binary(cameras_bin: Path) -> dict:
    """Reads COLMAP cameras.bin and returns dict of camera_id -> intrinsics."""
    cameras: dict = {}
    with cameras_bin.open("rb") as f:
        num_cameras = struct.unpack("<Q", f.read(8))[0]
        for _ in range(num_cameras):
            camera_id = struct.unpack("<I", f.read(4))[0]
            model_id = struct.unpack("<i", f.read(4))[0]
            width = struct.unpack("<Q", f.read(8))[0]
            height = struct.unpack("<Q", f.read(8))[0]
            # Number of params per model (common ones)
            num_params_map = {0: 3, 1: 4, 2: 4, 3: 5, 4: 4, 5: 5}
            num_params = num_params_map.get(model_id, 4)
            params = struct.unpack(f"<{num_params}d", f.read(8 * num_params))
            cameras[camera_id] = {
                "model_id": model_id,
                "width": width,
                "height": height,
                "params": list(params),
            }
    return cameras


def _read_colmap_images_binary(images_bin: Path) -> int:
    """Reads COLMAP images.bin and returns the number of registered images."""
    with images_bin.open("rb") as f:
        num_images = struct.unpack("<Q", f.read(8))[0]
        # Skip rest — we only need the count
    return num_images


def _read_colmap_points3d_binary(points3d_bin: Path) -> tuple[int, float]:
    """Reads COLMAP points3D.bin, returns (num_points, mean_reprojection_error)."""
    total_error = 0.0
    with points3d_bin.open("rb") as f:
        num_points = struct.unpack("<Q", f.read(8))[0]
        for _ in range(num_points):
            # point3D_id(Q) + xyz(3d) + rgb(3B) + error(d)
            _point3d_id = struct.unpack("<Q", f.read(8))[0]
            _xyz = struct.unpack("<3d", f.read(24))
            _rgb = struct.unpack("<3B", f.read(3))
            error = struct.unpack("<d", f.read(8))[0]
            total_error += error
            # track_length(Q) + track entries (each: image_id(I) + point2D_idx(I))
            track_length = struct.unpack("<Q", f.read(8))[0]
            f.read(track_length * 8)  # skip track data

    mean_error = total_error / num_points if num_points > 0 else 0.0
    return num_points, mean_error


def _read_sparse_model(
    sparse_dir: Path,
) -> tuple[int, int, float, dict]:
    """Reads COLMAP binary model files, returns (num_registered, num_points, reproj_error, cameras)."""
    cameras_bin = sparse_dir / "cameras.bin"
    images_bin = sparse_dir / "images.bin"
    points3d_bin = sparse_dir / "points3D.bin"

    for required_file in (cameras_bin, images_bin, points3d_bin):
        if not required_file.exists():
            msg = f"COLMAP model file missing: {required_file}"
            raise FileNotFoundError(msg)

    cameras = _read_colmap_cameras_binary(cameras_bin)
    num_registered = _read_colmap_images_binary(images_bin)
    num_points, reprojection_error = _read_colmap_points3d_binary(points3d_bin)

    return num_registered, num_points, reprojection_error, cameras


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def verify_colmap_installation(config: PipelineConfig) -> None:
    """Check COLMAP CLI is available. Raises FileNotFoundError with install instructions."""
    binary = str(config.colmap_binary)
    resolved = shutil.which(binary)

    if resolved is None:
        msg = (
            f"COLMAP binary '{binary}' not found on PATH.\n"
            f"Install COLMAP from https://colmap.github.io/install.html\n"
            f"Or set 'colmap_binary' in config/pipeline.yaml to the full path."
        )
        raise FileNotFoundError(msg)

    logger.success("COLMAP found at: {}", resolved)


def run_sparse(
    image_dir: Path,
    workspace: Path,
    config: PipelineConfig,
) -> SparseResult:
    """Run COLMAP sparse reconstruction via CLI subprocess. Returns SparseResult."""
    # --- Validate inputs ---
    if not image_dir.exists() or not image_dir.is_dir():
        msg = f"Image directory does not exist: {image_dir}"
        raise ValueError(msg)

    num_images = _count_images(image_dir)
    if num_images == 0:
        msg = f"No valid images (jpg/jpeg/png) found in {image_dir}"
        raise ValueError(msg)

    logger.info("Found {} images in {}", num_images, image_dir)

    # --- Set up workspace ---
    database_path = workspace / "database.db"
    sparse_dir = workspace / "sparse"
    sparse_dir.mkdir(parents=True, exist_ok=True)

    # --- Feature extraction ---
    _run_colmap_command(
        [
            "feature_extractor",
            "--database_path", str(database_path),
            "--image_path", str(image_dir),
            "--ImageReader.camera_model", config.colmap.camera_model,
        ],
        config,
    )

    # --- Matching ---
    _run_colmap_command(
        [
            "exhaustive_matcher",
            "--database_path", str(database_path),
        ],
        config,
    )

    # --- Mapping ---
    _run_colmap_command(
        [
            "mapper",
            "--database_path", str(database_path),
            "--image_path", str(image_dir),
            "--output_path", str(sparse_dir),
        ],
        config,
    )

    # --- Read results (COLMAP puts model in sparse/0/) ---
    model_dir = sparse_dir / "0"
    if not model_dir.exists():
        return SparseResult(
            workspace=workspace,
            num_registered=0,
            num_points=0,
            reprojection_error=0.0,
            cameras={},
            success=False,
            diagnostics="COLMAP mapper produced no output model at sparse/0/",
        )

    num_registered, num_points, reprojection_error, cameras = _read_sparse_model(
        model_dir,
    )
    logger.info(
        "Sparse result: {} registered, {} points, reproj_err={:.3f}px",
        num_registered,
        num_points,
        reprojection_error,
    )

    # --- Quality gates ---
    diagnostics_parts: list[str] = []

    registered_ratio = num_registered / num_images if num_images > 0 else 0.0
    if registered_ratio < config.colmap.min_registered_ratio:
        diagnostics_parts.append(
            f"Registration ratio {registered_ratio:.2f} below minimum "
            f"{config.colmap.min_registered_ratio} "
            f"({num_registered}/{num_images} images registered)"
        )

    if num_points < config.colmap.min_3d_points:
        diagnostics_parts.append(
            f"Only {num_points} 3D points reconstructed, "
            f"minimum is {config.colmap.min_3d_points}"
        )

    if reprojection_error > config.colmap.max_reprojection_error:
        diagnostics_parts.append(
            f"Reprojection error {reprojection_error:.3f}px exceeds "
            f"maximum {config.colmap.max_reprojection_error}px"
        )

    success = len(diagnostics_parts) == 0
    diagnostics = "; ".join(diagnostics_parts) if diagnostics_parts else "All quality gates passed"

    if success:
        logger.success("Sparse reconstruction passed all quality gates")
    else:
        logger.warning("Sparse reconstruction failed quality gates: {}", diagnostics)

    return SparseResult(
        workspace=workspace,
        num_registered=num_registered,
        num_points=num_points,
        reprojection_error=reprojection_error,
        cameras=cameras,
        success=success,
        diagnostics=diagnostics,
    )


def run_dense(
    workspace: Path,
    config: PipelineConfig,
) -> DenseResult:
    """Run COLMAP dense reconstruction. Returns DenseResult with PLY path."""
    sparse_dir = workspace / "sparse" / "0"
    dense_dir = workspace / "dense"
    dense_dir.mkdir(parents=True, exist_ok=True)

    # --- Image undistortion ---
    _run_colmap_command(
        [
            "image_undistorter",
            "--image_path", str(workspace / "images"),
            "--input_path", str(sparse_dir),
            "--output_path", str(dense_dir),
            "--output_type", "COLMAP",
        ],
        config,
    )

    # --- Patch match stereo ---
    _run_colmap_command(
        [
            "patch_match_stereo",
            "--workspace_path", str(dense_dir),
            "--workspace_format", "COLMAP",
        ],
        config,
    )

    # --- Stereo fusion ---
    fused_ply = dense_dir / "fused.ply"
    _run_colmap_command(
        [
            "stereo_fusion",
            "--workspace_path", str(dense_dir),
            "--workspace_format", "COLMAP",
            "--output_path", str(fused_ply),
        ],
        config,
    )

    if not fused_ply.exists():
        msg = f"Dense fusion output not found: {fused_ply}"
        raise RuntimeError(msg)

    # --- Read PLY stats ---
    cloud = trimesh.load(str(fused_ply))
    vertices = np.asarray(cloud.vertices)
    num_points = len(vertices)
    bbox_min = vertices.min(axis=0)
    bbox_max = vertices.max(axis=0)

    logger.success(
        "Dense reconstruction complete: {} points, bbox extent {:.1f}mm",
        num_points,
        np.linalg.norm(bbox_max - bbox_min),
    )

    return DenseResult(
        point_cloud_path=fused_ply,
        num_points=num_points,
        bounding_box=(bbox_min, bbox_max),
    )

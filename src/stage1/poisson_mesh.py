"""Open3D Poisson surface reconstruction from oriented point clouds."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import open3d as o3d
import trimesh
from loguru import logger

from src.common.config import PipelineConfig


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class MeshResult:
    """Holds the reconstructed mesh and associated metadata."""

    mesh: trimesh.Trimesh
    is_watertight: bool
    face_count: int
    vertex_count: int
    density_filtered: bool


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_point_cloud(point_cloud_path: Path) -> o3d.geometry.PointCloud:
    """Loads a PLY point cloud from disk, raising on missing file or too few points."""
    if not point_cloud_path.exists():
        msg = f"Point cloud file not found: {point_cloud_path}"
        raise FileNotFoundError(msg)

    pcd = o3d.io.read_point_cloud(str(point_cloud_path))
    num_points = len(pcd.points)
    logger.info("Loaded point cloud with {} points from {}", num_points, point_cloud_path)

    if num_points < 100:
        msg = f"Point cloud has too few points ({num_points} < 100)"
        raise ValueError(msg)

    return pcd


def _ensure_normals(pcd: o3d.geometry.PointCloud) -> o3d.geometry.PointCloud:
    """Estimates and orients normals if the point cloud lacks them."""
    if not pcd.has_normals():
        logger.info("Point cloud has no normals — estimating via KNN")
        pcd.estimate_normals(
            search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.1, max_nn=30),
        )
        pcd.orient_normals_consistent_tangent_plane(k=15)
        logger.success("Normals estimated and oriented")
    else:
        logger.info("Point cloud already has normals")
    return pcd


def _run_poisson(
    pcd: o3d.geometry.PointCloud,
    depth: int,
) -> tuple[o3d.geometry.TriangleMesh, np.ndarray]:
    """Runs Poisson reconstruction, retrying at depth-1 on failure."""
    logger.info("Running Poisson reconstruction at depth={}", depth)
    try:
        mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
            pcd, depth=depth,
        )
        density_array = np.asarray(densities)
        if len(mesh.vertices) == 0:
            raise RuntimeError("Poisson produced an empty mesh")
        logger.success(
            "Poisson succeeded: {} vertices, {} triangles",
            len(mesh.vertices),
            len(mesh.triangles),
        )
        return mesh, density_array
    except Exception as first_err:
        fallback_depth = depth - 1
        if fallback_depth < 1:
            msg = f"Poisson reconstruction failed at depth={depth} and no fallback available"
            raise RuntimeError(msg) from first_err

        logger.warning(
            "Poisson failed at depth={}: {}. Retrying at depth={}",
            depth, first_err, fallback_depth,
        )
        try:
            mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
                pcd, depth=fallback_depth,
            )
            density_array = np.asarray(densities)
            if len(mesh.vertices) == 0:
                msg = f"Poisson produced an empty mesh at fallback depth={fallback_depth}"
                raise RuntimeError(msg)
            logger.success(
                "Poisson succeeded at fallback depth={}: {} vertices, {} triangles",
                fallback_depth, len(mesh.vertices), len(mesh.triangles),
            )
            return mesh, density_array
        except Exception as retry_err:
            msg = (
                f"Poisson reconstruction failed at both depth={depth} "
                f"and depth={fallback_depth}"
            )
            raise RuntimeError(msg) from retry_err


def _filter_low_density(
    mesh: o3d.geometry.TriangleMesh,
    densities: np.ndarray,
    min_density_percentile: float,
) -> tuple[o3d.geometry.TriangleMesh, bool]:
    """Removes vertices below the given density quantile."""
    if len(densities) == 0 or min_density_percentile <= 0.0:
        return mesh, False

    threshold = np.quantile(densities, min_density_percentile)
    vertices_to_keep = densities >= threshold
    mesh.remove_vertices_by_mask(~vertices_to_keep)
    removed_count = int(np.sum(~vertices_to_keep))
    logger.info(
        "Density filter: removed {} vertices below {:.4f} (percentile={:.2%})",
        removed_count, threshold, min_density_percentile,
    )
    return mesh, True


def _to_trimesh(o3d_mesh: o3d.geometry.TriangleMesh) -> trimesh.Trimesh:
    """Converts an Open3D TriangleMesh to a trimesh.Trimesh."""
    vertices = np.asarray(o3d_mesh.vertices)
    faces = np.asarray(o3d_mesh.triangles)

    vertex_colors = None
    if o3d_mesh.has_vertex_colors():
        vertex_colors = (np.asarray(o3d_mesh.vertex_colors) * 255).astype(np.uint8)

    return trimesh.Trimesh(
        vertices=vertices,
        faces=faces,
        vertex_colors=vertex_colors,
        process=True,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def reconstruct(point_cloud_path: Path, config: PipelineConfig) -> MeshResult:
    """Open3D Poisson reconstruction from point cloud PLY — point cloud must have normals."""
    pcd = _load_point_cloud(point_cloud_path)
    pcd = _ensure_normals(pcd)

    o3d_mesh, densities = _run_poisson(pcd, depth=config.poisson.depth)

    o3d_mesh, density_filtered = _filter_low_density(
        o3d_mesh, densities, config.poisson.min_density_percentile,
    )

    mesh = _to_trimesh(o3d_mesh)

    if not mesh.is_watertight:
        logger.warning(
            "Reconstructed mesh is NOT watertight (vertex_count={}, face_count={})",
            len(mesh.vertices), len(mesh.faces),
        )
    else:
        logger.success("Reconstructed mesh is watertight")

    return MeshResult(
        mesh=mesh,
        is_watertight=mesh.is_watertight,
        face_count=len(mesh.faces),
        vertex_count=len(mesh.vertices),
        density_filtered=density_filtered,
    )

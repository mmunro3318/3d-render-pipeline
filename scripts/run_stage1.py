"""Stage 1 orchestrator: photos -> COLMAP -> Poisson mesh -> validated exports.

Usage:
    python scripts/run_stage1.py --input data/forearm --output output/forearm
    python scripts/run_stage1.py --input data/forearm --output output/forearm --skip-dense
    python scripts/run_stage1.py --input data/forearm --output output/forearm --config config/pipeline.yaml
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path for imports
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from loguru import logger

from src.common.config import PipelineConfig, load_config
from src.common.mesh_utils import (
    MeshValidationError,
    export_obj,
    export_ply,
    export_stl,
    repair_mesh,
    validate_mesh,
)
from src.stage1.colmap_runner import (
    DenseResult,
    SparseResult,
    run_dense,
    run_sparse,
    verify_colmap_installation,
)
from src.stage1.poisson_mesh import reconstruct


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser for the Stage 1 orchestrator."""
    parser = argparse.ArgumentParser(
        description="Stage 1: photos -> COLMAP reconstruction -> Poisson mesh -> validated exports",
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Path to directory containing input photos (jpg/jpeg/png)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path to output directory for mesh exports and metrics",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=_PROJECT_ROOT / "config" / "pipeline.yaml",
        help="Path to pipeline config YAML (default: config/pipeline.yaml)",
    )
    parser.add_argument(
        "--skip-dense",
        action="store_true",
        help="Skip dense reconstruction; go straight from sparse cloud to Poisson",
    )
    return parser


# ---------------------------------------------------------------------------
# Metrics helper
# ---------------------------------------------------------------------------

def _write_metrics(
    output_dir: Path,
    *,
    input_image_count: int,
    sparse: SparseResult,
    dense: DenseResult | None,
    mesh_report: dict,
    duration_seconds: float,
) -> Path:
    """Write metrics JSON sidecar to output directory. Returns path to metrics file."""
    dense_metrics: dict | None = None
    if dense is not None:
        bbox_min, bbox_max = dense.bounding_box
        dense_metrics = {
            "num_points": dense.num_points,
            "bounding_box": {
                "min": bbox_min.tolist(),
                "max": bbox_max.tolist(),
            },
        }

    metrics = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "input_images": input_image_count,
        "sparse": {
            "num_registered": sparse.num_registered,
            "num_points": sparse.num_points,
            "reprojection_error": round(sparse.reprojection_error, 4),
            "success": sparse.success,
        },
        "dense": dense_metrics,
        "mesh": {
            "face_count": mesh_report["face_count"],
            "vertex_count": mesh_report["vertex_count"],
            "is_watertight": mesh_report["is_watertight"],
            "extent_mm": mesh_report["extent_mm"],
        },
        "duration_seconds": round(duration_seconds, 2),
    }

    metrics_path = output_dir / "metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    logger.info("Metrics written to {}", metrics_path)
    return metrics_path


# ---------------------------------------------------------------------------
# Image counting (mirrors colmap_runner logic for metrics)
# ---------------------------------------------------------------------------

_IMAGE_EXTENSIONS: frozenset[str] = frozenset({".jpg", ".jpeg", ".png"})


def _count_input_images(image_dir: Path) -> int:
    """Count valid image files in the input directory."""
    return sum(
        1 for f in image_dir.iterdir()
        if f.is_file() and f.suffix.lower() in _IMAGE_EXTENSIONS
    )


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main() -> int:  # noqa: PLR0911 — intentional early returns for error paths
    """Run the full Stage 1 pipeline. Returns 0 on success, 1 on failure."""
    parser = _build_parser()
    args = parser.parse_args()

    input_dir: Path = args.input.resolve()
    output_dir: Path = args.output.resolve()
    config_path: Path = args.config.resolve()
    skip_dense: bool = args.skip_dense

    start_time = time.monotonic()

    # ------------------------------------------------------------------
    # 1. Load configuration
    # ------------------------------------------------------------------
    try:
        config: PipelineConfig = load_config(config_path)
    except (FileNotFoundError, ValueError) as exc:
        logger.error("Failed to load config: {}", exc)
        print(f"\nERROR: Could not load pipeline config at {config_path}")
        print(f"  Reason: {exc}")
        return 1

    # ------------------------------------------------------------------
    # 2. Validate input directory
    # ------------------------------------------------------------------
    if not input_dir.exists() or not input_dir.is_dir():
        logger.error("Input directory does not exist: {}", input_dir)
        print(f"\nERROR: Input directory not found: {input_dir}")
        return 1

    input_image_count = _count_input_images(input_dir)
    if input_image_count == 0:
        logger.error("No valid images found in {}", input_dir)
        print(f"\nERROR: No valid images (jpg/jpeg/png) in {input_dir}")
        return 1

    logger.info("Input: {} images in {}", input_image_count, input_dir)

    # ------------------------------------------------------------------
    # 3. Prepare output directory
    # ------------------------------------------------------------------
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Output directory: {}", output_dir)

    # COLMAP workspace lives alongside output
    colmap_workspace = output_dir / "colmap_workspace"
    colmap_workspace.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 4. Verify COLMAP installation
    # ------------------------------------------------------------------
    try:
        verify_colmap_installation(config)
    except FileNotFoundError as exc:
        logger.error("COLMAP not available: {}", exc)
        print("\nERROR: COLMAP is not installed or not on PATH.")
        print(f"  {exc}")
        print("\nInstall COLMAP: https://colmap.github.io/install.html")
        print("Or set 'colmap_binary' in config/pipeline.yaml to the full path.")
        return 1

    # ------------------------------------------------------------------
    # 5. Sparse reconstruction
    # ------------------------------------------------------------------
    logger.info("=== Starting sparse reconstruction ===")
    try:
        sparse_result: SparseResult = run_sparse(input_dir, colmap_workspace, config)
    except (ValueError, RuntimeError) as exc:
        logger.error("Sparse reconstruction failed: {}", exc)
        print(f"\nERROR: COLMAP sparse reconstruction failed.")
        print(f"  {exc}")
        print("\nDiagnostic hints:")
        print("  - Ensure images have >= 60% overlap between consecutive shots")
        print("  - Check for blurry or featureless images")
        print("  - Verify images are from the same capture session")
        return 1

    if not sparse_result.success:
        logger.error("Sparse reconstruction failed quality gates: {}", sparse_result.diagnostics)
        print(f"\nERROR: Sparse reconstruction did not pass quality gates.")
        print(f"  Diagnostics: {sparse_result.diagnostics}")
        print(f"  Registered: {sparse_result.num_registered} images")
        print(f"  3D points: {sparse_result.num_points}")
        print(f"  Reprojection error: {sparse_result.reprojection_error:.3f}px")
        return 1

    logger.success(
        "Sparse reconstruction complete: {} registered, {} points, {:.3f}px reproj error",
        sparse_result.num_registered,
        sparse_result.num_points,
        sparse_result.reprojection_error,
    )

    # ------------------------------------------------------------------
    # 6. Dense reconstruction (optional)
    # ------------------------------------------------------------------
    dense_result: DenseResult | None = None
    point_cloud_path: Path

    if skip_dense:
        logger.info("--skip-dense flag set, skipping dense reconstruction")
        # Use sparse point cloud for Poisson — COLMAP exports sparse as binary,
        # but the sparse model dir contains the data needed by poisson_mesh.reconstruct
        point_cloud_path = colmap_workspace / "sparse" / "0"
    else:
        logger.info("=== Starting dense reconstruction ===")
        try:
            dense_result = run_dense(colmap_workspace, config)
            point_cloud_path = dense_result.point_cloud_path
            logger.success("Dense reconstruction complete: {} points", dense_result.num_points)
        except RuntimeError as exc:
            logger.warning(
                "Dense reconstruction failed, falling back to sparse cloud: {}", exc,
            )
            print("\nWARNING: Dense reconstruction failed. Using sparse cloud as fallback.")
            print(f"  Reason: {exc}")
            point_cloud_path = colmap_workspace / "sparse" / "0"

    # ------------------------------------------------------------------
    # 7. Poisson surface reconstruction
    # ------------------------------------------------------------------
    logger.info("=== Starting Poisson surface reconstruction ===")
    try:
        mesh = reconstruct(point_cloud_path, config)
    except Exception as exc:
        logger.warning("Poisson reconstruction failed on first attempt: {}", exc)
        logger.info("Attempting reconstruction with repair fallback...")
        try:
            # Try reconstruct again — if it produced a partial mesh, repair it
            mesh = reconstruct(point_cloud_path, config)
            mesh = repair_mesh(mesh)
        except Exception as retry_exc:
            logger.error("Poisson reconstruction failed after retry: {}", retry_exc)
            print("\nERROR: Poisson surface reconstruction failed.")
            print(f"  {retry_exc}")
            print("\nThis usually means the point cloud is too sparse or noisy.")
            print("  - Try capturing more photos with better overlap")
            print("  - Ensure the subject is well-lit and has surface texture")
            return 1

    # ------------------------------------------------------------------
    # 8. Validate mesh
    # ------------------------------------------------------------------
    logger.info("=== Validating output mesh ===")
    try:
        mesh_report = validate_mesh(mesh)
    except MeshValidationError as exc:
        logger.error("Mesh validation failed: {}", exc)
        print(f"\nERROR: Output mesh is invalid: {exc}")
        return 1

    if not mesh_report["is_watertight"]:
        logger.warning("Mesh is not watertight — attempting repair")
        mesh = repair_mesh(mesh)
        mesh_report = validate_mesh(mesh)
        if not mesh_report["is_watertight"]:
            logger.warning(
                "Mesh is still not watertight after repair. "
                "Exporting anyway, but this mesh will NOT pass print constraints."
            )

    # ------------------------------------------------------------------
    # 9. Export mesh in all formats
    # ------------------------------------------------------------------
    logger.info("=== Exporting mesh files ===")
    stl_path = output_dir / "mesh.stl"
    ply_path = output_dir / "mesh.ply"
    obj_path = output_dir / "mesh.obj"

    try:
        export_stl(mesh, stl_path)
        export_ply(mesh, ply_path)
        export_obj(mesh, obj_path)
    except (MeshValidationError, FileNotFoundError) as exc:
        logger.error("Export failed: {}", exc)
        print(f"\nERROR: Failed to export mesh: {exc}")
        return 1

    # ------------------------------------------------------------------
    # 10. Write metrics JSON
    # ------------------------------------------------------------------
    duration_seconds = time.monotonic() - start_time

    _write_metrics(
        output_dir,
        input_image_count=input_image_count,
        sparse=sparse_result,
        dense=dense_result,
        mesh_report=mesh_report,
        duration_seconds=duration_seconds,
    )

    # ------------------------------------------------------------------
    # 11. Summary
    # ------------------------------------------------------------------
    logger.success("=== Stage 1 complete ===")
    logger.success("Duration: {:.1f}s", duration_seconds)
    logger.success("Exports: {}, {}, {}", stl_path.name, ply_path.name, obj_path.name)

    print(f"\n{'='*60}")
    print(f"  Stage 1 Complete")
    print(f"{'='*60}")
    print(f"  Input images:      {input_image_count}")
    print(f"  Sparse points:     {sparse_result.num_points}")
    print(f"  Dense points:      {dense_result.num_points if dense_result else 'skipped'}")
    print(f"  Mesh faces:        {mesh_report['face_count']}")
    print(f"  Mesh vertices:     {mesh_report['vertex_count']}")
    print(f"  Watertight:        {mesh_report['is_watertight']}")
    print(f"  Duration:          {duration_seconds:.1f}s")
    print(f"  Output:            {output_dir}")
    print(f"{'='*60}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())

# Implementation Guide — Sprint 1-2
## COLMAP Photogrammetry + Poisson Mesh Reconstruction
> Context doc for coding agents | HyperReal Prosthetic Cover Pipeline

---

## What This Sprint Builds

**Input:** 40-60 photos of a forearm taken with iPad Pro camera
**Output:** A watertight 3D mesh (STL) of the forearm

**Pipeline:**
```
Photos → COLMAP SfM (camera poses + sparse points)
  → COLMAP Dense / OpenMVS (dense point cloud)
    → Poisson Reconstruction (watertight mesh)
      → Export STL
```

---

## 1. Environment Setup

### Dependencies

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Core dependencies
pip install trimesh numpy open3d pydantic pyyaml pillow opencv-python tqdm loguru

# COLMAP Python bindings
pip install pycolmap

# For mesh booleans later
pip install manifold3d

# PyTorch (RTX 5060 Ti = Blackwell arch, needs CUDA 12.8+)
# CRITICAL: RTX 5060 Ti requires PyTorch 2.7+ for sm_120 compute capability
pip install torch==2.7.0 torchvision==0.19.0 --index-url https://download.pytorch.org/whl/cu128

# SAM2 for segmentation
pip install ultralytics>=8.2.70
```

### COLMAP Installation (Binary)

```bash
# Windows: Download pre-built binary from https://colmap.github.io/install.html
# Extract to C:\colmap\ and add to PATH

# Linux:
sudo apt-get install colmap

# Verify:
colmap -h
```

### Gotcha: RTX 5060 Ti CUDA Compatibility
The RTX 5060 Ti uses **Blackwell architecture (sm_120)**. Standard PyTorch < 2.7 does NOT support this. If you get errors about unsupported GPU architecture:
- Ensure `torch.__version__` >= 2.7.0
- Ensure CUDA toolkit is 12.8+
- Check with: `python -c "import torch; print(torch.cuda.get_arch_list())"`

### Fallback: CPU-only for testing
```python
# If GPU setup fails, everything except PyTorch3D refinement works on CPU
device = torch.device("cpu")  # COLMAP uses its own GPU path
```

---

## 2. COLMAP — Structure from Motion

### What COLMAP Does

COLMAP takes your photos and:
1. **Feature extraction** — Finds distinctive keypoints (SIFT features) in each photo
2. **Feature matching** — Matches keypoints across photo pairs
3. **Sparse reconstruction** — Triangulates 3D points + estimates camera poses (position/orientation for each photo)
4. **Dense reconstruction** — Computes depth maps for each photo, fuses into dense point cloud

### Running COLMAP via Command Line (Simplest)

```bash
# Create workspace
mkdir -p colmap_workspace/images
# Copy your 40-60 forearm photos into colmap_workspace/images/

# Run the full automatic pipeline
colmap automatic_reconstructor \
    --workspace_path colmap_workspace \
    --image_path colmap_workspace/images \
    --camera_model PINHOLE \
    --single_camera 1
```

**What `--single_camera 1` does:** Tells COLMAP all photos come from the same camera (iPad). This improves accuracy because it shares intrinsic parameters.

**What `--camera_model PINHOLE` does:** Uses a simple pinhole camera model (fx, fy, cx, cy). Good enough for iPad photos. Alternatives: `OPENCV` (adds distortion), `SIMPLE_RADIAL`.

### Running COLMAP via Python (pycolmap)

```python
import pycolmap
from pathlib import Path

def run_colmap_reconstruction(
    image_dir: str,
    output_dir: str,
    camera_model: str = "PINHOLE",
    single_camera: bool = True,
) -> dict:
    """
    Run full COLMAP reconstruction pipeline.

    Args:
        image_dir: Path to directory containing photos
        output_dir: Path for COLMAP output
        camera_model: Camera model type
        single_camera: Whether all images are from the same camera

    Returns:
        dict with reconstruction info (num_images, num_points, etc.)
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    database_path = output_path / "database.db"
    sparse_path = output_path / "sparse"
    dense_path = output_path / "dense"
    sparse_path.mkdir(exist_ok=True)
    dense_path.mkdir(exist_ok=True)

    # Step 1: Feature extraction
    print("Extracting features...")
    pycolmap.extract_features(
        database_path=str(database_path),
        image_path=str(image_dir),
        camera_model=camera_model,
        single_camera=single_camera,
    )

    # Step 2: Feature matching (exhaustive for small datasets)
    print("Matching features...")
    pycolmap.match_exhaustive(
        database_path=str(database_path),
    )

    # Step 3: Sparse reconstruction (Structure from Motion)
    print("Running sparse reconstruction...")
    reconstructions = pycolmap.incremental_mapping(
        database_path=str(database_path),
        image_path=str(image_dir),
        output_path=str(sparse_path),
    )

    if not reconstructions:
        raise RuntimeError("COLMAP failed to reconstruct. Check image quality/overlap.")

    # Use the largest reconstruction
    best_recon = max(reconstructions.values(), key=lambda r: r.num_reg_images())

    info = {
        "num_images": best_recon.num_reg_images(),
        "num_points": best_recon.num_points3D(),
        "num_cameras": len(best_recon.cameras),
    }

    print(f"Sparse reconstruction: {info['num_images']} images, "
          f"{info['num_points']} 3D points")

    return info

# Usage
info = run_colmap_reconstruction(
    image_dir="colmap_workspace/images",
    output_dir="colmap_workspace",
)
```

### Reading COLMAP Output (cameras, images, points)

```python
import numpy as np
from pathlib import Path

def read_colmap_cameras(cameras_txt: str) -> dict:
    """
    Parse COLMAP cameras.txt.

    Returns dict: {camera_id: {"model", "width", "height", "params"}}
    params for PINHOLE: [fx, fy, cx, cy]
    """
    cameras = {}
    with open(cameras_txt) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            cam_id = int(parts[0])
            cameras[cam_id] = {
                "model": parts[1],
                "width": int(parts[2]),
                "height": int(parts[3]),
                "params": np.array([float(p) for p in parts[4:]]),
            }
    return cameras

def read_colmap_images(images_txt: str) -> dict:
    """
    Parse COLMAP images.txt.

    Returns dict: {image_id: {"quat", "tvec", "camera_id", "name"}}
    quat = [qw, qx, qy, qz] (Hamilton convention)
    tvec = [tx, ty, tz]

    COLMAP convention: X_cam = R @ X_world + t
    Camera center in world: -R^T @ t
    """
    images = {}
    with open(images_txt) as f:
        lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]

    # images.txt has pairs of lines: pose line + points2D line
    for i in range(0, len(lines), 2):
        parts = lines[i].split()
        image_id = int(parts[0])
        qw, qx, qy, qz = [float(p) for p in parts[1:5]]
        tx, ty, tz = [float(p) for p in parts[5:8]]
        camera_id = int(parts[8])
        name = parts[9]

        images[image_id] = {
            "quat": np.array([qw, qx, qy, qz]),
            "tvec": np.array([tx, ty, tz]),
            "camera_id": camera_id,
            "name": name,
        }
    return images

def read_colmap_points(points3D_txt: str) -> np.ndarray:
    """
    Parse COLMAP points3D.txt.

    Returns (N, 3) array of 3D point coordinates.
    """
    points = []
    with open(points3D_txt) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
            points.append([x, y, z])
    return np.array(points)

def quat_to_rotmat(quat: np.ndarray) -> np.ndarray:
    """Convert quaternion [qw, qx, qy, qz] to 3x3 rotation matrix."""
    qw, qx, qy, qz = quat
    return np.array([
        [1 - 2*(qy**2 + qz**2), 2*(qx*qy - qw*qz), 2*(qx*qz + qw*qy)],
        [2*(qx*qy + qw*qz), 1 - 2*(qx**2 + qz**2), 2*(qy*qz - qw*qx)],
        [2*(qx*qz - qw*qy), 2*(qy*qz + qw*qx), 1 - 2*(qx**2 + qy**2)],
    ])

def get_camera_centers(images: dict) -> np.ndarray:
    """Get camera positions in world coordinates from COLMAP images."""
    centers = []
    for img_data in images.values():
        R = quat_to_rotmat(img_data["quat"])
        t = img_data["tvec"]
        # Camera center in world coords: C = -R^T @ t
        center = -R.T @ t
        centers.append(center)
    return np.array(centers)
```

### Validating COLMAP Output

```python
def validate_colmap_reconstruction(sparse_dir: str) -> bool:
    """
    Validate COLMAP reconstruction quality.

    Checks:
    1. Enough images registered (>80% of input)
    2. Enough 3D points reconstructed
    3. Point cloud is reasonable scale (not microscopic or planetary)
    """
    cameras = read_colmap_cameras(f"{sparse_dir}/cameras.txt")
    images = read_colmap_images(f"{sparse_dir}/images.txt")
    points = read_colmap_points(f"{sparse_dir}/points3D.txt")

    print(f"Registered cameras: {len(cameras)}")
    print(f"Registered images: {len(images)}")
    print(f"3D points: {len(points)}")

    # Check 1: Enough images
    if len(images) < 10:
        print("WARNING: Too few images registered. Capture more photos.")
        return False

    # Check 2: Enough points
    if len(points) < 1000:
        print("WARNING: Too few 3D points. Images may lack texture/overlap.")
        return False

    # Check 3: Reasonable scale
    # A forearm is roughly 25-30cm long
    extent = np.ptp(points, axis=0)  # Range along each axis
    max_extent = extent.max()
    print(f"Point cloud extent: {extent} (max: {max_extent:.3f})")

    # COLMAP outputs are in arbitrary scale, but with PINHOLE + real photos
    # the scale is usually close to meters
    if max_extent < 0.01 or max_extent > 100:
        print(f"WARNING: Scale looks off (max extent: {max_extent}). "
              "Check units or reconstruction quality.")

    # Check 4: Camera positions form a ring-like pattern
    centers = get_camera_centers(images)
    center_spread = np.std(centers, axis=0)
    print(f"Camera position spread (std): {center_spread}")

    print("Reconstruction looks reasonable.")
    return True
```

### Troubleshooting: When COLMAP Fails

| Symptom | Cause | Fix |
|---------|-------|-----|
| 0 images registered | No feature matches found | More overlap between photos (60%+), better lighting |
| Few images registered (<50%) | Some photos too blurry or too different | Remove blurry photos, ensure consistent lighting |
| Point cloud is flat/degenerate | All photos from similar angle | Capture from multiple heights + angles around the limb |
| Scale is wildly wrong | No real-world reference | Add a ruler or known-size object in frame |
| Very slow (>30 min) | Too many photos or exhaustive matching | Use `sequential_matching` instead of `exhaustive` for >100 photos |
| "Not enough inliers" error | Poor feature matching | Increase `--SiftExtraction.max_num_features 8192` |

---

## 3. Dense Reconstruction + Poisson Mesh

### Option A: COLMAP Dense (Command Line)

```bash
# After sparse reconstruction:
colmap image_undistorter \
    --image_path colmap_workspace/images \
    --input_path colmap_workspace/sparse/0 \
    --output_path colmap_workspace/dense

colmap patch_match_stereo \
    --workspace_path colmap_workspace/dense

colmap stereo_fusion \
    --workspace_path colmap_workspace/dense \
    --output_path colmap_workspace/dense/fused.ply
```

### Option B: Open3D Poisson Reconstruction (from COLMAP sparse)

```python
import open3d as o3d
import numpy as np

def sparse_points_to_mesh(
    points: np.ndarray,
    output_path: str,
    depth: int = 9,
    density_threshold_percentile: float = 10,
) -> "trimesh.Trimesh":
    """
    Convert sparse COLMAP point cloud to watertight mesh via Poisson.

    Args:
        points: (N, 3) array of 3D points
        output_path: where to save the mesh
        depth: Poisson octree depth (higher = more detail, 8-10 typical)
        density_threshold_percentile: remove low-density vertices (cleanup)

    Returns:
        trimesh.Trimesh mesh object
    """
    import trimesh

    # Create Open3D point cloud
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points)

    # Estimate normals (required for Poisson)
    # orient_normals_consistent_tangent_plane helps with orientation
    pcd.estimate_normals(
        search_param=o3d.geometry.KDTreeSearchParamHybrid(
            radius=0.05,  # Search radius for normal estimation
            max_nn=30      # Max neighbors to consider
        )
    )

    # Orient normals consistently (important for Poisson!)
    pcd.orient_normals_consistent_tangent_plane(k=15)

    print(f"Point cloud: {len(pcd.points)} points with normals")

    # Run Poisson surface reconstruction
    print(f"Running Poisson reconstruction (depth={depth})...")
    mesh_o3d, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
        pcd,
        depth=depth,
        width=0,
        scale=1.1,
        linear_fit=False
    )

    # Remove low-density vertices (cleans up reconstruction artifacts)
    densities = np.asarray(densities)
    density_threshold = np.percentile(densities, density_threshold_percentile)
    vertices_to_remove = densities < density_threshold
    mesh_o3d.remove_vertices_by_mask(vertices_to_remove)

    print(f"Mesh: {len(mesh_o3d.vertices)} vertices, "
          f"{len(mesh_o3d.triangles)} triangles")

    # Convert to trimesh
    vertices = np.asarray(mesh_o3d.vertices)
    faces = np.asarray(mesh_o3d.triangles)
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces)

    # Repair
    mesh.fix_normals()
    mesh.fill_holes()

    print(f"Watertight: {mesh.is_watertight}")
    print(f"Volume: {mesh.volume:.6f}")

    # Export
    mesh.export(output_path)
    print(f"Saved to {output_path}")

    return mesh

# Usage
points = read_colmap_points("colmap_workspace/sparse/0/points3D.txt")
mesh = sparse_points_to_mesh(
    points,
    output_path="forearm_mesh.stl",
    depth=9,
    density_threshold_percentile=10,
)
```

### Option C: Dense Point Cloud → Poisson (Best Quality)

```python
def dense_ply_to_mesh(
    dense_ply_path: str,
    output_path: str,
    depth: int = 10,
    voxel_size: float = 0.001,  # Downsample to 1mm voxels
) -> "trimesh.Trimesh":
    """
    Convert COLMAP dense fused.ply to watertight mesh.

    This gives better results than sparse points because the
    dense point cloud has millions of points with accurate normals.
    """
    import trimesh

    # Load dense point cloud
    pcd = o3d.io.read_point_cloud(dense_ply_path)
    print(f"Loaded {len(pcd.points)} points from dense cloud")

    # Downsample (dense clouds can be huge)
    if voxel_size > 0:
        pcd = pcd.voxel_down_sample(voxel_size=voxel_size)
        print(f"After downsampling: {len(pcd.points)} points")

    # Estimate normals if not present
    if not pcd.has_normals():
        pcd.estimate_normals(
            search_param=o3d.geometry.KDTreeSearchParamHybrid(
                radius=0.01, max_nn=30
            )
        )

    # Orient normals
    pcd.orient_normals_consistent_tangent_plane(k=15)

    # Poisson reconstruction
    print(f"Running Poisson reconstruction (depth={depth})...")
    mesh_o3d, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
        pcd, depth=depth
    )

    # Cleanup low-density regions
    densities = np.asarray(densities)
    threshold = np.percentile(densities, 5)
    mesh_o3d.remove_vertices_by_mask(densities < threshold)

    # Convert to trimesh
    vertices = np.asarray(mesh_o3d.vertices)
    faces = np.asarray(mesh_o3d.triangles)
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces)
    mesh.fix_normals()
    mesh.fill_holes()

    print(f"Final mesh: {len(mesh.vertices)} verts, "
          f"{len(mesh.faces)} faces, watertight={mesh.is_watertight}")

    mesh.export(output_path)
    return mesh
```

### Gotchas: Poisson Reconstruction

| Issue | Cause | Fix |
|-------|-------|-----|
| Mesh has big bulges at edges | Low-density artifacts from Poisson | Increase `density_threshold_percentile` to 15-20 |
| Mesh is too smooth, no detail | `depth` too low | Increase depth to 10-11 (slower but more detail) |
| Normals pointing wrong way | `orient_normals` failed | Try `orient_normals_towards_camera_location(camera_location)` |
| Mesh has holes | Point cloud has gaps | Capture more photos from missing angles |
| Mesh is inside-out | Normal orientation wrong | Call `mesh.fix_normals()` after conversion |
| Open3D crashes on large cloud | Too many points (>10M) | Downsample with `voxel_down_sample(0.002)` |

---

## 4. Complete Sprint 1-2 Pipeline Script

```python
#!/usr/bin/env python3
"""
run_stage1.py — Full Stage 1 pipeline: Photos → Watertight Mesh

Usage:
    python scripts/run_stage1.py --photos ./forearm_photos/ --output ./forearm.stl
"""

import argparse
import subprocess
from pathlib import Path
import numpy as np
import open3d as o3d
import trimesh
from loguru import logger

def run_colmap(image_dir: Path, workspace: Path):
    """Run COLMAP automatic reconstruction via CLI."""
    workspace.mkdir(parents=True, exist_ok=True)

    cmd = [
        "colmap", "automatic_reconstructor",
        "--workspace_path", str(workspace),
        "--image_path", str(image_dir),
        "--camera_model", "PINHOLE",
        "--single_camera", "1",
    ]

    logger.info(f"Running COLMAP: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)

    if result.returncode != 0:
        logger.error(f"COLMAP failed:\n{result.stderr}")
        raise RuntimeError("COLMAP reconstruction failed")

    logger.info("COLMAP reconstruction complete")

def load_colmap_dense_or_sparse(workspace: Path) -> np.ndarray:
    """Load point cloud from COLMAP output (prefer dense, fall back to sparse)."""

    dense_ply = workspace / "dense" / "fused.ply"
    if dense_ply.exists():
        logger.info(f"Loading dense point cloud: {dense_ply}")
        pcd = o3d.io.read_point_cloud(str(dense_ply))
        return np.asarray(pcd.points), pcd

    # Fall back to sparse
    sparse_dir = workspace / "sparse" / "0"
    if not sparse_dir.exists():
        # Try to find any sparse reconstruction
        sparse_dirs = sorted((workspace / "sparse").glob("*"))
        if sparse_dirs:
            sparse_dir = sparse_dirs[0]
        else:
            raise FileNotFoundError("No COLMAP reconstruction found")

    points3d_path = sparse_dir / "points3D.txt"
    if not points3d_path.exists():
        # Try binary format
        points3d_path = sparse_dir / "points3D.bin"

    logger.info(f"Loading sparse point cloud from: {sparse_dir}")
    points = []
    with open(sparse_dir / "points3D.txt") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            points.append([float(parts[1]), float(parts[2]), float(parts[3])])

    points = np.array(points)
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points)

    return points, pcd

def poisson_reconstruct(pcd: o3d.geometry.PointCloud, depth: int = 9) -> trimesh.Trimesh:
    """Run Poisson surface reconstruction on point cloud."""

    # Estimate normals if needed
    if not pcd.has_normals():
        logger.info("Estimating normals...")
        pcd.estimate_normals(
            search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.02, max_nn=30)
        )

    pcd.orient_normals_consistent_tangent_plane(k=15)

    logger.info(f"Running Poisson reconstruction (depth={depth})...")
    mesh_o3d, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
        pcd, depth=depth
    )

    # Remove low-density artifacts
    densities_np = np.asarray(densities)
    threshold = np.percentile(densities_np, 10)
    mesh_o3d.remove_vertices_by_mask(densities_np < threshold)

    # Convert to trimesh
    mesh = trimesh.Trimesh(
        vertices=np.asarray(mesh_o3d.vertices),
        faces=np.asarray(mesh_o3d.triangles),
    )

    # Repair
    mesh.fix_normals()
    mesh.fill_holes()

    return mesh

def validate_mesh(mesh: trimesh.Trimesh) -> bool:
    """Run QC checks on output mesh."""
    logger.info("--- Mesh Validation ---")
    logger.info(f"  Vertices: {len(mesh.vertices)}")
    logger.info(f"  Faces: {len(mesh.faces)}")
    logger.info(f"  Watertight: {mesh.is_watertight}")
    logger.info(f"  Volume: {mesh.volume:.6f}")

    bounds = mesh.bounds
    extent = bounds[1] - bounds[0]
    logger.info(f"  Extent (XYZ): {extent}")

    passed = True
    if not mesh.is_watertight:
        logger.warning("  FAIL: Mesh is not watertight")
        passed = False
    if mesh.volume <= 0:
        logger.warning("  FAIL: Mesh has non-positive volume")
        passed = False
    if len(mesh.vertices) < 100:
        logger.warning("  FAIL: Too few vertices")
        passed = False

    return passed

def main():
    parser = argparse.ArgumentParser(description="Stage 1: Photos → Mesh")
    parser.add_argument("--photos", required=True, help="Directory of input photos")
    parser.add_argument("--output", required=True, help="Output STL path")
    parser.add_argument("--workspace", default="./colmap_workspace", help="COLMAP workspace")
    parser.add_argument("--depth", type=int, default=9, help="Poisson depth (8-11)")
    parser.add_argument("--skip-colmap", action="store_true", help="Skip COLMAP, use existing workspace")
    args = parser.parse_args()

    photos_dir = Path(args.photos)
    workspace = Path(args.workspace)
    output_path = Path(args.output)

    # Step 1: COLMAP
    if not args.skip_colmap:
        run_colmap(photos_dir, workspace)

    # Step 2: Load point cloud
    points, pcd = load_colmap_dense_or_sparse(workspace)
    logger.info(f"Loaded {len(points)} points")

    # Step 3: Poisson reconstruction
    mesh = poisson_reconstruct(pcd, depth=args.depth)

    # Step 4: Validate
    if validate_mesh(mesh):
        logger.success("Mesh passed all checks")
    else:
        logger.warning("Mesh has issues — review before proceeding")

    # Step 5: Export
    output_path.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(str(output_path))
    logger.info(f"Saved mesh to {output_path}")

if __name__ == "__main__":
    main()
```

---

## 5. Capture Protocol Reference

```
Equipment: iPad Pro (main camera, NOT the LiDAR sensor)
Lighting:  Well-lit room, diffuse light (overcast window or ring light)
           AVOID: direct sunlight, harsh shadows, fluorescent flicker
Color card: Include Amazon color card in 5 photos (front, back, left, right, top)
Distance:  30-50cm from limb surface
Background: Simple, non-cluttered (plain wall or bedsheet)

Capture Pattern:
  Ring 1 (wrist level):    15-20 photos, every ~20°, camera level with wrist
  Ring 2 (mid-forearm):    15-20 photos, every ~20°, camera level with mid-arm
  Ring 3 (elbow level):    10-15 photos, every ~25°, camera angled slightly down

Total: 40-55 photos
Time: <10 minutes
Overlap: Each photo shares ~60% content with its neighbor

Tips:
  - Keep the limb STILL (rest it on a table)
  - Move the camera, not the limb
  - Maintain consistent distance
  - Avoid motion blur (hold steady or use burst mode)
  - Include some angled shots (not all perfectly horizontal)
```

---

## 6. Key Concepts for the Uninitiated

### What is a "watertight" mesh?
A mesh where every edge is shared by exactly 2 triangles — like a sealed balloon. No holes, no gaps. Required for 3D printing because the printer needs to know what's "inside" vs "outside."

### What are camera "intrinsics" vs "extrinsics"?
- **Intrinsics:** Properties of the camera lens — focal length (fx, fy), optical center (cx, cy). Same for all photos from the same camera.
- **Extrinsics:** Where the camera was in 3D space — rotation (R) and translation (t). Different for every photo.

### What is Poisson reconstruction?
An algorithm that takes a point cloud with normals and fits a smooth surface through it. It naturally produces watertight meshes. The `depth` parameter controls detail level (like resolution).

### What are "features" in COLMAP?
Distinctive visual patterns in photos (corners, edges, blobs) that COLMAP can match across different photos. Textured surfaces (freckles, hair, veins) have lots of features. Smooth skin has few — that's why we need enough photos with overlap.

# Implementation Guide — Sprint 6-8
## Differentiable Refinement, SAM2 Segmentation, Texture Mapping
> Context doc for coding agents | HyperReal Prosthetic Cover Pipeline

---

## What These Sprints Build

**Sprint 6:** PyTorch3D silhouette-based mesh refinement (optional — only if COLMAP alone isn't accurate enough)
**Sprint 7:** Per-vertex color mapping from multi-view photos
**Sprint 8:** Second print iteration with texture

**Input:** COLMAP mesh (Sprint 2) + original photos + camera poses
**Output:** Refined, color-mapped mesh ready for full-color 3D printing

---

## 1. SAM2 Segmentation — Generate Limb Masks (Sprint 6 prerequisite)

### Why We Need Masks
Differentiable rendering optimizes the mesh by comparing rendered silhouettes against target silhouettes. We need binary masks (white = limb, black = background) for every photo.

### Basic SAM2 Usage

```python
from ultralytics import SAM
import cv2
import numpy as np
from pathlib import Path

def generate_limb_masks(
    image_dir: str,
    output_dir: str,
    model_name: str = "sam2_hiera_small.pt",
    device: str = "cuda:0",
) -> list:
    """
    Generate binary limb masks for all photos using SAM2.

    Runs SAM2 in automatic mode, selects the largest mask
    (assumed to be the limb), and saves as binary PNG.

    Args:
        image_dir: Directory containing input photos
        output_dir: Directory to save binary masks
        model_name: SAM2 model size. Use "sam2_hiera_small.pt" for 16GB VRAM.
            Available: sam2_hiera_tiny, sam2_hiera_small, sam2_hiera_base, sam2_hiera_large
        device: "cuda:0" or "cpu"

    Returns:
        List of output mask paths
    """
    model = SAM(model_name)

    image_path = Path(image_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    mask_paths = []

    for img_file in sorted(image_path.glob("*.jpg")):
        # Run SAM2 (automatic mode - no prompts)
        results = model(str(img_file), device=device)

        # Extract masks
        masks = results[0].masks.data.cpu().numpy()  # (N_masks, H, W)

        if len(masks) == 0:
            print(f"WARNING: No masks found for {img_file.name}, skipping")
            continue

        # Select largest mask (the limb)
        mask_areas = [m.sum() for m in masks]
        largest_idx = np.argmax(mask_areas)
        limb_mask = (masks[largest_idx] * 255).astype(np.uint8)

        # Morphological cleanup
        limb_mask = cleanup_mask(limb_mask)

        # Save
        mask_file = output_path / f"{img_file.stem}_mask.png"
        cv2.imwrite(str(mask_file), limb_mask)
        mask_paths.append(str(mask_file))

    print(f"Generated {len(mask_paths)} masks")
    return mask_paths

def cleanup_mask(
    binary_mask: np.ndarray,
    kernel_size: int = 7,
    iterations: int = 2,
) -> np.ndarray:
    """
    Morphological cleanup: remove noise, fill holes, smooth edges.

    Operations:
    1. Opening (erosion→dilation): removes small noise blobs
    2. Closing (dilation→erosion): fills small holes
    """
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))

    # Remove small noise
    mask = cv2.morphologyEx(binary_mask, cv2.MORPH_OPEN, kernel, iterations=iterations)

    # Fill small holes
    mask = cv2.morphologyEx(binary_mask, cv2.MORPH_CLOSE, kernel, iterations=iterations)

    return mask
```

### Alternative: rembg (Simpler, Faster)

```python
# If SAM2 is overkill or uses too much VRAM alongside other tasks:
# pip install rembg

from rembg import remove
from PIL import Image
import numpy as np

def generate_masks_rembg(image_dir: str, output_dir: str) -> list:
    """Simple background removal using rembg (U2Net-based)."""
    from pathlib import Path

    image_path = Path(image_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    mask_paths = []
    for img_file in sorted(image_path.glob("*.jpg")):
        image = Image.open(img_file)
        output = remove(image)  # Returns RGBA

        # Extract alpha channel as mask
        alpha = np.array(output)[:, :, 3]
        binary_mask = (alpha > 128).astype(np.uint8) * 255

        mask_file = output_path / f"{img_file.stem}_mask.png"
        cv2.imwrite(str(mask_file), binary_mask)
        mask_paths.append(str(mask_file))

    return mask_paths
```

### SAM2 Gotchas

| Issue | Solution |
|-------|----------|
| Wrong object segmented (not the limb) | Use point prompt: `model(img, points=[[cx, cy]], labels=[1])` where (cx,cy) is on the limb |
| Out of VRAM | Use `sam2_hiera_tiny.pt` or resize images: `cv2.resize(img, (1024, 768))` |
| Memory leak in batch processing | Call `del results; torch.cuda.empty_cache()` between images |
| Jagged mask edges | Increase `kernel_size` in cleanup to 9 or 11 |

---

## 2. PyTorch3D Differentiable Refinement (Sprint 6)

### When to Use This
Only if COLMAP mesh accuracy is insufficient (>3mm error). Test COLMAP alone first. This adds complexity and may not be needed.

### Camera Conversion: COLMAP → PyTorch3D

```python
import torch
import numpy as np
import cv2

def colmap_cameras_to_pytorch3d(
    colmap_sparse_dir: str,
    device: torch.device = torch.device("cuda:0"),
):
    """
    Convert COLMAP camera output to PyTorch3D PerspectiveCameras.

    COORDINATE SYSTEM DIFFERENCE:
    - COLMAP: X-right, Y-down, Z-forward
    - PyTorch3D: X-left, Y-up, Z-into-screen

    We need to flip Y and Z when converting.

    Returns:
        cameras: PyTorch3D PerspectiveCameras
        image_names: List of image filenames (in same order)
    """
    from pytorch3d.renderer import PerspectiveCameras

    # Parse COLMAP output (using functions from Sprint 1-2 guide)
    cameras_data = read_colmap_cameras(f"{colmap_sparse_dir}/cameras.txt")
    images_data = read_colmap_images(f"{colmap_sparse_dir}/images.txt")

    R_list = []
    T_list = []
    focal_list = []
    pp_list = []
    image_names = []
    image_sizes = []

    # Flip matrix: COLMAP → PyTorch3D coordinate convention
    flip = np.array([[1, 0, 0], [0, -1, 0], [0, 0, -1]], dtype=np.float32)

    for image_id in sorted(images_data.keys()):
        img = images_data[image_id]
        cam = cameras_data[img["camera_id"]]

        # Intrinsics
        params = cam["params"]
        fx, fy, cx, cy = params[0], params[1], params[2], params[3]

        # Extrinsics: COLMAP quaternion → rotation matrix
        R_colmap = quat_to_rotmat(img["quat"])  # 3x3
        t_colmap = img["tvec"]  # (3,)

        # Convert to PyTorch3D convention
        # 1. Flip Y and Z axes
        R_pt3d = flip @ R_colmap @ flip  # Conjugate flip
        T_pt3d = flip @ t_colmap

        # 2. PyTorch3D uses transposed R: X_cam = X_world @ R^T + T
        R_pt3d = R_pt3d.T

        R_list.append(torch.from_numpy(R_pt3d).float())
        T_list.append(torch.from_numpy(T_pt3d).float())
        focal_list.append([fx, fy])
        pp_list.append([cx, cy])
        image_names.append(img["name"])
        image_sizes.append([cam["width"], cam["height"]])

    # Stack into batches
    R = torch.stack(R_list).to(device)
    T = torch.stack(T_list).to(device)
    focal_length = torch.tensor(focal_list, dtype=torch.float32, device=device)
    principal_point = torch.tensor(pp_list, dtype=torch.float32, device=device)
    image_size = torch.tensor(image_sizes, dtype=torch.float32, device=device)

    cameras = PerspectiveCameras(
        focal_length=focal_length,
        principal_point=principal_point,
        R=R,
        T=T,
        image_size=image_size,
        device=device,
    )

    return cameras, image_names
```

### Silhouette Optimization Loop

```python
import torch
import numpy as np
from pytorch3d.structures import Meshes
from pytorch3d.renderer import (
    MeshRenderer, MeshRasterizer, RasterizationSettings,
    SoftSilhouetteShader,
)
from pytorch3d.loss import (
    mesh_laplacian_smoothing,
    mesh_edge_loss,
    mesh_normal_consistency,
)
from pytorch3d.io import load_objs_as_meshes, save_obj
from tqdm import tqdm

def refine_mesh_with_silhouettes(
    mesh_path: str,
    masks_dir: str,
    colmap_sparse_dir: str,
    output_path: str,
    num_iterations: int = 500,
    image_size: int = 256,
    device_str: str = "cuda:0",
):
    """
    Refine a COLMAP mesh using differentiable silhouette rendering.

    Takes the rough COLMAP mesh and optimizes vertex positions so that
    rendered silhouettes match the SAM2 masks from each camera view.

    Args:
        mesh_path: Input mesh (OBJ format for PyTorch3D)
        masks_dir: Directory of binary mask PNGs (from SAM2)
        colmap_sparse_dir: COLMAP sparse reconstruction directory
        output_path: Where to save refined mesh
        num_iterations: Optimization iterations (300-1000 typical)
        image_size: Render resolution (lower = faster, 128-512)
    """
    device = torch.device(device_str)

    # === Load mesh ===
    # PyTorch3D loads OBJ natively
    mesh = load_objs_as_meshes([mesh_path], device=device)

    # === Load cameras ===
    cameras, image_names = colmap_cameras_to_pytorch3d(
        colmap_sparse_dir, device=device
    )
    num_views = len(image_names)

    # === Load target silhouettes ===
    import cv2
    from pathlib import Path

    target_silhouettes = []
    masks_path = Path(masks_dir)

    for name in image_names:
        stem = Path(name).stem
        mask_file = masks_path / f"{stem}_mask.png"

        if not mask_file.exists():
            print(f"WARNING: No mask for {name}, using blank")
            mask = np.zeros((image_size, image_size), dtype=np.float32)
        else:
            mask = cv2.imread(str(mask_file), cv2.IMREAD_GRAYSCALE)
            mask = cv2.resize(mask, (image_size, image_size))
            mask = mask.astype(np.float32) / 255.0

        target_silhouettes.append(
            torch.from_numpy(mask).unsqueeze(0).to(device)  # (1, H, W)
        )

    # === Setup renderer ===
    sigma = 1e-4
    raster_settings = RasterizationSettings(
        image_size=image_size,
        blur_radius=np.log(1.0 / sigma - 1.0) * sigma,
        faces_per_pixel=50,
    )

    renderer = MeshRenderer(
        rasterizer=MeshRasterizer(raster_settings=raster_settings),
        shader=SoftSilhouetteShader(),
    )

    # === Setup optimization ===
    # Learnable vertex deformations (NOT the vertices themselves)
    verts_shape = mesh.verts_packed().shape
    deform_verts = torch.zeros(verts_shape, device=device, requires_grad=True)

    optimizer = torch.optim.Adam([deform_verts], lr=0.005)

    # === Loss weights (coarse-to-fine schedule) ===
    def get_weights(iteration, total):
        """Higher regularization early, more silhouette weight later."""
        progress = iteration / total
        if progress < 0.3:
            return {"sil": 1.0, "lap": 2.0, "edge": 1.0, "normal": 0.05}
        elif progress < 0.7:
            return {"sil": 1.0, "lap": 1.0, "edge": 1.0, "normal": 0.01}
        else:
            return {"sil": 2.0, "lap": 0.5, "edge": 0.5, "normal": 0.005}

    # === Optimization loop ===
    views_per_iter = 2  # Random views per iteration
    best_loss = float("inf")

    print(f"Refining mesh: {num_iterations} iterations, "
          f"{num_views} views, {image_size}px resolution")

    for iteration in tqdm(range(num_iterations)):
        optimizer.zero_grad()

        # Deform mesh
        new_mesh = mesh.offset_verts(deform_verts)

        # Sample random views
        view_indices = np.random.choice(num_views, views_per_iter, replace=False)

        # Silhouette loss
        sil_loss = torch.tensor(0.0, device=device)
        for idx in view_indices:
            # Set camera for this view
            cam_i = cameras[idx]
            renderer.rasterizer.cameras = cam_i

            # Render silhouette
            images = renderer(new_mesh)
            predicted = images[..., 3]  # Alpha channel: (1, H, W)

            # L2 loss against target mask
            sil_loss += ((predicted - target_silhouettes[idx]) ** 2).mean()

        sil_loss /= views_per_iter

        # Regularization losses
        lap_loss = mesh_laplacian_smoothing(new_mesh, method="uniform")
        edge_loss = mesh_edge_loss(new_mesh)
        normal_loss = mesh_normal_consistency(new_mesh)

        # Weighted total
        w = get_weights(iteration, num_iterations)
        total_loss = (
            w["sil"] * sil_loss +
            w["lap"] * lap_loss +
            w["edge"] * edge_loss +
            w["normal"] * normal_loss
        )

        # Backprop with gradient clipping
        total_loss.backward()
        torch.nn.utils.clip_grad_norm_([deform_verts], max_norm=1.0)
        optimizer.step()

        # Track best
        if total_loss.item() < best_loss:
            best_loss = total_loss.item()

        # Log every 50 iterations
        if (iteration + 1) % 50 == 0:
            print(f"  Iter {iteration+1}: total={total_loss.item():.6f} "
                  f"sil={sil_loss.item():.6f} lap={lap_loss.item():.6f}")

        # Health check: detect divergence
        if torch.isnan(total_loss) or total_loss.item() > 100:
            print(f"WARNING: Loss exploded at iteration {iteration}. Stopping.")
            break

    # === Save refined mesh ===
    final_mesh = mesh.offset_verts(deform_verts.detach())
    verts = final_mesh.verts_packed().cpu()
    faces = final_mesh.faces_packed().cpu()
    save_obj(output_path, verts, faces)
    print(f"Saved refined mesh to {output_path}")
```

### PyTorch3D Gotchas

| Issue | Cause | Fix |
|-------|-------|-----|
| All-black silhouettes | Normals pointing away from camera | Check mesh orientation; try `mesh.fix_normals()` before loading |
| Vertices explode | Learning rate too high | Reduce to 0.001 or 0.0005; increase gradient clipping |
| Loss doesn't decrease | Camera conversion wrong | Render from one camera, compare visually to actual photo |
| CUDA out of memory | Image resolution too high | Reduce `image_size` to 128; reduce `faces_per_pixel` to 25 |
| "sm_120 not supported" | PyTorch too old for RTX 5060 Ti | Upgrade to PyTorch 2.7+ with CUDA 12.8 |
| Loss oscillates | Conflicting loss terms | Reduce `normal` weight; increase `edge` weight |

---

## 3. Texture Mapping (Sprint 7)

### Per-Vertex Color from Multi-View Photos

```python
import numpy as np
import cv2
import trimesh
from pathlib import Path

def texture_mesh_from_photos(
    mesh: trimesh.Trimesh,
    colmap_sparse_dir: str,
    image_dir: str,
    weight_by_angle: bool = True,
) -> np.ndarray:
    """
    Assign per-vertex RGB colors by projecting vertices onto photos.

    For each vertex:
    1. Project onto each camera view
    2. Check if projection is in-bounds and not behind camera
    3. Sample pixel color at projected location
    4. Blend colors across views (weighted by viewing angle)

    Args:
        mesh: 3D mesh (trimesh)
        colmap_sparse_dir: COLMAP output with cameras/images
        image_dir: Directory of original photos

    Returns:
        (N_vertices, 4) array of RGBA colors (uint8)
    """
    cameras = read_colmap_cameras(f"{colmap_sparse_dir}/cameras.txt")
    images = read_colmap_images(f"{colmap_sparse_dir}/images.txt")

    verts = mesh.vertices  # (N, 3)
    normals = mesh.vertex_normals  # (N, 3)
    n_verts = len(verts)

    # Accumulate colors + weights
    color_sum = np.zeros((n_verts, 3), dtype=np.float64)
    weight_sum = np.zeros(n_verts, dtype=np.float64)

    for image_id in sorted(images.keys()):
        img_data = images[image_id]
        cam_data = cameras[img_data["camera_id"]]

        # Load image
        img_path = Path(image_dir) / img_data["name"]
        if not img_path.exists():
            continue
        image = cv2.imread(str(img_path))  # BGR
        if image is None:
            continue
        h, w = image.shape[:2]

        # Camera parameters
        params = cam_data["params"]
        fx, fy, cx, cy = params[0], params[1], params[2], params[3]
        K = np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1]])

        R = quat_to_rotmat(img_data["quat"])
        t = img_data["tvec"]

        # Camera center in world coordinates
        cam_center = -R.T @ t

        # Project all vertices: pixel = K @ (R @ vertex + t)
        verts_cam = (R @ verts.T).T + t  # (N, 3) in camera coords

        # Skip vertices behind camera (z < 0)
        in_front = verts_cam[:, 2] > 0

        # Project to pixel coordinates
        px = fx * verts_cam[:, 0] / verts_cam[:, 2] + cx
        py = fy * verts_cam[:, 1] / verts_cam[:, 2] + cy

        # Check bounds
        in_bounds = (px >= 0) & (px < w - 1) & (py >= 0) & (py < h - 1)
        valid = in_front & in_bounds

        if not valid.any():
            continue

        # Compute viewing angle weight
        if weight_by_angle:
            # Direction from vertex to camera
            view_dirs = cam_center - verts  # (N, 3)
            view_dirs /= (np.linalg.norm(view_dirs, axis=1, keepdims=True) + 1e-8)

            # cos(angle) between surface normal and view direction
            cos_angles = np.sum(normals * view_dirs, axis=1)
            weights = np.maximum(cos_angles, 0)  # Only front-facing
        else:
            weights = np.ones(n_verts)

        # Sample colors at valid projections (bilinear interpolation)
        for i in np.where(valid)[0]:
            x, y = px[i], py[i]
            x0, y0 = int(x), int(y)

            # Simple nearest-neighbor sampling (bilinear is better but this works)
            bgr = image[y0, x0].astype(np.float64)
            rgb = bgr[::-1]  # BGR → RGB

            color_sum[i] += rgb * weights[i]
            weight_sum[i] += weights[i]

    # Average colors
    vertex_colors = np.zeros((n_verts, 4), dtype=np.uint8)
    has_color = weight_sum > 0

    vertex_colors[has_color, :3] = (
        color_sum[has_color] / weight_sum[has_color, np.newaxis]
    ).clip(0, 255).astype(np.uint8)
    vertex_colors[has_color, 3] = 255  # Alpha = opaque

    # Gray fallback for uncolored vertices
    vertex_colors[~has_color] = [128, 128, 128, 255]

    colored_pct = has_color.sum() / n_verts * 100
    print(f"Colored {colored_pct:.1f}% of vertices ({has_color.sum()}/{n_verts})")

    return vertex_colors

# === Apply to mesh and export ===
def export_colored_mesh(mesh, vertex_colors, output_path):
    """Export mesh with per-vertex colors as OBJ or PLY."""
    mesh.visual.vertex_colors = vertex_colors
    mesh.export(output_path)
    print(f"Saved colored mesh to {output_path}")

# Usage:
mesh = trimesh.load("forearm_refined.stl")
colors = texture_mesh_from_photos(
    mesh,
    colmap_sparse_dir="colmap_workspace/sparse/0",
    image_dir="colmap_workspace/images",
)
export_colored_mesh(mesh, colors, "forearm_colored.ply")
```

### Color Calibration (Optional)

```python
def apply_white_balance_from_card(
    image: np.ndarray,
    card_region: tuple,  # (x1, y1, x2, y2) of white patch on color card
    target_white: tuple = (240, 240, 240),
) -> np.ndarray:
    """
    Simple white balance correction using a known white patch.

    Args:
        image: BGR image
        card_region: Bounding box of white patch on color calibration card
        target_white: Expected RGB value for white

    Returns:
        Color-corrected image
    """
    x1, y1, x2, y2 = card_region
    white_patch = image[y1:y2, x1:x2]
    measured_white = white_patch.mean(axis=(0, 1))  # BGR

    # Compute per-channel gain
    target_bgr = np.array(target_white[::-1], dtype=np.float64)
    gains = target_bgr / (measured_white + 1e-6)
    gains = np.clip(gains, 0.5, 2.0)  # Prevent extreme corrections

    corrected = image.astype(np.float64) * gains
    return np.clip(corrected, 0, 255).astype(np.uint8)
```

---

## 4. PolyJet Color Printing Notes

### Format Requirements
- **Vertex colors:** Export as PLY or VRML with per-vertex RGB
- **Texture atlas:** Export as OBJ + MTL + PNG texture (higher quality)
- **Stratasys GrabCAD Print** accepts both formats

### For a first prototype
Start with **per-vertex colors** (simpler). Only switch to UV texture atlas if the vertex color resolution is insufficient (visible triangular color artifacts on the print).

### Color Accuracy
PolyJet color reproduction is ~80-90% accurate under daylight. Don't expect perfect skin tone matching on the first print. Plan for at least one color correction iteration.

---

## 5. Sprint 6 Decision Gate

Before implementing differentiable refinement, answer this question:

**Does the COLMAP mesh (from Sprint 2) look like a forearm when you open it in a viewer?**

- **Yes, it's recognizable and within ~3mm:** Skip Sprint 6 entirely. COLMAP is sufficient. Move to Sprint 7 (texture).
- **It's close but has obvious bumps/holes:** Try increasing Poisson `depth` to 10-11, or capture more photos. Cheaper than implementing PyTorch3D.
- **It's clearly wrong or too noisy:** Implement Sprint 6.

The differentiable refinement is the most complex piece of code in the entire pipeline. Don't build it if you don't need it.

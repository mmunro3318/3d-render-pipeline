# Implementation Guide — Sprint 3-5
## Mesh Cleanup, Mirroring, Cavity Boolean, Clamshell Split, Print Prep
> Context doc for coding agents | HyperReal Prosthetic Cover Pipeline

---

## What These Sprints Build

**Sprint 3:** Mesh repair pipeline + watertight validation + accuracy measurement
**Sprint 4:** Mirror limb + cavity subtraction (shell - hardware = cover)
**Sprint 5:** Clamshell split + magnet pockets + print-ready STL export

**Input:** Raw mesh from COLMAP/Poisson (Sprint 2 output)
**Output:** Two watertight STL files (clamshell halves) ready for Stratasys PolyJet

---

## 1. Mesh Repair Pipeline (Sprint 3)

### The Repair Sequence (Order Matters!)

```python
import trimesh
import numpy as np

def full_mesh_repair(mesh: trimesh.Trimesh, verbose: bool = True) -> trimesh.Trimesh:
    """
    Complete repair pipeline for raw photogrammetry meshes.

    Run these steps in order:
    1. Remove degenerate faces (zero-area triangles)
    2. Fill holes (close boundary loops)
    3. Fix winding (consistent triangle vertex order)
    4. Fix normals (all pointing outward)

    Args:
        mesh: Input mesh (may be broken)
        verbose: Print progress

    Returns:
        Repaired mesh (watertight if possible)
    """
    if verbose:
        print(f"Input: {len(mesh.vertices)} verts, {len(mesh.faces)} faces, "
              f"watertight={mesh.is_watertight}")

    # Step 1: Remove degenerate faces (zero-area triangles cause Boolean failures)
    face_areas = mesh.area_faces
    valid_mask = face_areas > 1e-8
    removed = (~valid_mask).sum()
    if removed > 0:
        mesh.update_faces(valid_mask)
        if verbose:
            print(f"  Removed {removed} degenerate faces")

    # Step 2: Fill holes
    mesh.fill_holes()
    if verbose:
        print(f"  After fill_holes: watertight={mesh.is_watertight}")

    # Step 3: Fix winding (consistent triangle vertex ordering)
    mesh.fix_winding()

    # Step 4: Fix normals (all pointing outward)
    mesh.fix_normals()

    if verbose:
        print(f"Output: {len(mesh.vertices)} verts, {len(mesh.faces)} faces, "
              f"watertight={mesh.is_watertight}")

    return mesh
```

### Mesh Validation / QC Checks

```python
def validate_mesh_for_printing(
    mesh: trimesh.Trimesh,
    min_wall_mm: float = 1.5,
    expected_length_mm: tuple = (150, 400),  # Forearm range
) -> dict:
    """
    Quality control checks before proceeding to Boolean ops or printing.

    Returns dict of check results.
    """
    results = {}

    # 1. Watertight
    results["watertight"] = mesh.is_watertight

    # 2. Positive volume
    results["volume_mm3"] = mesh.volume
    results["volume_positive"] = mesh.volume > 0

    # 3. Bounds / dimensions
    bounds = mesh.bounds  # (2, 3) array: [min_xyz, max_xyz]
    extent = bounds[1] - bounds[0]  # Length along each axis
    results["extent_mm"] = extent.tolist()
    results["max_length_mm"] = extent.max()

    # Check dimensions are plausible for a limb
    results["dimensions_plausible"] = (
        expected_length_mm[0] <= extent.max() <= expected_length_mm[1]
    )

    # 4. No degenerate faces
    face_areas = mesh.area_faces
    results["degenerate_faces"] = (face_areas < 1e-8).sum()

    # 5. Triangle count (for printing)
    results["face_count"] = len(mesh.faces)
    results["vertex_count"] = len(mesh.vertices)

    # Print report
    for key, val in results.items():
        status = "PASS" if val not in (False, 0) else "FAIL"
        if key in ("watertight", "volume_positive", "dimensions_plausible"):
            status = "PASS" if val else "FAIL"
        print(f"  [{status}] {key}: {val}")

    return results
```

### Mesh Decimation (Reduce Triangle Count)

```python
def decimate_mesh(mesh: trimesh.Trimesh, target_faces: int = 100_000) -> trimesh.Trimesh:
    """
    Reduce triangle count while preserving shape.

    Photogrammetry meshes often have 500K+ faces. For Boolean ops and
    printing, 100K-200K is plenty. Fewer faces = faster Booleans.
    """
    if len(mesh.faces) <= target_faces:
        print(f"Mesh already has {len(mesh.faces)} faces (<= {target_faces}), skipping")
        return mesh

    # Use Open3D for better decimation quality
    import open3d as o3d

    mesh_o3d = o3d.geometry.TriangleMesh()
    mesh_o3d.vertices = o3d.utility.Vector3dVector(mesh.vertices)
    mesh_o3d.triangles = o3d.utility.Vector3iVector(mesh.faces)

    decimated = mesh_o3d.simplify_quadric_decimation(
        target_number_of_triangles=target_faces
    )

    result = trimesh.Trimesh(
        vertices=np.asarray(decimated.vertices),
        faces=np.asarray(decimated.triangles),
    )
    result.fix_normals()

    print(f"Decimated: {len(mesh.faces)} → {len(result.faces)} faces")
    return result
```

---

## 2. Mirroring (Sprint 4)

### Reflect Mesh Across Sagittal Plane

```python
from trimesh.transformations import reflection_matrix

def mirror_limb(
    mesh: trimesh.Trimesh,
    axis: str = "x",
) -> trimesh.Trimesh:
    """
    Mirror a limb mesh for prosthetic cover design.

    The sound (healthy) limb is mirrored to create the base shape
    for the prosthetic side cover.

    Args:
        mesh: Sound limb mesh (watertight)
        axis: "x" for sagittal (left/right), "y" for coronal, "z" for transverse

    Returns:
        Mirrored mesh with corrected normals

    IMPORTANT GOTCHA: Reflection reverses triangle winding order,
    which flips all normals. You MUST call fix_normals() after mirroring
    or all downstream operations (rendering, Booleans) will fail.
    """
    assert mesh.is_watertight, "Input mesh must be watertight before mirroring"

    # Define reflection plane through mesh center
    center = mesh.centroid
    normal_map = {"x": [1, 0, 0], "y": [0, 1, 0], "z": [0, 0, 1]}
    normal = normal_map[axis]

    # Create reflection transform
    reflect = reflection_matrix(point=center, normal=normal)

    # Apply
    mirrored = mesh.copy()
    mirrored.apply_transform(reflect)

    # CRITICAL: Fix normals after reflection!
    # Reflection flips face winding, making all normals point inward
    mirrored.fix_normals()

    assert mirrored.is_watertight, "Mirrored mesh lost watertightness!"

    return mirrored
```

---

## 3. Cavity Boolean Subtraction (Sprint 4)

### Create Clearance Cavity

```python
def create_clearance_cavity(
    shell_mesh: trimesh.Trimesh,
    hardware_mesh: trimesh.Trimesh,
    clearance_mm: float = 1.5,
) -> trimesh.Trimesh:
    """
    Subtract prosthetic hardware (with clearance) from shell interior.

    This creates the hollow space inside the cover where the prosthetic
    hardware fits.

    Args:
        shell_mesh: The outer cover shell (mirrored limb)
        hardware_mesh: The prosthetic hardware scan
        clearance_mm: Extra space around hardware for comfortable fit

    Returns:
        Shell with internal cavity

    PREREQUISITES:
    - Both meshes must be watertight
    - Both must be in the same coordinate system and scale (mm)
    - Hardware must be INSIDE the shell (overlapping)
    """
    # Validate inputs
    assert shell_mesh.is_watertight, "Shell must be watertight"
    assert hardware_mesh.is_watertight, "Hardware must be watertight"

    # Expand hardware by clearance amount (offset outward along normals)
    cavity_tool = hardware_mesh.copy()
    cavity_tool.vertices += cavity_tool.vertex_normals * clearance_mm

    # Boolean difference: shell - cavity_tool
    try:
        result = shell_mesh.difference(cavity_tool, engine="manifold")

        if result is None or len(result.vertices) == 0:
            raise RuntimeError("Boolean returned empty mesh")

        if not result.is_watertight:
            print("WARNING: Result not watertight after boolean. Repairing...")
            result.fill_holes()
            result.fix_normals()

        print(f"Cavity created: {len(result.faces)} faces, "
              f"watertight={result.is_watertight}")
        return result

    except Exception as e:
        print(f"Manifold boolean failed: {e}")
        print("Trying blender engine as fallback...")

        try:
            result = shell_mesh.difference(cavity_tool, engine="blender")
            result.fix_normals()
            return result
        except Exception as e2:
            raise RuntimeError(
                f"All boolean engines failed. "
                f"Check that both meshes are watertight and overlapping. "
                f"Manifold error: {e}, Blender error: {e2}"
            )
```

### Dummy Hardware for Forearm Prototype

```python
def create_dummy_hardware(
    shell_mesh: trimesh.Trimesh,
    scale_factor: float = 0.7,
) -> trimesh.Trimesh:
    """
    Create a simple cylindrical 'dummy hardware' for prototyping.

    For the forearm prototype, we don't have real prosthetic hardware.
    This creates a cylinder roughly 70% the size of the shell,
    centered inside it, to simulate the cavity subtraction.
    """
    # Get shell dimensions
    bounds = shell_mesh.bounds
    extent = bounds[1] - bounds[0]
    center = shell_mesh.centroid

    # Create cylinder along the longest axis
    longest_axis = np.argmax(extent)
    height = extent[longest_axis] * 0.9  # Slightly shorter than shell

    # Estimate radius from the other two axes
    other_axes = [i for i in range(3) if i != longest_axis]
    radius = min(extent[other_axes]) * scale_factor / 2

    dummy = trimesh.creation.cylinder(
        radius=radius,
        height=height,
        sections=32,
    )

    # Align cylinder with the shell's longest axis
    if longest_axis == 0:  # X-axis
        # Rotate 90° around Y
        from trimesh.transformations import rotation_matrix
        dummy.apply_transform(rotation_matrix(np.pi/2, [0, 1, 0]))
    elif longest_axis == 1:  # Y-axis
        # Already aligned (default cylinder is along Z, but let's be safe)
        from trimesh.transformations import rotation_matrix
        dummy.apply_transform(rotation_matrix(np.pi/2, [1, 0, 0]))
    # Z-axis: cylinder is already along Z by default

    # Center on the shell
    from trimesh.transformations import translation_matrix
    dummy.apply_transform(translation_matrix(center))

    print(f"Dummy hardware: radius={radius:.1f}mm, height={height:.1f}mm")
    return dummy
```

### Boolean Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| "Boolean returned empty mesh" | Hardware not inside shell | Check alignment — hardware must overlap with shell |
| RuntimeError from Manifold3D | Non-watertight input | Run `full_mesh_repair()` on both meshes first |
| Result has inverted normals | Boolean flipped orientation | Call `result.fix_normals()` |
| Result has thin walls (<1mm) | Clearance too large | Reduce `clearance_mm` or thicken the shell |
| Very slow (>5 min) | Too many triangles | Decimate both meshes to 50K-100K faces first |
| "Self-intersections" error | Offset created overlapping faces | Use smaller clearance, or repair hardware mesh |

---

## 4. Clamshell Split (Sprint 5)

### Split Mesh Into Two Halves

```python
def split_clamshell(
    mesh: trimesh.Trimesh,
    split_axis: str = "x",
    split_offset: float = 0.0,
) -> tuple:
    """
    Split a prosthetic cover into two clamshell halves.

    Args:
        mesh: Watertight cover mesh
        split_axis: Which axis to split along ("x", "y", or "z")
        split_offset: Offset from centroid along split axis (mm)

    Returns:
        (half_a, half_b): Two watertight trimesh objects

    The `cap=True` parameter in slice_mesh_plane automatically
    triangulates the cut face, keeping both halves watertight.
    """
    assert mesh.is_watertight, "Input mesh must be watertight"

    # Define cutting plane
    center = mesh.centroid.copy()
    center_offset = center.copy()

    normal_map = {"x": [1, 0, 0], "y": [0, 1, 0], "z": [0, 0, 1]}
    plane_normal = np.array(normal_map[split_axis], dtype=np.float64)

    # Apply offset
    center_offset += plane_normal * split_offset

    # Cut: positive half (toward normal direction)
    half_a = trimesh.intersections.slice_mesh_plane(
        mesh,
        plane_normal=plane_normal,
        plane_origin=center_offset,
        cap=True,  # CRITICAL: cap=True closes the cut face
    )

    # Cut: negative half (away from normal)
    half_b = trimesh.intersections.slice_mesh_plane(
        mesh,
        plane_normal=-plane_normal,
        plane_origin=center_offset,
        cap=True,
    )

    # Verify both halves
    for name, half in [("A", half_a), ("B", half_b)]:
        half.fix_normals()
        print(f"Half {name}: {len(half.faces)} faces, "
              f"watertight={half.is_watertight}, "
              f"volume={half.volume:.2f}")

    return half_a, half_b
```

### Add Magnet Pockets

```python
from trimesh.transformations import translation_matrix

def add_magnet_pockets(
    mesh_half: trimesh.Trimesh,
    pocket_positions: list,
    magnet_radius_mm: float = 5.0,
    magnet_depth_mm: float = 4.0,
) -> trimesh.Trimesh:
    """
    Carve cylindrical magnet pockets into a clamshell half.

    Args:
        mesh_half: One clamshell half (watertight)
        pocket_positions: List of [x, y, z] coordinates for pocket centers
            These should be ON or slightly inside the split face
        magnet_radius_mm: Radius of magnet (plus ~0.2mm tolerance)
        magnet_depth_mm: Depth of pocket (magnet thickness + 1mm backing)

    Returns:
        Mesh with magnet pockets carved in

    TIPS:
    - Pocket positions should be on the FLAT SPLIT FACE
    - Leave at least 1mm of material behind the pocket
    - Place pockets at diagonal corners for alignment
    - Use magnet_radius + 0.2mm for tolerance
    """
    result = mesh_half.copy()

    for i, pos in enumerate(pocket_positions):
        pocket = trimesh.creation.cylinder(
            radius=magnet_radius_mm,
            height=magnet_depth_mm,
            sections=32,
        )

        pocket.apply_transform(translation_matrix(pos))

        try:
            result = result.difference(pocket, engine="manifold")

            if not result.is_watertight:
                result.fill_holes()
                result.fix_normals()

            print(f"  Pocket {i+1} at {pos}: OK")

        except Exception as e:
            print(f"  Pocket {i+1} FAILED: {e}")
            print("  Skipping this pocket — add manually in CAD")

    return result
```

### Add Registration Pins (Optional)

```python
def add_registration_features(
    half_a: trimesh.Trimesh,
    half_b: trimesh.Trimesh,
    pin_positions: list,
    pin_radius_mm: float = 3.0,
    pin_height_mm: float = 3.0,
) -> tuple:
    """
    Add registration pins to half_a and matching holes to half_b.

    These help the two halves align correctly during assembly.

    Args:
        half_a: First clamshell half (will get pins ADDED)
        half_b: Second clamshell half (will get holes SUBTRACTED)
        pin_positions: [x, y, z] coordinates on the split face
    """
    result_a = half_a.copy()
    result_b = half_b.copy()

    for pos in pin_positions:
        # Create pin cylinder
        pin = trimesh.creation.cylinder(
            radius=pin_radius_mm,
            height=pin_height_mm,
            sections=32,
        )
        pin.apply_transform(translation_matrix(pos))

        # Create hole (slightly larger for tolerance)
        hole = trimesh.creation.cylinder(
            radius=pin_radius_mm + 0.2,  # 0.2mm clearance
            height=pin_height_mm + 0.5,
            sections=32,
        )
        hole.apply_transform(translation_matrix(pos))

        # Add pin to half_a (union)
        try:
            result_a = trimesh.boolean.union([result_a, pin], engine="manifold")
        except Exception:
            print(f"Pin union failed at {pos}, skipping")

        # Subtract hole from half_b (difference)
        try:
            result_b = result_b.difference(hole, engine="manifold")
        except Exception:
            print(f"Hole subtraction failed at {pos}, skipping")

    return result_a, result_b
```

---

## 5. Wall Thickness Validation

```python
def check_wall_thickness(
    mesh: trimesh.Trimesh,
    num_samples: int = 500,
    min_thickness_mm: float = 1.5,
) -> dict:
    """
    Estimate wall thickness using ray casting.

    Shoots rays inward from surface points and measures
    distance to the opposite wall.

    Returns dict with thickness statistics.
    """
    # Sample points on the surface
    points, face_indices = trimesh.sample.sample_surface(mesh, num_samples)
    normals = mesh.face_normals[face_indices]

    # Shoot rays inward
    origins = points - normals * 0.01  # Slight inward offset
    directions = -normals  # Inward direction

    # Find intersections
    locations, index_ray, index_tri = mesh.ray.intersects_location(
        ray_origins=origins,
        ray_directions=directions,
    )

    # Compute distances (thickness at each sample point)
    thicknesses = []
    for i in range(num_samples):
        hits = locations[index_ray == i]
        if len(hits) > 0:
            # Distance from surface point to nearest internal hit
            dists = np.linalg.norm(hits - points[i], axis=1)
            # Take the first hit that's > 0.1mm (skip self-intersection)
            valid_dists = dists[dists > 0.1]
            if len(valid_dists) > 0:
                thicknesses.append(valid_dists.min())

    thicknesses = np.array(thicknesses)

    report = {
        "mean_mm": thicknesses.mean() if len(thicknesses) > 0 else 0,
        "min_mm": thicknesses.min() if len(thicknesses) > 0 else 0,
        "max_mm": thicknesses.max() if len(thicknesses) > 0 else 0,
        "std_mm": thicknesses.std() if len(thicknesses) > 0 else 0,
        "samples_measured": len(thicknesses),
        "thin_spots": (thicknesses < min_thickness_mm).sum() if len(thicknesses) > 0 else 0,
    }

    print(f"Wall thickness: {report['min_mm']:.1f} - {report['max_mm']:.1f}mm "
          f"(mean: {report['mean_mm']:.1f}mm)")

    if report["thin_spots"] > 0:
        pct = report["thin_spots"] / report["samples_measured"] * 100
        print(f"WARNING: {report['thin_spots']} samples ({pct:.0f}%) "
              f"below {min_thickness_mm}mm minimum")

    return report
```

---

## 6. Export for 3D Printing

```python
def export_for_printing(
    mesh: trimesh.Trimesh,
    output_path: str,
    units: str = "mm",
):
    """
    Export mesh as binary STL for 3D printing.

    CRITICAL NOTES:
    - STL files have NO unit information. The printer interprets
      coordinates as whatever unit is configured.
    - Stratasys GrabCAD Print defaults to millimeters.
    - Verify your mesh coordinates are in mm before exporting!

    Sanity check: A forearm cover should be roughly:
      - Length: 200-350mm
      - Width: 60-100mm
      - Wall thickness: 1.5-3mm
    """
    # Final validation
    assert mesh.is_watertight, "Cannot export non-watertight mesh for printing!"
    assert mesh.volume > 0, "Mesh has non-positive volume!"

    bounds = mesh.bounds
    extent = bounds[1] - bounds[0]
    print(f"Mesh dimensions: {extent[0]:.1f} x {extent[1]:.1f} x {extent[2]:.1f} {units}")
    print(f"Volume: {mesh.volume:.1f} {units}³")
    print(f"Faces: {len(mesh.faces)}")

    # Export as binary STL (most compatible with 3D printers)
    mesh.export(output_path)
    print(f"Exported to {output_path}")
```

---

## 7. Key Gotchas Summary

| Operation | Gotcha | Solution |
|-----------|--------|----------|
| **Mirroring** | Flips all normals (face winding reversal) | Always call `fix_normals()` after mirroring |
| **Boolean difference** | Fails if inputs aren't watertight | Validate `.is_watertight` before every Boolean |
| **Boolean difference** | Fails if meshes don't overlap | Verify hardware mesh is INSIDE shell mesh |
| **Vertex normal offset** | Can create self-intersections on concave regions | Keep clearance small (1-2mm), repair after |
| **Mesh splitting** | May not produce watertight halves without `cap=True` | Always use `cap=True` in `slice_mesh_plane` |
| **Magnet pockets** | Must be on the split face, not floating in space | Calculate positions from split plane geometry |
| **STL export** | No unit information in file | Document that all coordinates are in mm |
| **Large meshes** | Booleans slow or fail on >500K faces | Decimate to 100K-200K before Booleans |
| **Scale mismatch** | Meshes in different units (m vs mm) | Normalize everything to mm early in pipeline |

# Approach C: Blender-Assisted Pipeline (Weekend Experiment)

> This is a standalone experiment — NOT part of the main 3d-render-pipeline-core repo.
> Create a separate directory or repo for this work.

## Goal

Build a set of Blender Python scripts that take a Structure Sensor scan of a residual limb and produce two print-ready STL halves (clamshell prosthetic cover) with magnet pockets. Semi-automated — human runs scripts in Blender and reviews each step visually.

## Context

- **Patient:** Above-knee amputee
- **Input data available:**
  - Structure Sensor scan of the patient's residual limb (PLY/OBJ with textures)
  - Structure Sensor scan of the patient's existing prosthetic hardware
  - ~10 photos of the limb (front, left, right, back, off-angles, close-ups with color cards)
  - A manually cleaned Blender version of the limb scan (UV mapping was lost during deformation)
- **Output:** Two binary STL files (top half + bottom half) ready for Stratasys PolyJet printer
- **Print constraints (non-negotiable):**
  - Watertight meshes (no holes, no open edges)
  - Wall thickness >= 1.5mm everywhere (target 2-2.5mm)
  - Triangle count: 100K-300K per half
  - No degenerate geometry (flipped normals, T-junctions, duplicate verts)

## Script Sequence

Build each as a standalone Blender Python script. The operator runs them in order in Blender.

### Script 1: `01_import_and_repair.py`
- Import the Structure Sensor limb scan (PLY or OBJ)
- Clean up: remove duplicate vertices, recalculate normals, fill small holes
- Smooth mesh (Laplacian smooth, low iterations to preserve shape)
- Decimate to ~200K triangles if over 300K
- **Visual checkpoint:** Operator reviews the cleaned mesh in Blender viewport

### Script 2: `02_mirror.py`
- Mirror the mesh across the YZ plane (sagittal plane) for contralateral limb
- This is the simplest step — Blender's mirror modifier handles it
- If the scan is of the affected limb and we want a cover matching the sound limb, mirror
- If the scan IS the sound limb, this step produces the cover shape for the affected side
- **Visual checkpoint:** Operator verifies mirror looks correct

### Script 3: `03_cavity_boolean.py`
- Import the prosthetic hardware scan
- Position it inside the limb mesh (may need manual alignment by operator)
- Add a solidify modifier to the limb mesh (2mm thickness) to create the shell
- Boolean difference: subtract the prosthetic hardware from the shell interior
- This creates a hollow cover that fits OVER the prosthetic
- **Visual checkpoint:** Operator verifies the cavity looks right, hardware clears the inner wall
- **Fallback:** If boolean fails (common with messy meshes), try:
  1. Remesh both meshes at a consistent resolution before boolean
  2. Use Blender's "Exact" boolean solver instead of "Fast"
  3. Manual cleanup of boolean artifacts in edit mode

### Script 4: `04_split_and_magnets.py`
- Split the cover into two halves along a cutting plane (default: sagittal plane, operator adjustable)
- On each split face, add alignment peg geometry (one half gets pegs, other gets matching holes)
- Subtract magnet pocket cylinders from each split face (6-8mm diameter, 4mm deep — check config)
- Ensure both halves are individually watertight after split (cap the cut faces)
- **Visual checkpoint:** Operator reviews split, pegs, and magnet pockets

### Script 5: `05_validate_and_export.py`
- Run validation checks on each half:
  - Is it watertight? (mesh.is_manifold in Blender)
  - Triangle count within range?
  - No loose vertices or edges?
  - Approximate wall thickness check (ray cast from outside toward inside)
- Export both halves as binary STL
- Print a summary report to Blender's console

## Blender Version

Use Blender 4.x (current stable). All scripts should use `bpy` and `bmesh` APIs.

## Key Blender Python Patterns

```python
import bpy
import bmesh

# Import mesh
bpy.ops.import_mesh.ply(filepath="path/to/scan.ply")

# Get active object
obj = bpy.context.active_object

# Switch to edit mode for bmesh operations
bpy.ops.object.mode_set(mode='EDIT')
bm = bmesh.from_edit_mesh(obj.data)

# Operations...
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.001)
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

# Update and free
bmesh.update_edit_mesh(obj.data)
bpy.ops.object.mode_set(mode='OBJECT')

# Export
bpy.ops.export_mesh.stl(filepath="output.stl", use_selection=True, ascii=False)
```

## Important Notes

- Always `bm.free()` after bmesh operations on non-edit-mode meshes
- Always `mesh.update()` after `from_pydata()`
- Use `from_pydata()` for creating new meshes (pegs, magnet pockets), bmesh for modifying
- Blender is Z-up. Structure Sensor scans may be Y-up — check and rotate on import
- For 10k+ face meshes, prefer bmesh over repeated `bpy.ops` calls (operator overhead)
- Boolean operations on noisy meshes WILL fail sometimes. The "Exact" solver in Blender 4.x is more reliable than "Fast" but slower

## What This Experiment Teaches Us

Even if the results are rough, this experiment answers:
1. Does Blender's boolean engine handle the cavity subtraction on real scan data?
2. What does the split + magnet pocket geometry actually look like?
3. How bad is the Structure Sensor scan quality really? (visual inspection in Blender)
4. What's the manual effort per patient with this approach? (time it)

These answers feed directly into the automated pipeline (Approach A) design.

## Not In Scope

- Texture mapping / color
- Automated capture validation
- Config file system
- Tests
- Any reconstruction from photos
- Production quality — this is a prototype weekend hack

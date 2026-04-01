
> Research compiled April 2026 for HyperReal prosthetic cover pipeline

## Overview

This document surveys every viable approach for going from **multi-view photos → accurate 3D mesh** suitable for prosthetic cover manufacturing. Methods are evaluated against the core requirement: **±1–2mm accuracy on organic limb geometry**, with watertight meshes suitable for Stratasys 3D printing.

---

## 1. Classical Photogrammetry (COLMAP + OpenMVS)

**How it works:** Structure-from-Motion (SfM) recovers camera poses from feature matching (SIFT/ORB). Multi-View Stereo (MVS) computes per-view depth maps and fuses them into a dense point cloud, then meshes via Poisson reconstruction.

**Maturity:** Industry-standard. Proven in production since the 2000s.

**Key tools:** COLMAP 4.1 (SfM), OpenMVS (MVS), Meshroom/AliceVision (GUI pipeline)

**Accuracy:**
- SIGGRAPH Asia 2024 paper "Millimetric Human Surface Capture in Minutes" reports **1.13mm average accuracy** with **77% of points within ±1mm**
- Bone reconstruction studies show 0.2–0.4mm mean absolute difference vs physical measurement

**Strengths:** Proven sub-mm accuracy, free software, works with any camera, produces watertight meshes via Poisson reconstruction.

**Weaknesses:** Struggles with textureless skin regions, requires controlled lighting, 80–200 overlapping images needed, 2–4 hour processing time.

**Prosthetic suitability:** **HIGHEST.** This is the gold standard.

**Key references:**
- [COLMAP docs](https://colmap.github.io/)
- [Millimetric Human Surface Capture (SIGGRAPH Asia 2024)](https://dl.acm.org/doi/10.1145/3680528.3687690)

---

## 2. Differentiable Rendering (Mike's Core Approach)

**How it works:** Start with a rough 3D mesh. Render it from camera angles matching photos. Compute loss (silhouette IoU, photometric error) between renders and actual photos. Backpropagate gradients to deform mesh vertices. Iterate.

**Maturity:** Production-ready libraries since 2019.

**Key libraries:**
- **nvdiffrast** (NVIDIA) — Low-level GPU rasterization, most performant
- **PyTorch3D** (Meta) — Full-featured, well-documented, active development
- **Kaolin** (NVIDIA) — Modular, integrates DIB-R/DIB-R++
- **SoftRas** (ICCV 2019) — Soft rasterization enabling gradients through occlusions

**Accuracy:** Silhouette-only loss produces ~5mm accuracy. Adding photometric + normal losses gets to **1–5mm** depending on initialization quality and tuning.

**Strengths:** Conceptually elegant, can refine any initial mesh, gradient-based convergence.

**Weaknesses:**
- **Local minima** — If initial shape is too far from target, optimization converges to wrong shape
- **Gradient instability** — Vertices near silhouette edges get huge gradients; mesh can oscillate or collapse
- **Limited convergence range** — Large pose/shape differences overwhelm gradients
- **Over-smoothing** — Regularization needed to prevent degenerate triangles washes out fine detail
- **Requires good camera poses** — Needs COLMAP or calibration first anyway

**Prosthetic suitability:** **MODERATE.** Best used as a refinement step on top of photogrammetry, not as standalone reconstruction.

**Key insight:** Differentiable rendering is excellent for *refining* a rough mesh, but poor at *creating* one from scratch. Starting from a sphere and pulling it into a leg shape is asking the optimizer to cross a vast loss landscape with many local minima.

**Key references:**
- [nvdiffrast](https://nvlabs.github.io/nvdiffrast/)
- [PyTorch3D renderer docs](https://pytorch3d.org/docs/renderer)
- [SoftRas (ICCV 2019)](https://github.com/ShichenLiu/SoftRas)

---

## 3. 3D Gaussian Splatting (3DGS)

**How it works:** Scene represented as a cloud of 3D Gaussians (position, covariance, color, opacity). Rendered via fast GPU rasterization. Gradients optimize Gaussian parameters to match multi-view images.

**Maturity:** Rapidly maturing (2023+). Becoming industry standard for real-time view synthesis.

**Key methods:**
- **3DGS (original, 2023)** — Real-time rendering (100+ FPS), trains in 7–30 minutes
- **SuGaR (CVPR 2024)** — **Critical for our use case.** Extracts meshes from Gaussians via Poisson reconstruction. Produces clean, detail-preserving, potentially watertight meshes.

**Accuracy:** Visual quality rivals NeRF. Geometric accuracy ~2–3mm for well-textured surfaces.

**Strengths:** Very fast training (7–30 min), real-time rendering, SuGaR provides good mesh extraction, cleaner edges than NeRF.

**Weaknesses:** Mesh extraction still not trivial, can struggle with fine structures, watertightness not guaranteed.

**Prosthetic suitability:** **HIGH** as part of hybrid pipeline. 3DGS + SuGaR for mesh extraction, combined with photogrammetry for initial poses.

---

## 4. Neural Radiance Fields (NeRF)

**How it works:** A neural network learns a 5D function (3D position + 2D view direction → RGB + density). Volume rendering synthesizes novel views. Geometry is implicit in the density field.

**Maturity:** Research-to-production (2020+).

**Key methods:** Instant-NGP (1000x faster than vanilla NeRF), Nerfacto (Nerfstudio), NeuManifold (WACV 2025 — watertight mesh extraction).

**Accuracy:** Excellent for view synthesis, but geometric accuracy is poor (~1cm). Mesh extraction via Marching Cubes produces non-manifold, non-watertight meshes.

**Strengths:** Excellent texture/color capture, handles complex lighting.

**Weaknesses:** Geometry is implicit (hard to extract clean mesh), poor mesh topology for 3D printing, requires good camera poses, GPU-intensive.

**Prosthetic suitability:** **MODERATE.** Good for texture capture but NOT for primary geometry. Use photogrammetry for shape, NeRF for color if needed.

---

## 5. Shape from Silhouette (Visual Hull)

**How it works:** Segment object silhouettes from multiple views. Backproject silhouettes into 3D space. Intersection of all cones = visual hull (conservative outer bound of object).

**Accuracy:** 5–10mm. Cannot represent concave surfaces (inner elbow, armpit).

**Prosthetic suitability:** **LOW.** Useful only as rough initialization for other methods.

---

## 6. AI Single/Few-Image 3D Reconstruction

**Methods:** PIFu/PIFuHD (2019/2020), ICON (2021), ECON (2023), Wonder3D (CVPR 2024), One-2-3-45.

**Accuracy:** 5–10mm at best. PIFu has known "broken limbs" problem. Wonder3D is best-in-class (Chamfer Distance 0.0199) but evaluated on synthetic data only.

**Prosthetic suitability:** **LOW.** Good for quick prototyping, not for manufacturing tolerance.

---

## 7. iPad LiDAR / Structure Sensor

**iPad Pro LiDAR accuracy:** 5mm best case (planar), 10–20mm typical (organic shapes), 20–50mm on complex anatomy.

**Structure Sensor:** Higher accuracy (~1–2mm) but now discontinued.

**Prosthetic suitability:** **LOW as primary capture.** Useful as rough initialization or depth prior.

---

## Method Comparison Matrix

| Method | Accuracy | Mesh Quality | Speed | Maturity | Prosthetic Fit |
|--------|----------|-------------|-------|----------|----------------|
| Photogrammetry (COLMAP+MVS) | 1.13mm | Excellent | 2–3h | Industry std | **Highest** |
| Structured-light scanner | 0.25–1mm | Excellent | 15min | Industry std | **Highest** |
| 3DGS + SuGaR | 2–3mm | Very good | 30min–2h | Mature | **High** |
| Differentiable rendering | 1–5mm | Good | 1–2h | Mature | Moderate |
| NeRF + mesh extract | ~1cm | Poor topology | 1–2h | Mature | Moderate |
| Visual hull | 5–10mm | Fair | 30min | Established | Low |
| iPad LiDAR | 10–20mm | Poor | 15min | Commercial | Low |
| Wonder3D / ECON | 5–10mm | Fair | 30min | Emerging | Low |

---

## Texture Mapping

**State of the art (2024):**
- **TexPainter (SIGGRAPH 2024)** — Multi-view consistent texture optimization via gradient backpropagation
- **TEGLO (WACV 2024)** — Tri-plane representation for arbitrary resolution textures

**Color calibration:** Macbeth/X-Rite color chart in every shot. Calibrate all images to canonical color space. Sub-1% color error (ΔE < 2) achievable with proper calibration.

**Key point:** The cheap Amazon color card Mike has should work if it's a standard 24-patch card and used consistently.

---

## Prosthetic Manufacturing Tolerances

| Aspect | Tolerance |
|--------|-----------|
| Socket fit (residual limb) | ±0.5–1mm |
| Prosthetic alignment | ±1–2mm |
| **Cosmetic cover fit** | **±2–3mm** |
| Fine anatomical features | ±1mm desirable |

**Our target (cosmetic cover):** ±2–3mm is achievable with photogrammetry or 3DGS hybrid approaches.

---

## Recommended Pipeline Architecture

### Primary: Photogrammetry + Differentiable Refinement

```
Photos (80-200 images, color card)
    ↓
COLMAP (SfM → camera poses)
    ↓
OpenMVS or 3DGS+SuGaR (dense reconstruction → mesh)
    ↓
Differentiable rendering refinement (optional, if accuracy insufficient)
    ↓
Texture optimization (multi-view blending)
    ↓
Watertight mesh (Poisson reconstruction)
    ↓
Export for 3D printing
```

### Why this over pure differentiable rendering:
1. Photogrammetry gives you a **strong initialization** — no local minima problem
2. Differentiable rendering refines where photogrammetry is noisy
3. You get camera poses for free from COLMAP (needed regardless)
4. Proven accuracy meets prosthetic tolerances

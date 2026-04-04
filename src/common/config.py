"""Pydantic v2 configuration loader for the HyperReal pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from loguru import logger
from pydantic import BaseModel, field_validator, model_validator


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

class LimbProfile(BaseModel):
    """Limb-specific geometry and print parameters."""

    limb_type: str
    expected_length_mm: tuple[float, float]
    expected_diameter_mm: tuple[float, float]
    split_plane_axis: Literal["sagittal", "coronal"]
    split_plane_offset_mm: float = 0.0
    cavity_model: Path | None = None
    cavity_clearance_mm: float
    magnet_pocket_diameter_mm: float
    magnet_pocket_depth_mm: float
    wall_thickness_target_mm: float
    wall_thickness_min_mm: float

    @field_validator("expected_length_mm", "expected_diameter_mm")
    @classmethod
    def _range_must_be_positive_and_ordered(
        cls, value: tuple[float, float],
    ) -> tuple[float, float]:
        """Validates that range bounds are positive and min <= max."""
        low, high = value
        if low < 0 or high < 0:
            msg = f"Range values must be non-negative, got ({low}, {high})"
            raise ValueError(msg)
        if low > high:
            msg = f"Range minimum ({low}) exceeds maximum ({high})"
            raise ValueError(msg)
        return value


class CaptureConfig(BaseModel):
    """Photo capture quality-gate parameters."""

    min_images: int
    max_images: int
    min_laplacian_variance: float
    min_resolution: tuple[int, int]
    min_features_per_image: int
    min_pairwise_matches: int

    @field_validator("min_images", "max_images", "min_features_per_image", "min_pairwise_matches")
    @classmethod
    def _must_be_positive(cls, value: int) -> int:
        """Validates that integer fields are strictly positive."""
        if value <= 0:
            msg = f"Value must be positive, got {value}"
            raise ValueError(msg)
        return value

    @field_validator("min_laplacian_variance")
    @classmethod
    def _variance_must_be_positive(cls, value: float) -> float:
        """Validates that Laplacian variance threshold is positive."""
        if value <= 0:
            msg = f"Laplacian variance must be positive, got {value}"
            raise ValueError(msg)
        return value


class ColmapConfig(BaseModel):
    """COLMAP reconstruction parameters and quality gates."""

    camera_model: str
    max_reprojection_error: float
    min_registered_ratio: float
    min_3d_points: int

    @field_validator("min_3d_points")
    @classmethod
    def _points_must_be_positive(cls, value: int) -> int:
        """Validates that minimum 3D points is positive."""
        if value <= 0:
            msg = f"min_3d_points must be positive, got {value}"
            raise ValueError(msg)
        return value


class PoissonConfig(BaseModel):
    """Poisson surface reconstruction parameters."""

    depth: int
    min_density_percentile: float


# ---------------------------------------------------------------------------
# Root model
# ---------------------------------------------------------------------------

class PipelineConfig(BaseModel):
    """Top-level pipeline configuration aggregating all sub-configs."""

    capture: CaptureConfig
    colmap: ColmapConfig
    poisson: PoissonConfig
    limb_profiles: dict[str, LimbProfile]
    active_profile: str
    colmap_binary: Path

    @model_validator(mode="after")
    def _active_profile_must_exist(self) -> "PipelineConfig":
        """Validates that active_profile references an existing limb profile."""
        if self.active_profile not in self.limb_profiles:
            available = list(self.limb_profiles.keys())
            msg = (
                f"active_profile '{self.active_profile}' not found in "
                f"limb_profiles. Available: {available}"
            )
            raise ValueError(msg)
        return self


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def _inject_limb_type(raw: dict) -> dict:
    """Injects the profile key as 'limb_type' into each limb profile dict."""
    profiles = raw.get("limb_profiles", {})
    for key, profile in profiles.items():
        if isinstance(profile, dict):
            profile.setdefault("limb_type", key)
    return raw


def load_config(config_path: Path) -> PipelineConfig:
    """Loads YAML at *config_path* and returns a validated PipelineConfig."""
    if not config_path.exists():
        msg = f"Config file not found: {config_path}"
        raise FileNotFoundError(msg)

    logger.info("Loading pipeline config from {}", config_path)
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    if raw is None:
        msg = "Config file is empty or contains no YAML data"
        raise ValueError(msg)

    raw = _inject_limb_type(raw)
    config = PipelineConfig(**raw)
    logger.success("Config loaded — active profile: '{}'", config.active_profile)
    return config

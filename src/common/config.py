"""Pydantic v2 configuration loader for the HyperReal pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from loguru import logger
from pydantic import BaseModel, ConfigDict, field_validator, model_validator


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


class IntakeConfig(BaseModel):
    """Input mesh loading and contract validation parameters."""

    supported_formats: list[str] = ["obj", "stl"]
    max_faces: int = 500_000
    min_faces: int = 10_000
    warn_faces_high: int = 300_000
    warn_faces_low: int = 100_000


class RepairConfig(BaseModel):
    """Mesh repair parameters."""

    smooth_iterations: int = 3
    smooth_lambda: float = 0.5
    max_hole_edges: int = 100


class BooleanConfig(BaseModel):
    """Boolean subtraction parameters."""

    engine_preference: list[str] = ["manifold3d", "trimesh"]
    retry_after_repair: bool = True


class ExportConfig(BaseModel):
    """Export and validation parameters."""

    output_format: Literal["stl", "obj"] = "stl"
    debug_exports: bool = True
    debug_dir: str = "output/debug"


# ---------------------------------------------------------------------------
# Root model
# ---------------------------------------------------------------------------

class PipelineConfig(BaseModel):
    """Top-level pipeline configuration aggregating all sub-configs."""

    model_config = ConfigDict(extra="forbid")

    intake: IntakeConfig
    repair: RepairConfig
    boolean: BooleanConfig
    export: ExportConfig
    limb_profiles: dict[str, LimbProfile]
    active_profile: str

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

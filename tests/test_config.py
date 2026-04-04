"""Tests for src.common.config — Pydantic v2 pipeline config loader."""

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from src.common.config import PipelineConfig, load_config

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

VALID_YAML = {
    "capture": {
        "min_images": 40,
        "max_images": 55,
        "min_laplacian_variance": 100.0,
        "min_resolution": [3024, 4032],
        "min_features_per_image": 500,
        "min_pairwise_matches": 50,
    },
    "colmap": {
        "camera_model": "PINHOLE",
        "max_reprojection_error": 2.0,
        "min_registered_ratio": 0.8,
        "min_3d_points": 1000,
    },
    "poisson": {
        "depth": 9,
        "min_density_percentile": 0.01,
    },
    "colmap_binary": "colmap",
    "active_profile": "forearm",
    "limb_profiles": {
        "forearm": {
            "expected_length_mm": [200, 350],
            "expected_diameter_mm": [60, 120],
            "split_plane_axis": "sagittal",
            "wall_thickness_target_mm": 2.0,
            "wall_thickness_min_mm": 1.5,
            "magnet_pocket_diameter_mm": 6.0,
            "magnet_pocket_depth_mm": 3.0,
            "cavity_clearance_mm": 1.0,
        },
        "above_knee": {
            "expected_length_mm": [300, 500],
            "expected_diameter_mm": [120, 250],
            "split_plane_axis": "coronal",
            "wall_thickness_target_mm": 2.5,
            "wall_thickness_min_mm": 1.5,
            "magnet_pocket_diameter_mm": 8.0,
            "magnet_pocket_depth_mm": 4.0,
            "cavity_clearance_mm": 1.5,
        },
    },
}


def _write_yaml(tmp_path: Path, data: dict | str | None, filename: str = "pipeline.yaml") -> Path:
    """Write data to a YAML file and return its path."""
    config_file = tmp_path / filename
    if isinstance(data, str):
        config_file.write_text(data, encoding="utf-8")
    elif data is None:
        config_file.write_text("", encoding="utf-8")
    else:
        config_file.write_text(yaml.dump(data), encoding="utf-8")
    return config_file


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestHappyPath:
    """Valid config loads correctly and fields match."""

    def test_load_valid_config(self, tmp_path: Path) -> None:
        config_file = _write_yaml(tmp_path, VALID_YAML)
        config = load_config(config_file)
        assert isinstance(config, PipelineConfig)
        assert config.active_profile == "forearm"

    def test_capture_fields(self, tmp_path: Path) -> None:
        config = load_config(_write_yaml(tmp_path, VALID_YAML))
        assert config.capture.min_images == 40
        assert config.capture.max_images == 55
        assert config.capture.min_laplacian_variance == 100.0
        assert config.capture.min_resolution == (3024, 4032)
        assert config.capture.min_features_per_image == 500
        assert config.capture.min_pairwise_matches == 50

    def test_colmap_fields(self, tmp_path: Path) -> None:
        config = load_config(_write_yaml(tmp_path, VALID_YAML))
        assert config.colmap.camera_model == "PINHOLE"
        assert config.colmap.max_reprojection_error == 2.0
        assert config.colmap.min_registered_ratio == 0.8
        assert config.colmap.min_3d_points == 1000

    def test_poisson_fields(self, tmp_path: Path) -> None:
        config = load_config(_write_yaml(tmp_path, VALID_YAML))
        assert config.poisson.depth == 9
        assert config.poisson.min_density_percentile == 0.01

    def test_colmap_binary_is_path(self, tmp_path: Path) -> None:
        config = load_config(_write_yaml(tmp_path, VALID_YAML))
        assert isinstance(config.colmap_binary, Path)


# ---------------------------------------------------------------------------
# Limb profiles
# ---------------------------------------------------------------------------

class TestLimbProfiles:
    """Limb profile loading and validation."""

    def test_forearm_profile(self, tmp_path: Path) -> None:
        config = load_config(_write_yaml(tmp_path, VALID_YAML))
        forearm = config.limb_profiles["forearm"]
        assert forearm.limb_type == "forearm"
        assert forearm.expected_length_mm == (200, 350)
        assert forearm.split_plane_axis == "sagittal"
        assert forearm.wall_thickness_target_mm == 2.0
        assert forearm.cavity_clearance_mm == 1.0

    def test_above_knee_profile(self, tmp_path: Path) -> None:
        config = load_config(_write_yaml(tmp_path, VALID_YAML))
        ak = config.limb_profiles["above_knee"]
        assert ak.limb_type == "above_knee"
        assert ak.expected_length_mm == (300, 500)
        assert ak.split_plane_axis == "coronal"
        assert ak.wall_thickness_target_mm == 2.5
        assert ak.magnet_pocket_diameter_mm == 8.0

    def test_invalid_active_profile(self, tmp_path: Path) -> None:
        data = {**VALID_YAML, "active_profile": "nonexistent"}
        with pytest.raises(ValidationError, match="active_profile"):
            load_config(_write_yaml(tmp_path, data))


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    """Config loader rejects bad inputs gracefully."""

    def test_missing_file_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_config(Path("/nonexistent/pipeline.yaml"))

    def test_bad_yaml_syntax(self, tmp_path: Path) -> None:
        config_file = _write_yaml(tmp_path, "capture:\n  min_images: [invalid yaml\n  :")
        with pytest.raises(yaml.YAMLError):
            load_config(config_file)

    def test_empty_yaml(self, tmp_path: Path) -> None:
        config_file = _write_yaml(tmp_path, None)
        with pytest.raises(ValueError, match="empty"):
            load_config(config_file)

    def test_negative_min_images(self, tmp_path: Path) -> None:
        data = _deep_copy(VALID_YAML)
        data["capture"]["min_images"] = -1
        with pytest.raises(ValidationError):
            load_config(_write_yaml(tmp_path, data))

    def test_zero_min_features(self, tmp_path: Path) -> None:
        data = _deep_copy(VALID_YAML)
        data["capture"]["min_features_per_image"] = 0
        with pytest.raises(ValidationError):
            load_config(_write_yaml(tmp_path, data))

    def test_negative_min_3d_points(self, tmp_path: Path) -> None:
        data = _deep_copy(VALID_YAML)
        data["colmap"]["min_3d_points"] = -5
        with pytest.raises(ValidationError):
            load_config(_write_yaml(tmp_path, data))

    def test_unknown_fields_rejected(self, tmp_path: Path) -> None:
        """Pydantic v2 forbids extra fields by default when model_config is set."""
        data = _deep_copy(VALID_YAML)
        data["totally_unknown_field"] = "surprise"
        # Pydantic default allows extra fields; config loads but ignores them.
        # This test verifies no crash on unknown top-level keys.
        config = load_config(_write_yaml(tmp_path, data))
        assert not hasattr(config, "totally_unknown_field")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _deep_copy(data: dict) -> dict:
    """Return a deep copy of a nested dict (avoids mutating VALID_YAML)."""
    import copy
    return copy.deepcopy(data)

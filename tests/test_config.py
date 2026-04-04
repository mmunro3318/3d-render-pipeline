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
    "intake": {
        "supported_formats": ["obj", "stl"],
        "max_faces": 500_000,
        "min_faces": 10_000,
        "warn_faces_high": 300_000,
        "warn_faces_low": 100_000,
    },
    "repair": {
        "smooth_iterations": 3,
        "smooth_lambda": 0.5,
        "max_hole_edges": 100,
    },
    "boolean": {
        "engine_preference": ["manifold3d", "trimesh"],
        "retry_after_repair": True,
    },
    "export": {
        "output_format": "stl",
        "debug_exports": True,
        "debug_dir": "output/debug",
    },
    "active_profile": "above_knee",
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
            "split_plane_axis": "sagittal",
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


def _deep_copy(data: dict) -> dict:
    """Return a deep copy of a nested dict (avoids mutating VALID_YAML)."""
    import copy
    return copy.deepcopy(data)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestHappyPath:
    """Valid config loads correctly and fields match."""

    def test_load_valid_config(self, tmp_path: Path) -> None:
        config_file = _write_yaml(tmp_path, VALID_YAML)
        config = load_config(config_file)
        assert isinstance(config, PipelineConfig)
        assert config.active_profile == "above_knee"

    def test_intake_fields(self, tmp_path: Path) -> None:
        config = load_config(_write_yaml(tmp_path, VALID_YAML))
        assert config.intake.supported_formats == ["obj", "stl"]
        assert config.intake.max_faces == 500_000
        assert config.intake.min_faces == 10_000
        assert config.intake.warn_faces_high == 300_000
        assert config.intake.warn_faces_low == 100_000

    def test_repair_fields(self, tmp_path: Path) -> None:
        config = load_config(_write_yaml(tmp_path, VALID_YAML))
        assert config.repair.smooth_iterations == 3
        assert config.repair.smooth_lambda == 0.5
        assert config.repair.max_hole_edges == 100

    def test_boolean_fields(self, tmp_path: Path) -> None:
        config = load_config(_write_yaml(tmp_path, VALID_YAML))
        assert config.boolean.engine_preference == ["manifold3d", "trimesh"]
        assert config.boolean.retry_after_repair is True

    def test_export_fields(self, tmp_path: Path) -> None:
        config = load_config(_write_yaml(tmp_path, VALID_YAML))
        assert config.export.output_format == "stl"
        assert config.export.debug_exports is True
        assert config.export.debug_dir == "output/debug"


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
        assert ak.split_plane_axis == "sagittal"
        assert ak.wall_thickness_target_mm == 2.5
        assert ak.magnet_pocket_diameter_mm == 8.0

    def test_invalid_active_profile(self, tmp_path: Path) -> None:
        data = _deep_copy(VALID_YAML)
        data["active_profile"] = "nonexistent"
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
        config_file = _write_yaml(tmp_path, "intake:\n  max_faces: [invalid yaml\n  :")
        with pytest.raises(yaml.YAMLError):
            load_config(config_file)

    def test_empty_yaml(self, tmp_path: Path) -> None:
        config_file = _write_yaml(tmp_path, None)
        with pytest.raises(ValueError, match="empty"):
            load_config(config_file)

    def test_extra_fields_rejected(self, tmp_path: Path) -> None:
        """ConfigDict(extra='forbid') raises ValidationError on unknown fields."""
        data = _deep_copy(VALID_YAML)
        data["totally_unknown_field"] = "surprise"
        with pytest.raises(ValidationError, match="totally_unknown_field"):
            load_config(_write_yaml(tmp_path, data))

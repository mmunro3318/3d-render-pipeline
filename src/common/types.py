"""Shared pipeline types for the HyperReal mesh processing pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field

import trimesh


@dataclass
class StageResult:
    """Result of a single pipeline stage.

    Carries the output mesh, a structured report dict, any warnings,
    and the name of the stage that produced it.
    """

    mesh: trimesh.Trimesh
    report_dict: dict
    warnings: list[str] = field(default_factory=list)
    stage_name: str = ""

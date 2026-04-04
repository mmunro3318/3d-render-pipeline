# Testing Guidelines — HyperReal Pipeline

Meaningful tests that ship value, not theater. Every test must answer YES to: "If I deleted the function this covers, would the test fail?"

## Framework

- **pytest** with `conftest.py` for shared fixtures
- No GPU, no COLMAP, no network — all tests run offline on CPU
- No real patient data in tests — use synthetic geometry only

## Running Tests

```bash
pytest tests/ -v                                    # all tests
pytest tests/ --cov=src --cov-report=term-missing   # with coverage
pytest tests/test_mesh_utils.py -k "test_repair"    # single test
```

**Coverage target:** >= 80% on `src/`.

## Naming Conventions

| Element | Convention | Example |
|---------|-----------|---------|
| File | `test_<module>.py` | `test_mesh_utils.py` |
| Class | `TestClassName` | `TestMeshRepair` |
| Function | `test_descriptive_name` | `test_repair_closes_single_hole` |

## Synthetic Geometry Fixtures

Define in `tests/conftest.py`. Never load real scan data.

```python
import trimesh
import pytest

@pytest.fixture
def box_mesh() -> trimesh.Trimesh:
    """Watertight 10x10x10mm box — baseline for boolean and split tests."""
    return trimesh.creation.box(extents=(10, 10, 10))

@pytest.fixture
def cylinder_mesh() -> trimesh.Trimesh:
    """Watertight cylinder, radius=5mm height=20mm — limb-like proxy."""
    return trimesh.creation.cylinder(radius=5, height=20)

@pytest.fixture
def sphere_mesh() -> trimesh.Trimesh:
    """Watertight icosphere, radius=10mm."""
    return trimesh.creation.icosphere(radius=10)

@pytest.fixture
def open_mesh(box_mesh) -> trimesh.Trimesh:
    """Box with one face removed — non-watertight test case."""
    faces = box_mesh.faces[1:]  # drop first face
    return trimesh.Trimesh(vertices=box_mesh.vertices, faces=faces)
```

## What to Test

| Module | Test focus |
|--------|-----------|
| `common/mesh_utils.py` | Repair closes holes, decimation preserves watertight, export produces binary STL |
| `common/config.py` | Valid YAML loads, missing fields raise, defaults applied |
| `intake/validator.py` | Watertight check, scale bounds, face count limits, orientation |
| `stage2/mirror.py` | Mirrored mesh is reflected, stays watertight |
| `stage2/cavity_boolean.py` | Boolean subtraction produces hollow shell, result is watertight |
| `stage2/seam_split.py` | Planar cut yields exactly 2 pieces, both watertight |
| `stage2/magnets.py` | Pocket subtraction at configured coordinates, result is watertight |

## Mock Rules

1. Prefer real dependencies. Only mock for I/O, network, or non-deterministic behavior.
2. Never mock business logic from `src/` — test it directly.
3. If a test needs more than two mocks, refactor the production code first.
4. File system mocks: use `tmp_path` fixture, not mocking `pathlib`.

## Edge Cases Worth Testing

- Non-watertight input to a function that requires watertight
- Zero-volume or degenerate meshes (single triangle, empty mesh)
- Meshes at boundary of triangle count limits
- Boolean operations that produce multiple components
- Config with missing required fields or out-of-range values

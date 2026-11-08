import numpy as np
import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("skimage")
import trimesh  # noqa: E402


def test_mcubes_shim_matches_triposr_conventions():
    from abydex.engines.triposr_runner import _install_mcubes_shim
    _install_mcubes_shim()
    from torchmcubes import marching_cubes

    n = 48
    g = torch.linspace(-1, 1, n)
    X, Y, Z = torch.meshgrid(g, g, g, indexing="ij")
    v, f = marching_cubes((X / 0.9) ** 2 + (Y / 0.5) ** 2 + (Z / 0.3) ** 2 - 1, 0.0)
    m = trimesh.Trimesh((v[..., [2, 1, 0]] / (n - 1)).numpy(), f.numpy())  # what TripoSR does next
    assert np.allclose(m.extents, [0.9, 0.5, 0.3], atol=0.03)
    assert m.is_watertight and m.volume > 0

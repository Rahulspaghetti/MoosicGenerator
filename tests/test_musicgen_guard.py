"""The MusicGen service must refuse to run on CPU."""

import pytest

from app.services import musicgen


def test_require_cuda_raises_without_gpu() -> None:
    """With no torch/CUDA available (the test env), the guard fails loud."""
    with pytest.raises(RuntimeError, match="CUDA GPU required"):
        musicgen._require_cuda()

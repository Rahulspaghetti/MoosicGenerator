"""MusicGen text-to-music inference (HuggingFace ``transformers``).

The model is loaded lazily on first use and kept warm for the process. All GPU
work is serialized by a module lock so two concurrent jobs cannot exhaust VRAM.

**CUDA is mandatory.** If no GPU is available the service refuses to run rather
than silently falling back to the CPU (the 300M model is unusably slow there).
``torch``/``transformers``/``numpy`` are imported inside the functions so this
module imports cleanly in environments without them (e.g. the test suite, which
patches :func:`generate`).
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from app.core.config import get_settings

if TYPE_CHECKING:
    import numpy as np

_CUDA_ERROR = "CUDA GPU required; refusing to run MusicGen on CPU."

# Serializes GPU access; MusicGen weights + activations must not run concurrently
# on an 8 GB card.
_lock = threading.Lock()

_model = None
_processor = None


def _require_cuda() -> None:
    """Raise ``RuntimeError`` unless a usable CUDA GPU is present.

    Treats a missing ``torch`` install the same as a missing GPU — either way we
    cannot (and will not) run on CPU.
    """
    try:
        import torch
    except ImportError as exc:  # torch not installed at all
        raise RuntimeError(_CUDA_ERROR) from exc
    if not torch.cuda.is_available():
        raise RuntimeError(_CUDA_ERROR)


def _load() -> tuple[object, object]:
    """Load (once) and return the warm ``(model, processor)`` pair on CUDA."""
    global _model, _processor
    if _model is None:
        _require_cuda()
        from transformers import AutoProcessor, MusicgenForConditionalGeneration

        model_name = get_settings().MUSICGEN_MODEL
        _processor = AutoProcessor.from_pretrained(model_name)
        _model = MusicgenForConditionalGeneration.from_pretrained(model_name).to("cuda")
    return _model, _processor


def generate(prompt: str, duration_s: int) -> tuple["np.ndarray", int]:
    """Generate ~``duration_s`` seconds of audio conditioned on ``prompt``.

    Returns:
        A ``(mono float32 waveform, sample_rate)`` tuple. MusicGen emits at
        32 kHz. Raises ``RuntimeError`` if no CUDA GPU is available.
    """
    import numpy as np
    import torch

    with _lock:
        model, processor = _load()
        inputs = processor(text=[prompt], padding=True, return_tensors="pt").to("cuda")
        # MusicGen decodes at ~50 audio tokens per second.
        max_new_tokens = int(duration_s * 50)
        with torch.no_grad():
            tokens = model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=True)
        waveform = tokens[0, 0].detach().to("cpu").float().numpy().astype(np.float32)
        sample_rate = int(model.config.audio_encoder.sampling_rate)
        return waveform, sample_rate

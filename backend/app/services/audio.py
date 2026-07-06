"""Audio encoding helpers.

Transcodes raw PCM straight to MP3 by piping it through ``ffmpeg`` — no
intermediate WAV file and no extra Python audio dependency.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np


def pcm_to_mp3(samples: "np.ndarray", sample_rate: int, out_path: str | Path) -> None:
    """Encode a mono float32 waveform to an MP3 file via ffmpeg.

    Args:
        samples: 1-D float32 array in [-1, 1].
        sample_rate: Sample rate of ``samples`` in Hz.
        out_path: Destination ``.mp3`` path (parent dirs are created).

    Raises:
        RuntimeError: If ffmpeg is missing or exits non-zero (stderr included).
    """
    import numpy as np

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pcm = np.ascontiguousarray(samples, dtype="<f4").tobytes()

    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "f32le", "-ar", str(sample_rate), "-ac", "1", "-i", "pipe:0",
        "-codec:a", "libmp3lame", "-q:a", "4",
        str(out_path),
    ]
    try:
        proc = subprocess.run(cmd, input=pcm, capture_output=True)
    except FileNotFoundError as exc:
        raise RuntimeError("ffmpeg not found on PATH; cannot encode MP3.") from exc
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed (exit {proc.returncode}): {proc.stderr.decode(errors='replace')}"
        )

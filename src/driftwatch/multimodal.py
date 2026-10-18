"""Small, local-first multimodal monitoring helpers.

These adapters let a student project monitor tabular data, text, or image
batches through one JSON-shaped contract. They do not upload raw content or
require a paid provider. Embedding models can be plugged in later.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .advanced_metrics import image_metrics, semantic_text_metrics
from .metrics import text_metrics


def analyze_text(reference: Iterable[str], current: Iterable[str]) -> dict[str, Any]:
    """Return lexical, length, and TF-IDF semantic-shift metrics for text."""
    reference_values, current_values = list(reference), list(current)
    return {
        "modality": "text",
        "available": bool(reference_values and current_values),
        "quality": text_metrics(
            pd.Series(reference_values, dtype="string"),
            pd.Series(current_values, dtype="string"),
        ),
        "semantic": semantic_text_metrics(reference_values, current_values),
        "limitations": "TF-IDF is a transparent baseline; use an embedding provider for multilingual or domain-specific meaning.",
    }


def _image_quality(batch: Any) -> dict[str, Any]:
    values = np.asarray(batch, dtype=float)
    pixels = np.clip(values, 0, 255)
    if values.ndim < 3 or not values.size:
        return {"available": False, "reason": "expected a non-empty image batch"}
    if values.ndim == 3:
        values = values[..., None]
    edge_x = np.abs(np.diff(values, axis=2)).mean() if values.shape[2] > 1 else 0.0
    edge_y = np.abs(np.diff(values, axis=1)).mean() if values.shape[1] > 1 else 0.0
    return {
        "available": True,
        "images": int(values.shape[0]),
        "height": int(values.shape[1]),
        "width": int(values.shape[2]),
        "channels": int(values.shape[3]),
        "mean_brightness": round(float(pixels.mean()), 6),
        "contrast": round(float(pixels.std()), 6),
        "clipped_pixel_rate": round(float(((values < 0) | (values > 255)).mean()), 6),
        "edge_energy": round(float((edge_x + edge_y) / 2), 6),
    }


def analyze_images(reference: Any, current: Any) -> dict[str, Any]:
    """Compare image arrays using pixel-distribution and quality metrics."""
    return {
        "modality": "image",
        "available": True,
        "distribution": image_metrics(reference, current),
        "reference_quality": _image_quality(reference),
        "current_quality": _image_quality(current),
        "limitations": "Pixel metrics are a baseline; add a domain embedding model for semantic image drift.",
    }


def load_image_batch(paths: Iterable[str | Path]) -> np.ndarray:
    """Load image paths into an array; Pillow stays an optional dependency."""
    try:
        from PIL import Image
    except ImportError as error:
        raise RuntimeError(
            "Image loading requires Pillow. Install with: pip install 'driftwatch[production]'"
        ) from error
    images = [np.asarray(Image.open(path).convert("RGB")) for path in paths]
    if not images:
        raise ValueError("at least one image path is required")
    return np.stack(images)


def analyze(reference: Any, current: Any) -> dict[str, Any]:
    """Automatically select a tabular, text, or image monitoring adapter."""
    if isinstance(reference, pd.DataFrame) and isinstance(current, pd.DataFrame):
        return {"modality": "tabular", "available": True, "columns": list(reference.columns)}
    ref_array, cur_array = np.asarray(reference), np.asarray(current)
    if ref_array.ndim >= 3 and cur_array.ndim >= 3:
        return analyze_images(ref_array, cur_array)
    if ref_array.dtype.kind in {"U", "S", "O"} and cur_array.dtype.kind in {"U", "S", "O"}:
        return analyze_text(ref_array.tolist(), cur_array.tolist())
    return {"modality": "unsupported", "available": False, "reason": "use DataFrames, text sequences, or image batches"}

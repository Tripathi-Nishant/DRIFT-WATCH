import numpy as np

from driftwatch import analyze_images, analyze_text


def test_text_adapter_returns_quality_and_semantic_metrics():
    result = analyze_text(["cat on a mat", "small cat"], ["quantum finance", "bond yield"])
    assert result["modality"] == "text"
    assert result["semantic"]["available"]


def test_image_adapter_returns_distribution_and_quality_metrics():
    reference = np.zeros((2, 8, 8, 3), dtype=np.uint8)
    current = np.ones((2, 8, 8, 3), dtype=np.uint8) * 255
    result = analyze_images(reference, current)
    assert result["modality"] == "image"
    assert result["distribution"]["pixel_histogram_distance"] == 1.0
    assert result["current_quality"]["mean_brightness"] == 255.0

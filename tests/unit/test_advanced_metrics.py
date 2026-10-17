import numpy as np

from driftwatch import (
    image_metrics,
    llm_metrics,
    rag_metrics,
    ranking_metrics,
    semantic_text_metrics,
)


def test_semantic_text_metrics_detects_shift():
    result = semantic_text_metrics(["cat sat on mat"], ["quantum finance derivative"])
    assert result["available"]
    assert result["semantic_shift"] > 0


def test_image_metrics_reports_shape_and_pixel_shift():
    result = image_metrics(np.zeros((2, 4, 4, 3)), np.ones((2, 4, 4, 3)) * 255)
    assert result["available"]
    assert result["pixel_histogram_distance"] == 1.0


def test_ranking_and_generation_metrics():
    ranking = ranking_metrics([[1, 0, 0], [0, 1, 0]], k=3)
    assert ranking["ndcg_at_k"] > 0
    llm = llm_metrics(
        [
            {
                "question": "what is drift",
                "answer": "drift is change",
                "context": "drift means change",
                "citation": "doc-1",
            }
        ]
    )
    assert llm["groundedness"] > 0
    rag = rag_metrics(
        [{"answer": "change in data", "contexts": ["data change detected"]}]
    )
    assert rag["retrieval_hit_rate"] == 1.0

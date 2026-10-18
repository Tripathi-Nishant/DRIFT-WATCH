import pytest

from driftwatch.production import (
    GeminiLLMJudge,
    GovernedLLMJudge,
    LLMJudgeConfig,
    redacted,
)
from driftwatch.vector_store import QdrantVectorStore


def test_redacted_removes_named_and_inline_pii():
    value = redacted({"email": "person@example.com", "text": "Call 555-123-4567"})
    assert value["email"] == "[REDACTED]"
    assert "REDACTED" in value["text"]


def test_governed_judge_enforces_budget_and_calibration():
    judge = GovernedLLMJudge(
        LLMJudgeConfig(
            endpoint="https://judge.example",
            model="test",
            api_key="secret",
            max_cost_usd=0.01,
            estimated_cost_per_record_usd=0.01,
            min_score=0.2,
            max_score=0.8,
        ),
        transport=lambda body: {"results": [{"score": 0.5}]},
    )
    assert judge.evaluate([{"prompt": "hidden", "answer": "ok"}])[0]["score"] == 0.5
    with pytest.raises(ValueError, match="cost limit"):
        judge.evaluate([{}, {}])


def test_vector_store_requires_tenant_for_writes():
    store = QdrantVectorStore(url="https://vector.example")
    with pytest.raises(ValueError, match="organization_id"):
        store.upsert([], "")


def test_gemini_adapter_validates_json_response():
    judge = GeminiLLMJudge(
        "test-key",
        transport=lambda model, body: {
            "candidates": [{
                "content": {"parts": [{"text": '{"results":[{"score":0.7}]}'}]}
            }]
        },
    )
    assert judge.evaluate([{"question": "q"}])[0]["score"] == 0.7

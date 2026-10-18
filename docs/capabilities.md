# DriftWatch capability boundary

This matrix describes the current repository, not the aspirational roadmap.

| Capability | Current status | Notes |
| --- | --- | --- |
| Numeric tabular drift | Implemented | PSI, KS, Wasserstein, mean and variance shift. |
| Categorical drift | Implemented | Frequency distance, chi-square, and new categories. |
| Joint distribution drift | Implemented, experimental | Logistic domain classifier AUC; evidence of shift, not causation. |
| Subgroup drift | Implemented, basic | `Monitor.run(..., group_by="segment")`; compares shared groups. |
| Data quality | Implemented, basic | Missingness, duplicates, schema/type changes, categories and percentile outliers. |
| Metric registry and tests | Implemented | Discoverable metric catalog, quality metrics, portable drift/quality assertions and pass/fail results. |
| Text monitoring | Implemented, baseline | Empty rate, uniqueness, character/word length statistics and KS shift for text-like columns; no embeddings or semantic similarity. |
| Semantic text monitoring | Implemented, baseline | TF-IDF centroid cosine shift; replace with a governed embedding provider for production semantic monitoring. |
| Image monitoring | Implemented, baseline | Tensor shape, channel, pixel distribution and histogram shift; no vision model quality metrics. |
| Ranking/recommendation | Implemented, baseline | NDCG@k, MRR@k, precision@k and hit-rate@k from relevance matrices. |
| LLM evaluation | Implemented, baseline | Transparent token-overlap relevance, groundedness and citation coverage; no hidden model calls. |
| RAG evaluation | Implemented, baseline | Retrieval hit rate and context precision from answer/context records. |
| Prediction quality diagnostics | Implemented, baseline | Class distributions and regression residual diagnostics in addition to scored performance. |
| Prediction drift | Implemented | Requires reference and current predictions. |
| Classification performance | Implemented | Accuracy, precision, recall, F1 and ROC-AUC. |
| Regression performance | Implemented | MAE, RMSE, R² and MAPE. |
| Decision layer | DriftWatch differentiator | Severity, confidence, rule trace, impact estimate and ACT/MONITOR/IGNORE. |
| Production embedding/image/LLM judges | Governed adapters | Sentence Transformers embeddings plus opt-in authenticated LLM judge controls for prompt versioning, PII redaction, budgets, and calibration bounds. Vision quality remains provider-specific. |
| Vector storage | Optional adapter | Qdrant REST adapter with organization-scoped upserts and searches; deployment must provide and validate a Qdrant cluster. |
| Distributed ingestion | Optional adapter | Redis-backed queue plus bounded local queue; deployment must provide Redis persistence and worker supervision. |
| Statistical calibration against Evidently | In progress | The benchmark runner is present; matched-method validation is still required. |

Evidently remains the stronger general-purpose monitoring framework. DriftWatch now
has a metric-family architecture, governed provider adapters, tenant-aware storage,
and a transparent decision layer on top of monitoring signals. Provider quality,
calibration, and scale still require validation in each deployment environment.

# DriftWatch research protocol

DriftWatch includes a reproducible Research Lab for evaluating monitoring
decisions rather than reporting only a single drift score.

## Evaluation questions

1. Does the decision layer avoid unnecessary action on clean windows?
2. Does it identify planted distribution shifts consistently across seeds?
3. How do confidence intervals change as the experiment budget grows?
4. How do model quality and data drift behave across repeated monitoring runs?

## Reproducible procedure

1. Select the `synthetic` or `public` suite in the dashboard Research Lab.
2. Record the exact integer seed list and suite name.
3. Run the benchmark and retain the persisted JSON evidence record.
4. Report false-alert rate on clean windows and action rate on planted shifts.
5. Report the stored 95% normal-approximation intervals with the seed count.
6. Repeat with additional seeds or datasets as a separate experiment record.

The API endpoint is `POST /api/v1/research`. It validates the protocol,
persists the full result, and exposes prior runs through
`GET /api/v1/research`. JSON downloads are suitable as supplementary material.

## Claims and limitations

The synthetic suite measures behavioral sensitivity to known planted shifts; it
does not establish performance on every domain. The public suite provides
repeatable reference points, not a substitute for deployment-specific
calibration. Results should include dataset provenance, seed lists, thresholds,
software version, and limitations.

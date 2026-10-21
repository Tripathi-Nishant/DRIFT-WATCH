# Placement Predictor Demo Client

This directory is an optional client used to demonstrate DriftWatch with a
student placement model. It is deliberately kept outside the DriftWatch core
package.

The actual product is in `src/driftwatch/` and does not depend on this model.
You can delete or ignore this directory when integrating another model.

The integration scripts demonstrate the generic contract that other projects
can follow:

```text
reference features + current features
optional predictions + labels
                    ↓
              DriftWatch API
                    ↓
          dashboard report and decision
```

Use this only as an example. DriftWatch does not require this dataset, model,
or folder to monitor other classification, regression, text, or image models.

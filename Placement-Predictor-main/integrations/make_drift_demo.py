"""Create a visibly shifted placement batch for a DriftWatch demonstration."""

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "demo"


def main() -> None:
    features = pd.read_csv(ROOT / "data" / "processed" / "X_prepared.csv")
    labels = pd.read_csv(ROOT / "data" / "processed" / "Y_prepared.csv")
    reference = features.iloc[:140].copy()
    current = features.iloc[140:].copy()
    current_labels = labels.iloc[140:].copy()

    # Simulate a new cohort with stronger academic scores and more work experience.
    for column in ["ssc_p", "hsc_p", "degree_p", "etest_p", "mba_p"]:
        current[column] = (current[column] + 0.25).clip(0, 1)
    current["workex"] = 1
    current["hsc_s_Commerce"] = 1
    current["hsc_s_Science"] = 0
    OUTPUT.mkdir(parents=True, exist_ok=True)
    reference.to_csv(OUTPUT / "reference.csv", index=False)
    current.to_csv(OUTPUT / "current.csv", index=False)
    current_labels.to_csv(OUTPUT / "current_labels.csv", index=False)
    print(f"Created demo files in {OUTPUT}")


if __name__ == "__main__":
    main()

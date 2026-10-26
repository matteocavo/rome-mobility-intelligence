import numpy as np

from app.ml.evaluation import evaluate


def select_threshold(y, probability, grid=None):
    values = list(grid) if grid is not None else np.round(np.linspace(0.05, 0.95, 37), 6).tolist()
    if not values or any(not 0 < float(t) < 1 for t in values):
        raise ValueError("Threshold grid must be inside (0, 1)")
    rows = []
    for value in values:
        metrics = evaluate(y, probability, float(value))
        tn, fp, fn, tp = np.asarray(metrics["confusion_matrix"]).ravel().tolist()
        rows.append(
            {
                "threshold": float(value),
                **{k: metrics[k] for k in ("precision", "recall", "f1", "predicted_positive_rate")},
                "tp": tp,
                "fp": fp,
                "tn": tn,
                "fn": fn,
            }
        )
    # Candidate criterion: max validation F1, then precision, then higher threshold.
    winner = max(rows, key=lambda r: (r["f1"], r["precision"], r["threshold"]))
    return winner["threshold"], rows

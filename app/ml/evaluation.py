import numpy as np
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


def evaluate(y, probability, threshold: float) -> dict:
    p = np.asarray(probability, dtype=float)
    if not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
        raise ValueError("Invalid probabilities")
    if set(np.unique(y)) != {0, 1}:
        raise ValueError("Both classes required for evaluation")
    prediction = (p >= threshold).astype(int)
    return {
        "precision": float(precision_score(y, prediction, zero_division=0)),
        "recall": float(recall_score(y, prediction, zero_division=0)),
        "f1": float(f1_score(y, prediction, zero_division=0)),
        "roc_auc": float(roc_auc_score(y, p)),
        "pr_auc": float(average_precision_score(y, p)),
        "pr_auc_definition": "average_precision",
        "confusion_matrix": confusion_matrix(y, prediction, labels=[0, 1]).tolist(),
        "positive_rate": float(np.mean(y)),
        "predicted_positive_rate": float(np.mean(prediction)),
        "accuracy": float(accuracy_score(y, prediction)),
        "rows": len(y),
    }

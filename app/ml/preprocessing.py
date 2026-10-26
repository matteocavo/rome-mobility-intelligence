import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from app.contracts.operational_ml import CATEGORICAL, FEATURES, NUMERIC


class FeatureValidator(TransformerMixin, BaseEstimator):
    def fit(self, X, y=None):
        self.transform(X)
        self.feature_names_in_ = np.array(FEATURES, dtype=object)
        return self

    def transform(self, X):
        if not isinstance(X, pd.DataFrame) or X.columns.duplicated().any():
            raise ValueError("Unique named DataFrame columns required")
        if set(X.columns) != set(FEATURES):
            raise ValueError("Exactly the 47 contract features are required")
        result = X.loc[:, list(FEATURES)].copy()
        for name in NUMERIC:
            try:
                result[name] = pd.to_numeric(result[name], errors="raise").astype(float)
            except (ValueError, TypeError):
                raise ValueError(f"Non-numeric feature: {name}") from None
            if np.isinf(result[name]).any():
                raise ValueError(f"Infinite feature: {name}")
        for name in CATEGORICAL:
            if name in {"route_type", "direction_id"}:
                try:
                    values = pd.to_numeric(result[name], errors="raise").astype(float)
                except (TypeError, ValueError):
                    raise ValueError(f"Invalid integer category: {name}") from None
                known = values.dropna()
                if not np.isfinite(known).all() or (known != np.floor(known)).any():
                    raise ValueError(f"Invalid integer category: {name}")
                result[name] = values.map(lambda x: "__MISSING__" if pd.isna(x) else str(int(x)))
            else:
                result[name] = result[name].map(lambda x: "__MISSING__" if pd.isna(x) else str(x))
        return result


def build_pipeline(kind: str, seed: int = 42) -> Pipeline:
    if kind not in {"logistic_regression", "hist_gradient_boosting"}:
        raise ValueError("Unknown candidate")
    dense = kind == "hist_gradient_boosting"
    numeric = [("impute", SimpleImputer(strategy="median", keep_empty_features=True))]
    if not dense:
        numeric.append(("scale", StandardScaler()))
    preprocessing = ColumnTransformer(
        [
            ("numeric", Pipeline(numeric), list(NUMERIC)),
            (
                "categorical",
                OneHotEncoder(
                    handle_unknown="ignore",
                    sparse_output=not dense,
                    max_categories=32,
                ),
                list(CATEGORICAL),
            ),
        ],
        sparse_threshold=0 if dense else 1.0,
    )
    model = (
        HistGradientBoostingClassifier(
            max_iter=60,
            max_leaf_nodes=15,
            early_stopping=False,
            random_state=seed,
        )
        if dense
        else LogisticRegression(max_iter=1000, random_state=seed)
    )
    return Pipeline(
        [("contract", FeatureValidator()), ("preprocessing", preprocessing), ("classifier", model)]
    )

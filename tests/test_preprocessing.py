import numpy as np
import pytest

from app.contracts.operational_ml import FEATURES, LABEL
from app.ml.preprocessing import build_pipeline


@pytest.mark.parametrize("kind", ["logistic_regression", "hist_gradient_boosting"])
def test_missing_and_unknown_categories(frame, kind):
    pipeline = build_pipeline(kind)
    pipeline.fit(frame[list(FEATURES)], frame[LABEL])
    x = frame.iloc[:4][list(FEATURES)].copy()
    x["route_id"] = "never-seen"
    x["agency_id"] = None
    x["vehicle_speed"] = np.nan
    prediction = pipeline.predict_proba(x)
    assert prediction.shape == (4, 2)
    assert np.isfinite(prediction).all()
    np.testing.assert_allclose(prediction.sum(axis=1), 1)


def test_preprocessor_fits_training_only(frame):
    pipeline = build_pipeline("logistic_regression")
    x = frame.iloc[:100][list(FEATURES)].copy()
    pipeline.fit(x, frame.iloc[:100][LABEL])
    before = pipeline.named_steps["preprocessing"].transformers_[0][1]["impute"].statistics_.copy()
    x.loc[:, "vehicle_speed"] = 1e12
    pipeline.predict_proba(x)
    np.testing.assert_array_equal(
        before, pipeline.named_steps["preprocessing"].transformers_[0][1]["impute"].statistics_
    )


def test_integer_categories_normalize_nullable_floats(frame):
    from app.ml.preprocessing import FeatureValidator

    x = frame.iloc[:3][list(FEATURES)].copy()
    x["route_type"] = [3.0, None, 1.0]
    transformed = FeatureValidator().transform(x)
    assert transformed.route_type.tolist() == ["3", "__MISSING__", "1"]

"""Scientific and fail-closed tests for flood methodology."""
import numpy as np
import pytest
from engine.flood.bayuadji import evaluate as evaluate_bayuadji, stable_sigmoid
from engine.flood.screening import classify_rainfall, status as screening_status
from engine.flood.integration import status as integration_status, aggregate_basin


def test_bayuadji_model_is_not_configured():
    res = evaluate_bayuadji()
    assert res["status"] == "NOT_CONFIGURED"
    assert res["probability"] is None
    assert res["category"] is None
    assert res["parameter_verification"] == "unverified"
    assert res["local_validation"] == "not_performed"


def test_stable_sigmoid_extreme_values():
    vals = np.array([-1000.0, 0.0, 1000.0])
    res = stable_sigmoid(vals)
    assert np.all(np.isfinite(res))
    assert res[0] == 0.0
    assert res[1] == pytest.approx(0.5)
    assert res[2] == 1.0


def test_screening_and_bmkg_status_unverified():
    assert classify_rainfall(75.0) is None
    st = screening_status()
    assert st["classification_status"] == "unverified"
    assert st["rainfall_category_scale"] is None


def test_integration_exploratory_side_by_side():
    st = integration_status()
    assert st["status"] == "exploratory_indicators"
    assert st["combined_category"] is None
    assert st["combined_probability"] is None
    basin = aggregate_basin()
    assert basin["status"] == "unsupported"

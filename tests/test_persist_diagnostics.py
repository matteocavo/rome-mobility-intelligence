from scripts.persist_current_predictions import safe_stage, safe_category, OrchestrationError

def test_safe_stage_rejects_unknown():
    assert safe_stage("not-a-stage") == "internal"
    assert safe_stage("persistence") == "persistence"

def test_safe_category_rejects_unknown():
    assert safe_category("totally-unknown", 500) == "server_error"

def test_orchestration_error_preserves_original_category():
    exc = OrchestrationError("persistence", status=503, category="server_unavailable_or_timeout")
    assert exc.stage == "persistence"
    assert exc.status == 503
    assert exc.category == "server_unavailable_or_timeout"

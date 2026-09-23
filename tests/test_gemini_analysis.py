"""Tests for Gemini Multimodal Analysis and Security Guardrails."""

from pathlib import Path
import pytest
from pydantic import ValidationError

from schemas.citizen_image_analysis import (
    CitizenImageAnalysis,
    SmokeIntensity,
    VisualEventType,
)
from services.ai.gemini_service import FixtureGeminiAnalyzer, GeminiVisionAnalyzer

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "data" / "sample_images"


def test_valid_image_analysis_schema():
    """Valid structured output parses successfully with required fields."""
    analysis = CitizenImageAnalysis(
        visible_smoke=True,
        visible_flames=False,
        event_type=VisualEventType.INDUSTRIAL_EMISSIONS,
        smoke_intensity=SmokeIntensity.DENSE,
        visual_evidence="Dense vertical smoke plume discharging from factory stack.",
        uncertain_fields=[],
        needs_human_verification=True,
        confidence=0.88,
    )
    assert analysis.visible_smoke is True
    assert analysis.visible_flames is False
    assert analysis.event_type == VisualEventType.INDUSTRIAL_EMISSIONS
    assert analysis.confidence == 0.88


def test_guardrail_rejects_invented_pm25():
    """Guardrail must reject any output asserting numeric PM2.5 / concentration numbers."""
    with pytest.raises(ValidationError, match="Security Guardrail Violation"):
        CitizenImageAnalysis(
            visible_smoke=True,
            visible_flames=False,
            event_type=VisualEventType.INDUSTRIAL_EMISSIONS,
            smoke_intensity=SmokeIntensity.DENSE,
            visual_evidence="Heavy plume with PM2.5 of 350 ug/m3 causing severe smog.",  # Hallucinated PM2.5!
            uncertain_fields=[],
            needs_human_verification=True,
            confidence=0.9,
        )


def test_guardrail_rejects_legal_declarations():
    """Guardrail must reject output declaring a legal violation or criminal act."""
    with pytest.raises(ValidationError, match="Security Guardrail Violation"):
        CitizenImageAnalysis(
            visible_smoke=True,
            visible_flames=False,
            event_type=VisualEventType.INDUSTRIAL_EMISSIONS,
            smoke_intensity=SmokeIntensity.DENSE,
            visual_evidence="Visible dark plume that is an illegal emission violating environmental law.",
            uncertain_fields=[],
            needs_human_verification=True,
            confidence=0.9,
        )


def test_low_confidence_forces_human_verification():
    """Low confidence (< 0.65) must automatically enforce needs_human_verification=True."""
    analysis = CitizenImageAnalysis(
        visible_smoke=True,
        visible_flames=False,
        event_type=VisualEventType.UNKNOWN,
        smoke_intensity=SmokeIntensity.LOW,
        visual_evidence="Faint hazy dispersion in the distant background.",
        uncertain_fields=["source_type"],
        needs_human_verification=False,  # Set to False initially
        confidence=0.55,  # Low confidence
    )
    # Model validator should force needs_human_verification to True
    assert analysis.needs_human_verification is True


def test_fixture_analyzer_deterministic_responses():
    """Fixture analyzer returns accurate structured evidence based on sample files."""
    analyzer = GeminiVisionAnalyzer(force_fixture=True)

    # 1. Industrial smoke
    res_ind = analyzer.analyze_image(SAMPLE_DIR / "industrial_smoke.jpg")
    assert res_ind.visible_smoke is True
    assert res_ind.event_type == VisualEventType.INDUSTRIAL_EMISSIONS
    assert res_ind.confidence >= 0.80

    # 2. Crop burning
    res_crop = analyzer.analyze_image(SAMPLE_DIR / "crop_burning.jpg")
    assert res_crop.visible_smoke is True
    assert res_crop.visible_flames is True
    assert res_crop.event_type == VisualEventType.BIOMASS_BURNING

    # 3. Clear sky
    res_clear = analyzer.analyze_image(SAMPLE_DIR / "clear_sky.jpg")
    assert res_clear.visible_smoke is False
    assert res_clear.visible_flames is False
    assert res_clear.smoke_intensity == SmokeIntensity.NONE


def test_gemini_vision_analyzer_default_model():
    """GeminiVisionAnalyzer defaults to gemini-3.5-flash-lite without hardcoding."""
    analyzer = GeminiVisionAnalyzer(force_fixture=True)
    assert analyzer.configured_model == "gemini-3.5-flash-lite"
    assert "gemini-3.5-flash-lite" in analyzer.provider_name
    assert analyzer.provider_name.startswith("fixture:")


def test_gemini_vision_analyzer_custom_model_override():
    """GeminiVisionAnalyzer allows explicit model configuration."""
    custom_model = "gemini-3.1-flash-lite"
    analyzer = GeminiVisionAnalyzer(model=custom_model, force_fixture=True)
    assert analyzer.configured_model == custom_model
    assert analyzer.provider_name == f"fixture:{custom_model}"


def test_gemini_vision_analyzer_env_override(monkeypatch):
    """GEMINI_MODEL environment variable sets default analyzer model dynamically."""
    from apps.api import config
    # Reset singleton settings to test env variable pickup
    config._settings = None
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.5-flash")

    analyzer = GeminiVisionAnalyzer(force_fixture=True)
    assert analyzer.configured_model == "gemini-3.5-flash"
    assert analyzer.provider_name == "fixture:gemini-3.5-flash"

    # Reset singleton after test
    config._settings = None


def test_system_health_reports_configured_gemini_model():
    """Health check endpoint accurately reports configured Gemini model and provider status."""
    from fastapi.testclient import TestClient
    from apps.api.main import app

    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "providers" in data
    assert "gemini" in data["providers"]
    gemini_info = data["providers"]["gemini"]
    assert "model" in gemini_info
    assert gemini_info["model"] == "gemini-3.5-flash-lite"
    assert "provider" in gemini_info
    assert gemini_info["status"] in ("available", "unavailable")


def test_gemini_vision_analyzer_disables_function_calling_and_tools(monkeypatch):
    """Vision analysis must explicitly omit tools and disable automatic function calling."""
    from unittest.mock import MagicMock
    from schemas.citizen_image_analysis import CitizenImageAnalysis, VisualEventType, SmokeIntensity

    analyzer = GeminiVisionAnalyzer(api_key="fake-key-for-test", force_fixture=False)
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = CitizenImageAnalysis(
        visible_smoke=True,
        visible_flames=False,
        event_type=VisualEventType.INDUSTRIAL_EMISSIONS,
        smoke_intensity=SmokeIntensity.HEAVY,
        visual_evidence="Plume visible from smokestack.",
        confidence=0.92,
    ).model_dump_json()
    mock_client.models.generate_content.return_value = mock_response
    analyzer._client = mock_client

    sample_img = SAMPLE_DIR / "industrial_smoke.jpg"
    res = analyzer.analyze_image(sample_img)

    assert res.visible_smoke is True
    assert mock_client.models.generate_content.called
    _, kwargs = mock_client.models.generate_content.call_args
    passed_config = kwargs.get("config")
    assert passed_config is not None
    assert passed_config.tools is None
    assert passed_config.automatic_function_calling is not None
    assert passed_config.automatic_function_calling.disable is True

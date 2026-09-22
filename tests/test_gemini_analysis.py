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

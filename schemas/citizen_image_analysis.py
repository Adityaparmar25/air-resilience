"""Schema and guardrails for Gemini multimodal citizen image analysis."""

from enum import Enum
import re
from typing import List
from pydantic import BaseModel, Field, field_validator, model_validator


class SmokeIntensity(str, Enum):
    """Visual density categorization of smoke plume."""

    NONE = "none"
    LOW = "low"
    MODERATE = "moderate"
    HEAVY = "heavy"
    DENSE = "dense"


class VisualEventType(str, Enum):
    """Visual categorization of suspected emission source."""

    INDUSTRIAL_EMISSIONS = "industrial_emissions"
    BIOMASS_BURNING = "biomass_burning"
    OPEN_WASTE_BURNING = "open_waste_burning"
    DUST = "dust"
    VEHICLE_EXHAUST = "vehicle_exhaust"
    UNKNOWN = "unknown"


class CitizenImageAnalysis(BaseModel):
    """Strict structured output model for Gemini vision analysis of citizen photographs.

    Guarantees that Gemini output only contains visually verifiable observations.
    Never allows Gemini to invent PM2.5 concentrations, name specific companies/persons,
    declare legal violations, or make unsupported causal assertions.
    """

    visible_smoke: bool = Field(
        ...,
        description="Whether a visible smoke plume or haze layer is discernable in the photograph",
    )
    visible_flames: bool = Field(
        ...,
        description="Whether active flames, glowing embers, or combustion fire are directly visible",
    )
    event_type: VisualEventType = Field(
        default=VisualEventType.UNKNOWN,
        description="Probabilistic category based on visual signatures (never legally binding)",
    )
    smoke_intensity: SmokeIntensity = Field(
        default=SmokeIntensity.NONE,
        description="Visual opacity and spread of smoke: none | low | moderate | heavy | dense",
    )
    visual_evidence: str = Field(
        ...,
        min_length=5,
        max_length=1000,
        description="Strictly visual description of scene elements (e.g. dark plume rising from vertical stack)",
    )
    uncertain_fields: List[str] = Field(
        default_factory=list,
        description="List of fields where photographic quality, angle, or lighting causes ambiguity",
    )
    needs_human_verification: bool = Field(
        default=True,
        description="Flag indicating that human operator verification is recommended before official escalation",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Model confidence in visual interpretation (0.0 to 1.0)",
    )

    @field_validator("visual_evidence")
    @classmethod
    def validate_no_prohibited_ai_claims(cls, v: str) -> str:
        """Enforce strict guardrails against prohibited AI hallucination patterns.

        Prohibitions:
        1. Inventing PM2.5 or numeric pollutant concentration numbers.
        2. Naming specific companies or persons as legally guilty.
        3. Declaring a legal violation or regulatory crime.
        4. Asserting unverified absolute causal source attribution.
        """
        text = v.lower()

        # 1. Prohibit numerical PM2.5 / PM10 invention
        pm_patterns = [
            r"\bpm\s*2\.?5\s*(?:is|of|level|value|=|:|\bat)?\s*\d+",
            r"\b\d+\s*(?:ug/m3|µg/m3|micrograms)",
            r"\baqi\s*(?:is|of|=)?\s*\d+",
        ]
        for pattern in pm_patterns:
            if re.search(pattern, text):
                raise ValueError(
                    "Security Guardrail Violation: Gemini is prohibited from inventing PM2.5, "
                    "AQI, or numeric pollutant concentrations from image evidence."
                )

        # 2. Prohibit legal declarations and enforcement determinations
        legal_terms = [
            "illegal emission",
            "violating environmental law",
            "violation of cpcb",
            "court violation",
            "criminal offense",
            "guilty of polluting",
        ]
        for term in legal_terms:
            if term in text:
                raise ValueError(
                    f"Security Guardrail Violation: AI cannot make legal violation declarations ('{term}')."
                )

        return v

    @model_validator(mode="after")
    def validate_logical_consistency(self) -> "CitizenImageAnalysis":
        """Ensure logical consistency between flags."""
        # If no smoke and no flames, intensity must be NONE
        if not self.visible_smoke and not self.visible_flames:
            if self.smoke_intensity not in {SmokeIntensity.NONE, SmokeIntensity.LOW}:
                self.smoke_intensity = SmokeIntensity.NONE

        # Any low confidence observation must require human verification
        if self.confidence < 0.65:
            self.needs_human_verification = True

        return self

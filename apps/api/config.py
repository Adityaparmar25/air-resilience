"""Application configuration module using typed Pydantic settings."""

from typing import Optional
import os
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable overrides and validation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Google Cloud & Storage
    GOOGLE_CLOUD_PROJECT: Optional[str] = Field(
        default=None,
        description="Google Cloud Project ID for BigQuery, Vertex AI, Firestore, and Cloud Run",
    )
    GOOGLE_CLOUD_LOCATION: str = Field(
        default="global",
        description="Google Cloud location for Vertex AI models and services",
    )
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = Field(
        default=None,
        description="Optional local development path to Google service account JSON key (ADC used in production)",
    )
    STORAGE_BUCKET: Optional[str] = Field(
        default=None,
        description="Google Cloud Storage bucket name for persistent private citizen images",
    )
    FIREBASE_PROJECT_ID: Optional[str] = Field(
        default=None,
        description="Firebase Project ID for token verification and RBAC",
    )

    # Google AI / Vertex AI
    GEMINI_API_KEY: Optional[str] = Field(
        default=None,
        description="Gemini API Key for direct developer mode (not required in production Vertex AI mode)",
    )
    GEMINI_MODEL: str = Field(
        default="gemini-3.5-flash-lite",
        description="Gemini model name for multimodal vision analysis",
    )
    VERTEX_AI_ENABLED: bool = Field(
        default=False,
        description="Enable Google Cloud Vertex AI backend for multimodal inference via ADC",
    )

    # Operational & Analytical Database Settings
    FIRESTORE_DATABASE: str = Field(
        default="(default)",
        description="Firestore database instance for operational state",
    )
    BIGQUERY_DATASET: str = Field(
        default="air_resilience",
        description="BigQuery analytical dataset for historical observations and ML",
    )

    # Forecasting & Data Mode
    FORECAST_PROVIDER: str = Field(
        default="DEVELOPMENT",
        description="Forecast provider selection: DEVELOPMENT | BIGQUERY_TIMESFM",
    )
    DATA_MODE: str = Field(
        default="HISTORICAL_REPLAY",
        description="Operational data mode: LIVE | HISTORICAL_REPLAY",
    )
    CORS_ORIGINS: str = Field(
        default="*",
        description="Allowed CORS origins (comma-separated or '*' for dev)",
    )

    # Application Environment
    ENVIRONMENT: str = Field(
        default="development",
        description="Runtime environment: development | test | staging | production",
    )
    HOST: str = Field(default="0.0.0.0", description="API listen host")
    PORT: int = Field(default=8000, description="API listen port (Cloud Run standard)")
    LOG_LEVEL: str = Field(default="INFO", description="Logging verbosity")

    @property
    def ENV(self) -> str:
        """Alias for ENVIRONMENT for standard cloud environment checks."""
        return self.ENVIRONMENT

    @field_validator("ENVIRONMENT")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        allowed = {"development", "test", "staging", "production"}
        if v.lower() not in allowed:
            raise ValueError(f"ENVIRONMENT must be one of {allowed}, got: {v}")
        return v.lower()

    def validate_production_readiness(self) -> None:
        """Validate production configuration without requiring local credentials JSON."""
        if self.ENVIRONMENT == "production":
            missing = []
            if not self.GOOGLE_CLOUD_PROJECT:
                missing.append("GOOGLE_CLOUD_PROJECT")
            if not self.GOOGLE_CLOUD_LOCATION:
                missing.append("GOOGLE_CLOUD_LOCATION")
            if not self.GEMINI_MODEL:
                missing.append("GEMINI_MODEL")
            if not self.VERTEX_AI_ENABLED:
                missing.append("VERTEX_AI_ENABLED")

            if missing:
                raise RuntimeError(
                    f"Production startup error: missing required environment variables: {', '.join(missing)}"
                )

            # Wildcard CORS is strictly forbidden in production
            if self.CORS_ORIGINS.strip() == "*":
                raise RuntimeError(
                    "Production startup error: CORS_ORIGINS='*' (wildcard) is forbidden in production. "
                    "Must specify explicit domain origins (e.g. 'https://air-resilience.vercel.app')."
                )


_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Singleton getter for application settings."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

"""
VitalBand Configuration Module
"""

from pydantic import ConfigDict
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    PROJECT_NAME: str = "VitalBand Safety Platform"
    VERSION: str = "2.0.0"
    API_PREFIX: str = "/api"

    # Database
    # Default to async SQLite for local dev; set DATABASE_URL for Postgres in prod
    # e.g., postgresql+asyncpg://postgres:postgres@localhost:5432/vitalband
    DATABASE_URL: str = "sqlite+aiosqlite:///./vitalband_v2.db"

    # Security & Auth
    SECRET_KEY: str = "vitalband-production-secret-key-change-in-production-32bytes"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # Redis Pub/Sub & Queue
    REDIS_URL: Optional[str] = "redis://localhost:6379/0"

    # Clinical Alert Thresholds (Rule-Based Path)
    HR_LOW: int = 50
    HR_HIGH: int = 120
    SPO2_LOW: int = 92
    ALERT_COOLDOWN_SECONDS: int = 60

    # Voice Alerts
    VOICE_LANGUAGE: str = "ta"  # ta=Tamil, hi=Hindi, kn=Kannada, en=English

    model_config = ConfigDict(env_file=".env", extra="ignore")


settings = Settings()


import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BACKEND_DIR / ".env"

class Settings(BaseSettings):
    DATABASE_URL: str
    RAZORPAY_KEY_ID: str = "rzp_test_placeholder_id"
    RAZORPAY_KEY_SECRET: str = "rzp_test_placeholder_secret"
    RAZORPAY_WEBHOOK_SECRET: str = "razorpay_webhook_secret_123"
    MERCHANT_UPI_VPA: str = "merchant@razorpay"  # Override in .env with real UPI VPA
    FIREBASE_PROJECT_ID: str = "retail-automation-project"
    FIREBASE_SERVICE_ACCOUNT_JSON: str = ""
    JWT_SECRET: str = "8f3b23c9aef10e7dc2099351e220b3dfa6401918a287a93019318bdf881abfce"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    ENVIRONMENT: str = "development"
    CORS_ORIGINS: str = "*"

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        extra="ignore",
    )

settings = Settings()
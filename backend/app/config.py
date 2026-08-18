import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://postgres:ananyahebbark@localhost:5432/retail_automation"
    RAZORPAY_KEY_ID: str = "rzp_test_placeholder_id"
    RAZORPAY_KEY_SECRET: str = "rzp_test_placeholder_secret"
    RAZORPAY_WEBHOOK_SECRET: str = "razorpay_webhook_secret_123"
    FIREBASE_PROJECT_ID: str = "retail-automation-project"
    FIREBASE_SERVICE_ACCOUNT_JSON: str = ""
    JWT_SECRET: str = "8f3b23c9aef10e7dc2099351e220b3dfa6401918a287a93019318bdf881abfce"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    class Config:
        # Resolve the path to .env relative to this file
        env_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
        extra = "ignore"

settings = Settings()

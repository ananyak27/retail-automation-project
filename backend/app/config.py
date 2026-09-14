import os
from pydantic_settings import BaseSettings

# Absolute path to retail_automation.db inside backend directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "retail_automation.db").replace("\\", "/")
DEFAULT_SQLITE_URL = f"sqlite:///{DB_PATH}"

class Settings(BaseSettings):
    DATABASE_URL: str = DEFAULT_SQLITE_URL
    RAZORPAY_KEY_ID: str = "rzp_test_placeholder_id"
    RAZORPAY_KEY_SECRET: str = "rzp_test_placeholder_secret"
    RAZORPAY_WEBHOOK_SECRET: str = "razorpay_webhook_secret_123"
    FIREBASE_PROJECT_ID: str = "retail-automation-project"
    FIREBASE_SERVICE_ACCOUNT_JSON: str = ""
    JWT_SECRET: str = "8f3b23c9aef10e7dc2099351e220b3dfa6401918a287a93019318bdf881abfce"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    class Config:
        env_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
        extra = "ignore"

settings = Settings()

if "sqlite" in settings.DATABASE_URL and ("./" in settings.DATABASE_URL or settings.DATABASE_URL == "sqlite:///retail_automation.db"):
    settings.DATABASE_URL = DEFAULT_SQLITE_URL


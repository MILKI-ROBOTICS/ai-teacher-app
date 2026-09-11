from pathlib import Path
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    secret_key: str = "dev-only-change-me"
    database_url: str = "sqlite:///./teacher_intelligence.db"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.8-flash"
    upload_dir: str = "./data/uploads"
    max_upload_mb: int = 15
    access_token_expire_minutes: int = 720
    max_batch_files: int = 150
    ai_batch_workers: int = 6
    ai_max_retries: int = 2
    ai_retry_backoff_seconds: float = 1.0
    allowed_origins: str = "http://127.0.0.1:8000,http://localhost:8000,capacitor://localhost"
    public_app_url: str = "http://127.0.0.1:8000"
    session_cookie_name: str = "ati_session"
    signup_enabled: bool = True
    allow_demo_account: bool = True
    session_cookie_secure: bool = False
    session_cookie_samesite: str = "lax"
    offline_sync_batch_size: int = 100
    sync_operation_retention_days: int = 30
    max_login_attempts: int = 7
    login_window_seconds: int = 300
    identity_auto_accept_threshold: float = 0.92
    question_auto_accept_threshold: float = 0.90
    demo_teacher_email: str = "teacher@example.com"
    demo_teacher_name: str = "Teacher"
    demo_teacher_password: str = "Teacher123!"
    school_name: str = "My School"
    academic_year: str = "2026/27"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def validate_production_security(self):
        if self.app_env.lower() == "production":
            if len(self.secret_key) < 32 or self.secret_key == "dev-only-change-me":
                raise ValueError("SECRET_KEY must be a strong random value of at least 32 characters in production")
            if not self.session_cookie_secure:
                self.session_cookie_secure = True
            if self.session_cookie_name.startswith("__Host-") and not self.session_cookie_secure:
                raise ValueError("__Host- session cookies require Secure")
        return self


settings = Settings()
Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)

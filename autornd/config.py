from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    database_url: str = "sqlite+aiosqlite:///./autornd.db"

    api_host: str = "0.0.0.0"
    api_port: int = 8100

    log_level: str = "INFO"

    model_triage: str = "deepseek/deepseek-v4-flash"
    model_engineering: str = "minimax/minimax-m3"
    model_architecture: str = "z-ai/glm-5.3-20260816"
    model_research: str = "google/gemini-2.5-flash"
    model_escalation: str = "moonshotai/kimi-k3"
    model_premium: str = ""

    max_iterations: int = 5
    escalation_max_tokens: int = 4096
    escalation_recovery_attempts: int = 3

    chromadb_path: str = "./chromadb_data"

    api_key: str = ""
    jwt_secret: str = ""
    registration_enabled: bool = True

    autornd_profile: str = ""

    RUNTIME_MUTABLE: set[str] = {
        "max_iterations", "escalation_max_tokens", "escalation_recovery_attempts",
        "autornd_profile", "log_level",
    }

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @field_validator("max_iterations")
    @classmethod
    def validate_max_iterations(cls, v: int) -> int:
        if not 1 <= v <= 20:
            raise ValueError("max_iterations must be between 1 and 20")
        return v

    @field_validator(
        "model_triage", "model_engineering", "model_architecture",
        "model_research", "model_escalation",
    )
    @classmethod
    def validate_model_id(cls, v: str) -> str:
        if "/" not in v:
            raise ValueError(f"Model ID must contain '/' (got '{v}')")
        return v

    @field_validator("model_premium")
    @classmethod
    def validate_premium_model(cls, v: str) -> str:
        if v and "/" not in v:
            raise ValueError(f"Premium model ID must contain '/' (got '{v}')")
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid:
            raise ValueError(f"log_level must be one of {valid}")
        return v.upper()


settings = Settings()

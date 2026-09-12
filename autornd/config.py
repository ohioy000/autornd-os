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
    model_architecture: str = "z-ai/glm-5.3"
    model_research: str = "google/gemini-2.5-flash"
    model_escalation: str = "moonshotai/moonshot-v1-k3"

    max_iterations: int = 5
    escalation_max_tokens: int = 1500
    escalation_recovery_attempts: int = 3

    chromadb_path: str = "./chromadb_data"

    api_key: str = ""

    autornd_profile: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()

from pydantic import ValidationError, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    database_url: str = "sqlite+aiosqlite:///./autornd.db"

    api_host: str = "0.0.0.0"
    api_port: int = 8100

    log_level: str = "INFO"

    # AutoRnD ships no model defaults — it is a harness, not a model recommendation.
    # Every tier must name a model your provider serves. See .env.example.
    model_triage: str = ""
    model_engineering: str = ""
    model_architecture: str = ""
    model_escalation: str = ""
    # Both only run once project docs are ingested, so neither is required.
    model_research: str = ""
    model_ranker: str = ""
    # Outward lookups for facts the project's own documents do not cover. Needs
    # a search-capable model — a ":online" variant, or one with native search.
    model_search: str = ""
    model_premium: str = ""

    max_iterations: int = 5
    escalation_max_tokens: int = 16384

    # Validate judges work; it does not redo it. Measured against live models
    # an unbounded validator produced 15k output tokens for a green/red verdict,
    # taking three minutes and costing more than the implementation it checked.
    validate_max_tokens: int = 3000

    # A lookup wants room for figures and their sources, not an essay.
    search_max_tokens: int = 1200
    escalation_recovery_attempts: int = 3

    chromadb_path: str = "./chromadb_data"

    api_key: str = ""
    jwt_secret: str = ""
    registration_enabled: bool = True

    autornd_profile: str = ""

    # Which workflow graph to run. A bare name resolves inside workflows/.
    autornd_workflow: str = "engineering-rnd"

    RUNTIME_MUTABLE: set[str] = {
        "max_iterations", "escalation_max_tokens", "escalation_recovery_attempts",
        "autornd_profile", "autornd_workflow", "log_level",
        "validate_max_tokens", "search_max_tokens",
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
        "model_escalation", "model_research", "model_ranker", "model_search",
    )
    @classmethod
    def validate_model_id(cls, v: str) -> str:
        if v and "/" not in v:
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


# Tiers that run on every workflow. AutoRnD will not start without them.
_TIER_HELP = {
    "model_triage": "classification and routing — cheapest tier",
    "model_engineering": "implement, validate, review, feasibility — mid tier",
    "model_architecture": "planning and critical review — heavyweight tier",
    "model_escalation": "failure autopsy and recovery — reasoning tier",
}

# Tiers that only run when project documentation has been ingested, plus the
# opt-in premium reviewer. Unset simply means the feature is off.
_OPTIONAL_TIERS = {
    "model_research": "reads project docs and writes a grounded briefing",
    "model_ranker": "ranks retrieved documentation by usefulness",
    "model_search": "looks up facts the project documentation does not cover",
    "model_premium": "independent Double Check review",
}


def _config_help(problem: str, lines: list[str]) -> str:
    return "\n".join([
        f"AutoRnD is not configured — {problem}.",
        "",
        "AutoRnD ships no default models. You choose what runs at each tier:",
        "",
        *lines,
        "",
        "Set these in .env (copy .env.example) or as environment variables.",
        "Any model your provider serves will do — AutoRnD does not recommend one.",
        "See the README section 'Model Configuration'.",
    ])


def _build_settings() -> "Settings":
    try:
        cfg = Settings()
    except ValidationError as exc:
        bad = [
            (str(e["loc"][0]), e.get("msg", ""))
            for e in exc.errors()
            if str(e["loc"][0]) in _TIER_HELP or str(e["loc"][0]) in _OPTIONAL_TIERS
        ]
        if not bad:
            raise
        raise SystemExit(_config_help(
            f"{len(bad)} model id(s) are malformed",
            [f"  {name.upper():<20} {msg}" for name, msg in bad],
        )) from exc

    unset = [name for name in _TIER_HELP if not getattr(cfg, name).strip()]
    if unset:
        raise SystemExit(_config_help(
            f"no model is set for {len(unset)} of {len(_TIER_HELP)} tiers",
            [f"  {name.upper():<20} {_TIER_HELP[name]}" for name in unset],
        ))
    return cfg


settings = _build_settings()

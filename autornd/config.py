from pydantic import ValidationError, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    database_url: str = "sqlite+aiosqlite:///./autornd.db"

    # Loopback, because AutoRnD has no rate limiting and spends real money:
    # the safe default is the one that cannot be reached from another machine.
    # Read only when launching via `python -m autornd.main` — the bundled
    # Dockerfile passes --host 0.0.0.0 on its own command line, so containers
    # are unaffected. Serving a LAN from the module entry point now needs
    # API_HOST=0.0.0.0 set deliberately. This was 0.0.0.0 since the initial
    # commit while both .env.example and the README said it defaulted to
    # loopback; the documents were right about what it should be.
    api_host: str = "127.0.0.1"
    api_port: int = 8100

    log_level: str = "INFO"

    # AutoRnD ships no model defaults — it is a harness, not a model recommendation.
    # Every tier must name a model your provider serves. See .env.example.
    model_triage: str = ""
    model_engineering: str = ""
    model_architecture: str = ""
    model_escalation: str = ""
    # Research is core, not an enhancement. Grounding a request in real
    # documentation and looking up what that documentation does not cover is
    # the thing that separates this from a model with a checklist — and a
    # measured run showed a capable model confabulating a component and an RF
    # limit with full confidence. There is no confidence signal to gate that
    # on, so the lookup is not optional.
    model_research: str = ""
    model_search: str = ""
    # Ranking only improves the order of retrieved context; without it,
    # retrieval falls back to embedding distance. A degradation, not a break.
    model_ranker: str = ""
    model_premium: str = ""

    # Pin which upstream serves requests, comma separated, highest first. Empty
    # means the provider decides, which favours availability over
    # reproducibility — and the two are not the same: a model id served by a
    # different provider produced shorter replies, a 30x lower price and
    # different risk classifications between two runs of one eval suite.
    openrouter_provider_order: str = ""

    max_iterations: int = 5
    escalation_max_tokens: int = 16384

    # Validate judges work; it does not redo it. Measured against live models
    # an unbounded validator produced 15k output tokens for a green/red verdict,
    # taking three minutes and costing more than the implementation it checked.
    #
    # 3000 was too tight, though, and tight in the worst way: the default
    # engineering tier is a reasoning model, and on a hard request it spent the
    # whole 3000 on reasoning and emitted nothing — three times, so the run
    # failed having paid for 9000 tokens of nothing. A ceiling is only billed
    # when it is used, so raising it costs nothing on the runs that were already
    # fine and rescues the ones that were not. Still far below the 15k an
    # unbounded validator reached.
    validate_max_tokens: int = 8000

    # Budget for one lookup, which carries every blocking gap at once.
    #
    # Measured, not assumed. Sonar-pro bills $15.00 per million output tokens
    # plus about $0.007 a request, and the model fills whatever cap it is given
    # (2907 of 3000). So at a 3000-token cap the fee is 13% of the cost and
    # tokens are 87% — "it is priced per call, so give it the maximum" is the
    # opposite of what the billing does.
    #
    # Accuracy tracks the token budget almost linearly. Graded against published
    # figures across eight sectors: ~4800 tokens recovered 7/8, ~2900 recovered
    # 5/8, ~1400 recovered 3/8 — roughly one sector per 800 tokens. Tokens buy
    # figures, so this is a real trade rather than waste to be cut.
    #
    # Which is why it scales with consequence instead of being one number. Low
    # risk looks nothing up at all; medium gets a lean budget; work where a
    # wrong figure is expensive gets room to answer completely.
    search_max_tokens: int = 1500

    # Budget when being wrong is expensive — high and critical risk. About
    # $0.067 a lookup against $0.028 at the lean budget: the extra 2500 tokens
    # are the difference between a complete answer and a truncated one on the
    # work that can least afford a missing figure.
    search_max_tokens_consequential: int = 4000
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
        "search_max_tokens_consequential",
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
    "model_research": "grounds the request in documentation and briefs every phase",
    "model_search": "looks up facts the documentation does not cover, with sources",
}

# Genuine enhancements. Unset means the feature is off, and nothing breaks.
_OPTIONAL_TIERS = {
    "model_ranker": "ranks retrieved documentation by usefulness",
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

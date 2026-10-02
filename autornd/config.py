import os

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
    # The heterogeneous judge (Ruling D35). When set, the implementation-judging
    # nodes — domain_review, validate, review, rework_review — run on THIS model
    # instead of the engineering tier, so a different pretraining lineage reviews
    # the work rather than the model that produced it grading its own blind spots.
    # Optional: unset means those nodes fall back to the engineering tier (the
    # prior homogeneous behaviour), so nothing breaks when it is empty.
    model_judge: str = ""

    # Pin which upstream serves requests, comma separated, highest first. Empty
    # means the provider decides, which favours availability over
    # reproducibility — and the two are not the same: a model id served by a
    # different provider produced shorter replies, a 30x lower price and
    # different risk classifications between two runs of one eval suite.
    openrouter_provider_order: str = ""

    # Preferred-first failover beyond the pin. Empty/false (default) keeps
    # hard pins: the router serves ONLY the named providers and 404s when
    # its filters strip them all — measured 2026-09-26 on four traces
    # (076/077/078/082), where the same 112768-token ask 404d pinned and
    # served first try with fallbacks allowed, through the pin itself.
    # Set to 1/true to let the router fail over instead of 404ing. The
    # pin is still tried first; who answers is recorded per call, so the
    # ledger keeps attribution. Owner config (like the order itself).
    openrouter_provider_fallbacks: str = ""

    max_iterations: int = 5

    # How many times review may send work back before the run escalates.
    # Measured §15.1: three of four traces ended blocked at review (n=1 each),
    # with the findings unread by anything downstream. A round costs about one
    # body pass, $0.02-0.05 [derived: §15.2 per-trace cost], and exhaustion
    # routes to the escalation autopsy rather than looping — review and
    # implement can disagree indefinitely, the graph cannot.
    review_rework_attempts: int = 2

    # The plan node ran at Specialist.run's 16,384 default, with no setting of
    # its own, while every serving of the planning model advertises a ceiling
    # above 262,000. On hard requests it burned seven full-budget retries
    # returning nothing (§14.1) — the same shape as validate at 3000 tokens
    # (§6.4), where a reasoning model spent the whole budget thinking and
    # emitted no text. A ceiling is billed only when used, so headroom costs
    # nothing on the runs that were already fine, and one 32k success is
    # cheaper than seven 16k failures.
    plan_max_tokens: int = 32768
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

    # Ceiling for the judge tier's nodes (domain_review, validate, review,
    # rework_review) when a judge model is configured. A judge emits a verdict
    # with findings, not a second implementation, so it is capped tight and
    # separately from the plan/implement ceiling — this is the guard that keeps a
    # premium judge model's per-token rate from running away across the
    # high-frequency review nodes (Ruling D35).
    judge_max_tokens: int = 8000

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

    # Ruling D38: the API path's declared time budget, in seconds. A budgeted
    # run that is running out of time ends by its own terminal (status
    # blocked, a typed watchdog record) rather than running unbounded.
    # Measured need: 094 was killed at 3,600 s mid-review after its build
    # judges had agreed at $0.070, and returned nothing.
    #
    # Ruling D45 (2): every API run carries one now, so the default is a
    # bound rather than None. 1800 measured 2026-10-02: 098's three runs had
    # 1,800 s budgets and reached judge-approved answers at 15.6 and 20.7
    # minutes. The owner may change it in .env (G-3).
    run_time_budget_seconds: float | None = 1800.0

    # Ruling D45 (2): the API run's spend ceiling, in USD. Runs measured
    # since 102 cost $0.02 to $0.19 end to end, so 0.50 is several whole runs
    # of headroom and still a bound on an unwatched endpoint. The owner may
    # change it in .env (G-3).
    run_spend_ceiling_usd: float = 0.50

    # Ruling D45 (6): how many API runs may be in flight at once. A per-run
    # ceiling bounds one run, not a caller who submits many. Measured
    # 2026-10-02: the owner runs one workflow at a time, and two leave room
    # for one synchronous call beside one asynchronous run. A submission
    # beyond the cap is refused with 429 and creates no row. The owner may
    # change it in .env (G-3).
    max_concurrent_runs: int = 2

    # Ruling D45 (1): with neither API_KEY nor JWT_SECRET configured, the API
    # serves loopback callers only. This override serves remote callers
    # anyway — unauthenticated, spending the owner's credits — so it is off
    # by default, logged at startup and reported by /api/health.
    allow_unauthenticated_remote: bool = False

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
        "review_rework_attempts", "plan_max_tokens", "judge_max_tokens",
    }

    # The suite never reads the owner's .env (ARCH-20261002-112): with
    # AUTORND_TESTING set — by tests/conftest.py, before the first import —
    # there is no dotenv file at all, so no setting can arrive from one. A
    # checkout that holds the owner's .env and a checkout that does not are
    # the same configuration for the suite.
    model_config = {
        "env_file": None if os.environ.get("AUTORND_TESTING") else ".env",
        "env_file_encoding": "utf-8",
    }

    @field_validator("run_time_budget_seconds", mode="before")
    @classmethod
    def validate_run_time_budget(cls, v):
        # `RUN_TIME_BUDGET_SECONDS=` with no value reads as unset, not as a
        # parse failure that stops the server from starting.
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        if float(v) <= 0:
            raise ValueError("run_time_budget_seconds must be positive")
        return float(v)

    @field_validator("run_spend_ceiling_usd", mode="before")
    @classmethod
    def validate_run_spend_ceiling(cls, v):
        if isinstance(v, str) and not v.strip():
            raise ValueError("run_spend_ceiling_usd must be a positive number")
        if float(v) <= 0:
            raise ValueError("run_spend_ceiling_usd must be positive")
        return float(v)

    @field_validator("max_concurrent_runs", mode="before")
    @classmethod
    def validate_max_concurrent_runs(cls, v):
        if int(v) < 1:
            raise ValueError("max_concurrent_runs must be at least 1")
        return int(v)

    @field_validator("max_iterations")
    @classmethod
    def validate_max_iterations(cls, v: int) -> int:
        if not 1 <= v <= 20:
            raise ValueError("max_iterations must be between 1 and 20")
        return v

    @field_validator(
        "model_triage", "model_engineering", "model_architecture",
        "model_escalation", "model_research", "model_ranker", "model_search",
        "model_judge",
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
    "model_judge": "heterogeneous judge for domain_review/validate/review — "
                   "falls back to the engineering tier when unset",
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


# Ruling D39: the loop bounds a workflow names by setting, read from this one
# place by every path that runs a workflow. The API path (engine/workflow.py)
# and the eval CLI (evals/cli.py) each kept a hand-written map, and they
# drifted: the API path's had no review_rework_attempts, so any blocking review
# there ended BLOCKED with a ConditionError instead of running the rework loop
# (reproduced in ARCH-20260930-095's response). tests/test_settings_map.py
# loads every workflows/*.yaml and fails if one names a bound missing here.
# Token ceilings are not in this map: adapter._max_tokens reads them straight
# from `settings`, and the executor reads its lookup only for loop bounds.
LOOP_BOUND_SETTINGS = (
    "max_iterations", "escalation_recovery_attempts", "review_rework_attempts",
)


def settings_lookup() -> dict[str, int]:
    """The graph executor's settings_lookup: each loop bound by its name.

    Read when called, so a runtime settings change (RUNTIME_MUTABLE) reaches
    the next run on every path alike.
    """
    return {name: getattr(settings, name) for name in LOOP_BOUND_SETTINGS}

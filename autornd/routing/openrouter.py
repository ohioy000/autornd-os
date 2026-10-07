"""OpenRouter client with model routing per function."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx
from pydantic import ValidationError

from autornd.config import settings

logger = logging.getLogger(__name__)

# A 429 here is not our rate: it is OpenRouter's upstream capacity for one
# (model, provider) pair, and the body says "Please retry shortly". Pinned
# tiers run with `allow_fallbacks: False` on purpose (§6.1 — pinning is a
# QUALITY control), so there is nowhere else for the request to go and a
# transient shortage became a dead run. Measured 2026-09-20: the same pin
# 429'd and then completed 90 s later, and a sweep of six servings read as
# six failures when the rotation served the identical model on demand.
#
# Bounded and short, because the pinned tier cannot fall back and the caller
# is holding a scenario clock. Retries bill like any other attempt.
_RATE_LIMIT_ATTEMPTS = 3
_RATE_LIMIT_BACKOFF_S = 2.0


@dataclass
class ModelResponse:
    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost: float
    # Why generation stopped, and which upstream served it. Both matter when a
    # reply comes back empty: a reasoning model that spent its whole budget on
    # reasoning returns "length" with no content, which is a very different
    # problem from a provider returning nothing at all.
    finish_reason: str | None = None
    provider: str | None = None
    # Where a search-backed answer came from. Without these a lookup is just
    # another confident assertion, which is the thing it exists to replace.
    citations: list[str] = field(default_factory=list)
    # Tool calls the model requested (arch-20261003-119, arm B's
    # tool loop). Empty unless the call offered tools and the model
    # asked for them; the caller executes the tool and answers with
    # the result on the next call.
    tool_calls: list[dict[str, Any]] = field(default_factory=list)



def provider_fallbacks_allowed() -> bool:
    """Whether a pinned tier may fail over beyond its pin.

    Measured 2026-09-26 (probe, committed in the 082 record): the same
    112768-token ask to `z-ai/glm-5` pinned to StreamLake 404s with
    `allow_fallbacks: False` (Context Length filter strips the pin, zero
    candidates remain) and serves first try with `allow_fallbacks: True`
    — through StreamLake itself. The killer was never the ceiling, the
    model, or the provider; it was fallback-off meeting the filter.

    Hard pins stay the default (reproducibility — §6.1 measured why).
    Setting this opens preferred-first failover: the pin is still tried
    first, but the router may serve beyond it instead of 404ing. Who
    answers is recorded per call (`providers_by_function`), so the
    ledger keeps attribution and a failover run reads as one.
    """
    raw = (settings.openrouter_provider_fallbacks or "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def provider_order_for(function: str) -> list[str]:
    """Which providers may serve this tier, highest preference first.

    Per tier, because a pin has to be. Tiers run different models and no
    provider serves them all — a global pin of the triage provider would have
    the search tier asking it for a model it does not host, and with fallbacks
    disabled that is a hard failure rather than a slow one. Shipping a global
    pin and advising people to use it was a defect; this is the fix.

    Syntax, comma separated:

        StreamLake                      every tier prefers StreamLake
        triage:StreamLake,search:       triage pinned, search left free
        triage:StreamLake,Together      triage pinned, everything else Together

    A tier named with an empty value is explicitly unpinned, which is how one
    tier opts out of a global default.
    """
    raw = (settings.openrouter_provider_order or "").strip()
    if not raw:
        return []

    general: list[str] = []
    per_tier: dict[str, list[str]] = {}
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        if ":" in entry:
            tier, _, provider = entry.partition(":")
            tier, provider = tier.strip().lower(), provider.strip()
            per_tier.setdefault(tier, [])
            if provider:
                per_tier[tier].append(provider)
        else:
            general.append(entry)

    if function.lower() in per_tier:
        return per_tier[function.lower()]
    return general


def _raise_for_status(resp, what: str) -> None:
    """raise_for_status, but keep the half of the error that explains it.

    httpx renders only the status line, and a status code is not a diagnosis. A
    403 here was read as rate limiting and blamed on concurrent runs; the body
    said `Workspace weekly budget of $10.00 exceeded`, which is a different
    problem with a different fix, and it had been discarded at the point of
    raising. One request recovered it. The provider puts the reason in the body
    on every error class it returns — spend ceilings, data-policy refusals,
    unknown models — so the body travels with the exception from here on.
    """
    # Status code rather than `is_success`, so this works against any response
    # object with a status and a body — the test doubles included.
    if resp.status_code < 400:
        return
    detail = ""
    try:
        payload = resp.json()
        error = payload.get("error") or {}
        detail = error.get("message") or resp.text
        # The message is sometimes a category rather than a reason. A 429 reads
        # "Provider returned error", while `metadata.raw` carries the upstream's
        # own sentence — "<model> is temporarily rate-limited upstream. Please
        # retry shortly" — which names the model, says the condition is
        # transient, and is the difference between diagnosing a bad serving and
        # diagnosing a busy one. Measured 2026-09-20: ten 429s across five
        # servings were read as five failing providers because this half of the
        # body was dropped here. Same lesson as the 403 above, one status code
        # along.
        raw = (error.get("metadata") or {}).get("raw")
        if raw and str(raw) not in str(detail):
            detail = f"{detail} — {raw}"
    except Exception:
        detail = resp.text
    raise httpx.HTTPStatusError(
        f"{resp.status_code} from {what}: {str(detail)[:400]}",
        request=resp.request, response=resp,
    )


class BudgetExceeded(RuntimeError):
    """A run asked for more calls or more money than it was allowed."""


# D45 amendment (b): a bound, not a mean. The prompt's worst-case tokens used
# to be estimated as prompt_chars / 4 — a mean, which under-counts on any
# prompt a tokenizer finds expensive and is therefore not a worst case at all.
# A byte-level tokenizer never emits more tokens than bytes, so the prompt's
# UTF-8 byte length IS an upper bound on its tokens.
#
# The allowance covers what the chat template adds around the content strings.
# Measured 2026-10-02 on the wire shape this client sends: the JSON message
# envelope (roles and scaffolding) is 96 bytes for the two-message chat every
# phase sends, 33 bytes per additional message (json.dumps of the messages
# array with content strings excluded). The three chat-template families in
# circulation (ChatML, Llama-3, Mistral) wrap turns in under 64 bytes of
# markers each. 512 bytes is those figures rounded up to a power of two:
# headroom above a bound, and bytes rather than tokens so the bound holds.
CHAT_TEMPLATE_ALLOWANCE_BYTES = 512


def _prompt_bytes(*parts: str) -> int:
    """UTF-8 byte length of a prompt — the token bound described above."""
    return sum(len(p.encode("utf-8")) for p in parts)


class _Reservation:
    """One dispatch's worst case, released only by the call that made it.

    D47's instrument repair of D45 (5): the guard held reservations in a FIFO
    deque and released whatever was oldest when a call reconciled, so
    out-of-order completions moved ANOTHER call's worst case. The advisor's
    case: with A ($0.06) in flight, B ($0.01) completing released A's
    reservation, and a $0.05 call then dispatched and booked $0.111 against a
    $0.10 ceiling. Identity is the fix: a token travels with its call and only
    that call can release it.
    """

    __slots__ = ("worst", "function", "model", "released")

    def __init__(self, worst: float, function: str, model: str) -> None:
        self.worst = worst
        self.function = function
        self.model = model
        self.released = False


def _failure_kind(exc: BaseException) -> str:
    """The kind of failure that made a dispatched call unreconcilable.

    D45 (5) names four: an error status that is not retried, a transport
    error, a timeout, a cancellation. Anything else is recorded under its own
    class name rather than folded into a class it does not belong to
    (convention 26).
    """
    if isinstance(exc, asyncio.CancelledError):
        return "cancelled"
    if isinstance(exc, httpx.TimeoutException):
        return "timeout"
    if isinstance(exc, httpx.HTTPStatusError):
        return "error_status"
    if isinstance(exc, httpx.TransportError):
        return "transport_error"
    return type(exc).__name__


class SpendGuardRefused(BudgetExceeded):
    """F3: a call whose worst case could not fit the remaining budget was not
    made. Typed, so the record names the tier, model, worst case and what
    remained. The message starts 'stopped at $', the spend-ceiling form the
    eval runner already routes on."""

    def __init__(self, function: str, model: str, worst_case: float,
                 remaining: float, spend: float, ceiling: float) -> None:
        self.function, self.model = function, model
        self.worst_case, self.remaining = worst_case, remaining
        super().__init__(
            f"stopped at ${spend:.4f} before a call (ceiling ${ceiling:.4f}): "
            f"the {function} call to {model} could cost up to "
            f"${worst_case:.4f}, and ${remaining:.4f} remained")


class ProviderFailure(RuntimeError):
    """A provider ended the run without producing usable output.

    Raised when every retry for one call consumed its budget and emitted
    nothing — the -071 shape: `finish_reason=length`, the full
    `completion_tokens` spent, `content` empty, three attempts, zero
    verdicts. It is NOT a schema rejection (a reply the truth table could
    not repair) and NOT a parse failure (text that was not JSON): there
    was no reply at all, so there was nothing to validate or parse.
    Carries the serving that produced it, because a tier is not a system
    and "the engineering tier failed" names no one. The message is the
    last attempt's detail, so the terminal that quotes it names the
    provider, the finish reason, and the spent budget.
    """

    def __init__(self, function: str, provider: str | None, detail: str):
        super().__init__(detail)
        self.function = function
        self.provider = provider

    # The serving that produced the failure, for the unit record beside
    # `rejections_by_provider`. Recorded as "provider/model" when both are
    # known — the ledger counts servings, not providers alone — else
    # whichever half is known, else None.
    def serving(self, model: str | None = None) -> str | None:
        if self.provider and model:
            return f"{self.provider}/{model}"
        return self.provider


def _rejection_note(error: Exception) -> str:
    """Tell the next attempt what the last one got wrong.

    Pydantic's message already names the offending value and lists every
    permitted one, which is more than a re-ask conveys and more than a
    hand-written hint would.
    """
    return (
        "\n\nYour previous reply was rejected and must be corrected:\n"
        f"{error}\n"
        "Return only a JSON object. Use only values the schema permits — do not "
        "invent new field values, and do not add fields that are not in the schema."
    )


class OpenRouterClient:
    """Async client that routes requests to the right model via OpenRouter."""

    FUNCTION_MODELS: dict[str, str] = {
        "triage": settings.model_triage,
        "engineering": settings.model_engineering,
        "architecture": settings.model_architecture,
        "escalation": settings.model_escalation,
        "research": settings.model_research,
        "search": settings.model_search,
        **({"ranker": settings.model_ranker} if settings.model_ranker else {}),
        **({"premium": settings.model_premium} if settings.model_premium else {}),
        # Ruling D35: when set, the judge tier serves domain_review/validate/
        # review/rework_review. Dropped when unset so resolve_model falls back to
        # the engineering tier — the prior homogeneous behaviour.
        **({"judge": settings.model_judge} if settings.model_judge else {}),
    }

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key = api_key or settings.openrouter_api_key
        self.base_url = base_url or settings.openrouter_base_url
        self._client: httpx.AsyncClient | None = None

        # Spend and call counts live here, on the one object every request must
        # pass through, because accounting kept anywhere else gets bypassed.
        # It was: the phase runner tallied cost inside run_ai, so research
        # lookups, context expansion and reranking — the three most expensive
        # paths — were free as far as any report was concerned. Eight sectors
        # doing roughly thirty-two search calls self-reported $0.0025.
        self.spend: float = 0.0
        self.calls: int = 0
        self.spend_by_function: dict[str, float] = {}
        self.calls_by_function: dict[str, int] = {}
        # Which upstream actually served each tier. A model id is not a system:
        # the same id served by two providers is two different systems, with
        # different output lengths, latencies, prices and answers. Measured —
        # one triage model moved provider between two runs of the same suite and
        # went from $0.0003 to $0.00001 a call, 70-token replies, and a
        # different risk classification on four sectors. Without this recorded,
        # that looks like a code regression.
        self.providers_by_function: dict[str, set[str]] = {}
        # Optional budgets, used by experiments. Left unset in production: an
        # abort half-way through a real workflow throws away the work done so
        # far, whereas an experiment that runs away is a thing that has already
        # happened here once — forty minutes and $1.28 for an inconclusive run.
        self.tokens_by_function: dict[str, dict[str, int]] = {}
        # Schema rejections per tier. The retry loop has always logged these at
        # WARNING, but the eval CLI configures no logging, so they reached only
        # the lastResort stderr handler — and of nine recorded runs, three run
        # logs survived long enough to be counted. A rate that can only be
        # measured from a temp file is not an instrument. Counted here, it lands
        # in the JSONL beside the normalisation count it must be read with:
        # a normalisation is a reply the truth table repaired, a rejection is a
        # reply it could not.
        self.rejections_by_function: dict[str, int] = {}
        # And by serving, because a tier is not a system — B4's whole lesson.
        # Asked which serving refused the four verdicts that killed four
        # convergence traces, the per-tier count could only answer "the
        # engineering tier", and the tier's unpinned provider *set* per unit
        # was 4/4 OpenInference against 12/18 of the survivors: proportional,
        # therefore silent. A count attributed to the serving that produced the
        # reply can answer it; a count attributed to the tier never can.
        self.rejections_by_provider: dict[str, int] = {}
        # EVERY retry, by class, so the two counters above can be read as what
        # they are rather than as what they look like.
        #
        # Measured 2026-09-22 on the B17 prohibition run: three retry events in
        # stderr — one JSON parse failure and two empty replies — and both
        # rejection counters EMPTY in the unit record. The counters were right:
        # they are scoped to schema rejections, and none of the three was one.
        # But a reader seeing `rejections_by_tier: {}` beside 23 calls cannot
        # tell "nothing was refused" from "the refusals were a class this does
        # not count", and convention 26 makes that the instrument's defect
        # rather than the reader's error.
        #
        # So this counts all three classes and the record reconciles them:
        # total == attributed + unattributed, with the unattributed classes
        # named. Widening `rejections_by_function` instead would have destroyed
        # the distinction its own comment above exists to preserve — a schema
        # rejection is a reply the truth table could not repair, which an empty
        # reply is not.
        self.retries_by_kind: dict[str, int] = {}
        self.provider_failures: list[dict[str, Any]] = []
        self.call_ceiling: int | None = None
        self.spend_ceiling: float | None = None
        # F3: calls the pre-call guard could not bound, because the model's
        # rate was not in the loaded catalogue. They were made, and are
        # bounded only by the after-the-call check (convention 28).
        self.spend_guard_blind: list[dict[str, Any]] = []
        # D45 (5), repaired by D47: the guard HOLDS across concurrent calls,
        # failed calls and reranking — and each reservation is IDENTIFIED, so
        # only the call that made one releases it (see _Reservation for the
        # out-of-order case that motivated this). A call that fails after
        # dispatch keeps its own worst case as unreconciled liability for the
        # rest of the run: the money may have been spent (a request that
        # errored server-side can still be billed), so the worst case is
        # counted against the ceiling and recorded with the kind of failure
        # that prevented reconciliation.
        self._reservations: list[_Reservation] = []
        self.reserved: float = 0.0
        self._in_flight: int = 0
        self.unreconciled_liability: float = 0.0
        self.failed_after_dispatch: list[dict[str, Any]] = []

    def _account(self, function: str, cost: float,
                 provider: str | None = None,
                 prompt_tokens: int = 0, completion_tokens: int = 0,
                 reservation: _Reservation | None = None) -> None:
        """Record one billable request. Called for every request, no exceptions.

        Budgets are enforced here rather than by the caller, so a ceiling covers
        research lookups and reranking too. A run that exceeds one has already
        paid for the request in hand — this stops the next one.

        D47: this books cost and releases NOTHING. Releasing belongs to the
        call site that made the reservation (chat/rerank), because a test
        double books cost without ever having guarded — the old FIFO release
        here let such a booking consume another call's reservation.
        """
        self.calls += 1
        self.calls_by_function[function] = self.calls_by_function.get(function, 0) + 1
        if provider:
            self.providers_by_function.setdefault(function, set()).add(provider)
        if cost:
            self.spend += cost
            self.spend_by_function[function] = (
                self.spend_by_function.get(function, 0.0) + cost)
        # Tokens per tier, not just money. Cost conflates rate with volume, so a
        # tier that got more expensive cannot be told from one that was handed
        # more to read — which is exactly the question the escalation line
        # raises now that the failure log carries every criterion and finding.
        if prompt_tokens or completion_tokens:
            seen = self.tokens_by_function.setdefault(
                function, {"prompt": 0, "completion": 0})
            seen["prompt"] += prompt_tokens
            seen["completion"] += completion_tokens

        if self.call_ceiling is not None and self.calls > self.call_ceiling:
            raise BudgetExceeded(
                f"stopped at {self.calls} model calls (ceiling {self.call_ceiling}); "
                f"raise max_calls on the scenario if this is expected. "
                f"By tier: {self.calls_by_function}"
            )
        if self.spend_ceiling is not None and self._committed() > self.spend_ceiling:
            raise BudgetExceeded(
                f"stopped at ${self._committed():.4f} (ceiling "
                f"${self.spend_ceiling:.4f}). By tier: "
                f"{ {k: round(v, 4) for k, v in self.spend_by_function.items()} }"
                + (f". Unreconciled liability kept from failed calls: "
                   f"${self.unreconciled_liability:.4f}"
                   if self.unreconciled_liability else "")
            )

    def _committed(self) -> float:
        """What this run is on the hook for: booked spend, plus the worst case
        of every call still in flight, plus the worst case of every call that
        failed after dispatch and could not be reconciled."""
        return self.spend + self.reserved + self.unreconciled_liability

    def _release(self, reservation: _Reservation | None) -> None:
        """The call that made a reservation is the call that releases it.

        D47: by identity, never by order. A call that reserved nothing
        (blind, or no ceiling set) releases nothing — and a test double that
        books cost without guarding never reaches here at all.
        """
        self._in_flight = max(0, self._in_flight - 1)
        if reservation is None or reservation.released:
            return
        reservation.released = True
        self._reservations.remove(reservation)
        self.reserved -= reservation.worst

    def _fail_call(self, function: str, model: str, kind: str,
                   reservation: _Reservation | None) -> None:
        """D45 (5): a call that failed after dispatch keeps its own worst case.

        The request left this process, so the money may have been spent — a
        call that errored server-side can still be billed — and no actual cost
        will ever arrive to replace the estimate. The reservation becomes
        unreconciled liability: counted against the ceiling for the rest of the
        run, and recorded with the kind of failure that made reconciliation
        impossible (error_status, timeout, transport_error, cancelled). The
        reservation is the call's own — a failed call keeps its own worst
        case, never another in-flight call's. A call that never reserved (an
        unrated model) keeps nothing: no worst case was ever computed, and
        inventing one is the guessing the guard exists to avoid; its
        blindness is already recorded.
        """
        self._in_flight = max(0, self._in_flight - 1)
        worst = 0.0
        if reservation is not None and not reservation.released:
            reservation.released = True
            self._reservations.remove(reservation)
            self.reserved -= reservation.worst
            worst = reservation.worst
            self.unreconciled_liability += worst
        self.failed_after_dispatch.append({
            "function": function, "model": model, "kind": kind,
            "worst_case": round(worst, 6),
        })

    def _guard_spend(self, function: str, model: str, prompt_bytes: int,
                     max_tokens: int) -> _Reservation | None:
        """Refuse, before it is made, a call that cannot fit — and reserve it.

        F3 (ARCH-20261001-104): 102's IA run ended at $0.1570 against $0.08
        because one escalation call cost $0.1142 and the ceiling was only
        checked after the call. D45 amendment (b): the prompt side is now a
        bound (UTF-8 bytes plus the template allowance) rather than a mean.
        D45 (5), repaired by D47: the worst case is RESERVED, by identity,
        until the call that made it is reconciled or fails — a reservation
        is released only by the call that made it, never by whichever is
        oldest. The guard is blind — the call is made and the blindness
        recorded, never guessed — in three ways: the model is not in the
        catalogue, the catalogue prices neither side of the call (an absent
        component is unknown, not free), or the entry carries a charge
        the worst case cannot bound (a component priced above the rate
        its side is charged at, or one the bound does not know). A
        per-request charge is part of the bound, added once per call.
        Returns the reservation, or None for a blind call."""
        if self.call_ceiling is not None and (
                self.calls + self._in_flight + 1 > self.call_ceiling):
            # Amendment (c): checked before dispatch, and every in-flight call
            # counts — blind ones included — or a fan-out could start ten calls
            # at the ninth call.
            raise BudgetExceeded(
                f"stopped at {self.calls} model calls with "
                f"{self._in_flight} in flight (ceiling "
                f"{self.call_ceiling}); raise max_calls on the scenario if "
                f"this is expected. By tier: {self.calls_by_function}"
            )
        if self.spend_ceiling is None:
            return None
        rates = _model_pricing.get(model)
        if not rates:
            self.spend_guard_blind.append({"function": function, "model": model})
            return None
        prompt_rate, completion_rate = rates
        worst = ((prompt_bytes + CHAT_TEMPLATE_ALLOWANCE_BYTES) * prompt_rate
                 + max_tokens * completion_rate
                 + _model_per_request.get(model, 0.0))
        remaining = self.spend_ceiling - self._committed()
        if worst > remaining:
            raise SpendGuardRefused(function, model, worst, remaining,
                                    self._committed(), self.spend_ceiling)
        reservation = _Reservation(worst, function, model)
        self._reservations.append(reservation)
        self.reserved += worst
        return reservation

    def reset_accounting(self) -> None:
        self.spend = 0.0
        self.spend_guard_blind = []
        self._reservations.clear()
        self.reserved = 0.0
        self._in_flight = 0
        self.unreconciled_liability = 0.0
        self.failed_after_dispatch = []
        self.calls = 0
        self.tokens_by_function = {}
        self.spend_by_function = {}
        self.calls_by_function = {}
        self.providers_by_function = {}
        self.rejections_by_function = {}
        self.rejections_by_provider = {}
        self.retries_by_kind = {}
        # Provider failures that ended a call: one entry per exhausted
        # empty-reply sequence, naming the tier and the serving. Beside
        # `rejections_by_provider`, not inside it — an empty reply is not a
        # schema rejection, and widening that counter would destroy the
        # distinction its own comment exists to preserve.
        self.provider_failures = []

    # Retry classes. Named constants rather than string literals at the call
    # sites, because the reconciliation below subtracts one from the total and
    # a typo there would silently move events into "unattributed".
    RETRY_SCHEMA_REJECTION = "schema_rejection"
    RETRY_EMPTY_REPLY = "empty_reply"
    RETRY_PARSE_FAILURE = "parse_failure"

    def _count_retry(self, kind: str) -> None:
        self.retries_by_kind[kind] = self.retries_by_kind.get(kind, 0) + 1

    def retry_reconciliation(self) -> dict[str, Any]:
        """Every retry, split into the part the rejection counters explain and the part they do not.

        Convention 28: this states the total BEFORE the breakdown, and the
        unattributed figure is always present — never omitted when it is zero,
        because an absent field and a measured zero are different claims and
        only one of them is evidence.
        """
        total = sum(self.retries_by_kind.values())
        attributed = self.retries_by_kind.get(self.RETRY_SCHEMA_REJECTION, 0)
        unattributed = total - attributed
        return {
            "total": total,
            "attributed": attributed,
            "unattributed": unattributed,
            "by_kind": dict(self.retries_by_kind),
            # Named so a reader of an empty rejection count knows what it
            # excludes without reading this file.
            "excluded_from_rejection_counters": [
                self.RETRY_EMPTY_REPLY, self.RETRY_PARSE_FAILURE],
        }

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "HTTP-Referer": "https://github.com/ohioy000/autornd-os",
                    "X-Title": "AutoRnD",
                    "Content-Type": "application/json",
                },
                timeout=120.0,
            )
        return self._client

    def get_model(self, function: str) -> str:
        if function == "independent":
            return self.independent_model() or settings.model_engineering
        return self.FUNCTION_MODELS.get(function, settings.model_engineering)

    def independent_model(self) -> str | None:
        """A model for the independent pass, or None if there isn't an honest one.

        The premium tier when configured, otherwise the architecture tier —
        already configured, and a different family from the engineering tier
        that produces the work and its reviews.

        None when the resolution lands on the engineering model, because a
        review by the model under review is not a second opinion. This is not
        hypothetical: `premium` is dropped from FUNCTION_MODELS when unset, and
        the lookup then falls back to engineering, so the "independent" check
        would quietly have been the same model all along.
        """
        candidate = settings.model_premium or settings.model_architecture
        if not candidate or candidate == settings.model_engineering:
            return None
        return candidate

    async def chat(
        self,
        function: str,
        system_prompt: str,
        user_message: str,
        response_format: dict[str, Any] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 16384,
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | None = None,
    ) -> ModelResponse:
        # Additive (arch-20261003-119): a call may name its serving
        # directly (the tier-3 arms' TIER3_* pins, resolved from the
        # environment by the experiment's own settings class), and may
        # offer tools. Neither parameter changes an existing path: with
        # both unset the call resolves and behaves exactly as before.
        # The provider preference works the same way for a named
        # serving as for a tier - provider_order_for(function) reads
        # the per-tier syntax under the caller's function name, so an
        # arm named "tier3_arm_a" takes "tier3_arm_a:Provider".
        # tool_choice (R2) is additive the same way: unset, the
        # payload carries no tool_choice and the provider's own
        # default decides; set (arm B's final call sends "none"), it
        # declares the tools while forbidding their use.
        model = model or self.get_model(function)
        reservation = self._guard_spend(
            function, model,
            _prompt_bytes(system_prompt, user_message),
            max_tokens)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format
        if tools:
            payload["tools"] = tools
        if tool_choice:
            payload["tool_choice"] = tool_choice
        # Ask for real spend rather than inferring it. Providers that ignore
        # this simply omit usage.cost and we fall back to catalogue rates.
        payload["usage"] = {"include": True}

        # Optionally pin who serves the request. A model id alone does not
        # determine behaviour: pinning each of five providers that served one
        # tier gave 28/36, 30/36 and 33/36 on the same suite at 12x price
        # spread. Leave unset for availability; set it when a run has to be
        # reproducible or when quality has been measured.
        order = provider_order_for(function)
        if order:
            payload["provider"] = {
                "order": order,
                "allow_fallbacks": provider_fallbacks_allowed(),
            }

        # D45 (5): a call that fails after dispatch keeps its worst case. The
        # request left this process, so no actual cost will ever arrive to
        # replace the reservation — it becomes unreconciled liability with the
        # kind of failure recorded. `reconciled` is set before the release:
        # this call's own reservation, by identity, released only here.
        self._in_flight += 1
        reconciled = False
        try:
            client = await self._get_client()
            resp = await client.post("/chat/completions", json=payload)
            if resp.status_code == 400 and response_format:
                logger.warning(
                    "400 with response_format for %s — retrying without it. Body: %s",
                    model, resp.text[:300],
                )
                payload.pop("response_format", None)
                resp = await client.post("/chat/completions", json=payload)
            for attempt in range(1, _RATE_LIMIT_ATTEMPTS):
                if resp.status_code != 429:
                    break
                delay = _RATE_LIMIT_BACKOFF_S * (2 ** (attempt - 1))
                logger.warning(
                    "429 for %s (attempt %d/%d) — upstream capacity, retrying in "
                    "%.1fs. Body: %s",
                    model, attempt, _RATE_LIMIT_ATTEMPTS, delay, resp.text[:200],
                )
                await asyncio.sleep(delay)
                resp = await client.post("/chat/completions", json=payload)
            _raise_for_status(resp, "chat/completions")
            data = resp.json()

            choice = data["choices"][0]
            content = choice["message"]["content"] or ""
            tool_calls = choice["message"].get("tool_calls") or []
            finish_reason = choice.get("finish_reason")
            citations = [
                (a.get("url_citation") or {}).get("url", "")
                for a in (choice.get("message", {}).get("annotations") or [])
            ]
            citations = [c for c in citations if c]
            provider = data.get("provider")
            usage = data.get("usage", {})

            if not content.strip():
                logger.warning(
                    "Empty content from %s via %s (finish_reason=%s, "
                    "completion_tokens=%s, max_tokens=%s)",
                    model, provider, finish_reason,
                    usage.get("completion_tokens"), max_tokens,
                )
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)

            reported = (data.get("usage") or {}).get("cost")
            if reported is not None:
                cost = float(reported)
            else:
                cost = self._estimate_cost(model, prompt_tokens, completion_tokens)

            # Every attempt counts, retries included. A retry storm that costs real
            # money should look expensive rather than free.
            reconciled = True
            self._release(reservation)
            self._account(function, cost, provider,
                          prompt_tokens=prompt_tokens,
                          completion_tokens=completion_tokens,
                          reservation=reservation)
        except BaseException as exc:
            if not reconciled:
                self._fail_call(function, model, _failure_kind(exc),
                                reservation)
            raise

        return ModelResponse(
            content=content,
            model=model,
            finish_reason=finish_reason,
            provider=provider,
            citations=citations,
            tool_calls=tool_calls,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost=cost,
        )

    async def rerank(
        self, model: str, query: str, documents: list[str], top_n: int
    ) -> list[tuple[int, float]]:
        """Score documents against a query with a purpose-built rerank model.

        Returns (original_index, relevance_score) best first. Raises if the
        provider or model does not support the rerank API, which is how the
        caller learns to fall back.
        """
        client = await self._get_client()
        # D45 (5): reranking passes the same guard. Before this it posted with
        # no pre-call check at all — the one dispatch in the client that could
        # spend without asking. Rerank responses carry no completion side, so
        # the worst case is the document bytes bounded as prompt.
        reservation = self._guard_spend(
            "ranker", model,
            _prompt_bytes(query, *documents), max_tokens=0)
        self._in_flight += 1
        reconciled = False
        try:
            resp = await client.post("/rerank", json={
                "model": model,
                "query": query,
                "documents": documents,
                "top_n": top_n,
            })
            _raise_for_status(resp, "rerank")
            data = resp.json()
            usage = data.get("usage", {}) or {}
            # This cost used to reach a debug log and go no further, so reranking
            # was the one tier that never appeared in any total.
            reconciled = True
            self._release(reservation)
            self._account("ranker", float(usage.get("cost") or 0.0),
                          prompt_tokens=int(usage.get("total_tokens") or 0),
                          reservation=reservation)
        except BaseException as exc:
            if not reconciled:
                self._fail_call("ranker", model, _failure_kind(exc),
                                reservation)
            raise
        logger.debug(
            "rerank %s: %s docs, %s tokens, cost %s",
            model, len(documents), usage.get("total_tokens"), usage.get("cost"),
        )
        return [
            (int(r["index"]), float(r.get("relevance_score", 0.0)))
            for r in data.get("results", [])
        ]

    async def chat_json(
        self,
        function: str,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.3,
        max_tokens: int = 16384,
        max_retries: int = 3,
        schema: type | None = None,
    ) -> tuple[dict[str, Any], ModelResponse]:
        """Chat and parse the response as JSON. Returns (parsed_dict, response).

        When `schema` is a Pydantic model, the parsed object is validated against
        it inside the retry loop. Syntactically valid JSON of the wrong shape is
        as useless as unparseable text, and a model that produced one usually
        produces a correct one on the next attempt — so both get the same retries.
        """
        import asyncio as _aio

        last_error = None
        # What the previous attempt got wrong, fed back into the next one.
        # Re-asking an identical question is close to hoping: a model that
        # answered `infrastructure_engineer` for a role enum has no reason to
        # answer differently second time. The rejection text already names the
        # offending value and every permitted one, so the cheapest way to spend
        # a retry is to say what was wrong.
        correction = ""
        # The empty-reply attempts of THIS call, for the provider-failure
        # record if the retries exhaust. Tracked per call, not per client:
        # a call that eventually parses must not carry earlier calls'
        # failures, and the record below is one entry per exhausted call.
        # Counted, not flagged: a mixed sequence (some empty, some
        # malformed) has no single owning class, and claiming one would be
        # convention 26.
        empty_attempts = 0
        empty_provider: str | None = None
        empty_finish: str | None = None
        empty_completion: int = 0
        for attempt in range(max_retries):
            if attempt > 0:
                await _aio.sleep(min(2 ** attempt, 8))
            response = await self.chat(
                function=function,
                system_prompt=system_prompt,
                user_message=user_message + correction,
                response_format={"type": "json_object"},
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if not (response.content or "").strip():
                detail = (
                    f"model returned no text (provider={response.provider}, "
                    f"finish_reason={response.finish_reason}"
                )
                if response.finish_reason == "length":
                    detail += (
                        f", completion_tokens={response.completion_tokens} of "
                        f"max_tokens={max_tokens} — a reasoning model can spend "
                        f"its whole budget before emitting an answer; raise "
                        f"max_tokens or use a non-reasoning model for this tier"
                    )
                detail += ")"
                last_error = ValueError(detail)
                self._count_retry(self.RETRY_EMPTY_REPLY)
                # The last attempt's serving wins: with fallbacks disabled a
                # call is one serving throughout, and if that ever changes the
                # failure belongs to the serving that ended it.
                empty_attempts += 1
                empty_provider = response.provider
                empty_finish = response.finish_reason
                empty_completion = response.completion_tokens
                logger.warning(
                    "Empty reply (attempt %d/%d) for %s: %s",
                    attempt + 1, max_retries, function, detail,
                )
                continue

            try:
                parsed = self._extract_json(response.content)
                if schema is not None:
                    schema(**parsed)
                return parsed, response
            # ValidationError subclasses ValueError, so it must be caught first
            # or the clause below swallows it — which is what happened, and it
            # logged every schema violation as a parse failure.
            except ValidationError as e:
                last_error = e
                correction = _rejection_note(e)
                self._count_retry(self.RETRY_SCHEMA_REJECTION)
                self.rejections_by_function[function] = (
                    self.rejections_by_function.get(function, 0) + 1)
                if response.provider:
                    self.rejections_by_provider[response.provider] = (
                        self.rejections_by_provider.get(response.provider, 0) + 1)
                logger.warning(
                    "Response did not match %s (attempt %d/%d) for %s: %s",
                    getattr(schema, "__name__", schema), attempt + 1, max_retries,
                    function, e,
                )
            except (json.JSONDecodeError, ValueError) as e:
                last_error = e
                correction = _rejection_note(e)
                self._count_retry(self.RETRY_PARSE_FAILURE)
                logger.warning(
                    "JSON parse failed (attempt %d/%d) for %s: %s — raw: %s",
                    attempt + 1, max_retries, function, e, (response.content or "")[:300],
                )
        # The retries exhausted. An all-empty sequence means the provider
        # ended the call without producing output — a distinct failure
        # class, not a schema rejection and not a parse failure, so it
        # raises its own exception carrying the serving. Counted per call
        # above (empty_attempts), not read back from the client-wide
        # counter, so a call whose own attempts were mixed — or a client
        # with history — cannot be misread as all-empty.
        if empty_attempts >= max_retries and empty_provider is not None:
            failure = ProviderFailure(function, empty_provider, str(last_error))
            self.provider_failures.append({
                "function": function,
                "provider": empty_provider,
                "model": self.get_model(function),
                "serving": failure.serving(self.get_model(function)),
                "finish_reason": empty_finish,
                "completion_tokens": empty_completion,
                "attempts": max_retries,
            })
            raise failure from last_error
        raise last_error

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        """Find the JSON object in a model's reply.

        Dropping the first line positionally to remove a fence was wrong for
        three shapes seen in practice — a fence with the object on the same
        line (which took the object with it), a closing fence with no newline
        before it, and a sentence of preamble. Each cost a full retry, and one
        of them parsed into a valid-but-meaningless dict rather than failing.
        So: strip fences by pattern, then fall back to the outermost balanced
        object.
        """
        if not text:
            raise ValueError("Empty response content — model returned no text")
        import re

        # Reasoning models put their working in <think> blocks.
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
        # ```json ... ``` in any of its spellings, including same-line content.
        text = re.sub(r"^```[A-Za-z0-9_-]*\s*", "", text).strip()
        text = re.sub(r"```\s*$", "", text).strip()

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            span = OpenRouterClient._outermost_object(text)
            if span is None:
                raise
            parsed = json.loads(span)

        if not isinstance(parsed, dict):
            raise ValueError(
                f"Expected JSON object, got {type(parsed).__name__}: {text[:200]}")
        return parsed

    @staticmethod
    def _outermost_object(text: str) -> str | None:
        """The first balanced {...} span, ignoring braces inside strings."""
        start = text.find("{")
        if start < 0:
            return None
        depth = 0
        in_string = False
        escaped = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
        return None

    @staticmethod
    def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Estimate from the provider's own published rates.

        Rates are learned from the model catalogue at startup — AutoRnD hardcodes
        no prices, because it hardcodes no models. An unknown model estimates as
        0.0 rather than inventing a number; a fabricated cost is worse than an
        obviously absent one. Actual spend is read from the provider's usage
        accounting when it reports any, and only falls back to this.
        """
        rates = _model_pricing.get(model)
        if not rates:
            return 0.0
        prompt_rate, completion_rate = rates
        return prompt_tokens * prompt_rate + completion_tokens * completion_rate

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()


_model_status: dict[str, dict] = {}

# model id -> (prompt rate, completion rate) per token, from the provider catalogue
_model_pricing: dict[str, tuple[float, float]] = {}

# model id -> the flat per-request charge (the catalogue's per-request
# components, a search surcharge among them), from the provider
# catalogue. The worst-case bound adds it once per request the call
# can make.
_model_per_request: dict[str, float] = {}

# The catalogue's component classes, as the worst-case bound reads
# them. The tier-3 preflight applies the same classes
# (evals/tier3/runner.py: _unboundable_reason), and a test asserts
# the two agree.
_CACHE_COMPONENTS = ("input_cache_read", "input_cache_write")
_REASONING_COMPONENTS = ("internal_reasoning",)
_PER_REQUEST_COMPONENTS = ("web_search", "request")
_MODALITY_COMPONENTS = ("image", "audio", "input_audio_cache")


def _prices_what_the_guard_cannot_bound(pricing: dict[str, Any]) -> bool:
    """Does this catalogue entry carry a charge the worst-case bound
    cannot bound?

    The bound charges the prompt rate for every prompt byte and the
    completion rate for the whole output cap, so a component priced
    at or below the rate the bound already charges its side at
    cannot cost more than the bound does: the cache components
    against the prompt rate, reasoning against the completion rate
    (reasoning tokens are part of the output the cap bounds). A
    flat per-request charge does not scale with the call, so the
    bound adds it once per request. The modality components (image,
    audio) never charge on the text-only calls the harness makes.
    Anything else — a component priced above the rate its side is
    charged at, or a component the bound does not know — is a
    charge a token-only bound understates. The catalogue prices in
    strings; empty and zero mean "no charge for this component",
    and a value that does not parse is a charge this cannot read,
    which is the same answer: unboundable.
    """
    try:
        prompt = float(pricing.get("prompt"))
    except (TypeError, ValueError):
        prompt = None
    try:
        completion = float(pricing.get("completion"))
    except (TypeError, ValueError):
        completion = None
    for key, value in pricing.items():
        if key in ("prompt", "completion") or value in (None, ""):
            continue
        try:
            rate = float(value)
        except (TypeError, ValueError):
            return True
        if key in _PER_REQUEST_COMPONENTS:
            continue
        if key in _MODALITY_COMPONENTS:
            continue
        if key in _CACHE_COMPONENTS:
            if prompt is None or rate > prompt:
                return True
            continue
        if key in _REASONING_COMPONENTS:
            if completion is None or rate > completion:
                return True
            continue
        return True
    return False


async def check_models() -> dict[str, dict]:
    """Validate configured models against OpenRouter's model list."""
    global _model_status
    configured = {
        "triage": settings.model_triage,
        "engineering": settings.model_engineering,
        "architecture": settings.model_architecture,
        "escalation": settings.model_escalation,
    }
    configured["research"] = settings.model_research
    configured["search"] = settings.model_search
    for tier, model_id in (
        ("ranker", settings.model_ranker),
        ("premium", settings.model_premium),
        ("judge", settings.model_judge),
    ):
        if model_id:
            configured[tier] = model_id

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # The catalogue is usually public, and httpx rejects a bare
            # "Bearer " — so only authenticate when there is a key to send.
            # This lets tier ids be validated before a key is configured.
            headers = {}
            if settings.openrouter_api_key.strip():
                headers["Authorization"] = f"Bearer {settings.openrouter_api_key}"
            resp = await client.get(
                f"{settings.openrouter_base_url.rstrip('/')}/models",
                headers=headers,
            )
            _raise_for_status(resp, "models catalogue")
            catalogue = resp.json().get("data", [])
            available_ids = {m["id"] for m in catalogue}
            for m in catalogue:
                pricing = m.get("pricing") or {}
                # A component the catalogue does not price is unknown,
                # not free: the model stays unrated — the guard is
                # blind for it — rather than entering the table at
                # $0.00, which a bounded client would read as "a call
                # costs nothing". An explicit "0" is a published
                # price of zero and stays priced, so the two facts
                # remain distinguishable (Ruling D49's distinction,
                # applied to pricing; ARCH-20261002-116). A charge
                # the worst-case bound cannot bound — a component
                # priced above the rate its side is charged at, or
                # one the bound does not know — leaves the model
                # unrated too: a bound built from the token rates
                # alone would understate what the call can cost. The
                # components the bound does cover (the cache and
                # reasoning components at or below their side's
                # rate, the per-request charge added once per
                # request, the modality components a text-only call
                # never carries) leave it rated.
                if _prices_what_the_guard_cannot_bound(pricing):
                    continue
                prompt = pricing.get("prompt")
                completion = pricing.get("completion")
                if prompt is None or completion is None:
                    continue
                try:
                    _model_pricing[m["id"]] = (
                        float(prompt), float(completion))
                except (TypeError, ValueError):
                    continue
                # The per-request components the bound adds once
                # per request, recorded beside the token rates so
                # the guard charges them on every call.
                per_request = sum(
                    float(pricing[key])
                    for key in _PER_REQUEST_COMPONENTS
                    if pricing.get(key) not in (None, ""))
                if per_request:
                    _model_per_request[m["id"]] = per_request
    except Exception as exc:
        logger.warning("Could not fetch OpenRouter model list: %s", exc)
        _model_status = {fn: {"model": mid, "available": None} for fn, mid in configured.items()}
        return _model_status

    # The bulk catalogue lists chat models only. Other classes a provider serves
    # — rerankers, embedding models — are absent from it but perfectly valid to
    # configure, so confirm each miss individually before calling it missing.
    misses = {m for m in configured.values() if m and m not in available_ids}
    if misses:
        available_ids |= await _confirm_models(misses)

    # A variant suffix (':exacto' among them) names a serving of the
    # base model. The bulk catalogue prices the base entry; the
    # per-model endpoint confirms a variant is served but carries no
    # pricing of its own, so a confirmed variant is rated at its base
    # entry's published price — the known price, not an unknown one
    # (D49: a known price is not unknown).
    for model_id in sorted(available_ids):
        if model_id in _model_pricing or ":" not in model_id:
            continue
        base, _separator, _variant = model_id.rpartition(":")
        if base in _model_pricing:
            _model_pricing[model_id] = _model_pricing[base]
            if base in _model_per_request:
                _model_per_request[model_id] = (
                    _model_per_request[base])

    status = {}
    for fn, model_id in configured.items():
        status[fn] = {"model": model_id, "available": model_id in available_ids}
    _model_status = status
    return status


async def _confirm_models(model_ids: set[str]) -> set[str]:
    """Check ids one by one against the per-model endpoint.

    A served model returns 200 there whatever its output modality; an unknown id
    returns 404. Anything else (network fault, rate limit) is treated as
    unconfirmed rather than absent — the caller reports that as degraded, which
    is the honest answer when we could not check.
    """
    base = settings.openrouter_base_url.rstrip("/")
    headers = {}
    if settings.openrouter_api_key.strip():
        headers["Authorization"] = f"Bearer {settings.openrouter_api_key}"

    confirmed: set[str] = set()

    async def _check(client: httpx.AsyncClient, model_id: str) -> None:
        try:
            resp = await client.get(f"{base}/models/{model_id}/endpoints", headers=headers)
            if resp.status_code == 200:
                confirmed.add(model_id)
        except Exception as exc:
            logger.warning("Could not confirm model %s: %s", model_id, exc)

    async with httpx.AsyncClient(timeout=15.0) as client:
        await asyncio.gather(*[_check(client, m) for m in model_ids])
    return confirmed


def get_model_status() -> dict[str, dict]:
    return _model_status


def rebuild_function_models() -> None:
    OpenRouterClient.FUNCTION_MODELS = {
        "triage": settings.model_triage,
        "engineering": settings.model_engineering,
        "architecture": settings.model_architecture,
        "escalation": settings.model_escalation,
        "research": settings.model_research,
        "search": settings.model_search,
        **({"ranker": settings.model_ranker} if settings.model_ranker else {}),
        **({"premium": settings.model_premium} if settings.model_premium else {}),
        # Ruling D35: same optional-tier contract as FUNCTION_MODELS above —
        # unset drops `judge` so judging nodes fall back to engineering.
        **({"judge": settings.model_judge} if settings.model_judge else {}),
    }

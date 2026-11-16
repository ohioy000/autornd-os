"""Decision switches: cheap typed questions that guard expensive steps.

A switch is one yes/no question put to a decision model about evidence it is
shown, with two thresholds and a safe answer. In shadow mode the answer is
recorded and nothing acts on it. In live mode the harness acts on a confident
answer and takes the safe side on anything else. The switches themselves are
data, in switches/default.yaml; this module reads them, asks them and settles
each probability into a record. It decides nothing about what a route means:
the step a switch guards reads the record's `route` and acts.

A decision model is not a deterministic check. Its probabilities shift a
little between runs and it can be wrong, so a switch never removes work on an
unsure answer, and a harness with no decision tier behaves exactly as it did
before any switch existed.
"""

from __future__ import annotations

import contextvars
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

SWITCHES_FILE = (Path(__file__).resolve().parent.parent.parent
                 / "switches" / "default.yaml")

SHADOW, LIVE = "shadow", "live"
YES, NO = "yes", "no"
# What a record's `route` says when no switch is in force: act as the
# harness acted before the switch existed.
DEFAULT = "default"
# What a record's `choice` says beside yes and no.
UNSURE, UNAVAILABLE = "unsure", "unavailable"

# Questions in one request. They are answered side by side from one state,
# so the bound keeps a request small. A judgment, not a measurement.
MAX_QUESTIONS = 24
# Characters of any one piece of evidence sent. A switch judges whether a
# text bears on a question, which its opening shows; the bound keeps a
# request's cost a fraction of the step it guards.
MAX_EVIDENCE_CHARS = 6000


class SwitchError(ValueError):
    """A switch declared wrongly."""


@dataclass(frozen=True)
class Switch:
    name: str
    question: str
    yes: str
    no: str
    yes_at: float
    no_at: float
    safe: str
    mode: str = SHADOW
    each: str = ""
    guards: str = ""

    def settle(self, probability: float | None) -> dict[str, Any]:
        """A probability as a record: what the model chose, and the route.

        `choice` is the model's answer by the thresholds. `route` is what the
        guarded step must do: `default` while the switch is in shadow; in
        live mode the confident answer, and the safe answer for an unsure or
        missing one.
        """
        if probability is None:
            choice = UNAVAILABLE
        elif probability >= self.yes_at:
            choice = YES
        elif probability <= self.no_at:
            choice = NO
        else:
            choice = UNSURE
        if self.mode != LIVE:
            route = DEFAULT
        else:
            route = choice if choice in (YES, NO) else self.safe
        return {"switch": self.name, "probability": probability,
                "choice": choice, "mode": self.mode, "route": route}


def parse_switches(raw: Any) -> dict[str, Switch]:
    """Switches from their declared form. Raises SwitchError on a bad one:
    a switch that would silently take the wrong side must fail at load."""
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise SwitchError("switches must be a mapping of name to switch")
    out: dict[str, Switch] = {}
    for name, body in raw.items():
        if not isinstance(body, dict):
            raise SwitchError(f"switch '{name}' must be a mapping")
        # YAML reads a bare yes or no as a boolean, as a key and as a value.
        body = {{True: YES, False: NO}.get(k, k) if isinstance(k, bool) else k: v
                for k, v in body.items()}
        for key in ("question", "yes", "no", "yes_at", "no_at", "safe"):
            if key not in body:
                raise SwitchError(f"switch '{name}' is missing '{key}'")
        try:
            yes_at, no_at = float(body["yes_at"]), float(body["no_at"])
        except (TypeError, ValueError):
            raise SwitchError(
                f"switch '{name}': yes_at and no_at must be numbers") from None
        if not 0.0 <= no_at < yes_at <= 1.0:
            raise SwitchError(
                f"switch '{name}': need 0 <= no_at < yes_at <= 1 "
                f"(got no_at={no_at}, yes_at={yes_at})")
        safe = ({True: YES, False: NO}[body["safe"]]
                if isinstance(body["safe"], bool) else body["safe"])
        if safe not in (YES, NO):
            raise SwitchError(f"switch '{name}': safe must be yes or no")
        mode = str(body.get("mode", SHADOW))
        if mode not in (SHADOW, LIVE):
            raise SwitchError(f"switch '{name}': mode must be shadow or live")
        out[str(name)] = Switch(
            name=str(name), question=" ".join(str(body["question"]).split()),
            yes=" ".join(str(body["yes"]).split()),
            no=" ".join(str(body["no"]).split()),
            yes_at=yes_at, no_at=no_at, safe=safe, mode=mode,
            each=str(body.get("each") or ""),
            guards=" ".join(str(body.get("guards") or "").split()))
    return out


_loaded: dict[str, Switch] | None = None


def load_switches(path: Path | None = None) -> dict[str, Switch]:
    """The declared switches. A missing file is no switches, not an error:
    the harness runs without them."""
    global _loaded
    if path is None and _loaded is not None:
        return _loaded
    target = path or SWITCHES_FILE
    if not target.is_file():
        switches: dict[str, Switch] = {}
    else:
        switches = parse_switches(
            yaml.safe_load(target.read_text(encoding="utf-8")))
    if path is None:
        _loaded = switches
    return switches


def reset_switches() -> None:
    """Forget the loaded file. For tests, and for a deliberate re-read."""
    global _loaded
    _loaded = None


def _probability(answer: Any) -> float | None:
    """The probability a yes/no answer states, or None when it states none
    (a refusal, a missing question, a number outside 0 to 1)."""
    value = answer.get("noul") if isinstance(answer, dict) else None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if 0.0 <= value <= 1.0 else None


def _clip(evidence: Any) -> Any:
    """Evidence with each text bounded."""
    if isinstance(evidence, str):
        return evidence[:MAX_EVIDENCE_CHARS]
    if isinstance(evidence, dict):
        return {str(k): _clip(v) for k, v in evidence.items()}
    return evidence


class Switchboard:
    """Asks switches through one client and keeps every record.

    `ask` never raises and never blocks a run on the decision tier: with no
    tier configured it asks nothing and returns nothing, and a failed call
    settles every question as unavailable, which a live switch routes to its
    safe side.
    """

    def __init__(self, client: Any, switches: dict[str, Switch] | None = None):
        self.client = client
        self.switches = load_switches() if switches is None else switches
        self.records: list[dict[str, Any]] = []
        # The paid responses behind the records, for the phase record.
        self.responses: list[Any] = []

    def on(self) -> bool:
        """Is there a decision tier to ask?"""
        model = getattr(self.client, "decision_model", None)
        return bool(self.switches) and callable(model) and model() is not None

    async def ask(self, items: list[tuple[str, str, Any]]) -> list[dict[str, Any]]:
        """Put one request of questions; return a record for each.

        An item is (switch name, a label for the record, the evidence the
        question is about). An unknown switch is left out. Items past
        MAX_QUESTIONS are not asked and get no record.
        """
        if not self.on():
            return []
        asked = [(self.switches[name], label, evidence)
                 for name, label, evidence in items
                 if name in self.switches][:MAX_QUESTIONS]
        if not asked:
            return []
        state: dict[str, Any] = {}
        questions: dict[str, dict[str, Any]] = {}
        for index, (switch, _, evidence) in enumerate(asked):
            key = f"q{index}"
            state[key] = _clip(evidence)
            questions[key] = {
                "type": "noul",
                "instructions": (f'Look only at state["{key}"]. '
                                 f"{switch.question}"),
                "criteria": {"true": switch.yes, "false": switch.no},
            }
        try:
            answers, response = await self.client.decide(state, questions)
            self.responses.append(response)
        except Exception as exc:
            # Never a run's failure: every question settles as unavailable.
            # A cancellation is a BaseException and passes through.
            logger.warning("decision switches unavailable: %s: %s",
                           type(exc).__name__, str(exc)[:200])
            answers = {}
        records = []
        for index, (switch, label, _) in enumerate(asked):
            record = switch.settle(_probability(answers.get(f"q{index}")))
            record["item"] = label
            records.append(record)
        self.records.extend(records)
        return records

    async def route(self, name: str, evidence: Any, label: str = "") -> str:
        """One switch's route for one piece of evidence; `default` when the
        switch is not declared or there is no tier to ask."""
        records = await self.ask([(name, label, evidence)])
        return records[0]["route"] if records else DEFAULT

    def drain(self) -> list[dict[str, Any]]:
        """The records taken since the last drain."""
        taken, self.records = self.records, []
        return taken

    def drain_responses(self) -> list[Any]:
        taken, self.responses = self.responses, []
        return taken


# The switchboard of the run in progress. The knowledge layer's functions are
# called through several layers that tests replace with doubles of fixed
# shape, so the board travels in the context and not in every signature.
# None outside a run: every switch then routes `default`.
_current: contextvars.ContextVar[Switchboard | None] = contextvars.ContextVar(
    "autornd_switchboard", default=None)


def current_switchboard() -> Switchboard | None:
    return _current.get()


def use_switchboard(board: Switchboard | None) -> contextvars.Token:
    return _current.set(board)


def release_switchboard(token: contextvars.Token) -> None:
    _current.reset(token)


async def route_for(name: str, evidence: Any, label: str = "") -> str:
    """The route of switch `name` in the run in progress, or `default`."""
    board = current_switchboard()
    if board is None:
        return DEFAULT
    return await board.route(name, evidence, label)

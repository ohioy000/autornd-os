"""Per-profile model pins: the model a profile reads a tier from when it has its own.

A profile chooses the team, the vocabulary and the words in the prompts. It never chose a
model: a tier named one model for every profile, so a legal team and an engineering team
drafted on the same engineering-tier model. PROFILE_MODELS lets the owner give one profile
its own model, and optionally its own provider, for one tier:

    PROFILE_MODELS=legal:engineering=vendor/legal-model@vendor

This module is a pure overlay. Every reader of a tier asks here first and falls back to the
expression it used before, so with the setting empty nothing resolves differently; the tests
hold that for every tier, every accessor and every shipped profile.

Three rules, each a choice the owner can overrule:

- A pin does not inherit through a profile's ``base:``. cupline and tier4 are built on
  engineering; they must not change model because engineering gained one.
- A pin carries its own serving. ``@vendor`` is the provider that serves it. With none, the
  router decides and OPENROUTER_PROVIDER_ORDER is not applied to that tier for that profile:
  the order was written for another model, and under hard pins a provider that does not host
  this one answers 404.
- 'independent' is not pinnable. It is derived (the premium tier, else the architecture tier,
  and never the engineering model), and it is derived from the effective models, pins included.
"""

from __future__ import annotations

import functools

from autornd.config import PINNABLE_TIERS, ProfilePin, parse_profile_models, settings

__all__ = [
    "PINNABLE_TIERS", "ProfilePin", "active_pin", "active_stem", "effective_models",
    "pins_by_profile", "pins_for", "tier_model",
]


@functools.lru_cache(maxsize=16)
def _parsed(raw: str) -> dict[str, dict[str, ProfilePin]]:
    return parse_profile_models(raw)


def pins_by_profile() -> dict[str, dict[str, ProfilePin]]:
    """Every pin that is set, by profile stem: {} when the setting is empty.

    Read from the setting on each call, so a test or a runtime change reaches the next call.
    """
    return _parsed(settings.profile_models or "")


def pins_for(stem: str) -> dict[str, ProfilePin]:
    """The pins one profile has, by tier. A profile with none has {}."""
    return pins_by_profile().get(stem, {})


def active_stem() -> str:
    """The file stem of the active profile ('' for a profile built without one)."""
    from autornd.profiles import get_profile  # profiles imports config; keep the edge one-way

    return get_profile().stem


def active_pin(tier: str) -> ProfilePin | None:
    """The active profile's own pin for this tier, or None.

    With no pin set anywhere this returns before it asks which profile is active, so the
    empty setting costs one dict read per call and cannot change an answer.
    """
    pins = pins_by_profile()
    if not pins:
        return None
    return pins.get(active_stem(), {}).get(tier)


def tier_model(tier: str, default: str = "") -> str:
    """The model the active profile reads this tier from: its pin, else `default`.

    `default` is the expression the caller used before pins existed (a settings field), so
    a caller changes from ``settings.model_x`` to ``tier_model("x", settings.model_x)`` and
    nothing else.
    """
    pin = active_pin(tier)
    return pin.model if pin else default


def effective_models(base: dict[str, str]) -> dict[str, str]:
    """The tier-to-model map the active profile reads: `base` with its pins laid over it.

    `base` is the global map (OpenRouterClient.FUNCTION_MODELS). A pin on a tier the global
    map leaves unset adds that tier, which is how a profile turns an optional tier on.
    """
    pins = pins_by_profile()
    own = pins.get(active_stem(), {}) if pins else {}
    return {**base, **{tier: pin.model for tier, pin in own.items()}}

"""Provider-free scorer for the tier-2 candidate dataset.

Scores a free-text model answer against the scorer-only key
(evals/tier2/keys.json). No provider, no network, no model
involvement: every check is deterministic arithmetic, unit
conversion, operator/selection/ordering semantics, or the
verdict logic the key states. Regex presence alone never
passes an item - each numeric item compares a converted
value against the key within the stated tolerance, each
operator item checks the comparison direction, the
specification item checks the discrete selection, the
procedure items check the operation order, and the verdict
item recomputes the verdict from the stated log.

The whole-question verdict requires every required item to
pass (the command: whole-question correctness requires all
requested parts and a consistent final conclusion).

Usage:
    .venv/bin/python3 evals/tier2/scorer.py --self-test
    .venv/bin/python3 evals/tier2/scorer.py answers.json
      (answers.json maps question id -> answer text)

Exit status: 0 if the self-test passes (or every scored
answer is reported), 1 if any self-test fixture fails.
"""

from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
KEYS = json.loads((HERE / "keys.json").read_text(encoding="utf-8"))
MANIFEST = json.loads(
    (HERE / "manifest.json").read_text(encoding="utf-8"))
SCORER_VERSION = MANIFEST["scorer_version"]

# unit -> (dimension, factor to the dimension's base unit)
UNITS: dict[str, tuple[str, float]] = {
    # voltage (base V)
    "v": ("V", 1.0), "volt": ("V", 1.0), "volts": ("V", 1.0),
    "mv": ("V", 1e-3),
    # current (base A)
    "a": ("A", 1.0), "amp": ("A", 1.0), "amps": ("A", 1.0),
    "ampere": ("A", 1.0), "amperes": ("A", 1.0),
    "ma": ("A", 1e-3),
    # polar second moment of area (base m^4)
    "m^4": ("m^4", 1.0), "m4": ("m^4", 1.0),
    # stress (base Pa)
    "pa": ("Pa", 1.0), "pascal": ("Pa", 1.0),
    "pascals": ("Pa", 1.0),
    "kpa": ("Pa", 1e3), "mpa": ("Pa", 1e6), "gpa": ("Pa", 1e9),
    "n/mm^2": ("Pa", 1e6), "n/mm2": ("Pa", 1e6),
    "n/m^2": ("Pa", 1.0),
    # length (base m)
    "m": ("m", 1.0), "mm": ("m", 1e-3), "cm": ("m", 1e-2),
    "metre": ("m", 1.0), "metres": ("m", 1.0),
    "meter": ("m", 1.0), "meters": ("m", 1.0),
    # area (base m^2)
    "m^2": ("m^2", 1.0), "m2": ("m^2", 1.0),
    "mm^2": ("m^2", 1e-6), "mm2": ("m^2", 1e-6),
    "cm^2": ("m^2", 1e-4), "cm2": ("m^2", 1e-4),
    # volume (base m^3)
    "m^3": ("m^3", 1.0), "m3": ("m^3", 1.0),
    "mm^3": ("m^3", 1e-9), "mm3": ("m^3", 1e-9),
    "cm^3": ("m^3", 1e-6), "cm3": ("m^3", 1e-6),
    # mass (base kg)
    "kg": ("kg", 1.0), "kilogram": ("kg", 1.0),
    "kilograms": ("kg", 1.0),
    "g": ("kg", 1e-3), "gram": ("kg", 1e-3),
    "grams": ("kg", 1e-3),
    # pressure (base Pa; bar and kPa are the same dimension,
    # so 600 kPa and 6.00 bar compare equal)
    "bar": ("Pa", 1e5), "mbar": ("Pa", 1e2),
    "barg": ("Pa", 1e5), "bar(g)": ("Pa", 1e5),
    # angle (base rad)
    "rad": ("rad", 1.0), "radian": ("rad", 1.0),
    "radians": ("rad", 1.0), "mrad": ("rad", 1e-3),
    "deg": ("rad", math.pi / 180), "degree": ("rad", math.pi / 180),
    "degrees": ("rad", math.pi / 180),
    # time (base s)
    "s": ("s", 1.0), "sec": ("s", 1.0), "secs": ("s", 1.0),
    "second": ("s", 1.0), "seconds": ("s", 1.0),
    "min": ("s", 60.0), "mins": ("s", 60.0),
    "minute": ("s", 60.0), "minutes": ("s", 60.0),
    # dimensionless
    "%": ("%", 1.0), "percent": ("%", 1.0), "pct": ("%", 1.0),
}

_SUPERSCRIPT = {"⁰": "0", "¹": "1", "²": "2", "³": "3",
                "⁴": "4", "⁵": "5", "⁶": "6", "⁷": "7",
                "⁸": "8", "⁹": "9", "⁻": "-"}


def _normalize(text: str) -> str:
    """LaTeX, unicode signs and superscripts to plain text,
    so number/unit extraction sees '6.14e-7 m^4',
    '8000 mV', '150 N/mm^2', '0.10 bar', '5 min'."""
    text = re.sub(r"\\mathrm\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\text\{([^}]*)\}", r"\1", text)
    text = text.replace("\\%", "%")
    # 6.13592\times10^{-7}, 6.14 x 10^-7 and 6.14*10^7
    # -> 6.14e-7
    text = re.sub(r"(\d)\s*(?:\\times|×|x|\*)\s*10\s*\^\s*"
                    r"\{?\s*(-?\d+)\s*\}?", r"\1e\2", text)
    text = text.replace("\\times", " * ")
    text = text.replace("\\,", " ").replace("\\;", " ")
    text = text.replace("\\ ", " ")
    text = text.replace("$", "")
    text = text.replace("\\leq", " <= ").replace("\\le", " <= ")
    text = text.replace("\\geq", " >= ").replace("\\ge", " >= ")
    text = text.replace("\\pm", " +/- ")
    for uni, asc in _SUPERSCRIPT.items():
        text = text.replace(uni, asc)
    for uni, asc in {"×": "*", "≤": "<=", "≥": ">=",
                     "±": "+/-", "µ": "u", "°": " deg"}.items():
        text = text.replace(uni, asc)
    return text


_NUMBER = re.compile(r"[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?")
_UNIT_AFTER = re.compile(
    r"\s*([A-Za-z%]+(?:\^\d+)?(?:/[A-Za-z%+^\d]+)?)")


def extract_quantities(text: str) -> list[tuple[float, str]]:
    """Every (value, unit) pair the text states, in reading
    order. A number with no unit behind it carries ''."""
    normalized = _normalize(text)
    found: list[tuple[float, str]] = []
    for m in _NUMBER.finditer(normalized):
        value = float(m.group(0))
        rest = normalized[m.end():m.end() + 14]
        unit = ""
        um = _UNIT_AFTER.match(rest)
        if um and um.group(1):
            unit = um.group(1)
        found.append((value, unit))
    return found


def _dimension(unit: str) -> str | None:
    entry = UNITS.get(unit.strip().lower().replace(" ", ""))
    return entry[0] if entry else None


def _to_base(value: float, unit: str) -> tuple[str, float] | None:
    """Convert (value, unit) to its dimension's base unit."""
    entry = UNITS.get(unit.strip().lower().replace(" ", ""))
    if not entry:
        return None
    return entry[0], value * entry[1]


def parse_tolerance(spec: str) -> tuple[str, float, str] | None:
    """Parse a key's tolerance_or_variants into
    (kind, magnitude, unit): ('abs', 0.01, 'V'),
    ('rel', 0.002, '') or None for semantic items."""
    plain = _normalize(spec)
    m = re.search(r"numerical tolerance\s*\+/-\s*"
                  r"(\d+(?:\.\d+)?)\s*([A-Za-z%]+)", plain)
    if m:
        return "abs", float(m.group(1)), m.group(2)
    m = re.search(r"absolute tolerance\s*\+/-\s*"
                  r"(\d+(?:\.\d+)?)\s*([A-Za-z%]+)", plain)
    if m:
        return "abs", float(m.group(1)), m.group(2)
    m = re.search(r"relative tolerance\s*(\d+(?:\.\d+)?)\s*%",
                  plain)
    if m:
        return "rel", float(m.group(1)) / 100.0, ""
    return None


def _within(value: float, key_value: float,
            tolerance: tuple[str, float, str]) -> bool:
    kind, magnitude, _unit = tolerance
    # One part in 10^9 of slack absorbs binary
    # floating-point representation error at the boundary
    # (0.236 - 0.2355 is 0.0005000000000000004 in
    # binary). It is far below every stated tolerance,
    # and the key itself lists the rounded boundary value
    # (0.236 kg) as accepted.
    slack = magnitude * 1e-9
    if kind == "abs":
        return abs(value - key_value) <= magnitude + slack
    return (abs(value - key_value)
            <= magnitude * abs(key_value) + slack)


def _key_quantities(item: dict, dimension: str | None = None,
                    index: int = 0) -> tuple[float, str]:
    """The key's own quantity for a numeric item: the value
    string's quantities, optionally filtered by dimension."""
    quantities = extract_quantities(item["value"])
    if dimension is not None:
        quantities = [q for q in quantities
                      if _dimension(q[1]) == dimension]
    return quantities[index]


def _numeric_item(item: dict, answer: str,
                  dimension: str | None = None,
                  index: int = 0) -> dict:
    """Score one numeric required item: the answer must state
    a quantity in the key's dimension whose converted value
    is within the stated tolerance of the key's value."""
    tolerance = parse_tolerance(item["tolerance_or_variants"])
    key_value, key_unit = _key_quantities(item, dimension, index)
    key_dim, key_base = _to_base(key_value, key_unit)
    assert tolerance is not None, (
        f"numeric item '{item['item']}' has no parseable "
        f"tolerance: {item['tolerance_or_variants']}")
    tol_kind, tol_magnitude, tol_unit = tolerance
    if tol_unit:
        # The tolerance carries a unit (abs tolerances do):
        # express it in the key dimension's base unit.
        tol_dim, tol_base = _to_base(tol_magnitude, tol_unit)
        assert tol_dim == key_dim, (
            f"tolerance unit {tol_unit} does not match key "
            f"unit {key_unit} on item '{item['item']}'")
        tolerance = (tol_kind, tol_base, "")
    for value, unit in extract_quantities(answer):
        converted = _to_base(value, unit)
        if converted and converted[0] == key_dim:
            if _within(converted[1], key_base, tolerance):
                return _pass(item, f"{value} {unit} = "
                                   f"{converted[1]:.6g} "
                                   f"{key_dim} within "
                                   f"{tol_kind} tolerance of "
                                   f"key {key_base:.6g} {key_dim}")
    return _fail(item, f"no stated {key_dim} quantity within "
                       f"{tol_kind} tolerance "
                       f"({tolerance[1]:.6g}) of key "
                       f"{key_base:.6g} {key_dim}")


def _pass(item: dict, detail: str) -> dict:
    return {"item": item["item"], "pass": True, "detail": detail}


def _fail(item: dict, detail: str) -> dict:
    return {"item": item["item"], "pass": False, "detail": detail}


def _item_by_name(record: dict, name: str) -> dict:
    return next(i for i in record["required_items"]
                if i["item"] == name)


# ── Q1: the unloaded divider ──────────────────────────────────

def _score_q1(answer: str, record: dict) -> list[dict]:
    return [
        _numeric_item(_item_by_name(record, "Output voltage"),
                      answer, dimension="V"),
        _numeric_item(_item_by_name(record, "Divider current"),
                      answer, dimension="A"),
    ]


# ── Q2: the two definitions, with operators and basis ─────────

_STRICT_LESS = ("less than", "below", "under", "<")
_NONSTRICT_LESS = ("at or below", "or less", "no more than",
                   "<=", "at most")
_STRICT_MORE = ("more than", "above", "greater than", "over", ">")
_NONSTRICT_MORE = ("at or above", "or more", "at least", ">=")


def _score_q2(answer: str, record: dict) -> list[dict]:
    plain = _normalize(answer).lower()
    quantities = extract_quantities(plain)

    def threshold_check(gas: str, operator_words: tuple,
                        nonstrict_words: tuple,
                        threshold: float, name: str) -> dict:
        item = _item_by_name(record, name)
        if gas not in plain:
            return _fail(item, f"the answer does not name the "
                               f"{gas} atmosphere")
        # The threshold the answer states for this gas: a
        # percent quantity, or a unitless value below 1 (a
        # volume fraction), near the gas's name.
        gas_at = plain.find(gas)
        near = plain[gas_at:gas_at + 120]
        stated = None
        for value, unit in quantities:
            dim = _dimension(unit)
            if dim == "%":
                candidate = value
            elif unit == "" and value < 1:
                candidate = value * 100.0   # volume fraction
            else:
                continue
            if abs(candidate - threshold) < 1e-9:
                stated = candidate
                break
        if stated is None:
            return _fail(item, f"no {threshold}% threshold stated "
                               f"for the {gas} atmosphere "
                               f"(strict inequality and threshold "
                               f"must be exact)")
        # The operator must be the strict one the definition
        # states; a non-strict operator misstates it.
        if any(w in near for w in nonstrict_words):
            return _fail(item, f"a non-strict operator "
                               f"({nonstrict_words[0]}) misstates "
                               f"the definition, which is strict "
                               f"'{'less' if 'less' in operator_words[0] else 'more'} "
                               f"than'")
        if not any(w in near for w in operator_words):
            return _fail(item, f"no strict comparison operator "
                               f"stated for the {threshold}% "
                               f"threshold")
        if "mass" in near:
            return _fail(item, "the basis is stated as by mass; "
                               "the definition is by volume")
        if "volume" not in near and "v/v" not in near:
            return _fail(item, "the concentration basis "
                               "(by volume) is not stated")
        return _pass(item, f"{operator_words[0]} {threshold}% "
                           f"by volume, as the definition states")

    return [
        threshold_check("deficient", _STRICT_LESS,
                        _NONSTRICT_LESS, 19.5,
                        "Oxygen-deficient atmosphere"),
        threshold_check("enriched", _STRICT_MORE,
                        _NONSTRICT_MORE, 23.5,
                        "Oxygen-enriched atmosphere"),
    ]


# ── Q3: torsion of a solid shaft ──────────────────────────────

def _score_q3(answer: str, record: dict) -> list[dict]:
    return [
        _numeric_item(_item_by_name(record,
                    "Polar second moment of area"),
                    answer, dimension="m^4"),
        _numeric_item(_item_by_name(record,
                    "Maximum shear-stress magnitude"),
                    answer, dimension="Pa"),
        _numeric_item(_item_by_name(record,
                    "End-to-end twist magnitude"),
                    answer, dimension="rad"),
    ]


# ── Q4: the tie-strip specification ───────────────────────────

def _selected_thickness(answer: str) -> float | None:
    """The thickness the answer selects, in metres, from a
    selection context: a line naming 'thickness', or a line
    that selects. Rejection contexts (the next thinner strip
    and its failure) do not count as selections."""
    selection: float | None = None
    for line in _normalize(answer).splitlines():
        low = line.lower()
        rejects = any(w in low for w in
                      ("fail", "exceed", "reject", "next thinner",
                       "gives", "too thin"))
        if "thickness" in low and not rejects:
            at = low.find("thickness")
            for value, unit in extract_quantities(line[at:]):
                converted = _to_base(value, unit)
                if converted and converted[0] == "m":
                    selection = converted[1]
                    break
        elif (any(w in low for w in
                  ("select", "chose", "choose"))
              and not rejects):
            for value, unit in extract_quantities(line):
                converted = _to_base(value, unit)
                if converted and converted[0] == "m":
                    selection = converted[1]
                    break
    return selection


def _score_q4(answer: str, record: dict) -> list[dict]:
    items: list[dict] = []

    # Selected dimensions: all three, and the thickness is
    # exactly the available 3.00 mm size.
    dims = _item_by_name(record, "Selected dimensions")
    key_width = _to_base(
        *_key_quantities(dims, "m", 0))[1]
    key_thickness = _to_base(
        *_key_quantities(dims, "m", 1))[1]
    key_length = _to_base(
        *_key_quantities(dims, "m", 2))[1]
    stated = {"width": None, "thickness": None,
                "length": None}
    quantities = [(v, u) for v, u in extract_quantities(answer)
                  if _to_base(v, u) and _to_base(v, u)[0] == "m"]
    for value, unit in quantities:
        base = _to_base(value, unit)[1]
        for key, label in ((key_width, "width"),
                           (key_thickness, "thickness"),
                           (key_length, "length")):
            if stated.get(label) is None and abs(base - key) <= 1e-6:
                stated[label] = base
    selection = _selected_thickness(answer)
    ok = (all(v is not None for v in stated.values())
          and selection is not None
          and abs(selection - key_thickness) <= 1e-9)
    items.append(_pass(dims, f"selected 20.0 x 3.00 x 500 mm; "
                             f"thickness selection is exactly "
                             f"3.00 mm") if ok else _fail(
        dims, f"selection {selection!r} m and stated dimensions "
              f"{stated} do not match the required 20.0 x "
              f"{key_thickness * 1e3:.2f} x {key_length * 1e3:.0f} "
              f"mm with the 3.00 mm thickness selected exactly"))

    items.append(_numeric_item(
        _item_by_name(record, "Selected gross cross-sectional "
                              "area"), answer, dimension="m^2"))

    # Selected-strip stress: the value, and equality with the
    # allowable is identified as acceptable.
    stress = _item_by_name(record,
                           "Selected-strip stress and strength "
                           "verdict")
    stress_result = _numeric_item(stress, answer, dimension="Pa")
    low = _normalize(answer).lower()
    if stress_result["pass"] and not any(
            w in low for w in ("pass", "acceptable", "ok")):
        stress_result = _fail(stress, "the stress value is stated "
                                      "but equality with the "
                                      "allowable is not identified "
                                      "as acceptable")
    items.append(stress_result)

    # Next thinner strip: the 2.00 mm thickness, its 150 MPa
    # stress, and the failure verdict.
    thinner = _item_by_name(record,
                            "Next thinner available strip stress "
                            "and verdict")
    key_t = _to_base(
        *_key_quantities(thinner, "m", 0))[1]
    key_sigma = _to_base(
        *_key_quantities(thinner, "Pa", 0))[1]
    has_thickness = any(
        _to_base(v, u) and _to_base(v, u)[0] == "m"
        and abs(_to_base(v, u)[1] - key_t) <= 1e-9
        for v, u in extract_quantities(answer))
    sigma_result = _numeric_item(thinner, answer, dimension="Pa")
    low = _normalize(answer).lower()
    has_fail = any(w in low for w in ("fail", "exceed", "reject"))
    if has_thickness and sigma_result["pass"] and has_fail:
        items.append(_pass(thinner, f"the next thinner strip is "
                                    f"identified at "
                                    f"{key_t * 1e3:.2f} mm with "
                                    f"{key_sigma / 1e6:.1f} MPa "
                                    f"and its failure is stated"))
    else:
        items.append(_fail(
            thinner, f"thickness stated: {has_thickness}; stress "
                     f"within tolerance: {sigma_result['pass']}; "
                     f"failure verdict stated: {has_fail} - all "
                     f"three are required"))

    items.append(_numeric_item(
        _item_by_name(record, "Selected-strip volume"),
        answer, dimension="m^3"))
    items.append(_numeric_item(
        _item_by_name(record, "Selected-strip mass"),
        answer, dimension="kg"))

    # Organization: three sections covering dimensions, the
    # strength check, and volume and mass.
    org = _item_by_name(record,
                        "Answer organization and consistency")
    lines = [l.strip() for l in answer.splitlines() if l.strip()]
    sections = [l for l in lines
                if re.match(r"^(#{1,6}\s+\S|\d+\.\s+[A-Z])", l)]
    low = _normalize(answer).lower()
    themes = (any(w in low for w in ("dimension", "width",
                                     "thickness")),
              any(w in low for w in ("strength", "stress",
                                     "pass")),
              ("volume" in low and "mass" in low))
    if len(sections) >= 3 and all(themes):
        items.append(_pass(org, f"{len(sections)} sections "
                                f"covering dimensions, the "
                                f"strength check, and volume "
                                f"and mass"))
    else:
        items.append(_fail(org, f"{len(sections)} section headings "
                                f"(three required); themes "
                                f"present: dimensions "
                                f"{themes[0]}, strength "
                                f"{themes[1]}, volume and mass "
                                f"{themes[2]}"))

    return items


# ── Q5: the hydrostatic leak-test procedure ───────────────────

def _numbered_steps(text: str) -> list[str]:
    steps = []
    for line in _normalize(text).splitlines():
        m = re.match(r"\s*(\d+)\.\s+(.*)", line)
        if m:
            steps.append(m.group(2).strip())
    return steps


def _locate(answer: str, phrases: tuple[str, ...]):
    """The reading-order position of the first phrase: a
    (step, offset) pair when the answer is numbered, else a
    (0, character-offset) pair. None when absent. A phrase
    starting with 're:' is a regular expression, matched at
    its start position - which keeps '0 bar' from matching
    inside '6.00 bar'."""
    steps = _numbered_steps(answer)
    if len(steps) >= 2:
        for i, step in enumerate(steps):
            low = step.lower()
            for phrase in phrases:
                if phrase.startswith("re:"):
                    m = re.search(phrase[3:], low)
                    if m:
                        return (i, m.start())
                elif phrase in low:
                    return (i, low.find(phrase))
        return None
    low = _normalize(answer).lower()
    for phrase in phrases:
        if phrase.startswith("re:"):
            m = re.search(phrase[3:], low)
            if m:
                return (0, m.start())
        elif phrase in low:
            return (0, low.find(phrase))
    return None


def _ordered(answer: str, pairs: tuple[tuple[str, ...],
                                        tuple[str, ...]]) -> bool:
    """Every (before-phrases, after-phrases) pair holds in the
    answer's reading order."""
    for before, after in pairs:
        loc_before, loc_after = (_locate(answer, before),
                                 _locate(answer, after))
        if loc_before is None or loc_after is None:
            return False
        if loc_before >= loc_after:
            return False
    return True


def _score_q5(answer: str, record: dict) -> list[dict]:
    items: list[dict] = []
    low = _normalize(answer).lower()
    quantities = extract_quantities(answer)

    def has_pressure(target_bar: float) -> bool:
        for value, unit in quantities:
            converted = _to_base(value, unit)
            if (converted and converted[0] == "Pa"
                    and abs(converted[1] - target_bar * 1e5)
                    <= 1e2):
                return True
        return False

    # 1. fill and vent
    item = _item_by_name(record, "First operation: fill and vent")
    if "bubble-free" in low and "vent" in low:
        items.append(_pass(item, "filling with the high-point "
                                 "vent open until bubble-free "
                                 "water exits"))
    else:
        items.append(_fail(item, "the fill-and-vent operation "
                                 "(open high-point vent, "
                                 "bubble-free discharge) is not "
                                 "stated"))

    # 2. close the vent before pressurizing
    item = _item_by_name(record, "Second operation: close vent")
    if ("close" in low and "vent" in low
            and _ordered(answer,
                         ((("close",), ("pressuriz",)),))):
        items.append(_pass(item, "the vent is closed before "
                                 "pressurization"))
    else:
        items.append(_fail(item, "vent closure before "
                                 "pressurization is not stated"))

    # 3. the specified 6.00 bar test pressure
    item = _item_by_name(record, "Third operation: establish "
                                 "test pressure")
    if has_pressure(6.00):
        items.append(_pass(item, "the specified 6.00 bar gauge "
                                 "test pressure is stated "
                                 "(600 kPa accepted)"))
    else:
        items.append(_fail(item, "no 6.00 bar (600 kPa) test "
                                 "pressure stated; the 10.0 bar "
                                 "component rating is not the "
                                 "test pressure"))

    # 4. isolate the pump, then start the timer
    item = _item_by_name(record, "Fourth operation: isolate "
                                 "before timing")
    if ("isolat" in low
            and _ordered(answer,
                         ((("isolat",), ("timer", "timing")),))):
        items.append(_pass(item, "the hand pump is isolated "
                                 "before the hold timer starts"))
    else:
        items.append(_fail(item, "isolation before timing is not "
                                 "stated"))

    # 5. the 300 s hold with no added water
    item = _item_by_name(record, "Fifth operation: isolated hold")
    hold_300 = any(
        (_to_base(v, u) and _to_base(v, u)[0] == "s"
         and abs(_to_base(v, u)[1] - 300.0) <= 1e-9)
        for v, u in quantities)
    if (hold_300 and any(w in low for w in
                         ("without adding water", "no water",
                          "do not add", "no pumping"))):
        items.append(_pass(item, "the 300 s (5 min) hold with no "
                                 "added water is stated"))
    else:
        items.append(_fail(item, "the 300 s hold and the "
                                 "no-addition rule are not both "
                                 "stated"))

    # 6. the conjunctive acceptance criteria
    item = _item_by_name(record, "Acceptance and failure criteria")
    criteria = [(w in low) for w in
                ("0.20", "leak")]
    drop_limit = any(
        (_to_base(v, u) and _to_base(v, u)[0] == "Pa"
         and abs(_to_base(v, u)[1] - 0.20 * 1e5) <= 1e2)
        for v, u in quantities)
    nonpositive = any(w in low for w in ("no more than",
                                         "at most", "<=",
                                         "no greater than"))
    if (drop_limit and nonpositive and criteria[1]
            and "no visible" in low):
        items.append(_pass(item, "both conjunctive criteria "
                                 "stated: drop at most 0.20 bar "
                                 "and no visible leakage"))
    else:
        items.append(_fail(item, f"0.20 bar limit stated: "
                                 f"{drop_limit}; inclusive "
                                 f"operator stated: {nonpositive}; "
                                 f"leakage condition stated: "
                                 f"{criteria[1] and 'no visible' in low}"))

    # 7. the logged drop
    item = _item_by_name(record, "Logged pressure drop")
    items.append(_numeric_item(item, answer, dimension="Pa"))

    # 8. the verdict, recomputed from the question's log
    item = _item_by_name(record, "Logged test verdict")
    start = [v for v, u in quantities
             if _to_base(v, u) and _to_base(v, u)[0] == "Pa"
             and abs(_to_base(v, u)[1] - 6.00 * 1e5) <= 1e2]
    end = [v for v, u in quantities
           if _to_base(v, u) and _to_base(v, u)[0] == "Pa"
           and abs(_to_base(v, u)[1] - 5.90 * 1e5) <= 1e2]
    no_leakage = "no visible" in low and "leak" in low
    # The compact logged-drop arithmetic
    # 'start-end=drop unit' states all three pressures
    # in one unit; the end pressure carries no unit of
    # its own, so read it from the expression.
    compact = re.search(
        r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*=\s*"
        r"(\d+(?:\.\d+)?)\s*(bar|mbar|kpa|pa)\b", low)
    if compact and not end:
        factor = UNITS[compact.group(4)][1]
        start.append(float(compact.group(1)) * factor)
        end.append(float(compact.group(2)) * factor)
    # The answer's stated verdict is its last verdict
    # word: a conditional 'otherwise fail' inside the
    # criteria does not override the conclusion. Leading
    # word boundaries only, so 'unacceptable' is not
    # matched again through its 'acceptable' stem.
    stated = None
    for stem, verdict in ((r"\bunacceptable", "FAIL"),
                            (r"\bacceptable", "PASS"),
                            (r"\bfail", "FAIL"),
                            (r"\bpass", "PASS")):
        matches = list(re.finditer(stem, low))
        if matches:
            at = matches[-1].start()
            if stated is None or at >= stated[0]:
                stated = (at, verdict)
    stated_verdict = stated[1] if stated else None
    # The question's log: 6.00 -> 5.90 bar, no visible
    # leakage. The drop is 0.10 bar, within the 0.20 bar
    # limit, so the verdict for this log is PASS. The
    # answer links its verdict to the log either by
    # stating the raw hold pressures or by stating the
    # drop they produce.
    drop_stated = any(
        (_to_base(v, u) and _to_base(v, u)[0] == "Pa"
         and abs(_to_base(v, u)[1] - 0.10 * 1e5) <= 1e2)
        for v, u in quantities)
    recomputed = no_leakage and (
        (bool(start) and bool(end)) or drop_stated)
    if (recomputed and stated_verdict == "PASS"):
        items.append(_pass(item, "the logged drop 6.00 - "
                                 "5.90 = 0.10 bar <= "
                                 "0.20 bar with no visible "
                                 "leakage: PASS, and the "
                                 "answer states PASS"))
    else:
        items.append(_fail(item, f"log values stated: "
                                 f"{bool(start and end)}; "
                                 f"no leakage: {no_leakage}; "
                                 f"verdict the log requires: "
                                 f"{'PASS' if recomputed else 'FAIL'}; "
                                 f"answer's stated verdict: "
                                 f"{stated_verdict}"))

    # 9. assess, depressurize, confirm zero, then disconnect
    item = _item_by_name(record,
                         "Final operations: assess, depressurize, "
                         "confirm zero, disconnect")
    final_order = (
        (("assess", "pass", "fail"), ("release", "depressuriz",
                                        "bleed")),
        (("release", "depressuriz", "bleed"),
         (r"re:(?<![\d.])0\s*bar", "zero")),
        ((r"re:(?<![\d.])0\s*bar", "zero"), ("disconnect",)),
    )
    has_final = ("release" in low or "depressuriz" in low
                 or "bleed" in low) and "disconnect" in low
    if has_final and _ordered(answer, final_order):
        items.append(_pass(item, "the result is assessed, then "
                                 "the release valve depressurizes, "
                                 "0 bar gauge is confirmed, and "
                                 "only then the manifold is "
                                 "disconnected"))
    else:
        items.append(_fail(item, "the final sequence (assess, "
                                 "release, confirm 0 bar, "
                                 "disconnect) is not stated in "
                                 "order"))

    return items


SCORERS = {"Q1": _score_q1, "Q2": _score_q2, "Q3": _score_q3,
           "Q4": _score_q4, "Q5": _score_q5}


def score(question_id: str, answer: str,
          keys: list[dict] | None = None) -> dict:
    """Score one free-text answer against its key. Returns the
    per-item results, the item count, and the whole-question
    verdict: every required item must pass."""
    record = next(k for k in (keys or KEYS)
                  if k["id"] == question_id)
    items = SCORERS[question_id](answer, record)
    return {
        "question": question_id,
        "scorer_version": SCORER_VERSION,
        "items": items,
        "passed_items": sum(1 for i in items if i["pass"]),
        "total_items": len(items),
        "verdict": "PASS" if all(i["pass"] for i in items)
                   else "FAIL",
    }


def score_all(answers: dict[str, str]) -> list[dict]:
    return [score(qid, text) for qid, text in answers.items()]


# ── self-test: the fixtures that prove the scorer ─────────────
#
# Every fixture is a stated case, not a sample of model
# output: the key's own model answer, every equivalent
# notation the key lists, every common wrong answer, and the
# tolerance boundaries themselves.

def _fixture(
        cases: list[tuple[str, str, str, dict]],
) -> tuple[int, int]:
    """Run (label, question_id, answer, expectation) cases.
    Expectation maps item names to expected pass/fail, plus
    an optional 'verdict' key. Returns (failures, fixtures
    run)."""
    failures = 0
    for label, qid, answer, expectation in cases:
        result = score(qid, answer)
        expected_verdict = expectation.get("verdict")
        problems = []
        for item in result["items"]:
            if item["item"] in expectation:
                if item["pass"] != expectation[item["item"]]:
                    problems.append(
                        f"item '{item['item']}': "
                        f"{'pass' if item['pass'] else 'FAIL'}, "
                        f"expected "
                        f"{'pass' if expectation[item['item']] else 'FAIL'}")
        if expected_verdict is not None and result["verdict"] != expected_verdict:
            problems.append(f"verdict {result['verdict']}, "
                            f"expected {expected_verdict}")
        if problems:
            failures += 1
            print(f"  FAIL  {label}")
            for problem in problems:
                print(f"        {problem}")
        else:
            print(f"  ok    {label}")
    return failures, len(cases)


def self_test() -> int:
    print(f"Scorer self-test, scorer version "
          f"{SCORER_VERSION}, dataset version "
          f"{MANIFEST['dataset_version']}")
    print(f"Candidate holds {MANIFEST['questions']} questions "
          f"(the command expects "
          f"{MANIFEST['command_expected_questions']}); the set "
          f"is NOT frozen - see manifest.json")
    failures = 0
    ran = 0

    # The key's own worked answers must hold every item.
    print("\nThe key's own model answers hold every item:")
    for record in KEYS:
        more, count = _fixture([
            (f"{record['id']} model answer", record["id"],
             record["model_answer"],
             {i["item"]: True for i in record["required_items"]}
             | {"verdict": "PASS"}),
        ])
        failures += more
        ran += count

    # Equivalent notations the keys list must pass.
    print("\nEquivalent notations the keys list:")
    more, count = _fixture([
        ("Q1 output in volts", "Q1", "Output: 8 V",
         {"Output voltage": True}),
        ("Q1 output in tenths", "Q1", "Output: 8.0 V",
         {"Output voltage": True}),
        ("Q1 output in millivolts", "Q1", "Output: 8000 mV",
         {"Output voltage": True}),
        ("Q1 current in amperes", "Q1", "Current: 0.002 A",
         {"Divider current": True}),
        ("Q3 J in plain scientific notation", "Q3",
         "J = 6.14e-7 m^4", {"Polar second moment of area": True}),
        ("Q3 stress in pascals", "Q3",
         "tau = 2.03718e7 Pa",
         {"Maximum shear-stress magnitude": True}),
        ("Q3 stress in N/mm^2", "Q3",
         "tau = 20.37 N/mm^2",
         {"Maximum shear-stress magnitude": True}),
        ("Q3 twist in milliradians", "Q3",
         "theta = 10.1859 mrad",
         {"End-to-end twist magnitude": True}),
        ("Q4 area in square metres", "Q4",
         "A = 6.00e-5 m^2",
         {"Selected gross cross-sectional area": True}),
        ("Q4 stress in N/mm^2", "Q4",
         "sigma = 100 N/mm^2: passes",
         {"Selected-strip stress and strength verdict": True}),
        ("Q4 thinner-strip stress in pascals", "Q4",
         "The 2.00 mm strip gives 1.50e8 Pa: fails",
         {"Next thinner available strip stress and verdict": True}),
        ("Q4 volume in mm^3", "Q4",
         "V = 30000 mm^3",
         {"Selected-strip volume": True}),
        ("Q4 volume in cm^3", "Q4",
         "V = 30.0 cm^3",
         {"Selected-strip volume": True}),
        ("Q4 mass in grams", "Q4",
         "m = 235.5 g",
         {"Selected-strip mass": True}),
        ("Q4 mass rounded", "Q4",
         "m = 0.236 kg",
         {"Selected-strip mass": True}),
        ("Q4 dimensions in metres", "Q4",
         "Selected dimensions: width 0.020 m; "
         "thickness 0.003 m; length 0.5 m",
         {"Selected dimensions": True}),
        ("Q5 test pressure in kPa", "Q5",
         "Pressurize to 600 kPa gauge",
         {"Third operation: establish test pressure": True}),
        ("Q5 hold in minutes", "Q5",
         "Hold for 5 min without adding water",
         {"Fifth operation: isolated hold": True}),
        ("Q5 drop in kPa", "Q5",
         "Logged drop: 10 kPa",
         {"Logged pressure drop": True}),
        ("Q5 fraction notation for the thresholds", "Q2",
         "Oxygen deficient: volume fraction below 0.195. "
         "Oxygen enriched: volume fraction above 0.235.",
         {"Oxygen-deficient atmosphere": True,
          "Oxygen-enriched atmosphere": True}),
        ("Q2 below/above phrasing", "Q2",
         "Oxygen deficient atmosphere: below 19.5% oxygen "
         "by volume. Oxygen enriched atmosphere: above 23.5% "
         "oxygen by volume.",
         {"Oxygen-deficient atmosphere": True,
          "Oxygen-enriched atmosphere": True}),
        ("Q2 v/v notation", "Q2",
         "Oxygen deficient: <19.5% v/v. Oxygen enriched: "
         ">23.5% v/v.",
         {"Oxygen-deficient atmosphere": True,
          "Oxygen-enriched atmosphere": True}),
    ])
    failures += more
    ran += count

    # Tolerance boundaries: at the boundary passes, just
    # past it fails.
    print("\nTolerance boundaries (at the boundary passes, "
          "just past fails):")
    more, count = _fixture([
        ("Q1 voltage at +0.01 V", "Q1", "Output: 8.01 V",
         {"Output voltage": True}),
        ("Q1 voltage past +0.01 V", "Q1", "Output: 8.02 V",
         {"Output voltage": False}),
        ("Q1 voltage at -0.01 V", "Q1", "Output: 7.991 V",
         {"Output voltage": True}),
        ("Q1 voltage past -0.01 V", "Q1", "Output: 7.97 V",
         {"Output voltage": False}),
        ("Q1 current at +0.01 mA", "Q1", "Current: 2.01 mA",
         {"Divider current": True}),
        ("Q1 current past +0.01 mA", "Q1", "Current: 2.02 mA",
         {"Divider current": False}),
        ("Q3 J just inside +0.2% relative", "Q3",
         "J = 6.1481e-7 m^4",
         {"Polar second moment of area": True}),
        ("Q3 J past +0.2% relative", "Q3",
         "J = 6.1488e-7 m^4",
         {"Polar second moment of area": False}),
        ("Q3 twist just inside -0.2% relative", "Q3",
         "theta = 0.0101656 rad",
         {"End-to-end twist magnitude": True}),
        ("Q3 twist past -0.2% relative", "Q3",
         "theta = 0.01016 rad",
         {"End-to-end twist magnitude": False}),
        ("Q4 stress at the allowable (equality permitted)",
         "Q4", "sigma = 100 MPa: passes",
         {"Selected-strip stress and strength verdict": True}),
        ("Q4 stress past the 0.1% relative tolerance", "Q4",
         "sigma = 100.2 MPa: passes",
         {"Selected-strip stress and strength verdict": False}),
        ("Q4 mass just inside +0.0005 kg", "Q4",
         "m = 0.2359 kg",
         {"Selected-strip mass": True}),
        ("Q4 mass past +0.0005 kg", "Q4", "m = 0.2361 kg",
         {"Selected-strip mass": False}),
        ("Q5 criterion accepts the boundary "
         "('no more than 0.20 bar')", "Q5",
         "1. Fill with water through the open high-point "
         "vent until bubble-free water exits.\n"
         "2. Close the vent; pressurize to 6.00 bar "
         "gauge.\n"
         "3. Isolate the hand pump, then start the timer.\n"
         "4. Hold for 300 s without adding water; observe "
         "for leakage.\n"
         "5. A test passes only if the pressure drop is no "
         "more than 0.20 bar and there is no visible water "
         "leakage during the hold. Logged drop: "
         "6.00 - 5.90 = 0.10 bar, with no visible "
         "leakage: PASS.\n"
         "6. Open the release valve, confirm 0 bar gauge, "
         "then disconnect.",
         {"Acceptance and failure criteria": True,
          "verdict": "PASS"}),
        ("Q5 criterion misstates the boundary "
         "('below 0.20 bar' excludes the limit)", "Q5",
         "1. Fill with water through the open high-point "
         "vent until bubble-free water exits.\n"
         "2. Close the vent; pressurize to 6.00 bar "
         "gauge.\n"
         "3. Isolate the hand pump, then start the timer.\n"
         "4. Hold for 300 s without adding water; observe "
         "for leakage.\n"
         "5. A test passes only if the pressure drop is "
         "below 0.20 bar and there is no visible water "
         "leakage during the hold. Logged drop: "
         "6.00 - 5.90 = 0.10 bar, with no visible "
         "leakage: PASS.\n"
         "6. Open the release valve, confirm 0 bar gauge, "
         "then disconnect.",
         {"Acceptance and failure criteria": False,
          "verdict": "FAIL"}),
    ])
    failures += more
    ran += count

    # Every common wrong answer the key lists must be caught.
    print("\nEvery common wrong answer the keys list is caught:")
    more, count = _fixture([
        ("Q1 wrong: 4 V output", "Q1", "Output: 4 V",
         {"Output voltage": False, "verdict": "FAIL"}),
        ("Q1 wrong: 6 mA current", "Q1", "Current: 6 mA",
         {"Divider current": False, "verdict": "FAIL"}),
        ("Q2 wrong: at or below 19.5%", "Q2",
         "Oxygen deficient: at or below 19.5% oxygen by volume. "
         "Oxygen enriched: more than 23.5% oxygen by volume.",
         {"Oxygen-deficient atmosphere": False, "verdict": "FAIL"}),
        ("Q2 wrong: at or above 23.5%", "Q2",
         "Oxygen deficient: less than 19.5% oxygen by volume. "
         "Oxygen enriched: at or above 23.5% oxygen by volume.",
         {"Oxygen-enriched atmosphere": False, "verdict": "FAIL"}),
        ("Q2 wrong: by mass", "Q2",
         "Oxygen deficient: less than 19.5% oxygen by mass. "
         "Oxygen enriched: more than 23.5% oxygen by mass.",
         {"Oxygen-deficient atmosphere": False,
          "Oxygen-enriched atmosphere": False, "verdict": "FAIL"}),
        ("Q3 wrong: J = pi d^4/64", "Q3",
         "J = 3.06796e-7 m^4",
         {"Polar second moment of area": False, "verdict": "FAIL"}),
        ("Q3 wrong: 40.7 MPa", "Q3",
         "tau_max = 40.7 MPa",
         {"Maximum shear-stress magnitude": False,
          "verdict": "FAIL"}),
        ("Q3 wrong: 0.0102 degrees", "Q3",
         "theta = 0.0102 degrees",
         {"End-to-end twist magnitude": False, "verdict": "FAIL"}),
        ("Q4 wrong: select 4 mm", "Q4",
         "### Selected dimensions\n"
         "Width 20.0 mm; thickness 4.00 mm; length 500 mm.\n"
         "### Strength check\n"
         "Area 80.0 mm^2; stress 6000/80.0 = 75 MPa: passes.\n"
         "### Volume and mass\n"
         "V = 80.0 x 500 = 40000 mm^3 = 4.00e-5 m^3.\n"
         "m = 7850V = 0.314 kg.",
         {"Selected dimensions": False, "verdict": "FAIL"}),
        ("Q4 wrong: select 2 mm", "Q4",
         "### Selected dimensions\n"
         "Width 20.0 mm; thickness 2.00 mm; length 500 mm.\n"
         "### Strength check\n"
         "Area 40.0 mm^2; stress 6000/40.0 = 150 MPa: passes.\n"
         "### Volume and mass\n"
         "V = 40.0 x 500 = 20000 mm^3 = 2.00e-5 m^3.\n"
         "m = 7850V = 0.157 kg.",
         {"Selected dimensions": False,
          "Selected-strip stress and strength verdict": False,
          "verdict": "FAIL"}),
        ("Q4 wrong: 235.5 kg", "Q4",
         "### Selected dimensions\n"
         "Width 20.0 mm; thickness 3.00 mm; length 500 mm.\n"
         "### Strength check\n"
         "Area 60.0 mm^2; stress 100 MPa: passes.\n"
         "### Volume and mass\n"
         "V = 3.00e-5 m^3. m = 235.5 kg.",
         {"Selected-strip mass": False, "verdict": "FAIL"}),
        ("Q5 wrong: test at 10.0 bar", "Q5",
         "1. Fill with water through the open high-point vent "
         "until bubble-free water exits.\n"
         "2. Close the vent; pressurize to 10.0 bar gauge.\n"
         "3. Isolate the hand pump, then start the timer.\n"
         "4. Hold for 300 s without adding water.\n"
         "5. Drop 0.10 bar <= 0.20 bar, no visible leakage: "
         "PASS.\n"
         "6. Open the release valve, confirm 0 bar gauge, then "
         "disconnect.",
         {"Third operation: establish test pressure": False,
          "verdict": "FAIL"}),
        ("Q5 wrong: start timing while raising pressure", "Q5",
         "1. Fill with water through the open high-point vent "
         "until bubble-free water exits.\n"
         "2. Close the vent; pressurize to 6.00 bar gauge, "
         "starting the timer while raising pressure.\n"
         "3. Isolate the hand pump.\n"
         "4. Hold for 300 s without adding water.\n"
         "5. Drop 0.10 bar <= 0.20 bar, no visible leakage: "
         "PASS.\n"
         "6. Open the release valve, confirm 0 bar gauge, then "
         "disconnect.",
         {"Fourth operation: isolate before timing": False,
          "verdict": "FAIL"}),
        ("Q5 wrong: pump during the hold", "Q5",
         "1. Fill with water through the open high-point vent "
         "until bubble-free water exits.\n"
         "2. Close the vent; pressurize to 6.00 bar gauge.\n"
         "3. Isolate the hand pump, then start the timer.\n"
         "4. Hold for 300 s, pumping water to maintain "
         "6.00 bar.\n"
         "5. Drop 0.00 bar <= 0.20 bar, no visible leakage: "
         "PASS.\n"
         "6. Open the release valve, confirm 0 bar gauge, then "
         "disconnect.",
         {"Fifth operation: isolated hold": False,
          "verdict": "FAIL"}),
        ("Q5 wrong: fail because the final pressure is below "
         "6.00 bar", "Q5",
         "1. Fill with water through the open high-point vent "
         "until bubble-free water exits.\n"
         "2. Close the vent; pressurize to 6.00 bar gauge.\n"
         "3. Isolate the hand pump, then start the timer.\n"
         "4. Hold for 300 s without adding water.\n"
         "5. Final pressure 5.90 bar is below 6.00 bar: FAIL.\n"
         "6. Open the release valve, confirm 0 bar gauge, then "
         "disconnect.",
         {"Logged test verdict": False, "verdict": "FAIL"}),
        ("Q5 wrong: disconnect before confirming zero", "Q5",
         "1. Fill with water through the open high-point vent "
         "until bubble-free water exits.\n"
         "2. Close the vent; pressurize to 6.00 bar gauge.\n"
         "3. Isolate the hand pump, then start the timer.\n"
         "4. Hold for 300 s without adding water.\n"
         "5. Drop 0.10 bar <= 0.20 bar, no visible leakage: "
         "PASS.\n"
         "6. Disconnect the manifold, then open the release "
         "valve and confirm 0 bar gauge.",
         {"Final operations: assess, depressurize, confirm "
          "zero, disconnect": False, "verdict": "FAIL"}),
    ])
    failures += more
    ran += count

    # The discrete selection, in both directions.
    print("\nDiscrete selection (the smallest passing thickness):")
    more, count = _fixture([
        ("Q4 selects exactly 3.00 mm", "Q4",
         "Selected dimensions: width 20.0 mm, thickness "
         "3.00 mm, length 500 mm.",
         {"Selected dimensions": True}),
        ("Q4 rounded notation for the selection", "Q4",
         "Selected dimensions: width 20 mm, thickness 3 mm, "
         "length 500 mm.",
         {"Selected dimensions": True}),
        ("Q4 selection stated in metres", "Q4",
         "Selected dimensions: width 0.020 m, thickness "
         "0.003 m, length 0.500 m.",
         {"Selected dimensions": True}),
        ("Q4 does not select 2 mm", "Q4",
         "Selected dimensions: width 20.0 mm, thickness "
         "2.00 mm, length 500 mm.",
         {"Selected dimensions": False}),
        ("Q4 does not select 4 mm", "Q4",
         "Selected dimensions: width 20.0 mm, thickness "
         "4.00 mm, length 500 mm.",
         {"Selected dimensions": False}),
    ])
    failures += more
    ran += count

    print()
    if failures:
        print(f"SCORER SELF-TEST FAILED: {failures} fixture(s)")
        return 1
    print(f"SCORER SELF-TEST PASSED: all {ran} fixtures hold "
          "(model answers, equivalent notations, tolerance "
          "boundaries, wrong answers, discrete selections)")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    if not argv or argv[0] == "--self-test":
        return self_test()
    answers = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    for result in score_all(answers):
        print(f"{result['question']}: {result['verdict']} "
              f"({result['passed_items']}/{result['total_items']} "
              f"items, key version {result['scorer_version']})")
        for item in result["items"]:
            mark = "ok  " if item["pass"] else "FAIL"
            print(f"  {mark} {item['item']}: {item['detail']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

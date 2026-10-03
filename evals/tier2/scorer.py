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
    "mm^4": ("m^4", 1e-12), "mm4": ("m^4", 1e-12),
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
    "ms": ("s", 1e-3), "millisecond": ("s", 1e-3),
    "milliseconds": ("s", 1e-3),
    "min": ("s", 60.0), "mins": ("s", 60.0),
    "minute": ("s", 60.0), "minutes": ("s", 60.0),
    # dimensionless
    "%": ("%", 1.0), "percent": ("%", 1.0), "pct": ("%", 1.0),
    "percentage": ("%", 1.0),
    "percentagepoints": ("%", 1.0),
    # power (base W)
    "w": ("W", 1.0), "watt": ("W", 1.0), "watts": ("W", 1.0),
    "kw": ("W", 1e3), "mw": ("W", 1e-3),
    # energy (base J)
    "j": ("J", 1.0), "joule": ("J", 1.0), "joules": ("J", 1.0),
    "kj": ("J", 1e3), "mj": ("J", 1e-3),
    # force (base N)
    "n": ("N", 1.0), "newton": ("N", 1.0),
    "newtons": ("N", 1.0), "kn": ("N", 1e3),
    # torque and moment (base N m; N mm is an
    # energy unit in this dataset: 720 N mm =
    # 0.720 J, the key's accepted notation)
    "nm": ("N m", 1.0), "n m": ("N m", 1.0),
    "newtonmetres": ("N m", 1.0),
    "newtonmetre": ("N m", 1.0),
    "nmm": ("J", 1e-3),
    "knm": ("N m", 1e3),
    # stiffness (base N/mm)
    "n/mm": ("N/mm", 1.0), "n/m": ("N/mm", 1e-3),
    "kn/mm": ("N/mm", 1e3), "kn/m": ("N/mm", 1.0),
    # thermal resistance (base K/W; the prose
    # spellings the keys accept)
    "k/w": ("K/W", 1.0),
    "kelvinperwatt": ("K/W", 1.0),
    "degreescelsiusperwatt": ("K/W", 1.0),
    "degreecelsiusperwatt": ("K/W", 1.0),
    # electrical resistance (base ohm)
    "ohm": ("ohm", 1.0), "ohms": ("ohm", 1.0),
    # flow (base L/min)
    "l/min": ("L/min", 1.0), "l/s": ("L/min", 60.0),
    # concentration (base mg/L)
    "mg/l": ("mg/L", 1.0), "ug/l": ("mg/L", 1e-3),
    "mgn/l": ("mg/L", 1.0),
    # micrometre and microamp, the keys'
    # accepted micro notations
    "um": ("m", 1e-6), "ua": ("A", 1e-6),
    # rotational speed (base rpm)
    "rpm": ("rpm", 1.0), "rev/min": ("rpm", 1.0),
    "revolutionsperminute": ("rpm", 1.0),
    "rev/s": ("rpm", 60.0),
    "revolutionspersecond": ("rpm", 60.0),
    # linear speed (base m/s)
    "m/s": ("m/s", 1.0),
    # temperature (base deg C; kelvin carries an
    # offset, not a factor: 308.15 K = 35.0 deg C)
    "degc": ("deg C", 1.0), "celsius": ("deg C", 1.0),
    "degreescelsius": ("deg C", 1.0),
    "degreecelsius": ("deg C", 1.0),
    "k": ("deg C", 1.0, -273.15),
    "kelvin": ("deg C", 1.0, -273.15),
    "kelvins": ("deg C", 1.0, -273.15),
    # mass (lb)
    "lb": ("lb", 1.0), "lbs": ("lb", 1.0),
    "pound": ("lb", 1.0), "pounds": ("lb", 1.0),
    # clock and calendar units
    "h": ("h", 1.0), "hr": ("h", 1.0), "hrs": ("h", 1.0),
    "hour": ("h", 1.0), "hours": ("h", 1.0),
    "month": ("month", 1.0), "months": ("month", 1.0),
    "d": ("day", 1.0), "day": ("day", 1.0),
    "days": ("day", 1.0),
}

# number words the keys' accepted notations use
# ('eight hours', 'fourteen hours', 'thirty days')
_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19, "twenty": 20,
    "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80,
    "ninety": 90, "hundred": 100, "thousand": 1000,
}

_SUPERSCRIPT = {"⁰": "0", "¹": "1", "²": "2", "³": "3",
                "⁴": "4", "⁵": "5", "⁶": "6", "⁷": "7",
                "⁸": "8", "⁹": "9", "⁻": "-"}


def _normalize(text: str) -> str:
    """LaTeX, unicode signs and superscripts to plain text,
    so number/unit extraction sees '6.14e-7 m^4',
    '8000 mV', '150 N/mm^2', '0.10 bar', '5 min',
    '26.7 deg C', '9.00 N m', '330 ohm'."""
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
    # ^{\circ} and \circ read as the degree sign;
    # \Omega and the ohm sign read as 'ohm'
    text = re.sub(r"\^\{\\circ\}", "°", text)
    text = text.replace("\\circ", "°")
    # the hyphenated torque spelling the keys
    # accept reads as two tokens
    text = text.replace("newton-metres",
                        "newton metres")
    text = text.replace("newton-metre",
                        "newton metre")
    text = text.replace("\\Omega", " ohm ")
    text = text.replace("\\omega", " ohm ")
    text = text.replace("\\mu", " u ")
    for uni, asc in _SUPERSCRIPT.items():
        text = text.replace(uni, asc)
    # Two-character units before their single-character
    # prefixes: '°C' must become 'deg C', not 'degC'
    for uni, asc in {"°C": " deg C", "×": "*", "≤": "<=",
                     "≥": ">=", "±": "+/-", "µ": "u",
                     "μ": "u", "·": " ", "Ω": " ohm ",
                     "ω": " ohm ", "°": " deg",
                     "−": "-", "⊕": " xor "}.items():
        text = text.replace(uni, asc)
    return text


_NUMBER = re.compile(r"[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?")
# A unit is one token, or tokens joined by a slash,
# a space or a middle dot (K/W, N m, N·m, L/min,
# m/s, N/mm); a compound capture that names no known
# unit falls back to its longest known prefix, so
# '8 h/day' still reads as hours and '9.00 N m and'
# still reads as newton-metres.
_UNIT_AFTER = re.compile(
    r"\s*([A-Za-z%]+(?:\^\d+)?(?:[\s/·][A-Za-z%]+(?:\^\d+)?)*)")


def _word_numbers(text: str) -> str:
    """Number words to digits, on word boundaries only,
    so the keys' 'eight hours' and 'thirty days'
    notations read as quantities. Applied to the
    extraction copy alone: phrase checks must keep
    reading 'return to zero' as words."""
    def repl(m):
        return str(_NUMBER_WORDS[m.group(0)])
    return re.sub(r"\b(" + "|".join(_NUMBER_WORDS)
                  + r")\b", repl, text)


def _known_unit(capture: str) -> str:
    """The known unit a capture names: the capture
    itself, or its longest known token prefix ('deg c
    inclusive' -> 'deg c', 'n/mm spring' -> 'n/mm')."""
    if _dimension(capture) is not None:
        return capture
    tokens = re.split(r"[\s·]+", capture)
    while len(tokens) > 1:
        tokens.pop()
        unit = " ".join(tokens)
        if _dimension(unit) is not None:
            return unit
    # a single token: try its slash prefixes
    # ('h/day' -> 'h')
    parts = tokens[0].split("/")
    while len(parts) > 1:
        parts.pop()
        if _dimension("/".join(parts)) is not None:
            return "/".join(parts)
    return ""


def _unit_behind(rest: str) -> str:
    """The unit behind a number. A unit may follow the
    number directly ('8 h'), close a range or an
    'and'-joined list ('2.90-3.10 V', '3.04 and
    1.96 V' - the unit belongs to every number in
    the list), or trail prose the capture absorbed
    ('8 h/day', '9.00 N m and'), in which case the
    longest known prefix of the capture is the unit."""
    m = _UNIT_AFTER.match(rest)
    if m and m.group(1):
        unit = _known_unit(m.group(1))
        if unit:
            return unit
    # Past a range dash or an 'and', to the unit the
    # list's last number carries.
    tail = rest
    for _ in range(3):
        m = re.match(r"\s*(?:[–—-]|and)\s*"
                     r"[+-]?\d+(?:\.\d+)?"
                     r"(?:[eE][+-]?\d+)?", tail)
        if not m:
            break
        tail = tail[m.end():]
        um = _UNIT_AFTER.match(tail)
        if um and um.group(1):
            unit = _known_unit(um.group(1))
            if unit:
                return unit
            break
    return ""


def extract_quantities(text: str) -> list[tuple[float, str]]:
    """Every (value, unit) pair the text states, in reading
    order. A number with no unit behind it carries ''."""
    normalized = _word_numbers(_normalize(text))
    found: list[tuple[float, str]] = []
    for m in _NUMBER.finditer(normalized):
        value = float(m.group(0))
        # The window is wide enough for the keys'
        # longest prose unit ('degrees Celsius per
        # watt' is 24 characters); _known_unit drops
        # any trailing prose the capture absorbs.
        rest = normalized[m.end():m.end() + 32]
        found.append((value, _unit_behind(rest)))
    return found


def _dimension(unit: str) -> str | None:
    entry = UNITS.get(unit.strip().lower().replace(" ", ""))
    return entry[0] if entry else None


def _to_base(value: float, unit: str) -> tuple[str, float] | None:
    """Convert (value, unit) to its dimension's base unit.
    A kelvin entry carries an offset, not a factor:
    308.15 K converts to 35.0 deg C."""
    entry = UNITS.get(unit.strip().lower().replace(" ", ""))
    if not entry:
        return None
    dimension, factor = entry[0], entry[1]
    offset = entry[2] if len(entry) > 2 else 0.0
    return dimension, value * factor + offset


def parse_tolerance(spec: str) -> tuple[str, float, str] | None:
    """Parse a key's tolerance_or_variants into
    (kind, magnitude, unit): ('abs', 0.01, 'V'),
    ('rel', 0.002, '') or None for semantic items.
    The unit may be compound (K/W, N m, L/min),
    and the Q6-Q25 keys state bare tolerances
    ('tolerance +/-0.001 K/W') and prefixed ones
    ('error tolerance +/-0.0005 mm') alike."""
    plain = _normalize(spec)
    # A tolerance's unit may be compound (L/min,
    # N m), so the capture allows slash, space and
    # middle-dot separators.
    unit = r"([A-Za-z%]+(?:[\s/·][A-Za-z%]+)*)"
    m = re.search(r"numerical tolerance\s*\+/-\s*"
                  r"(\d+(?:\.\d+)?)\s*" + unit, plain)
    if m:
        return "abs", float(m.group(1)), m.group(2)
    m = re.search(r"absolute tolerance\s*\+/-\s*"
                  r"(\d+(?:\.\d+)?)\s*" + unit, plain)
    if m:
        return "abs", float(m.group(1)), m.group(2)
    m = re.search(r"relative tolerance\s*(\d+(?:\.\d+)?)\s*%",
                  plain)
    if m:
        return "rel", float(m.group(1)) / 100.0, ""
    m = re.search(r"tolerance\s*\+/-\s*(\d+(?:\.\d+)?)"
                  r"\s*" + unit, plain)
    if m:
        return "abs", float(m.group(1)), m.group(2)
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
                  index: int = 0,
                  tolerance: tuple[str, float, str]
                  | None = None) -> dict:
    """Score one numeric required item: the answer must state
    a quantity in the key's dimension whose converted value
    is within the stated tolerance of the key's value.

    The tolerance is parsed from the item's own spec unless
    the caller passes one: an item that pairs an exact
    selection with a tolerated figure (Q9's stiffness and
    extension, Q19's resistance and current) carries one
    tolerance for both, so the exact part is scored with an
    explicit exact tolerance."""
    if tolerance is None:
        tolerance = parse_tolerance(
            item["tolerance_or_variants"])
    key_value, key_unit = _key_quantities(item, dimension, index)
    key_dim, key_base = _to_base(key_value, key_unit)
    if tolerance is None:
        # The item states 'Exact ... required': the
        # key's own value must be stated exactly, to
        # the last printed digit.
        tolerance = ("rel", 1e-12, "")
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


def _has_quantity(quantities: list[tuple[float, str]],
                  dimension: str, target: float,
                  tolerance: float = 1e-9) -> bool:
    """Whether the stated quantities include the target
    value in the dimension's base unit."""
    return any(
        _to_base(v, u) and _to_base(v, u)[0] == dimension
        and abs(_to_base(v, u)[1] - target)
        <= tolerance
        for v, u in quantities)


def _organization(record: dict, answer: str,
                  sections: int,
                  themes: tuple[tuple[str, ...],
                                ...]) -> dict:
    """The explicit-answer-format item: the answer is
    organized into the requested number of sections,
    each covering one stated theme."""
    item = next(i for i in record["required_items"]
                if i["item"] == "Organization")
    lines = [l.strip() for l in answer.splitlines()
             if l.strip()]
    heads = [l for l in lines
             if re.match(r"^(#{1,6}\s+\S|\d+\.\s+[A-Z])",
                         l)]
    low = _normalize(answer).lower()
    present = [any(w in low for w in theme)
               for theme in themes]
    if len(heads) >= sections and all(present):
        return _pass(item, f"{len(heads)} section "
                           f"headings covering the "
                           f"requested themes")
    return _fail(item, f"{len(heads)} section headings "
                       f"({sections} required); themes "
                       f"present: {present}")


# ── Q6: the pump alarm ──────────────────────────────────

def _score_q6(answer: str, record: dict) -> list[dict]:
    items: list[dict] = []
    low = _normalize(answer).lower()

    # 1. the alarm function: exclusive OR of A and B,
    #    named or written as its sum of products
    item = _item_by_name(record, "Alarm function")
    xor = ("xor" in low
           or "exclusive or" in low
           or "exclusive-or" in low
           or bool(re.search(
               r"A\s*\\overline\{B\}\s*\+\s*"
               r"\\overline\{A\}\s*B", answer))
           or bool(re.search(r"a'\s*b\s*\+\s*a\s*b'",
                             low)))
    if xor:
        items.append(_pass(item, "the alarm is driven by "
                                 "A XOR B (exclusive OR, "
                                 "or the A'B + AB' sum of "
                                 "products)"))
    else:
        items.append(_fail(item, "the alarm function is "
                                 "not the exclusive OR of "
                                 "A and B"))

    # 2. the ordered outputs for 00, 01, 10, 11
    item = _item_by_name(record, "Ordered outputs")
    values = [v for v, _u in extract_quantities(answer)]
    target = [0.0, 1.0, 1.0, 0.0]
    found = any(values[i:i + 4] == target
                for i in range(max(len(values) - 3, 0)))
    if found:
        items.append(_pass(item, "the ordered outputs for "
                                 "00, 01, 10, 11 are "
                                 "0, 1, 1, 0"))
    else:
        items.append(_fail(item, "the ordered output "
                                 "sequence 0, 1, 1, 0 is "
                                 f"not stated (quantities "
                                 f"found: {values})"))
    return items


# ── Q7: the Table G-16 exposure durations ───────────────

def _score_q7(answer: str, record: dict) -> list[dict]:
    items: list[dict] = []
    for level in ("90", "95", "100"):
        item = _item_by_name(
            record,
            rf"Duration at ${level}\,\mathrm{{dBA}}$")
        items.append(_numeric_item(item, answer,
                                   dimension="h"))
    return items


# ── Q8: the two-layer wall ──────────────────────────────

def _score_q8(answer: str, record: dict) -> list[dict]:
    items: list[dict] = []
    low = _normalize(answer).lower()

    items.append(_numeric_item(
        _item_by_name(record, "Layer A resistance"),
        answer, dimension="K/W"))
    items.append(_numeric_item(
        _item_by_name(record, "Layer B resistance"),
        answer, dimension="K/W"))

    # the heat-transfer rate: magnitude and direction
    item = _item_by_name(record, "Heat-transfer rate")
    rate = _numeric_item(item, answer, dimension="W")
    direction = ("hot to cold" in low
                 or ("from hot" in low
                     and "cold" in low))
    if rate["pass"] and direction:
        items.append(_pass(item, f"{rate['detail']}; the "
                                 f"direction hot to cold "
                                 f"is stated"))
    else:
        items.append(_fail(item, f"rate within tolerance: "
                                 f"{rate['pass']}; "
                                 f"direction hot to cold "
                                 f"stated: {direction} - "
                                 f"both are required"))

    items.append(_numeric_item(
        _item_by_name(record, "Interface temperature"),
        answer, dimension="deg C"))
    return items


# ── Q9: the tension-spring selection ────────────────────

def _score_q9(answer: str, record: dict) -> list[dict]:
    items: list[dict] = []
    low = _normalize(answer).lower()

    # 1. the selected stiffness: the lowest passing
    #    available value, exactly
    items.append(_numeric_item(
        _item_by_name(record, "Selected stiffness"),
        answer, dimension="N/mm"))

    # 2. the selected extension, with its pass verdict
    item = _item_by_name(record,
                         "Selected extension and verdict")
    ext = _numeric_item(item, answer, dimension="m")
    if ext["pass"] and "pass" in low:
        items.append(_pass(item, f"{ext['detail']}; the "
                                 f"limit-equality pass is "
                                 f"stated"))
    else:
        items.append(_fail(item, f"extension within "
                                 f"tolerance: {ext['pass']}; "
                                 f"pass verdict stated: "
                                 f"{'pass' in low} - both "
                                 f"are required"))

    # 3. the next lower stiffness: 8.00 N/mm extends
    #    15.0 mm and fails
    item = _item_by_name(record, "Next lower stiffness check")
    stiff = _numeric_item(item, answer,
                          dimension="N/mm",
                          tolerance=("rel", 1e-12, ""))
    ext8 = _numeric_item(item, answer, dimension="m")
    if (stiff["pass"] and ext8["pass"]
            and "fail" in low):
        items.append(_pass(item, f"{stiff['detail']}; "
                                 f"{ext8['detail']}; the "
                                 f"failure verdict is "
                                 f"stated"))
    else:
        items.append(_fail(item, f"8.00 N/mm within "
                                 f"tolerance: "
                                 f"{stiff['pass']}; "
                                 f"15.0 mm within "
                                 f"tolerance: {ext8['pass']}; "
                                 f"failure verdict stated: "
                                 f"{'fail' in low} - all "
                                 f"three are required"))

    # 4. the stored elastic energy
    items.append(_numeric_item(
        _item_by_name(record, "Stored elastic energy"),
        answer, dimension="J"))

    # 5. organization
    items.append(_organization(record, answer, 3, (
        ("select", "spring"),
        ("extension",),
        ("energy", "stored"),
    )))
    return items


# ── Q10: the cure-check sequence ────────────────────────

def _score_q10(answer: str, record: dict) -> list[dict]:
    items: list[dict] = []
    low = _normalize(answer).lower()
    quantities = extract_quantities(answer)

    def has_temp(target: float) -> bool:
        return _has_quantity(quantities, "deg C", target)

    # 1. setpoint, qualifying band, then the timer start
    item = _item_by_name(record,
                         "Setpoint and timer-start order")
    order = _ordered(answer, (
        (("set",), ("timer", "timing", "start")),
    ))
    if (order and has_temp(120.0)
            and has_temp(118.0) and has_temp(122.0)
            and "coupon" in low):
        items.append(_pass(item, "the oven is set to "
                                 "120 deg C, the coupon "
                                 "probe must enter the "
                                 "118-122 deg C band, and "
                                 "only then does the timer "
                                 "start"))
    else:
        items.append(_fail(item, f"setpoint before timer "
                                 f"start: {order}; 120 deg C "
                                 f"stated: {has_temp(120.0)}; "
                                 f"118-122 deg C band stated: "
                                 f"{has_temp(118.0) and has_temp(122.0)}; "
                                 f"coupon probe named: "
                                 f"{'coupon' in low} - all "
                                 f"are required"))

    # 2. the hold criterion
    item = _item_by_name(record, "Hold criterion")
    hold = _has_quantity(quantities, "s", 600.0)
    if (hold and "excursion" in low
            and "without restart" in low
            and ("inclusive" in low or "<=" in low)):
        items.append(_pass(item, "the 600 s hold inside "
                                 "the inclusive band, with "
                                 "any excursion failing "
                                 "without restart, is "
                                 "stated"))
    else:
        items.append(_fail(item, f"600 s stated: {hold}; "
                                 f"excursion fails without "
                                 f"restart stated: "
                                 f"{'excursion' in low and 'without restart' in low}; "
                                 f"inclusive limits stated: "
                                 f"{'inclusive' in low or '<=' in low} - all "
                                 f"are required"))

    # 3. the logged verdict
    item = _item_by_name(record, "Logged verdict")
    if ("pass" in low and has_temp(119.0)
            and has_temp(121.0) and hold):
        items.append(_pass(item, "the logged 119-121 deg C "
                                 "range throughout the "
                                 "600 s hold satisfies "
                                 "every criterion: PASS"))
    else:
        items.append(_fail(item, f"pass verdict stated: "
                                 f"{'pass' in low}; 119-121 "
                                 f"deg C range stated: "
                                 f"{has_temp(119.0) and has_temp(121.0)}; "
                                 f"600 s duration stated: "
                                 f"{hold} - all are "
                                 f"required"))

    # 4. the shutdown and removal order
    item = _item_by_name(record,
                         "Shutdown and removal order")
    order = _ordered(answer, (
        (("switch off", "off"), ("cool",)),
        (("cool",), ("remove",)),
    ))
    if order and has_temp(40.0):
        items.append(_pass(item, "heating is switched off, "
                                 "the coupon cools inside "
                                 "to at most 40 deg C at "
                                 "the coupon probe, and "
                                 "only then is it removed"))
    else:
        items.append(_fail(item, f"switch-off then cool "
                                 f"then remove order: "
                                 f"{order}; 40 deg C "
                                 f"removal threshold "
                                 f"stated: {has_temp(40.0)} "
                                 f"- both are required"))
    return items


# ── Q11: the gear pair ──────────────────────────────────

def _score_q11(answer: str, record: dict) -> list[dict]:
    items: list[dict] = []
    low = _normalize(answer).lower()

    items.append(_numeric_item(
        _item_by_name(record, "Output speed"),
        answer, dimension="rpm"))

    item = _item_by_name(record, "Output direction")
    ccw = any(w in low for w in ("counterclockwise",
                                 "anticlockwise", "ccw"))
    if ccw:
        items.append(_pass(item, "counterclockwise "
                                 "(anticlockwise, CCW)"))
    else:
        items.append(_fail(item, "the counterclockwise "
                                 "output direction is not "
                                 "stated"))

    items.append(_numeric_item(
        _item_by_name(record, "Output torque magnitude"),
        answer, dimension="N m"))
    return items


# ── Q12: the drinking-water MCLs ────────────────────────

def _score_q12(answer: str, record: dict) -> list[dict]:
    items: list[dict] = []
    low = _normalize(answer).lower()

    items.append(_numeric_item(
        _item_by_name(record, "Arsenic MCL"),
        answer, dimension="mg/L"))
    items.append(_numeric_item(
        _item_by_name(record, "Fluoride MCL"),
        answer, dimension="mg/L"))

    # nitrate: the concentration and its nitrogen basis
    item = _item_by_name(record,
                         "Nitrate MCL and reporting basis")
    nitrate = _numeric_item(item, answer,
                            dimension="mg/L")
    basis = ("as nitrogen" in low
             or "nitrate-n" in low
             or "mg n/l" in low
             or "as n " in low)
    if nitrate["pass"] and basis:
        items.append(_pass(item, f"{nitrate['detail']}; "
                                 f"the nitrogen reporting "
                                 f"basis is stated"))
    else:
        items.append(_fail(item, f"nitrate within "
                                 f"tolerance: "
                                 f"{nitrate['pass']}; "
                                 f"nitrogen basis stated: "
                                 f"{basis} - both are "
                                 f"required"))
    return items


# ── Q13: the RC charging transient ──────────────────────

def _score_q13(answer: str, record: dict) -> list[dict]:
    items: list[dict] = []

    items.append(_numeric_item(
        _item_by_name(record, "Time constant"),
        answer, dimension="s"))
    items.append(_numeric_item(
        _item_by_name(record, "Capacitor voltage"),
        answer, dimension="V"))
    # the resistor current: the key allows the positive
    # sign to be implicit, so the numeric comparison
    # alone scores it (a negative value is out of
    # tolerance by construction)
    items.append(_numeric_item(
        _item_by_name(record, "Resistor current"),
        answer, dimension="A"))
    return items


# ── Q14: the heater selection ───────────────────────────

def _score_q14(answer: str, record: dict) -> list[dict]:
    items: list[dict] = []
    low = _normalize(answer).lower()

    items.append(_numeric_item(
        _item_by_name(record, "Required heat"),
        answer, dimension="J"))

    # the selected heater: the smallest passing power,
    # exactly
    items.append(_numeric_item(
        _item_by_name(record, "Selected heater"),
        answer, dimension="W"))

    # the selected heating time, with its pass verdict
    item = _item_by_name(record,
                         "Selected heating time and verdict")
    time = _numeric_item(item, answer, dimension="s")
    if time["pass"] and "pass" in low:
        items.append(_pass(item, f"{time['detail']}; the "
                                 f"equality pass is "
                                 f"stated"))
    else:
        items.append(_fail(item, f"time within tolerance: "
                                 f"{time['pass']}; pass "
                                 f"verdict stated: "
                                 f"{'pass' in low} - both "
                                 f"are required"))

    # the next smaller heater: 750 W takes 160 s and fails
    item = _item_by_name(record, "Next smaller heater check")
    heater = _numeric_item(item, answer, dimension="W",
                           tolerance=("rel", 1e-12, ""))
    time750 = _numeric_item(item, answer, dimension="s")
    if (heater["pass"] and time750["pass"]
            and "fail" in low):
        items.append(_pass(item, f"{heater['detail']}; "
                                 f"{time750['detail']}; the "
                                 f"failure verdict is "
                                 f"stated"))
    else:
        items.append(_fail(item, f"750 W within tolerance: "
                                 f"{heater['pass']}; 160 s "
                                 f"within tolerance: "
                                 f"{time750['pass']}; "
                                 f"failure verdict stated: "
                                 f"{'fail' in low} - all "
                                 f"three are required"))

    items.append(_numeric_item(
        _item_by_name(record, "Delivered energy"),
        answer, dimension="J"))
    items.append(_organization(record, answer, 3, (
        ("energy", "requirement"),
        ("heater",),
        ("delivered", "energy"),
    )))
    return items


# ── Q15: the extensometer check ─────────────────────────

def _score_q15(answer: str, record: dict) -> list[dict]:
    items: list[dict] = []
    low = _normalize(answer).lower()

    def verdict_near(targets: tuple[str, ...],
                     word: str) -> bool:
        """Whether the stated error carries its verdict:
        the word appears with the error value, in the
        same step or within the following text. The
        error may be stated in any notation the key
        accepts ('0.010 mm' or '10 um')."""
        for step in _numbered_steps(answer):
            low_step = step.lower()
            if (any(t in low_step for t in targets)
                    and word in low_step):
                return True
        for target in targets:
            i = low.find(target)
            if i >= 0 and word in low[i:i + 48]:
                return True
        return False

    # 1. the ordered check sequence
    item = _item_by_name(record, "Ordered check sequence")
    order = _ordered(answer, (
        (("zero",), ("1.000", "1 mm")),
        (("1.000", "1 mm"), ("2.000", "2 mm")),
        (("2.000", "2 mm"), ("return",)),
    ))
    no_readjust = ("without" in low
                   and ("re-zero" in low
                        or "readjust" in low
                        or "adjustment" in low))
    if order and no_readjust:
        items.append(_pass(item, "zero at unloaded zero, "
                                 "apply and record 1.000 mm, "
                                 "apply and record 2.000 mm, "
                                 "then return to zero and "
                                 "record without re-zeroing"))
    else:
        items.append(_fail(item, f"ordered sequence "
                                 f"(zero, 1.000 mm, 2.000 mm, "
                                 f"return): {order}; no "
                                 f"re-zeroing between "
                                 f"readings stated: "
                                 f"{no_readjust} - both are "
                                 f"required"))

    # 2. the acceptance criteria
    item = _item_by_name(record, "Acceptance criteria")
    limit1 = (re.search(r"(?:<=|at most|no more than)\s*"
                        r"0\.020?\s*mm", low)
              or re.search(r"(?:<=|at most|no more than)\s*"
                           r"20\s*um", low))
    limit2 = (re.search(r"(?:<=|at most|no more than)\s*"
                        r"0\.010?\s*mm", low)
              or re.search(r"(?:<=|at most|no more than)\s*"
                           r"10\s*um", low))
    if limit1 and limit2:
        items.append(_pass(item, "both inclusive limits "
                                 "(nonzero errors at most "
                                 "0.020 mm, return zero at "
                                 "most 0.010 mm) are "
                                 "stated"))
    else:
        items.append(_fail(item, f"0.020 mm nonzero limit "
                                 f"stated: {limit1 is not None}; "
                                 f"0.010 mm return-zero limit "
                                 f"stated: {limit2 is not None} "
                                 f"- both are required"))

    # 3-5. the three signed errors with their verdicts
    error_targets = {
        "First signed error and verdict":
            ("0.010", "10 um"),
        "Second signed error and verdict":
            ("0.030", "30 um"),
        "Return-zero error and verdict":
            ("0.005", "5 um"),
    }
    for name, word in (("First signed error and verdict",
                        "pass"),
                       ("Second signed error and verdict",
                        "fail"),
                       ("Return-zero error and verdict",
                        "pass")):
        item = _item_by_name(record, name)
        err = _numeric_item(item, answer, dimension="m")
        stated = verdict_near(error_targets[name], word)
        if err["pass"] and stated:
            items.append(_pass(item, f"{err['detail']}; the "
                                     f"'{word}' verdict is "
                                     f"stated with the error"))
        else:
            items.append(_fail(item, f"error within "
                                     f"tolerance: "
                                     f"{err['pass']}; "
                                     f"'{word}' verdict "
                                     f"stated with the "
                                     f"error: {stated} - "
                                     f"both are required"))

    # 6. the overall verdict
    item = _item_by_name(record, "Overall verdict")
    if (any(w in low for w in ("fail", "unacceptable"))
            and verdict_near(("0.030", "30 um"),
                               "fail")):
        items.append(_pass(item, "the overall FAIL "
                                 "identifies the failed "
                                 "second reading as the "
                                 "cause"))
    else:
        items.append(_fail(item, "the overall FAIL and the "
                                 "second reading as its "
                                 "cause are not both "
                                 "stated"))
    return items


# ── Q16: the freely expanding bar ───────────────────────

def _score_q16(answer: str, record: dict) -> list[dict]:
    items: list[dict] = []

    items.append(_numeric_item(
        _item_by_name(record, "Length increase"),
        answer, dimension="m"))
    items.append(_numeric_item(
        _item_by_name(record, "Final length"),
        answer, dimension="m"))
    return items


# ── Q17: the lockout-tagout lookup ──────────────────────

def _score_q17(answer: str, record: dict) -> list[dict]:
    items: list[dict] = []
    low = _normalize(answer).lower()

    # 1. the minimum unlocking strength, with its
    #    inclusive lower bound
    item = _item_by_name(record,
                         "Minimum unlocking strength")
    strength = _numeric_item(item, answer,
                             dimension="lb")
    bound = any(w in low for w in ("at least",
                                   "no less than",
                                   ">=", "minimum"))
    if strength["pass"] and bound:
        items.append(_pass(item, f"{strength['detail']}; "
                                 f"the inclusive lower "
                                 f"bound is stated"))
    else:
        items.append(_fail(item, f"50 lb within tolerance: "
                                 f"{strength['pass']}; "
                                 f"lower bound stated: "
                                 f"{bound} - both are "
                                 f"required"))

    # 2. the inspection frequency, as a minimum
    item = _item_by_name(record, "Inspection frequency")
    annually = ("annually" in low
                or "once per year" in low
                or "once a year" in low)
    freq_bound = any(w in low for w in ("at least",
                                        "no less than",
                                        ">=", "minimum"))
    if annually and freq_bound:
        items.append(_pass(item, "the at-least-annually "
                                 "inspection frequency is "
                                 "stated"))
    else:
        items.append(_fail(item, f"annually stated: "
                                 f"{annually}; minimum "
                                 f"frequency bound stated: "
                                 f"{freq_bound} - both are "
                                 f"required"))
    return items


# ── Q18: the simply supported beam ──────────────────────

def _score_q18(answer: str, record: dict) -> list[dict]:
    items: list[dict] = []
    low = _normalize(answer).lower()

    items.append(_numeric_item(
        _item_by_name(record, "Maximum bending moment"),
        answer, dimension="N m"))
    items.append(_numeric_item(
        _item_by_name(record, "Second moment of area"),
        answer, dimension="m^4"))
    items.append(_numeric_item(
        _item_by_name(record, "Maximum bending stress"),
        answer, dimension="Pa"))

    # the midspan deflection: magnitude and direction
    item = _item_by_name(record, "Midspan deflection")
    defl = _numeric_item(item, answer, dimension="m")
    if defl["pass"] and "downward" in low:
        items.append(_pass(item, f"{defl['detail']}; the "
                                 f"downward direction is "
                                 f"stated"))
    else:
        items.append(_fail(item, f"deflection within "
                                 f"tolerance: "
                                 f"{defl['pass']}; "
                                 f"downward direction "
                                 f"stated: "
                                 f"{'downward' in low} - "
                                 f"both are required"))
    return items


# ── Q19: the LED series resistor ────────────────────────

def _score_q19(answer: str, record: dict) -> list[dict]:
    items: list[dict] = []
    low = _normalize(answer).lower()

    # 1. the selected resistance and its current
    item = _item_by_name(record,
                         "Selected resistance and current")
    ohm = _numeric_item(item, answer, dimension="ohm",
                        tolerance=("rel", 1e-12, ""))
    current = _numeric_item(item, answer, dimension="A")
    if ohm["pass"] and current["pass"]:
        items.append(_pass(item, f"{ohm['detail']}; "
                                 f"{current['detail']}"))
    else:
        items.append(_fail(item, f"resistance within "
                                 f"tolerance: "
                                 f"{ohm['pass']}; current "
                                 f"within tolerance: "
                                 f"{current['pass']} - "
                                 f"both are required"))

    # 2. the 270 ohm rejection: 24.4444 mA, fails high
    item = _item_by_name(record,
                         "Lower resistance rejection")
    r270 = _numeric_item(item, answer, dimension="ohm",
                         tolerance=("rel", 1e-12, ""))
    i270 = _numeric_item(item, answer, dimension="A")
    if (r270["pass"] and i270["pass"]
            and any(w in low for w in ("high",
                                       "exceed"))):
        items.append(_pass(item, f"{r270['detail']}; "
                                 f"{i270['detail']}; the "
                                 f"too-high failure is "
                                 f"stated"))
    else:
        items.append(_fail(item, f"270 ohm within "
                                 f"tolerance: "
                                 f"{r270['pass']}; 24.4444 "
                                 f"mA within tolerance: "
                                 f"{i270['pass']}; "
                                 f"too-high verdict stated: "
                                 f"{any(w in low for w in ('high', 'exceed'))} - "
                                 f"all three are required"))

    # 3. the 390 ohm rejection: 16.9231 mA, fails low
    item = _item_by_name(record,
                         "Higher resistance rejection")
    r390 = _numeric_item(item, answer, dimension="ohm",
                         tolerance=("rel", 1e-12, ""))
    i390 = _numeric_item(item, answer, dimension="A")
    if (r390["pass"] and i390["pass"]
            and any(w in low for w in ("low",
                                       "below"))):
        items.append(_pass(item, f"{r390['detail']}; "
                                 f"{i390['detail']}; the "
                                 f"too-low failure is "
                                 f"stated"))
    else:
        items.append(_fail(item, f"390 ohm within "
                                 f"tolerance: "
                                 f"{r390['pass']}; 16.9231 "
                                 f"mA within tolerance: "
                                 f"{i390['pass']}; "
                                 f"too-low verdict stated: "
                                 f"{any(w in low for w in ('low', 'below'))} - "
                                 f"all three are required"))

    # 4. the resistor dissipation
    items.append(_numeric_item(
        _item_by_name(record, "Resistor dissipation"),
        answer, dimension="W"))

    # 5. the minimum required and selected ratings
    item = _item_by_name(record,
                         "Minimum required and selected "
                         "power ratings")
    minimum = _numeric_item(item, answer, dimension="W")
    selected = any(
        _to_base(v, u) and _to_base(v, u)[0] == "W"
        and _within(_to_base(v, u)[1], 0.500,
                    ("rel", 1e-12, ""))
        for v, u in extract_quantities(answer))
    if minimum["pass"] and selected:
        items.append(_pass(item, f"{minimum['detail']}; the "
                                 f"selected 0.500 W rating "
                                 f"is stated exactly"))
    else:
        items.append(_fail(item, f"0.264 W minimum within "
                                 f"tolerance: "
                                 f"{minimum['pass']}; 0.500 "
                                 f"W selected exactly: "
                                 f"{selected} - both are "
                                 f"required"))

    items.append(_organization(record, answer, 3, (
        ("selection", "current"),
        ("other", "choice"),
        ("dissipation", "rating"),
    )))
    return items


# ── Q20: the flowmeter collection check ─────────────────

def _score_q20(answer: str, record: dict) -> list[dict]:
    items: list[dict] = []
    low = _normalize(answer).lower()
    quantities = extract_quantities(answer)

    # 1. start and stabilization
    item = _item_by_name(record, "Start and stabilization")
    order = _ordered(answer, (
        (("return",), ("set",)),
        (("set",), ("stabiliz",)),
        (("stabiliz",), ("collect",)),
    ))
    setpoint = _has_quantity(quantities, "L/min", 12.0)
    settle = _has_quantity(quantities, "s", 30.0)
    if order and setpoint and settle:
        items.append(_pass(item, "flow starts to the "
                                 "return tank, the "
                                 "12.0 L/min setpoint is "
                                 "set and stabilized for "
                                 "30 s, and only then is "
                                 "anything collected"))
    else:
        items.append(_fail(item, f"return before set before "
                                 f"stabilize before collect: "
                                 f"{order}; 12.0 L/min "
                                 f"stated: {setpoint}; 30 s "
                                 f"stated: {settle} - all "
                                 f"are required"))

    # 2. the collection sequence
    item = _item_by_name(record, "Collection sequence")
    order = _ordered(answer, (
        (("zero",), ("divert",)),
        (("divert",), ("collect",)),
    ))
    together = "together" in low
    collect = _has_quantity(quantities, "s", 60.0)
    no_adjust = ("without" in low
                 and "adjust" in low)
    if order and together and collect and no_adjust:
        items.append(_pass(item, "the volume is zeroed, "
                                 "diversion and timer start "
                                 "together, and 60.0 s is "
                                 "collected without "
                                 "adjustment"))
    else:
        items.append(_fail(item, f"zero before divert before "
                                 f"collect: {order}; "
                                 f"diversion and timer "
                                 f"together: {together}; "
                                 f"60.0 s stated: {collect}; "
                                 f"no adjustment stated: "
                                 f"{no_adjust} - all are "
                                 f"required"))

    # 3. the end sequence
    item = _item_by_name(record, "End sequence")
    order = _ordered(answer, (
        (("divert back",), ("read",)),
        (("read",), ("stop the pump",)),
    ))
    if order:
        items.append(_pass(item, "diversion back and timer "
                                 "stop happen together, the "
                                 "volume is read, and only "
                                 "then is the pump stopped"))
    else:
        items.append(_fail(item, "the end sequence (divert "
                                 "back and stop timing "
                                 "together, read volume, "
                                 "then stop pump) is not "
                                 "stated in order"))

    # 4. the reference flow
    items.append(_numeric_item(
        _item_by_name(record, "Reference flow"),
        answer, dimension="L/min"))

    # 5. the signed indication error
    item = _item_by_name(record, "Signed indication error")
    tolerance = parse_tolerance(
        item["tolerance_or_variants"])
    key_value, _ = _key_quantities(item, "%", 0)
    _, key_pct = _to_base(key_value, "%")
    signed: float | None = None
    for value, unit in extract_quantities(answer):
        converted = _to_base(value, unit)
        if (converted and converted[0] == "%"
                and _within(converted[1], key_pct,
                            tolerance)):
            signed = converted[1]
            break
    positive = signed is not None and (
        re.search(r"\+\s*2\.0\d*\s*%", low) is not None
        or "over" in low or "reads high" in low
        or "over-read" in low)
    if positive:
        items.append(_pass(item, f"the signed error "
                                 f"{signed:.5g}% carries "
                                 f"its positive sign (or an "
                                 f"over-reading statement)"))
    else:
        items.append(_fail(item, "no positively signed "
                                 f"error within tolerance of "
                                 f"{key_pct:.5g}% is stated "
                                 f"(positive sign or "
                                 f"over-reading statement "
                                 f"required)"))

    # 6. the acceptance criterion and verdict
    item = _item_by_name(record, "Acceptance and verdict")
    criterion = (re.search(
        r"(?:<=|at most|no more than)\s*"
        r"(?:\|\s*e\s*\|)?\s*3\.0\s*%", low)
        is not None)
    if criterion and "pass" in low:
        items.append(_pass(item, "the inclusive 3.0% "
                                 "magnitude limit and the "
                                 "passing verdict are "
                                 "stated"))
    else:
        items.append(_fail(item, f"inclusive 3.0% limit "
                                 f"stated: {criterion}; "
                                 f"pass verdict stated: "
                                 f"{'pass' in low} - both "
                                 f"are required"))
    return items


# ── Q21: the insulated mixing vessel ────────────────────

def _score_q21(answer: str, record: dict) -> list[dict]:
    items: list[dict] = []

    items.append(_numeric_item(
        _item_by_name(record, "Final temperature"),
        answer, dimension="deg C"))
    return items


# ── Q22: the audiogram baseline lookup ──────────────────

def _score_q22(answer: str, record: dict) -> list[dict]:
    items: list[dict] = []
    low = _normalize(answer).lower()
    quantities = extract_quantities(answer)

    # 1. the baseline deadline
    item = _item_by_name(record, "Baseline deadline")
    months = _has_quantity(quantities, "month", 6.0)
    context = ("first exposure" in low
               and "action level" in low)
    if months and context:
        items.append(_pass(item, "the 6-month deadline "
                                 "from first exposure at "
                                 "or above the action "
                                 "level is stated"))
    else:
        items.append(_fail(item, f"6 months stated: "
                                 f"{months}; first exposure "
                                 f"at or above the action "
                                 f"level stated: {context} - "
                                 f"both are required"))

    # 2. the pre-baseline workplace-noise-free period
    item = _item_by_name(
        record,
        "Pre-baseline workplace-noise-free period")
    hours = _has_quantity(quantities, "h", 14.0)
    context = ("workplace" in low and "noise" in low
               and any(w in low for w in ("at least",
                                          "no less than",
                                          ">=")))
    if hours and context:
        items.append(_pass(item, "the at-least-14 h "
                                 "workplace-noise-free "
                                 "period is stated"))
    else:
        items.append(_fail(item, f"14 h stated: {hours}; "
                                 f"workplace-noise "
                                 f"qualification and minimum "
                                 f"bound stated: {context} - "
                                 f"both are required"))

    # 3. the retest window
    item = _item_by_name(record, "Retest window")
    days = _has_quantity(quantities, "day", 30.0)
    if days and "retest" in low:
        items.append(_pass(item, "the 30-day retest "
                                 "window is stated"))
    else:
        items.append(_fail(item, f"30 days stated: {days}; "
                                 f"retest named: "
                                 f"{'retest' in low} - both "
                                 f"are required"))
    return items


# ── Q23: the parallel bars ──────────────────────────────

def _score_q23(answer: str, record: dict) -> list[dict]:
    items: list[dict] = []

    items.append(_numeric_item(
        _item_by_name(record, "Common extension"),
        answer, dimension="m"))
    items.append(_numeric_item(
        _item_by_name(record, "Aluminum tensile stress"),
        answer, dimension="Pa"))
    items.append(_numeric_item(
        _item_by_name(record, "Steel tensile stress"),
        answer, dimension="Pa"))
    items.append(_numeric_item(
        _item_by_name(record, "Aluminum force"),
        answer, dimension="N"))
    items.append(_numeric_item(
        _item_by_name(record, "Steel force"),
        answer, dimension="N"))
    return items


# ── Q24: the open-belt drive ────────────────────────────

def _score_q24(answer: str, record: dict) -> list[dict]:
    items: list[dict] = []
    low = _normalize(answer).lower()

    # 1. the selected driven diameter and ratio
    item = _item_by_name(record,
                         "Selected driven diameter and ratio")
    diameter = _numeric_item(item, answer,
                             dimension="m")
    ratio = ("3:1" in low
             or "ratio 3" in low
             or "ratio of 3" in low
             or re.search(r"ratio\s*=\s*3\b",
                          low) is not None)
    if diameter["pass"] and ratio:
        items.append(_pass(item, f"{diameter['detail']}; "
                                 f"the 3:1 driven-to-driver "
                                 f"ratio is stated"))
    else:
        items.append(_fail(item, f"240 mm within tolerance: "
                                 f"{diameter['pass']}; 3:1 "
                                 f"ratio stated: {ratio} - "
                                 f"both are required"))

    items.append(_numeric_item(
        _item_by_name(record, "Output speed"),
        answer, dimension="rpm"))

    item = _item_by_name(record, "Output direction")
    same = ("same" in low
            and ("direction" in low or "sense" in low)
            and "driver" in low)
    if same:
        items.append(_pass(item, "the output rotates in "
                                 "the same direction as "
                                 "the driver"))
    else:
        items.append(_fail(item, "the same-rotation-direction-"
                                 "as-driver relationship is "
                                 "not stated"))

    items.append(_numeric_item(
        _item_by_name(record, "Output torque"),
        answer, dimension="N m"))
    items.append(_numeric_item(
        _item_by_name(record, "Belt linear speed"),
        answer, dimension="m/s"))
    items.append(_organization(record, answer, 3, (
        ("selection", "ratio"),
        ("output",),
        ("belt", "speed"),
    )))
    return items


# ── Q25: the comparator hysteresis check ────────────────

def _score_q25(answer: str, record: dict) -> list[dict]:
    items: list[dict] = []
    low = _normalize(answer).lower()
    quantities = extract_quantities(answer)

    # 1. the initialization order and state
    item = _item_by_name(record,
                         "Initialization order and state")
    order = _ordered(answer, (
        ((r"re:(?<![\d.])0\s*v", "zero"),
         ("enable",)),
        (("enable",), ("low",)),
    ))
    if order:
        items.append(_pass(item, "the input is set to 0 V "
                                 "before the supply is "
                                 "enabled, and LOW is "
                                 "confirmed"))
    else:
        items.append(_fail(item, "the initialization order "
                                 "(0 V, then enable supply, "
                                 "then confirm LOW) is not "
                                 "stated in order"))

    # 2. the rising sweep
    item = _item_by_name(record, "Rising sweep")
    rising = ("monoton" in low
              and any(w in low for w in ("increase",
                                         "upward",
                                         "raise"))
              and "low-to-high" in low)
    # the record precedes the continuation to the
    # 5.00 V endpoint, where HIGH is confirmed; the
    # first 'confirm' belongs to the initialization
    # ('confirm LOW'), so the endpoint is the
    # 'high' that follows 'continue' in reading order
    norm = low
    i_record = norm.find("record")
    i_continue = norm.find("continue")
    order = (i_record >= 0 and i_continue > i_record
             and "high" in norm[i_continue:])
    if (rising and order
            and _has_quantity(quantities, "V", 5.00)):
        items.append(_pass(item, "the input rises "
                                 "monotonically, the "
                                 "LOW-to-HIGH transition is "
                                 "recorded, and the sweep "
                                 "continues to 5.00 V where "
                                 "HIGH is confirmed"))
    else:
        items.append(_fail(item, f"monotonic rise with "
                                 f"LOW-to-HIGH recorded: "
                                 f"{rising}; record then "
                                 f"continue then confirm "
                                 f"order: {order}; 5.00 V "
                                 f"stated: "
                                 f"{_has_quantity(quantities, 'V', 5.00)} - "
                                 f"all are required"))

    # 3. the falling sweep and shutdown
    item = _item_by_name(record,
                         "Falling sweep and shutdown")
    falling = ("monoton" in low
               and any(w in low for w in ("decrease",
                                          "downward",
                                          "lower"))
               and "high-to-low" in low)
    order = _ordered(answer, (
        (("return",), ("disable",)),
    ))
    if falling and order:
        items.append(_pass(item, "the input falls "
                                 "monotonically, the "
                                 "HIGH-to-LOW transition is "
                                 "recorded, and the input "
                                 "returns to zero before the "
                                 "supply is disabled"))
    else:
        items.append(_fail(item, f"monotonic fall with "
                                 f"HIGH-to-LOW recorded: "
                                 f"{falling}; return to zero "
                                 f"before disabling supply: "
                                 f"{order} - both are "
                                 f"required"))

    # 4. the acceptance criteria
    item = _item_by_name(record, "Acceptance criteria")
    rising_band = (re.search(
        r"2\.90\s*(?:[–—-]|to)\s*3\.10", low)
        is not None)
    falling_band = (re.search(
        r"1\.90\s*(?:[–—-]|to)\s*2\.10", low)
        is not None)
    inclusive = ("inclusive" in low or "<=" in low)
    endpoints = "endpoint" in low
    one_transition = ("one transition" in low
                      or "single transition" in low)
    if (rising_band and falling_band and inclusive
            and endpoints and one_transition):
        items.append(_pass(item, "both inclusive transition "
                                 "bands, the correct "
                                 "endpoint states, and "
                                 "exactly one transition "
                                 "per sweep are required"))
    else:
        items.append(_fail(item, f"rising 2.90-3.10 V band "
                                 f"stated: {rising_band}; "
                                 f"falling 1.90-2.10 V band "
                                 f"stated: {falling_band}; "
                                 f"inclusive stated: "
                                 f"{inclusive}; endpoints "
                                 f"stated: {endpoints}; one "
                                 f"transition per sweep "
                                 f"stated: {one_transition} "
                                 f"- all five are required"))

    # 5. the hysteresis width
    items.append(_numeric_item(
        _item_by_name(record, "Hysteresis width"),
        answer, dimension="V"))

    # 6. the logged verdict
    item = _item_by_name(record, "Logged verdict")
    if ("pass" in low
            and _has_quantity(quantities, "V", 3.04)
            and _has_quantity(quantities, "V", 1.96)):
        items.append(_pass(item, "the passing verdict "
                                 "identifies the logged "
                                 "3.04 V and 1.96 V "
                                 "transitions"))
    else:
        items.append(_fail(item, "the pass verdict and the "
                                 "logged 3.04 V and 1.96 V "
                                 "transitions are not all "
                                 "stated"))
    return items


SCORERS = {"Q1": _score_q1, "Q2": _score_q2, "Q3": _score_q3,
           "Q4": _score_q4, "Q5": _score_q5, "Q6": _score_q6,
           "Q7": _score_q7, "Q8": _score_q8, "Q9": _score_q9,
           "Q10": _score_q10, "Q11": _score_q11,
           "Q12": _score_q12, "Q13": _score_q13,
           "Q14": _score_q14, "Q15": _score_q15,
           "Q16": _score_q16, "Q17": _score_q17,
           "Q18": _score_q18, "Q19": _score_q19,
           "Q20": _score_q20, "Q21": _score_q21,
           "Q22": _score_q22, "Q23": _score_q23,
           "Q24": _score_q24, "Q25": _score_q25}


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
          f"is frozen at {MANIFEST['dataset_version']} by the "
          f"owner's signoff - see manifest.json")
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
        ("Q6 sum-of-products form", "Q6",
         r"Y = A\overline{B}+\overline{A}B. "
         "For 00, 01, 10, 11: 0, 1, 1, 0.",
         {"Alarm function": True,
          "Ordered outputs": True}),
        ("Q6 prose exclusive OR", "Q6",
         "The alarm is the exclusive OR of A and B. "
         "Outputs: 0, 1, 1, 0.",
         {"Alarm function": True,
          "Ordered outputs": True}),
        ("Q7 durations in number words", "Q7",
         "90 dBA: eight hours per day. "
         "95 dBA: four hours. 100 dBA: two hours.",
         {"Duration at $90\\,\\mathrm{dBA}$": True,
          "Duration at $95\\,\\mathrm{dBA}$": True,
          "Duration at $100\\,\\mathrm{dBA}$": True}),
        ("Q7 durations in hours abbreviated", "Q7",
         "90 dBA: 8 hr/day. 95 dBA: 4 hr. "
         "100 dBA: 2 hr.",
         {"Duration at $90\\,\\mathrm{dBA}$": True,
          "Duration at $95\\,\\mathrm{dBA}$": True,
          "Duration at $100\\,\\mathrm{dBA}$": True}),
        ("Q8 resistances in prose spellings", "Q8",
         "Layer A: 0.250 degrees Celsius per watt. "
         "Layer B: 0.0500 K/W. Heat flow 133 W from "
         "hot to cold. Interface 26.7 deg C.",
         {"Layer A resistance": True,
          "Layer B resistance": True,
          "Heat-transfer rate": True,
          "Interface temperature": True}),
        ("Q9 stiffness in N/m", "Q9",
         "Selected spring: k = 10000 N/m.",
         {"Selected stiffness": True}),
        ("Q9 stiffness in kN/m", "Q9",
         "Selected spring: k = 10 kN/m.",
         {"Selected stiffness": True}),
        ("Q9 energy in mJ", "Q9",
         "Stored energy U = 720 mJ.",
         {"Stored elastic energy": True}),
        ("Q9 energy in N mm", "Q9",
         "Stored energy U = 720 N mm.",
         {"Stored elastic energy": True}),
        ("Q11 speed in rev/s", "Q11",
         "Output: 5 rev/s, counterclockwise, "
         "9.00 N m.",
         {"Output speed": True}),
        ("Q12 MCLs in ug/L and mg N/L", "Q12",
         "Arsenic: 10 μg/L. Fluoride: 4000 μg/L. "
         "Nitrate: 10 mg N/L as nitrogen.",
         {"Arsenic MCL": True,
          "Fluoride MCL": True,
          "Nitrate MCL and reporting basis": True}),
        ("Q13 time constant in ms, current in uA",
         "Q13",
         "tau = RC = 1000 ms. V_C(2.00) = 8.65 V. "
         "I(2.00) = 135.335 μA.",
         {"Time constant": True,
          "Capacitor voltage": True,
          "Resistor current": True}),
        ("Q14 heat in kJ, heater in kW, time in min",
         "Q14",
         "Required heat Q = 120 kJ. Select 1.00 kW: "
         "t = 2 min, passes. The 750 W heater takes "
         "160 s, fails. Delivered energy E = 120 kJ.",
         {"Required heat": True,
          "Selected heater": True,
          "Selected heating time and verdict": True,
          "Next smaller heater check": True,
          "Delivered energy": True}),
        ("Q15 errors in um", "Q15",
         "1. Zero at unloaded zero.\n"
         "2. Apply 1.000 mm and record: error +10 μm, "
         "pass.\n"
         "3. Increase to 2.000 mm and record: error "
         "-30 μm, fail.\n"
         "4. Return to zero without adjustment: error "
         "+5 μm, pass.\n"
         "Limits: nonzero errors <= 20 um; return zero "
         "<= 10 um. Overall: FAIL.",
         {"Ordered check sequence": True,
          "Acceptance criteria": True,
          "First signed error and verdict": True,
          "Second signed error and verdict": True,
          "Return-zero error and verdict": True,
          "Overall verdict": True}),
        ("Q16 increase in metres", "Q16",
         "Delta L = 0.000480 m. L_f = 0.800480 m.",
         {"Length increase": True,
          "Final length": True}),
        ("Q17 strength in pounds, frequency in words",
         "Q17",
         "Attachment unlocking strength: no less than "
         "50 pounds. Energy-control procedure "
         "inspection: at least once per year.",
         {"Minimum unlocking strength": True,
          "Inspection frequency": True}),
        ("Q18 moment in kN m, I in mm^4, deflection "
         "in metres", "Q18",
         "M_max = 0.500 kN m. I = 720000 mm^4. "
         "sigma_max = 20.8 MPa. "
         "delta = 0.00115741 m downward.",
         {"Maximum bending moment": True,
          "Second moment of area": True,
          "Maximum bending stress": True,
          "Midspan deflection": True}),
        ("Q19 current in A, dissipation in mW", "Q19",
         "Selection and current: 330 ohm, I = 0.0200 A, "
         "passes. Other choices: 270 ohm gives 24.4 mA, "
         "too high; 390 ohm gives 16.9 mA, too low. "
         "Dissipation and rating: P = 132 mW. Required "
         "rating >= 264 mW; select 0.500 W.",
         {"Selected resistance and current": True,
          "Lower resistance rejection": True,
          "Higher resistance rejection": True,
          "Resistor dissipation": True,
          "Minimum required and selected power ratings": True}),
        ("Q20 reference in L/s, collection in minutes",
         "Q20",
         "1. Start with flow to return; set 12.0 L/min "
         "and stabilize for 30 s.\n"
         "2. Zero volume; divert into the vessel and "
         "start timing together.\n"
         "3. Collect 1 minute without adjustment.\n"
         "4. Divert back and stop timing together; read "
         "volume, then stop the pump.\n"
         "5. Reference: 0.196 L/s. Error: +2.04%. "
         "Limit: |e| <= 3.0%. PASS.",
         {"Start and stabilization": True,
          "Collection sequence": True,
          "End sequence": True,
          "Reference flow": True,
          "Signed indication error": True,
          "Acceptance and verdict": True}),
        ("Q21 temperature in kelvin", "Q21",
         "T_f = 308.15 K.",
         {"Final temperature": True}),
        ("Q22 intervals in number words", "Q22",
         "Baseline: within six months of first exposure "
         "at or above the action level. Before baseline: "
         "at least fourteen hours without workplace-noise "
         "exposure. Optional threshold-shift retest: "
         "within thirty days.",
         {"Baseline deadline": True,
          "Pre-baseline workplace-noise-free period": True,
          "Retest window": True}),
        ("Q23 figures rounded as the key accepts", "Q23",
         "Extension: 0.882 mm. Aluminum: 61.8 MPa "
         "tension, 12.35 kN. Steel: 176.5 MPa tension, "
         "17.65 kN.",
         {"Common extension": True,
          "Aluminum tensile stress": True,
          "Steel tensile stress": True,
          "Aluminum force": True,
          "Steel force": True}),
        ("Q24 diameter in metres, torque in words",
         "Q24",
         "Selection and ratio: driven pitch diameter "
         "0.240 m; ratio 3. Output: 500 rpm, same "
         "direction as driver; torque 12 newton-metres. "
         "Belt speed: v = 6.28 m/s.",
         {"Selected driven diameter and ratio": True,
          "Output torque": True}),
        ("Q25 width in mV", "Q25",
         "1. Set input to 0 V; enable 5.00 V supply; "
         "confirm LOW.\n"
         "2. Sweep upward monotonically and record "
         "LOW-to-HIGH; continue to 5.00 V and confirm "
         "HIGH.\n"
         "3. Sweep downward monotonically and record "
         "HIGH-to-LOW; return input to zero, then "
         "disable supply.\n"
         "4. Require rising 2.90-3.10 V and falling "
         "1.90-2.10 V inclusive, correct endpoints, and "
         "one transition per sweep.\n"
         "5. Logged 3.04 and 1.96 V satisfy all checks: "
         "PASS. Width = 1080 mV.",
         {"Hysteresis width": True}),
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
        ("Q8 layer A resistance at +0.001 K/W", "Q8",
         "R_A = 0.251 K/W.",
         {"Layer A resistance": True}),
        ("Q8 layer A resistance past +0.001 K/W", "Q8",
         "R_A = 0.252 K/W.",
         {"Layer A resistance": False}),
        ("Q8 layer B resistance at +0.0001 K/W", "Q8",
         "R_B = 0.0501 K/W.",
         {"Layer B resistance": True}),
        ("Q8 layer B resistance past +0.0001 K/W", "Q8",
         "R_B = 0.0502 K/W.",
         {"Layer B resistance": False}),
        ("Q8 heat rate at the boundary", "Q8",
         "Q = 133.833 W, hot to cold.",
         {"Heat-transfer rate": True}),
        ("Q8 heat rate past the boundary", "Q8",
         "Q = 133.9 W, hot to cold.",
         {"Heat-transfer rate": False}),
        ("Q8 interface temperature at the boundary",
         "Q8", "T_i = 26.7667 deg C.",
         {"Interface temperature": True}),
        ("Q8 interface temperature past the boundary",
         "Q8", "T_i = 26.8 deg C.",
         {"Interface temperature": False}),
        ("Q9 extension at the limit (equality "
         "permitted)", "Q9",
         "Extension check: 12.01 mm: passes.",
         {"Selected extension and verdict": True}),
        ("Q9 extension past the limit", "Q9",
         "Extension check: 12.02 mm: passes.",
         {"Selected extension and verdict": False}),
        ("Q9 stored energy at +0.001 J", "Q9",
         "Stored energy U = 0.721 J.",
         {"Stored elastic energy": True}),
        ("Q9 stored energy past +0.001 J", "Q9",
         "Stored energy U = 0.722 J.",
         {"Stored elastic energy": False}),
        ("Q11 speed at +0.1 rpm", "Q11",
         "Output: 300.1 rpm, counterclockwise, "
         "9.00 N m.",
         {"Output speed": True}),
        ("Q11 speed past +0.1 rpm", "Q11",
         "Output: 300.2 rpm, counterclockwise, "
         "9.00 N m.",
         {"Output speed": False}),
        ("Q11 torque at +0.01 N m", "Q11",
         "Output: 300 rpm, counterclockwise, "
         "9.01 N m.",
         {"Output torque magnitude": True}),
        ("Q11 torque past +0.01 N m", "Q11",
         "Output: 300 rpm, counterclockwise, "
         "9.02 N m.",
         {"Output torque magnitude": False}),
        ("Q12 arsenic exactly 0.010 mg/L", "Q12",
         "Arsenic: 0.010 mg/L.",
         {"Arsenic MCL": True}),
        ("Q12 arsenic past 0.010 mg/L", "Q12",
         "Arsenic: 0.011 mg/L.",
         {"Arsenic MCL": False}),
        ("Q12 fluoride exactly 4.0 mg/L", "Q12",
         "Fluoride: 4.0 mg/L.",
         {"Fluoride MCL": True}),
        ("Q12 fluoride past 4.0 mg/L", "Q12",
         "Fluoride: 4.1 mg/L.",
         {"Fluoride MCL": False}),
        ("Q13 time constant at +0.001 s", "Q13",
         "tau = 1.001 s.",
         {"Time constant": True}),
        ("Q13 time constant past +0.001 s", "Q13",
         "tau = 1.002 s.",
         {"Time constant": False}),
        ("Q13 capacitor voltage at +0.01 V", "Q13",
         "V_C(2.00) = 8.6565 V.",
         {"Capacitor voltage": True}),
        ("Q13 capacitor voltage past +0.01 V", "Q13",
         "V_C(2.00) = 8.6665 V.",
         {"Capacitor voltage": False}),
        ("Q13 current at +0.001 mA", "Q13",
         "I(2.00) = 0.136335 mA.",
         {"Resistor current": True}),
        ("Q13 current past +0.001 mA", "Q13",
         "I(2.00) = 0.137335 mA.",
         {"Resistor current": False}),
        ("Q14 heating time at the limit (equality "
         "permitted)", "Q14",
         "Select 1000 W: t = 120.1 s, passes.",
         {"Selected heating time and verdict": True}),
        ("Q14 heating time past the limit", "Q14",
         "Select 1000 W: t = 120.2 s, passes.",
         {"Selected heating time and verdict": False}),
        ("Q14 required heat at +100 J", "Q14",
         "Required heat Q = 120100 J.",
         {"Required heat": True}),
        ("Q14 required heat past +100 J", "Q14",
         "Required heat Q = 120200 J.",
         {"Required heat": False}),
        ("Q14 delivered energy at +0.1 kJ", "Q14",
         "Delivered energy E = 120.1 kJ.",
         {"Delivered energy": True}),
        ("Q14 delivered energy past +0.1 kJ", "Q14",
         "Delivered energy E = 120.2 kJ.",
         {"Delivered energy": False}),
        ("Q15 first error at +0.0005 mm", "Q15",
         "2. Apply 1.000 mm and record: error "
         "+0.0105 mm, pass.",
         {"First signed error and verdict": True}),
        ("Q15 first error past +0.0005 mm", "Q15",
         "2. Apply 1.000 mm and record: error "
         "+0.011 mm, pass.",
         {"First signed error and verdict": False}),
        ("Q15 second error at -0.0005 mm", "Q15",
         "3. Increase to 2.000 mm and record: error "
         "-0.0305 mm, fail.",
         {"Second signed error and verdict": True}),
        ("Q15 second error past -0.0005 mm", "Q15",
         "3. Increase to 2.000 mm and record: error "
         "-0.031 mm, fail.",
         {"Second signed error and verdict": False}),
        ("Q15 return-zero error at +0.0005 mm", "Q15",
         "4. Return to zero without adjustment: "
         "error +0.0055 mm, pass.",
         {"Return-zero error and verdict": True}),
        ("Q15 return-zero error past +0.0005 mm",
         "Q15",
         "4. Return to zero without adjustment: "
         "error +0.006 mm, pass.",
         {"Return-zero error and verdict": False}),
        ("Q16 length increase at +0.001 mm", "Q16",
         "Delta L = 0.481 mm.",
         {"Length increase": True}),
        ("Q16 length increase past +0.001 mm", "Q16",
         "Delta L = 0.482 mm.",
         {"Length increase": False}),
        ("Q16 final length at +0.000001 m", "Q16",
         "L_f = 0.800481 m.",
         {"Final length": True}),
        ("Q16 final length past +0.000001 m", "Q16",
         "L_f = 0.800482 m.",
         {"Final length": False}),
        ("Q17 strength exactly 50 lb", "Q17",
         "Attachment unlocking strength: no less "
         "than 50 lb.",
         {"Minimum unlocking strength": True}),
        ("Q17 strength past 50 lb", "Q17",
         "Attachment unlocking strength: no less "
         "than 51 lb.",
         {"Minimum unlocking strength": False}),
        ("Q18 moment at +0.5 N m", "Q18",
         "M_max = 500.5 N m.",
         {"Maximum bending moment": True}),
        ("Q18 moment past +0.5 N m", "Q18",
         "M_max = 501 N m.",
         {"Maximum bending moment": False}),
        ("Q18 second moment at +0.1% relative", "Q18",
         "I = 7.2072e-7 m^4.",
         {"Second moment of area": True}),
        ("Q18 second moment past +0.1% relative",
         "Q18", "I = 7.21e-7 m^4.",
         {"Second moment of area": False}),
        ("Q18 stress at +0.05 MPa", "Q18",
         "sigma_max = 20.8833 MPa.",
         {"Maximum bending stress": True}),
        ("Q18 stress past +0.05 MPa", "Q18",
         "sigma_max = 20.89 MPa.",
         {"Maximum bending stress": False}),
        ("Q18 deflection at +0.005 mm", "Q18",
         "delta = 1.16241 mm downward.",
         {"Midspan deflection": True}),
        ("Q18 deflection past +0.005 mm", "Q18",
         "delta = 1.163 mm downward.",
         {"Midspan deflection": False}),
        ("Q19 current at +0.05 mA", "Q19",
         "Selection: 330 ohm, I = 20.05 mA, passes.",
         {"Selected resistance and current": True}),
        ("Q19 current past +0.05 mA", "Q19",
         "Selection: 330 ohm, I = 20.06 mA, passes.",
         {"Selected resistance and current": False}),
        ("Q19 dissipation at +0.001 W", "Q19",
         "Dissipation: P_R = 0.133 W.",
         {"Resistor dissipation": True}),
        ("Q19 dissipation past +0.001 W", "Q19",
         "Dissipation: P_R = 0.134 W.",
         {"Resistor dissipation": False}),
        ("Q19 minimum rating at +0.001 W", "Q19",
         "Required rating >= 0.265 W; select "
         "0.500 W.",
         {"Minimum required and selected power ratings": True}),
        ("Q19 minimum rating past +0.001 W", "Q19",
         "Required rating >= 0.266 W; select "
         "0.500 W.",
         {"Minimum required and selected power ratings": False}),
        ("Q20 reference flow at +0.005 L/min", "Q20",
         "Reference: 11.765 L/min.",
         {"Reference flow": True}),
        ("Q20 reference flow past +0.005 L/min",
         "Q20", "Reference: 11.77 L/min.",
         {"Reference flow": False}),
        ("Q20 signed error at +0.01 points", "Q20",
         "Error: +2.05082%.",
         {"Signed indication error": True}),
        ("Q20 signed error past +0.01 points", "Q20",
         "Error: +2.06%.",
         {"Signed indication error": False}),
        ("Q21 temperature at +0.05 deg C", "Q21",
         "T_f = 35.05 deg C.",
         {"Final temperature": True}),
        ("Q21 temperature past +0.05 deg C", "Q21",
         "T_f = 35.06 deg C.",
         {"Final temperature": False}),
        ("Q23 extension at +0.001 mm", "Q23",
         "Extension: 0.883353 mm.",
         {"Common extension": True}),
        ("Q23 extension past +0.001 mm", "Q23",
         "Extension: 0.884 mm.",
         {"Common extension": False}),
        ("Q23 aluminum stress at +0.1 MPa", "Q23",
         "Aluminum: 61.8647 MPa tension.",
         {"Aluminum tensile stress": True}),
        ("Q23 aluminum stress past +0.1 MPa", "Q23",
         "Aluminum: 61.9 MPa tension.",
         {"Aluminum tensile stress": False}),
        ("Q23 steel stress at +0.5 MPa", "Q23",
         "Steel: 176.971 MPa tension.",
         {"Steel tensile stress": True}),
        ("Q23 steel stress past +0.5 MPa", "Q23",
         "Steel: 177.0 MPa tension.",
         {"Steel tensile stress": False}),
        ("Q23 aluminum force at +0.01 kN", "Q23",
         "Aluminum: 12.3629 kN.",
         {"Aluminum force": True}),
        ("Q23 aluminum force past +0.01 kN", "Q23",
         "Aluminum: 12.37 kN.",
         {"Aluminum force": False}),
        ("Q24 speed at +0.5 rpm", "Q24",
         "Output: 500.5 rpm.",
         {"Output speed": True}),
        ("Q24 speed past +0.5 rpm", "Q24",
         "Output: 501 rpm.",
         {"Output speed": False}),
        ("Q24 torque at +0.01 N m", "Q24",
         "Output torque 12.01 N m.",
         {"Output torque": True}),
        ("Q24 torque past +0.01 N m", "Q24",
         "Output torque 12.02 N m.",
         {"Output torque": False}),
        ("Q24 belt speed at +0.01 m/s", "Q24",
         "Belt speed: v = 6.29319 m/s.",
         {"Belt linear speed": True}),
        ("Q24 belt speed past +0.01 m/s", "Q24",
         "Belt speed: v = 6.30 m/s.",
         {"Belt linear speed": False}),
        ("Q25 width at +0.005 V", "Q25",
         "Width = 1.085 V.",
         {"Hysteresis width": True}),
        ("Q25 width past +0.005 V", "Q25",
         "Width = 1.09 V.",
         {"Hysteresis width": False}),
        ("Q7 duration exactly 8 h", "Q7",
         "90 dBA: 8 h per day.",
         {"Duration at $90\\,\\mathrm{dBA}$": True}),
        ("Q7 duration past 8 h", "Q7",
         "90 dBA: 9 h per day.",
         {"Duration at $90\\,\\mathrm{dBA}$": False}),
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
        ("Q6 wrong: OR", "Q6", "OR",
         {"Alarm function": False,
          "Ordered outputs": False, "verdict": "FAIL"}),
        ("Q6 wrong: XNOR", "Q6", "XNOR",
         {"Alarm function": False,
          "Ordered outputs": False, "verdict": "FAIL"}),
        ("Q7 wrong: 90 dBA permits 2.5 h", "Q7",
         "90 dBA permits 2.5 h.",
         {"Duration at $90\\,\\mathrm{dBA}$": False,
          "verdict": "FAIL"}),
        ("Q7 wrong: 95 dBA permits 8 h", "Q7",
         "95 dBA permits 8 h.",
         {"Duration at $95\\,\\mathrm{dBA}$": False,
          "verdict": "FAIL"}),
        ("Q8 wrong: 200 W", "Q8", "Q = 200 W.",
         {"Heat-transfer rate": False,
          "verdict": "FAIL"}),
        ("Q8 wrong: 40 deg C interface", "Q8",
         "T_i = 40 deg C.",
         {"Interface temperature": False,
          "verdict": "FAIL"}),
        ("Q9 wrong: select 12 N/mm", "Q9",
         "Selected spring: k = 12 N/mm.",
         {"Selected stiffness": False,
          "verdict": "FAIL"}),
        ("Q9 wrong: 1.44 J stored energy", "Q9",
         "Stored energy U = 1.44 J.",
         {"Stored elastic energy": False,
          "verdict": "FAIL"}),
        ("Q10 wrong: start the timer when the oven "
         "is switched on", "Q10",
         "Start the timer when the oven is switched on.",
         {"Setpoint and timer-start order": False,
          "verdict": "FAIL"}),
        ("Q10 wrong: restart the timer after an "
         "excursion", "Q10",
         "Restart the timer after an excursion.",
         {"Hold criterion": False,
          "verdict": "FAIL"}),
        ("Q11 wrong: 2700 rpm", "Q11",
         "Output: 2700 rpm.",
         {"Output speed": False, "verdict": "FAIL"}),
        ("Q11 wrong: clockwise output", "Q11",
         "Output: clockwise.",
         {"Output direction": False,
          "verdict": "FAIL"}),
        ("Q12 wrong: 2 mg/L fluoride", "Q12",
         "Fluoride: 2 mg/L.",
         {"Fluoride MCL": False, "verdict": "FAIL"}),
        ("Q12 wrong: 10 mg/L as nitrate ion", "Q12",
         "Nitrate: 10 mg/L as nitrate ion.",
         {"Nitrate MCL and reporting basis": False,
          "verdict": "FAIL"}),
        ("Q12 wrong: 0.050 mg/L arsenic", "Q12",
         "Arsenic: 0.050 mg/L.",
         {"Arsenic MCL": False, "verdict": "FAIL"}),
        ("Q13 wrong: 1.353 V capacitor voltage", "Q13",
         "V_C(2.00) = 1.353 V.",
         {"Capacitor voltage": False,
          "verdict": "FAIL"}),
        ("Q13 wrong: 1 mA current at 2 s", "Q13",
         "I(2.00) = 1 mA.",
         {"Resistor current": False,
          "verdict": "FAIL"}),
        ("Q14 wrong: select 1250 W", "Q14",
         "Select 1250 W.",
         {"Selected heater": False,
          "verdict": "FAIL"}),
        ("Q14 wrong: 280 kJ required heat", "Q14",
         "Required heat Q = 280 kJ.",
         {"Required heat": False, "verdict": "FAIL"}),
        ("Q15 wrong: PASS because the final zero is "
         "acceptable", "Q15",
         "PASS because the final zero is acceptable.",
         {"Overall verdict": False, "verdict": "FAIL"}),
        ("Q15 wrong: re-zero before the final reading",
         "Q15", "Re-zero before the final reading.",
         {"Ordered check sequence": False,
          "verdict": "FAIL"}),
        ("Q16 wrong: 0.672 mm increase", "Q16",
         "Delta L = 0.672 mm.",
         {"Length increase": False,
          "verdict": "FAIL"}),
        ("Q16 wrong: compressive thermal stress", "Q16",
         "A compressive thermal stress develops.",
         {"Length increase": False,
          "Final length": False, "verdict": "FAIL"}),
        ("Q17 wrong: 50 kg", "Q17",
         "Attachment unlocking strength: at least "
         "50 kg.",
         {"Minimum unlocking strength": False,
          "verdict": "FAIL"}),
        ("Q17 wrong: every two years", "Q17",
         "Energy-control procedure inspection: every "
         "two years.",
         {"Inspection frequency": False,
          "verdict": "FAIL"}),
        ("Q18 wrong: I = hb^3/12", "Q18",
         "I = hb^3/12.",
         {"Second moment of area": False,
          "verdict": "FAIL"}),
        ("Q18 wrong: the cantilever deflection formula",
         "Q18",
         "Use the cantilever deflection formula.",
         {"Midspan deflection": False,
          "verdict": "FAIL"}),
        ("Q19 wrong: select a 0.250 W resistor", "Q19",
         "Select a 0.250 W resistor.",
         {"Minimum required and selected power ratings": False,
          "verdict": "FAIL"}),
        ("Q19 wrong: use 9.00/R for LED current", "Q19",
         "Use 9.00/R for LED current.",
         {"Selected resistance and current": False,
          "verdict": "FAIL"}),
        ("Q20 wrong: -2.0% error", "Q20",
         "Error: -2.0%.",
         {"Signed indication error": False,
          "verdict": "FAIL"}),
        ("Q20 wrong: stop the pump to end collection",
         "Q20", "Stop the pump to end collection.",
         {"End sequence": False, "verdict": "FAIL"}),
        ("Q21 wrong: 50 deg C", "Q21",
         "T_f = 50 deg C.",
         {"Final temperature": False,
          "verdict": "FAIL"}),
        ("Q21 wrong: 65 deg C", "Q21",
         "T_f = 65 deg C.",
         {"Final temperature": False,
          "verdict": "FAIL"}),
        ("Q22 wrong: baseline within one year", "Q22",
         "Baseline: within one year.",
         {"Baseline deadline": False,
          "verdict": "FAIL"}),
        ("Q22 wrong: retest within 21 days", "Q22",
         "Retest: within 21 days.",
         {"Retest window": False, "verdict": "FAIL"}),
        ("Q23 wrong: each bar carries 15 kN", "Q23",
         "Each bar carries 15 kN.",
         {"Aluminum force": False,
          "Steel force": False, "verdict": "FAIL"}),
        ("Q23 wrong: both bars have the same stress",
         "Q23", "Both bars have the same stress.",
         {"Aluminum tensile stress": False,
          "Steel tensile stress": False,
          "verdict": "FAIL"}),
        ("Q24 wrong: select 200 mm", "Q24",
         "Driven pitch diameter 200 mm.",
         {"Selected driven diameter and ratio": False,
          "verdict": "FAIL"}),
        ("Q24 wrong: output rotates oppositely", "Q24",
         "Output rotates oppositely.",
         {"Output direction": False,
          "verdict": "FAIL"}),
        ("Q24 wrong: 1.33 N m output torque", "Q24",
         "Output torque 1.33 N m.",
         {"Output torque": False, "verdict": "FAIL"}),
        ("Q25 wrong: -1.08 V hysteresis width", "Q25",
         "Width = -1.08 V.",
         {"Hysteresis width": False,
          "verdict": "FAIL"}),
        ("Q25 wrong: pass based only on hysteresis "
         "width", "Q25",
         "Pass based only on hysteresis width.",
         {"Logged verdict": False,
          "verdict": "FAIL"}),
        ("Q25 wrong: disable supply before returning "
         "input to zero", "Q25",
         "Disable the supply before returning the "
         "input to zero.",
         {"Falling sweep and shutdown": False,
          "verdict": "FAIL"}),
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
        ("Q9 selects exactly 10.0 N/mm", "Q9",
         "Selected spring: k = 10.0 N/mm.",
         {"Selected stiffness": True}),
        ("Q9 does not select 8.00 N/mm (extends "
         "too far)", "Q9",
         "Selected spring: k = 8.00 N/mm.",
         {"Selected stiffness": False}),
        ("Q9 does not select 12 N/mm (not the "
         "lowest passing)", "Q9",
         "Selected spring: k = 12 N/mm.",
         {"Selected stiffness": False}),
        ("Q14 selects exactly 1000 W", "Q14",
         "Selected heater: 1000 W.",
         {"Selected heater": True}),
        ("Q14 does not select 750 W (too slow)",
         "Q14", "Selected heater: 750 W.",
         {"Selected heater": False}),
        ("Q14 does not select 1250 W (not the "
         "smallest passing)", "Q14",
         "Selected heater: 1250 W.",
         {"Selected heater": False}),
        ("Q19 selects exactly 330 ohm", "Q19",
         "Selected resistor: 330 ohm; I = 20.0 mA, "
         "passes.",
         {"Selected resistance and current": True}),
        ("Q19 does not select 270 ohm (current "
         "too high)", "Q19",
         "Selected resistor: 270 ohm.",
         {"Selected resistance and current": False}),
        ("Q19 does not select 390 ohm (current "
         "too low)", "Q19",
         "Selected resistor: 390 ohm.",
         {"Selected resistance and current": False}),
        ("Q19 selects exactly the 0.500 W rating",
         "Q19",
         "Required rating >= 0.264 W; select "
         "0.500 W.",
         {"Minimum required and selected power ratings": True}),
        ("Q19 does not select the 0.125 W rating",
         "Q19", "Selected rating: 0.125 W.",
         {"Minimum required and selected power ratings": False}),
        ("Q19 does not select the 0.250 W rating "
         "(below two times dissipation)", "Q19",
         "Selected rating: 0.250 W.",
         {"Minimum required and selected power ratings": False}),
        ("Q24 selects exactly 240 mm", "Q24",
         "Driven pitch diameter 240 mm; ratio 3:1.",
         {"Selected driven diameter and ratio": True}),
        ("Q24 does not select 160 mm (600 rpm)",
         "Q24", "Driven pitch diameter 160 mm.",
         {"Selected driven diameter and ratio": False}),
        ("Q24 does not select 200 mm (600 rpm)",
         "Q24", "Driven pitch diameter 200 mm.",
         {"Selected driven diameter and ratio": False}),
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

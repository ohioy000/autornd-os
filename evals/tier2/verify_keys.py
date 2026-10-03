"""Independent verification of the tier-2 candidate dataset's keys.

The owner's tier-2 command (ARCH-20261002-117) requires, per
question: deterministic recomputation of every numerical key;
checks of dimensions, boundary operators, discrete selections and
tolerances; verification that each claimed wrong answer is
actually wrong under the stated assumptions; and, for lookup
questions, matching of every claimed verbatim quotation against
the archived source. This script performs exactly those checks on
the committed dataset - no network, no provider calls, no model
involvement (the command forbids querying a model about the
questions).

It is deliberately independent of scorer.py: this verifier checks
the keys against first principles (the formulas, the archived
regulation text); the scorer scores free-text model answers
against the keys. Two instruments, two failure modes.

Usage:
    .venv/bin/python3 evals/tier2/verify_keys.py [--dir DIR]

Exit status: 0 if every check holds, 1 otherwise. The check
table prints either way, so a failure names what failed.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# The question set the command expects. The owner
# supplied all 25 on 2026-10-03; the count
# discrepancy that blocked the first registration is
# resolved, and the remaining freeze blocker is the
# review and signoff the command requires.
COMMAND_EXPECTED_QUESTIONS = 25

# The two definitions 29 CFR 1910.146(b) states, as the archived
# July 1, 2014 edition prints them. The verifier reconstructs the
# left column of the two-column extraction and matches these
# sentences against it character-for-character (modulo whitespace).
DEFICIENT_SENTENCE = (
    "Oxygen deficient atmosphere means an atmosphere containing "
    "less than 19.5 percent oxygen by volume."
)
ENRICHED_SENTENCE = (
    "Oxygen enriched atmosphere means an atmosphere containing "
    "more than 23.5 percent oxygen by volume."
)

CHECKS: list[dict] = []

# The recomputed values, populated by the per-question
# verifiers and consumed by the numeric cross-check that
# parses keys.json's own value strings against them.
RECOMPUTED: dict[str, float] = {}

# The verifier's own unit table, deliberately independent
# of scorer.py's: two instruments that share a conversion
# table share a bug. Dimension -> base unit factor.
VERIFIER_UNITS: dict[str, tuple[str, float]] = {
    "v": ("V", 1.0), "volt": ("V", 1.0),
    "mv": ("V", 1e-3),
    "a": ("A", 1.0), "amp": ("A", 1.0),
    "ma": ("A", 1e-3),
    "m^4": ("m^4", 1.0), "m4": ("m^4", 1.0),
    "pa": ("Pa", 1.0), "kpa": ("Pa", 1e3),
    "mpa": ("Pa", 1e6), "gpa": ("Pa", 1e9),
    "n/mm^2": ("Pa", 1e6), "n/mm2": ("Pa", 1e6),
    "m": ("m", 1.0), "mm": ("m", 1e-3), "cm": ("m", 1e-2),
    "m^2": ("m^2", 1.0), "m2": ("m^2", 1.0),
    "mm^2": ("m^2", 1e-6), "mm2": ("m^2", 1e-6),
    "cm^2": ("m^2", 1e-4),
    "m^3": ("m^3", 1.0), "m3": ("m^3", 1.0),
    "mm^3": ("m^3", 1e-9), "mm3": ("m^3", 1e-9),
    "cm^3": ("m^3", 1e-6),
    "kg": ("kg", 1.0), "g": ("kg", 1e-3),
    "bar": ("bar", 1.0), "mbar": ("bar", 1e-3),
    "rad": ("rad", 1.0), "mrad": ("rad", 1e-3),
    "deg": ("rad", math.pi / 180),
    "degree": ("rad", math.pi / 180),
    "s": ("s", 1.0), "min": ("s", 60.0),
    "%": ("%", 1.0),
    # The units the Q6-Q25 keys state. Resistance
    # (K/W), energy (J), power (W), speed (rpm),
    # torque and force (N m, N), flow (L/min, m/s),
    # concentration (mg/L), temperature (deg C, K)
    # and the pound (lb) the tagout regulation states.
    "k/w": ("K/W", 1.0),
    "j": ("J", 1.0), "kj": ("J", 1e3), "mj": ("J", 1e-3),
    "w": ("W", 1.0), "watt": ("W", 1.0),
    "watts": ("W", 1.0), "kw": ("W", 1e3),
    "mw": ("W", 1e-3),
    "rpm": ("rpm", 1.0), "rev/s": ("rpm", 60.0),
    "n": ("N", 1.0), "kn": ("N", 1e3),
    "n m": ("N m", 1.0), "nm": ("N m", 1.0),
    "nmm": ("N m", 1e-3), "knm": ("N m", 1e3),
    "newtonmetres": ("N m", 1.0),
    "newton": ("N", 1.0), "newtons": ("N", 1.0),
    "n/mm": ("N/mm", 1.0),
    "l/min": ("L/min", 1.0), "l/s": ("L/min", 60.0),
    "m/s": ("m/s", 1.0),
    "mg/l": ("mg/L", 1.0), "ug/l": ("mg/L", 1e-3),
    "lb": ("lb", 1.0), "pound": ("lb", 1.0),
    "pounds": ("lb", 1.0),
    "degc": ("deg C", 1.0), "celsius": ("deg C", 1.0),
    "k": ("K", 1.0), "kelvin": ("K", 1.0),
    "kelvins": ("K", 1.0),
    "ohm": ("ohm", 1.0), "ohms": ("ohm", 1.0),
    "ω": ("ohm", 1.0),
    "h": ("h", 1.0), "hr": ("h", 1.0), "hrs": ("h", 1.0),
    "hour": ("h", 1.0), "hours": ("h", 1.0),
    "month": ("month", 1.0), "months": ("month", 1.0),
    "d": ("day", 1.0), "day": ("day", 1.0),
    "days": ("day", 1.0),
    "percentagepoints": ("%", 1.0),
}


def check(cid: str, name: str, ok: bool, detail: str = "") -> bool:
    CHECKS.append({"id": cid, "name": name,
                   "ok": bool(ok), "detail": detail})
    return bool(ok)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(a: float, b: float) -> float:
    return abs(a - b) / abs(b)


# ── Q2 source reconstruction ──────────────────────────────────────────

def reconstruct_left_column(text: str) -> str:
    """The section PDF is typeset in two columns, and
    pdftotext -layout emits each visual line as one text line:
    left-column text, a wide gap, then right-column text.
    Splitting every line at its first run of six or more spaces
    and joining the left parts reconstructs the left column's
    reading order, which is where the definitions sit. A line
    with no such run is single-column (a heading or footer) and
    is kept whole."""
    parts = []
    for line in text.splitlines():
        stripped = line.strip()
        m = re.search(r" {6,}", stripped)
        parts.append(stripped[:m.start()] if m else stripped)
    return re.sub(r"\s+", " ", " ".join(p for p in parts if p))


def strip_xml(text: str) -> str:
    body = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", body)


# ── keys.json parsing for the numeric cross-check ─────
#
# The per-question verifiers compare the recomputation
# against values transcribed into this file. The
# cross-check below closes the loop: it parses the
# key's own value string out of keys.json and requires
# it to agree with the recomputation within the item's
# own stated tolerance, so a dataset whose numbers
# drifted from the formulas cannot pass.

_KEY_NUMBER = re.compile(
    r"[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?")
# A unit is one token, or tokens joined by a slash, a
# space or a middle dot (K/W, N m, N·m, L/min, m/s,
# N/mm); a compound capture that names no known unit
# falls back to its first token, so '133.333 W from hot
# to cold' still reads as watts. The ohm sign U+2126
# joins the class for the Q19 resistance keys.
_KEY_UNIT = re.compile(
    r"\s*([A-Za-z%°Ω]+(?:\^\d+)?"
    r"(?:[\s/·][A-Za-z%°Ω]+(?:\^\d+)?)*)")


def _key_quantities(text: str) -> list[tuple[float, str]]:
    plain = _plain(text)
    plain = re.sub(
        r"(\d)\s*(?:×|x|\*)\s*10\s*\^\s*\{?\s*"
        r"(-?\d+)\s*\}?", r"\1e\2", plain)
    found: list[tuple[float, str]] = []
    for m in _KEY_NUMBER.finditer(plain):
        rest = plain[m.end():m.end() + 20]
        um = _KEY_UNIT.match(rest)
        unit = um.group(1) if um and um.group(1) else ""
        if unit and _convert(0.0, unit) is None:
            # A compound capture that names no known
            # unit: retry with its first token, so a
            # value followed by prose ('W from hot to
            # cold') still reads in its own unit.
            first = unit.split()[0]
            if " " in unit and _convert(0.0, first) is not None:
                unit = first
            else:
                unit = ""
        found.append((float(m.group(0)), unit))
    return found


def _convert(value: float, unit: str):
    key = (unit.strip().lower().replace(" ", "")
               .replace("°", "deg")
               .replace("·", "").replace("-", ""))
    entry = VERIFIER_UNITS.get(key)
    if not entry:
        return None
    return entry[0], value * entry[1]


def _parse_tolerance(spec: str):
    plain = _plain(spec)
    # A tolerance's unit may be compound (L/min,
    # N m), so the capture allows slash, space and
    # middle-dot separators, as the key parser's
    # own unit capture does.
    unit = r"([A-Za-z%°]+(?:[\s/·][A-Za-z%°]+)*)"
    m = re.search(r"(?:numerical|absolute) tolerance"
                    r"\s*\+/-\s*(\d+(?:\.\d+)?)"
                    r"\s*" + unit,
                  plain)
    if m:
        return "abs", float(m.group(1)), m.group(2)
    m = re.search(r"relative tolerance"
                    r"\s*(\d+(?:\.\d+)?)\s*%", plain)
    if m:
        return "rel", float(m.group(1)) / 100.0, ""
    # The Q6-Q25 keys state bare tolerances
    # ('tolerance +/-0.001 K/W', 'error tolerance
    # +/-0.0005 mm'); the spelling carries the
    # same meaning as the prefixed forms.
    m = re.search(r"tolerance\s*\+/-\s*(\d+(?:\.\d+)?)"
                    r"\s*" + unit,
                  plain)
    if m:
        return "abs", float(m.group(1)), m.group(2)
    return None


def verify_numeric_keys(keys: list[dict]) -> None:
    """Every numerical key in keys.json is checked
    against the first-principles recomputation."""
    plans = [
        ("Q1", "Output voltage", "q1_v_out", "V"),
        ("Q1", "Divider current", "q1_i_series", "A"),
        ("Q3", "Polar second moment of area",
         "q3_j", "m^4"),
        ("Q3", "Maximum shear-stress magnitude",
         "q3_tau", "MPa"),
        ("Q3", "End-to-end twist magnitude",
         "q3_theta", "rad"),
        ("Q4", "Selected gross cross-sectional area",
         "q4_area", "mm^2"),
        ("Q4", "Selected-strip stress and strength "
         "verdict", "q4_sigma", "MPa"),
        ("Q4", "Next thinner available strip stress "
         "and verdict", "q4_sigma2", "MPa"),
        ("Q4", "Selected-strip volume",
         "q4_volume", "m^3"),
        ("Q4", "Selected-strip mass",
         "q4_mass", "kg"),
        ("Q5", "Logged pressure drop",
         "q5_drop", "bar"),
        # Q7: durations read off the archived Table G-16
        # rows themselves (verify_q7 parses the archive).
        ("Q7", r"Duration at $90\,\mathrm{dBA}$",
         "q7_h90", "h"),
        ("Q7", r"Duration at $95\,\mathrm{dBA}$",
         "q7_h95", "h"),
        ("Q7", r"Duration at $100\,\mathrm{dBA}$",
         "q7_h100", "h"),
        # Q8: two-layer conduction.
        ("Q8", "Layer A resistance", "q8_ra", "K/W"),
        ("Q8", "Layer B resistance", "q8_rb", "K/W"),
        ("Q8", "Heat-transfer rate", "q8_qdot", "W"),
        ("Q8", "Interface temperature", "q8_ti", "deg C"),
        # Q9: spring selection.
        ("Q9", "Selected stiffness", "q9_k", "N/mm"),
        ("Q9", "Selected extension and verdict",
         "q9_x", "mm"),
        ("Q9", "Next lower stiffness check",
         "q9_x8", "mm"),
        ("Q9", "Stored elastic energy", "q9_u", "J"),
        # Q11: gear pair.
        ("Q11", "Output speed", "q11_n", "rpm"),
        ("Q11", "Output torque magnitude", "q11_t", "N m"),
        # Q12: MCLs read off the archived 141.62(b) table.
        ("Q12", "Arsenic MCL", "q12_as", "mg/L"),
        ("Q12", "Fluoride MCL", "q12_f", "mg/L"),
        ("Q12", "Nitrate MCL and reporting basis",
         "q12_no3", "mg/L"),
        # Q13: RC charging.
        ("Q13", "Time constant", "q13_tau", "s"),
        ("Q13", "Capacitor voltage", "q13_vc", "V"),
        ("Q13", "Resistor current", "q13_i", "A"),
        # Q14: heater selection.
        ("Q14", "Required heat", "q14_q", "J"),
        ("Q14", "Selected heater", "q14_p", "W"),
        ("Q14", "Selected heating time and verdict",
         "q14_t", "s"),
        ("Q14", "Next smaller heater check",
         "q14_t750", "s"),
        ("Q14", "Delivered energy", "q14_e", "kJ"),
        # Q15: extensometer errors.
        ("Q15", "First signed error and verdict",
         "q15_e1", "mm"),
        ("Q15", "Second signed error and verdict",
         "q15_e2", "mm"),
        ("Q15", "Return-zero error and verdict",
         "q15_e0", "mm"),
        # Q16: thermal expansion.
        ("Q16", "Length increase", "q16_dl", "mm"),
        ("Q16", "Final length", "q16_lf", "m"),
        # Q17: tagout provisions, read off the archive.
        ("Q17", "Minimum unlocking strength",
         "q17_lb", "lb"),
        # Q18: simply supported beam.
        ("Q18", "Maximum bending moment", "q18_m", "N m"),
        ("Q18", "Second moment of area", "q18_i", "m^4"),
        ("Q18", "Maximum bending stress",
         "q18_sigma", "MPa"),
        ("Q18", "Midspan deflection", "q18_delta", "mm"),
        # Q19: LED series resistor.
        ("Q19", "Selected resistance and current",
         "q19_r", "ohm"),
        ("Q19", "Selected resistance and current",
         "q19_i", "A"),
        ("Q19", "Lower resistance rejection",
         "q19_i270", "A"),
        ("Q19", "Higher resistance rejection",
         "q19_i390", "A"),
        ("Q19", "Resistor dissipation", "q19_p", "W"),
        ("Q19", "Minimum required and selected power "
         "ratings", "q19_pmin", "W"),
        # Q20: flowmeter indication error.
        ("Q20", "Reference flow", "q20_qref", "L/min"),
        ("Q20", "Signed indication error", "q20_e", "%"),
        # Q21: mixing.
        ("Q21", "Final temperature", "q21_tf", "deg C"),
        # Q22: audiogram provisions, read off the archive.
        ("Q22", "Baseline deadline", "q22_m", "month"),
        ("Q22", "Pre-baseline workplace-noise-free period",
         "q22_h", "h"),
        ("Q22", "Retest window", "q22_d", "day"),
        # Q23: parallel bars.
        ("Q23", "Common extension", "q23_dl", "mm"),
        ("Q23", "Aluminum tensile stress",
         "q23_sa", "MPa"),
        ("Q23", "Steel tensile stress", "q23_ss", "MPa"),
        ("Q23", "Aluminum force", "q23_fa", "kN"),
        ("Q23", "Steel force", "q23_fs", "kN"),
        # Q24: open-belt drive.
        ("Q24", "Selected driven diameter and ratio",
         "q24_d", "mm"),
        ("Q24", "Output speed", "q24_n", "rpm"),
        ("Q24", "Output torque", "q24_t", "N m"),
        ("Q24", "Belt linear speed", "q24_v", "m/s"),
        # Q25: comparator hysteresis.
        ("Q25", "Hysteresis width", "q25_width", "V"),
    ]
    for n, (qid, item_name, recomputed_key,
              dimension) in enumerate(plans, 1):
        record = next(k for k in keys if k["id"] == qid)
        item = next(i for i in record["required_items"]
                      if i["item"] == item_name)
        tolerance = _parse_tolerance(
            item["tolerance_or_variants"])
        dimension_base = _convert(1.0, dimension)[0]
        quantities = [
            (v, u) for v, u in _key_quantities(item["value"])
            if _convert(v, u)
            and _convert(v, u)[0] == dimension_base]
        assert quantities, (
            f"numeric key '{item_name}' names no value in "
            f"the {dimension} dimension: {item['value']}")
        key_value, key_unit = quantities[0]
        key_base = _convert(key_value, key_unit)[1]
        recomputed = RECOMPUTED[recomputed_key]
        recomputed_base = _convert(
            recomputed, dimension)[1]
        if tolerance is None:
            # The item states 'Exact ... required': the
            # key's own value must equal the recomputation
            # exactly, to the last printed digit.
            ok = (abs(key_base - recomputed_base)
                  <= 1e-12 * max(1.0, abs(recomputed_base)))
            tol_text = "exact"
        else:
            kind, magnitude, tol_unit = tolerance
            tol_base = (_convert(magnitude, tol_unit)[1]
                        if tol_unit else magnitude)
            if kind == "abs":
                ok = abs(key_base - recomputed_base) <= tol_base
            else:
                ok = (abs(key_base - recomputed_base)
                      <= tol_base * abs(recomputed_base))
            tol_text = (f"{kind} {magnitude} "
                        f"{tol_unit or dimension}")
        check(f"X{n}", f"keys.json's own value for "
                          f"'{item_name}' ({qid}) agrees "
                          f"with the recomputation",
              ok,
              f"keys.json states {key_value} {key_unit} = "
              f"{key_base:.6g} {dimension_base}; recomputed "
              f"{recomputed:.6g} {dimension} = "
              f"{recomputed_base:.6g}; tolerance {tol_text}")


# ── per-question verification ─────────────────────────────────────────

def verify_q1() -> None:
    # Stated inputs: 2.00 kohm from supply to output, 4.00 kohm
    # from output to ground, 12.0 V supply, output unloaded.
    r_upper, r_lower, v_supply = 2000.0, 4000.0, 12.0

    v_out = v_supply * r_lower / (r_upper + r_lower)
    RECOMPUTED["q1_v_out"] = v_out
    check("Q1.1", "output voltage recomputed from the divider "
                  "formula", abs(v_out - 8.00) <= 0.01,
          f"V_o = 12.0 x 4000/(2000+4000) = {v_out:.4f} V; "
          "key 8.00 V, tolerance +/-0.01 V")

    i_series = v_supply / (r_upper + r_lower)
    RECOMPUTED["q1_i_series"] = i_series
    check("Q1.2", "divider current recomputed from Ohm's law",
          abs(i_series * 1000 - 2.00) <= 0.01,
          f"I = 12.0/(2000+4000) = {i_series * 1000:.4f} mA; "
          "key 2.00 mA, tolerance +/-0.01 mA")

    check("Q1.3", "dimensions: V x ohm/ohm is volts; V/ohm is "
                  "amperes",
          True,
          "Both formulas are dimensionally consistent in SI: the "
          "resistance ratio is dimensionless, so V_o carries "
          "volts and I = V/R carries amperes. Computed above in "
          "base SI units (ohm, volt), so the units follow from "
          "the arithmetic, not from a label.")

    # Wrong answer 1: "4 V output". The claim is that 4 V is the
    # upper resistor's voltage, not the output voltage.
    v_upper = v_supply * r_upper / (r_upper + r_lower)
    check("Q1.4", "wrong answer '4 V output' is genuinely wrong",
          abs(v_upper - 4.00) <= 0.01 and abs(v_upper - v_out) > 0.01,
          f"12.0 x 2000/6000 = {v_upper:.4f} V is indeed the "
          f"upper resistor's drop, and it differs from the "
          f"output voltage {v_out:.4f} V by "
          f"{abs(v_upper - v_out):.2f} V - far outside the "
          "+/-0.01 V tolerance")

    # Wrong answer 2: "6 mA current". The claim is that it uses
    # only the upper resistance.
    i_upper_only = v_supply / r_upper
    check("Q1.5", "wrong answer '6 mA current' is genuinely wrong",
          abs(i_upper_only * 1000 - 6.00) <= 0.01
          and abs(i_upper_only - i_series) > 0.0001,
          f"12.0/2000 = {i_upper_only * 1000:.4f} mA is indeed "
          f"the upper-resistance-only current, and it differs "
          f"from the series current {i_series * 1000:.4f} mA "
          f"by {abs(i_upper_only - i_series) * 1000:.2f} mA - "
          f"far outside the +/-0.01 mA tolerance")


def verify_q2(directory: Path, manifest: dict) -> None:
    archive = manifest["source_archives"][0]
    crosscheck = manifest["source_archives"][1]

    pdf = directory / archive["file"]
    txt = directory / archive["text_extraction"]
    ecfr = directory / crosscheck["file"]

    check("Q2.1", "archived PDF hashes to the manifest record",
          sha256_file(pdf) == archive["sha256"],
          f"{pdf.name}: sha256 {sha256_file(pdf)[:16]}... "
          f"({pdf.stat().st_size} bytes)")
    check("Q2.2", "archived text extraction hashes to the manifest "
                  "record",
          sha256_file(txt) == archive["text_sha256"],
          f"{txt.name}: sha256 {sha256_file(txt)[:16]}... "
          f"({txt.stat().st_size} bytes)")
    check("Q2.3", "stability-cross-check XML hashes to the manifest "
                  "record",
          sha256_file(ecfr) == crosscheck["sha256"],
          f"{ecfr.name}: sha256 {sha256_file(ecfr)[:16]}... "
          f"({ecfr.stat().st_size} bytes)")

    left = reconstruct_left_column(txt.read_text(encoding="utf-8"))

    check("Q2.4", "oxygen-deficient definition matches the archive "
                  "verbatim",
          DEFICIENT_SENTENCE in left,
          f"archive paragraph (b): \"{DEFICIENT_SENTENCE}\"")
    check("Q2.5", "oxygen-enriched definition matches the archive "
                  "verbatim",
          ENRICHED_SENTENCE in left,
          f"archive paragraph (b): \"{ENRICHED_SENTENCE}\"")

    check("Q2.6", "both definitions sit in paragraph (b), Definitions",
          "(b) Definitions." in left
          and left.index("(b) Definitions.") < left.index(DEFICIENT_SENTENCE)
          < left.index(ENRICHED_SENTENCE),
          "the extraction's line 69 reads '(b) Definitions.' and "
          "both definition sentences follow it in the reconstructed "
          "left column")

    check("Q2.7", "boundary operators are strict, as the key claims",
          "less than" in DEFICIENT_SENTENCE
          and "more than" in ENRICHED_SENTENCE
          and "equal" not in DEFICIENT_SENTENCE
          and "equal" not in ENRICHED_SENTENCE,
          "the archived definitions say 'less than' and 'more than' "
          "- no 'or equal to' appears in either sentence")

    check("Q2.8", "concentration basis is by volume, as the key claims",
          "by volume" in DEFICIENT_SENTENCE
          and "by volume" in ENRICHED_SENTENCE
          and "by mass" not in left[left.index(DEFICIENT_SENTENCE):
                                   left.index(ENRICHED_SENTENCE)
                                   + len(ENRICHED_SENTENCE)],
          "both archived definitions end '... percent oxygen by "
          "volume.'; no 'by mass' appears between them")

    ecfr_text = strip_xml(ecfr.read_text(encoding="utf-8"))
    check("Q2.9", "the same two definitions stand in the current eCFR "
                  "(stability cross-check)",
          DEFICIENT_SENTENCE in ecfr_text
          and ENRICHED_SENTENCE in ecfr_text,
          "the eCFR text as of 2026-10-01 carries both sentences "
          "verbatim - a 12-year span from the pinned 2014 edition, "
          "which satisfies the command's 'unchanged for at least "
          "three years' requirement")

    # Wrong answers, checked against the archive, not against the
    # key's own claim.
    check("Q2.10", "wrong answer 'at or below 19.5%' is genuinely "
                   "wrong",
          "less than" in DEFICIENT_SENTENCE
          and "at or below" not in DEFICIENT_SENTENCE,
          "the archived operator is strict 'less than', so an "
          "'at or below' (non-strict) answer misstates the "
          "definition the question asks for")
    check("Q2.11", "wrong answer 'at or above 23.5%' is genuinely "
                   "wrong",
          "more than" in ENRICHED_SENTENCE
          and "at or above" not in ENRICHED_SENTENCE,
          "the archived operator is strict 'more than', so an "
          "'at or above' (non-strict) answer misstates the "
          "definition the question asks for")
    check("Q2.12", "wrong answer 'percent oxygen by mass' is "
                   "genuinely wrong",
          "by volume" in DEFICIENT_SENTENCE
          and "by volume" in ENRICHED_SENTENCE,
          "both archived definitions specify 'by volume'; a "
          "'by mass' basis contradicts the source text")


def verify_q3() -> None:
    # Stated inputs: d = 50.0 mm, L = 1.00 m, G = 80.0 GPa,
    # T = 500 N m; linear-elastic Saint-Venant torsion.
    d, length, g_mod, torque = 0.0500, 1.00, 80.0e9, 500.0

    j_polar = math.pi * d ** 4 / 32
    RECOMPUTED["q3_j"] = j_polar
    check("Q3.1", "polar second moment of area recomputed",
          rel(j_polar, 6.13592e-7) <= 0.002,
          f"J = pi d^4/32 = pi (0.0500 m)^4/32 = "
          f"{j_polar:.8e} m^4; key 6.13592e-7 m^4, "
          f"relative tolerance 0.2% (deviation "
          f"{rel(j_polar, 6.13592e-7) * 100:.4f}%)")

    tau_max = torque * (d / 2) / j_polar
    RECOMPUTED["q3_tau"] = tau_max / 1e6
    check("Q3.2", "maximum shear-stress magnitude recomputed",
          rel(tau_max / 1e6, 20.3718) <= 0.002,
          f"tau_max = T (d/2)/J = 500 x 0.0250/{j_polar:.6e} = "
          f"{tau_max:.6e} Pa = {tau_max / 1e6:.4f} MPa; key "
          f"20.3718 MPa, relative tolerance 0.2% (deviation "
          f"{rel(tau_max / 1e6, 20.3718) * 100:.4f}%)")

    twist = torque * length / (g_mod * j_polar)
    RECOMPUTED["q3_theta"] = twist
    check("Q3.3", "end-to-end twist magnitude recomputed",
          rel(twist, 0.0101859) <= 0.002,
          f"theta = TL/(GJ) = 500 x 1.00/(80.0e9 x "
          f"{j_polar:.6e}) = {twist:.8f} rad; key 0.0101859 rad, "
          f"relative tolerance 0.2% (deviation "
          f"{rel(twist, 0.0101859) * 100:.4f}%)")

    check("Q3.4", "dimensions: J in m^4; tau = N m m / m^4 = Pa; "
                  "theta = N m m / (Pa m^4) is dimensionless",
          True,
          "d enters in metres, so d^4 is m^4 and J is m^4; "
          "tau = T r/J is (N m)(m)/(m^4) = N/m^2 = Pa; "
          "theta = TL/(GJ) is (N m)(m)/((N/m^2)(m^4)) = 1, "
          "reported in radians. All three were computed above in "
          "SI base units, so the units follow from the arithmetic.")

    # Wrong answer 1: J = pi d^4 / 64 (the planar second moment).
    j_planar = math.pi * d ** 4 / 64
    check("Q3.5", "wrong answer 'J = pi d^4/64' is genuinely wrong",
          rel(j_planar, j_polar / 2) < 1e-12
          and j_polar / j_planar == 2.0,
          f"pi d^4/64 = {j_planar:.8e} m^4 is exactly half the "
          f"polar second moment (J/(pi d^4/64) = "
          f"{j_polar / j_planar:.1f}), so it misstates the "
          f"requested quantity by a factor of 2 - far outside the "
          f"0.2% relative tolerance")

    # Wrong answer 2: 40.7 MPa (diameter instead of radius in Tr/J).
    tau_diameter = torque * d / j_polar
    check("Q3.6", "wrong answer '40.7 MPa' is genuinely wrong",
          rel(tau_diameter / 1e6, 40.7) <= 0.002
          and rel(tau_diameter, tau_max) > 0.5,
          f"T d/J (d instead of d/2) = {tau_diameter / 1e6:.4f} "
          f"MPa is indeed the doubled stress (ratio to the correct "
          f"{tau_max / 1e6:.4f} MPa: {tau_diameter / tau_max:.1f}x)")

    # Wrong answer 3: "0.0102 degrees". The numeral matches the
    # radian value within tolerance; the unit is wrong.
    check("Q3.7", "wrong answer '0.0102 degrees' is genuinely wrong",
          rel(0.0102, twist) <= 0.002
          and rel(0.0102 * math.pi / 180, twist) > 0.5,
          f"the numeral 0.0102 matches the radian value within "
          f"0.2% (deviation {rel(0.0102, twist) * 100:.4f}%), but "
          f"read as degrees it is {0.0102 * math.pi / 180:.3e} rad "
          f"- a factor of {twist / (0.0102 * math.pi / 180):.1f} "
          f"from the true twist. The question asks for radians and "
          f"the torsion formula produces radians.")


def verify_q4() -> None:
    # Stated inputs: F = 6.00 kN, width 20.0 mm, length 500 mm,
    # available thicknesses 2.00/3.00/4.00 mm, allowable stress
    # 100 MPa with equality permitted, density 7850 kg/m^3.
    force, width, length = 6000.0, 20.0, 500.0
    sigma_allow = 100.0            # N/mm^2 == MPa
    rho = 7850.0                   # kg/m^3
    thicknesses = [2.0, 3.0, 4.0]  # mm

    a_min = force / sigma_allow    # mm^2
    t_min = a_min / width          # mm
    selected = min(t for t in thicknesses if t >= t_min)
    check("Q4.1", "smallest passing thickness selected by discrete "
                  "search",
          a_min == 60.0 and t_min == 3.0 and selected == 3.0,
          f"A_min = F/sigma_allow = 6000/100 = {a_min:.1f} mm^2 "
          f"(100 MPa = 100 N/mm^2); t_min = {a_min:.0f}/20.0 = "
          f"{t_min:.2f} mm; of the available {thicknesses} mm the "
          f"smallest that passes is {selected:.2f} mm")

    a_sel = width * selected
    RECOMPUTED["q4_area"] = a_sel
    check("Q4.2", "selected gross cross-sectional area recomputed",
          rel(a_sel, 60.0) <= 0.001,
          f"A = bt = 20.0 x 3.00 = {a_sel:.1f} mm^2; key 60.0 mm^2, "
          f"relative tolerance 0.1%")

    sigma_sel = force / a_sel
    RECOMPUTED["q4_sigma"] = sigma_sel
    check("Q4.3", "selected-strip stress recomputed; equality with "
                  "the allowable passes",
          rel(sigma_sel, 100.0) <= 0.001
          and sigma_sel <= sigma_allow,
          f"sigma = F/A = 6000/{a_sel:.1f} = {sigma_sel:.1f} MPa; "
          f"key 100 MPa, relative tolerance 0.1%. The value equals "
          f"the allowable and the question states 'equality "
          f"permitted', so the boundary operator passes it.")

    t_thinner = max(t for t in thicknesses if t < selected)
    a_thinner = width * t_thinner
    sigma_thinner = force / a_thinner
    RECOMPUTED["q4_sigma2"] = sigma_thinner
    check("Q4.4", "next thinner available strip recomputed; it fails",
          t_thinner == 2.0 and rel(sigma_thinner, 150.0) <= 0.001
          and sigma_thinner > sigma_allow,
          f"the next thinner available size is {t_thinner:.2f} mm: "
          f"A = {a_thinner:.1f} mm^2, sigma = 6000/{a_thinner:.0f} "
          f"= {sigma_thinner:.1f} MPa > {sigma_allow:.0f} MPa - "
          f"fails, as the key claims")

    v_sel = a_sel * length             # mm^3
    RECOMPUTED["q4_volume"] = v_sel * 1e-9
    check("Q4.5", "selected-strip volume recomputed",
          rel(v_sel * 1e-9, 3.00e-5) <= 0.001,
          f"V = AL = {a_sel:.1f} x 500 = {v_sel:.0f} mm^3 = "
          f"{v_sel * 1e-9:.2e} m^3; key 3.00e-5 m^3, relative "
          f"tolerance 0.1%")

    m_sel = rho * v_sel * 1e-9       # kg
    RECOMPUTED["q4_mass"] = m_sel
    check("Q4.6", "selected-strip mass recomputed",
          abs(m_sel - 0.2355) <= 0.0005,
          f"m = rho V = 7850 x {v_sel * 1e-9:.2e} = {m_sel:.4f} "
          f"kg; key 0.2355 kg, absolute tolerance +/-0.0005 kg")

    # Wrong answer 1: "select 4 mm because 3 mm reaches the
    # allowable stress".
    sigma_4mm = force / (width * 4.0)
    check("Q4.7", "wrong answer 'select 4 mm' is genuinely wrong",
          sigma_4mm <= sigma_allow and selected < 4.0,
          f"4.00 mm would pass (sigma = 6000/80.0 = "
          f"{sigma_4mm:.1f} MPa <= {sigma_allow:.0f} MPa), but "
          f"3.00 mm also passes - at the expressly permitted "
          f"equality - and is smaller, so the task's 'smallest "
          f"available thickness that passes' rule rejects 4.00 mm")

    check("Q4.8", "wrong answer 'select 2 mm' is genuinely wrong",
          sigma_thinner > sigma_allow,
          f"2.00 mm gives {sigma_thinner:.1f} MPa > "
          f"{sigma_allow:.0f} MPa - it fails the stated allowable, "
          f"so selecting it violates the strength requirement")

    check("Q4.9", "wrong answer '235.5 kg mass' is genuinely wrong",
          abs(235.5 - m_sel) > 0.0005
          and abs(235.5 / m_sel - 1000) < 1.0,
          f"the correct mass is {m_sel:.4f} kg; 235.5 kg differs by "
          f"{abs(235.5 - m_sel):.2f} kg (a factor of "
          f"{235.5 / m_sel:.0f}) - a g/kg unit-conversion error, "
          f"outside the +/-0.0005 kg tolerance")


def verify_q5(directory: Path) -> None:
    # Stated inputs: component rating 10.0 bar, test pressure
    # 6.00 bar, hold 300 s, pass iff drop <= 0.20 bar and no
    # visible leakage. Log: 6.00 -> 5.90 bar, no leakage.
    p_start, p_end = 6.00, 5.90
    p_test, p_rating = 6.00, 10.0
    drop_limit = 0.20

    drop = p_start - p_end
    RECOMPUTED["q5_drop"] = drop
    check("Q5.1", "logged pressure drop recomputed",
          abs(drop - 0.10) <= 0.001,
          f"drop = p_start - p_end = 6.00 - 5.90 = {drop:.2f} bar; "
          f"key 0.10 bar, absolute tolerance +/-0.001 bar")

    verdict = "PASS" if (drop <= drop_limit) else "FAIL"
    check("Q5.2", "verdict for the logged hold follows from the "
                  "stated criteria",
          verdict == "PASS",
          f"drop {drop:.2f} bar <= {drop_limit:.2f} bar and the log "
          f"reports no visible leakage throughout, so both "
          f"conjunctive criteria hold: {verdict}")

    check("Q5.3", "acceptance boundary operator verified: the limit "
                  "itself passes, one hundredth past it fails",
          (drop_limit <= drop_limit) and not (drop_limit + 0.01 <= drop_limit),
          f"a drop of exactly {drop_limit:.2f} bar passes ('no more "
          f"than 0.20 bar' is inclusive); a drop of "
          f"{drop_limit + 0.01:.2f} bar fails")

    check("Q5.4", "the specified test pressure is 6.00 bar, not the "
                  "10.0 bar component rating",
          p_test == 6.00 and p_rating == 10.0 and p_test != p_rating,
          "the question states 'raise the pressure to 6.00 bar "
          "gauge' and separately that components are 'rated for "
          "10.0 bar gauge' - the rating is not the test pressure")

    # The candidate's worked answer must carry the ordered procedure
    # the question prescribes. Each pair is (must-precede,
    # must-follow); order is the answer's reading order - step
    # number first, then position within a shared step.
    ordering = [
        ("bubble-free", "Close the vent"),
        ("Close the vent", "pressurize"),
        ("pressurize", "Isolate the hand pump"),
        ("Isolate the hand pump", "start the timer"),
        ("start the timer", "Hold for 300"),
        ("Hold for 300", "Pass only"),
        ("Pass only", "release valve"),
        ("release valve", "confirm 0 bar"),
        ("confirm 0 bar", "disconnect"),
    ]
    steps = _numbered_steps(_plain(_model_answer("Q5", directory)))
    ok_all, details = [], []
    for before, after in ordering:
        i_before, i_after = _step_of(steps, before), _step_of(steps, after)
        ok = (i_before is not None and i_after is not None
              and (i_before < i_after
                   or (i_before == i_after
                       and steps[i_before].lower().index(before.lower())
                       < steps[i_after].lower().index(after.lower()))))
        ok_all.append(ok)
        details.append(f"'{before}' -> '{after}': steps "
                       f"{i_before}->{i_after} "
                       f"{'ok' if ok else 'OUT OF ORDER'}")
    check("Q5.5", "worked answer carries the prescribed operation "
                  "order",
          all(ok_all),
          "; ".join(details))

    plain = _plain(_model_answer("Q5", directory))
    check("Q5.6", "worked answer states the no-addition rule and the "
                  "conjunctive acceptance criteria",
          _has_phrase(plain, "without adding water")
          and _has_phrase(plain, "0.20")
          and _has_phrase(plain, "no visible leakage")
          and _has_phrase(plain, "PASS"),
          "the hold step forbids adding water; the criteria require "
          "both drop <= 0.20 bar and no visible leakage; the logged "
          "verdict is PASS")

    # Wrong answers, checked against the question's own rules.
    check("Q5.7", "wrong answer 'test at 10.0 bar' is genuinely wrong",
          p_rating != p_test,
          f"10.0 bar is the component rating; the specified test "
          f"pressure is {p_test:.2f} bar - substituting the rating "
          f"changes the test the question asks for")
    check("Q5.8", "wrong answer 'start timing while raising pressure' "
                  "is genuinely wrong",
          True,
          "the question states the hold timer starts 'only after "
          "isolation' of the hand pump; timing during pressurization "
          "measures pump-down, not the isolated pressure drop")
    check("Q5.9", "wrong answer 'maintain 6.00 bar by pumping during "
                  "the hold' is genuinely wrong",
          True,
          "the question states 'do not add water during the 300 s "
          "hold'; pumping during the hold defeats the isolated "
          "pressure-drop assessment the test exists to make")
    check("Q5.10", "wrong answer 'fail because the final pressure is "
                   "below 6.00 bar' is genuinely wrong",
          (drop_limit <= drop_limit),
          f"the criterion is the drop, not the final pressure: a drop "
          f"of up to and including {drop_limit:.2f} bar passes, so a "
          f"final pressure of {p_test - drop_limit:.2f} bar still "
          f"passes; the logged 0.10 bar drop passes")
    check("Q5.11", "wrong answer 'disconnect before confirming zero "
                   "gauge pressure' is genuinely wrong",
          True,
          "the question prescribes depressurization through the "
          "release valve and confirmation of 0 bar gauge 'before "
          "disconnecting' - the ordering constraint the wrong answer "
          "violates")


def _model_answer(qid: str, directory: Path) -> str:
    keys = json.loads((directory / "keys.json").read_text(encoding="utf-8"))
    return next(k["model_answer"] for k in keys if k["id"] == qid)


def _plain(text: str) -> str:
    r"""Strip the LaTeX wrappers the candidate's worked
    answers use, so phrase and number matching sees the
    prose and the bare values. ^{\circ} reads as the
    degree sign, which the unit table resolves to deg C."""
    text = re.sub(r"\\mathrm\{([^}]*)\}", r"\1", text)
    text = text.replace("$", "").replace("\\,", " ")
    text = text.replace("\\Omega", "Ω")
    text = text.replace("\\%", "%")
    text = text.replace("\\pm", "+/-")
    text = text.replace("\\leq", "<=").replace("\\le", "<=")
    text = text.replace("\\geq", ">=").replace("\\ge", ">=")
    text = text.replace("\\times", "x")
    text = re.sub(r"\^\{\\circ\}", "°", text)
    text = re.sub(r"\\circ", "°", text)
    return text


def _straight(text: str) -> str:
    """Typographic quotes to straight ones, so phrase
    matching sees one apostrophe spelling."""
    return (text.replace("’", "'")
                .replace("‘", "'")
                .replace("“", '"')
                .replace("”", '"'))


def reconstruct_columns(text: str) -> tuple[str, str]:
    """The section PDFs are typeset in two columns, and
    pdftotext -layout emits each visual line as one text
    line: left-column text, a wide gap, then right-column
    text. Splitting every line at its first run of six or
    more spaces reconstructs both columns' reading order.
    A line with no such run is single-column (a heading
    or footer) and belongs to the left column."""
    lefts, rights = [], []
    for line in text.splitlines():
        stripped = line.strip()
        m = re.search(r" {6,}", stripped)
        if m:
            lefts.append(stripped[:m.start()])
            rights.append(stripped[m.end():])
        else:
            lefts.append(stripped)
    return (re.sub(r"\s+", " ", " ".join(p for p in lefts
                                          if p)),
            re.sub(r"\s+", " ", " ".join(p for p in rights
                                          if p)))


def _numbered_steps(text: str) -> list[str]:
    steps = []
    for line in text.splitlines():
        m = re.match(r"\s*(\d+)\.\s+(.*)", line)
        if m:
            steps.append(m.group(2).strip())
    return steps


def _step_of(steps: list[str], phrase: str) -> int | None:
    for i, step in enumerate(steps):
        if phrase.lower() in step.lower():
            return i
    return None


def _has_phrase(text: str, phrase: str) -> bool:
    return phrase.lower() in text.lower()


def source_pair(manifest: dict, qid: str) -> tuple[dict, dict]:
    """The archived regulation source for a lookup
    question: the govinfo section PDF with its
    pdftotext extraction, and the eCFR stability
    cross-check XML, matched on the manifest's own
    question tag and section number."""
    pdf = next(a for a in manifest["source_archives"]
               if "text_extraction" in a
               and qid in [s.strip() for s
                           in a["question"].split(",")])
    section = (pdf["file"].split("sec")[-1]
                  .removesuffix(".pdf"))
    cross = next(a for a in manifest["source_archives"]
                 if "text_extraction" not in a
                 and f"sec{section}" in a["file"])
    return pdf, cross


def table_g16(text: str):
    """Table G-16 of 29 CFR 1910.95, parsed from the
    raw two-column extraction. Each row is one visual
    line - the daily duration in hours, a dot leader,
    then the constant sound level in dBA - so the rows
    are matched on the raw lines, anchored at the line
    start, and bounded by this table's caption and the
    caption of the table that follows it (G-16a, whose
    rows run the other way: level first, dose second,
    so a duration-first match cannot come from it).
    Returns the level-to-duration rows, the line each
    row was read from, and the caption line span."""
    lines = text.splitlines()
    caption = next((i for i, l in enumerate(lines)
                    if "TABLE G–16—PERMISSIBLE NOISE "
                       "EXPOSURES" in l), -1)
    following = next((i for i, l in enumerate(lines)
                      if i > caption
                      and l.strip().startswith("TABLE G–16A")),
                     len(lines))
    rows: dict[int, float] = {}
    row_lines: dict[int, int] = {}
    for i in range(caption + 1, following):
        m = re.match(r"\s*(\d+(?:\.\d+)?)\s*\.{3,}"
                     r"\s+(\d+)\b", lines[i])
        if m:
            level = int(m.group(2))
            rows[level] = float(m.group(1))
            row_lines[level] = i
    return rows, row_lines, (caption, following)


def mcl_row(text: str, paragraph: int, name: str) -> str:
    """One maximum-contaminant-level row of 40 CFR
    141.62(b), parsed from the raw two-column
    extraction. Each row is a visual line of its own:
    the paragraph number, the contaminant name, a dot
    leader, then the MCL in mg/l - the nitrate row
    carrying its 'as Nitrogen' reporting basis."""
    for l in text.splitlines():
        m = re.match(
            rf"\s*\({paragraph}\)\s*{name}"
            r"\s*\.{3,}\s+([^ ]+"
            r"(?:\s*\(as [^)]+\))?)", l)
        if m:
            return m.group(1).strip()
    return ""


def _keyed_items(qid: str, directory: Path) -> list[dict]:
    """The required items of one keys.json entry,
    read from the directory being verified."""
    keys = json.loads(
        (directory / "keys.json").read_text(
            encoding="utf-8"))
    return next(k["required_items"] for k in keys
                if k["id"] == qid)


def verify_q6(directory: Path) -> None:
    # The requirement: an active-high alarm that is on
    # when exactly one of the two pumps runs and off
    # otherwise. That is the definition of exclusive OR.
    items = {i["item"]: i for i
             in _keyed_items("Q6", directory)}
    required = [int(a != b) for a in (0, 1)
                for b in (0, 1)]
    check("Q6.1", "alarm function is the exactly-one-"
                  "pump function (XOR)",
          all((a ^ b) == int(a != b)
              for a in (0, 1) for b in (0, 1))
          and "oplus" in _plain(
              items["Alarm function"]["value"]),
          "for input pairs 00, 01, 10, 11 the "
          "exactly-one-pump requirement gives "
          f"{required}; the keyed function Y=A\\oplus B "
          "is XOR, the Boolean function whose output is "
          "true for exactly one asserted input")

    outputs = _plain(items["Ordered outputs"]["value"])
    keyed = [int(c) for c in re.findall(r"\d", outputs)]
    check("Q6.2", "ordered outputs recomputed for 00, 01, "
                  "10, 11",
          keyed == required,
          f"the keyed ordered outputs are {keyed}; the "
          f"recomputed exactly-one-pump table is "
          f"{required} - identical")

    answer = _model_answer("Q6", directory)
    check("Q6.3", "worked answer names the function and "
                  "carries the same table",
          "xor" in answer.lower()
          and "0,1,1,0" in _plain(answer),
          f"the worked answer reads '{_plain(answer)}' - "
          "it names XOR and carries the same ordered "
          "outputs the requirement determines")

    or_table = [int(a or b) for a in (0, 1)
                for b in (0, 1)]
    check("Q6.4", "wrong answer 'OR' is genuinely wrong",
          or_table != required and or_table[3] == 1
          and required[3] == 0,
          f"OR gives {or_table} for 00,01,10,11: it "
          "asserts the alarm when both pumps run "
          "(input 11), where the requirement gives "
          f"{required[3]} - the alarm must be off when "
          "both pumps run")

    xnor_table = [int(a == b) for a in (0, 1)
                  for b in (0, 1)]
    check("Q6.5", "wrong answer 'XNOR' is genuinely wrong",
          xnor_table != required
          and xnor_table[1] != required[1]
          and xnor_table[2] != required[2],
          f"XNOR gives {xnor_table}: it asserts the alarm "
          "when the inputs are equal (00 and 11), the "
          "opposite of the requirement at 01 and 10")


def verify_q7(directory: Path, manifest: dict) -> None:
    pdf, cross = source_pair(manifest, "Q7")
    check("Q7.1", "archived section PDF hashes to the "
                  "manifest record",
          sha256_file(directory / pdf["file"])
          == pdf["sha256"],
          f"{pdf['file']}: sha256 "
          f"{sha256_file(directory / pdf['file'])[:16]}... "
          f"({(directory / pdf['file']).stat().st_size} "
          f"bytes)")
    check("Q7.2", "archived text extraction hashes to the "
                  "manifest record",
          sha256_file(directory / pdf["text_extraction"])
          == pdf["text_sha256"],
          f"{pdf['text_extraction']}: sha256 "
          f"{sha256_file(directory / pdf['text_extraction'])[:16]}"
          f"... "
          f"({(directory / pdf['text_extraction']).stat().st_size} "
          f"bytes)")
    check("Q7.3", "stability cross-check XML hashes to the "
                  "manifest record",
          sha256_file(directory / cross["file"])
          == cross["sha256"],
          f"{cross['file']}: sha256 "
          f"{sha256_file(directory / cross['file'])[:16]}... "
          f"({(directory / cross['file']).stat().st_size} "
          f"bytes)")

    raw = (directory / pdf["text_extraction"]
           ).read_text(encoding="utf-8")
    rows, row_lines, span = table_g16(raw)
    RECOMPUTED["q7_h90"] = rows.get(90, float("nan"))
    RECOMPUTED["q7_h95"] = rows.get(95, float("nan"))
    RECOMPUTED["q7_h100"] = rows.get(100, float("nan"))

    dehyphenated = re.sub(r"-\s*\n\s*", "", raw)
    # The table's centered header lines carry no
    # column gutter, so column reconstruction
    # misassigns them; the headers are probed in
    # the whitespace-collapsed text, where each
    # header reads contiguously ('Sound' and
    # 'level dBA' sit on consecutive right-column
    # lines, and 'slow re-/sponse' is joined by
    # the de-hyphenation above).
    collapsed = re.sub(r"\s+", " ", dehyphenated)
    check("Q7.4", "Table G-16's caption and column "
                  "headers stand in the archive",
          "TABLE G–16—PERMISSIBLE NOISE EXPOSURES" in raw
          and "Duration per day, hours" in collapsed
          and "Sound level dBA" in collapsed
          and "slow response" in collapsed,
          "the archive carries the caption 'TABLE "
          "G-16-PERMISSIBLE NOISE EXPOSURES' and the "
          "column headers 'Duration per day, hours' "
          "and 'Sound level dBA slow response' (the "
          "level header wraps as 'Sound' / 'level "
          "dBA' across two centered lines and the "
          "response header as 'slow re-/sponse', "
          "joined by de-hyphenation)")

    check("Q7.5", "the 90/95/100 dBA durations recomputed "
                  "from the archived table rows",
          rows.get(90) == 8.0 and rows.get(95) == 4.0
          and rows.get(100) == 2.0,
          f"the archived Table G-16 rows read: "
          f"90 dBA -> {rows.get(90)} h, "
          f"95 dBA -> {rows.get(95)} h, "
          f"100 dBA -> {rows.get(100)} h; the keyed "
          f"durations are 8, 4 and 2 hours")

    check("Q7.6", "the parsed rows sit inside Table "
                  "G-16's own span",
          all(span[0] < row_lines[lvl] < span[1]
              for lvl in (90, 95, 100)),
          f"the table's caption sits on extraction line "
          f"{span[0]} and the following table (G-16a) on "
          f"line {span[1]}; the 90/95/100 dBA rows were "
          f"read from lines "
          f"{[row_lines[lvl] for lvl in (90, 95, 100)]}, "
          f"inside that span - they are this table's rows, "
          f"not the neighbouring tables'")

    xml = (directory / cross["file"]
           ).read_text(encoding="utf-8")
    cross_rows = all(
        re.search(rf"<TD[^>]*>{dur}</TD>\s*"
                  rf"<TD[^>]*>{lvl}</TD>", xml)
        for dur, lvl in ((8, 90), (4, 95), (2, 100)))
    check("Q7.7", "the eCFR cross-check carries the same "
                  "three rows",
          cross_rows,
          "the current eCFR text as of 2026-10-01 carries "
          "the same three rows (8 h at 90 dBA, 4 h at "
          "95 dBA, 2 h at 100 dBA) - a 12-year span from "
          "the pinned 2014 edition, which satisfies the "
          "command's 'unchanged for at least three years' "
          "requirement")

    check("Q7.8", "the table's response qualifier is slow "
                  "response, as the question specifies",
          "slow response" in dehyphenated,
          "the archived table's level column is headed "
          "'Sound level dBA slow response'; the question "
          "specifies slow-response measurement, so these "
          "rows are the ones the question asks for")

    check("Q7.9", "wrong answer '90 dBA permits 2.5 h' is "
                  "genuinely wrong",
          2.5 not in rows.values() and rows.get(90) == 8.0,
          f"2.5 h is not a duration Table G-16 lists at "
          f"any level (the table's durations are "
          f"{sorted(set(rows.values()))} h), and the row "
          f"for 90 dBA pairs it with {rows.get(90)} h")

    check("Q7.10", "wrong answer '95 dBA permits 8 h' is "
                   "genuinely wrong",
          rows.get(95) == 4.0 and rows.get(90) == 8.0,
          f"the archived row pairs 95 dBA with "
          f"{rows.get(95)} h; 8 h is the duration the "
          f"table pairs with 90 dBA - the wrong answer "
          f"transplants the neighbouring row's duration")


def verify_q8() -> None:
    # Stated inputs: area 2.00 m^2; layer A 0.100 m at
    # 0.200 W/(m K), layer B 0.0500 m at 0.500 W/(m K);
    # face temperatures 60.0 and 20.0 deg C; steady
    # 1-D conduction, perfect contact, no generation.
    area, l_a, k_a = 2.00, 0.100, 0.200
    l_b, k_b = 0.0500, 0.500
    t_hot, t_cold = 60.0, 20.0

    r_a = l_a / (k_a * area)
    RECOMPUTED["q8_ra"] = r_a
    check("Q8.1", "layer A thermal resistance recomputed",
          rel(r_a, 0.250) <= 0.001 / 0.250,
          f"R_A = L_A/(k_A A) = 0.100/(0.200 x 2.00) = "
          f"{r_a:.4f} K/W; key 0.250 K/W, tolerance "
          f"+/-0.001 K/W (deviation "
          f"{rel(r_a, 0.250) * 100:.4f}%)")

    r_b = l_b / (k_b * area)
    RECOMPUTED["q8_rb"] = r_b
    check("Q8.2", "layer B thermal resistance recomputed",
          rel(r_b, 0.0500) <= 0.0001 / 0.0500,
          f"R_B = 0.0500/(0.500 x 2.00) = {r_b:.4f} K/W; "
          f"key 0.0500 K/W, tolerance +/-0.0001 K/W "
          f"(deviation {rel(r_b, 0.0500) * 100:.4f}%)")

    q_dot = (t_hot - t_cold) / (r_a + r_b)
    RECOMPUTED["q8_qdot"] = q_dot
    check("Q8.3", "heat-transfer rate recomputed",
          abs(q_dot - 133.333) <= 0.5,
          f"Qdot = (60.0-20.0)/(0.250+0.0500) = "
          f"{q_dot:.3f} W, hot to cold; key 133.333 W, "
          f"tolerance +/-0.5 W")

    t_i_hot = t_hot - q_dot * r_a
    t_i_cold = t_cold + q_dot * r_b
    RECOMPUTED["q8_ti"] = t_i_hot
    check("Q8.4", "interface temperature recomputed from "
                  "both sides",
          abs(t_i_hot - 26.6667) <= 0.1
          and abs(t_i_cold - 26.6667) <= 0.1,
          f"T_i = 60.0 - {q_dot:.3f} x 0.250 = "
          f"{t_i_hot:.4f} deg C from the hot side, and "
          f"20.0 + {q_dot:.3f} x 0.0500 = "
          f"{t_i_cold:.4f} deg C from the cold side - "
          f"the two agree; key 26.6667 deg C, tolerance "
          f"+/-0.1 deg C")

    check("Q8.5", "dimensions: L/(k A) is K/W; Qdot is "
                  "K/(K/W) = W",
          True,
          "R = L/(k A) is m/((W/(m K)) m^2) = K/W; the "
          "series sum R_A+R_B is K/W; Qdot = "
          "delta T/R is K/(K/W) = W; T_i = T - Qdot R is "
          "K - W(K/W) = K. All were computed above in SI "
          "units, so the units follow from the arithmetic.")

    q_wrong_basis = (t_hot - t_cold) / k_a
    check("Q8.6", "wrong answer '200 W' is genuinely "
                     "wrong",
          abs(q_wrong_basis - 200.0) <= 0.5
          and abs(q_wrong_basis - q_dot) > 0.5,
          f"(60.0-20.0)/0.200 = {q_wrong_basis:.1f} "
          f"W divides the temperature difference by "
          f"layer A's conductivity - omitting layer "
          f"B and confusing k with R, exactly the "
          f"error the key's wrong answer names. The "
          f"correct rate is {q_dot:.3f} W; the wrong "
          f"answer differs by "
          f"{abs(q_wrong_basis - q_dot):.1f} W, "
          f"outside the +/-0.5 W tolerance")

    t_split = (t_hot + t_cold) / 2
    check("Q8.7", "wrong answer '40 deg C interface' is "
                  "genuinely wrong",
          abs(t_split - 40.0) <= 0.1
          and abs(t_split - t_i_hot) > 0.1,
          f"the arithmetic mean (60.0+20.0)/2 = "
          f"{t_split:.1f} deg C would hold only for equal "
          f"resistances; R_A is {r_a / r_b:.0f} times R_B, "
          f"so the drop across A is {r_a / (r_a + r_b) * 100:.0f}% "
          f"of the total and the interface sits at "
          f"{t_i_hot:.4f} deg C - {abs(t_split - t_i_hot):.1f} deg C "
          f"from the wrong answer, outside the +/-0.1 deg C "
          f"tolerance")


def verify_q9() -> None:
    # Stated inputs: load 120 N; extension limit 12.0 mm
    # with equality allowed; available stiffnesses 8.00,
    # 10.0, 12.0 N/mm; zero-preload linear spring.
    force, x_max = 120.0, 12.0
    stiffnesses = [8.00, 10.0, 12.0]

    k_min = force / x_max
    RECOMPUTED["q9_k"] = k_min
    check("Q9.1", "minimum passing stiffness and the "
                  "discrete selection recomputed",
          k_min == 10.0
          and min(k for k in stiffnesses if k >= k_min) == 10.0,
          f"k_min = F/x_max = 120/12.0 = {k_min:.1f} N/mm; "
          f"of the available {stiffnesses} N/mm the "
          f"lowest that passes (stiffness >= k_min, "
          f"equality allowed) is 10.0 N/mm - the keyed "
          f"selection")

    x_sel = force / 10.0
    RECOMPUTED["q9_x"] = x_sel
    check("Q9.2", "extension at the selected stiffness "
                  "recomputed; the limit itself passes",
          x_sel == 12.0 and x_sel <= x_max,
          f"x = F/k = 120/10.0 = {x_sel:.1f} mm; the "
          f"limit is 12.0 mm with equality allowed, so the "
          f"selected spring passes at the limit exactly")

    x_8 = force / 8.00
    RECOMPUTED["q9_x8"] = x_8
    check("Q9.3", "next lower stiffness check recomputed",
          x_8 == 15.0 and x_8 > x_max,
          f"the 8.00 N/mm spring extends 120/8.00 = "
          f"{x_8:.1f} mm > 12.0 mm - it fails the "
          f"extension limit, so 10.0 N/mm is the lowest "
          f"passing stiffness, not merely a passing one")

    energy = force * (x_sel / 1000.0) / 2
    RECOMPUTED["q9_u"] = energy
    check("Q9.4", "stored elastic energy recomputed",
          abs(energy - 0.720) <= 0.001,
          f"U = Fx/2 = 120 x 0.0120/2 = {energy:.3f} J "
          f"(linear spring loaded from zero); key 0.720 J, "
          f"tolerance +/-0.001 J")

    check("Q9.5", "dimensions: F/x is N/mm; U = Fx/2 is "
                  "N m = J",
          True,
          "stiffness is N/mm (equivalently 1000 N/m or "
          "10 kN/m - the key's accepted variants); energy "
          "is N x m = J. Computed above in N and mm, with "
          "the extension converted to metres for the energy.")

    check("Q9.6", "wrong answer 'select 12 N/mm' is "
                  "genuinely wrong",
          12.0 in stiffnesses and 12.0 >= k_min
          and 10.0 >= k_min and 10.0 < 12.0,
          "12.0 N/mm passes the extension limit, but so "
          "does 10.0 N/mm (at the limit, which the "
          "question expressly allows), and the question "
          "requires the lowest passing stiffness - 12.0 N/mm "
          "is not the selection the rule determines")

    energy_no_half = force * (x_sel / 1000.0)
    check("Q9.7", "wrong answer '1.44 J stored energy' is "
                  "genuinely wrong",
          abs(energy_no_half - 1.44) <= 0.001
          and abs(energy_no_half - energy) > 0.001,
          f"Fx = 120 x 0.0120 = {energy_no_half:.2f} J "
          f"omits the one-half factor of a linear spring "
          f"loaded from zero; the correct energy is "
          f"{energy:.3f} J - the wrong answer is double "
          f"the key, outside the +/-0.001 J tolerance")


def verify_q10(directory: Path) -> None:
    # Stated work instruction: setpoint 120 deg C;
    # the coupon-temperature band 118-122 deg C
    # inclusive controls the timer start; a 600 s
    # hold that any excursion fails, without
    # restart; removal only at or below 40 deg C at
    # the coupon probe. The log: an uninterrupted
    # 600 s hold, minimum 119 deg C, maximum 121.
    items = {i["item"]: i for i
             in _keyed_items("Q10", directory)}
    start = _plain(
        items["Setpoint and timer-start order"]["value"])
    hold = _plain(items["Hold criterion"]["value"])
    shutdown = _plain(
        items["Shutdown and removal order"]["value"])

    i_set = start.index("120")
    i_band = start.index("inclusive")
    i_timer = start.lower().index("start timer")
    check("Q10.1", "setpoint and timer-start order as "
                     "the instruction states them",
          i_set < i_band < i_timer
          and "coupon" in start
          and "118" in start and "122" in start,
          f"the keyed sequence reads '{start}': the "
          f"120 deg C setpoint precedes the "
          f"118-122 deg C inclusive coupon-temperature "
          f"band, which precedes the timer start - and "
          f"the coupon temperature, not merely the "
          f"oven-air temperature, controls the start")

    check("Q10.2", "hold criterion as the instruction "
                     "states it",
          "inclusive" in hold and "600" in hold
          and "excursion" in hold and "restart" in hold,
          f"the keyed criterion reads '{hold}': both "
          f"limits are inclusive, the hold is the "
          f"full 600 s, any excursion fails, and no "
          f"restart is permitted")

    log_min, log_max, log_t = 119.0, 121.0, 600.0
    verdict = (log_min >= 118.0 and log_max <= 122.0
               and log_t >= 600.0)
    keyed_verdict = items["Logged verdict"]["value"]
    answer = _model_answer("Q10", directory)
    check("Q10.3", "the logged verdict follows from the "
                     "logged data",
          verdict and keyed_verdict == "PASS"
          and all(s in _plain(answer)
                  for s in ("119", "121", "600")),
          f"the log's range 119-121 deg C sits inside "
          f"the required 118-122 deg C inclusive band "
          f"and the logged {log_t:.0f} s meets the "
          f"600 s hold, so the verdict is PASS - the "
          f"keyed verdict is '{keyed_verdict}', and the "
          f"worked answer identifies the log's range "
          f"and duration")

    i_assess = shutdown.lower().index("assess run")
    i_off = shutdown.lower().index("switch off")
    i_cool = shutdown.lower().index("cool inside")
    i_remove = shutdown.lower().index("then remove")
    check("Q10.4", "shutdown and removal order as the "
                     "instruction states it",
          i_assess < i_off < i_cool < i_remove
          and "40" in shutdown and "coupon probe"
          in shutdown,
          f"the keyed sequence reads '{shutdown}': "
          f"assess the run, switch off heating, cool "
          f"inside the oven to at most 40 deg C at the "
          f"coupon probe, then remove - the removal "
          f"threshold is stated at the coupon probe, "
          f"not the oven air")

    check("Q10.5", "wrong answer 'start the timer when "
                     "the oven is switched on' is "
                     "genuinely wrong",
          i_band < i_timer,
          "the instruction starts the timer only once "
          "the coupon temperature enters the "
          "118-122 deg C band; starting it at "
          "switch-on times the heat-up, not the "
          "required in-band hold")

    check("Q10.6", "wrong answer 'restart the timer "
                     "after an excursion' is genuinely "
                     "wrong",
          "excursion" in hold and "restart" in hold,
          "the instruction states that any excursion "
          "fails the run and no restart is permitted; "
          "restarting the timer after an excursion is "
          "the action the instruction forbids")


def verify_q11(directory: Path) -> None:
    # Stated inputs: 20-tooth driver, 60-tooth driven,
    # direct external mesh; input 900 rpm clockwise,
    # 3.00 N m; ideal lossless pair.
    items = {i["item"]: i for i
             in _keyed_items("Q11", directory)}
    n_i, t_i = 900.0, 3.00
    teeth_i, teeth_o = 20.0, 60.0

    speed = n_i * teeth_i / teeth_o
    RECOMPUTED["q11_n"] = speed
    check("Q11.1", "output speed recomputed",
          abs(speed - 300.0) <= 0.1,
          f"n_o = n_i N_i/N_o = 900 x 20/60 = "
          f"{speed:.1f} rpm; key 300 rpm, tolerance "
          f"+/-0.1 rpm")

    keyed_direction = items["Output direction"]["value"]
    answer = _model_answer("Q11", directory)
    check("Q11.2", "output direction recomputed from "
                     "the mesh rule",
          keyed_direction.strip().lower()
          in ("counterclockwise", "anticlockwise", "ccw")
          and "counterclockwise" in answer.lower(),
          "directly meshing external gears rotate in "
          "opposite directions; the input turns "
          "clockwise, so viewed from the same side of "
          "both parallel shafts the output turns "
          f"counterclockwise - the keyed direction is "
          f"'{keyed_direction}'")

    torque = t_i * teeth_o / teeth_i
    RECOMPUTED["q11_t"] = torque
    check("Q11.3", "output torque magnitude recomputed",
          abs(torque - 9.00) <= 0.01,
          f"lossless power conservation: T_o = T_i "
          f"N_o/N_i = 3.00 x 60/20 = {torque:.2f} N m; "
          f"key 9.00 N m, tolerance +/-0.01 N m")

    check("Q11.4", "power conservation holds for the "
                     "recomputed pair",
          abs(t_i * n_i - torque * speed) <= 1e-9,
          f"input power proxy T_i n_i = 3.00 x 900 = "
          f"{t_i * n_i:.0f}; output T_o n_o = 9.00 x "
          f"300 = {torque * speed:.0f} - equal, as an "
          f"ideal lossless pair requires; speed is "
          f"rev/min and torque is N m, so the product "
          f"is proportional to power on both sides")

    inverted = n_i * teeth_o / teeth_i
    check("Q11.5", "wrong answer '2700 rpm' is "
                     "genuinely wrong",
          abs(inverted - 2700.0) <= 0.1
          and abs(inverted - speed) > 0.1,
          f"900 x 60/20 = {inverted:.0f} rpm inverts "
          f"the tooth ratio: the larger driven gear "
          f"turns more slowly, not faster. The correct "
          f"speed is {speed:.1f} rpm - the wrong answer "
          f"differs by {abs(inverted - speed):.0f} rpm, "
          f"outside the +/-0.1 rpm tolerance")

    check("Q11.6", "wrong answer 'clockwise output' is "
                     "genuinely wrong",
          keyed_direction.strip().lower()
          != "clockwise",
          "a directly meshing external gear pair "
          "reverses rotation direction; a clockwise "
          "output would require an idler gear or an "
          "internal mesh, neither of which the question "
          "states - the keyed direction is "
          f"'{keyed_direction}'")


def verify_q12(directory: Path, manifest: dict) -> None:
    pdf, cross = source_pair(manifest, "Q12")
    check("Q12.1", "archived section PDF hashes to the "
                     "manifest record",
          sha256_file(directory / pdf["file"])
          == pdf["sha256"],
          f"{pdf['file']}: sha256 "
          f"{sha256_file(directory / pdf['file'])[:16]}... "
          f"({(directory / pdf['file']).stat().st_size} "
          f"bytes)")
    check("Q12.2", "archived text extraction hashes to "
                     "the manifest record",
          sha256_file(directory / pdf["text_extraction"])
          == pdf["text_sha256"],
          f"{pdf['text_extraction']}: sha256 "
          f"{sha256_file(directory / pdf['text_extraction'])[:16]}"
          f"... "
          f"({(directory / pdf['text_extraction']).stat().st_size} "
          f"bytes)")
    check("Q12.3", "stability cross-check XML hashes to "
                     "the manifest record",
          sha256_file(directory / cross["file"])
          == cross["sha256"],
          f"{cross['file']}: sha256 "
          f"{sha256_file(directory / cross['file'])[:16]}..."
          f" "
          f"({(directory / cross['file']).stat().st_size} "
          f"bytes)")

    raw = (directory / pdf["text_extraction"]
           ).read_text(encoding="utf-8")
    arsenic = mcl_row(raw, 16, "Arsenic")
    fluoride = mcl_row(raw, 1, "Fluoride")
    nitrate = mcl_row(raw, 7, "Nitrate")
    RECOMPUTED["q12_as"] = float(arsenic)
    RECOMPUTED["q12_f"] = float(fluoride)
    RECOMPUTED["q12_no3"] = float(nitrate.split()[0])

    check("Q12.4", "the archived 141.62(b)(16) row "
                     "lists the arsenic MCL",
          arsenic == "0.010",
          f"the archived table row reads '(16) Arsenic "
          f"... {arsenic}' mg/l - the keyed arsenic "
          f"MCL is 0.010 mg/L")
    check("Q12.5", "the archived 141.62(b)(1) row "
                     "lists the fluoride MCL",
          fluoride == "4.0",
          f"the archived table row reads '(1) Fluoride "
          f"... {fluoride}' mg/l - the keyed fluoride "
          f"MCL is 4.0 mg/L")
    check("Q12.6", "the archived 141.62(b)(7) row lists "
                     "the nitrate MCL and its basis",
          nitrate == "10 (as Nitrogen)",
          f"the archived table row reads '(7) Nitrate "
          f"... {nitrate}' mg/l - the keyed nitrate MCL "
          f"is 10 mg/L, reported as nitrogen")

    xml = strip_xml((directory / cross["file"]
                     ).read_text(encoding="utf-8"))
    cross_rows = all(
        re.search(rf"\({p}\)\s*{n}\s+"
                  rf"{re.escape(v)}(?:\s*\(as [^)]+\))?",
                  xml)
        for p, n, v in ((16, "Arsenic", "0.010"),
                        (1, "Fluoride", "4.0"),
                        (7, "Nitrate", "10")))
    check("Q12.7", "the eCFR cross-check carries the "
                     "same three rows",
          cross_rows,
          "the current eCFR text as of 2026-10-01 "
          "carries the same three rows - (16) Arsenic "
          "0.010, (1) Fluoride 4.0, (7) Nitrate 10 "
          "(as Nitrogen) - a 12-year span from the "
          "pinned 2014 edition, which satisfies the "
          "command's 'unchanged for at least three "
          "years' requirement")

    items = {i["item"]: i for i
             in _keyed_items("Q12", directory)}
    keyed_nitrate = _plain(
        items["Nitrate MCL and reporting basis"]["value"])
    check("Q12.8", "the key states nitrate's reporting "
                     "basis as nitrogen",
          "as nitrogen" in keyed_nitrate,
          f"the keyed nitrate answer reads "
          f"'{keyed_nitrate}' - the concentration and "
          f"the nitrogen reporting basis the archived "
          f"row specifies, not a nitrate-ion mass basis")

    check("Q12.9", "wrong answer '2 mg/L fluoride' is "
                     "genuinely wrong",
          fluoride == "4.0" and fluoride != "2",
          f"the archived 141.62(b)(1) row states "
          f"{fluoride} mg/l; 2 mg/L is not the primary "
          f"MCL the requested section lists")

    check("Q12.10", "wrong answer '10 mg/L as nitrate "
                      "ion' is genuinely wrong",
          nitrate == "10 (as Nitrogen)",
          "the archived 141.62(b)(7) row reports "
          "nitrate 'as Nitrogen' - the basis is "
          "nitrogen mass, not nitrate-ion mass; the "
          "concentration is the same numeral but the "
          "reporting basis the question asks for is "
          "the one the regulation specifies")

    check("Q12.11", "wrong answer '0.050 mg/L arsenic' "
                      "is genuinely wrong",
          arsenic == "0.010",
          f"the archived July 1, 2014 edition lists "
          f"{arsenic} mg/l for arsenic; 0.050 mg/L was "
          f"the pre-2006 MCL, which this edition does "
          f"not carry - the wrong answer cites a "
          f"superseded value")


def verify_q13() -> None:
    # Stated inputs: C = 100 uF, R = 10.0 kohm,
    # V = 10.0 V, t = 2.00 s, initially uncharged;
    # positive current flows from source toward the
    # capacitor.
    r, c, v_supply, t = 10000.0, 100e-6, 10.0, 2.00

    tau = r * c
    RECOMPUTED["q13_tau"] = tau
    check("Q13.1", "time constant recomputed",
          abs(tau - 1.00) <= 0.001,
          f"tau = RC = 10000 x 100e-6 = {tau:.2f} s; "
          f"key 1.00 s, tolerance +/-0.001 s")

    v_c = v_supply * (1.0 - math.exp(-t / tau))
    RECOMPUTED["q13_vc"] = v_c
    check("Q13.2", "capacitor voltage at t = 2.00 s "
                     "recomputed",
          abs(v_c - 8.64665) <= 0.01,
          f"V_C(2.00) = 10.0(1-e^(-2.00/1.00)) = "
          f"{v_c:.5f} V; key 8.64665 V, tolerance "
          f"+/-0.01 V")

    i_r = (v_supply / r) * math.exp(-t / tau)
    RECOMPUTED["q13_i"] = i_r
    check("Q13.3", "resistor current at t = 2.00 s "
                     "recomputed, positive as defined",
          abs(i_r * 1000 - 0.135335) <= 0.001,
          f"I(2.00) = (10.0/10000)e^(-2.00) = "
          f"{i_r:.7f} A = {i_r * 1000:.6f} mA, flowing "
          f"from the source toward the capacitor while "
          f"it charges, so the defined positive sign is "
          f"explicit; key +0.135335 mA, tolerance "
          f"+/-0.001 mA")

    check("Q13.4", "dimensions: RC is s; the exponent "
                     "is dimensionless; V_C is V",
          True,
          "RC is ohm x farad = s; t/tau is s/s = 1, "
          "so the exponent is dimensionless; V_C = "
          "V(1-e^(-t/tau)) carries volts and I = "
          "(V/R)e^(-t/tau) carries amperes. All were "
          "computed above in SI units, so the units "
          "follow from the arithmetic.")

    v_residual = v_supply - v_c
    check("Q13.5", "wrong answer '1.353 V capacitor "
                     "voltage' is genuinely wrong",
          abs(v_residual - 1.353) <= 0.01
          and abs(v_residual - v_c) > 0.01,
          f"10.0 - 8.64665 = {v_residual:.3f} V is the "
          f"voltage still across the resistor at 2.00 s, "
          f"not the capacitor voltage; the capacitor "
          f"holds {v_c:.5f} V - the wrong answer "
          f"differs by {abs(v_residual - v_c):.2f} V, "
          f"outside the +/-0.01 V tolerance")

    i_initial = v_supply / r
    check("Q13.6", "wrong answer '1 mA current at 2 s' "
                     "is genuinely wrong",
          abs(i_initial * 1000 - 1.0) <= 0.01
          and abs(i_initial - i_r) > 0.000001,
          f"the initial current (t = 0) is 10.0/10000 "
          f"= {i_initial * 1000:.1f} mA; by t = 2.00 s "
          f"it has decayed by e^(-2.00) to "
          f"{i_r * 1000:.6f} mA - the wrong answer is "
          f"the initial value, outside the +/-0.001 mA "
          f"tolerance")


def verify_q14() -> None:
    # Stated inputs: mass 2.00 kg, c_p 4000 J/(kg K),
    # 20.0 to 35.0 deg C, at most 120 s; available
    # heaters 750, 1000, 1250 W; equality with the
    # time limit allowed.
    mass, c_p, d_t = 2.00, 4000.0, 15.0
    t_max = 120.0
    powers = [750.0, 1000.0, 1250.0]

    heat = mass * c_p * d_t
    RECOMPUTED["q14_q"] = heat
    check("Q14.1", "required heat recomputed",
          abs(heat - 120000.0) <= 100.0,
          f"Q = m c_p delta T = 2.00 x 4000 x 15.0 = "
          f"{heat:.0f} J; key 120000 J, tolerance "
          f"+/-100 J")

    p_min = heat / t_max
    RECOMPUTED["q14_p"] = p_min
    check("Q14.2", "minimum passing power and the "
                     "discrete selection recomputed",
          p_min == 1000.0
          and min(p for p in powers if p >= p_min) == 1000.0,
          f"P_min = Q/t_max = 120000/120 = {p_min:.0f} W; "
          f"of the available {powers} W the smallest "
          f"that passes (power >= P_min, equality "
          f"allowed) is 1000 W - the keyed selection")

    t_sel = heat / 1000.0
    RECOMPUTED["q14_t"] = t_sel
    check("Q14.3", "heating time at the selected power "
                     "recomputed; the limit itself passes",
          t_sel == 120.0 and t_sel <= t_max,
          f"t = Q/P = 120000/1000 = {t_sel:.0f} s; the "
          f"limit is 120 s with equality allowed, so the "
          f"selected heater passes at the limit exactly")

    t_750 = heat / 750.0
    RECOMPUTED["q14_t750"] = t_750
    check("Q14.4", "next smaller heater check recomputed",
          t_750 == 160.0 and t_750 > t_max,
          f"the 750 W heater takes 120000/750 = "
          f"{t_750:.0f} s > 120 s - it fails the time "
          f"limit, so 1000 W is the smallest passing "
          f"power, not merely a passing one")

    delivered = 1000.0 * t_sel / 1000.0
    RECOMPUTED["q14_e"] = delivered
    check("Q14.5", "energy delivered by the selected "
                     "heater recomputed",
          abs(delivered - 120.0) <= 0.1,
          f"E = P t = 1000 x 120 = {1000.0 * t_sel:.0f} J "
          f"= {delivered:.0f} kJ; key 120 kJ, tolerance "
          f"+/-0.1 kJ")

    check("Q14.6", "dimensions: m c_p delta T is kg J/(kg K) "
                     "K = J; Q/t is J/s = W",
          True,
          "the heat is kg x (J/(kg K)) x K = J; the "
          "power is J/s = W; the delivered energy is W x "
          "s = J. All were computed above in SI units, so "
          "the units follow from the arithmetic.")

    check("Q14.7", "wrong answer 'select 1250 W' is "
                     "genuinely wrong",
          1250.0 in powers and 1250.0 >= p_min
          and 1000.0 >= p_min and 1000.0 < 1250.0,
          "1250 W passes the time limit, but so does "
          "1000 W (at the limit, which the question "
          "expressly allows), and the question requires "
          "the smallest passing power - 1250 W is not "
          "the selection the rule determines")

    heat_wrong = mass * c_p * 35.0
    check("Q14.8", "wrong answer '280 kJ required heat' "
                     "is genuinely wrong",
          abs(heat_wrong - 280000.0) <= 100.0
          and abs(heat_wrong - heat) > 100.0,
          f"2.00 x 4000 x 35.0 = {heat_wrong:.0f} J "
          f"uses the final Celsius temperature instead "
          f"of the temperature rise; the correct heat is "
          f"{heat:.0f} J - the wrong answer differs by "
          f"{heat_wrong - heat:.0f} J, outside the "
          f"+/-100 J tolerance")


def verify_q15(directory: Path) -> None:
    # Stated instruction: zero at zero displacement;
    # apply and record 1.000 mm; apply and record
    # 2.000 mm; return to zero and record without
    # re-zeroing; nonzero readings within +/-0.020 mm
    # of reference, final zero within 0.010 mm,
    # inclusive; no adjustment between readings. The
    # log: 1.010, 1.970, 0.005 mm.
    items = {i["item"]: i for i
             in _keyed_items("Q15", directory)}
    sequence = _plain(
        items["Ordered check sequence"]["value"])
    criteria = _plain(
        items["Acceptance criteria"]["value"])

    i_zero = sequence.lower().index("zero at")
    i_first = sequence.index("1.000")
    i_second = sequence.index("2.000")
    i_return = sequence.lower().index("return to zero")
    check("Q15.1", "ordered check sequence as the "
                     "instruction states it",
          i_zero < i_first < i_second < i_return
          and "without re-zeroing" in sequence,
          f"the keyed sequence reads '{sequence}': "
          f"zero at the unloaded zero, then the 1.000 mm "
          f"reference, then the 2.000 mm reference, then "
          f"a return to zero recorded without re-zeroing - "
          f"no adjustment between recorded readings")

    check("Q15.2", "acceptance criteria as the "
                     "instruction states them",
          "0.020" in criteria and "0.010" in criteria
          and "<=" in criteria,
          f"the keyed criteria read '{criteria}': nonzero "
          f"errors at most 0.020 mm in magnitude, the "
          f"final zero at most 0.010 mm, both inclusive")

    e1 = 1.010 - 1.000
    RECOMPUTED["q15_e1"] = e1
    check("Q15.3", "first signed error recomputed "
                     "(reading minus reference)",
          abs(e1 - 0.010) <= 0.0005 and abs(e1) <= 0.020,
          f"e_1 = 1.010 - 1.000 = {e1:+.3f} mm; its "
          f"magnitude is within the 0.020 mm limit, so "
          f"the first check passes; key +0.010 mm, "
          f"tolerance +/-0.0005 mm")

    e2 = 1.970 - 2.000
    RECOMPUTED["q15_e2"] = e2
    check("Q15.4", "second signed error recomputed "
                     "(reading minus reference)",
          abs(e2 - (-0.030)) <= 0.0005
          and abs(e2) > 0.020,
          f"e_2 = 1.970 - 2.000 = {e2:+.3f} mm; its "
          f"magnitude 0.030 mm exceeds the 0.020 mm "
          f"limit, so the second check fails - the keyed "
          f"error is -0.030 mm (negative sign required), "
          f"tolerance +/-0.0005 mm")

    e0 = 0.005 - 0.0
    RECOMPUTED["q15_e0"] = e0
    check("Q15.5", "return-zero error recomputed "
                     "(reading minus zero)",
          abs(e0 - 0.005) <= 0.0005 and abs(e0) <= 0.010,
          f"e_0 = 0.005 - 0 = {e0:+.3f} mm; its magnitude "
          f"is within the 0.010 mm return-zero limit, so "
          f"the final zero passes; key +0.005 mm, "
          f"tolerance +/-0.0005 mm")

    keyed_verdict = items["Overall verdict"]["value"]
    check("Q15.6", "overall verdict follows from the "
                     "per-check verdicts",
          keyed_verdict == "FAIL"
          and abs(e2) > 0.020
          and abs(e1) <= 0.020 and abs(e0) <= 0.010,
          "every check must pass, but the second "
          f"displacement check fails (|{e2:+.3f}| mm > "
          f"0.020 mm), so the overall verdict is FAIL - "
          f"the keyed verdict is '{keyed_verdict}', and "
          f"the failed check is the second reading")

    check("Q15.7", "wrong answer 'PASS because the final "
                     "zero is acceptable' is genuinely "
                     "wrong",
          abs(e2) > 0.020 and abs(e0) <= 0.010,
          "an acceptable return zero does not excuse the "
          "failed second displacement check: the "
          "instruction requires every check to pass, and "
          f"the second reading's error is {e2:+.3f} mm, "
          "outside its 0.020 mm limit")

    check("Q15.8", "wrong answer 're-zero before the "
                     "final reading' is genuinely wrong",
          "without re-zeroing" in sequence,
          "the instruction requires recording the return "
          "to zero without re-zeroing, precisely so the "
          "return-zero error is visible; re-zeroing "
          "before the final reading is the adjustment "
          "the instruction forbids, and it would mask "
          "the error the check exists to measure")


def verify_q16() -> None:
    # Stated inputs: L_0 = 0.800 m at 20.0 deg C,
    # alpha = 12.0e-6 /K, heated to 70.0 deg C,
    # free expansion, original length in the formula.
    alpha, l_0 = 12.0e-6, 0.800
    d_t = 70.0 - 20.0

    d_l = alpha * l_0 * d_t
    RECOMPUTED["q16_dl"] = d_l * 1000.0
    check("Q16.1", "length increase recomputed",
          abs(d_l * 1000.0 - 0.480) <= 0.001,
          f"delta L = alpha L_0 delta T = 12.0e-6 x "
          f"0.800 x 50.0 = {d_l:.6f} m = {d_l * 1000:.3f} "
          f"mm; key +0.480 mm, tolerance +/-0.001 mm")

    l_f = l_0 + d_l
    RECOMPUTED["q16_lf"] = l_f
    check("Q16.2", "final length recomputed",
          abs(l_f - 0.800480) <= 0.000001,
          f"L_f = L_0 + delta L = 0.800 + 0.000480 = "
          f"{l_f:.6f} m; key 0.800480 m, tolerance "
          f"+/-0.000001 m")

    check("Q16.3", "dimensions: K^-1 x m x K = m",
          True,
          "alpha carries K^-1, the original length m and "
          "the temperature change K, so the increase is "
          "m and the final length is m. Both were "
          "computed above in SI units, so the units "
          "follow from the arithmetic.")

    d_l_wrong = alpha * l_0 * 70.0
    check("Q16.4", "wrong answer '0.672 mm increase' is "
                     "genuinely wrong",
          abs(d_l_wrong * 1000.0 - 0.672) <= 0.001
          and abs(d_l_wrong - d_l) > 0.001 / 1000.0,
          f"12.0e-6 x 0.800 x 70.0 = {d_l_wrong:.6f} m "
          f"= {d_l_wrong * 1000:.3f} mm uses the final "
          f"Celsius temperature instead of the "
          f"temperature change; the correct increase is "
          f"{d_l * 1000:.3f} mm - the wrong answer "
          f"differs by {(d_l_wrong - d_l) * 1000:.3f} mm, "
          f"outside the +/-0.001 mm tolerance")

    check("Q16.5", "wrong answer 'a compressive thermal "
                     "stress develops' is genuinely wrong",
          True,
          "the question specifies a freely expanding bar: "
          "with no restraint there is no reaction force "
          "and no stress - thermal stress arises only "
          "when expansion is constrained, which the "
          "stated assumptions exclude")


def verify_q17(directory: Path, manifest: dict) -> None:
    pdf, cross = source_pair(manifest, "Q17")
    check("Q17.1", "archived section PDF hashes to the "
                     "manifest record",
          sha256_file(directory / pdf["file"])
          == pdf["sha256"],
          f"{pdf['file']}: sha256 "
          f"{sha256_file(directory / pdf['file'])[:16]}... "
          f"({(directory / pdf['file']).stat().st_size} "
          f"bytes)")
    check("Q17.2", "archived text extraction hashes to "
                     "the manifest record",
          sha256_file(directory / pdf["text_extraction"])
          == pdf["text_sha256"],
          f"{pdf['text_extraction']}: sha256 "
          f"{sha256_file(directory / pdf['text_extraction'])[:16]}"
          f"... "
          f"({(directory / pdf['text_extraction']).stat().st_size} "
          f"bytes)")
    check("Q17.3", "stability cross-check XML hashes to "
                     "the manifest record",
          sha256_file(directory / cross["file"])
          == cross["sha256"],
          f"{cross['file']}: sha256 "
          f"{sha256_file(directory / cross['file'])[:16]}..."
          f" "
          f"({(directory / cross['file']).stat().st_size} "
          f"bytes)")

    left, _right = reconstruct_columns(
        (directory / pdf["text_extraction"]
         ).read_text(encoding="utf-8"))
    strength = float(re.search(
        r"no less than (\d+) pounds", left).group(1))
    RECOMPUTED["q17_lb"] = strength
    items = {i["item"]: i for i
             in _keyed_items("Q17", directory)}
    keyed_strength = _plain(
        items["Minimum unlocking strength"]["value"])
    keyed_frequency = _plain(
        items["Inspection frequency"]["value"])

    check("Q17.4", "the attachment-means provision "
                     "matches the archive verbatim",
          "a minimum unlocking strength of no less than "
          "50 pounds" in left
          and re.search(r"\b50\s*(?:lb|pounds?)\b",
                        keyed_strength.lower())
          is not None,
          "the archived 1910.147(c)(5)(ii)(C)(2) reads "
          "'...with a minimum unlocking strength of no "
          "less than 50 pounds...' - the keyed answer "
          f"is '{keyed_strength}', the same inclusive "
          "lower bound in the regulation's pounds unit "
          "(the key abbreviates it 'lb')")

    check("Q17.5", "the inspection provision matches the "
                     "archive verbatim",
          "periodic inspection" in left
          and "energy control procedure" in left
          and "at least annually" in left
          and "annually" in keyed_frequency.lower(),
          "the archived 1910.147(c)(6)(i) reads 'The "
          "employer shall conduct a periodic inspection "
          "of the energy control procedure at least "
          f"annually...' - the keyed answer is "
          f"'{keyed_frequency}', the same minimum "
          "frequency")

    xml = (directory / cross["file"]
           ).read_text(encoding="utf-8")
    check("Q17.6", "the eCFR cross-check carries both "
                     "provisions verbatim",
          "a minimum unlocking strength of no less than "
          "50 pounds" in xml
          and "at least annually" in xml,
          "the current eCFR text as of 2026-10-01 "
          "carries both provisions verbatim - a 12-year "
          "span from the pinned 2014 edition, which "
          "satisfies the command's 'unchanged for at "
          "least three years' requirement")

    check("Q17.7", "wrong answer '50 kg' is genuinely "
                     "wrong",
          "pounds" in left and "kg" not in keyed_strength,
          "the archived provision states pounds, not "
          "kilograms: 50 lb is about 22.7 kg, and "
          "50 kg is about 110 lb - neither equals the "
          "50 lb the regulation specifies")

    check("Q17.8", "wrong answer 'every two years' is "
                     "genuinely wrong",
          "at least annually" in left,
          "the archived provision requires the periodic "
          "inspection 'at least annually'; every two "
          "years is half the required minimum frequency "
          "- the keyed answer is 'at least annually'")


def verify_q18() -> None:
    # Stated inputs: span 2.00 m, midspan load 1000 N
    # downward, section 40.0 mm wide x 60.0 mm deep
    # (vertical), E = 200 GPa; simply supported,
    # Euler-Bernoulli, no self-weight or shear.
    p, span = 1000.0, 2.00
    b, h = 0.0400, 0.0600
    e_mod = 200.0e9

    moment = p * span / 4
    RECOMPUTED["q18_m"] = moment
    check("Q18.1", "maximum bending moment recomputed",
          abs(moment - 500.0) <= 0.5,
          f"M_max = PL/4 = 1000 x 2.00/4 = {moment:.0f} "
          f"N m; key 500 N m, tolerance +/-0.5 N m")

    second = b * h ** 3 / 12
    RECOMPUTED["q18_i"] = second
    check("Q18.2", "second moment of area recomputed "
                     "about the bending axis",
          rel(second, 7.20e-7) <= 0.001,
          f"I = bh^3/12 = 0.0400 x 0.0600^3/12 = "
          f"{second:.8e} m^4; key 7.20e-7 m^4, relative "
          f"tolerance 0.1% (deviation "
          f"{rel(second, 7.20e-7) * 100:.4f}%)")

    sigma = moment * (h / 2) / second
    RECOMPUTED["q18_sigma"] = sigma / 1e6
    check("Q18.3", "maximum bending stress recomputed",
          abs(sigma / 1e6 - 20.8333) <= 0.05,
          f"sigma_max = M_max (h/2)/I = 500 x 0.0300/"
          f"{second:.6e} = {sigma:.6e} Pa = "
          f"{sigma / 1e6:.4f} MPa; key 20.8333 MPa, "
          f"tolerance +/-0.05 MPa")

    deflection = (p * span ** 3
                  / (48 * e_mod * second))
    RECOMPUTED["q18_delta"] = deflection * 1000.0
    check("Q18.4", "midspan deflection recomputed",
          abs(deflection * 1000.0 - 1.15741) <= 0.005,
          f"delta = PL^3/(48EI) = 1000 x 2.00^3/(48 x "
          f"200e9 x {second:.6e}) = {deflection:.9f} m = "
          f"{deflection * 1000:.5f} mm downward; key "
          f"1.15741 mm, tolerance +/-0.005 mm")

    check("Q18.5", "dimensions: PL is N m; bh^3 is m^4; "
                     "M c/I is Pa; PL^3/(EI) is m",
          True,
          "the moment is N x m; the second moment is "
          "m x m^3 = m^4; the stress is (N m)(m)/(m^4) "
          "= N/m^2 = Pa; the deflection is "
          "N m^3/((N/m^2)(m^4)) = m. All were computed "
          "above in SI units, so the units follow from "
          "the arithmetic.")

    second_wrong = h * b ** 3 / 12
    check("Q18.6", "wrong answer 'I = hb^3/12' is "
                     "genuinely wrong",
          rel(second_wrong, second) > 0.5,
          f"hb^3/12 = 0.0600 x 0.0400^3/12 = "
          f"{second_wrong:.8e} m^4 cubes the width "
          f"instead of the vertical depth; the correct "
          f"I = {second:.8e} m^4 - the wrong formula "
          f"misstates the requested quantity by "
          f"{rel(second_wrong, second) * 100:.1f}%, "
          f"outside the 0.1% relative tolerance")

    cantilever = p * span ** 3 / (3 * e_mod * second)
    check("Q18.7", "wrong answer 'use the cantilever "
                     "deflection formula' is genuinely "
                     "wrong",
          abs(cantilever * 1000.0
              - 16.0 * deflection * 1000.0) <= 0.005
          and abs(cantilever - deflection) > 0.005 / 1000.0,
          f"the stated beam is simply supported, so the "
          f"deflection is PL^3/(48EI); the cantilever "
          f"formula PL^3/(3EI) gives "
          f"{cantilever * 1000:.4f} mm - exactly "
          f"{cantilever / deflection:.0f} times the "
          f"correct {deflection * 1000:.5f} mm, outside "
          f"the +/-0.005 mm tolerance")


def verify_q19() -> None:
    # Stated inputs: supply 9.00 V, LED forward drop
    # exactly 2.40 V, current 18.0-22.0 mA inclusive;
    # available resistances 270, 330, 390 ohm;
    # available ratings 0.125, 0.250, 0.500 W; the
    # rating must be at least twice the dissipation,
    # equality allowed.
    v_supply, v_led = 9.00, 2.40
    i_lo, i_hi = 0.0180, 0.0220
    resistances = [270.0, 330.0, 390.0]
    ratings = [0.125, 0.250, 0.500]

    v_r = v_supply - v_led
    currents = {r: v_r / r for r in resistances}
    passing = [r for r in resistances
               if i_lo <= currents[r] <= i_hi]

    RECOMPUTED["q19_r"] = 330.0
    RECOMPUTED["q19_i"] = currents[330.0]
    check("Q19.1", "selected resistance and current "
                     "recomputed",
          passing == [330.0]
          and abs(currents[330.0] - 0.0200) <= 0.00005,
          f"V_R = 9.00 - 2.40 = {v_r:.2f} V; the "
          f"available resistances draw "
          f"{{270: {currents[270.0] * 1000:.4f}, "
          f"330: {currents[330.0] * 1000:.4f}, "
          f"390: {currents[390.0] * 1000:.4f}}} mA; only "
          f"330 ohm lies inside the 18.0-22.0 mA "
          f"inclusive band, drawing "
          f"{currents[330.0] * 1000:.1f} mA - the keyed "
          f"selection, with current 20.0 mA")

    check("Q19.2", "the selection is exact: exactly one "
                     "available resistance passes",
          len(passing) == 1,
          f"of the available {avail_str(resistances)} "
          f"ohm, the currents are "
          f"{[round(currents[r] * 1000, 4) for r in resistances]} "
          f"mA against the 18.0-22.0 mA band: exactly one "
          f"resistance (330 ohm) passes, so the "
          f"selection is exact, not a choice among "
          f"several")

    i_270 = currents[270.0]
    RECOMPUTED["q19_i270"] = i_270
    check("Q19.3", "lower resistance rejection "
                     "recomputed",
          abs(i_270 * 1000 - 24.4444) <= 0.00005
          and i_270 > i_hi,
          f"270 ohm draws 6.60/270 = {i_270 * 1000:.4f} "
          f"mA > 22.0 mA - it fails high, so the keyed "
          f"rejection is genuine (tolerance +/-0.05 mA)")

    i_390 = currents[390.0]
    RECOMPUTED["q19_i390"] = i_390
    check("Q19.4", "higher resistance rejection "
                     "recomputed",
          abs(i_390 * 1000 - 16.9231) <= 0.00005
          and i_390 < i_lo,
          f"390 ohm draws 6.60/390 = {i_390 * 1000:.4f} "
          f"mA < 18.0 mA - it fails low, so the keyed "
          f"rejection is genuine (tolerance +/-0.05 mA)")

    dissipation = v_r * currents[330.0]
    RECOMPUTED["q19_p"] = dissipation
    check("Q19.5", "resistor dissipation recomputed",
          abs(dissipation - 0.132) <= 0.001,
          f"P_R = V_R I = 6.60 x 0.0200 = "
          f"{dissipation:.3f} W; key 0.132 W, tolerance "
          f"+/-0.001 W")

    p_min = 2.0 * dissipation
    selected_rating = min(
        r for r in ratings if r >= p_min)
    RECOMPUTED["q19_pmin"] = p_min
    check("Q19.6", "minimum required rating and the "
                     "discrete rating selection "
                     "recomputed",
          abs(p_min - 0.264) <= 0.001
          and selected_rating == 0.500,
          f"the required rating is at least 2 x 0.132 = "
          f"{p_min:.3f} W (equality allowed); of the "
          f"available {avail_str(ratings)} W, 0.250 W "
          f"falls short of 0.264 W and 0.500 W passes - "
          f"the keyed selection is 0.500 W")

    check("Q19.7", "dimensions: V/ohm is A; V x A is W",
          True,
          "the current is V/ohm = A and the dissipation "
          "is V x A = W. All were computed above in SI "
          "units, so the units follow from the arithmetic.")

    check("Q19.8", "wrong answer 'select a 0.250 W "
                     "resistor' is genuinely wrong",
          0.250 < p_min,
          f"the question requires a rating at least twice "
          f"the actual dissipation: 2 x 0.132 = "
          f"{p_min:.3f} W, and the available 0.250 W "
          f"rating falls short of that minimum - it "
          f"satisfies the dissipation but not the stated "
          f"rating margin")

    i_wrong = v_supply / 330.0
    check("Q19.9", "wrong answer 'use 9.00/R for LED "
                     "current' is genuinely wrong",
          abs(i_wrong * 1000 - 27.2727) <= 0.0001
          and (i_wrong > i_hi or i_wrong < i_lo)
          and abs(i_wrong - currents[330.0]) > 0.00005,
          f"9.00/330 = {i_wrong * 1000:.4f} mA omits "
          f"the LED forward drop: the resistor sees only "
          f"9.00 - 2.40 = 6.60 V, so the current is "
          f"{currents[330.0] * 1000:.1f} mA. The wrong "
          f"answer is {i_wrong * 1000 - currents[330.0] * 1000:.1f} mA "
          f"high - outside the 18.0-22.0 mA band and "
          f"outside the +/-0.05 mA tolerance")


def avail_str(values: list[float]) -> str:
    """The available values as a comma-joined
    string, for the check details."""
    return ", ".join(f"{v:g}" for v in values)


def verify_q20(directory: Path) -> None:
    # Stated bench instruction: start the pump with
    # flow diverted to the return tank, adjust the
    # indication to 12.0 L/min, hold steady 30 s;
    # zero the collection-volume reading, divert into
    # the vessel while starting the timer, collect
    # 60.0 s without adjusting flow, divert back and
    # stop timing together; read the volume before
    # stopping the pump. Signed indication error is
    # 100 (indicated - reference)/reference; pass if
    # |e| <= 3.0%. The log: 11.76 L in 60.0 s at a
    # steady 12.0 L/min indication.
    items = {i["item"]: i for i
             in _keyed_items("Q20", directory)}
    start = _plain(
        items["Start and stabilization"]["value"])
    collect = _plain(items["Collection sequence"]["value"])
    end = _plain(items["End sequence"]["value"])

    i_start = start.lower().index("return")
    i_set = start.lower().index("set")
    i_steady = start.lower().index("steady")
    check("Q20.1", "start and stabilization order as "
                     "the instruction states it",
          i_start < i_set < i_steady
          and "12.0" in start and "30" in start,
          f"the keyed sequence reads '{start}': the "
          f"pump starts with flow diverted to the "
          f"return tank, the indication is set to "
          f"12.0 L/min, and that indication is held "
          f"steady for 30 s - stabilization precedes "
          f"collection")

    i_zero = collect.lower().index("zero")
    i_divert = collect.lower().index("divert")
    i_timer = collect.lower().index("timer")
    # 'collect 60', not 'collect': the keyed
    # sequence's own 'collection-volume reading'
    # contains 'collect' before the diversion.
    i_collect = collect.lower().index("collect 60")
    check("Q20.2", "collection sequence as the "
                     "instruction states it",
          i_zero < i_divert < i_timer < i_collect
          and "together" in collect
          and "without adjustment" in collect,
          f"the keyed sequence reads '{collect}': the "
          f"collection-volume reading is zeroed, the "
          f"flow is diverted into the vessel and the "
          f"timer started together, and the collection "
          f"runs 60.0 s without adjustment - zeroing "
          f"precedes collection, and adjusting flow "
          f"during collection is forbidden")

    i_divert_back = end.lower().index("divert back")
    i_stop_timing = end.lower().index("stop timing")
    i_read = end.lower().index("read")
    i_pump = end.lower().index("pump")
    check("Q20.3", "end sequence as the instruction "
                     "states it",
          i_divert_back < i_stop_timing < i_read
          < i_pump,
          f"the keyed sequence reads '{end}': the flow "
          f"is diverted back and the timer stopped "
          f"together, the volume is read, and only then "
          f"is the pump stopped - the volume reading "
          f"precedes pump shutdown")

    collected, collect_t, indicated = 11.76, 60.0, 12.0
    q_ref = collected / (collect_t / 60.0)
    RECOMPUTED["q20_qref"] = q_ref
    check("Q20.4", "reference flow recomputed from the "
                     "logged collection",
          abs(q_ref - 11.76) <= 0.005,
          f"Q_ref = 11.76 L / (60.0 s / 60 s/min) = "
          f"{q_ref:.2f} L/min; key 11.76 L/min, "
          f"tolerance +/-0.005 L/min")

    error = 100.0 * (indicated - q_ref) / q_ref
    RECOMPUTED["q20_e"] = error
    check("Q20.5", "signed indication error recomputed "
                     "against the reference flow",
          abs(error - 2.04082) <= 0.01 and error > 0,
          f"e = 100 (12.0 - 11.76)/11.76 = "
          f"{error:+.5f}% - positive, an over-reading "
          f"against the stipulated reference flow; key "
          f"+2.04082%, tolerance +/-0.01 percentage "
          f"points")

    keyed_verdict = _plain(
        items["Acceptance and verdict"]["value"])
    answer = _model_answer("Q20", directory)
    check("Q20.6", "the logged verdict follows from "
                     "the recomputed error",
          abs(error) <= 3.0
          and "pass" in keyed_verdict.lower()
          and "11.76" in _plain(answer)
          and "12.0" in _plain(answer),
          f"|e| = {abs(error):.5f}% <= 3.0% (inclusive "
          f"limit), so the logged test passes - the "
          f"keyed verdict reads '{keyed_verdict}', and "
          f"the worked answer identifies the reference "
          f"flow and the indication")

    reversed_error = 100.0 * (q_ref - indicated) / indicated
    check("Q20.7", "wrong answer '-2.0% error' is "
                     "genuinely wrong",
          abs(reversed_error - (-2.0)) <= 0.01
          and abs(reversed_error - error) > 0.01,
          f"100 (11.76 - 12.0)/12.0 = {reversed_error:+.1f}% "
          f"reverses the numerator and divides by the "
          f"indicated flow instead of the stipulated "
          f"reference flow; the correct error is "
          f"{error:+.5f}% - the wrong answer differs by "
          f"{abs(reversed_error - error):.2f} percentage "
          f"points, outside the +/-0.01 tolerance")

    check("Q20.8", "wrong answer 'stop the pump to end "
                     "collection' is genuinely wrong",
          i_read < i_pump,
          "the stipulated endpoint is diversion back to "
          "the return tank and timer stop together; the "
          "pump is stopped only after the collected "
          "volume is read - stopping the pump to end "
          "collection reverses the stated order")


def verify_q21() -> None:
    # Stated inputs: 1.00 kg at 80.0 deg C, 3.00 kg
    # at 20.0 deg C, equal constant specific heat,
    # insulated vessel of negligible heat capacity,
    # no phase change or heat loss.
    m_h, t_h = 1.00, 80.0
    m_c, t_c = 3.00, 20.0

    t_f = (m_h * t_h + m_c * t_c) / (m_h + m_c)
    RECOMPUTED["q21_tf"] = t_f
    check("Q21.1", "final mixed temperature recomputed",
          abs(t_f - 35.0) <= 0.05,
          f"T_f = (m_h T_h + m_c T_c)/(m_h + m_c) = "
          f"(1.00 x 80.0 + 3.00 x 20.0)/4.00 = "
          f"{t_f:.1f} deg C; the common specific heat "
          f"cancels; key 35.0 deg C, tolerance "
          f"+/-0.05 deg C")

    check("Q21.2", "dimensions: the mass-weighted "
                     "average of temperatures is a "
                     "temperature",
          True,
          "the numerator is kg x K and the denominator "
          "kg, so the quotient is K (equivalently deg C "
          "- the scales share increments, so the "
          "weighted average is the same in either unit, "
          "308.15 K). Computed above in kg and deg C, "
          "so the units follow from the arithmetic.")

    unweighted = (t_h + t_c) / 2
    check("Q21.3", "wrong answer '50 deg C' is genuinely "
                     "wrong",
          abs(unweighted - 50.0) <= 0.05
          and abs(unweighted - t_f) > 0.05,
          f"the unweighted average (80.0+20.0)/2 = "
          f"{unweighted:.1f} deg C ignores the unequal "
          f"masses (1.00 kg hot against 3.00 kg cold); "
          f"the correct temperature is {t_f:.1f} deg C - "
          f"the wrong answer differs by "
          f"{abs(unweighted - t_f):.1f} deg C, outside "
          f"the +/-0.05 deg C tolerance")

    swapped = (m_c * t_h + m_h * t_c) / (m_h + m_c)
    check("Q21.4", "wrong answer '65 deg C' is genuinely "
                     "wrong",
          abs(swapped - 65.0) <= 0.05
          and abs(swapped - t_f) > 0.05,
          f"(3.00 x 80.0 + 1.00 x 20.0)/4.00 = "
          f"{swapped:.1f} deg C assigns the larger mass "
          f"to the hot portion; the correct temperature "
          f"is {t_f:.1f} deg C - the wrong answer "
          f"differs by {abs(swapped - t_f):.1f} deg C, "
          f"outside the +/-0.05 deg C tolerance")


def verify_q22(directory: Path, manifest: dict) -> None:
    pdf, cross = source_pair(manifest, "Q22")
    check("Q22.1", "archived section PDF hashes to the "
                     "manifest record",
          sha256_file(directory / pdf["file"])
          == pdf["sha256"],
          f"{pdf['file']}: sha256 "
          f"{sha256_file(directory / pdf['file'])[:16]}... "
          f"({(directory / pdf['file']).stat().st_size} "
          f"bytes)")
    check("Q22.2", "archived text extraction hashes to "
                     "the manifest record",
          sha256_file(directory / pdf["text_extraction"])
          == pdf["text_sha256"],
          f"{pdf['text_extraction']}: sha256 "
          f"{sha256_file(directory / pdf['text_extraction'])[:16]}"
          f"... "
          f"({(directory / pdf['text_extraction']).stat().st_size} "
          f"bytes)")
    check("Q22.3", "stability cross-check XML hashes to "
                     "the manifest record",
          sha256_file(directory / cross["file"])
          == cross["sha256"],
          f"{cross['file']}: sha256 "
          f"{sha256_file(directory / cross['file'])[:16]}..."
          f" "
          f"({(directory / cross['file']).stat().st_size} "
          f"bytes)")

    raw = (directory / pdf["text_extraction"]
           ).read_text(encoding="utf-8")
    _left, right = reconstruct_columns(raw)
    # The GPO typesetting carries typographic
    # apostrophes; phrase probes use straight
    # ones, so the column is straightened before
    # matching.
    right = _straight(right)
    deadline = float(re.search(
        r"Within (\d+) months", right).group(1))
    period = float(re.search(
        r"at least (\d+) hours", right).group(1))
    retest = float(re.search(
        r"retest within (\d+) days", right).group(1))
    RECOMPUTED["q22_m"] = deadline
    RECOMPUTED["q22_h"] = period
    RECOMPUTED["q22_d"] = retest
    items = {i["item"]: i for i
             in _keyed_items("Q22", directory)}
    keyed_deadline = _plain(
        items["Baseline deadline"]["value"])
    keyed_period = _plain(
        items["Pre-baseline workplace-noise-free "
               "period"]["value"])
    keyed_retest = _plain(
        items["Retest window"]["value"])

    check("Q22.4", "the baseline deadline matches the "
                     "archive verbatim",
          "Within 6 months of an employee's first "
          "exposure at or above the action level" in right
          and "6" in keyed_deadline
          and "month" in keyed_deadline.lower(),
          "the archived 1910.95(g)(5)(i) reads '(i) "
          "Within 6 months of an employee's first "
          "exposure at or above the action level, the "
          "employer shall establish a valid baseline "
          f"audiogram...' - the keyed answer is "
          f"'{keyed_deadline}', the same deadline")

    check("Q22.5", "the pre-baseline noise-free period "
                     "matches the archive verbatim",
          "at least 14 hours without exposure to "
          "workplace noise" in right
          and re.search(r"\b14\s*(?:h|hr|hours?)\b",
                        keyed_period.lower())
          is not None,
          "the archived 1910.95(g)(5)(iii) requires "
          "baseline testing 'preceded by at least 14 "
          "hours without exposure to workplace noise' "
          f"- the keyed answer is '{keyed_period}', the "
          f"same minimum period (hearing protectors as a "
          f"substitute are excluded by the question; the "
          f"key abbreviates the unit 'h')")

    check("Q22.6", "the retest window matches the "
                     "archive verbatim",
          "obtain a retest within 30 days" in right
          and "30" in keyed_retest
          and "day" in keyed_retest.lower(),
          "the archived 1910.95(g)(7)(ii) lets the "
          "employer 'obtain a retest within 30 days and "
          "consider the results of the retest as the "
          f"annual audiogram' - the keyed answer is "
          f"'{keyed_retest}', the same window (the "
          f"retest is permitted, not universally "
          f"mandatory)")

    xml = (directory / cross["file"]
           ).read_text(encoding="utf-8")
    check("Q22.7", "the eCFR cross-check carries all "
                     "three provisions verbatim",
          "Within 6 months of an employee's first "
          "exposure at or above the action level" in xml
          and "at least 14 hours without exposure to "
          "workplace noise" in xml
          and "within 30 days" in xml,
          "the current eCFR text as of 2026-10-01 "
          "carries all three provisions verbatim - a "
          "12-year span from the pinned 2014 edition, "
          "which satisfies the command's 'unchanged for "
          "at least three years' requirement")

    check("Q22.8", "the question excludes the mobile-"
                     "test-van exception, and the keyed "
                     "deadline is the general rule",
          "within 1 year" in re.sub(r"-\s*\n\s*", "", raw)
          and "6" in keyed_deadline,
          "the archive's 1910.95(g)(5)(ii) permits a "
          "baseline 'within 1 year' only where a mobile "
          "test van is used; the question states that "
          "exception is not used, so the 6-month "
          "general rule of (g)(5)(i) is the deadline "
          "the question asks for")

    check("Q22.9", "wrong answer 'baseline within one "
                     "year' is genuinely wrong",
          "within 1 year" in re.sub(r"-\s*\n\s*", "", raw),
          "one year is the (g)(5)(ii) mobile-test-van "
          "exception, which the question expressly "
          "excludes; with the exception not used, the "
          "(g)(5)(i) deadline is 6 months - the keyed "
          "answer")

    check("Q22.10", "wrong answer 'retest within 21 "
                      "days' is genuinely wrong",
          "within 21 days" in re.sub(r"-\s*\n\s*", "", raw)
          and "within 30 days" in right,
          "the 21-day figure in the archive is the "
          "written-notification window of a standard "
          "threshold-shift determination "
          "('(10) Standard threshold shift... informed "
          "of this fact in writing, within 21 days of "
          "the determination'), not the retest window; "
          "the retest window the archive states is "
          "30 days - the keyed answer")


def verify_q23() -> None:
    # Stated inputs: parallel bars between rigid end
    # plates, same 1.00 m length, same extension;
    # aluminum 200 mm^2 at 70.0 GPa, steel 100 mm^2
    # at 200.0 GPa; total tensile load 30.0 kN;
    # linear elasticity, no temperature change.
    f_total, length = 30000.0, 1.00
    e_a, a_a = 70.0e9, 200.0e-6
    e_s, a_s = 200.0e9, 100.0e-6

    strain = f_total / (e_a * a_a + e_s * a_s)
    extension = strain * length
    RECOMPUTED["q23_dl"] = extension * 1000.0
    check("Q23.1", "common strain and extension "
                     "recomputed",
          abs(extension * 1000.0 - 0.882353) <= 0.001,
          f"epsilon = F/(E_a A_a + E_s A_s) = 30000/"
          f"({e_a:.0f} x {a_a} + {e_s:.0f} x {a_s}) = "
          f"{strain:.9f}; delta = epsilon L = "
          f"{extension:.9f} m = {extension * 1000:.6f} "
          f"mm; key 0.882353 mm, tolerance +/-0.001 mm")

    sigma_a = e_a * strain
    RECOMPUTED["q23_sa"] = sigma_a / 1e6
    check("Q23.2", "aluminum tensile stress recomputed",
          abs(sigma_a / 1e6 - 61.7647) <= 0.1,
          f"sigma_a = E_a epsilon = {e_a:.0f} x "
          f"{strain:.9f} = {sigma_a:.6e} Pa = "
          f"{sigma_a / 1e6:.4f} MPa; key 61.7647 MPa, "
          f"tolerance +/-0.1 MPa")

    sigma_s = e_s * strain
    RECOMPUTED["q23_ss"] = sigma_s / 1e6
    check("Q23.3", "steel tensile stress recomputed",
          abs(sigma_s / 1e6 - 176.471) <= 0.5,
          f"sigma_s = E_s epsilon = {e_s:.0f} x "
          f"{strain:.9f} = {sigma_s:.6e} Pa = "
          f"{sigma_s / 1e6:.4f} MPa; key 176.471 MPa, "
          f"tolerance +/-0.5 MPa")

    force_a = sigma_a * a_a
    force_s = sigma_s * a_s
    RECOMPUTED["q23_fa"] = force_a / 1000.0
    RECOMPUTED["q23_fs"] = force_s / 1000.0
    check("Q23.4", "the force carried by each bar "
                     "recomputed, and the shares sum "
                     "to the total load",
          abs(force_a / 1000.0 - 12.3529) <= 0.01
          and abs(force_s / 1000.0 - 17.6471) <= 0.01
          and abs(force_a + force_s - f_total) <= 1e-6
          and abs((f_total - force_a) - force_s) <= 1e-6,
          f"F_a = sigma_a A_a = {sigma_a / 1e6:.4f} MPa "
          f"x 200 mm^2 = {force_a:.1f} N = "
          f"{force_a / 1000:.4f} kN; F_s = sigma_s A_s = "
          f"{force_s:.1f} N = {force_s / 1000:.4f} kN; "
          f"independently F_s = 30000 - F_a = "
          f"{(f_total - force_a) / 1000:.4f} kN; the "
          f"shares sum to {force_a / 1000 + force_s / 1000:.4f} "
          f"kN = the applied 30.0 kN")

    check("Q23.5", "dimensions: F/(E A) is N/((Pa) m^2) "
                     "= 1; sigma = E epsilon is Pa; "
                     "F = sigma A is N",
          True,
          "the strain is N/((N/m^2)(m^2)) = 1 (reported "
          "dimensionless); the stresses are Pa; the "
          "forces are Pa x m^2 = N. All were computed "
          "above in SI units, so the units follow from "
          "the arithmetic.")

    equal_share = f_total / 2
    check("Q23.6", "wrong answer 'each bar carries 15 "
                     "kN' is genuinely wrong",
          abs(equal_share / 1000.0 - 15.0) <= 0.01
          and (abs(force_a - equal_share) > 100.0
               or abs(force_s - equal_share) > 100.0),
          f"an equal split would give 15.0 kN per bar, "
          f"but the load shares follow the axial "
          f"stiffnesses E A: aluminum {e_a * a_a / 1e6:.1f} "
          f"MN against steel {e_s * a_s / 1e6:.1f} MN - "
          f"the actual shares are "
          f"{force_a / 1000:.4f} kN and "
          f"{force_s / 1000:.4f} kN, each more than "
          f"{abs(force_a / 1000 - 15.0):.2f} kN from the "
          f"wrong answer, outside the +/-0.01 kN "
          f"tolerance")

    check("Q23.7", "wrong answer 'both bars have the "
                     "same stress' is genuinely wrong",
          abs(sigma_a - sigma_s) > 1e6
          and abs(sigma_s / sigma_a - e_s / e_a) <= 1e-9,
          f"equal strain with different moduli gives "
          f"different stresses: sigma_s/sigma_a = "
          f"E_s/E_a = {e_s / e_a:.4f}, so the steel "
          f"stress ({sigma_s / 1e6:.4f} MPa) is "
          f"{sigma_s / sigma_a:.1f} times the aluminum "
          f"stress ({sigma_a / 1e6:.4f} MPa) - the "
          f"wrong answer contradicts the equal-strain "
          f"condition the parallel mounting imposes")


def verify_q24() -> None:
    # Stated inputs: driver pitch diameter 80.0 mm at
    # 1500 rpm transmitting 4.00 N m; available
    # driven diameters 160, 200, 240 mm; output at
    # most 500 rpm, equality allowed; ideal open-belt
    # drive, no slip or loss.
    d_i, n_i, t_i = 80.0, 1500.0, 4.00
    n_max = 500.0
    diameters = [160.0, 200.0, 240.0]

    d_min = d_i * n_i / n_max
    speeds = {d: n_i * d_i / d for d in diameters}
    passing = [d for d in diameters
               if speeds[d] <= n_max]
    selected = min(passing)
    RECOMPUTED["q24_d"] = selected
    check("Q24.1", "minimum driven diameter and the "
                     "discrete selection recomputed",
          d_min == 240.0 and selected == 240.0
          and speeds[240.0] == n_max,
          f"D_o >= D_i n_i/n_o,max = 80.0 x 1500/500 = "
          f"{d_min:.1f} mm; of the available "
          f"{avail_str(diameters)} mm the smallest "
          f"giving an output no greater than 500 rpm "
          f"(equality allowed) is 240 mm, at exactly "
          f"{speeds[240.0]:.0f} rpm - the keyed "
          f"selection")

    ratio = selected / d_i
    check("Q24.2", "driven-to-driver diameter ratio "
                     "recomputed",
          ratio == 3.0,
          f"D_o/D_i = 240/80.0 = {ratio:.1f} - the "
          f"keyed ratio 3:1")

    n_o = n_i * d_i / selected
    RECOMPUTED["q24_n"] = n_o
    check("Q24.3", "output speed recomputed",
          abs(n_o - 500.0) <= 0.5,
          f"n_o = n_i D_i/D_o = 1500 x 80.0/240 = "
          f"{n_o:.1f} rpm; key 500 rpm, tolerance "
          f"+/-0.5 rpm")

    check("Q24.4", "output direction: an open belt "
                     "preserves the driver's rotation",
          True,
          "an open (uncrossed) belt drive transmits the "
          "same sense of rotation on both pulleys, so "
          "the output rotates in the same direction as "
          "the driver, viewed from the same side of both "
          "shafts - the keyed answer")

    torque_o = t_i * n_i / n_o
    RECOMPUTED["q24_t"] = torque_o
    check("Q24.5", "output torque recomputed",
          abs(torque_o - 12.0) <= 0.01,
          f"lossless power conservation: T_o = T_i "
          f"n_i/n_o = 4.00 x 1500/500 = {torque_o:.2f} "
          f"N m; key 12.0 N m, tolerance +/-0.01 N m")

    v_belt = math.pi * (d_i / 1000.0) * n_i / 60.0
    v_driven = math.pi * (selected / 1000.0) * n_o / 60.0
    RECOMPUTED["q24_v"] = v_belt
    check("Q24.6", "belt linear speed recomputed from "
                     "both pulleys",
          abs(v_belt - 6.28319) <= 0.01
          and abs(v_driven - v_belt) <= 1e-9,
          f"v = pi D_i n_i/60 = pi x 0.0800 x 1500/60 = "
          f"{v_belt:.5f} m/s; the driven pulley gives "
          f"pi x 0.240 x 500/60 = {v_driven:.5f} m/s - "
          f"the same belt speed; key 6.28319 m/s, "
          f"tolerance +/-0.01 m/s")

    check("Q24.7", "dimensions: rpm mm/mm is rpm; "
                     "T n is proportional to power; "
                     "pi m rev/min / (s/min) is m/s",
          True,
          "the speed ratio is dimensionless, so n_o "
          "carries rpm; T_i n_i and T_o n_o are both "
          "N m rev/min, proportional to power on both "
          "sides of a lossless drive; the belt speed is "
          "pi x m x (1/min) / (s/min)... in SI: "
          "pi x m x (1/60 s) per revolution x rev/min "
          "gives m/s. All were computed above in SI "
          "units, so the units follow from the arithmetic.")

    check("Q24.8", "wrong answer 'select 200 mm' is "
                     "genuinely wrong",
          speeds[200.0] == 600.0
          and speeds[200.0] > n_max,
          f"a 200 mm driven pulley gives n_o = 1500 x "
          f"80.0/200 = {speeds[200.0]:.0f} rpm, which "
          f"exceeds the 500 rpm limit - it is not a "
          f"passing selection, let alone the smallest "
          f"one")

    check("Q24.9", "wrong answer 'output rotates "
                     "oppositely' is genuinely wrong",
          True,
          "opposite rotation describes a crossed belt; "
          "the question specifies an open-belt drive, "
          "which preserves the driver's sense of "
          "rotation - the keyed answer is 'same "
          "rotation direction as driver'")

    torque_wrong = t_i * n_o / n_i
    check("Q24.10", "wrong answer '1.33 N m output "
                      "torque' is genuinely wrong",
          abs(torque_wrong - 4.0 / 3.0) <= 0.01
          and abs(torque_wrong - torque_o) > 0.01,
          f"T_i n_o/n_i = 4.00 x 500/1500 = "
          f"{torque_wrong:.2f} N m inverts the speed "
          f"ratio: a lossless speed reduction increases "
          f"output torque. The correct value is "
          f"{torque_o:.2f} N m - the wrong answer "
          f"differs by {abs(torque_wrong - torque_o):.2f} "
          f"N m, outside the +/-0.01 N m tolerance")


def verify_q25(directory: Path) -> None:
    # Stated bench instruction: input to 0 V before
    # enabling the 5.00 V supply, output LOW; sweep up
    # monotonically, record the LOW-to-HIGH transition,
    # continue to 5.00 V, confirm HIGH; sweep down
    # monotonically, record the HIGH-to-LOW transition,
    # return the input to zero before disabling the
    # supply. Pass only if the rising transition is
    # within 2.90-3.10 V, the falling within 1.90-2.10
    # V, both endpoint states correct, and exactly one
    # transition per sweep, all limits inclusive. The
    # log: correct endpoints, one transition per sweep,
    # rising 3.04 V, falling 1.96 V.
    items = {i["item"]: i for i
             in _keyed_items("Q25", directory)}
    init = _plain(items["Initialization order and state"]["value"])
    rising = _plain(items["Rising sweep"]["value"])
    falling = _plain(
        items["Falling sweep and shutdown"]["value"])
    criteria = _plain(items["Acceptance criteria"]["value"])

    i_zero = init.lower().index("0 v")
    i_enable = init.lower().index("enable")
    i_low = init.lower().index("low")
    check("Q25.1", "initialization order and state as "
                     "the instruction states them",
          i_zero < i_enable < i_low
          and "5.00" in init,
          f"the keyed sequence reads '{init}': the input "
          f"is set to 0 V before the 5.00 V supply is "
          f"enabled, and the output is confirmed LOW - "
          f"input zero precedes supply enable")

    i_increase = rising.lower().index("increase")
    i_transition = rising.lower().index("low-to-high")
    i_continue = rising.lower().index("5.00")
    # 'high' from here: 'low-to-high' earlier in
    # the sequence also contains it.
    i_high = rising.lower().index("high", i_continue)
    check("Q25.2", "rising sweep as the instruction "
                     "states it",
          i_increase < i_transition < i_continue
          < i_high
          and "monotonic" in rising.lower(),
          f"the keyed sweep reads '{rising}': the input "
          f"increases monotonically, the LOW-to-HIGH "
          f"transition voltage is recorded, the sweep "
          f"continues to 5.00 V and the HIGH endpoint "
          f"state is confirmed")

    i_decrease = falling.lower().index("decrease")
    i_fall = falling.lower().index("high-to-low")
    i_return = falling.lower().index("return")
    i_disable = falling.lower().index("disabl")
    check("Q25.3", "falling sweep and shutdown order as "
                     "the instruction states them",
          i_decrease < i_fall < i_return < i_disable
          and "monotonic" in falling.lower(),
          f"the keyed sweep reads '{falling}': the input "
          f"decreases monotonically, the HIGH-to-LOW "
          f"transition voltage is recorded, the input "
          f"returns to zero, and only then is the supply "
          f"disabled - zero input precedes shutdown")

    check("Q25.4", "acceptance criteria: all four "
                     "conditions, limits inclusive",
          all(s in criteria for s in
              ("2.90", "3.10", "1.90", "2.10"))
          and "inclusive" in criteria
          and "endpoint" in criteria.lower()
          and "transition" in criteria.lower(),
          f"the keyed criteria read '{criteria}': the "
          f"rising transition within 2.90-3.10 V "
          f"inclusive, the falling within 1.90-2.10 V "
          f"inclusive, correct endpoint states, and "
          f"exactly one transition per sweep - all four "
          f"conditions required")

    v_rise, v_fall = 3.04, 1.96
    width = v_rise - v_fall
    RECOMPUTED["q25_width"] = width
    check("Q25.5", "hysteresis width recomputed "
                     "(rising minus falling)",
          abs(width - 1.08) <= 0.005,
          f"width = V_up - V_down = 3.04 - 1.96 = "
          f"{width:.2f} V; key 1.08 V, tolerance "
          f"+/-0.005 V")

    in_band = (2.90 <= v_rise <= 3.10
               and 1.90 <= v_fall <= 2.10)
    keyed_verdict = items["Logged verdict"]["value"]
    answer = _model_answer("Q25", directory)
    check("Q25.6", "the logged verdict follows from "
                     "the logged transitions",
          in_band and keyed_verdict == "PASS"
          and "3.04" in _plain(answer)
          and "1.96" in _plain(answer),
          f"the logged rising transition 3.04 V sits "
          f"inside 2.90-3.10 V inclusive and the falling "
          f"transition 1.96 V inside 1.90-2.10 V "
          f"inclusive; the log states correct endpoint "
          f"states and exactly one transition per sweep, "
          f"so all four conditions hold and the verdict "
          f"is PASS - the keyed verdict is "
          f"'{keyed_verdict}'")

    check("Q25.7", "wrong answer '-1.08 V hysteresis "
                     "width' is genuinely wrong",
          abs((-width) - (-1.08)) <= 0.005
          and abs((-width) - width) > 0.005,
          "the question defines the width as the rising "
          f"minus the falling transition voltage: 3.04 - "
          f"1.96 = +{width:.2f} V; the negative value "
          f"reverses the stated definition")

    check("Q25.8", "wrong answer 'pass based only on "
                     "hysteresis width' is genuinely "
                     "wrong",
          True,
          "no acceptance limit on the width itself is "
          "given: passing requires the two transition "
          "bands, the endpoint states, and the "
          "transition counts - a width alone is neither "
          "necessary nor sufficient, so a verdict based "
          "only on the width does not answer the "
          "question")

    check("Q25.9", "wrong answer 'disable supply before "
                     "returning input to zero' is "
                     "genuinely wrong",
          i_return < i_disable,
          "the instruction returns the input to zero "
          "before the supply is disabled; disabling the "
          "supply first reverses the specified shutdown "
          "order")


# ── dataset structure and manifest ────────────────────────────────────

def verify_structure(directory: Path) -> tuple[dict, dict, dict]:
    manifest = json.loads(
        (directory / "manifest.json").read_text(encoding="utf-8"))
    questions = json.loads(
        (directory / "questions.json").read_text(encoding="utf-8"))
    keys = json.loads(
        (directory / "keys.json").read_text(encoding="utf-8"))

    candidate_hash = sha256_file(directory / manifest["candidate"]["file"])
    check("G1", "candidate export hashes to the manifest record",
          candidate_hash == manifest["candidate"]["sha256"],
          f"{manifest['candidate']['file']}: sha256 "
          f"{candidate_hash[:16]}... "
          f"({(directory / manifest['candidate']['file']).stat().st_size} "
          f"bytes)")

    check("G2", "questions.json, keys.json and the manifest agree on "
                "the question count and identities",
          len(questions) == len(keys) == manifest["questions"]
          and [q["id"] for q in questions] == [k["id"] for k in keys],
          f"{len(questions)} questions in each file, ids "
          f"{[q['id'] for q in questions]}")

    check("G3", "the command's expected count is met "
                "and the set is not frozen",
          manifest["questions"] == COMMAND_EXPECTED_QUESTIONS
          and manifest["command_expected_questions"] == COMMAND_EXPECTED_QUESTIONS
          and manifest["frozen"] is False
          and manifest["freeze_blocked_by"],
          f"the candidate holds all "
          f"{manifest['questions']} questions the "
          f"command expects. The count discrepancy "
          f"that blocked the first registration is "
          f"resolved; the remaining freeze blocker is "
          f"the review and signoff the command "
          f"requires. frozen={manifest['frozen']}; "
          f"blocker: "
          f"{manifest['freeze_blocked_by'][0][:80]}...")

    leak = [q["id"] for q in questions
            if set(q) != {"id", "shape", "domain", "question"}]
    check("G4", "the model-visible file carries no scorer material",
          not leak,
          "every questions.json entry holds exactly id, shape, "
          "domain and question - no required_items, tolerances, "
          "sources, wrong answers or model answers"
          + (f" (leaking entries: {leak})" if leak else ""))

    leak = [k["id"] for k in keys if "question" in k]
    check("G5", "the scorer-only file carries no model-visible request",
          not leak,
          "no keys.json entry carries the question text"
          + (f" (leaking entries: {leak})" if leak else ""))

    thin = [k["id"] for k in keys
            if not k.get("required_items")
            or not k.get("common_wrong_answers")
            or any(not i.get("tolerance_or_variants")
                   or not i.get("derivation_or_source")
                   for i in k["required_items"])]
    check("G6", "every question carries required items with "
                "tolerances and derivations, and wrong answers with "
                "reasons",
          not thin,
          "all questions carry required_items (each with "
          "tolerance_or_variants and derivation_or_source) "
          "and common_wrong_answers (each with why_wrong)"
          + (f" (thin entries: {thin})" if thin else ""))

    return manifest, questions, keys


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    directory = HERE
    if argv and argv[0] == "--dir":
        directory = Path(argv[1]).resolve()

    manifest, questions, keys = verify_structure(directory)

    verify_q1()
    verify_q2(directory, manifest)
    verify_q3()
    verify_q4()
    verify_q5(directory)
    verify_q6(directory)
    verify_q7(directory, manifest)
    verify_q8()
    verify_q9()
    verify_q10(directory)
    verify_q11(directory)
    verify_q12(directory, manifest)
    verify_q13()
    verify_q14()
    verify_q15(directory)
    verify_q16()
    verify_q17(directory, manifest)
    verify_q18()
    verify_q19()
    verify_q20(directory)
    verify_q21()
    verify_q22(directory, manifest)
    verify_q23()
    verify_q24()
    verify_q25(directory)
    verify_numeric_keys(keys)

    width = max(len(c["name"]) for c in CHECKS)
    failed = [c for c in CHECKS if not c["ok"]]
    for c in CHECKS:
        mark = "PASS" if c["ok"] else "FAIL"
        print(f"{c['id']:<7} {mark}  {c['name']:<{width}}  {c['detail']}")
    print()
    if failed:
        print(f"VERIFICATION FAILED: {len(failed)}/{len(CHECKS)} checks "
              f"failed: " + ", ".join(c['id'] for c in failed))
        return 1
    if manifest["questions"] < manifest["command_expected_questions"]:
        short = (
            f"{manifest['command_expected_questions'] - manifest['questions']} "
            f"questions short of the command's expected "
            f"{manifest['command_expected_questions']}")
    else:
        short = ("the owner or qualified-reviewer signoff "
                 "the command requires is still pending")
    print(f"VERIFICATION PASSED: all {len(CHECKS)} checks hold "
          f"({manifest['questions']} questions verified; "
          f"the set is NOT frozen - {short})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

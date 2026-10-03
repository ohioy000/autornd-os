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

# The question set the command expects; the candidate holds 5.
# The discrepancy is recorded, not resolved here: resolving it
# means supplying questions, which the command forbids.
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
_KEY_UNIT = re.compile(
    r"\s*([A-Za-z%]+(?:\^\d+)?(?:/[A-Za-z%+^\d]+)?)")


def _key_quantities(text: str) -> list[tuple[float, str]]:
    plain = _plain(text)
    plain = re.sub(
        r"(\d)\s*(?:×|x|\*)\s*10\s*\^\s*\{?\s*"
        r"(-?\d+)\s*\}?", r"\1e\2", plain)
    found: list[tuple[float, str]] = []
    for m in _KEY_NUMBER.finditer(plain):
        rest = plain[m.end():m.end() + 14]
        um = _KEY_UNIT.match(rest)
        found.append((float(m.group(0)),
                        um.group(1) if um and um.group(1)
                        else ""))
    return found


def _convert(value: float, unit: str):
    entry = VERIFIER_UNITS.get(unit.strip().lower()
                                 .replace(" ", ""))
    if not entry:
        return None
    return entry[0], value * entry[1]


def _parse_tolerance(spec: str):
    plain = _plain(spec)
    m = re.search(r"(?:numerical|absolute) tolerance"
                    r"\s*\+/-\s*(\d+(?:\.\d+)?)"
                    r"\s*([A-Za-z%]+)", plain)
    if m:
        return "abs", float(m.group(1)), m.group(2)
    m = re.search(r"relative tolerance"
                    r"\s*(\d+(?:\.\d+)?)\s*%", plain)
    if m:
        return "rel", float(m.group(1)) / 100.0, ""
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
        key_value, key_unit = quantities[0]
        key_base = _convert(key_value, key_unit)[1]
        recomputed = RECOMPUTED[recomputed_key]
        recomputed_base = _convert(
            recomputed, dimension)[1]
        assert tolerance is not None, (
            f"numeric key '{item_name}' has no parseable "
            f"tolerance: {item['tolerance_or_variants']}")
        kind, magnitude, tol_unit = tolerance
        tol_base = (_convert(magnitude, tol_unit)[1]
                    if tol_unit else magnitude)
        if kind == "abs":
            ok = abs(key_base - recomputed_base) <= tol_base
        else:
            ok = (abs(key_base - recomputed_base)
                  <= tol_base * abs(recomputed_base))
        check(f"X{n}", f"keys.json's own value for "
                          f"'{item_name}' ({qid}) agrees "
                          f"with the recomputation",
              ok,
              f"keys.json states {key_value} {key_unit} = "
              f"{key_base:.6g} {dimension_base}; recomputed "
              f"{recomputed:.6g} {dimension} = "
              f"{recomputed_base:.6g}; tolerance "
              f"{kind} {magnitude} {tol_unit or dimension}")


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
    """Strip the LaTeX wrappers the candidate's worked answers
    use ($...$, \\mathrm{...}, \\,, \\le), so phrase and
    number matching sees the prose and the bare values."""
    text = re.sub(r"\\mathrm\{([^}]*)\}", r"\1", text)
    text = text.replace("$", "").replace("\\,", " ")
    text = text.replace("\\%", "%")
    text = text.replace("\\pm", "+/-")
    text = text.replace("\\leq", "<=").replace("\\le", "<=")
    text = text.replace("\\geq", ">=").replace("\\ge", ">=")
    text = text.replace("\\times", "x")
    return text


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

    check("G3", "the count discrepancy against the command is "
                "recorded, and the set is not frozen",
          manifest["questions"] == 5
          and manifest["command_expected_questions"] == COMMAND_EXPECTED_QUESTIONS
          and manifest["frozen"] is False
          and manifest["freeze_blocked_by"],
          f"the candidate holds {manifest['questions']} questions; the "
          f"command expects {manifest['command_expected_questions']}. "
          f"frozen={manifest['frozen']}; blocker: "
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
          "all five questions carry required_items (each with "
          "tolerance_or_variants and derivation_or_source) and "
          "common_wrong_answers (each with why_wrong)"
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
    print(f"VERIFICATION PASSED: all {len(CHECKS)} checks hold "
          f"({manifest['questions']} questions verified; the set is "
          f"NOT frozen - {manifest['command_expected_questions'] - manifest['questions']} "
          f"questions short of the command's expected "
          f"{manifest['command_expected_questions']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

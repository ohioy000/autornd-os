# Pre-registration — ARCH-20260930-094: first live reading of D36/D37

Committed BEFORE any spend on this command. The paid run is n=1 under a
one-dollar cap and waits for the owner's explicit authorisation.

## Setup

- Branch `arch/20260930-094-cup-grounded-test`, on main at `7dc26e9` (D36+D37 merged via PR #100).
- Corpus `docs/cupline/` (three files, verbatim per the command), profile
  `profiles/cupline.yaml` (name Cupline; changes nothing but the docs
  directory — no domains, roles, checks, constraints or structural roles),
  scenario `conv_cup_line_sensor_grounded.yaml` (request byte-identical to
  `conv_cup_line_sensor.yaml`; timeout 3600; max_calls 40; figures_present
  on 23.995 / 0.00483 / LV-N11N / 214).
- Run shape: `AUTORND_PROFILE=cupline`, workflow engineering-rnd,
  `--max-spend 1.00 --max-spend-sweep 1.00`, owner's current `.env` lineup
  (recorded by the results header as usual).

## Answer key (the advisor's, verbatim)

(1) supply 24 VDC, identical in every section; (2) 22 AWG, identical in every section; (3) voltage drop = 2 x 3 ft x 16.1 ohm/1000 ft x 0.05 A = 0.00483 V (4.83 mV), with the arithmetic shown; (4) voltage at the sensor head 24 - 0.00483 = 23.995 V nominal, and 22.795 V at the 22.8 V rail minimum, both passing the 21.6-26.4 V threshold; (5) output NPN open-collector, matching the CF-IO8 inputs, with the match cited from the docs rather than labelled an unverified assumption; (6) part number Keyence LV-N11N and unit cost $214.00, identical everywhere; (7) commissioning thresholds exactly as the docs state: 21.6-26.4 V at the head, and 150 of 150 marks in 60 s at 150 cups per minute.

## Predictions (the advisor's, verbatim)

P1: triage reads medium risk (085 read medium, n=1). P2: the first grounding carries the cupline docs, the plan names no blockers, and D37 does not fire (regrounding rounds 0), so this run is D37's control, not a test of it firing. P3: all seven answer-key items are correct in the final implementation. P4: the deterministic consistency check passes on the final iteration. P5: status is completed within 40 calls and $1.00. P6: no prediction that it finishes inside 3,600 s on the current judge serving; a deadline stop is possible and would be recorded as a stop, not as a verdict on the answer. Falsifiers: a key item wrong while the docs were in context means grounding or judging failed on a closed-world question; D37 firing (rounds 1) means the plan named a blocker the docs already answer, so record which one.

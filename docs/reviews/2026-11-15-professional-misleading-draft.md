# A set of questions where a summary misleads: draft for the owner's sign-off (2026-11-15)

Step 4 of the plan the owner approved in `docs/carryover-2026-11-15.md`. This is the set only.
**No run is made on it until the owner signs the keys (D44).** The runner refuses it while its
status says draft.

File: `evals/professional/misleading-questions.json`, version professional-misleading-1.

**Signed by the owner on 2026-11-15, all 12 keys; the set is approved and frozen. The owner chose
run C. The run is preregistered in `docs/preregistration-20261115-misleading-set-run.md`.**

## The point

- **12 questions,** each chosen because the common answer is a figure that is still printed on
  a live official page: an older edition, a sister rule, last year's rate.
- **Every key passage was found on its live source today,** with the harness's own fetch and
  quote check: `python -I evals/professional/verify_keys.py . misleading-questions.json`, 12 of
  12 hold.
- **The misleading pages were checked too.** Five questions name a live page that still prints
  the other figure. `verify_keys.py` now checks those and says when one has gone.
- **Two decisions are the owner's:** the keys, and the size of the run. They are at the end.

## The questions

| | Question, in short | Key | The figure that misleads, and where it still stands |
|---|---|---|---|
| M1 | BasicMed aircraft limits | 12,500 pounds, 7 occupants, 6 passengers | 6,000 pounds, 6 and 5: the FAA's own advisory circular AC 68-1A, still served |
| M2 | PM2.5 primary standards | 9.0 µg/m³ annual, 35 µg/m³ 24-hour | 12.0: section 50.18, still in the code beside 50.20 |
| M3 | Hours for a passenger-carrying driver | 10 hours driving, after 8 off duty, none after 15 on duty | 11, 10 and 14: the property-carrying rule, 395.3 |
| M4 | Fall protection height, general industry | 4 feet (1.2 m) | 6 feet: the construction rule, 1926.501 |
| M5 | Rest for a Part 135 flight attendant | at least 9 consecutive hours, reducible to 8 | 10, not reducible: the airline rule, 121.467 |
| M6 | VFR fuel reserve for a helicopter | at least 20 minutes | 30 and 45: the airplane figures of the same section |
| M7 | The current HTTP/2 specification | RFC 9113, obsoletes 7540 and 8740 | RFC 7540, still widely cited |
| M8 | The RFC that deprecated TLS 1.0 and 1.1 | RFC 8996; the old RFCs are Historic | RFC 7525, RFC 8446 |
| M9 | UK National Living Wage from April 2026 | £12.71; £10.85 for 18 to 20 | £12.21 and £10 (last year), £13.21 and £11.27 (next year), all on the same page |
| M10 | Social Security wage base for 2026 | $184,500 | $176,100 (2025) and $192,300 (2027), in the same table |
| M11 | Short-haul exception: radius and hours | 150 air-mile radius, 14 consecutive hours | 100 air-miles and 12 hours, the rule before September 2020 |
| M12 | 401(k) elective deferral limit for 2026 | $24,500 | $23,500 (2025) |

- **M5 is H1 turned round.** On the harder set the wrong answer was 9 hours where the airline
  rule says 10. Here 9 is right, and a harness that has learned to say 10 is wrong.
- **M4 and M6 are sisters of P8 and P1** of the first set, which ask the construction height
  and the airplane reserve.
- **M9, M10 and M12 depend on the year.** Each question names its year. M9 and M10 have next
  year's figure on the same page already.

## What was left out, and why

- **The lead action level in drinking water.** The code now prints 0.010 mg/L, and systems must
  meet it from 1 November 2027; until then 0.015 applies. A fair question, but the right key is
  arguable, and a set's keys must not be.
- **The overtime salary threshold.** A court set the 2024 rule aside and the code's text does
  not show it. The same objection.
- **Questions already in the two frozen sets,** the flight attendant under Part 121 among them.

## What the architect asks of the owner

1. **Sign the 12 keys,** or strike any. On the owner's word the status becomes "Approved by the
   owner … and frozen" and the runner will take the set.
2. **Choose the size of the run.** The plan says at least 12 answers a question a side, inside
   '$3'. At the comparison's cost of about '$0.013' an answer, that does not fit all 12
   questions:

   | | Answers | Expected | |
   |---|---|---|---|
   | A | 8 questions, 2 lookups, 12 each: 192 | about '$2.50' | inside the '$3' approved; which 4 questions wait is then to choose |
   | B | 12 questions, 2 lookups, 12 each: 288 | about '$3.75' | needs about '$0.75' more than approved |
   | C | B, and a third arm with the second request for documents: 432 | about '$5.60' | needs about '$2.60' more; it is the only way to measure step 3 on answers |

   **The architect advises B.** Dropping four questions weakens the one thing this run is for.
   The third arm can wait: the run's record will show free how often the second request would
   have fired, and that says whether C is worth its money.
3. **The reading.** One reader has read every run so far. D50 asks for two.

A preregistration with the amount and the stop is written and pushed before the run, once 1 and
2 are answered.

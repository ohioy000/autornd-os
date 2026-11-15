# Seventeen harder professional questions, a draft for the owner's sign-off (2026-11-15)

The owner's word of 2026-11-15: harder questions, the difficulty from all angles, vague where it
helps, the harness left to find the document itself, and other formats such as EPUB. They are in
`evals/professional/draft-hard-questions.json`. **Nothing here is a key until the owner approves
it** (D44). No run has used them.

## Why a harder set

The first set's baseline was 45 of 45 right. A set the harness cannot get wrong cannot show how
it behaves when it is wrong, which is the thing its warnings exist for.

## Where the difficulty comes from

| Angle | Questions |
|---|---|
| The rule or standard is not named; the harness must find the document | H1, H2, H3, H4, H5, H6, H7, H8, H16, H17 |
| Loosely or colloquially worded | H1, H3, H16 |
| The answer is a row of a table | H5, H8, H12 |
| The source is not a web page: EPUB, PDF, JSON record, CSV registry, plain text | H11; H12, H13; H9; H10; H6 |
| Two documents, or a figure the sources do not state themselves | H4, H8, H13 |
| An older figure is still widely quoted, or the rule changed recently | H1, H7, H8, H11 |
| A near answer sits beside the right one | H3, H5, H9, H16, H17 |
| Reasoning over the text, not a look-up of one figure | H15 |
| The rule does not answer the question, and the right answer says so | H14 |

## The set

| Id | Field | Question | Key |
|---|---|---|---|
| H1 | airline cabin crew | how much rest does a US airline have to give a flight attendant between duty days | Rest after a duty period of 14 hours or less: at least 10 consecutive hours; Reduction: may not be reduced to less than 10 consecutive hours |
| H2 | commercial driving | At what alcohol concentration is a US commercial motor vehicle driver barred from safety-sensitive duty under the federal drug and alcohol testing rules? | Alcohol concentration: 0.04 or greater |
| H3 | unmanned aircraft | how heavy can a drone be and still count as a small drone under the FAA rules | Weight: less than 55 pounds on takeoff; Counted: everything on board or otherwise attached |
| H4 | UK employment law | How much paid annual leave does a worker in Great Britain get by statute, in weeks, and what is the cap in days? | Basic leave: four weeks; Additional leave: 1.6 weeks; Total: 5.6 weeks; Cap: 28 days |
| H5 | flight operations | What are the basic VFR weather minimums in Class E airspace below 10,000 feet MSL: flight visibility and distance from clouds? | Flight visibility: 3 statute miles; Distance from clouds: 500 feet below, 1,000 feet above, 2,000 feet horizontal |
| H6 | network engineering | In the original DNS specification, what are the size limits on a label and on a full domain name, in octets? | Label: 63 octets or less; Name: 255 octets or less |
| H7 | industrial hygiene | What are OSHA's permissible exposure limit and action level for respirable crystalline silica in general industry? | Permissible exposure limit: 50 µg/m3, as an 8-hour TWA; Action level: 25 µg/m3, as an 8-hour TWA |
| H8 | drinking water | What is the US federal maximum contaminant level for PFOA in drinking water? Give it as the rule lists it and in nanograms per litre. | As listed: 0.0000040 mg/l; In ng/L: 4.0 ng/L |
| H9 | software security | What CVSS version 3.1 base score and severity does the US National Vulnerability Database give CVE-2021-44228? | Base score: 10.0; Severity: CRITICAL |
| H10 | web protocols | In the IANA HTTP status code registry, what is the name of status code 425 and which RFC is its reference? | Name: Too Early; Reference: RFC 8470 |
| H11 | meeting procedure | In Robert's Rules of Order as first published in 1876, the pocket manual that Project Gutenberg carries, what vote does the manual require to adopt a motion for the Previous Question? | Vote: a two-thirds vote |
| H12 | electronics | From Texas Instruments' LM317 datasheet: what is the absolute maximum input-output voltage differential, and what is the typical reference voltage? | Absolute maximum input-output differential: 40 V; Typical reference voltage: 1.25 V |
| H13 | metrology | In the SI Brochure, 9th edition, what value is fixed for the luminous efficacy Kcd, and for monochromatic radiation of what frequency? | Kcd: 683 lm/W; Frequency: 540 × 10^12 Hz |
| H14 | aviation | Under 14 CFR § 91.151, what fuel reserve must a glider carry to begin a flight under VFR conditions? | Glider reserve: none is stated: the section sets reserves for airplanes and for rotorcraft only |
| H15 | hazardous materials transport | A liquid has a flash point of 65 °C and meets the definition of no other hazard class. For transport under the US hazardous materials regulations, is it a Class 3 flammable liquid, and if not, what is it? | Class 3 flammable liquid?: no: its flash point is above 60 °C (140 °F); What it is: a combustible liquid: flash point above 60 °C (140 °F) and below 93 °C (200 °F) |
| H16 | commercial trucking | how long can a trucker drive before they have to take a break | Driving time before a break: 8 hours; The break: at least a consecutive 30-minute interruption in driving status |
| H17 | radiation protection | What dose limits does the US Nuclear Regulatory Commission set for individual members of the public from a licensee's operations: per year, and in any one hour in an unrestricted area? | Per year: 0.1 rem (1 mSv); In any one hour: 0.002 rem (0.02 millisievert) |

## How each key was made

- Written from the source itself, fetched on 2026-11-15 with the harness's own fetch, which read
  every format here: the EPUB, both PDFs, the JSON record and the CSV.
- `evals/professional/verify_keys.py . draft-hard-questions.json` fetches every source again and
  checks each passage with the harness's own quote check, and each key figure against the page:
  17 of 17 on 2026-11-15. Free.
- A key item marked `derived` is worked out from the sources: the sum in H4, the unit conversion
  in H8, the exponent in H13, the absence in H14. Its figures need not be on a page.
- Each entry names the answer most easily confused with the right one.

## What the owner should know before approving

- **H14 is a trap on purpose.** The section sets no fuel reserve for gliders. A right answer says
  so; an answer that gives the airplane's or the rotorcraft's figure is wrong.
- **H9 and H10 name live registries.** If the registry changes, the key changes with it;
  `verify_keys.py` shows that.
- **H11's source is one edition on one site.** That is the point of the question.
- **Still not here:** paywalled standards, and sources not in English.
- **No automatic screen.** As with the first set, a run is read by hand against the keys.

## What the owner is asked

1. Approve, change or strike each key. An approved set is frozen as its own version.
2. Then a run on main: 17 questions, 3 answers each, about '$0.80' at the first set's cost an
   answer and likely somewhat more, with a stop stated before the run. About '$5.42' of the
   owner's '$7' is spent.

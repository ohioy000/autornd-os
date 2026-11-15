# Fifteen professional lookup questions, a draft for the owner's sign-off (2026-11-15)

The owner's word of 2026-11-15: draft professional-style lookup questions, vastly varied, no set
discipline. They are in `evals/professional/draft-questions.json`. **Nothing here is a key until
the owner approves it** (D44). No run has used them.

## Why

- Only 5 of the 25 tier-2 questions use a lookup, and 4 of those are OSHA rules.
- A professional's question is most often "what does this rule or standard say?".
- Every lookup result so far rests on those 5 questions and one request of the owner's.

## How each key was made

- Each question names its rule, standard or specification, as a professional would.
- Each key was written from the source's own page, fetched on 2026-11-15 with the harness's own
  fetch, and holds the governing passage word for word.
- `evals/professional/verify_draft.py` fetches every source again and checks the passage with the
  harness's own quote check, and that every figure in the key is on the page: 15 of 15 on
  2026-11-15. It is free.
- Each entry also names the answer most easily confused with the right one.

## The set

| Id | Field | Source | What is asked | Key |
|---|---|---|---|---|
| P1 | aviation | US CFR (eCFR) | Under 14 CFR § 91.151, how much fuel beyond the first point of intended landing must an airplane carry to begin a flight? | Day reserve: 30 minutes; Night reserve: 45 minutes |
| P2 | commercial trucking | US CFR (eCFR) | Under 49 CFR § 395.3(a), for a driver of a property-carrying commercial motor vehicle: how many consecutive hours off du? | Off duty before driving: 10 consecutive hours; On-duty window: 14 consecutive hours; Driving time: 11 hours |
| P3 | health privacy | US CFR (eCFR) | Under 45 CFR § 164.404(b), by when must a covered entity notify an individual of a breach of unsecured protected health ? | Standard: without unreasonable delay; Outer limit: 60 calendar days; Runs from: discovery of the breach |
| P4 | consumer lending | US CFR (eCFR) | Under 12 CFR § 1026.23(a)(3)(i), until when may a consumer exercise the right to rescind a covered credit transaction, a? | Rescission period: midnight of the third business day; Measured from: the last of consummation, delivery of the notice, delivery of all material disclosures; If never delivered: 3 years after consummation |
| P5 | radio | US CFR (eCFR) | Under 47 CFR § 97.313, what is the general maximum transmitter power for an amateur station, and what lower limit applie? | General limit: 1.5 kW PEP; 10.10-10.15 MHz: 200 W PEP |
| P6 | radiation protection | US CFR (eCFR) | Under 10 CFR § 20.1201(a), what are the annual occupational dose limits for an adult: the total effective dose equivalen? | Total effective dose equivalent: 5 rems (0.05 Sv); Lens of the eye: 15 rems (0.15 Sv); Skin of the whole body: 50 rem (0.5 Sv) |
| P7 | hazardous materials transport | US CFR (eCFR) | Under 49 CFR § 173.120(a), what flash point defines a Class 3 flammable liquid? | Flash point: not more than 60 °C (140 °F) |
| P8 | construction safety | US CFR (eCFR) | Under 29 CFR § 1926.501(b)(1), at what height above a lower level must an employee on a walking/working surface with an ? | Height: 6 feet (1.8 m) or more; Systems: guardrail systems, safety net systems, or personal fall arrest systems |
| P9 | network engineering | IETF RFC | Which three blocks of IPv4 address space does RFC 1918 reserve for private internets? | Block 1: 10.0.0.0 - 10.255.255.255 (10/8); Block 2: 172.16.0.0 - 172.31.255.255 (172.16/12); Block 3: 192.168.0.0 - 192.168.255.255 (192.168/16) |
| P10 | UK employment law | UK legislation | Under regulation 4(1) of the Working Time Regulations 1998 (UK), what is the limit on a worker's average working time, o? | Limit: an average of 48 hours for each seven days; Opt-out: the worker's agreement in writing, obtained first by the employer |
| P11 | air quality | US CFR (eCFR) | Under 40 CFR § 50.19, what is the level of the national 8-hour primary ambient air quality standard for ozone, and when ? | Level: 0.070 ppm, daily maximum 8-hour average; Met when: the 3-year average of the annual fourth-highest daily maximum 8-hour average concentration is less than or equal to 0.070 ppm |
| P12 | pharmaceutical manufacturing | US CFR (eCFR) | Under 21 CFR § 211.180(a), how long must a production, control, or distribution record specifically associated with a ba? | Retention: at least 1 year after the expiration date of the batch; OTC without expiration dating: 3 years after distribution of the batch |
| P13 | employment leave | US CFR (eCFR) | Under 29 CFR § 825.200(a), how much FMLA leave is an eligible employee entitled to, over what period, leaving aside leav? | Entitlement: 12 workweeks; Period: any 12-month period |
| P14 | information security | NIST | In NIST SP 800-63B-4, what minimum length must verifiers require for a password used as a single-factor authentication m? | Single-factor minimum: 15 characters; Multi-factor minimum: eight characters; Maximum to permit: at least 64 characters |
| P15 | email protocol | IETF RFC | Under RFC 5321 section 4.5.3.1, what is the maximum total length of an SMTP text line and of a reply line, and what do t? | Text line: 1000 octets, including the <CRLF>; Reply line: 512 octets, including the reply code and the <CRLF> |

## What is varied, and what is not

- **Fields:** fifteen, from aviation fuel to email protocol; no two the same.
- **Kinds of source:** four. Eleven are US federal rules on one site, two are internet standards
  in plain text, one is UK law, one is a NIST guideline. Standards that sit behind a paywall (ISO,
  IEC, ASME, NFPA) are left out: no key can be checked against a page nobody can read.
- **Kinds of answer:** single figures, pairs, a three-row list, a figure with its condition, and
  two that need the right edition of a document that changed (P11, P14).
- **Not here:** tables as the answer, PDFs as the only source, and sources not in English. Those
  are known weak spots and deserve their own questions once this set is in use.

## What the owner is asked

1. Approve, change or strike each key. An approved set is frozen and gets a version.
2. Then a baseline on main as it stands: 15 questions, 3 answers each, about '$0.90', with a
   stop stated before the run. It needs the owner's word.
3. The set has no automatic screen yet. The first baseline would be read by hand against the
   keys, which is what D50 asks for anyway.

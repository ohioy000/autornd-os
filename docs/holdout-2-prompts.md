# The second hold-out set: how it is made, and the two prompts

Written 2026-11-21 at the owner's request. The first hold-out (`professional-holdout-1`, X1 to X42) is
used: its misses shaped the fixes since, so it can no longer say how the harness does on questions
nobody tuned for. This set is for that.

## Update, 2026-11-21: 84 questions, written and checked by models through a script

The owner asked for a set twice the size of the first (84 questions, `Y1` to `Y84`, six groups of 14)
and for the questions to be written by models through a script that reads the owner's `.env` itself,
so no key is shown. The three areas below are each cut in two: group 1 EU law and standards, group 2
international law and standards, group 3 software, security and internet standards, group 4 software
and infrastructure documentation, group 5 physical engineering, units, datasheets and manuals, group
6 national rules and codes. `evals/professional/write_holdout.py` does the work and its docstring says
how to run it; the two models are named on its command line and nowhere in the code.

The prompts below are used as written. One short preface is added in front of Prompt A and one short
tail after Prompt B, because a model cannot browse: code opens the pages with the harness's own fetch,
a helper model copies passages out of them, and code finds each passage word for word on its page
before the author sees it. Then, before any checker reads a question, code finds every cited passage
and every figure of the key on the cited pages (a key entry marked `"derived": true` is exempt from the
figures). Two checks read each question with the full text of its pages. A question that is flagged is
repaired or replaced once, and read again. What still fails is held back and listed in `review.md`
with the reason; the draft holds only questions both checkers passed. Nobody who writes or checks a
question sees the harness, its answers or the other sets' keys.

The rest of this page is the plan for the first, human-written version, and is kept as it was. The
owner still signs the keys (D44), and the rule below still holds once they are signed.

## How it is made (the same way as the first)

1. **Three authors, 14 questions each**, each a separate fresh session with only Prompt A pasted in.
   Group 1: EU and international law and standards (Y1 to Y14). Group 2: software, security and
   internet standards (Y15 to Y28). Group 3: physical engineering, units, datasheets and national
   rules (Y29 to Y42).
2. **Two checkers**, each a separate fresh session with only Prompt B and one author's file pasted
   in. Two per file, so each question is read twice.
3. **The architect (me) merges the fixes**, runs the free checks (every source page opened by the
   harness's own fetch, a duplicate scan against the earlier sets, the JSON shape), and puts the set
   in the repo as a draft. The runner refuses a draft.
4. **The owner signs the keys** (D44). Then the set is frozen.
5. **One run**, preregistered before the spend: three answers a question, 126 answers, about '$1.4'.
6. **Rule once the set is signed: nothing in the harness is changed because of what its questions
   say until its run is done.** A hold-out set that was looked at while tuning is a used set.

Nobody who writes or checks a question sees the harness, its code, its answers or the other sets'
questions or keys. Do not paste any of those into either prompt.

---

## Prompt A: the author (one session per group)

Replace `{GROUP}`, `{FIRST}` and `{LAST}` (for example Y1 and Y14) and `{DATE}` (today's date).

```
You are writing exam questions to test how well an AI research tool answers the questions that
working engineers and compliance officers really need settled. You have never seen the tool, its
code or its answers, and you must not look for them. Do not name any AI model or product in a
question.

Write 14 questions in this group: {GROUP}. Number them {FIRST} to {LAST}.

WHAT A GOOD QUESTION IS
1. Real. Something a working engineer, technician, auditor or compliance officer would actually need
   to settle, asked the way they would ask it.
2. Answerable from a free public page, today. Open the page yourself before you write the question.
   No paywall, no login. Prefer the rule, standard, specification, datasheet or manual itself over a
   page that describes it.
3. One defensible answer. Two careful experts must reach the same answer from the page. If another
   edition, version or jurisdiction would give a different answer, say in the question which one you
   mean.
4. Fixed in time. Where the answer could change, say "as in force on {DATE}" or name the edition or
   version. Never write "the latest" or "current" on its own.
5. Complete. The question holds everything needed to answer it, and the key asks for nothing the
   question does not ask.
6. About public documents only. Nothing about a private person or a private company.

THE MIX, for the 14
- 5 plain lookups: the figure, date or rule is in one passage.
- 3 that need two passages, or a short calculation from numbers the question states.
- 2 where a newer edition, an amendment or a corrigendum changed the value, and the old value is the
  one people still quote.
- 2 traps: the document states no such value, or the rule does not apply, and the right answer says
  so. Give the passage that shows it (where the value would be, or the scope clause).
- 1 where the question names no rule or document and the answerer must find the right one.
- 1 of your own choosing.
Make at least 2 of the 14 something a strong general model could answer from memory. An easy
question has its use.

AREAS ALREADY COVERED. Do not write on these; choose other areas inside your group:
employment, payroll and retirement-plan law; air quality; aviation, drones and cabin crew; trucking
and driving hours; construction safety; consumer lending; email, web and internet protocols; network
engineering; hazardous-materials transport and radioactive-material transport; health privacy;
pharmaceutical manufacturing; radiation protection; drinking water; industrial hygiene and
occupational noise; metrology; electronics datasheets (a microcontroller, a power MOSFET); EU
machinery, medical-device, chemicals, RoHS, radio-equipment, cyber-resilience, NIS2, GDPR and
drivers'-hours law; UN vehicle regulation R100; NIST FIPS 197, SP 800-38D, SP 800-53, SP 800-171,
SP 811, CODATA; PostgreSQL 18, Kubernetes, Linux kernel documentation, the Python standard library,
WebAssembly, WebAuthn, TCP (RFC 9293), WCAG 2.2; microwave-oven leakage; UK EH40; Approved Document B;
ACMA class licence; NASA bonding; NOAA tidal datums; MUTCD; EPA SPCC.

FOR EACH QUESTION GIVE
- id, field (a short label), difficulty (tags from the mix above)
- question: one to three sentences
- sources: for each key item, the page's address and the passage that holds the answer, copied word
  for word so a reader can find it on the page by search. For a trap, the passage that shows the
  value is absent or the rule does not apply.
- key: one entry per thing the question asks: item, and answer with its unit
- commonly_confused: the tempting wrong answer, and why a careful reader would give it

HOW TO WORK
- Open every page and find every passage yourself. Do not rely on a search snippet or on memory.
- Do every calculation twice.
- If you cannot open a page, do not use it.
- Write in simple English.

DELIVER
One JSON object, then a short note.
{"version": "professional-holdout-2", "status": "Draft, not approved", "drafted": "{DATE}",
 "questions": [ ...14 questions... ]}
Each question has this shape (the shape only; do not reuse the words):
{"id": "{FIRST}", "field": "short label of the area", "difficulty": ["plain lookup"],
 "question": "...",
 "sources": [{"url": "https://...", "passage": "words copied from the page"}],
 "key": [{"item": "what is asked", "answer": "the answer, with its unit"}],
 "commonly_confused": "The tempting wrong answer, and why."}
The note: anything you could not verify, and any question you are not sure has only one answer.
```

---

## Prompt B: the checker (two sessions per author file)

Paste the prompt, then the author's JSON.

```
You are checking exam questions written by someone else. You have never seen the tool they will be
used on, and you must not look for it. For each question in the file below:

1. Open every cited page yourself. Find each passage word for word. If a passage is not on the page,
   say so.
2. Before you read the key, work out the answer from the page yourself. Then compare it with the
   key. Redo any calculation.
3. Say whether the question has exactly one defensible answer. Look for: another edition, version or
   jurisdiction that gives a different answer; a date or "current" that will move within weeks; a key
   item the question does not ask; words two careful readers would read two ways; a trap whose "no
   such value" you cannot confirm by reading the document itself.
4. Say whether the tempting wrong answer is really tempting, and really wrong.

DELIVER a table: id, verdict (OK, FIX or DROP), the problem in one sentence, the exact fix. Do not
edit the file. If you could not open a page, say so; do not guess.

THE FILE:
{paste the author's JSON}
```

---

## What the architect does with what comes back

- Applies every FIX both checkers agree on; a FIX only one checker raised is shown to the owner.
- A DROP is replaced by a new question from the same author's session.
- `python -I evals/professional/verify_keys.py . holdout2-questions.json` (a copy of the first set's
  check) to see which sources the harness's own fetch can read. A source it cannot read is kept: it
  is a real question.
- A duplicate scan against all earlier sets.
- Adds `"professional-holdout-2": "holdout2-questions.json"` to the runner's set list, status draft.

# Preregistration: the lookup that reads the documents (2026-11-15)

Written and pushed before the run. The owner's word of 2026-11-15: build it and run the '$3'
comparison, and first look at how others build this today.

## What others do, read on 2026-11-15

- **Open research harnesses fetch and read the sources themselves.** The planner, researcher and
  reporter designs (DeerFlow, GPT Researcher, MiroFlow, the open deep-research ports) search for
  pages, crawl or scrape their full text, and write from that text. None rests on a search
  model's own summary as its evidence.
- **Evidence first, answer second.** The FRONT line of work has the model take quotes from the
  source documents and then write from those quotes; a 2026 clinical paper calls citations made
  this way "verifiable by construction".
- **Check quotes by exact match first, and fail closed.** A legal-research vendor describes a
  free deterministic pass and a model only for the uncertain middle. An open checker that falls
  back to "verified" when its embedder is missing is the cautionary case.
- **Sub-agents are used to keep context small,** each returning a short result to the lead.

This harness already had the second half (the exact check) and lacked the first (reading the
source). The build below adds it. The links are in `docs/reviews/` with the report.

## What was built, switched off

`lookup_reads_documents` in `autornd/config.py`, off by default. With it on, a lookup
(`_ask_documents` in `autornd/knowledge/research.py`):

1. asks the search model **where** the answer is written, not what it is: up to six documents,
   the rule's own page ahead of pages about it, each with a few words that stand near the answer;
2. fetches those pages itself, skipping a site listed as refusing;
3. hands on stretches of each page's own text: a short page whole, of a long one the three
   stretches that share the rarest words with the request and with the search model's pointer;
4. records each stretch as a quote, put through the same check as any quote. No model's summary
   is handed on, and nothing is asked a second time.

Seven tests, three lines break-proved; 2024 tests in 90 files.

## What is run

Full answers through the default workflow. Two arms: `now`, and `documents` with the setting on.

| Set | `now` | `documents` |
|---|---|---|
| Harder professional set, 17 questions × 3 | run afresh | run |
| Inspection-authorization request × 8 | run afresh | run |
| First professional set, 15 questions × 3 | the record of this morning: 45 of 45 | run |

163 answers. **Cost:** about '$2.30' expected. Stops: '$0.45' on each of four hard-set
processes, '$0.35' on each of two first-set processes, '$0.20' on each of the two
inspection-authorization runs: '$2.90' in all, inside the '$3' the owner approved. About '$6.50'
is spent before it.

## The bars

1. **Harder set:** `documents` is right in at least 2 more of 51 than `now`, and on H1 in at
   least 2 of 3.
2. **First set:** `documents` is right in at least 43 of 45. It was 45 of 45 as the code is.
3. **Inspection authorization:** `documents` is right in at least 7 of 8.
4. **The text arrives:** in at least 85 percent of `documents` runs, the figures of the key's
   governing passage are in the text handed on.
5. **Cost:** `documents` costs no more an answer than `now`.

All met: the architect advises making it the default. Bar 2 missed: it harms what works, and is
not advised. Bars 1 or 3 missed with 4 met: reading is not the whole root. Bar 4 missed: the
finding half needs more than this build gives it.

## Predictions

1. Bars 1, 2 and 5 are met.
2. Bar 3 is missed by one: the search will still sometimes name the privileges section only.
3. Bar 4 lands between 80 and 90 percent.
4. `documents` answers carry fewer cautions than `now` answers on the harder set.
5. H9, whose source is a page built by script, is where `documents` hands on the least.

## Limits, stated beforehand

- The first set's `now` arm is this morning's record, not a fresh run. Same code for the lookup,
  same models, some hours apart.
- One reader; D50 asks for two, a stated departure. The free figure check points the reading and
  is not the result.

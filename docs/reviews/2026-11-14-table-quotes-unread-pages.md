# Table quotes and unread pages: two of the owner's rulings (2026-11-14)

The lookup test (`docs/reviews/2026-11-14-lookup-asks-request.md`) found two places where the
quote check lost a passage the search had returned. The owner ruled on both on 2026-11-14. Both
are built here. The third ruling, a test for the vague request, follows on its own.

## Ruling 1: a quoted table is read row by row

- **What was wrong.** A search model quotes a table with a bar between the cells
  ("|(7) Nitrate|10 (as Nitrogen)|"). The page prints the same cells with a space between them.
  The check looked for the bars and found nothing.
- **What changed.** `quote_found` in `autornd/knowledge/research.py`. A quote in which every line
  is a row of cells is read row by row: each row must be on the page with its cells side by side,
  and the rows must come in the order quoted. A line of dashes under the heading is layout and is
  not compared.
- **What stays strict.** A changed cell is not found. A figure beside another row's name is not
  found. Rows out of order are not found. A grid with under 20 characters of cell text is too
  short to check, as before. A row left out between two quoted rows is allowed: the model quoted
  the rows it used.
- **What is left out.** Prose is read as before. A PDF table with dot leaders
  ("(16) Arsenic ......" then "0.010") is not a grid and is still not found.

## Ruling 2: a page that could not be read is not counted

The owner's words: if the response is not coming back from the web page, that one does not get
counted and is not tested by the decision engine.

- **What was wrong.** The delivery's caution counted a quote on an unread page among the quotes
  not found: "1 of 2 quoted passages were found in their pages; the rest are unverified." One site
  refused all 13 fetches of quotes that held the answer.
- **What changed.** `_cautions` in `autornd/api/routes.py`. The count is now over the quotes
  whose pages were read. Quotes on unread pages are said apart: "2 more quoted passages were on a
  page that could not be read; not checked and not counted." When no page at all could be read
  the delivery says so, and the findings are still called unverified.
- **The decision engine.** The `quote_answers` switch was already asked only about quotes found
  on their pages (`_quote_items` in `autornd/graph/adapter.py`), so a quote on an unread page was
  never put to it. Nothing changed there.
- **What is not hidden.** Not counted is not the same as checked. The stored records keep every
  quote with its status and the reason the page was not read.
- **What is left as it was.** A question whose only quotes were on unread pages is still asked
  once more, which is how a readable copy gets quoted. The text the answering model reads is not
  changed.

## What proves it

- **Free replay,** `docs/probes/table_quote_replay.py`, on the lookup test's trace against the
  pages fetched again on 2026-11-14: all 9 grid quotes recorded as not found are found now; all 59
  quotes recorded as found are still found; none of the 15 prose quotes recorded as not found
  changed.
- **Tests,** 12 new: 9 in `tests/test_source_check.py`, 3 in `tests/test_convergence.py`. One
  older test stated the old count and was corrected to the ruling.
- **Break-proofs,** each seen to fail: dropping the row order; matching cells one by one instead
  of side by side; counting unread pages again.
- **Suite:** 1981 passed, 1 skipped; 1982 tests in 90 files.

## What this does not do

It does not make any answer more often right. It makes the delivery's word on what was checked
true more often. The inspection-authorization errors are the third ruling's subject.

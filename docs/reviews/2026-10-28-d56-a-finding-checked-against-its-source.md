# D56: a finding is checked against its source (advisor, 2026-10-28)

**Status: ruled by the advisor on 2026-10-28.** Command ARCH-20261028-128 carries it. It is free work: no paid call, no `.env` change, and no DB schema change.

This is step 4 of the generality-first order the owner approved on 2026-10-21: retrieval, meaning fetch, a quote check, and more than one lookup. Research is how the harness avoids confident guesses about the world. Today it trusts the search provider's word that a page says what the answer says. After this ruling, the harness reads the page itself.

## 1. The problem

| where | what |
|---|---|
| `autornd/knowledge/research.py` `_lookup` | A lookup is one search call. Its "citations" are the provider's `url_citation` annotations (`routing/openrouter.py`). Nothing fetches a page, and nothing checks that the answer's words are on it. |
| `Finding.grounded` | "Grounded" means the provider attached at least one URL. A confident wrong figure with a URL beside it counts as grounded. |
| `MAX_LOOKUPS = 1` | Every gap rides in one request, and there is no second look when the first answer cannot be backed. |
| `_remember` | A whole multi-part answer is stored under `citations[0]`, one URL for every question in it. |
| `REUSE_DISTANCE` | Its comment says the distance is squared L2. The collection is cosine (`store.py`, `hnsw:space cosine`), so the threshold is twice as loose as the comment meant. |

The 10-02 consultant review found each of these, and the advisor checked them against main on 2026-10-28.

## 2. The ruling

1. **The lookup reply is typed.** It is `LookupVerdict`: an `answer`, which is the prose every phase reads as before, and `quotes`, each with the question's number, the passage, and the page's address. The lookup stays a plain chat, because:
   - the parameters it sends are the ones preflight checks the search serving for, so a pinned serving still passes (G-2);
   - one reply is one search fee, with no retry for its shape.

   The reply is read with the same JSON extraction every JSON call uses. A reply that is not the format loses no word of its answer, so it is kept whole as the answer with no quotes, which marks it unverified. It is counted in `untyped_replies()` (convention 21).
2. **The harness fetches each quoted page** (`autornd/knowledge/fetch.py`).
   - It fetches public web pages only: `http` or `https`, and a host whose every address is public. No loopback, private or link-local address is fetched. Every redirect is checked the same way, and at most 3 are followed. The addresses come from model output, and a page can steer a model, so this is a hard line.
   - A fetch is bounded: 10 s in all, 2 MB, HTML and plain text only. A PDF is recorded as unfetched, with its content type, so the gap shows.
   - A fetch records the version it read: the final address, the time in UTC, the sha256 of the bytes, and the server's Last-Modified and ETag.
   - A fetch never raises; it returns what happened. At most 8 pages are fetched per lookup, all together.
3. **The quote check is free and deterministic** (`quote_found`).
   - A passage is found when its words are in the page's text, every word, in order, with nothing changed.
   - Spacing, case, curly quotes, dashes and soft hyphens are read alike, because pages and models print those differently without changing a word.
   - A passage under 20 characters checks nothing, and is recorded as too short.
   - **Found means the words are on the page, not that the answer follows from them.** Every phase sees the found passage verbatim, with its address and version, and can read it for itself.
4. **One more look, only when a check failed.**
   - A question whose answer quoted a passage, and had none found, is asked once more. All such questions go together, in one more request, which says why.
   - There are two rounds at most. A question whose answer quoted nothing is not asked again: the model did not follow the format, and the same request again buys little.
   - So a search serving that ignores the format never doubles the bill.
5. **Only a found passage is kept.**
   - Each found passage is stored on its own entry, under its own page's address, with the question it answers and the version read. It carries the tag `research-quoted`, and recall reads only that tag. Findings stored before D56, which nothing checked, are no longer recalled; they stay in the store.
   - `REUSE_DISTANCE` becomes 0.175, the old comment's intent restated as a cosine distance. The embedder returns unit vectors, on which squared L2 is twice the cosine distance.
6. **The record shows the check.** The grounding lookup record gains:
   - `quotes`, a count of the passages found, not found, unfetched and too short;
   - `asked_again`, the number of second rounds.

   It is a reading of the check, not of whether the answers are right (convention 26).
7. **The budgets are re-derived and unchanged** (convention 18).
   - **Spend:** a fetch makes no provider call. A second request comes at most once per lookup and three times per run, about $0.067 each at the consequential budget. That puts at most about $0.20 on top of measured runs, which cost $0.02 to $0.19, inside the $0.50 ceiling.
   - **Time:** fetching adds at most 60 s a run. That leaves the second requests about 160 s each inside the 558 s between 098's slowest run and the 1,800 s bound. The measurement of record checks this.

## 3. What it does not do, and why

| left out | why | when |
|---|---|---|
| reading PDFs | Most datasheets are PDFs. Text extraction from PDFs breaks words and columns, so a strict quote check against it fails often, and a loose one passes wrongly. | After the measurement shows how many quotes are unfetched for this reason. |
| the eCFR adapter | It is one source's adapter. Generality first: the general fetch comes before any one source. | The adapter pattern can follow the PDF reader. |
| applicability (does the passage support the answer?) | That is a judgment, not a free check. | A later ruling, with its own falsifier. |
| an age limit on recalled passages | The version is stored with each passage, so a reader can see its age. A limit would change which work ships. | When a stale recall is seen. |
| a name that resolves differently at check and at request | The check resolves before the request, and the request resolves again. Closing that needs a pinned connection. The harness runs on the owner's machine. | If the harness is ever served to others. |

Recall compares the whole question text of a lookup. A lookup that bundles several questions rarely matches one stored single-question passage at 0.175, so recall mainly serves single-gap lookups. This is recorded, not changed.

## 4. How it could be shown wrong

The measurement of record reads the grounding record's `quotes` counts and `untyped_replies()` for every lookup. If most answers come back untyped, or their pages unfetched, then the check adds a label but no evidence. The next step would then be the PDF reader or a different search serving, and the serving is the owner's choice (G-2).

## 5. Amendment (advisor, 2026-10-28)

The last row of §3 is closed. A fetch now connects to the address its check approved: the request goes to that address, with the page's name in the Host header and as the TLS server name, so the name is resolved once per hop, by the check. The client takes nothing from the environment: no proxy, which would resolve the name itself, and no `.netrc` credentials. The row deferred this "if the harness is ever served to others". The repo is public and its Dockerfile serves on all interfaces, so that condition already holds, and the fix turned out small. Command ARCH-20261028-129 carries it, beside Ruling D57 (`docs/reviews/2026-10-28-d57-the-convergence-repairs.md`).

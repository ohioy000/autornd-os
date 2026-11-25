# Independent check of the keys that looked wrong (2026-11-23)

The owner asked, after the final tally: "any keys you are sus of do an independent check". A key is suspect when several answers
that were made separately agree with each other and disagree with the key. Over the tally and the re-asks five questions had two
or more not-right readings with answers that agreed among themselves: **Y13, Y88, Y115, Y170, Y68**. (The other questions with a
not-right answer, X8, X12, X14, X20, Y9, Y37, Y124, X31, X41 and the two tier-4 designs, had one not-right answer among right ones,
or answers that disagreed with each other, and are not suspect.)

## How

One agent for each question, started fresh, **given the question and nothing else**: not the key, not our answers, not the readers'
notes. Each was told to answer only from a primary text it fetched itself, to quote the sentence with its URL, to say where it
could not, and to mark anything it could not fetch UNVERIFIED. The agents' reports are cited below as they were returned; they are
one reading each, not two, so this is a screen with a source behind it and not a ruling. **A change to a key is a new key version the
owner ratifies (D44); none is made here.**

## What they found

| Question | Key says | The primary text says | Verdict on the key |
|---|---|---|---|
| **Y115** FHWA HDS-4 rational method | 5 minutes; under about 200 acres | HDS-4 (June 2008, ch. 2): "if the total time of concentration is less than 5 minutes, a minimum value of 5 minutes should be used"; "restricted to drainage areas less than 80 hectares (200 acres)". Same sentence in the 1997 metric edition. No 10-minute minimum in HDS-4. | **Holds.** The answers that said 10 minutes took it from another document. |
| **Y170** UHECR threshold, PDG 2024 | strictly greater than 1 EeV, exclusive | PDG 2024, "30. Cosmic Rays": "CRs with energies in excess of 1 EeV are referred to as ultra-high energy cosmic rays (UHECRs)." The only other threshold in the review (E > 5x10^19 eV) is a narrower use for cosmogenic neutrinos. | **Holds.** The answers that said 10^17 eV took it from another chapter. |
| **Y68** UI Events wheel | no such value is stated; the section moved to Pointer Events | The W3C working draft of 21 February 2026 (current on 2026-11-21): section 1.1.1, "The Mouse Events and Wheel Events section of this specification have been moved to the Pointer Events specification [pointerevents4]." No wheel section in the table of contents. The 2016 and 2019 drafts still define `wheel`. | **Holds.** The answers that said "wheel" cite older snapshots. (The agent could not rule out a later draft between February and November.) |
| **Y88** NERC PRC-024-3 | 60 days; 60 days after a change unless the requester says not required; retention "3 years or until the next audit, whichever is longer" | The -3 text says exactly that for retention and for both 60-day duties. But **PRC-024-4** was adopted in October 2024, ordered by FERC in July 2025 and, by NERC's page, is effective **1 October 2026**; the implementation plan retires -3 immediately before that date in the US. Its retention reads "five years or until the next audit, whichever is longer"; the 60-day duties are unchanged. | **Holds for the standard the question names (-3)**; the question's own words "as in force on 2026-11-21" now point at -4. Flagged, not stale in the sense Y13 is: the question asks about -3 by name. |
| **Y13** EU prospectus regulation | the regulation does not apply below EUR 1 000 000 over 12 months (Article 1(3)) | Regulation (EU) 2024/2809 (the Listing Act) **deleted Article 1(3)** and, from **5 June 2026**, Article 3(2)(b) exempts offers below **EUR 12 000 000** per issuer or offeror over 12 months from the duty to publish a prospectus; under Article 3(2a) a Member State may lower that to **EUR 5 000 000**. EUR-Lex consolidation of 05.06.2026 read. Between 2024 and June 2026 the Article 3(2) band was EUR 8 000 000. | **Stale on 2026-11-21.** There was no EUR 1 000 000 threshold in force; a EUR 1 000 000 offer is inside the regulation and exempt from the prospectus duty. The "5 000 000" and "12 000 000" in three of the four answers were the current law. |

UNVERIFIED in the agents' own words: the date Article 1(3) stopped applying (4 December 2024 is an inference from the amending act's
application clauses); that no amendment after the 5 June 2026 consolidation exists; that no UI Events draft was published and
withdrawn after 21 February 2026; NERC's 1 October 2026 date was read off NERC's page, not the FERC order.

## What it does to the tally

* **Y13:** the tally's answer to Y13 (3c0bf4fd) was read not right against the key and is one of the seven misses of the 174 unseen
  questions (167 of 174). Under a corrected key it could count; it said the regulation "does not apply" and gave EUR 5 000 000,
  which is the Member-State option, so whether it would be right depends on the new key's wording and is not decided here. The most it
  changes is the 174 from 167 to 168. **No figure of the review is changed**; the owner decides under D44 whether Y13 gets a new
  key version (and the question's own "below EUR 1 000 000" premise may need rewording, since it describes a threshold that no
  longer exists).
* **Y13's re-asks** (rerun2) are excluded from the revised caution fix's test for this reason.
* **Y88:** nothing changes; a note on the key that PRC-024-4 supersedes -3 from 1 October 2026 would keep the question honest.
* **Y115, Y170, Y68:** the not-right readings stand; the harness answered wrongly, not the key.

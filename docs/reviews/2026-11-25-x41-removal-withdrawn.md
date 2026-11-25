# X41 is back in the first hold-out (the removal withdrawn), 2026-11-25

**Status: a correction of my own error; the owner told me to fix it ("fix your error") on 2026-11-25.**

## What was wrong

On 2026-11-25 I removed X41 (PR #343, set version 1.1) because "a real page for the same part states one" thermal figure. Before planting that page for a
retrieval test I fetched it. The page the three answers quoted (`onlinedocs.microchip.com/oxy/GUID-3EE676DF-490E-41BC-98F0-5774B35DC989-en-US-25/...`)
is the **AVR DA family** thermal table (title "AVR DA Family", parts AVR128DA28, AVR128DA32 and so on; Table 37-9, 60 degC/W for the 28-pin PDIP). It is not
the ATmega328P's. The other page fetched for a first look is a PIC18-Q71 page.

## What that means

- The key was right: the ATmega328P datasheet DS40002061B states no thermal resistance, junction temperature or dissipation figure (310,048 characters read).
- The three answers that quoted the AVR DA table took a figure from another family. That is the trap in the key's own `commonly_confused` field, and they were
  correctly scored not right.
- The removal, and the review that gave its reason, were wrong. The review document of the removal is deleted by this change; this one replaces it.

## What changed

The live set is `professional-holdout` as signed on 2026-11-17 (42 questions, sha256 `c5d4a9da...`); the version 1.1 file, the archive copy and the guard test of
the removal are gone. No code. Counts re-derived on the branch.

## A second look, free, same day

Read again with the harness's own fetcher: the keyed address (`...DS40002061B.pdf`) gives **932,316 characters, 653 pages**, names DS40002061B 654 times, holds the two
keyed passages (`40.0mA`, `200.0mA`), and has no "junction", no "dissipation" and no thermal-resistance figure ("thermal" appears only in a package-drawing note on
thermal vias). The 310,048-character figure in the withdrawn review belongs to the older Atmel 8271 / 40001984A files, which the same search turns up; it was the
wrong document to cite as "the keyed PDF". The older Atmel automotive datasheet, the 40001906C document and Microchip's ATmega328P product page were read the same
way: none gives a junction-to-ambient figure. **No genuine ATmega328P document found states one**; a figure for this part can only come from another family or a
third party, which is what the key's trap says.

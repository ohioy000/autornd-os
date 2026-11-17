# A hold-out set: draft for the owner's sign-off (2026-11-17)

Step 1 of the five steps the owner asked for on 2026-11-17, before the version is named and
released. This is the set only. **No run is made on it until the owner signs the keys (D44).**
The runner refuses it while its status says draft.

File: `evals/professional/holdout-questions.json`, version professional-holdout-1.

**Signed by the owner on 2026-11-17, all 42 keys; the set is approved and frozen. The owner's
word was "Sign all 42 and approve '$2'". The run is preregistered in
`docs/preregistration-20261117-holdout-run.md`.**

## The point

Every figure so far was measured on questions the harness was shaped against. This set is for
questions it was not. **42 questions** were written after the harness was fixed, by authors that
never saw its answers, in fields the other three sets do not touch.

- **Three authors, 14 questions each.** Each was a separate agent. None had the harness's code,
  its answers or the other sets' keys. Each was told to write a question a working engineer or
  compliance officer would really ask, to name no model, and to give every question a source
  passage on a live page, a key with one defensible answer, and the tempting wrong answer.
  The three fields: EU and international law and standards (X1 to X14); software, security and
  internet standards (X15 to X28); physical engineering, units, datasheets and national rules
  (X29 to X42).
- **Two other agents checked every question.** Each opened every cited page itself, found each
  passage, worked out the answer from the page before comparing it with the key where they could, redid
  the arithmetic, and said whether the question has one defensible answer. They are agents, not
  people.
- **They found ten things to fix, and all are fixed.** X14 called a blood-glucose meter an MDR
  device; under the rules it is an in-vitro device, so the question now names an insulin pump
  and the key is unchanged. X21 said "the latest release", which will point at a different
  release within weeks; it now names PostgreSQL 18. X30 had a second reading: the federal
  marine-vessel and offshore regulations give a different answer to the same words; the
  question now names the general regulation and says it is not those two. X16, X22, X23, X27,
  X31 and X41 each had a key item the question did not ask for; the item is removed. X9's note
  on the tempting wrong date was made exact.
- **None was dropped. Four are marked as ones a model could answer from general knowledge**
  (X5, X6, X15, X17) and are kept: a set that has no easy question would not show an easy one
  going wrong. The checkers also named many where the answer cannot be guessed, X11, X12, X18 and
  X35 among them.
- **At least five questions are traps** where the document states no such figure or the rule does not
  apply: X13, X16, X19, X36 and X41. A right answer says so.

## What the harness's own fetch can read

`python -I evals/professional/verify_keys.py . holdout-questions.json` fetches each source with
the harness's own fetch and looks for the passage with the harness's own quote check.
**26 of 42 hold.** The other 16 are not wrong; they show where the harness's reading of a page
differs from a person's. The checkers read every one of these on the live page and found the
passage there. The reasons, as far as they were looked into:

| Question | Why the harness's fetch does not find it |
|---|---|
| X3 | the PDF's table reads as columns run together |
| X12 | the PDF's table reads as columns run together |
| X17 | the PDF breaks the figure across a line |
| X18 | the PDF's superscripts (2^32) read as plain digits |
| X19 | the 492-page PDF did not answer in 25 seconds |
| X20 | two NIST PDFs did not answer in 25 seconds |
| X26 | the page's maths markup differs from plain text |
| X29 | the Canadian page and the eCFR text read differently |
| X30 | the page's table reads differently |
| X31 | the PDF's table reads differently |
| X32 | the page's formula reads differently |
| X33 | the PDF's table rows read joined |
| X35 | superscripts and spacing in the numbers |
| X38 | the PDFs are over the harness's 15 MB limit |
| X40 | the page's table reads differently |
| X41 | the 653-page PDF is over the harness's 15 MB limit |

The preregistration reports two cuts: all 42, and the 26 the harness's fetch can read:
X1, X2, X4, X5, X6, X7, X8, X9, X10, X11, X13, X14, X15, X16, X21, X22, X23, X24, X25, X27, X28, X34, X36, X37, X39, X42. A question whose source the harness cannot read is still a real question, and it
stays in the first cut. I did not change the harness to read them, and I did not change the
passages to match what it reads, because the set must stay what the authors wrote.

## What was not settled

- X2: that the Commission's reform proposal for the medical-devices transition was not adopted
  after 9 November 2026. The consolidated text of that date is the one on the page today.
- X19: concrete lockout values printed by FedRAMP and the CJIS policy were seen only in search
  snippets. Only the one non-NIST page that prints them was opened.
- X37: the NOAA page is undated, so "2029" is true as of 17 November 2026.
- X26: the second passage is a transcription of the page's maths markup, not a word-for-word
  string. X31: the register page is a program, so "no later amendment" rests on its text and a
  web search.

## What the owner is asked

1. **Sign the 42 keys,** or strike any. On the owner's word the status becomes "Approved by the
   owner and frozen" and the runner will take the set. A key that is wrong in a way the checkers
   did not see would count against the harness, so any question whose key looks wrong to the
   owner should be struck here.
2. **Authorise the run and its amount.** The run is proposed in
   `docs/preregistration-20261117-holdout-run.md`: three answers a question, 126 answers, about
   '$1.30', stopping at '$1.80', inside '$2'.

## The questions

## EU and international law and standards

### X1  (EU machinery safety law)

*amendment/corrigendum changed the figure; older printed date widely quoted*  
*The harness's fetch reads the passage.*

**Question.** Regulation (EU) 2023/1230 on machinery repeals Directive 2006/42/EC. According to the text of the Regulation as corrected and in force today (17 November 2026), from which date does the Regulation apply and the Directive stop applying, and is the Directive still in force today?

**Key.**
- date from which Regulation (EU) 2023/1230 applies and Directive 2006/42/EC is repealed: 20 January 2027
- is Directive 2006/42/EC still in force on 17 November 2026: Yes; it is repealed only with effect from 20 January 2027

**The tempting wrong answer.** 14 January 2027: that is the date printed in Articles 51(2), 52(1) and 54 of the Regulation as first published (OJ L 165, 29.6.2023) and still shown on EUR-Lex's page of the original text; Corrigendum OJ L 169, 4.7.2023, p. 35 replaced it with 20 January 2027, and the consolidated text uses the corrected date.

**Sources.** https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:02023R1230-20260727; https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32023R1230R(01)
### X2  (EU medical devices regulation)

*amendment changed the figure; older end-of-transition date widely quoted*  
*The harness's fetch reads the passage.*

**Question.** A manufacturer holds a notified-body certificate issued under the old Medical Devices Directive 93/42/EEC for a class IIa device, and that certificate is still valid by virtue of Article 120(2) of Regulation (EU) 2017/745 (MDR). Assuming it meets the conditions of Article 120(3c), what is the last date on which the legacy device may be placed on the market or put into service, and by which two dates must it have lodged a formal application with a notified body and had a written agreement signed with it?

**Key.**
- last date to place a legacy class IIa device on the market / put into service: 31 December 2028
- deadline to lodge the formal application with a notified body: 26 May 2024
- deadline for the signed written agreement with the notified body: 26 September 2024

**The tempting wrong answer.** 26 May 2024, the end date of the transitional period before Regulation (EU) 2023/607 (its recital says it was maintained after the 2020 postponement), which the amended Article 120 replaced with 31 December 2027 or 31 December 2028 for devices meeting the conditions; and 31 December 2027, which is the date for class III and class IIb implantable devices, not class IIa.

**Sources.** https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:02017R0745-20261109
### X3  (WHO air quality guidelines)

*newer edition changed the figure; older (2005) values widely quoted*

**Question.** In the WHO global air quality guidelines (2021 update), what are the recommended AQG levels, in µg/m3, for (a) the 24-hour mean of sulfur dioxide and (b) the annual mean of nitrogen dioxide?

**Key.**
- SO2 24-hour AQG level (2021): 40 µg/m3
- NO2 annual AQG level (2021): 10 µg/m3

**The tempting wrong answer.** 20 µg/m3 for SO2 (24-hour) and 40 µg/m3 for NO2 (annual) are the 2005 values; the 2021 SO2 24-hour level went up from 20 to 40 while the NO2 annual level fell from 40 to 10.

**Sources.** https://iris.who.int/server/api/core/bitstreams/551b515e-2a32-4e1a-a58c-cdaecd395b19/content
### X4  (IAEA radiation protection standards)

*amendment/newer edition changed the figure; older ICRP-60-era limit widely quoted*  
*The harness's fetch reads the passage.*

**Question.** Under IAEA General Safety Requirements Part 3 (the international basic safety standards, 2014 edition), what is the dose limit for occupational exposure of workers over 18 years for the equivalent dose to the lens of the eye, and what annual limit had applied to the lens before the change that its preface describes?

**Key.**
- current occupational lens-of-the-eye limit (adult workers): 20 mSv per year averaged over five consecutive years (100 mSv in 5 years), and not more than 50 mSv in any single year
- previous annual lens limit: 150 mSv per year

**The tempting wrong answer.** 150 mSv per year (the old limit, still widely quoted); or reading 20 mSv as a flat annual cap with no five-year averaging; 15 mSv in a year is the separate public-exposure lens limit.

**Sources.** https://www-pub.iaea.org/MTCD/Publications/PDF/Pub1578_web-57265295.pdf
### X5  (EU electrical equipment safety)

*plain lookup; no rule named*  
*The harness's fetch reads the passage.*

**Question.** Under EU harmonisation law on the safety of electrical equipment within certain voltage limits, what voltage ratings (AC and DC) bring a product into scope, and would equipment designed for use at 24 V AC be within that scope?

**Key.**
- AC voltage rating range in scope: between 50 and 1 000 V
- DC voltage rating range in scope: between 75 and 1 500 V
- equipment designed for 24 V AC in scope?: No, it is below the 50 V AC lower limit *(worked out, not printed)*

**The tempting wrong answer.** A single 50-1 000 V window for both AC and DC, or 1 000 V as the DC upper limit; the Directive gives separate ranges, 50-1 000 V for AC and 75-1 500 V for DC, so a 24 V AC product is below the lower bound.

**Sources.** https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:02014L0035-20260530
### X6  (EU chemicals law)

*plain lookup; no rule named*  
*The harness's fetch reads the passage.*

**Question.** A consumer in the EU asks a retailer whether a product it sold contains a substance of very high concern (a candidate-list substance). Above what concentration in the article does the retailer's duty to answer arise, within how many days must it answer, and may it charge for the answer?

**Key.**
- concentration above which the duty arises: above 0,1 % weight by weight (w/w)
- time limit to answer: within 45 days of receipt of the request
- may the supplier charge: No, the information is provided free of charge

**The tempting wrong answer.** 30 days or one month (the usual data-subject-request clock) instead of 45 days; or believing a fee may be charged; or applying 0,1 % to something other than the article's weight by weight concentration of the substance.

**Sources.** https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:02006R1907-20260622
### X7  (EU cybersecurity of networks and information systems (NIS2))

*plain lookup; derogation for one entity type*  
*The harness's fetch reads the passage.*

**Question.** Under the NIS2 Directive, by when must a trust service provider that suffers a significant incident affecting its trust services submit its incident notification to the CSIRT or competent authority, and what is the time limit for the same notification from other essential and important entities?

**Key.**
- trust service provider: incident notification: within 24 hours of becoming aware of the significant incident
- other entities: incident notification: within 72 hours of becoming aware of the significant incident

**The tempting wrong answer.** 72 hours for every entity (missing the trust-service-provider derogation); or confusing it with the 24-hour early warning in point (a), which every entity must send.

**Sources.** https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32022L2555
### X8  (EU Cyber Resilience Act)

*plain lookup; status: earlier date than the headline application date; combines application date and legacy-product rule*  
*The harness's fetch reads the passage.*

**Question.** A manufacturer placed a connected consumer product on the EU market in 2025. On 17 November 2026 it becomes aware that a vulnerability in that product is being actively exploited. Does the EU Cyber Resilience Act oblige it to report this now, and what are the deadlines for the early warning, the vulnerability notification and the final report?

**Key.**
- does the reporting duty apply now to a product placed on the market in 2025: Yes: Article 14 applies from 11 September 2026, including to products placed on the market before 11 December 2027 (Article 69(3))
- early warning notification: without undue delay and within 24 hours of becoming aware
- vulnerability notification: within 72 hours of becoming aware
- final report: no later than 14 days after a corrective or mitigating measure is available

**The tempting wrong answer.** That nothing applies until 11 December 2027 (the general application date), and, for the final report, 'one month after the incident notification', which is the deadline for severe incidents, not for actively exploited vulnerabilities.

**Sources.** https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32024R2847
### X9  (EU RoHS (restriction of hazardous substances in electrical equipment))

*plain lookup; list extended by later amendment*  
*The harness's fetch reads the passage.*

**Question.** In Annex II of the RoHS Directive 2011/65/EU as currently consolidated, how many substances are restricted, which one has a maximum concentration of 0,01 % by weight in homogeneous materials, and from what date does the restriction on DEHP, BBP, DBP and DIBP apply to medical devices?

**Key.**
- number of restricted substances in Annex II: 10 (lead, mercury, cadmium, hexavalent chromium, PBB, PBDE, DEHP, BBP, DBP, DIBP) *(worked out, not printed)*
- substance with the 0,01 % limit: cadmium
- date the DEHP/BBP/DBP/DIBP restriction applies to medical devices: 22 July 2021

**The tempting wrong answer.** 0,1 % for cadmium (it is the only entry at 0,01 %); and 22 July 2019, the date from which the four phthalates apply to equipment other than medical devices and monitoring and control instruments (Delegated Directive (EU) 2015/863, Article 2), instead of 22 July 2021 for medical devices.

**Sources.** https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:02011L0065-20260701
### X10  (EU road transport drivers' hours)

*two passages combined; derived; no rule named*  
*The harness's fetch reads the passage.*

**Question.** An EU-based lorry driver subject to the EU drivers'-hours rules for road transport drove a total of 30 hours in one week. What is the most they may drive in the following week without exceeding the limits on driving time?

**Key.**
- maximum driving time in the following week: 56 hours (the weekly cap binds, because 90 - 30 = 60 hours would be allowed by the two-week cap alone) *(worked out, not printed)*

**The tempting wrong answer.** 60 hours, from subtracting 30 from the 90-hour two-week cap and ignoring the separate 56-hour weekly cap.

**Sources.** https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:02006R0561-20241231
### X11  (UN vehicle regulation (electric power train, UN R100))

*two passages combined; unit calculation; derived*  
*The harness's fetch reads the passage.*

**Question.** UN Regulation No. 100 (electric power train safety, 05 series, as published in the EU Official Journal as 2026/1695): a vehicle's high-voltage system has galvanically connected AC and DC buses with a working voltage of 400 V. What minimum isolation resistance, in kilo-ohms, is required between the high voltage bus and the electrical chassis (a) when the AC buses have none of the extra protections in the Regulation, and (b) when all AC buses are protected by one of the two measures it lists?

**Key.**
- (a) no extra protection on the AC buses: 500 Ω/V x 400 V = 200 kΩ *(worked out, not printed)*
- (b) all AC buses protected by one of the two listed measures: 100 Ω/V x 400 V = 40 kΩ *(worked out, not printed)*

**The tempting wrong answer.** 40 kΩ (100 Ω/V) for both cases, which is the figure for DC-only buses and for REESS tests; the 500 Ω/V figure is what applies to combined AC/DC buses without the extra protection.

**Sources.** https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=OJ:L_202601695
### X12  (International radioactive material transport requirements (IAEA SSR-6 Rev. 2))

*two passages combined; calculation; derived; no rule named*

**Question.** Under the current edition of the international safety requirements for transporting radioactive material, a freight container used as packaging (not under exclusive use) has a maximum dose rate of 0.08 mSv/h measured at 1 m from its external surfaces, and the largest cross-sectional area of the load is 3 m2. What transport index (TI) is assigned, and is it within the TI limit for such a container?

**Key.**
- transport index assigned: 16 (0.08 mSv/h x 100 = 8, x 2 for a 1 m2 < load area <= 5 m2) *(worked out, not printed)*
- within the TI limit for a freight container used as packaging?: Yes: the limit is 50 *(worked out, not printed)*

**The tempting wrong answer.** TI 8, from forgetting the Table 7 multiplication factor for a freight container; or testing the result against the limit of 10 that applies to a package other than a freight container (para. 526(a)) and wrongly finding it exceeded.

**Sources.** https://www-pub.iaea.org/MTCD/publications/PDF/p15912-PUB2120_web.pdf
### X13  (EU data protection (GDPR))

*trap: the instrument states no such figure*  
*The harness's fetch reads the passage.*

**Question.** At how many employees does the GDPR make it mandatory for a controller or processor to appoint a data protection officer?

**Key.**
- employee-count threshold for a DPO in the GDPR: None: Article 37(1) ties mandatory designation to the kind of processing (public authority or body other than courts; core activities requiring regular and systematic large-scale monitoring of data subjects; large-scale processing of special categories or criminal-conviction data), not to headcount
- where the 250-person figure appears: Article 30(5), the derogation from keeping records of processing, not Article 37

**The tempting wrong answer.** 250 employees, which is the Article 30(5) records-of-processing derogation, not a DPO rule; Article 37(4) lets Union or Member State law require designation in other cases, so a national headcount rule may exist outside the Regulation, but none is in Article 37(1).

**Sources.** https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32016R0679
### X14  (EU radio equipment (RED cybersecurity delegated act))

*trap: does not apply; date postponed by amendment*  
*The harness's fetch reads the passage.*

**Question.** A manufacturer's Bluetooth-connected insulin pump is a medical device under Regulation (EU) 2017/745. Do the cybersecurity-related essential requirements of Article 3(3), points (d), (e) and (f), of the Radio Equipment Directive 2014/53/EU, as specified by Delegated Regulation (EU) 2022/30, apply to it, and from what date does that Delegated Regulation apply to radio equipment that it does cover?

**Key.**
- do the Article 3(3)(d), (e), (f) requirements apply to a radio-connected device that is also a medical device under Regulation (EU) 2017/745: No: Article 2(1) of Delegated Regulation (EU) 2022/30 disapplies them for radio equipment to which Regulation (EU) 2017/745 or 2017/746 also applies
- date from which Delegated Regulation 2022/30 applies to covered radio equipment: 1 August 2025

**The tempting wrong answer.** Yes, because the device is internet-capable radio equipment; and 1 August 2024, the original application date that Delegated Regulation (EU) 2023/2444 postponed to 1 August 2025.

**Sources.** https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:02022R0030-20231027

## software, security and internet standards

### X15  (Web accessibility (W3C WCAG 2.2))

*plain lookup*  
*The harness's fetch reads the passage.*

**Question.** Under WCAG 2.2, which Level AA success criterion sets a minimum size for pointer-input targets, what is that size in CSS pixels, what diameter of circle does its spacing exception use, and what larger size does the Level AAA 'Target Size (Enhanced)' criterion require?

**Key.**
- Level AA criterion: 2.5.8 Target Size (Minimum), new in WCAG 2.2
- minimum target size: 24 by 24 CSS pixels
- spacing-exception circle diameter: 24 CSS pixels
- Level AAA enhanced size (criterion 2.5.5): 44 by 44 CSS pixels

**The tempting wrong answer.** 44 by 44 CSS pixels given as the Level AA requirement. That is the Level AAA figure of 2.5.5 Target Size (Enhanced); the AA minimum in 2.5.8 is 24 by 24.

**Sources.** https://www.w3.org/TR/WCAG22/#target-size-enhanced; https://www.w3.org/TR/WCAG22/#target-size-minimum
### X16  (Web accessibility (W3C WCAG 2.2))

*trap: criterion removed, does not apply*  
*The harness's fetch reads the passage.*

**Question.** A vendor questionnaire for the W3C web content accessibility Recommendation published in December 2024 (conformance target Level AA) asks for a pass or fail result on success criterion 4.1.1 'Parsing' (well-formed markup, unique IDs). Must a page pass 4.1.1 to conform to that version, and what does the document say is the reason?

**Key.**
- must a page pass 4.1.1 for WCAG 2.2 conformance: No: 4.1.1 Parsing is marked 'Obsolete and removed' in WCAG 2.2
- reason given: Assistive technology no longer has any need to directly parse HTML

**The tempting wrong answer.** Answering yes, because 4.1.1 Parsing is a Level A criterion in WCAG 2.0 (still printed as Level A there) and in WCAG 2.1 (whose page notes it 'should be considered as always satisfied for any content using HTML or XML'). WCAG 2.2 marks it 'Obsolete and removed'.

**Sources.** https://www.w3.org/TR/WCAG22/; https://www.w3.org/TR/WCAG22/#parsing
### X17  (Cryptography standards (NIST FIPS 197))

*plain lookup; one derived count*

**Question.** Per FIPS 197 (Advanced Encryption Standard), how many rounds does AES-256 use, what is its block size in bits, and how many round keys (each an array of four words) does the cipher consume?

**Key.**
- rounds for AES-256 (Nr): 14
- block size: 128 bits
- round keys for AES-256: 15 (Nr + 1) *(worked out, not printed)*

**The tempting wrong answer.** Giving 14 round keys (forgetting the initial key addition, so Nr + 1 = 15), or 10 or 12 rounds (AES-128 or AES-192), or a 256-bit block (256 is the key length; the block is 128 bits for all three).

**Sources.** https://nvlpubs.nist.gov/nistpubs/fips/nist.fips.197-upd1.pdf
### X18  (Cryptography standards (NIST SP 800-38D))

*two passages combined; unit conversion (bits to bytes)*

**Question.** Under NIST SP 800-38D (Galois/Counter Mode, November 2007 edition), for AES-GCM with IVs produced by the RBG-based construction: what IV length should implementations restrict support to, what is the maximum total number of invocations of the authenticated encryption function under one key, and what is the maximum plaintext length per invocation expressed in bytes?

**Key.**
- recommended supported IV length: 96 bits
- max total invocations per key (RBG-based IVs): 2^32
- max plaintext length per invocation: 2^39 - 256 bits = 2^36 - 32 bytes = 68,719,476,704 bytes *(worked out, not printed)*

**The tempting wrong answer.** Reading len(P) <= 2^39 - 256 as bytes (it is bits), or giving 2^64 (the block-count guidance elsewhere in the document, or the bound on len(A) and len(IV)) as the invocation cap.

**Sources.** https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication800-38d.pdf
### X19  (Security controls (NIST SP 800-53 Rev. 5))

*trap: document states no such value*

**Question.** What number of consecutive invalid logon attempts, within what time period, and with what lockout duration does NIST SP 800-53 Rev. 5 control AC-7 (Unsuccessful Logon Attempts) require?

**Key.**
- required number of consecutive invalid attempts: None stated: an assignment parameter, '[Assignment: organization-defined number]'
- required time period and lockout duration: None stated: both are organization-defined parameters
- what the control does fix: That a limit be enforced and that an action (lock for a defined time, lock until released by an administrator, delay the next prompt, notify an administrator, or other defined action) follow when it is exceeded

**The tempting wrong answer.** Quoting a figure such as 3 or 5 attempts and a 15 or 30 minute lockout as 'the NIST requirement'. Any such figure is an organization's own choice or comes from another document; AC-7 states none.

**Sources.** https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-53r5.pdf
### X20  (Security requirements (NIST SP 800-171))

*newer version changed the value*

**Question.** How many families of security requirements does the current revision of NIST SP 800-171 (Protecting Controlled Unclassified Information in Nonfederal Systems and Organizations) define, how many did Revision 2 define, and what is Revision 2's status on NIST's own published copy?

**Key.**
- families in the current revision (Rev. 3, May 2024): 17
- families in Revision 2: 14 (fourteen)
- status of Revision 2: Withdrawn 14 May 2024, superseded in its entirety by Rev. 3

**The tempting wrong answer.** Giving 14 families as current, or treating Rev. 2 as the in-force NIST publication. Rev. 2 is the older text that is still widely quoted; NIST's own copy is stamped withdrawn.

**Sources.** https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-171r2.pdf; https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-171r3.pdf
### X21  (Databases (PostgreSQL 18))

*newer version changed the default*  
*The harness's fetch reads the passage.*

**Question.** A DBA creates a new PostgreSQL 18 cluster with initdb, passing no checksum-related option. Are data checksums enabled, how are they switched off, and what must hold for checksum settings when running pg_upgrade?

**Key.**
- checksums enabled with plain initdb on 18: Yes, enabled by default
- how to disable: initdb --no-data-checksums
- pg_upgrade requirement: Old and new clusters must have matching checksum settings

**The tempting wrong answer.** No, checksums are off unless -k/--data-checksums is given. That was the default through PostgreSQL 17; the 18 release notes list the new default under incompatibilities.

**Sources.** https://www.postgresql.org/docs/18/app-initdb.html#APP-INITDB-DATA-CHECKSUMS; https://www.postgresql.org/docs/18/release-18.html#RELEASE-18-MIGRATION
### X22  (Operating systems (Linux kernel documentation))

*plain lookup*  
*The harness's fetch reads the passage.*

**Question.** On a current Linux kernel, what range of values does the vm.swappiness sysctl accept, what is its default, and what value fits a swap device (for example zram) whose random IO averages 2x faster than IO from the filesystem?

**Key.**
- range: 0 to 200
- default: 60
- example value for swap 2x faster than filesystem: 133

**The tempting wrong answer.** A range of 0 to 100, which many tuning guides still give. The kernel page states 0 to 200 (a value of 100 means equal IO cost; values above 100 are for cheaper swap) and does not itself date the change.

**Sources.** https://docs.kernel.org/admin-guide/sysctl/vm.html#swappiness
### X23  (Programming languages (Python standard library))

*newer version changed the default*  
*The harness's fetch reads the passage.*

**Question.** In the current CPython documentation for the multiprocessing module (3.15 series), which start method is the default on Linux when a program never calls set_start_method(), which method was the Linux default before Python 3.14, and under what condition does the default become spawn instead?

**Key.**
- Linux default now: forkserver
- Linux default before 3.14: fork
- when the default is spawn instead: When there is no writable temporary directory (for example a read-only file system); documented from 3.15.1

**The tempting wrong answer.** fork as the Linux default, which was true before 3.14 and is still quoted widely. fork is no longer the default on any platform.

**Sources.** https://docs.python.org/3/library/multiprocessing.html#contexts-and-start-methods
### X24  (Container orchestration (Kubernetes))

*two clauses combined; older value still applies below 1.25; derived from the rule*  
*The harness's fetch reads the passage.*

**Question.** Under the Kubernetes version skew policy, kube-apiserver is at v1.27. Which of these kubelets are inside the supported skew: v1.28, v1.25, v1.24?

**Key.**
- kubelet v1.28 with kube-apiserver v1.27: Not supported: a kubelet must not be newer than kube-apiserver
- kubelet v1.25: Supported: two minors older, within the three-minor allowance (it is not below 1.25) *(worked out, not printed)*
- kubelet v1.24: Not supported: it is below 1.25, so only two minors older are allowed, and it is three older *(worked out, not printed)*

**The tempting wrong answer.** Treating v1.24 as supported because it is three minors behind and the general rule allows three. The page limits kubelets below 1.25 to two minors; the three-minor allowance is the newer value, and the two-minor limit is the older one still widely quoted.

**Sources.** https://kubernetes.io/releases/version-skew-policy/
### X25  (Container orchestration (Kubernetes))

*plain lookup*  
*The harness's fetch reads the passage.*

**Question.** An operator creates a Service of type NodePort without setting nodePort, and the API server was started without any port-range flag. From which port range is the node port allocated, and under that default range how is it split into static and dynamic bands?

**Key.**
- default node port range: 30000-32767
- static band: 30000-30085
- dynamic band: 30086-32767

**The tempting wrong answer.** Quoting a range of 30000-32768, or treating the whole range as one pool. The page gives 30000-32767 and splits it into the two bands above; dynamic assignment uses the upper band first.

**Sources.** https://kubernetes.io/docs/concepts/services-networking/service/
### X26  (Web platform specifications (WebAssembly))

*two passages combined; unit conversion (pages to bytes)*

**Question.** In the WebAssembly 3.0 core specification, what is the page size in bytes, how many pages may a memory with a 32-bit address type (i32) declare at most, and what is that maximum in bytes? What is the corresponding page limit for a 64-bit address type (i64)?

**Key.**
- page size: 65536 bytes (64 Ki)
- max pages, i32 memory: 2^(32-16) = 65536 pages *(worked out, not printed)*
- max memory size, i32: 2^32 bytes = 4 GiB *(worked out, not printed)*
- max pages, i64 memory: 2^(64-16) = 2^48 pages *(worked out, not printed)*

**The tempting wrong answer.** Giving only the 32-bit figure (65536 pages, 4 GiB) as the limit for every memory. In this 3.0 text the address type may be i32 or i64, and an i64 memory is valid within 2^48 pages.

**Sources.** https://webassembly.github.io/spec/core/exec/runtime.html#memory-instances; https://webassembly.github.io/spec/core/valid/types.html#valid-memtype
### X27  (Web platform specifications (W3C Web Authentication))

*newer version changed the value*  
*The harness's fetch reads the passage.*

**Question.** What recommended range and default, in milliseconds, does the W3C Web Authentication Level 3 Recommendation give for a WebAuthn ceremony timeout, and how did the Level 2 Recommendation differ when userVerification is 'discouraged'?

**Key.**
- Level 3 recommended range: 300000 ms to 600000 ms
- Level 3 recommended default: 300000 ms (5 minutes)
- Level 2 with userVerification discouraged: Range 30000 ms to 180000 ms, default 120000 ms (2 minutes)

**The tempting wrong answer.** Giving the Level 2 figures (default 120000 ms for discouraged, lower bound 30000 ms) as current. Level 3 replaces the userVerification-dependent table with one range and one default.

**Sources.** https://www.w3.org/TR/webauthn-2/#sctn-createCredential; https://www.w3.org/TR/webauthn-3/; https://www.w3.org/TR/webauthn-3/#sctn-timeout-recommended-range
### X28  (Internet protocols (IETF RFC 9293, TCP))

*plain lookup*  
*The harness's fetch reads the passage.*

**Question.** In RFC 9293 (Transmission Control Protocol), if a TCP endpoint receives no MSS option at connection setup, what default send MSS must it assume for IPv4 and for IPv6, and with what requirement level?

**Key.**
- default send MSS, IPv4: 536 bytes (576 - 40)
- default send MSS, IPv6: 1220 bytes (1280 - 60)
- requirement level: MUST (MUST-15)

**The tempting wrong answer.** 1460 bytes for IPv4 or 1440 for IPv6 (Ethernet-sized values derived from a 1500 byte MTU), or 536 for both families. Those are not the defaults RFC 9293 prescribes when no option arrives.

**Sources.** https://www.rfc-editor.org/rfc/rfc9293.html#section-3.7.1

## physical engineering, units, datasheets and national rules

### X29  (Consumer-product RF safety: microwave oven leakage (Canada, Radiation Emitting Devices Regulations; US FDA 21 CFR 1030.10))

*two passages combined; two jurisdictions*

**Question.** A manufacturer ships the same domestic microwave oven to Canada and to the United States. At points at least 5 cm from the oven's external surface, what leakage power-density limit applies (a) in Canada under the Radiation Emitting Devices Regulations (Part III, microwave ovens), measured with the prescribed test load in place; (b) in the United States under the FDA microwave-oven performance standard, 21 CFR 1030.10, for an oven measured prior to acquisition by a purchaser; and (c) under that same US section once the oven has been acquired by a purchaser? Give each in mW/cm2.

**Key.**
- Canada, with the prescribed test load in place (Radiation Emitting Devices Regulations, Part III, s. 4(1)(a)(i)): 1.0 mW/cm2
- United States, 21 CFR 1030.10(c)(1), measured prior to acquisition by a purchaser: 1 mW/cm2 at any point 5 cm or more from the external surface
- United States, same paragraph, thereafter (once acquired by a purchaser): 5 mW/cm2 at any such point

**The tempting wrong answer.** Quoting 5 mW/cm2 as the single limit for both countries. In Canada 5.0 mW/cm2 is only the no-test-load limit for ovens operable empty (s. 4(1)(a)(ii)); in the US 5 mW/cm2 applies only after the oven is acquired by a purchaser, while the pre-sale limit is 1 mW/cm2.

**Sources.** https://laws-lois.justice.gc.ca/eng/regulations/C.R.C.,_c._1370/page-3.html; https://www.ecfr.gov/api/versioner/v1/full/2026-11-01/title-21.xml?part=1030&section=1030.10
### X30  (Occupational noise exposure limits, Canadian federal workplaces)

*plain lookup*

**Question.** Under Canada's general federal workplace health and safety regulations, the Canada Occupational Health and Safety Regulations (not the separate marine-vessel or offshore oil and gas regulations), an employee is exposed to a steady A-weighted sound pressure level of 93 dBA. What is the longest permitted exposure at that level, in hours per employee per 24-hour period, and what separate ceiling, in dBA, applies to the employee's 8-hour-normalised noise exposure level L(ex,8)?

**Key.**
- Maximum duration at 93 dBA per employee per 24 hours (Canada Occupational Health and Safety Regulations, SOR/86-304, Part VII, Schedule to s. 7.4): 2.0 hours
- Ceiling on noise exposure level L(ex,8) (s. 7.4(b)): 87 dBA (exposure level must not exceed 87 dBA)

**The tempting wrong answer.** Reading 8 hours at 85 dBA or 90 dBA as the limit. 85 dB is the rule of the Maritime and the Oil and Gas occupational health and safety regulations, which are other live federal regulations and answer a different question; the table here is on a 3 dB exchange rate starting at 87 dBA = 8.0 h (90 dBA = 4.0 h, 93 dBA = 2.0 h). 84 dBA is the s. 7.3 investigation trigger, not the limit.

**Sources.** https://laws-lois.justice.gc.ca/eng/regulations/SOR-86-304/FullText.html
### X31  (Radiocommunications licensing, Australia (ACMA low-interference-potential-devices class licence))

*plain lookup; current instrument replaced an older one*

**Question.** Under the Australian Radiocommunications (Low Interference Potential Devices) Class Licence that is in force on 17 November 2026, what maximum EIRP, in watts, is permitted for a 'digital modulation' radiocommunications transmitter operating in 2400-2483.5 MHz, what additional limit on radiated peak power spectral density applies to that class, and in what year was the instrument now in force made (its name carries the year)?

**Key.**
- Maximum EIRP, digital modulation, 2400-2483.5 MHz (Schedule 1, Table 8, item 7, column 3): 4 W
- Additional limitation (clause 43): radiated peak power spectral density must not be greater than 25 mW per 3 kHz
- Instrument in force and its commencement: Radiocommunications (Low Interference Potential Devices) Class Licence 2025, commenced at the start of 1 October 2025 (it replaced the 2015 licence)

**The tempting wrong answer.** Giving 500 mW (the frequency-hopping class, Table 8 item 2) or 10 mW (the generic 'Any' class, 2400-2483.5 MHz) instead of 4 W, or citing the 2015 licence, which is no longer in force.

**Sources.** https://www.legislation.gov.au/F2025L01047/asmade/2025-09-05/es/original/pdf; https://www.legislation.gov.au/F2025L01047/asmade/2025-09-05/text/original/pdf
### X32  (Occupational noise, Great Britain statutory instrument)

*plain lookup; document not named*

**Question.** A manufacturing employer in Great Britain asks what the legal exposure limit values for employee noise are (daily or weekly personal noise exposure in dB(A), and peak sound pressure in dB(C)), and whether the attenuation of hearing protectors the employer has issued may be counted when judging whether the upper exposure action value has been reached.

**Key.**
- Exposure limit value, daily or weekly personal noise exposure (Control of Noise at Work Regulations 2005, reg. 4(3)(a)): 87 dB(A)
- Exposure limit value, peak sound pressure (reg. 4(3)(b)): 140 dB(C)
- Hearing-protector attenuation when judging the upper exposure action value (reg. 4(5)): No: protector attenuation is taken into account only when applying the exposure limit values, not the lower or upper action values

**The tempting wrong answer.** Quoting the action values (lower 80 dB(A) / 135 dB(C); upper 85 dB(A) / 137 dB(C)) as the limits, or assuming hearing protection is credited against the action values.

**Sources.** https://www.legislation.gov.uk/uksi/2005/1643/regulation/4
### X33  (Occupational exposure limits, UK HSE EH40/2005)

*changed value: older figure widely quoted; status depends on a dated transitional note*

**Question.** In HSE's EH40/2005 Workplace exposure limits (fourth edition, 2020), what are the carbon monoxide long-term (8-hour TWA) and short-term (15-minute) workplace exposure limits in ppm? The table also lists a second, higher pair of ppm values for carbon monoxide: to whom did that pair apply, and does it still apply today (17 November 2026)?

**Key.**
- Long-term exposure limit (8-hr TWA), carbon monoxide: 20 ppm (23 mg/m3)
- Short-term exposure limit (15-minute), carbon monoxide: 100 ppm (117 mg/m3)
- Second pair, 30 ppm (8-hr) and 200 ppm (15-min): who it applied to: underground mining and tunnelling industries only, until 21/8/23
- Does that pair still apply on 17 November 2026: No, its stated end date 21 August 2023 has passed *(worked out, not printed)*

**The tempting wrong answer.** Quoting 30 ppm / 200 ppm (the older limits that stay printed on the table as the underground-mining transitional pair) as the current carbon monoxide WELs.

**Sources.** https://www.hse.gov.uk/pubns/priced/eh40.pdf
### X34  (Building fire safety, England (Approved Document B volume 1))

*changed value: older figure widely quoted; amendment changed the threshold; status date*  
*The harness's fetch reads the passage.*

**Question.** In Approved Document B (fire safety) Volume 1: Dwellings, for England, as currently published (2019 edition incorporating the 2020, 2022, 2025 and 2026 amendments): (a) blocks of flats with a top storey more than what height above ground level should be fitted with a sprinkler system throughout; (b) what was that sprinkler trigger height before the 2020 amendments; and (c) at what top-storey height should flats be served by more than one common stair, and from what date do the changes that introduced that recommendation take effect?

**Key.**
- (a) Sprinkler trigger today (para 7.4): top storey more than 11 m above ground level
- (b) Trigger height before the 2020 amendments: 30 m
- (c) Top-storey height for more than one common stair (para 3.30b): 18 m or more
- (c) Date the 2026 amendments introducing it take effect: 30 September 2026

**The tempting wrong answer.** Putting the 18 m figure on sprinklers (18 m is the second-stair trigger and the old high-rise yardstick; the sprinkler trigger is 'more than 11 m') or quoting 30 m, the pre-May-2020 sprinkler threshold.

**Sources.** https://assets.publishing.service.gov.uk/media/66d57a94d107658faec7e448/AD_B_2026_amendments.pdf; https://assets.publishing.service.gov.uk/media/6aa3bb335f6e942efe37f150/AD_B1_2026.pdf
### X35  (Fundamental physical constants (NIST CODATA))

*changed value: older figure widely quoted*

**Question.** What is the NIST-published CODATA 2022 recommended value of the Rydberg constant R_infinity in m^-1, with its standard uncertainty, and what was the CODATA 2018 value it replaced?

**Key.**
- CODATA 2022 value of R_infinity: 10 973 731.568 157 m^-1
- Standard uncertainty (2022): 0.000 012 m^-1 (concise form (12); relative 1.1 x 10^-12)
- CODATA 2018 value replaced: 10 973 731.568 160(21) m^-1

**The tempting wrong answer.** Giving the 2018 value 10 973 731.568 160(21) m^-1 (still widely copied) or the rounded 1.097 373 x 10^7 m^-1 without the 2022 digits.

**Sources.** https://physics.nist.gov/cgi-bin/cuu/Value?ryd; https://physics.nist.gov/cuu/pdf/wall_2018.pdf
### X36  (Spacecraft electrical bonding (NASA technical standard))

*trap: document states no such value; plain-looking lookup*  
*The harness's fetch reads the passage.*

**Question.** A designer asks what maximum RF impedance, in ohms at a stated frequency, NASA-STD-4003A (Electrical Bonding for NASA Launch Vehicles, Spacecraft, Payloads, and Flight Equipment) allows across a Class R (EMI/RF) bond joint. What does the standard actually require for a Class R joint?

**Key.**
- Numeric maximum RF impedance (ohms at a frequency) for a Class R joint: None is stated; the standard sets no ohms-at-frequency limit, only the qualitative requirement that impedance be low enough to prevent interference at the frequencies of interest (EBR 21)
- What the standard does specify numerically for each Class R joint (EBR 22, para 4.1.4b(1)): dc resistance not to exceed 2.5 milliohms

**The tempting wrong answer.** Inventing an RF impedance figure, or treating the 2.5 milliohm dc resistance as an RF impedance limit; the standard's own appendix says it has no RF design basis and that an acceptable RF bond may be in the ohms range.

**Sources.** https://standards.nasa.gov/system/files/tmp/NASA-STD-4003A_w-Change%201%20-%20Revalidated%2003-13-2026.pdf
### X37  (Tidal datums, NOAA CO-OPS (National Tidal Datum Epoch))

*plain lookup; status that is about to change*  
*The harness's fetch reads the passage.*

**Question.** According to NOAA CO-OPS, which 19-year National Tidal Datum Epoch is currently the basis for official U.S. tidal datums, which years will the replacement (fifth) epoch's water-level data cover, and what release year does NOAA currently propose for products based on the new epoch?

**Key.**
- Current National Tidal Datum Epoch: 1983-2001
- Replacement epoch (fifth NTDE) data years: 2002-2020
- Currently proposed release year for new NTDE products: 2029

**The tempting wrong answer.** Treating the 2002-2020 epoch as already in force; as of this page the 1983-2001 epoch is still the official one and the new products are proposed for 2029.

**Sources.** https://tidesandcurrents.noaa.gov/datum-updates/ntde/
### X38  (Traffic signals, FHWA MUTCD (11th Edition vs 2009))

*changed value: older figure widely quoted*

**Question.** In the MUTCD 11th Edition (December 2023), Section 4I.06 on pedestrian intervals and signal phases: what is the minimum duration of the buffer interval (steady UPRAISED HAND) that must follow the pedestrian change interval before a conflicting vehicular movement is released, what walking speed should the pedestrian clearance time be sized for by default, and what was the buffer-interval minimum in the 2009 MUTCD?

**Key.**
- 11th Edition minimum buffer interval: at least 2 seconds
- Default walking speed for pedestrian clearance time (Guidance): 3.5 feet per second (the Option allows up to 4 ft/s where an extended push-button function is installed)
- 2009 MUTCD minimum buffer interval: at least 3 seconds

**The tempting wrong answer.** Quoting the 2009 MUTCD's 3-second buffer interval for the 11th Edition (which now says at least 2 seconds).

**Sources.** https://mutcd.fhwa.dot.gov/pdfs/11th_Edition/mutcd11thedition.pdf; https://mutcd.fhwa.dot.gov/pdfs/2009r1r2/mutcd2009r1r2edition.pdf
### X39  (Oil spill prevention, US EPA (SPCC applicability))

*plain lookup; document not named; two conditions must both hold*  
*The harness's fetch reads the passage.*

**Question.** A US onshore industrial facility, not a vessel or part of a pipeline, stores oil in aboveground drums and tanks and in some completely buried tanks. Which two oil storage capacity ceilings, in US gallons, must it stay at or under to fall outside the coverage of EPA's oil spill prevention regulation for non-transportation-related facilities, and which aboveground containers count toward the aboveground total?

**Key.**
- Aggregate aboveground storage capacity ceiling (40 CFR 112.1(d)(2)(ii)): 1,320 U.S. gallons or less
- Which aboveground containers are counted: only containers of 55 U.S. gallons capacity or greater
- Completely buried storage capacity ceiling (40 CFR 112.1(d)(2)(i)): 42,000 U.S. gallons or less
- Combination rule: the facility must meet both requirements to be outside the part

**The tempting wrong answer.** Counting every container regardless of size (containers under 55 gal are not counted), or mixing up the two figures (42,000 gal is the completely buried ceiling, 1,320 gal the aboveground one).

**Sources.** https://www.ecfr.gov/api/versioner/v1/full/2026-11-01/title-40.xml?part=112&section=112.1
### X40  (Units and conversions, HVAC capacity (NIST SP 811 conversion factors))

*unit conversion; ambiguous unit: Btu_IT versus Btu_th; document not named*

**Question.** A US-made chiller is nameplated at 10 tons of refrigeration. Using the official conversion factor published by the US National Institute of Standards and Technology for the ton of refrigeration (defined as 12 000 Btu_IT per hour), what is the chiller's capacity in kW, to four significant figures?

**Key.**
- NIST factor, 1 ton of refrigeration (12 000 Btu_IT/h) to watts: 3.516 853 E+03 W
- Capacity of 10 tons of refrigeration: 35.17 kW (35 168.53 W) *(worked out, not printed)*

**The tempting wrong answer.** Using the thermochemical Btu (Btu_th/h = 2.928 751 E-01 W, giving about 35 145 W for 10 tons) or the 3.5 kW-per-ton rule of thumb (35 kW).

**Sources.** https://www.nist.gov/pml/special-publication-811/nist-guide-si-appendix-b-conversion-factors/nist-guide-si-appendix-b8
### X41  (Microcontroller datasheet, Microchip ATmega328P (DS40002061B))

*trap: document states no such value; plain-looking lookup*

**Question.** From Microchip's ATmega48A/PA/88A/PA/168A/PA/328/328P complete datasheet (DS40002061B, 09/2020), what is the junction-to-ambient thermal resistance (in degC/W) of the ATmega328P in the 28-pin PDIP package, and what maximum junction temperature or total power dissipation does the datasheet specify?

**Key.**
- Junction-to-ambient thermal resistance, maximum junction temperature, maximum power dissipation: None of these is stated: the datasheet gives no thermal resistance, junction-temperature or power-dissipation value for any package; a search of its full text for 'junction', 'thermal resistance', 'dissipation' and degC/W finds none

**The tempting wrong answer.** Quoting a theta-JA figure from another vendor's or another family's datasheet or a distributor page; this Microchip datasheet publishes none, so the safe-power budget has to be derived from the per-pin and VCC/GND current ratings.

**Sources.** https://ww1.microchip.com/downloads/aemDocuments/documents/MCU08/ProductDocuments/DataSheets/ATmega48A-PA-88A-PA-168A-PA-328-P-DS-DS40002061B.pdf
### X42  (Power MOSFET datasheet, Infineon IRF540NPbF)

*two passages combined; derived calculation*  
*The harness's fetch reads the passage.*

**Question.** In Infineon's IRF540NPbF datasheet (Rev. 2.1, 2026-07-24), what is the maximum power dissipation at a case temperature of 25 degC and the linear derating factor, and what maximum power dissipation does that derating allow at a case temperature of 100 degC (in W)?

**Key.**
- Maximum power dissipation at TC = 25 degC: 130 W
- Linear derating factor: 0.87 W/degC
- Maximum power dissipation at TC = 100 degC by linear derating: about 64.75 W (130 - 0.87 x 75) *(worked out, not printed)*

**The tempting wrong answer.** Using 130 W at every temperature, or the junction-to-ambient figure (62 degC/W) that applies to free-air operation without a heatsink and is a different limit.

**Sources.** https://www.infineon.com/dgdl/irf540npbf.pdf

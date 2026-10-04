# Paper outline: PaperLens

Working title: *PaperLens: Classifying research papers by publication venue and ranking from the PDF alone, with open metadata*

This is a scaffold for the author to write from. Every number below is produced by
`python eval/evaluate.py` and `python eval/report.py`; replace the placeholders marked
`[held-out]` once the larger sample has been evaluated. Suggested length: 6–8 pages in
a two-column format (IEEE/ACM style) or 10–12 pages single column.

## Abstract (150–200 words)

Problem (students and reviewers need to know whether a paper is a journal article, a
conference paper or a preprint, and how the venue ranks); gap (existing tools require
a DOI or manual search and do not combine rankings with indexing and reputation checks);
method (PDF parsing + four open metadata services + Scimago/CORE/Scopus/DOAJ/watchlists,
voting with a calibrated confidence); results (category accuracy, quartile and CORE
rank accuracy on the held-out set, with confidence intervals); availability (free web
tool and API, open source).

## 1. Introduction

- Why venue classification matters: thesis requirements, UGC/AICTE-style rules in India,
  reviewer workload, predatory and hijacked journals.
- What is hard: PDFs do not state their venue in a machine-readable way; preprints and
  published versions coexist; rankings live in separate, differently formatted lists.
- Contributions (bullet list):
  1. A pipeline that classifies a paper from its PDF or identifier into journal / conference /
     preprint and attaches the Scimago quartile or CORE rank.
  2. Verification against the Scopus source list (including discontinued titles), DOAJ,
     the Retraction Watch hijacked-journal list and a community predatory list.
  3. A labelled evaluation set of real open-access PDFs with labels taken from where
     each PDF was downloaded, not from any classifier (104 development + [held-out] test).
  4. An ablation showing how much comes from PDF parsing alone versus metadata services.
  5. A free, accessible (WCAG 2.2 AA) web tool and JSON API.

## 2. Related work

- Venue ranking systems: SJR (Guerrero-Bote & Moya-Anegón 2012), Scopus CiteScore, JCR
  impact factor (licensed), CORE conference ranking, Google Scholar Metrics (no API).
- Metadata infrastructure: CrossRef, OpenAlex (Priem et al. 2022), Semantic Scholar
  (Kinney et al. 2023), arXiv API; Unpaywall for open access.
- PDF metadata extraction: GROBID (Lopez 2009), CERMINE, Science Parse; note that these
  extract bibliographic headers but do not classify the venue or attach rankings.
- Predatory and hijacked journals: Beall's list and its successors, Retraction Watch
  Hijacked Journal Checker (Abalkina), Cabells (commercial).
- Position PaperLens as combining these layers for an end user, not as a new extractor.

## 3. System design

### 3.1 Inputs
PDF/DOCX upload, or DOI / arXiv ID / title (figure: screenshot of the input card).

### 3.2 PDF parsing (`classifier/pdf_parser.py`, `text_metadata.py`)
- Text extraction with tight word tolerance; rotated-text pass for the arXiv margin stamp.
- Identifier regexes: DOI (with line-break repair), ISSN with checksum, ISBN, arXiv ID.
- Title from font size, taking whole lines (small-caps initials), with document-info and
  first-line fallbacks.
- Venue line and its continuation; two-column pages read column by column.
- Scanned front pages detected and refused.
(Table: the text cues and what each votes for.)

### 3.3 Metadata enrichment (`metadata_fetcher.py`)
CrossRef, OpenAlex, Semantic Scholar, arXiv API in parallel; title matches must pass a
similarity threshold; published version preferred over preprint copies; rate-limit
handling without blocking. (Figure: data-flow diagram.)

### 3.4 Decision (`classifier.py`)
API votes (CrossRef type, OpenAlex source type, S2 venue type) and text votes;
rules for arXiv papers; confidence score from vote strengths. (Pseudo-code or table of
weights.)

### 3.5 Ranking and verification
ISSN-first journal lookup, exact-name-only fallback when an ISSN is known; conference
lookup by acronym, name, then name-in-text; Scopus status, DOAJ, hijacked/predatory
lists; OpenAlex venue statistics for unranked venues. State the design rule: a
warning is a reason to verify, never an accusation; name matches on watchlists are exact.

### 3.6 Data (Table: list, edition, size, licence — from `data/sources/README.md`)

### 3.7 Web application
Accessibility (axe 0 violations on all screens, keyboard and screen-reader focus
handling, reduced motion), performance (Lighthouse 95/100/100/100), privacy (files
deleted after analysis, no trackers), security (CSP, upload validation, rate limits).

## 4. Evaluation

### 4.1 Dataset
How papers were sampled and labelled (from `eval/README.md`): journals by quartile from
random open-access SJR journals via OpenAlex/CrossRef+Unpaywall; conferences from venue
archives (ACL Anthology, PMLR, NeurIPS, CVF); preprints from recent arXiv submissions
across CS, maths, physics, biology, economics, statistics. Development set (104) versus
held-out set ([held-out] papers, sampled after all rules were fixed). Table: composition.

### 4.2 Metrics
Category accuracy with Wilson 95% CI; per-class precision/recall/F1 and macro F1;
quartile, CORE rank and conference type accuracy on correctly categorised papers;
calibration by confidence band; median latency.

### 4.3 Systems compared
v2 (previous deployment), v3 text-only (ablation: no network), v3 full.

### 4.4 Results
- Table 1: system comparison (from `report.py`).  Development: 44.2% → 92.3% → 99.0%.
  Held-out: [held-out].
- Figure: accuracy by system (`results/figures/accuracy_by_system.svg`).
- Figure: confusion matrix (`confusion_full.svg`).
- Figure: calibration (`calibration_full.svg`).
- Table: per-class metrics.

### 4.5 Error analysis
Walk through each remaining error with its cause (scanned front pages; any held-out
errors). Explain which errors are refusals ("unknown" with low confidence) versus wrong
answers, and why refusing is preferable for this use.

### 4.6 Ablation discussion
What PDF parsing alone achieves (92.3%) and which cues matter most (rotated arXiv stamp,
venue line in two-column papers, journal name in header); what the services add
(quartile accuracy 76% → 100%).

## 5. Discussion and limitations

- Sample size and composition: conferences are computing venues (CORE's scope); IEEE
  conference PDFs are not open access, so the IEEE label comes from CVF copies.
- Dependence on external services and their rate limits; graceful degradation.
- Rankings judge venues, not papers.
- Scopus list and watchlists are snapshots; the update script and the edition shown in
  the UI mitigate staleness.
- UGC-CARE is not included (no machine-readable list); OCR for scanned papers is not run
  on the free hosting plan.
- Potential misuse: a Q1 badge is not proof of quality; the UI's wording was chosen with
  this in mind.

## 6. Conclusion and future work

OCR; learned title/venue extraction (GROBID) as an optional backend; more conference
rankings for non-computing fields (e.g. ERA, Qualis); user study with students and
reviewers; longitudinal tracking of discontinued journals.

## Reproducibility statement

Code (MIT), data lists with provenance, evaluation scripts, dataset CSV with URLs, and the
exact commands (`eval/README.md`). Note which lists are not redistributed (SJR, DOAJ,
Scopus) and how to re-download them (`update_data.py`).

## Checklist before submission

- [ ] Replace every `[held-out]` placeholder with numbers from `report.py` on the held-out set.
- [ ] Cite each data source and API (names and URLs are in `data/sources/README.md` and the About page).
- [ ] Keep the author list to the people who did the work; acknowledge tools used in an Acknowledgements note.
- [ ] Export figures: `rsvg-convert -f pdf results/figures/*.svg` or open the SVG in Inkscape.

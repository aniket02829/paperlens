# PaperLens evaluation

This directory measures how accurately PaperLens classifies real research papers from their PDF files alone.

## Method

**Dataset.** 440 open-access PDFs sampled on 2026-10-03 (`dataset.csv`): a 104-paper development set (`dataset_dev.csv`) and a 336-paper held-out set drawn afterwards (its composition is given with its results below). Each paper's label comes from where it was downloaded, not from PaperLens. The development set:

| Group | Papers | Source | Label |
|---|---|---|---|
| Journal | 40 (10 per quartile) | Publisher PDFs of OpenAlex works in randomly chosen open-access SJR journals | `journal`, quartile from SJR |
| Conference | 37 | The venues' own archives: ACL Anthology (ACL, EMNLP, NAACL, EACL, COLING, LREC, CoNLL, RANLP), PMLR (ICML, AISTATS, UAI, ACML, COLT), NeurIPS, CVF (CVPR, WACV) | `conference`, CORE rank and type (IEEE for CVF, National for RANLP, otherwise International) |
| Preprint | 27 | arXiv submissions from the previous days in 9 categories across CS, maths, biology, physics, economics and statistics, excluding any whose metadata mentioned a journal, DOI or acceptance | `arxiv` |

Conference ranks span A* to C plus National. Journals span all four quartiles and 40 different journals (one paper per journal).

**Procedure.** `evaluate.py` gives each PDF to `PaperClassifier.classify()` and compares the output with the label. Three systems are compared:

- **v2 (live site)**: commit `616e0b2`, the version deployed before this work.
- **v3, text only**: the new pipeline with every metadata API disabled, so only evidence printed in the PDF is used.
- **v3, full**: the new pipeline with CrossRef, OpenAlex, Semantic Scholar and arXiv.

All runs used no Semantic Scholar key. During the final v3 run OpenAlex's keyless daily budget for title searches was exhausted, so OpenAlex contributed DOI lookups only. The v3 numbers are therefore a conservative estimate.

**Metrics.** Category accuracy and per-class precision, recall and F1 (a paper predicted `unknown` counts as an error). Rank accuracy is measured on papers whose category was predicted correctly: exact quartile for journals, exact CORE rank for conferences, and exact type (IEEE / International / National) for conferences.

## Results (development set, 104 papers)

These 104 papers were used to find and fix failures, so the numbers below are a development-set result; the held-out set further down is the fair test. `python eval/report.py` regenerates the tables with 95% Wilson confidence intervals and the figures in `results/figures/`.

| Metric | v2 (live site) | v3 text only | v3 full |
|---|---|---|---|
| Category accuracy | 44.2% [35–54] | 92.3% [86–96] | **99.0%** [95–100] |
| Macro F1 | 0.419 | 0.957 | **0.996** |
| Journal F1 | 0.857 | 0.904 | **0.987** |
| Conference F1 | 0.400 | 0.987 | **1.000** |
| Preprint F1 | 0.000 | 0.981 | **1.000** |
| Quartile accuracy | 94.4% (n=36) | 75.8% (n=33) | **100%** (n=39) |
| CORE rank accuracy | 0% (n=10) | 78.4% (n=37) | **100%** (n=37) |
| Conference type accuracy | 50.0% (n=10) | 86.5% (n=37) | **100%** (n=37) |
| Median time per paper | 3.1 s | 1.8 s | 2.6 s |

**Confusion matrix, v3 full** (rows are true labels):

| | journal | conference | preprint | unknown |
|---|---|---|---|---|
| journal (40) | **39** | 0 | 0 | 1 |
| conference (37) | 0 | **37** | 0 | 0 |
| preprint (27) | 0 | 0 | **27** | 0 |

**Confidence calibration, v3 full:**

| Confidence | Papers | Accuracy |
|---|---|---|
| below 0.6 | 15 | 93.3% |
| 0.6 to 0.8 | 40 | 100% |
| 0.8 and above | 49 | 100% |

Higher confidence means higher accuracy, so the score is meaningful, although it is conservative below 0.6.

## Findings

- **v2 never detected a preprint and never produced a CORE rank.** Its conference table had been loaded with empty rows (the CORE export has no header row), and arXiv stamps were missed because they are printed sideways.
- **Most of the gain comes from reading the PDF properly.** Text-only v3 reaches 92.3%: reading the rotated arXiv stamp, keeping word spacing in tightly set text, rejoining DOIs and venue lines that wrap, reading two-column front pages column by column, taking whole lines for small-caps titles, recognising a journal name printed in the header, and finding CORE names inside venue lines.
- **The metadata services fix the rest.** They resolve journal identity from the DOI (quartile accuracy rises from 76% to 100%) and confirm conference names. Title searches prefer the published record over a preprint copy of the same paper.

## Remaining error (v3 full)

| Paper | Predicted | Cause |
|---|---|---|
| journal-Q2-W4377093113 | unknown (refused) | The front pages are scanned images; only typed footnotes are readable. PaperLens now recognises this and asks for the DOI or title instead of guessing. |

The four errors of the first v3 run (an SSRN preprint matched instead of the published article, a small-caps title, a two-column ICML footnote, and this scanned paper) were each traced to a parsing or search rule and fixed; the fixes are covered by unit tests in `tests/`.

## Results (held-out set, 336 papers)

After every rule above was fixed, a second, larger sample was drawn with `build_dataset.py --scale 3` (ids not in `dataset_dev.csv`): 120 journal papers (30 per quartile, one per journal, all fields), 147 conference papers (ACL 2023–24, EMNLP 2022–23, NAACL 2022/24, EACL 2023–24, COLING, LREC 2022/24, CoNLL, RANLP 2021/23, ICML, COLT, AISTATS 2023–24, UAI, ACML, ALT, NeurIPS 2022–23, CVPR 2023–24, ICCV 2023, WACV 2023–24) and 69 arXiv preprints from 21 categories across CS, maths, physics, biology, economics and statistics. OpenAlex's keyless budget was again exhausted, so title searches relied on CrossRef and arXiv.

| Metric | v3 text only | v3 full, first run | v3 full, after two fixes |
|---|---|---|---|
| Category accuracy | 88.7% [85–92] | 96.7% [94–98] | **97.9%** [96–99] |
| Macro F1 | 0.933 | 0.973 | **0.986** |
| Journal F1 | 0.885 | 0.974 | **0.974** |
| Conference F1 | 0.958 | 0.990 | **0.997** |
| Preprint F1 | 0.956 | 0.956 | **0.986** |
| Quartile accuracy | 75.0% (n=96) | 100% (n=114) | **100%** (n=114) |
| CORE rank accuracy | 74.5% (n=137) | 98.6% (n=146) | **98.6%** (n=146) |
| Conference type accuracy | 84.7% (n=137) | 99.3% (n=146) | **99.3%** (n=146) |

The *first run* is the honest held-out number: no rule had seen these papers. Its 11 errors were then inspected and two rules changed, so the *after two fixes* column is no longer strictly blind for those two rules: (1) an ISBN alone no longer counts as conference evidence (two journal issues with ISBNs had been called conferences), and (2) a title that CrossRef and OpenAlex do not know is looked up on arXiv, which recognises preprints whose PDF carries no arXiv stamp (four of them); a title-only arXiv match is weak evidence that a proceedings footer in the PDF can outweigh. Both are covered by unit tests. `results/*_heldout_first.*` keep the first run.

**Confusion matrix, held-out, after fixes** (rows are true labels):

| | journal | conference | preprint | unknown |
|---|---|---|---|---|
| journal (120) | **114** | 0 | 1 | 5 |
| conference (147) | 0 | **146** | 1 | 0 |
| preprint (69) | 0 | 0 | **69** | 0 |

**Remaining errors (7):**

| Paper | Predicted | Cause |
|---|---|---|
| conf-2022.naacl-main.39 | preprint | The ACL Anthology PDF carries an arXiv stamp; the services that know its NAACL venue (Semantic Scholar, OpenAlex) were rate-limited in this keyless run. |
| journal-Q2 (Annals of Functional Analysis) | preprint | Unpaywall's "open-access copy" of this article is the arXiv version, so the file really is a preprint copy; the published DOI is known to Semantic Scholar only. |
| journal-Q1 (História da Historiografia), journal-Q3 (Eurasian Chemical Communications) | refused | Scanned front pages; PaperLens asks for the DOI or title instead. |
| journal-Q2 (Humanitas), journal-Q3 (case report), journal-Q4 (RIG) | unknown | No DOI, ISSN or journal name on the front pages; the title line is an author list, an article-type banner, or a file name. PaperLens declines (confidence 0.30) rather than guessing. |

Five of the seven are refusals, not wrong answers. With API keys configured (as in production) the two preprint errors should resolve through Semantic Scholar's arXiv-to-DOI mapping.

## Limitations

- 440 papers in all (104 development, 336 held-out). Confidence intervals are reported with every accuracy; see `report.py`.
- Journal labels come from Scimago's quartile for the journal, and the PDF was found through OpenAlex or CrossRef + Unpaywall; in one case Unpaywall returned the arXiv copy rather than the publisher's PDF.
- Conference papers come from computing venues, which CORE ranks. IEEE-published PDFs could not be included because they are not open access; the IEEE label here comes from CVF versions of CVPR, ICCV and WACV.
- Journal papers are from open-access journals, so subscription-journal layouts are under-represented.
- The arXiv papers were preprints at sampling time; some may be published later.

## Reproducing

```bash
pip install -r requirements-dev.txt
python eval/build_dataset.py                 # downloads PDFs to eval/pdfs/ (not committed)
python eval/evaluate.py                      # v3 full     -> results/full.{csv,json}
python eval/evaluate.py --text-only          # v3 text     -> results/text_only.{csv,json}
git worktree add /tmp/paperlens-v2 616e0b2
python eval/evaluate.py --baseline /tmp/paperlens-v2   # v2 -> results/baseline.{csv,json}
python eval/report.py                        # Markdown tables with confidence intervals + SVG figures
python eval/build_dataset.py --scale 3       # the larger held-out sample (see below)
```

`build_dataset.py` samples new papers each time it runs (arXiv in particular changes daily). To evaluate the exact papers above, download the URLs listed in `dataset.csv` into `eval/pdfs/<id>.pdf`.

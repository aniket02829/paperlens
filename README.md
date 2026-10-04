# PaperLens

**Where was this paper published, and how good is the venue?**

PaperLens tells you whether a research paper is a **journal article** (with its Scimago quartile, Q1–Q4), a **conference paper** (IEEE / International / National, with its CORE rank, A*–C), or an **unreviewed preprint** (with suggested journals to submit to). Search by DOI, arXiv ID or title, or upload a PDF or Word file. It is free and needs no account.

Live site: https://paperlens-imv4.onrender.com

## Features

- **Search without uploading:** paste a DOI, a `doi.org` or arXiv link, an arXiv ID, or a title.
- **Upload one paper or up to 20 at once** (PDF or DOCX), with CSV export for batches.
- **Plain-language results:** "Published in a Q1 journal: top 25% of its field by citations", plus the evidence behind each answer and a confidence score. Copy a summary, a share link or a **BibTeX** entry, or print the report.
- **Scanned PDFs are recognised** and refused with advice (search by DOI or title) rather than guessed at.
- **Verification:** whether the journal is on the Scopus source list and still active, or was **discontinued by Scopus** (with the year), whether it is in DOAJ (with its fees and review process), whether a **hijacked clone** of the journal exists (Retraction Watch, with the authentic address), whether the journal or publisher name is on a **predatory list**, whether the paper was retracted, and a link to a free legal copy when one exists.
- **Unranked venues** still get OpenAlex's citation statistics (h-index, citations per paper), clearly labelled as an estimate rather than a rank.
- **Preprints that were later published** are matched to their published version.
- **Find journals** by name, ISSN or subject, filtered by quartile and open access, and **compare** up to 4 side by side.
- **Usable by everyone:** WCAG 2.2 AA (keyboard, screen readers, contrast, reduced motion), dark mode, mobile layout, no trackers or third-party scripts.
- **Free JSON API** (see below).

## How it works

1. **Read the paper.** `pdfplumber` / `python-docx` extract the text; shared regexes find the DOI, arXiv ID, ISSN (checksum-validated), ISBN and venue cues such as review dates, "Proceedings", and the IEEE conference footer. The PDF title is the largest text on page 1.
2. **Ask the metadata services, in parallel.** CrossRef (registered DOI type and venue), OpenAlex (venue type, DOAJ, open access, retractions, topics), Semantic Scholar (venue type, citations, published DOI of preprints) and the arXiv API. Title searches only count when the returned title really matches.
3. **Decide.** Each source votes for journal, conference or preprint; agreement between independent services counts most, and text cues count less. An arXiv paper counts as published only if a service names its venue.
4. **Rank.** Journals are matched to Scimago by ISSN, then by name; conferences to CORE by acronym, then by name.

## Accuracy

Measured on 440 real open-access PDFs whose true venue is known from where they were downloaded (ACL Anthology, PMLR, NeurIPS, CVF, publisher sites, arXiv). On the 336-paper held-out set, PaperLens gets the category right for **97.9%** of papers (95% CI 96–99%), the Scimago quartile for 100% of correctly identified journal papers and the CORE rank for 98.6% of conference papers; most remaining errors are refusals ("undetermined") rather than wrong answers. See [`eval/README.md`](eval/README.md) for the method, confidence intervals and error analysis, and rerun it with `python eval/evaluate.py`.

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/lookup` | `{"query": "<DOI, arXiv ID/link or title>"}` → classification |
| POST | `/analyze` | multipart `file` (PDF/DOCX) → classification |
| POST | `/analyze-bulk` | multipart `files` (up to 20) → results + summary |
| GET | `/api/journals/search` | `q`, `area`, `quartile`, `oa`, `page`, `per_page` |
| GET | `/api/journals?ids=1,2` | journals by id, for comparison |
| GET | `/api/journals/areas` | subject areas |
| GET | `/api/journals/suggest?field=…` | top journals for a field |
| GET | `/health`, `/stats` | status and database counts |

```bash
curl -X POST https://paperlens-imv4.onrender.com/api/lookup \
  -H 'Content-Type: application/json' -d '{"query": "10.1109/CVPR.2016.90"}'
```

Rate limits apply per IP (for example 30 lookups per minute).

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env          # add your Semantic Scholar key (optional)
python app.py                 # http://127.0.0.1:5000
python -m pytest              # offline test suite
cd frontend && npm install
npm run dev                   # http://127.0.0.1:5173, proxies the API to Flask on :5000
npm run build                 # typecheck and build into static/dist
```

The frontend is React + TypeScript + Vite + Tailwind, with Motion for animation. The built `static/dist/` is committed, so deploying needs no Node.

### Data

- `data/paper_classifier.db` (committed): 32,193 Scimago sources, 987 CORE conferences, 50,040 Scopus sources, 23,392 DOAJ journals, 471 hijacked journals and 2,493 predatory-list entries. The edition of each list is in the `meta` table and on the About page.
- Download the latest lists and rebuild: `python update_data.py` (yearly is enough; see [`data/sources/README.md`](data/sources/README.md)).
- Rebuild from the files already in `data/sources/`: `python setup_db.py`.
- Rebuild only conferences: `python setup_db.py --conferences-only data/sources/core.csv`.

### Configuration

Environment variables (or `.env` locally): `SEMANTIC_SCHOLAR_API_KEY`, `CROSSREF_EMAIL`, `SECRET_KEY`, and optional `RATELIMIT_*` overrides. Never commit keys.

## Data sources

[Scimago Journal Rank](https://www.scimagojr.com) · [CORE conference rankings](https://portal.core.edu.au/conf-ranks/) · [Scopus source list](https://www.elsevier.com/products/scopus/content) · [DOAJ](https://doaj.org) · [Retraction Watch Hijacked Journal Checker](https://retractionwatch.com/the-retraction-watch-hijacked-journal-checker/) · [Stop Predatory Journals](https://predatoryjournals.org) · [CrossRef](https://www.crossref.org) · [OpenAlex](https://openalex.org) · [Semantic Scholar](https://www.semanticscholar.org) · [arXiv](https://arxiv.org)

## License

MIT. Free to use for academic and research purposes.

## Author

**Aniket Kumar** · Jain (Deemed-to-be University), B.Tech Computer Science

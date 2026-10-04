# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

PaperLens is a Flask app that classifies a research paper as a **journal** paper (with SJR quartile Q1–Q4), a **conference** paper (IEEE / International / National, plus CORE rank A*–C), or a **preprint** (category value `arxiv`, with suggested journals). Input is an uploaded PDF/DOCX or a typed DOI / arXiv ID / title.

The backend (`app.py`, `classifier/`) is a JSON API. The UI is a **React 19 + TypeScript + Vite** app in `frontend/`, built into `static/dist/` (committed, so Render needs no Node). Flask serves `templates/index.html`, a shell that loads the built entry through Vite's manifest (`vite_assets()` in `app.py`). Views are hash-routed: `#/analyze`, `#/journals`, `#/compare`, `#/about`; `?q=<query>` runs a lookup on load and `?compare=1,2` preselects journals.

## Commands

```bash
pip install -r requirements-dev.txt
python app.py                      # dev server on 127.0.0.1:5000 (debug unless FLASK_ENV != development; PORT overrides)
python -m pytest                   # offline tests; every external API is monkeypatched in tests/conftest.py
python -m pytest tests/test_classifier.py::test_journal_by_doi   # one test
cd frontend && npm install && npm run build   # typecheck + build static/dist (commit the output); `npm run dev` serves on :5173 and proxies the API to Flask on :5000
python eval/build_dataset.py       # download the labelled evaluation PDFs into eval/pdfs/ (gitignored)
python eval/evaluate.py [--text-only | --baseline <old checkout>] [--subset dev|heldout]   # accuracy metrics into eval/results/
python eval/report.py [--subset heldout]   # Markdown tables with confidence intervals + SVG figures
python eval/build_dataset.py --scale 3     # larger sample; --from-files adds rows for PDFs already in eval/pdfs/
python setup_db.py                 # rebuild the database from data/sources/ (needs openpyxl, in requirements-dev)
python update_data.py              # download the latest SJR/CORE/Scopus/DOAJ/watchlists, then rebuild
python setup_db.py --conferences-only data/sources/core.csv   # rebuild only the CORE table
```

Production: `gunicorn app:app --workers 2 --threads 4 --timeout 120` (Procfile / render.yaml, Python 3.11 on Render; keep code 3.11-compatible).

## Architecture

**Request flow:** `app.py` validates uploads (extension plus file signature), saves to `uploads/` under a UUID-prefixed name, calls `PaperClassifier.classify(path)` and always deletes the file. `/api/lookup` calls `PaperClassifier.lookup(query)` instead. `PaperClassifier` is a lazily created process-wide singleton (`get_classifier()`). Bulk analysis classifies files in a 4-thread pool.

**Pipeline** (`classifier/classifier.py`, `_classify_parsed()`):
1. Parse: `PDFParser` / `DocxParser` are thin; all regexes and flag detection live in `classifier/text_metadata.py` (`empty_result()` defines the parsed-dict shape). Change extraction there, once. The PDF parser also reads the front pages column by column (`venue_context_alt`, for two-column footnotes), takes whole lines for the font-size title (small-caps initials), and flags scanned front pages (`looks_scanned` → a clear error, not a guess).
2. Enrich: `MetadataFetcher.gather()` queries CrossRef, OpenAlex, Semantic Scholar and the arXiv API in parallel, depending on whether there is a DOI, an arXiv ID, or only a title. Title searches only accept results whose title matches (`titles_match`). When a title is found nowhere else, `fetch_arxiv_by_title` asks arXiv (content words only; stop words make its `ti:` search return nothing): arXiv serves some PDFs without the margin stamp, and this is how they are recognised as preprints. Every fetch returns `{}` on failure. Responses are cached (TTL LRU); Semantic Scholar is throttled to 1 req/s across threads.
3. Decide: `_api_votes()` (CrossRef type, OpenAlex source/work type, S2 venue type) plus `_text_votes()` (file input only, including an SJR journal name printed in the header, `_journal_named_in_text`, which skips lines that describe a conference) → `_decide()`. An arXiv paper is "published" only if API votes reach 2; text cues alone can't override an arXiv stamp. Title searches prefer the published record over a preprint copy (`fetch_by_title` follows CrossRef's `is-preprint-of`).
4. Rank: journals by ISSN (CrossRef, OpenAlex, parsed, S2), then by name; conferences by acronym (`acronym_candidates`, S2 alternate names), then by name with filler words removed (`ConferenceDB.FILLER_WORDS`). Preprint suggestions use the OpenAlex subfield (same taxonomy as SJR), then `ARXIV_TO_SJR_CATEGORY`, then S2 fields.

**Things to know:**
- Signals are a `Signals` object: `add(key, message)`. Confidence (`_calculate_confidence`) uses the keys and vote counts, never the message text, so messages can be reworded freely.
- Every result starts from `_base_result()`, so all categories share the same keys. Add new fields there; `tests/test_classifier.py::test_every_result_has_the_same_keys` enforces it. The frontend mirrors them in `frontend/src/types.ts` (`PaperResult`) and reads them in `views/analyze/ResultCard.tsx` and `BulkResult.tsx`.
- `category` values: `journal | conference | arxiv | unknown | error`. `arxiv` means any preprint (bioRxiv too); the UI calls it "Preprint".
- `ReadOnlyDB` (`classifier/db_base.py`) opens one read-only SQLite connection per thread and builds an in-memory name index on first use.
- Frontend safety: React escapes text, so never use `dangerouslySetInnerHTML`; external links go through `safeUrl()` / `<ExternalLink>`. The CSP in `app.py` forbids inline scripts and inline `<style>`, so add no CDN assets, inline scripts or components that inject style tags (setting `element.style` from JS is fine).
- Design tokens: colours, radii and shadows are CSS variables in `frontend/src/styles/tokens.css` (light and `.dark`), mapped to Tailwind names in `frontend/tailwind.config.js` (`bg-surface`, `text-muted`, `bg-q1-soft`…). Use those names, never raw hex or gray-*; every text pairing was checked for WCAG AA. Fonts are self-hosted (Crimson Pro headings, Atkinson Hyperlegible body).
- Motion: `motion/react` with `LazyMotion` + `m.*` and `MotionConfig reducedMotion="user"`. Features are bundled eagerly on purpose: content starts at opacity 0 and `AnimatePresence mode="wait"` gates what renders next, so a late feature chunk would hide results. The Journals, Compare and About views are `React.lazy` chunks instead (`App.tsx`, with `ViewBoundary` for a failed chunk); `focusHeading` polls briefly for the new view's `h1`.
- Responses are gzip/brotli compressed by Flask-Compress and `/static/dist/assets/*` (content-hashed) get a one-year immutable cache header, both in `app.py`. `static/og.png` is the social preview image (rendered from a scratch HTML page; regenerate by hand if the branding changes).
- BibTeX export is built client-side in `frontend/src/lib/bibtex.ts` from the result fields.
- Text built in code lives in `frontend/src/lib/strings.ts` (`t('key', {vars})`). Tailwind purges unused classes, so write full class names.

**Database:** `data/paper_classifier.db` is committed. Tables: `journals` (SJR; `id` is the Scimago source id, so ids survive rebuilds; `source_type` separates journals from book series and proceedings), `conferences` (CORE), `doaj_journals`, `scopus_sources` (every Scopus source with `active`/`discontinued`), `watchlist` (`kind` = hijacked | predatory_journal | predatory_publisher) and `meta` (list editions, shown on About via `/stats`). `setup_db.py` builds it from `data/sources/` (big files gitignored; `update_data.py` downloads them). SJR is `;`-delimited with comma decimals; the CORE export has **no header row** (`read_core_rows` handles both). ISSNs are stored without hyphens. CORE ranks include values like `National: India`, which mean a National conference.

**Venue checks** (`classifier/venue_checks.py`, `VenueChecksDB`) run after classification for journals and conferences: Scopus status, DOAJ entry, hijacked clone, predatory lists, and OpenAlex `fetch_openalex_source` statistics when the venue is in neither SJR nor CORE. Name matches on these lists are exact (normalised) on purpose: a fuzzy match could accuse the wrong journal. Likewise `_classify_journal` only fuzzy-matches names when no ISSN is known; a known ISSN missing from SJR means "unranked", not "find something similar". `trust.warnings` keys drive the frontend alerts (`Warnings` in `ResultCard.tsx`).

**Config:** `config.py` reads `SEMANTIC_SCHOLAR_API_KEY`, `CROSSREF_EMAIL`, `SECRET_KEY` and `RATELIMIT_*` from the environment (or `.env` via python-dotenv). Never hardcode keys; the repo is public.

## Deployment

Render (`render.yaml`, free plan, auto-deploys on push to main). The free plan sleeps after 15 minutes idle; the frontend shows a "server may be waking up" note on slow requests. The live URL is in the OG and canonical tags in `templates/index.html`.

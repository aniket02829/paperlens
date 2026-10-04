# Data sources

`python update_data.py` downloads these files and rebuilds `data/paper_classifier.db`;
`python setup_db.py` rebuilds from the files already here. The three large files are not
committed (see `.gitignore`); the small lists are, so the database can be rebuilt exactly.

| File | Source | What it gives PaperLens | Update rhythm |
|---|---|---|---|
| `sjr.csv` (not committed) | [Scimago Journal Rank](https://www.scimagojr.com/journalrank.php) export | journal quartiles, SJR score, h-index, source type | yearly (spring) |
| `core.csv` | [CORE conference ranking](https://portal.core.edu.au/conf-ranks/) export (no header row) | CORE ranks A*–C, National | every two years |
| `scopus_sources.xlsx` (not committed) | [Scopus source title list](https://www.elsevier.com/products/scopus/content), Elsevier | every Scopus-indexed source, active/inactive, titles discontinued by Scopus with year and reason, serial conference proceedings | monthly |
| `doaj.csv` (not committed) | [DOAJ](https://doaj.org/csv) full export | open-access journals with fees, review process, licence | weekly |
| `rw_hijacked.csv` | [Retraction Watch Hijacked Journal Checker](https://retractionwatch.com/the-retraction-watch-hijacked-journal-checker/) | hijacked (cloned) journal websites with the authentic journal's ISSN and URL | weekly |
| `spj_journals.csv`, `spj_publishers.csv` | [Stop Predatory Journals](https://github.com/stop-predatory-journals/stop-predatory-journals.github.io) | community-maintained predatory journal and publisher names | occasional |

The edition of each list in the current database is stored in the `meta` table and shown on
the About page (`/stats` returns it).

## Licences and use

- Scimago data is free for non-commercial use with attribution.
- CORE rankings are published openly by the CORE association.
- The Scopus source list is published by Elsevier for public download; PaperLens stores only
  indexing facts (title, ISSN, active/discontinued, coverage), not Scopus content.
- DOAJ metadata is CC0.
- The Retraction Watch Hijacked Journal Checker is free to use with attribution.
- Stop Predatory Journals is a community list: PaperLens treats a match as a reason to verify,
  never as a verdict, and matches names exactly to avoid accusing a journal with a similar name.

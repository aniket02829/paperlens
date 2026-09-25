# 🔍 PaperLens — AI-Powered Research Paper Classifier

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

**PaperLens** is a web application that analyzes uploaded research papers and classifies them by publication type and quality ranking.

## ✨ Features

- **Upload PDF or DOCX** research papers
- **Automatic Classification**:
  - 📘 **Journal Papers** → Q1, Q2, Q3, Q4 quartile ranking (Scimago/SJR)
  - 📗 **Conference Papers** → IEEE / International / National + CORE ranking (A*, A, B, C)
  - 📦 **Arxiv Preprints** → Suggests suitable journals for publication
- **Single & Bulk Upload** modes
- **Real-time API enrichment** via CrossRef & Semantic Scholar
- **32,000+ journals** and **986 conferences** in the database

## 🛠 Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python, Flask |
| Frontend | HTML, Tailwind CSS, JavaScript |
| Database | SQLite (Scimago SJR + CORE rankings) |
| APIs | CrossRef, Semantic Scholar |
| PDF Parsing | pdfplumber |
| DOCX Parsing | python-docx |

## 🚀 Quick Start

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/paperlens.git
cd paperlens

# Install dependencies
pip install -r requirements.txt

# Start the server
python app.py

# Open http://127.0.0.1:5000
```

## 📊 How It Works

1. **Parse** — Extracts text, DOI, ISSN, arXiv ID from the uploaded paper
2. **Enrich** — Queries CrossRef & Semantic Scholar APIs for metadata
3. **Classify** — Determines Journal vs Conference vs Arxiv using weighted signals
4. **Rank** — Looks up quartile (Q1-Q4) or CORE rank (A*-C) from local database
5. **Suggest** — For Arxiv papers, recommends top journals in the field

## 📁 Project Structure

```
paperlens/
├── app.py                     # Flask web server
├── config.py                  # Configuration & API keys
├── setup_db.py                # Database builder from CSV data
├── classifier/
│   ├── classifier.py          # Main classification engine
│   ├── pdf_parser.py          # PDF text & metadata extraction
│   ├── docx_parser.py         # DOCX text extraction
│   ├── metadata_fetcher.py    # CrossRef & Semantic Scholar API
│   ├── journal_db.py          # SJR journal quartile lookup
│   └── conference_db.py       # CORE conference ranking lookup
├── data/
│   └── paper_classifier.db    # SQLite database (32K journals, 986 conferences)
├── templates/
│   └── index.html             # Frontend UI
├── static/
│   ├── css/style.css
│   └── js/app.js
└── uploads/                   # Temporary upload storage
```

## 📖 Data Sources

- **Scimago Journal Rankings (SJR)** — [scimagojr.com](https://www.scimagojr.com)
- **CORE Conference Rankings** — [portal.core.edu.au](http://portal.core.edu.au/conf-ranks/)
- **CrossRef API** — [crossref.org](https://www.crossref.org)
- **Semantic Scholar API** — [semanticscholar.org](https://www.semanticscholar.org)

## 📝 License

MIT License — Free to use for academic and research purposes.

## 👨‍💻 Author

**Aniket Kumar** — Jain (Deemed-to-be University), B.Tech Computer Science

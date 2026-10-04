"""Shared fixtures. Network access is blocked: every external API call is faked."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import config  # noqa: E402
from classifier.metadata_fetcher import MetadataFetcher  # noqa: E402


class FakeAPIs:
    """Canned API responses keyed by DOI / arXiv ID / title."""

    def __init__(self):
        self.crossref = {}
        self.openalex = {}
        self.s2 = {}
        self.crossref_titles = {}
        self.openalex_titles = {}
        self.openalex_sources = {}
        self.arxiv = {}
        self.arxiv_titles = {}


@pytest.fixture
def fake_apis(monkeypatch):
    fake = FakeAPIs()
    monkeypatch.setattr(MetadataFetcher, 'fetch_by_doi', lambda self, doi: dict(fake.crossref.get(doi.lower(), {})))
    monkeypatch.setattr(MetadataFetcher, 'fetch_openalex', lambda self, doi: dict(fake.openalex.get(doi.lower(), {})))
    monkeypatch.setattr(MetadataFetcher, 'fetch_semantic_scholar', lambda self, ident: dict(fake.s2.get(ident.lower(), {})))
    monkeypatch.setattr(MetadataFetcher, 'fetch_by_title', lambda self, t: dict(fake.crossref_titles.get(t.lower(), {})))
    monkeypatch.setattr(MetadataFetcher, 'fetch_arxiv', lambda self, i: dict(fake.arxiv.get(i.lower(), {})))
    monkeypatch.setattr(MetadataFetcher, 'fetch_openalex_by_title', lambda self, t: dict(fake.openalex_titles.get(t.lower(), {})))
    monkeypatch.setattr(MetadataFetcher, 'fetch_openalex_source', lambda self, s: dict(fake.openalex_sources.get(s, {})))
    monkeypatch.setattr(MetadataFetcher, 'fetch_arxiv_by_title', lambda self, t: dict(fake.arxiv_titles.get(t.lower(), {})))
    return fake


@pytest.fixture
def classifier(fake_apis):
    from classifier.classifier import PaperClassifier
    return PaperClassifier(config.DATABASE_PATH, 'test@example.com', None)


@pytest.fixture
def app_client(fake_apis, monkeypatch):
    import app as app_module
    monkeypatch.setattr(app_module, '_classifier', None)
    app_module.app.config['TESTING'] = True
    app_module.limiter.enabled = False
    with app_module.app.test_client() as client:
        yield client


def make_pdf(path, lines, title=None, title_size=20):
    """Write a simple PDF: an optional big title, then body lines in normal size."""
    from fpdf import FPDF
    pdf = FPDF()
    pdf.add_page()
    if title:
        pdf.set_font('Helvetica', 'B', title_size)
        pdf.multi_cell(0, 10, title, new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Helvetica', size=10)
    for line in lines:
        pdf.multi_cell(0, 6, line, new_x='LMARGIN', new_y='NEXT')
    pdf.output(str(path))
    return str(path)


def make_docx(path, paragraphs):
    import docx
    doc = docx.Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    doc.save(str(path))
    return str(path)

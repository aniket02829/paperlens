"""Configuration file for the Research Paper Classifier (PaperLens).

In production, set environment variables:
    SEMANTIC_SCHOLAR_API_KEY - Your Semantic Scholar API key
    CROSSREF_EMAIL - Email for CrossRef polite pool
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# API Keys — reads from environment variables first, falls back to defaults
SEMANTIC_SCHOLAR_API_KEY = os.environ.get(
    'SEMANTIC_SCHOLAR_API_KEY',
    's2k-y2A28R07Oz1Hyl0BQVlz0Mo1UOVPGpm3U0BdhUMB'
)
CROSSREF_EMAIL = os.environ.get(
    'CROSSREF_EMAIL',
    'juug25btech29115@jainuniversity.ac.in'
)

# Paths
DATABASE_PATH = os.path.join(BASE_DIR, 'data', 'paper_classifier.db')
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')

# Limits
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'doc'}

# Flask secret key for sessions (generate a random one in production)
SECRET_KEY = os.environ.get('SECRET_KEY', 'paperlens-dev-key-change-in-production')

"""Configuration file for the Research Paper Classifier (PaperLens).

Settings come from environment variables. For local development you can put them
in a .env file (see .env.example); it is loaded automatically and never committed.

    SEMANTIC_SCHOLAR_API_KEY - Semantic Scholar API key (optional, raises the rate limit)
    OPENALEX_API_KEY         - OpenAlex API key (optional but recommended in production:
                               without it, title searches share a small daily budget per IP)
    CROSSREF_EMAIL           - contact email for the CrossRef/OpenAlex polite pools
    SECRET_KEY               - Flask secret key
    RATELIMIT_STORAGE_URI    - where rate-limit counters live (default: in memory)
"""
import os

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))
except ImportError:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# API keys: never hardcode secrets here, this file is public on GitHub.
SEMANTIC_SCHOLAR_API_KEY = os.environ.get('SEMANTIC_SCHOLAR_API_KEY') or None
OPENALEX_API_KEY = os.environ.get('OPENALEX_API_KEY') or None
CROSSREF_EMAIL = os.environ.get('CROSSREF_EMAIL', 'juug25btech29115@jainuniversity.ac.in')

# Paths
DATABASE_PATH = os.path.join(BASE_DIR, 'data', 'paper_classifier.db')
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')

# Limits
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB per request
ALLOWED_EXTENSIONS = {'pdf', 'docx'}
MAX_BULK_FILES = 20
MAX_QUERY_LENGTH = 500

# Rate limits per visitor IP (Flask-Limiter syntax)
RATELIMIT_DEFAULT = os.environ.get('RATELIMIT_DEFAULT', '120 per minute')
RATELIMIT_ANALYZE = os.environ.get('RATELIMIT_ANALYZE', '20 per minute;200 per day')
RATELIMIT_BULK = os.environ.get('RATELIMIT_BULK', '3 per minute;30 per day')
RATELIMIT_LOOKUP = os.environ.get('RATELIMIT_LOOKUP', '30 per minute;500 per day')
RATELIMIT_STORAGE_URI = os.environ.get('RATELIMIT_STORAGE_URI', 'memory://')

# Flask secret key for sessions (generate a random one in production)
SECRET_KEY = os.environ.get('SECRET_KEY', 'paperlens-dev-key-change-in-production')

APP_VERSION = '3.0.0'

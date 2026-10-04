"""
Flask web application for the Research Paper Classifier (PaperLens).

Routes:
    GET  /                       - Serve the main page
    POST /analyze                - Analyze a single uploaded paper
    POST /analyze-bulk           - Analyze multiple uploaded papers
    POST /api/lookup             - Classify a paper from a DOI, arXiv ID/link, or title
    GET  /api/journals/search    - Search journals by title, ISSN or subject, with filters
    GET  /api/journals           - Fetch journals by id (?ids=1,2,3) for comparison
    GET  /api/journals/areas     - List subject areas for the search filter
    GET  /api/journals/suggest   - Top journals for a research field
    GET  /health                 - Health check endpoint
    GET  /stats                  - Database statistics
"""
import os
import json
import uuid
import logging
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Optional, Tuple

from flask import Flask, request, jsonify, render_template
from flask_compress import Compress
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename

import config
from classifier.classifier import PaperClassifier
from classifier.journal_db import JournalDB, QUARTILES

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = config.MAX_CONTENT_LENGTH
app.config['UPLOAD_FOLDER'] = config.UPLOAD_FOLDER
app.config['SECRET_KEY'] = config.SECRET_KEY
app.json.sort_keys = False

# gzip responses (the frontend bundle shrinks from ~420 KB to ~130 KB); Render's proxy
# does not compress for us.
app.config['COMPRESS_MIMETYPES'] = ['text/html', 'text/css', 'application/javascript', 'text/javascript',
                                    'application/json', 'image/svg+xml']
Compress(app)

# Render (and most hosts) sit behind one proxy; trust its X-Forwarded-For so
# rate limits apply per visitor rather than to the proxy's address.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[config.RATELIMIT_DEFAULT],
    storage_uri=config.RATELIMIT_STORAGE_URI,
)

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize classifier (lazy - created on first request)
_classifier = None

# The first bytes of each accepted file type, so a renamed .exe is rejected.
FILE_SIGNATURES = {'pdf': [b'%PDF'], 'docx': [b'PK\x03\x04']}

CONTENT_SECURITY_POLICY = '; '.join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self'",
    "font-src 'self'",
    "img-src 'self' data:",
    "connect-src 'self'",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
])


VITE_MANIFEST = os.path.join(config.BASE_DIR, 'static', 'dist', '.vite', 'manifest.json')
VITE_ENTRY = 'src/main.tsx'


@lru_cache(maxsize=1)
def vite_assets() -> dict:
    """The built frontend's hashed JS and CSS paths, read from Vite's manifest.

    Build them with `npm run build` in frontend/ (the output in static/dist is committed).
    """
    try:
        with open(VITE_MANIFEST, encoding='utf-8') as f:
            entry = json.load(f)[VITE_ENTRY]
    except (OSError, KeyError, ValueError):
        logger.error(f"Frontend build missing: run `npm run build` in frontend/ ({VITE_MANIFEST})")
        return {'js': None, 'css': []}
    return {'js': f"/static/dist/{entry['file']}", 'css': [f'/static/dist/{c}' for c in entry.get('css', [])]}


def get_classifier() -> PaperClassifier:
    """Get or create the PaperClassifier singleton instance."""
    global _classifier
    if _classifier is None:
        if not os.path.exists(config.DATABASE_PATH):
            logger.error(f"Database not found at {config.DATABASE_PATH}. Run setup_db.py first.")
            raise RuntimeError(
                "Database not initialized. Please run: python setup_db.py"
            )
        _classifier = PaperClassifier(
            db_path=config.DATABASE_PATH,
            crossref_email=config.CROSSREF_EMAIL,
            semantic_scholar_api_key=config.SEMANTIC_SCHOLAR_API_KEY,
            openalex_api_key=config.OPENALEX_API_KEY
        )
        logger.info("PaperClassifier initialized successfully.")
    return _classifier


def file_extension(filename: str) -> str:
    return filename.rsplit('.', 1)[1].lower() if '.' in filename else ''


def allowed_file(filename: str) -> bool:
    """Check if the uploaded file has an allowed extension."""
    return file_extension(filename) in config.ALLOWED_EXTENSIONS


def has_valid_signature(file, extension: str) -> bool:
    """Check that the file's first bytes match its extension (PDFs may have leading junk)."""
    head = file.stream.read(1024)
    file.stream.seek(0)
    signatures = FILE_SIGNATURES.get(extension, [])
    if extension == 'pdf':
        return any(sig in head for sig in signatures)
    return any(head.startswith(sig) for sig in signatures)


def validate_upload(file) -> Optional[str]:
    """Return an error message for an unacceptable upload, or None if it is fine."""
    if not file or file.filename == '':
        return 'No file selected. Please choose a file to upload.'
    if not allowed_file(file.filename):
        if file_extension(file.filename) == 'doc':
            return 'Old Word (.doc) files are not supported. Please save the file as .docx or PDF and try again.'
        return 'Invalid file type. Please upload a PDF or DOCX file.'
    if not has_valid_signature(file, file_extension(file.filename)):
        return "This file's contents don't match its extension. Please upload a real PDF or DOCX file."
    return None


def save_uploaded_file(file) -> Tuple[str, str]:
    """
    Save an uploaded file to the uploads directory with a unique name.

    Returns:
        Tuple of (saved_path, original_filename)
    """
    original_name = secure_filename(file.filename) or f'upload.{file_extension(file.filename)}'
    # Add UUID prefix to avoid filename collisions
    unique_name = f"{uuid.uuid4().hex[:8]}_{original_name}"
    save_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
    file.save(save_path)
    return save_path, original_name


def cleanup_file(file_path: str) -> None:
    """Remove a temporary uploaded file."""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except OSError as e:
        logger.warning(f"Could not remove temp file {file_path}: {e}")


def error_response(message: str, status: int):
    return jsonify({'success': False, 'error': message}), status


def public_journal(row: Dict) -> Dict:
    """The journal fields the frontend needs, with lists split out of the SJR strings."""
    issns = [i.strip() for i in (row.get('issn_list') or '').split(',') if i.strip()]
    return {
        'id': row['id'],
        'title': row.get('title'),
        'issn': [f'{i[:4]}-{i[4:]}' if len(i) == 8 else i for i in issns],
        'sjr_score': round(row['sjr_score'], 3) if row.get('sjr_score') else None,
        'quartile': row.get('best_quartile') or None,
        'quartile_color': JournalDB.get_quartile_color(row.get('best_quartile')),
        'h_index': row.get('h_index'),
        'publisher': row.get('publisher') or None,
        'country': row.get('country') or None,
        'categories': [c.strip() for c in (row.get('categories') or '').split(';') if c.strip()],
        'areas': [a.strip() for a in (row.get('areas') or '').split(';') if a.strip()],
        'open_access': row.get('open_access') == 'Yes',
    }


def int_arg(name: str, default: int, low: int, high: int) -> int:
    try:
        value = int(request.args.get(name, default))
    except (TypeError, ValueError):
        value = default
    return max(low, min(value, high))


# ==================== SECURITY HEADERS ====================

@app.after_request
def add_security_headers(response):
    response.headers.setdefault('Content-Security-Policy', CONTENT_SECURITY_POLICY)
    response.headers.setdefault('X-Content-Type-Options', 'nosniff')
    response.headers.setdefault('X-Frame-Options', 'DENY')
    response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
    response.headers.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
    if request.is_secure:
        response.headers.setdefault('Strict-Transport-Security', 'max-age=31536000')
    # Vite names built assets by content hash, so they can be cached for a year.
    if request.path.startswith('/static/dist/assets/'):
        response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    return response


# ==================== ROUTES ====================

@app.route('/')
def index():
    """Serve the main page."""
    return render_template('index.html', assets=vite_assets())


@app.route('/analyze', methods=['POST'])
@limiter.limit(config.RATELIMIT_ANALYZE)
def analyze():
    """
    Analyze a single uploaded research paper.

    Expects: multipart/form-data with a 'file' field.
    Returns: JSON with classification results.
    """
    if 'file' not in request.files:
        return error_response('No file provided. Please upload a PDF or DOCX file.', 400)

    file = request.files['file']
    problem = validate_upload(file)
    if problem:
        return error_response(problem, 400)

    saved_path = None
    try:
        # Save the uploaded file
        saved_path, original_name = save_uploaded_file(file)
        logger.info(f"Analyzing file: {original_name}")

        # Run classification
        classifier = get_classifier()
        result = classifier.classify(saved_path)
        result['filename'] = original_name

        return jsonify({
            'success': True,
            'result': result
        })

    except RuntimeError as e:
        logger.error(f"Runtime error: {e}")
        return error_response(str(e), 500)

    except Exception as e:
        logger.error(f"Unexpected error analyzing file: {e}", exc_info=True)
        return error_response('An unexpected error occurred while analyzing the file. Please try again.', 500)

    finally:
        # Clean up the uploaded file
        if saved_path:
            cleanup_file(saved_path)


@app.route('/analyze-bulk', methods=['POST'])
@limiter.limit(config.RATELIMIT_BULK)
def analyze_bulk():
    """
    Analyze multiple uploaded research papers.

    Expects: multipart/form-data with multiple 'files' fields.
    Returns: JSON with classification results for each file.
    """
    if 'files' not in request.files:
        return error_response('No files provided. Please upload PDF or DOCX files.', 400)

    files = [f for f in request.files.getlist('files') if f and f.filename]
    if not files:
        return error_response('No files selected. Please choose files to upload.', 400)
    if len(files) > config.MAX_BULK_FILES:
        return error_response(f'Too many files. You can analyze up to {config.MAX_BULK_FILES} papers at once.', 400)

    errors = []
    to_classify = []
    saved_paths = []

    try:
        classifier = get_classifier()

        for file in files:
            problem = validate_upload(file)
            if problem:
                errors.append({'filename': file.filename, 'error': problem})
                continue
            saved_path, original_name = save_uploaded_file(file)
            saved_paths.append(saved_path)
            to_classify.append((saved_path, original_name))

        def classify_one(item):
            path, name = item
            logger.info(f"Analyzing file (bulk): {name}")
            try:
                result = classifier.classify(path)
                result['filename'] = name
                return result, None
            except Exception as e:
                logger.error(f"Error analyzing {name}: {e}", exc_info=True)
                return None, {'filename': name, 'error': 'Could not analyze this file.'}

        # Most of the time is spent waiting on the metadata APIs, so a few threads help a lot.
        with ThreadPoolExecutor(max_workers=4) as pool:
            outcomes = list(pool.map(classify_one, to_classify))

        results = [r for r, _ in outcomes if r is not None]
        errors += [e for _, e in outcomes if e is not None]

        # Summary statistics
        summary = {
            'total': len(results) + len(errors),
            'successful': len(results),
            'failed': len(errors),
            'journals': sum(1 for r in results if r.get('category') == 'journal'),
            'conferences': sum(1 for r in results if r.get('category') == 'conference'),
            'arxiv': sum(1 for r in results if r.get('category') == 'arxiv'),
            'unknown': sum(1 for r in results if r.get('category') in ('unknown', 'error')),
        }

        return jsonify({
            'success': True,
            'results': results,
            'errors': errors,
            'summary': summary
        })

    except RuntimeError as e:
        logger.error(f"Runtime error: {e}")
        return error_response(str(e), 500)

    except Exception as e:
        logger.error(f"Unexpected error in bulk analysis: {e}", exc_info=True)
        return error_response('An unexpected error occurred. Please try again.', 500)

    finally:
        # Clean up all uploaded files
        for path in saved_paths:
            cleanup_file(path)


@app.route('/api/lookup', methods=['POST'])
@limiter.limit(config.RATELIMIT_LOOKUP)
def lookup():
    """
    Classify a paper without uploading it.

    Expects: JSON {"query": "<DOI, DOI link, arXiv ID/link, or title>"}
    """
    payload = request.get_json(silent=True) or {}
    query = str(payload.get('query') or request.form.get('query') or '').strip()
    if not query:
        return error_response("Please enter a DOI, an arXiv ID or link, or the paper's title.", 400)
    if len(query) > config.MAX_QUERY_LENGTH:
        return error_response(f'That is too long. Please enter at most {config.MAX_QUERY_LENGTH} characters.', 400)

    try:
        result = get_classifier().lookup(query)
        if result['category'] == 'error':
            return error_response(result['error'], 400)
        return jsonify({'success': True, 'result': result})
    except RuntimeError as e:
        logger.error(f"Runtime error: {e}")
        return error_response(str(e), 500)
    except Exception as e:
        logger.error(f"Unexpected error in lookup: {e}", exc_info=True)
        return error_response('An unexpected error occurred. Please try again.', 500)


@app.route('/api/journals/search')
def journal_search():
    """Search journals. Query args: q, area, quartile (Q1-Q4), oa (1/0), page, per_page."""
    quartile = (request.args.get('quartile') or '').upper()
    oa_arg = request.args.get('oa')
    open_access = None if oa_arg in (None, '') else oa_arg in ('1', 'true', 'yes')
    per_page = int_arg('per_page', 20, 1, 50)
    page = int_arg('page', 1, 1, 1000)

    found = get_classifier().journal_db.search(
        text=(request.args.get('q') or '')[:200],
        area=(request.args.get('area') or '')[:100],
        quartile=quartile if quartile in QUARTILES else '',
        open_access=open_access,
        limit=per_page,
        offset=(page - 1) * per_page,
    )
    return jsonify({
        'success': True,
        'total': found['total'],
        'page': page,
        'per_page': per_page,
        'results': [public_journal(r) for r in found['results']],
    })


@app.route('/api/journals')
def journals_by_id():
    """Fetch up to 4 journals by id for side-by-side comparison: ?ids=12,345"""
    ids = []
    for part in (request.args.get('ids') or '').split(','):
        if part.strip().isdigit():
            ids.append(int(part))
    ids = list(dict.fromkeys(ids))[:4]
    if not ids:
        return error_response('Please choose at least one journal to compare.', 400)
    rows = get_classifier().journal_db.get_by_ids(ids)
    return jsonify({'success': True, 'results': [public_journal(r) for r in rows]})


@app.route('/api/journals/areas')
def journal_areas():
    return jsonify({'success': True, 'areas': get_classifier().journal_db.list_areas()})


@app.route('/api/journals/suggest')
def journal_suggest():
    """Top journals for a field: ?field=Artificial Intelligence"""
    field = (request.args.get('field') or '').strip()[:100]
    if not field:
        return error_response('Please enter a research field.', 400)
    rows = get_classifier().journal_db.suggest_journals(field, top_n=int_arg('limit', 10, 1, 50))
    return jsonify({'success': True, 'field': field, 'results': [public_journal(r) for r in rows]})


@app.route('/health')
@limiter.exempt
def health():
    """Health check endpoint."""
    db_exists = os.path.exists(config.DATABASE_PATH)
    return jsonify({
        'status': 'healthy' if db_exists else 'degraded',
        'database': 'connected' if db_exists else 'missing - run setup_db.py',
        'upload_folder': os.path.exists(app.config['UPLOAD_FOLDER']),
        'version': config.APP_VERSION
    })


@app.route('/stats')
def stats():
    """Return database statistics for the frontend."""
    try:
        classifier = get_classifier()
        counts = classifier.checks.counts()
        return jsonify({
            'journals': classifier.journal_db.count(),
            'conferences': classifier.conference_db.count(),
            'apis': 4,  # CrossRef, OpenAlex, Semantic Scholar, arXiv
            'editions': classifier.checks.editions(),
            **counts,
        })
    except Exception:
        return jsonify({'journals': 32193, 'conferences': 987, 'apis': 4, 'editions': {}})


@app.errorhandler(413)
def file_too_large(e):
    """Handle file too large errors."""
    max_mb = config.MAX_CONTENT_LENGTH // (1024 * 1024)
    return error_response(f'File too large. The maximum is {max_mb}MB per upload.', 413)


@app.errorhandler(429)
def rate_limited(e):
    return error_response("You're sending requests too quickly. Please wait a minute and try again.", 429)


@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors: JSON for API calls, a friendly page for browsers."""
    if request.path.startswith('/api/') or request.method != 'GET':
        return error_response('Not found.', 404)
    return render_template('404.html', assets=vite_assets()), 404


@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors."""
    return error_response('Internal server error. Please try again.', 500)


if __name__ == '__main__':
    # Ensure database exists before starting
    if not os.path.exists(config.DATABASE_PATH):
        print("=" * 60)
        print("DATABASE NOT FOUND!")
        print(f"Expected at: {config.DATABASE_PATH}")
        print("")
        print("Please run the following command first:")
        print("  python setup_db.py")
        print("=" * 60)
    else:
        port = int(os.environ.get('PORT', 5000))
        debug = os.environ.get('FLASK_ENV', 'development') == 'development'
        print("=" * 60)
        print("  PaperLens - Research Paper Classifier")
        print(f"  Starting server at http://127.0.0.1:{port}")
        print(f"  Debug mode: {debug}")
        print("=" * 60)
        app.run(debug=debug, host='127.0.0.1' if debug else '0.0.0.0', port=port)

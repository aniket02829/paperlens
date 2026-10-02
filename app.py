"""
Flask web application for the Research Paper Classifier (PaperLens).

Routes:
    GET  /              - Serve the main upload page
    POST /analyze       - Analyze a single uploaded paper
    POST /analyze-bulk  - Analyze multiple uploaded papers
    GET  /health        - Health check endpoint
"""
import os
import uuid
import logging
from typing import Tuple

from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename

import config
from classifier.classifier import PaperClassifier

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

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize classifier (lazy - created on first request)
_classifier = None


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
            semantic_scholar_api_key=config.SEMANTIC_SCHOLAR_API_KEY
        )
        logger.info("PaperClassifier initialized successfully.")
    return _classifier


def allowed_file(filename: str) -> bool:
    """Check if the uploaded file has an allowed extension."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in config.ALLOWED_EXTENSIONS


def save_uploaded_file(file) -> Tuple[str, str]:
    """
    Save an uploaded file to the uploads directory with a unique name.

    Returns:
        Tuple of (saved_path, original_filename)
    """
    original_name = secure_filename(file.filename)
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


# ==================== ROUTES ====================

@app.route('/')
def index():
    """Serve the main upload page."""
    return render_template('index.html')


@app.route('/analyze', methods=['POST'])
def analyze():
    """
    Analyze a single uploaded research paper.

    Expects: multipart/form-data with a 'file' field.
    Returns: JSON with classification results.
    """
    if 'file' not in request.files:
        return jsonify({
            'success': False,
            'error': 'No file provided. Please upload a PDF or DOCX file.'
        }), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({
            'success': False,
            'error': 'No file selected. Please choose a file to upload.'
        }), 400

    if not allowed_file(file.filename):
        return jsonify({
            'success': False,
            'error': f'Invalid file type. Allowed types: {", ".join(config.ALLOWED_EXTENSIONS)}'
        }), 400

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
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

    except Exception as e:
        logger.error(f"Unexpected error analyzing file: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'An unexpected error occurred while analyzing the file. Please try again.'
        }), 500

    finally:
        # Clean up the uploaded file
        if saved_path:
            cleanup_file(saved_path)


@app.route('/analyze-bulk', methods=['POST'])
def analyze_bulk():
    """
    Analyze multiple uploaded research papers.

    Expects: multipart/form-data with multiple 'files' fields.
    Returns: JSON with classification results for each file.
    """
    if 'files' not in request.files:
        return jsonify({
            'success': False,
            'error': 'No files provided. Please upload PDF or DOCX files.'
        }), 400

    files = request.files.getlist('files')
    if not files or all(f.filename == '' for f in files):
        return jsonify({
            'success': False,
            'error': 'No files selected. Please choose files to upload.'
        }), 400

    results = []
    errors = []
    saved_paths = []

    try:
        classifier = get_classifier()

        for file in files:
            if file.filename == '' or not allowed_file(file.filename):
                errors.append({
                    'filename': file.filename or 'unknown',
                    'error': f'Skipped: invalid file type'
                })
                continue

            saved_path = None
            try:
                saved_path, original_name = save_uploaded_file(file)
                saved_paths.append(saved_path)
                logger.info(f"Analyzing file (bulk): {original_name}")

                result = classifier.classify(saved_path)
                result['filename'] = original_name
                results.append(result)

            except Exception as e:
                logger.error(f"Error analyzing {file.filename}: {e}")
                errors.append({
                    'filename': file.filename,
                    'error': str(e)
                })

        # Summary statistics
        summary = {
            'total': len(results) + len(errors),
            'successful': len(results),
            'failed': len(errors),
            'journals': sum(1 for r in results if r.get('category') == 'journal'),
            'conferences': sum(1 for r in results if r.get('category') == 'conference'),
            'arxiv': sum(1 for r in results if r.get('category') == 'arxiv'),
            'unknown': sum(1 for r in results if r.get('category') == 'unknown'),
        }

        return jsonify({
            'success': True,
            'results': results,
            'errors': errors,
            'summary': summary
        })

    except RuntimeError as e:
        logger.error(f"Runtime error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

    except Exception as e:
        logger.error(f"Unexpected error in bulk analysis: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'An unexpected error occurred. Please try again.'
        }), 500

    finally:
        # Clean up all uploaded files
        for path in saved_paths:
            cleanup_file(path)


@app.route('/health')
def health():
    """Health check endpoint."""
    db_exists = os.path.exists(config.DATABASE_PATH)
    return jsonify({
        'status': 'healthy' if db_exists else 'degraded',
        'database': 'connected' if db_exists else 'missing - run setup_db.py',
        'upload_folder': os.path.exists(app.config['UPLOAD_FOLDER']),
        'version': '2.0.0'
    })


@app.route('/stats')
def stats():
    """Return database statistics for the frontend."""
    import sqlite3
    try:
        conn = sqlite3.connect(config.DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM journals')
        journal_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM conferences')
        conference_count = cursor.fetchone()[0]
        conn.close()
        return jsonify({
            'journals': journal_count,
            'conferences': conference_count,
            'apis': 3  # CrossRef, Semantic Scholar, SJR
        })
    except Exception:
        return jsonify({
            'journals': 32193,
            'conferences': 986,
            'apis': 3
        })


@app.errorhandler(413)
def file_too_large(e):
    """Handle file too large errors."""
    max_mb = config.MAX_CONTENT_LENGTH // (1024 * 1024)
    return jsonify({
        'success': False,
        'error': f'File too large. Maximum size is {max_mb}MB.'
    }), 413


@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors."""
    return jsonify({
        'success': False,
        'error': 'Page not found.'
    }), 404


@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors."""
    return jsonify({
        'success': False,
        'error': 'Internal server error. Please try again.'
    }), 500


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
        app.run(debug=debug, host='0.0.0.0', port=port)


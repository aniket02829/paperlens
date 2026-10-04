"""
Measure PaperLens accuracy on the labelled PDFs in eval/dataset.csv.

    python eval/evaluate.py                    # full system (PDF text + metadata APIs)
    python eval/evaluate.py --text-only        # ablation: no API calls, PDF text only
    python eval/evaluate.py --baseline <dir>   # an older checkout of PaperLens, for comparison
    python eval/evaluate.py --subset heldout   # only papers not in dataset_dev.csv (the 104 development papers)

Writes eval/results/<name>.csv (one row per paper) and eval/results/<name>.json
(metrics), and prints a summary. Each paper is classified from its PDF alone; the
label in dataset.csv never reaches the classifier.
"""
import argparse
import csv
import json
import os
import sys
import time
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVAL_DIR = os.path.join(ROOT, 'eval')
CATEGORIES = ['journal', 'conference', 'arxiv', 'unknown']


def load_classifier(code_dir, text_only):
    sys.path.insert(0, code_dir)
    import config
    from classifier.classifier import PaperClassifier
    db_path = os.path.join(code_dir, 'data', 'paper_classifier.db')
    # Keyless Semantic Scholar for every run, so runs are comparable.
    classifier = PaperClassifier(db_path, config.CROSSREF_EMAIL, None)
    if text_only:
        fetcher = classifier.fetcher
        empty = lambda *a, **k: {}
        for name in ('fetch_by_doi', 'fetch_by_title', 'fetch_semantic_scholar', 'fetch_openalex',
                     'fetch_openalex_by_title', 'fetch_arxiv', 'fetch_arxiv_by_title', 'fetch_openalex_source'):
            if hasattr(fetcher, name):
                setattr(fetcher, name, empty)
    return classifier


def normalize_rank(rank):
    rank = (rank or '').strip()
    if rank.lower().startswith(('national', 'regional')):
        return 'National'
    return rank


def per_class_metrics(pairs):
    metrics = {}
    for cat in CATEGORIES[:3]:
        tp = sum(1 for e, p in pairs if e == cat and p == cat)
        fp = sum(1 for e, p in pairs if e != cat and p == cat)
        fn = sum(1 for e, p in pairs if e == cat and p != cat)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        metrics[cat] = {'precision': round(precision, 3), 'recall': round(recall, 3), 'f1': round(f1, 3),
                        'support': tp + fn}
    metrics['macro_f1'] = round(sum(metrics[c]['f1'] for c in CATEGORIES[:3]) / 3, 3)
    return metrics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--text-only', action='store_true')
    parser.add_argument('--baseline', help='path to an older PaperLens checkout')
    parser.add_argument('--name', help='name for the output files')
    parser.add_argument('--subset', choices=['all', 'dev', 'heldout'], default='all',
                        help='dev = the papers in dataset_dev.csv, heldout = everything else')
    args = parser.parse_args()

    code_dir = os.path.abspath(args.baseline) if args.baseline else ROOT
    name = args.name or ('baseline' if args.baseline else 'text_only' if args.text_only else 'full')
    if args.subset != 'all':
        name += f'_{args.subset}'
    classifier = load_classifier(code_dir, args.text_only)

    with open(os.path.join(EVAL_DIR, 'dataset.csv'), encoding='utf-8') as f:
        dataset = list(csv.DictReader(f))
    if args.subset != 'all':
        with open(os.path.join(EVAL_DIR, 'dataset_dev.csv'), encoding='utf-8') as f:
            dev_ids = {r['id'] for r in csv.DictReader(f)}
        dataset = [r for r in dataset if (r['id'] in dev_ids) == (args.subset == 'dev')]

    rows = []
    for i, item in enumerate(dataset, 1):
        path = os.path.join(EVAL_DIR, 'pdfs', f"{item['id']}.pdf")
        if not os.path.exists(path):
            continue
        start = time.time()
        try:
            result = classifier.classify(path)
        except Exception as e:  # the old baseline can crash; count it as an error
            result = {'category': 'error', 'error': str(e)}
        elapsed = time.time() - start
        predicted = result.get('category') or 'error'
        if predicted == 'error':
            predicted = 'unknown'
        rank = result.get('quartile') if predicted == 'journal' else result.get('core_rank') if predicted == 'conference' else ''
        rows.append({
            'id': item['id'],
            'expected_category': item['expected_category'],
            'predicted_category': predicted,
            'category_correct': int(predicted == item['expected_category']),
            'expected_rank': normalize_rank(item['expected_rank']),
            'predicted_rank': normalize_rank(rank),
            'expected_conference_type': item['expected_conference_type'],
            'predicted_conference_type': result.get('conference_type') or '',
            'expected_venue': item['expected_venue'],
            'predicted_venue': result.get('venue') or '',
            'confidence': result.get('confidence'),
            'seconds': round(elapsed, 2),
            'title': (result.get('title') or '')[:120],
        })
        mark = 'ok ' if rows[-1]['category_correct'] else 'XX '
        print(f"{mark}{i:3}/{len(dataset)} {item['id'][:45]:45} expected={item['expected_category']:10} "
              f"got={predicted:10} rank={rows[-1]['predicted_rank'] or '-':8} ({elapsed:.1f}s)")

    pairs = [(r['expected_category'], r['predicted_category']) for r in rows]
    confusion = {e: {p: 0 for p in CATEGORIES} for e in CATEGORIES[:3]}
    for e, p in pairs:
        confusion[e][p] += 1

    # Rank accuracy only counts papers whose category was right and whose label has a rank.
    ranked = [r for r in rows if r['category_correct'] and r['expected_rank'] and r['expected_category'] != 'arxiv']
    journals = [r for r in ranked if r['expected_category'] == 'journal']
    conferences = [r for r in ranked if r['expected_category'] == 'conference']
    typed = [r for r in rows if r['category_correct'] and r['expected_conference_type']]

    # Calibration: accuracy within confidence bands.
    bands = {}
    for low, high in ((0, 0.6), (0.6, 0.8), (0.8, 1.01)):
        in_band = [r for r in rows if r['confidence'] is not None and low <= r['confidence'] < high]
        bands[f'{low:.1f}-{min(high, 1):.1f}'] = {
            'n': len(in_band),
            'accuracy': round(sum(r['category_correct'] for r in in_band) / len(in_band), 3) if in_band else None,
        }

    metrics = {
        'name': name,
        'papers': len(rows),
        'category_accuracy': round(sum(r['category_correct'] for r in rows) / len(rows), 3),
        'per_class': per_class_metrics(pairs),
        'confusion': confusion,
        'journal_quartile_accuracy': round(sum(r['predicted_rank'] == r['expected_rank'] for r in journals) / len(journals), 3) if journals else None,
        'journal_quartile_n': len(journals),
        'conference_rank_accuracy': round(sum(r['predicted_rank'] == r['expected_rank'] for r in conferences) / len(conferences), 3) if conferences else None,
        'conference_rank_n': len(conferences),
        'conference_type_accuracy': round(sum(r['predicted_conference_type'] == r['expected_conference_type'] for r in typed) / len(typed), 3) if typed else None,
        'conference_type_n': len(typed),
        'confidence_bands': bands,
        'median_seconds': sorted(r['seconds'] for r in rows)[len(rows) // 2],
        'support': dict(Counter(r['expected_category'] for r in rows)),
    }

    out_dir = os.path.join(EVAL_DIR, 'results')
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, f'{name}.csv'), 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    with open(os.path.join(out_dir, f'{name}.json'), 'w', encoding='utf-8') as f:
        json.dump(metrics, f, indent=2)

    print(json.dumps(metrics, indent=2))


if __name__ == '__main__':
    main()

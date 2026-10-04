"""Turn eval/results/*.json into the tables and figures a paper needs.

    python eval/report.py                 # prints Markdown tables, writes eval/results/figures/*.svg
    python eval/report.py --subset heldout   # the same for results/<system>_heldout.json

Tables: system comparison with 95% Wilson confidence intervals, per-class precision /
recall / F1, confusion matrix, calibration. Figures are plain SVG (no plotting library),
so they can be dropped into LaTeX (via Inkscape/rsvg) or a Word document.
"""
import json
import math
import os

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(EVAL_DIR, 'results')
FIGURES = os.path.join(RESULTS, 'figures')
SYSTEMS = [('baseline', 'v2 (previous live site)'), ('text_only', 'v3, PDF text only'), ('full', 'v3, full')]
CLASSES = ['journal', 'conference', 'arxiv']
CLASS_LABEL = {'journal': 'Journal', 'conference': 'Conference', 'arxiv': 'Preprint', 'unknown': 'Unknown'}
COLOURS = {'baseline': '#94A3B8', 'text_only': '#B45309', 'full': '#1E3A5F'}


def wilson(successes, n, z=1.96):
    """95% Wilson score interval for a proportion, as (low, high)."""
    if not n:
        return (0.0, 0.0)
    p = successes / n
    denominator = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denominator
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return (max(0.0, centre - half), min(1.0, centre + half))


def pct(x, digits=1):
    return '–' if x is None else f'{100 * x:.{digits}f}%'


def load(suffix=''):
    out = {}
    for key, _ in SYSTEMS:
        path = os.path.join(RESULTS, f'{key}{suffix}.json')
        if os.path.exists(path):
            with open(path, encoding='utf-8') as f:
                out[key] = json.load(f)
    return out


def ci_text(metric, n):
    if metric is None or not n:
        return '–'
    low, high = wilson(round(metric * n), n)
    return f'{pct(metric)} [{pct(low, 0)}–{pct(high, 0)}]'


# ----------------------------------------------------------------------------- tables

def comparison_table(results):
    rows = [('Category accuracy', lambda r: ci_text(r['category_accuracy'], r['papers'])),
            ('Macro F1', lambda r: f"{r['per_class']['macro_f1']:.3f}"),
            ('Journal F1', lambda r: f"{r['per_class']['journal']['f1']:.3f}"),
            ('Conference F1', lambda r: f"{r['per_class']['conference']['f1']:.3f}"),
            ('Preprint F1', lambda r: f"{r['per_class']['arxiv']['f1']:.3f}"),
            ('Quartile accuracy', lambda r: ci_text(r['journal_quartile_accuracy'], r['journal_quartile_n']) + f" (n={r['journal_quartile_n']})"),
            ('CORE rank accuracy', lambda r: ci_text(r['conference_rank_accuracy'], r['conference_rank_n']) + f" (n={r['conference_rank_n']})"),
            ('Conference type accuracy', lambda r: ci_text(r['conference_type_accuracy'], r['conference_type_n']) + f" (n={r['conference_type_n']})"),
            ('Median seconds per paper', lambda r: f"{r['median_seconds']:.1f}")]
    present = [(k, label) for k, label in SYSTEMS if k in results]
    lines = ['| Metric | ' + ' | '.join(label for _, label in present) + ' |',
             '|---|' + '---|' * len(present)]
    for name, fn in rows:
        lines.append(f'| {name} | ' + ' | '.join(fn(results[k]) for k, _ in present) + ' |')
    lines.append('')
    lines.append('Accuracies are followed by 95% Wilson confidence intervals in brackets.')
    return '\n'.join(lines)


def per_class_table(result):
    lines = ['| Class | Precision | Recall | F1 | Support |', '|---|---|---|---|---|']
    for cls in CLASSES:
        m = result['per_class'][cls]
        lines.append(f"| {CLASS_LABEL[cls]} | {m['precision']:.3f} | {m['recall']:.3f} | {m['f1']:.3f} | {m['support']} |")
    return '\n'.join(lines)


def confusion_table(result):
    cols = CLASSES + ['unknown']
    lines = ['| True \\ Predicted | ' + ' | '.join(CLASS_LABEL[c] for c in cols) + ' |', '|---|' + '---|' * len(cols)]
    for cls in CLASSES:
        row = result['confusion'][cls]
        lines.append(f"| {CLASS_LABEL[cls]} ({sum(row.values())}) | " + ' | '.join(
            f"**{row[c]}**" if c == cls else str(row[c]) for c in cols) + ' |')
    return '\n'.join(lines)


def calibration_table(result):
    lines = ['| Confidence | Papers | Accuracy |', '|---|---|---|']
    for band, v in result['confidence_bands'].items():
        lines.append(f"| {band} | {v['n']} | {pct(v['accuracy'])} |")
    return '\n'.join(lines)


# ----------------------------------------------------------------------------- figures

def svg(width, height, body, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
            f'font-family="Helvetica, Arial, sans-serif" font-size="12" role="img" aria-label="{title}">'
            f'<rect width="{width}" height="{height}" fill="white"/>{body}</svg>')


def bar_chart(results, path):
    """Grouped bars: category, quartile, CORE rank and type accuracy per system."""
    metrics = [('category_accuracy', None, 'Category'), ('journal_quartile_accuracy', 'journal_quartile_n', 'Quartile'),
               ('conference_rank_accuracy', 'conference_rank_n', 'CORE rank'), ('conference_type_accuracy', 'conference_type_n', 'Conf. type')]
    systems = [(k, label) for k, label in SYSTEMS if k in results]
    width, height, left, top, bottom = 640, 320, 50, 30, 60
    plot_w, plot_h = width - left - 20, height - top - bottom
    group_w = plot_w / len(metrics)
    bar_w = group_w / (len(systems) + 1)
    body = []
    for i in range(0, 101, 25):
        y = top + plot_h - plot_h * i / 100
        body.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width - 20}" y2="{y:.1f}" stroke="#E2E8F0"/>')
        body.append(f'<text x="{left - 6}" y="{y + 4:.1f}" text-anchor="end" fill="#475569">{i}%</text>')
    for gi, (metric, n_key, label) in enumerate(metrics):
        x0 = left + gi * group_w + bar_w / 2
        for si, (key, _) in enumerate(systems):
            value = results[key].get(metric) or 0
            x = x0 + si * bar_w
            h = plot_h * value
            body.append(f'<rect x="{x:.1f}" y="{top + plot_h - h:.1f}" width="{bar_w - 4:.1f}" height="{h:.1f}" fill="{COLOURS[key]}"/>')
            body.append(f'<text x="{x + (bar_w - 4) / 2:.1f}" y="{top + plot_h - h - 4:.1f}" text-anchor="middle" fill="#0F172A" font-size="10">{100 * value:.0f}</text>')
        body.append(f'<text x="{x0 + len(systems) * bar_w / 2 - 2:.1f}" y="{top + plot_h + 18}" text-anchor="middle" fill="#0F172A">{label}</text>')
    for si, (key, label) in enumerate(systems):
        x = left + si * 200
        body.append(f'<rect x="{x}" y="{height - 22}" width="12" height="12" fill="{COLOURS[key]}"/>')
        body.append(f'<text x="{x + 18}" y="{height - 12}" fill="#0F172A">{label}</text>')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(svg(width, height, ''.join(body), 'Accuracy by system and metric'))


def confusion_figure(result, path):
    cols = CLASSES + ['unknown']
    cell, left, top = 90, 110, 50
    width, height = left + cell * len(cols) + 20, top + cell * len(CLASSES) + 20
    total = max(1, result['papers'])
    body = [f'<text x="{left + cell * len(cols) / 2}" y="20" text-anchor="middle" font-weight="bold">Predicted</text>']
    for j, c in enumerate(cols):
        body.append(f'<text x="{left + j * cell + cell / 2}" y="{top - 8}" text-anchor="middle">{CLASS_LABEL[c]}</text>')
    for i, cls in enumerate(CLASSES):
        row = result['confusion'][cls]
        row_total = max(1, sum(row.values()))
        body.append(f'<text x="{left - 8}" y="{top + i * cell + cell / 2 + 4}" text-anchor="end">{CLASS_LABEL[cls]}</text>')
        for j, c in enumerate(cols):
            share = row[c] / row_total
            fill = f'rgba(30,58,95,{0.08 + 0.85 * share:.2f})'
            colour = 'white' if share > 0.5 else '#0F172A'
            x, y = left + j * cell, top + i * cell
            body.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" fill="{fill}" stroke="white"/>')
            body.append(f'<text x="{x + cell / 2}" y="{y + cell / 2 + 5}" text-anchor="middle" fill="{colour}" font-size="16" font-weight="bold">{row[c]}</text>')
    body.append(f'<text x="14" y="{top + cell * len(CLASSES) / 2}" text-anchor="middle" font-weight="bold" transform="rotate(-90 14 {top + cell * len(CLASSES) / 2})">True</text>')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(svg(width, height, ''.join(body), f'Confusion matrix ({total} papers)'))


def calibration_figure(result, path):
    bands = list(result['confidence_bands'].items())
    width, height, left, top, bottom = 420, 260, 50, 20, 50
    plot_w, plot_h = width - left - 20, height - top - bottom
    bar_w = plot_w / len(bands)
    body = []
    for i in range(0, 101, 25):
        y = top + plot_h - plot_h * i / 100
        body.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width - 20}" y2="{y:.1f}" stroke="#E2E8F0"/>')
        body.append(f'<text x="{left - 6}" y="{y + 4:.1f}" text-anchor="end" fill="#475569">{i}%</text>')
    for i, (band, v) in enumerate(bands):
        acc = v['accuracy'] or 0
        x = left + i * bar_w + 10
        h = plot_h * acc
        body.append(f'<rect x="{x:.1f}" y="{top + plot_h - h:.1f}" width="{bar_w - 20:.1f}" height="{h:.1f}" fill="#1E3A5F"/>')
        body.append(f'<text x="{x + (bar_w - 20) / 2:.1f}" y="{top + plot_h - h - 4:.1f}" text-anchor="middle" font-size="10">{100 * acc:.0f}% (n={v["n"]})</text>')
        body.append(f'<text x="{x + (bar_w - 20) / 2:.1f}" y="{top + plot_h + 18}" text-anchor="middle">confidence {band}</text>')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(svg(width, height, ''.join(body), 'Accuracy by confidence band'))


def main():
    import sys
    subset = sys.argv[sys.argv.index('--subset') + 1] if '--subset' in sys.argv else ''
    suffix = f'_{subset}' if subset else ''
    results = load(suffix)
    if 'full' not in results:
        raise SystemExit(f'eval/results/full{suffix}.json not found: run python eval/evaluate.py first')
    os.makedirs(FIGURES, exist_ok=True)
    bar_chart(results, os.path.join(FIGURES, f'accuracy_by_system{suffix}.svg'))
    confusion_figure(results['full'], os.path.join(FIGURES, f'confusion_full{suffix}.svg'))
    calibration_figure(results['full'], os.path.join(FIGURES, f'calibration_full{suffix}.svg'))

    full = results['full']
    print(f"## Results on {full['papers']} papers{' (' + subset + ')' if subset else ''}\n")
    print('### System comparison\n')
    print(comparison_table(results) + '\n')
    print('### Per-class metrics (v3, full)\n')
    print(per_class_table(full) + '\n')
    print('### Confusion matrix (v3, full)\n')
    print(confusion_table(full) + '\n')
    print('### Calibration (v3, full)\n')
    print(calibration_table(full) + '\n')
    print(f'Figures written to {FIGURES}/')


if __name__ == '__main__':
    main()

import type { PaperResult } from '../types';

/** 'Jian-Ping Zhu, Xuxun Cai' -> 'Jian-Ping Zhu and Xuxun Cai' (BibTeX separates authors with 'and'). */
function bibAuthors(authors: string | null): string | null {
  if (!authors) return null;
  const names = authors.split(/,\s*|\s+and\s+|;\s*/).map(n => n.trim()).filter(Boolean);
  return names.length ? names.join(' and ') : null;
}

/** A citation key such as zhu2025probabilistic: first author's surname, year, first long title word. */
function citationKey(result: PaperResult): string {
  const first = (result.authors || '').split(/,|;|\band\b/)[0]?.trim().split(/\s+/).pop() || 'paper';
  const word = (result.title || '').toLowerCase().split(/\W+/).find(w => w.length > 3) || 'untitled';
  return `${first}${result.year || ''}${word}`.replace(/[^a-z0-9]/gi, '').toLowerCase();
}

function escapeBib(text: string): string {
  return text.replace(/[{}]/g, '').replace(/&/g, '\\&').replace(/%/g, '\\%');
}

/** A BibTeX entry for the classified paper: @article, @inproceedings or @misc (preprint). */
export function toBibtex(result: PaperResult): string {
  const type = result.category === 'journal' ? 'article' : result.category === 'conference' ? 'inproceedings' : 'misc';
  const fields: [string, string | number | null | undefined][] = [
    ['title', result.title],
    ['author', bibAuthors(result.authors)],
    [result.category === 'journal' ? 'journal' : 'booktitle', result.category === 'arxiv' ? null : result.venue],
    ['year', result.year],
    ['publisher', result.category === 'arxiv' ? null : result.publisher],
    ['doi', result.published_doi || result.doi],
    ['eprint', result.arxiv_id],
    ['archivePrefix', result.arxiv_id ? 'arXiv' : null],
    ['url', result.doi ? `https://doi.org/${result.published_doi || result.doi}` : result.arxiv_id ? `https://arxiv.org/abs/${result.arxiv_id}` : null],
  ];
  const body = fields
    .filter(([, value]) => value !== null && value !== undefined && value !== '')
    .map(([key, value]) => `  ${key} = {${escapeBib(String(value))}}`)
    .join(',\n');
  return `@${type}{${citationKey(result)},\n${body}\n}`;
}

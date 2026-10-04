export type Category = 'journal' | 'conference' | 'arxiv' | 'unknown' | 'error';

export interface SuggestedJournal {
  id: number | null;
  name: string;
  quartile: string;
  sjr_score: number | null;
  category: string;
  publisher: string;
  open_access: boolean;
  quartile_color: string;
}

export interface Trust {
  indexed_in_sjr: boolean | null;
  indexed_in_scopus: boolean | null;
  in_doaj: boolean | null;
  in_core: boolean | null;
  is_retracted: boolean;
  warnings: string[];
}

/** The journal's entry on the Scopus source list. */
export interface ScopusInfo {
  title: string;
  source_type: string;
  active: boolean;
  discontinued: boolean;
  discontinued_year: string | null;
  discontinued_reason: string | null;
  coverage: string | null;
}

/** The journal's entry in the Directory of Open Access Journals. */
export interface DoajInfo {
  title: string;
  url: string | null;
  apc: string | null;
  apc_amount: string | null;
  review_process: string | null;
  weeks_to_publication: string | null;
  license: string | null;
  added_on: string | null;
}

export interface Watchlist {
  hijacked: { clone_name: string; clone_url: string | null; authentic_name: string; authentic_url: string | null; source: string } | null;
  predatory_journal: { name: string; url: string | null; source: string } | null;
  predatory_publisher: { name: string; url: string | null; source: string } | null;
}

/** OpenAlex citation statistics, shown when a venue has no SJR or CORE rank. */
export interface VenueStats {
  name?: string;
  type?: string;
  works_count?: number;
  cited_by_count?: number;
  h_index?: number;
  i10_index?: number;
  mean_citedness_2yr?: number;
  homepage_url?: string;
}

/** One classification, as returned by /analyze, /analyze-bulk and /api/lookup. */
export interface PaperResult {
  title: string;
  category: Category;
  venue: string | null;
  quartile: string | null;
  sjr_score: number | null;
  h_index: number | null;
  journal_id: number | null;
  is_arxiv: boolean;
  arxiv_id: string | null;
  conference_type: 'IEEE' | 'International' | 'National' | null;
  core_rank: string | null;
  core_rank_description: string | null;
  core_acronym: string | null;
  suggested_journals: SuggestedJournal[];
  suggestion_field: string | null;
  confidence: number;
  signals: string[];
  doi: string | null;
  page_count: number | null;
  keywords: string | null;
  publisher: string | null;
  categories: string | null;
  authors: string | null;
  abstract: string | null;
  citation_count: number | null;
  year: number | null;
  fields_of_study: string | null;
  topics: string[];
  is_open_access: boolean | null;
  oa_url: string | null;
  is_retracted: boolean;
  published_doi: string | null;
  matched_by: string | null;
  in_sjr: boolean | null;
  in_core: boolean | null;
  scopus: ScopusInfo | null;
  doaj: DoajInfo | null;
  watchlist: Watchlist | null;
  venue_stats: VenueStats | null;
  trust: Trust | null;
  error: string | null;
  filename?: string;
}

export interface BulkResponse {
  results: PaperResult[];
  errors: { filename: string; error: string }[];
  summary: { total: number; successful: number; failed: number; journals: number; conferences: number; arxiv: number; unknown: number };
}

export interface Journal {
  id: number;
  title: string;
  issn: string[];
  sjr_score: number | null;
  quartile: string | null;
  quartile_color: string;
  h_index: number | null;
  publisher: string | null;
  country: string | null;
  categories: string[];
  areas: string[];
  open_access: boolean;
}

export interface JournalSearchResponse {
  total: number;
  page: number;
  per_page: number;
  results: Journal[];
}

export interface HistoryEntry {
  title: string;
  category: Category;
  venue: string | null;
  rank: string | null;
  query: string | null;
  at: number;
}

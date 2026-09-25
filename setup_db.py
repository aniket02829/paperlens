"""Script to setup the paper classifier database from SCIMAGO and CORE CSV datasets.

Usage:
    python setup_db.py <sjr_csv_path> <core_csv_path>
    python setup_db.py   (uses default paths)
"""
import csv
import sqlite3
import os
import sys
import glob

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'paper_classifier.db')


def find_csv(pattern_list: list, label: str) -> str:
    """Try to find a CSV file from a list of glob patterns."""
    for pattern in pattern_list:
        matches = glob.glob(pattern)
        if matches:
            # Return the most recently modified match
            matches.sort(key=os.path.getmtime, reverse=True)
            print(f"Found {label}: {matches[0]}")
            return matches[0]
    return ""


def get_csv_paths():
    """Get SJR and CORE CSV paths from args, env, or auto-detect."""
    downloads = os.path.expanduser('~\\Downloads')
    
    # Try command line args first
    if len(sys.argv) >= 3:
        return sys.argv[1], sys.argv[2]
    
    # Auto-detect SJR
    sjr_path = find_csv([
        os.path.join(downloads, 'scimagojr*.csv'),
        os.path.join(downloads, 'sjr*.csv'),
        os.path.join(downloads, 'SJR*.csv'),
    ], "SJR CSV")
    
    # Auto-detect CORE
    core_path = find_csv([
        os.path.join(downloads, 'CORE*.csv'),
        os.path.join(downloads, 'core*.csv'),
    ], "CORE CSV")
    
    return sjr_path, core_path

def init_db(conn: sqlite3.Connection):
    """Initialize database tables."""
    cursor = conn.cursor()
    # Drop existing tables for fresh rebuild
    cursor.execute('DROP TABLE IF EXISTS journal_issns')
    cursor.execute('DROP TABLE IF EXISTS journals')
    cursor.execute('DROP TABLE IF EXISTS conferences')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS journals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            title_normalized TEXT,
            issn_list TEXT,
            sjr_score REAL,
            best_quartile TEXT,
            h_index INTEGER,
            publisher TEXT,
            country TEXT,
            categories TEXT,
            areas TEXT,
            open_access TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS journal_issns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            journal_id INTEGER,
            issn TEXT,
            FOREIGN KEY(journal_id) REFERENCES journals(id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            title_normalized TEXT,
            acronym TEXT,
            acronym_normalized TEXT,
            source TEXT,
            rank TEXT,
            is_primary TEXT,
            for_code_1 TEXT,
            for_code_2 TEXT,
            for_code_3 TEXT
        )
    ''')
    # Indexes
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_journal_issns_issn ON journal_issns(issn)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_journals_title ON journals(title_normalized)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_conferences_acronym ON conferences(acronym_normalized)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_conferences_title ON conferences(title_normalized)')
    conn.commit()

def process_sjr_csv(conn: sqlite3.Connection, csv_path: str) -> int:
    """Process SJR CSV and populate journals."""
    if not csv_path or not os.path.exists(csv_path):
        print(f"Warning: SJR CSV not found at '{csv_path}'")
        return 0

    cursor = conn.cursor()
    count = 0
    with open(csv_path, 'r', encoding='utf-8-sig', errors='replace') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            title = row.get('Title', '').strip()
            title_normalized = title.lower()
            issn_list = row.get('Issn', '').strip()
            
            sjr_str = row.get('SJR', '').strip()
            sjr_score = 0.0
            if sjr_str:
                try:
                    sjr_score = float(sjr_str.replace(',', '.'))
                except ValueError:
                    pass
                    
            best_quartile = row.get('SJR Best Quartile', '').strip()
            
            h_index_str = row.get('H index', '').strip()
            h_index = 0
            if h_index_str:
                try:
                    h_index = int(h_index_str)
                except ValueError:
                    pass
                    
            publisher = row.get('Publisher', '').strip()
            country = row.get('Country', '').strip()
            categories = row.get('Categories', '').strip()
            areas = row.get('Areas', '').strip()
            open_access = row.get('Open Access', '').strip()

            cursor.execute('''
                INSERT INTO journals (
                    title, title_normalized, issn_list, sjr_score, best_quartile,
                    h_index, publisher, country, categories, areas, open_access
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (title, title_normalized, issn_list, sjr_score, best_quartile,
                  h_index, publisher, country, categories, areas, open_access))
            journal_id = cursor.lastrowid
            
            if issn_list:
                issns = [i.strip().replace('-', '') for i in issn_list.split(',')]
                for issn in issns:
                    if issn:
                        cursor.execute('INSERT INTO journal_issns (journal_id, issn) VALUES (?, ?)',
                                       (journal_id, issn))
            count += 1
    conn.commit()
    return count

def process_core_csv(conn: sqlite3.Connection, csv_path: str) -> int:
    """Process CORE CSV and populate conferences."""
    if not csv_path or not os.path.exists(csv_path):
        print(f"Warning: CORE CSV not found at '{csv_path}'")
        return 0

    cursor = conn.cursor()
    count = 0
    with open(csv_path, 'r', encoding='utf-8-sig', errors='replace') as f:
        reader = csv.DictReader(f, delimiter=',')
        for row in reader:
            title = row.get('Title', '').strip()
            title_normalized = title.lower()
            acronym = row.get('Acronym', '').strip()
            acronym_normalized = acronym.lower()
            source = row.get('Source', '').strip()
            rank = row.get('Rank', '').strip()
            is_primary = row.get('Primary', '').strip()
            for_code_1 = row.get('FoR1', '').strip()
            for_code_2 = row.get('FoR2', '').strip()
            for_code_3 = row.get('FoR3', '').strip()

            cursor.execute('''
                INSERT INTO conferences (
                    title, title_normalized, acronym, acronym_normalized,
                    source, rank, is_primary, for_code_1, for_code_2, for_code_3
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (title, title_normalized, acronym, acronym_normalized,
                  source, rank, is_primary, for_code_1, for_code_2, for_code_3))
            count += 1
    conn.commit()
    return count

def main():
    sjr_path, core_path = get_csv_paths()
    
    print("=" * 60)
    print("  PaperLens Database Setup")
    print("=" * 60)
    
    if not sjr_path:
        print("\n[!] SJR CSV not found! Please either:")
        print("  1. Download from https://www.scimagojr.com/journalrank.php")
        print("  2. Place the CSV in your Downloads folder")
        print("  3. Run: python setup_db.py <sjr_path> <core_path>")
    
    if not core_path:
        print("\n[!] CORE CSV not found! Please either:")
        print("  1. Download from http://portal.core.edu.au/conf-ranks/")
        print("  2. Place the CSV in your Downloads folder")
        print("  3. Run: python setup_db.py <sjr_path> <core_path>")
    
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    # Remove old database if it exists (fresh rebuild)
    if os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
            print("\nRemoved old database.")
        except PermissionError:
            # File is locked — use a new path
            print("\nOld database is locked. Creating fresh database...")
            import time
            backup = DB_PATH + f".old_{int(time.time())}"
            try:
                os.rename(DB_PATH, backup)
            except Exception:
                pass  # If rename also fails, just overwrite tables
    
    conn = sqlite3.connect(DB_PATH)
    try:
        init_db(conn)
        print("Database schema initialized.")
        
        j_count = process_sjr_csv(conn, sjr_path)
        print(f"[OK] Loaded {j_count:,} journals.")
        
        c_count = process_core_csv(conn, core_path)
        print(f"[OK] Loaded {c_count:,} conferences.")
        
        print(f"\nDatabase saved to: {DB_PATH}")
        print("=" * 60)
        
    finally:
        conn.close()

if __name__ == '__main__':
    main()


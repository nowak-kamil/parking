import sqlite3
import csv
import time
import re
import sys
import os
from datetime import datetime
from playwright.sync_api import sync_playwright

URL = 'https://ztp.krakow.pl/parkingi-pr/sprawdz-wolne-miejsca-pr'
DB_PATH = 'archiwum_parkingow.db'
CSV_PATH = 'archiwum_parkingow.csv'

PARKING_NAMES = [
    'P+R Górka Narodowa', 'P+R Pachońskiego', 'P+R Krowodrza Górka',
    'P+R Czerwone Maki', 'P+R Mały Płaszów', 'P+R Nowy Bieżanów', 'P+R Kurdwanów'
]

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS historia (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            nazwa TEXT,
            wolne INTEGER,
            exported INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    return conn


def export_to_csv(conn):
    cursor = conn.execute('SELECT id, timestamp, nazwa, wolne FROM historia WHERE exported = 0 ORDER BY id')
    rows = cursor.fetchall()

    if not rows:
        print('Brak nowych danych do dopisania do CSV.')
        return

    file_exists = os.path.isfile(CSV_PATH)
    try:
        with open(CSV_PATH, 'a', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f, delimiter=';')
            if not file_exists:
                writer.writerow(['Data i Godzina', 'Parking', 'Wolne miejsca'])

            data_to_save = [row[1:] for row in rows]
            writer.writerows(data_to_save)

            ids = [row[0] for row in rows]
            placeholders = ",".join(["?"] * len(ids))
            conn.execute(f'UPDATE historia SET exported = 1 WHERE id IN ({placeholders})', ids)
            conn.commit()
            print(f'Dopisano {len(rows)} nowych wierszy do {CSV_PATH}')
    except Exception as e:
        print(f'Błąd podczas zapisu do CSV: {e}')


def run_monitor():
    db_conn = init_db()
    print('=== MONITOR PARKINGÓW P+R KRAKÓW ===')

    with sync_playwright() as p:
        try:
                browser = p.chromium.launch(headless=True)
                try:
                    context = browser.new_context()
                    page = context.new_page()

                    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    print(f'[{ts}] Pobieranie danych...')

                    page.goto(URL, wait_until='networkidle', timeout=60000)
                    html_content = page.content()

                    found_count = 0
                    for name in PARKING_NAMES:
                        pattern = re.escape(name) + r'.*?Wolnych:\s*(\d+)'
                        match = re.search(pattern, html_content, re.DOTALL)

                        if match:
                            wolne = int(match.group(1))
                            db_conn.execute(
                                'INSERT INTO historia (timestamp, nazwa, wolne) VALUES (?, ?, ?)',
                                (ts, name, wolne)
                            )
                            found_count += 1

                    if found_count > 0:
                        db_conn.commit()
                        export_to_csv(db_conn)
                    else:
                        print('Błąd: Nie znaleziono danych na stronie.')

                except Exception as err:
                    print(f'Błąd w trakcie sesji: {err}')

                finally:
                    browser.close()
                    print('Przeglądarka zamknięta, zasoby zwolnione.')

                print('Oczekiwanie')

        except KeyboardInterrupt:
            print('\nZatrzymywanie skryptu...')
        finally:
            if db_conn:
                export_to_csv(db_conn)
                db_conn.close()


if __name__ == '__main__':
    run_monitor()
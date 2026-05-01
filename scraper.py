import sqlite3
import csv
import time
import re
import sys
import os
from datetime import datetime
from playwright.sync_api import sync_playwright

URL = 'https://ztp.krakow.pl/parkingi-pr/sprawdz-wolne-miejsca-pr'
DB_PATH = 'db_parkingow.db'
CSV_PATH = 'csv_parkingow.csv'

PARKING_NAMES = [
    'P+R Górka Narodowa', 'P+R Pachońskiego', 'P+R Krowodrza Górka',
    'P+R Czerwone Maki', 'P+R Mały Płaszów', 'P+R Nowy Bieżanów', 'P+R Kurdwanów'
]

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            parking TEXT,
            free INTEGER,
            exported INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    return conn


def export_to_csv(conn):
    cursor = conn.execute('SELECT id, timestamp, parking, free FROM history WHERE exported = 0 ORDER BY id')
    rows = cursor.fetchall()

    if not rows:
        print('No data to save in CSV.')
        return

    file_exists = os.path.isfile(CSV_PATH)
    try:
        with open(CSV_PATH, 'a', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f, delimiter=';')
            if not file_exists:
                writer.writerow(['Date and Time', 'Parking name', 'Free parking space'])

            data_to_save = [row[1:] for row in rows]
            writer.writerows(data_to_save)

            ids = [row[0] for row in rows]
            placeholders = ",".join(["?"] * len(ids))
            conn.execute(f'UPDATE history SET exported = 1 WHERE id IN ({placeholders})', ids)
            conn.commit()
            print(f'Add {len(rows)} new rows to {CSV_PATH}')
    except Exception as e:
        print(f'Error while saving to CSV: {e}')


def run_monitor():
    db_conn = init_db()
    print('PARKINGÓW P+R KRAKÓW MONITOR ')

    with sync_playwright() as p:
        try:
                browser = p.chromium.launch(headless=True)
                try:
                    context = browser.new_context()
                    page = context.new_page()

                    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    print(f'[{ts}] Data download...')

                    page.goto(URL, wait_until='networkidle', timeout=60000)
                    html_content = page.content()

                    found_count = 0
                    for name in PARKING_NAMES:
                        pattern = re.escape(name) + r'.*?Wolnych:\s*(\d+)'
                        match = re.search(pattern, html_content, re.DOTALL)

                        if match:
                            wolne = int(match.group(1))
                            db_conn.execute(
                                'INSERT INTO history (timestamp, parking, free ) VALUES (?, ?, ?)',
                                (ts, name, wolne)
                            )
                            found_count += 1

                    if found_count > 0:
                        db_conn.commit()
                        export_to_csv(db_conn)
                    else:
                        print('Error: No data on site')

                except Exception as err:
                    print(f'Error: {err}')

                finally:
                    browser.close()
                    print('Browser closed')

                print('Waiting')

        except KeyboardInterrupt:
            print('\nClosing...')
        finally:
            if db_conn:
                export_to_csv(db_conn)
                db_conn.close()


if __name__ == '__main__':
    run_monitor()
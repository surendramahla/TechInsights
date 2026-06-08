import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'instance', 'site.db')
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    try:
        c.execute('ALTER TABLE user ADD COLUMN google_id VARCHAR(120)')
        print("Added google_id")
    except Exception as e:
        print(f"Skipped google_id: {e}")
    conn.commit()
    conn.close()

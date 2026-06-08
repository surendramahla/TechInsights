import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'instance', 'site.db')
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    try:
        c.execute('ALTER TABLE blog ADD COLUMN summary TEXT')
    except Exception as e:
        print(f"Summary column exists or error: {e}")
    try:
        c.execute('ALTER TABLE blog ADD COLUMN sentiment VARCHAR(50)')
    except Exception as e:
        print(f"Sentiment column exists or error: {e}")
    conn.commit()
    conn.close()
    print("Database altered successfully.")
else:
    print("DB not found.")

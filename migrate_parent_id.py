import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'instance', 'site.db')
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    try:
        c.execute('ALTER TABLE comment ADD COLUMN parent_id INTEGER REFERENCES comment(id)')
        print("Successfully added parent_id to comment table.")
    except Exception as e:
        print(f"Error (column might already exist or other issue): {e}")
        
    conn.commit()
    conn.close()
else:
    print("Database not found!")

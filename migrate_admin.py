import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'instance', 'site.db')
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # User cols
    for col, type_ in [('is_banned', 'BOOLEAN DEFAULT 0'), ('account_status', 'VARCHAR(20) DEFAULT "active"')]:
        try:
            c.execute(f'ALTER TABLE user ADD COLUMN {col} {type_}')
            print(f"Added {col} to user")
        except: pass
        
    # Blog cols
    for col, type_ in [('is_blocked', 'BOOLEAN DEFAULT 0'), ('is_featured', 'BOOLEAN DEFAULT 0'), ('moderation_reason', 'VARCHAR(200)')]:
        try:
            c.execute(f'ALTER TABLE blog ADD COLUMN {col} {type_}')
            print(f"Added {col} to blog")
        except: pass
        
    # Comment cols
    for col, type_ in [('is_reported', 'BOOLEAN DEFAULT 0')]:
        try:
            c.execute(f'ALTER TABLE comment ADD COLUMN {col} {type_}')
            print(f"Added {col} to comment")
        except: pass
        
    # ActivityLog table
    try:
        c.execute('''
        CREATE TABLE activity_log (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            action VARCHAR(50) NOT NULL,
            target_type VARCHAR(50),
            target_id INTEGER,
            details TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES user(id)
        )
        ''')
        print("Created activity_log table")
    except Exception as e:
        print(f"Skipped activity_log: {e}")
        
    conn.commit()
    conn.close()
    print("Database updated for admin system.")
else:
    print("DB not found.")

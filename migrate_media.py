import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'instance', 'site.db')

if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    try:
        c.execute('ALTER TABLE user ADD COLUMN profile_image_public_id VARCHAR(200)')
        print("Successfully added profile_image_public_id to user table.")
    except Exception as e:
        print(f"User table migration issue: {e}")
        
    try:
        c.execute("ALTER TABLE blog ADD COLUMN cover_image VARCHAR(255) DEFAULT 'default_cover.jpg'")
        c.execute('ALTER TABLE blog ADD COLUMN image_public_id VARCHAR(200)')
        print("Successfully added cover_image and image_public_id to blog table.")
    except Exception as e:
        print(f"Blog table migration issue: {e}")
        
    try:
        c.execute('''
        CREATE TABLE IF NOT EXISTS media (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name VARCHAR(255) NOT NULL,
            file_url VARCHAR(500) NOT NULL,
            public_id VARCHAR(200) NOT NULL,
            upload_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            user_id INTEGER NOT NULL,
            FOREIGN KEY(user_id) REFERENCES user(id)
        )
        ''')
        print("Successfully created Media table.")
    except Exception as e:
        print(f"Table creation issue: {e}")
        
    conn.commit()
    conn.close()
else:
    print("Database not found!")

import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'instance', 'site.db')

if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    try:
        c.execute('''
        CREATE TABLE IF NOT EXISTS notification (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER,
            receiver_id INTEGER NOT NULL,
            notification_type VARCHAR(50) NOT NULL,
            message VARCHAR(255) NOT NULL,
            link_url VARCHAR(255),
            is_read BOOLEAN DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(sender_id) REFERENCES user(id),
            FOREIGN KEY(receiver_id) REFERENCES user(id)
        )
        ''')
        print("Successfully created Notification table.")
    except Exception as e:
        print(f"Table creation issue (Notification): {e}")

    try:
        c.execute('''
        CREATE TABLE IF NOT EXISTS conversation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user1_id INTEGER NOT NULL,
            user2_id INTEGER NOT NULL,
            last_message_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user1_id) REFERENCES user(id),
            FOREIGN KEY(user2_id) REFERENCES user(id)
        )
        ''')
        print("Successfully created Conversation table.")
    except Exception as e:
        print(f"Table creation issue (Conversation): {e}")

    try:
        c.execute('''
        CREATE TABLE IF NOT EXISTS message (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            sender_id INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            message_content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_read BOOLEAN DEFAULT 0,
            FOREIGN KEY(conversation_id) REFERENCES conversation(id) ON DELETE CASCADE,
            FOREIGN KEY(sender_id) REFERENCES user(id),
            FOREIGN KEY(receiver_id) REFERENCES user(id)
        )
        ''')
        print("Successfully created Message table.")
    except Exception as e:
        print(f"Table creation issue (Message): {e}")
        
    conn.commit()
    conn.close()
else:
    print("Database not found!")

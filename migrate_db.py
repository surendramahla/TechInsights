"""
migrate_db.py — Run once to add new columns to the existing site.db
Usage: python migrate_db.py
"""
import sqlite3
import os

DB_PATH = os.path.join('instance', 'site.db')

def column_exists(cursor, table, column):
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())

def add_column_if_missing(cursor, table, column, col_type):
    if not column_exists(cursor, table, column):
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
        print(f"  + Added {table}.{column}")
    else:
        print(f"  OK {table}.{column} already exists")


conn = sqlite3.connect(DB_PATH)
cur  = conn.cursor()

print("\n[migrate_db] Applying schema migrations...\n")

# ── user table ───────────────────────────────────
add_column_if_missing(cur, 'user', 'date_joined', "DATETIME")

add_column_if_missing(cur, 'user', 'image_file',  "VARCHAR(200) DEFAULT 'default.jpg'")

# ── blog table ───────────────────────────────────
add_column_if_missing(cur, 'blog', 'views', "INTEGER DEFAULT 0")

# ── comment table — parent_id for nested replies ─
add_column_if_missing(cur, 'comment', 'parent_id', "INTEGER REFERENCES comment(id)")

# ── Create new tables if they don't exist ────────
cur.execute("""
CREATE TABLE IF NOT EXISTS tag (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(50) NOT NULL UNIQUE
)""")

cur.execute("""
CREATE TABLE IF NOT EXISTS blog_tags (
    blog_id INTEGER NOT NULL REFERENCES blog(id),
    tag_id  INTEGER NOT NULL REFERENCES tag(id),
    PRIMARY KEY (blog_id, tag_id)
)""")

cur.execute("""
CREATE TABLE IF NOT EXISTS bookmark (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES user(id),
    blog_id    INTEGER NOT NULL REFERENCES blog(id),
    date_saved DATETIME DEFAULT (datetime('now')),
    UNIQUE(user_id, blog_id)
)""")

cur.execute("""
CREATE TABLE IF NOT EXISTS comment_like (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES user(id),
    comment_id INTEGER NOT NULL REFERENCES comment(id),
    UNIQUE(user_id, comment_id)
)""")

conn.commit()
conn.close()
print("\n[migrate_db] Done! All migrations applied successfully.\n")

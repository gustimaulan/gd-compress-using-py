import sqlite3
import json
from pathlib import Path

# Initialize database path
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "database.db"

def get_db_connection():
    """Returns a database connection with dict-like rows."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the database schema if it doesn't exist."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # User configurations table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS configs (
                email TEXT PRIMARY KEY,
                folder_id TEXT,
                quality INTEGER,
                min_size_kb INTEGER,
                max_width INTEGER,
                max_height INTEGER,
                delete_original BOOLEAN,
                output_folder_id TEXT,
                cron_schedule TEXT,
                next_run REAL
            )
        ''')
        
        # Sessions table (token -> user info)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                email TEXT,
                name TEXT,
                picture TEXT
            )
        ''')
        
        # OAuth tokens table (email -> credentials JSON)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tokens (
                email TEXT PRIMARY KEY,
                credentials_json TEXT
            )
        ''')
        
        conn.commit()
    finally:
        conn.close()

# Helper functions for config
def get_user_config(email: str) -> dict:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM configs WHERE email = ?", (email,))
        row = cursor.fetchone()
        
        if row:
            # Convert to dict and handle boolean
            config = dict(row)
            config['delete_original'] = bool(config['delete_original'])
            return config
        else:
            # Default config
            return {
                "folder_id": "",
                "quality": 80,
                "min_size_kb": 0,
                "max_width": None,
                "max_height": None,
                "delete_original": False,
                "output_folder_id": "",
                "cron_schedule": "",
                "next_run": 0.0
            }
    finally:
        conn.close()

def save_user_config(email: str, config: dict):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO configs (
                email, folder_id, quality, min_size_kb, 
                max_width, max_height, delete_original, 
                output_folder_id, cron_schedule, next_run
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(email) DO UPDATE SET
                folder_id=excluded.folder_id,
                quality=excluded.quality,
                min_size_kb=excluded.min_size_kb,
                max_width=excluded.max_width,
                max_height=excluded.max_height,
                delete_original=excluded.delete_original,
                output_folder_id=excluded.output_folder_id,
                cron_schedule=excluded.cron_schedule,
                next_run=excluded.next_run
        ''', (
            email,
            config.get("folder_id", ""),
            config.get("quality", 80),
            config.get("min_size_kb", 0),
            config.get("max_width"),
            config.get("max_height"),
            1 if config.get("delete_original") else 0,
            config.get("output_folder_id", ""),
            config.get("cron_schedule", ""),
            config.get("next_run", 0.0)
        ))
        
        conn.commit()
    finally:
        conn.close()

# Helper functions for sessions
def create_session(token: str, email: str, name: str, picture: str):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO sessions (token, email, name, picture) VALUES (?, ?, ?, ?)",
            (token, email, name, picture)
        )
        conn.commit()
    finally:
        conn.close()

def get_session(token: str) -> dict | None:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sessions WHERE token = ?", (token,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def delete_session(token: str):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()
    finally:
        conn.close()

# Helper functions for tokens
def save_token(email: str, credentials_json: str):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO tokens (email, credentials_json) VALUES (?, ?)
            ON CONFLICT(email) DO UPDATE SET credentials_json=excluded.credentials_json
        ''', (email, credentials_json))
        conn.commit()
    finally:
        conn.close()

def get_token(email: str) -> str | None:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT credentials_json FROM tokens WHERE email = ?", (email,))
        row = cursor.fetchone()
        return row['credentials_json'] if row else None
    finally:
        conn.close()

def delete_token(email: str):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tokens WHERE email = ?", (email,))
        conn.commit()
    finally:
        conn.close()

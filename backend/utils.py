import os
import json
import hashlib
from pathlib import Path
from flask import session, jsonify
from functools import wraps
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# ─── Paths ───────────────────────────────────────────────────────────────────────────
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
TOKENS_DIR = DATA_DIR / "tokens"
TOKENS_DIR.mkdir(exist_ok=True)
CONFIG_FILE = DATA_DIR / "config.json"

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/drive",
]

IMAGE_MIME_TYPES = [
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/bmp",
    "image/tiff",
]

# ─── Helpers ───────────────────────────────────────────────────────────────────

CONFIGS_DIR = DATA_DIR / "configs"
CONFIGS_DIR.mkdir(exist_ok=True)

def _user_config_path() -> Path:
    email = session.get("user_email")
    if not email:
        return DATA_DIR / "config.json" # Unauthenticated fallback
    safe = hashlib.sha256(email.encode()).hexdigest()[:16]
    return CONFIGS_DIR / f"{safe}.json"

def load_config() -> dict:
    config_file = _user_config_path()
    if config_file.exists():
        try:
            return json.loads(config_file.read_text())
        except Exception:
            pass
    return {
        "folder_id": "",
        "quality": 80,
        "min_size_kb": 0,
        "max_width": None,
        "max_height": None,
        "delete_original": False,
        "output_folder_id": "",
    }

def save_config(data: dict):
    config_file = _user_config_path()
    config_file.write_text(json.dumps(data, indent=2))

def _user_token_path(email: str) -> Path:
    """Get the token file path for a specific user."""
    safe = hashlib.sha256(email.encode()).hexdigest()[:16]
    return TOKENS_DIR / f"{safe}.json"

def get_drive_service(user_email: str = None):
    """Build a Drive service from the current user's stored token."""
    email = user_email or (session.get("user_email") if session else None)
    if not email:
        return None
    token_file = _user_token_path(email)
    if not token_file.exists():
        return None
    try:
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token_file.write_text(creds.to_json())
        if creds and creds.valid:
            return build("drive", "v3", credentials=creds)
    except Exception:
        pass
    return None

def auth_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_email"):
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated

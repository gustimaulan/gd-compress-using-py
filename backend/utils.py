import os
import json
import hashlib
import secrets
from pathlib import Path
from flask import request, jsonify
from functools import wraps
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# ─── Paths ───────────────────────────────────────────────────────────────────────────
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

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

# ─── Token Session Store ──────────────────────────────────────────────────────

def create_session_token(email: str, name: str = "", picture: str = "") -> str:
    """Create a new session token and persist session data to database."""
    from .db import create_session
    token = secrets.token_hex(32)
    create_session(token, email, name, picture)
    return token

def get_session_data(token: str) -> dict | None:
    """Read session data for a given token. Returns None if invalid."""
    if not token:
        return None
    from .db import get_session
    return get_session(token)

def delete_session_token(token: str):
    """Delete a session token from database."""
    from .db import delete_session
    delete_session(token)

def _get_current_token() -> str | None:
    """Extract Bearer token from the Authorization header or query param (for SSE)."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    # Fallback: token as query param (needed for EventSource which can't set headers)
    return request.args.get("token")

def get_current_user_email() -> str | None:
    """Get the email of the currently authenticated user from the Bearer token."""
    token = _get_current_token()
    data = get_session_data(token)
    return data["email"] if data else None

# ─── Config (per-user) ────────────────────────────────────────────────────────

def load_config() -> dict:
    email = get_current_user_email()
    if email:
        from .db import get_user_config
        return get_user_config(email)
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

def save_config(data: dict):
    email = get_current_user_email()
    if not email:
        return
    from .db import save_user_config
    save_user_config(email, data)

# ─── Drive ────────────────────────────────────────────────────────────────────

def get_drive_service(user_email: str = None):
    """Build a Drive service from the current user's stored token."""
    email = user_email or get_current_user_email()
    if not email:
        return None
    
    from .db import get_token, save_token
    creds_json = get_token(email)
    if not creds_json:
        return None
        
    try:
        creds = Credentials.from_authorized_user_info(json.loads(creds_json), SCOPES)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            save_token(email, creds.to_json())
        if creds and creds.valid:
            return build("drive", "v3", credentials=creds)
    except Exception:
        pass
    return None

# ─── Auth Decorator ───────────────────────────────────────────────────────────

def auth_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        email = get_current_user_email()
        if not email:
            return jsonify({"error": "Unauthorized"}), 401
        # Attach email to request context for downstream use
        request.user_email = email
        return f(*args, **kwargs)
    return decorated

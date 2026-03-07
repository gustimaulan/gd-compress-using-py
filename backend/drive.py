import json
from collections import defaultdict
from flask import Blueprint, jsonify, request, session, Response
from .utils import (
    load_config,
    save_config,
    _user_token_path,
    get_drive_service,
    auth_required,
)
import os

drive_bp = Blueprint("drive", __name__)

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")

@drive_bp.route("/api/status")
def api_status():
    email = session.get("user_email")
    authed = email is not None
    drive_connected = False
    if authed:
        drive_connected = _user_token_path(email).exists()
    env_creds = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)
    config = load_config()
    return jsonify({
        "authenticated": authed,
        "drive_connected": drive_connected,
        "oauth_ready": env_creds,
        "google_client_id": GOOGLE_CLIENT_ID,
        "config": config,
    })

@drive_bp.route("/api/config", methods=["GET"])
def get_config():
    return jsonify(load_config())

@drive_bp.route("/api/config", methods=["POST"])
@auth_required
def set_config():
    data = request.json or {}
    config = load_config()
    for key in ["folder_id", "quality", "min_size_kb", "max_width", "max_height",
                "delete_original", "output_folder_id"]:
        if key in data:
            config[key] = data[key]
    save_config(config)
    return jsonify({"ok": True, "config": config})

@drive_bp.route("/api/drive/folders")
@auth_required
def list_drive_folders():
    service = get_drive_service()
    if not service:
        return jsonify({"error": "Not authenticated with Google Drive"}), 401

    try:
        folders = []
        page_token = None
        while True:
            resp = service.files().list(
                q="mimeType='application/vnd.google-apps.folder' and trashed=false",
                spaces="drive",
                fields="nextPageToken, files(id, name)",
                orderBy="name",
                pageSize=200,
                pageToken=page_token,
            ).execute()
            folders.extend(resp.get("files", []))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return jsonify(folders)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@drive_bp.route("/api/drive/duplicates")
@auth_required
def list_duplicates():
    folder_id = request.args.get("folder_id", "").strip()
    if not folder_id:
        return jsonify({"error": "folder_id is required"}), 400

    service = get_drive_service()
    if not service:
        return jsonify({"error": "Not authenticated with Google Drive"}), 401

    try:
        files = []
        page_token = None
        while True:
            resp = service.files().list(
                q=f"'{folder_id}' in parents and trashed=false and mimeType!='application/vnd.google-apps.folder'",
                spaces="drive",
                fields="nextPageToken, files(id, name, size, md5Checksum, mimeType, modifiedTime)",
                pageSize=500,
                pageToken=page_token,
            ).execute()
            files.extend(resp.get("files", []))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break

        hash_map = defaultdict(list)
        for f in files:
            key = f.get("md5Checksum") or f.get("name", "")
            hash_map[key].append(f)

        groups = []
        for key, group in hash_map.items():
            if len(group) > 1:
                groups.append({
                    "hash": key,
                    "count": len(group),
                    "files": group,
                })

        return jsonify({
            "total_files": len(files),
            "duplicate_groups": len(groups),
            "groups": groups,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@drive_bp.route("/api/drive/duplicates/cleanup", methods=["POST"])
@auth_required
def cleanup_duplicates():
    data = request.json or {}
    file_ids = data.get("file_ids", [])
    if not file_ids:
        return jsonify({"error": "No file_ids provided"}), 400

    service = get_drive_service()
    if not service:
        return jsonify({"error": "Not authenticated with Google Drive"}), 401

    def generate():
        deleted = 0
        errors = []
        for fid in file_ids:
            try:
                service.files().delete(fileId=fid).execute()
                deleted += 1
            except Exception as e:
                errors.append({"id": fid, "error": str(e)})
            
            chunk = json.dumps({"deleted": deleted, "errors": errors, "total": len(file_ids)})
            yield f"data: {chunk}\n\n"
        
        yield "data: __done__\n\n"

    return Response(generate(), mimetype="text/event-stream")

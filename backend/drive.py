import json
from collections import defaultdict
import os
from flask import Blueprint, jsonify, request, Response
import croniter
from datetime import datetime
from .utils import (
    load_config,
    save_config,
    get_drive_service,
    get_current_user_email,
    auth_required,
)

drive_bp = Blueprint("drive", __name__)

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")

@drive_bp.route("/api/status")
def api_status():
    email = get_current_user_email()
    authed = email is not None
    drive_connected = False
    if authed:
        from .db import get_token
        drive_connected = get_token(email) is not None
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
@auth_required
def get_config():
    return jsonify(load_config())

@drive_bp.route("/api/config", methods=["POST"])
@auth_required
def set_config():
    data = request.json or {}
    config = load_config()
    for key in ["folder_id", "quality", "min_size_kb", "max_width", "max_height",
                "delete_original", "output_folder_id", "cron_schedule"]:
        if key in data:
            config[key] = data[key]
            
    if "cron_schedule" in data:
        if data["cron_schedule"]:
            try:
                import pytz
                tz = pytz.timezone('Asia/Jakarta')
                # Calculate strictly in JKT local time
                now_jkt = datetime.now(tz).replace(tzinfo=None)
                itr = croniter.croniter(data["cron_schedule"], now_jkt)
                next_naive = itr.get_next(datetime)
                # Convert back to timezone-aware timestamp
                next_aware = tz.localize(next_naive)
                config["next_run"] = next_aware.timestamp()
            except Exception as e:
                return jsonify({"error": f"Invalid cron expression: {e}"}), 400
        else:
            config["next_run"] = 0.0

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
            ).execute(num_retries=3)
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
            ).execute(num_retries=3)
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
                service.files().delete(fileId=fid).execute(num_retries=3)
                deleted += 1
            except Exception as e:
                errors.append({"id": fid, "error": str(e)})
            
            chunk = json.dumps({"deleted": deleted, "errors": errors, "total": len(file_ids)})
            yield f"data: {chunk}\n\n"
        
        yield "data: __done__\n\n"

    return Response(generate(), mimetype="text/event-stream")

@drive_bp.route("/api/drive/storage")
@auth_required
def drive_storage():
    service = get_drive_service()
    if not service:
        return jsonify({"error": "Not authenticated with Google Drive"}), 401

    try:
        about = service.about().get(fields="storageQuota").execute(num_retries=3)
        quota = about.get("storageQuota", {})
        
        # quota structure usually has: limit, usage, usageInDrive, usageInDriveTrash
        return jsonify({
            "limit": int(quota.get("limit", 0)),
            "usage": int(quota.get("usage", 0)),
            "usageInDrive": int(quota.get("usageInDrive", 0)),
            "usageInDriveTrash": int(quota.get("usageInDriveTrash", 0))
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500



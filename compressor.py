#!/usr/bin/env python3
"""
Google Drive Image Compressor
------------------------------
Downloads images from a Google Drive folder, compresses them,
converts them to WebP format, and uploads them back to Drive.

Usage:
  python compressor.py --folder-id YOUR_FOLDER_ID [options]

Requirements:
  - credentials.json from Google Cloud Console (OAuth 2.0 Desktop App)
  - Run: pip install -r requirements.txt
"""

import os
import io
import argparse
import logging
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from PIL import Image
from tqdm import tqdm

# ─── Configuration ────────────────────────────────────────────────────────────

SCOPES = ["https://www.googleapis.com/auth/drive"]
CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"

# Supported image MIME types to process
IMAGE_MIME_TYPES = [
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/bmp",
    "image/tiff",
    "image/webp",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ─── Authentication ────────────────────────────────────────────────────────────

def authenticate_gdrive():
    """
    Authenticates with Google Drive using OAuth 2.0.
    On first run, opens a browser for consent and saves token.json.
    Subsequent runs reuse the cached token.
    """
    creds = None

    if not os.path.exists(CREDENTIALS_FILE):
        raise FileNotFoundError(
            f"'{CREDENTIALS_FILE}' not found. Download it from "
            "Google Cloud Console -> APIs & Services -> Credentials."
        )

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    # Refresh or obtain new credentials
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            log.info("Refreshing expired access token...")
            creds.refresh(Request())
        else:
            log.info("Starting OAuth flow — a browser window will open...")
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "w") as token_file:
            token_file.write(creds.to_json())
        log.info(f"Token saved to '{TOKEN_FILE}'.")

    return build("drive", "v3", credentials=creds)


# ─── Google Drive Operations ───────────────────────────────────────────────────

def list_images(service, folder_id: str, min_size_kb: int = 0):
    """
    Lists all image files in a Google Drive folder.
    Optionally filters by minimum file size.

    Args:
        service: Authenticated Drive API service.
        folder_id: The Google Drive folder ID to scan.
        min_size_kb: Only process files larger than this size (KB). 0 = all.

    Returns:
        List of file metadata dicts.
    """
    mime_query = " or ".join(
        [f"mimeType='{m}'" for m in IMAGE_MIME_TYPES if m != "image/webp"]
    )
    query = f"('{folder_id}' in parents) and ({mime_query}) and trashed=false"

    log.info(f"Scanning folder '{folder_id}' for images...")
    files = []
    page_token = None

    while True:
        response = (
            service.files()
            .list(
                q=query,
                spaces="drive",
                fields="nextPageToken, files(id, name, mimeType, size)",
                pageToken=page_token,
            )
            .execute()
        )

        for f in response.get("files", []):
            size_kb = int(f.get("size", 0)) / 1024
            if size_kb >= min_size_kb:
                files.append(f)

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    log.info(f"Found {len(files)} image(s) to process.")
    return files


def download_file(service, file_id: str) -> bytes:
    """Downloads a file from Google Drive into memory."""
    request = service.files().get_media(fileId=file_id)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)

    done = False
    while not done:
        _, done = downloader.next_chunk()

    buffer.seek(0)
    return buffer.read()


def upload_file(service, file_name: str, data: bytes, mime_type: str, parent_folder_id: str) -> str:
    """
    Uploads a file to Google Drive and returns the new file's ID.

    Args:
        service: Authenticated Drive API service.
        file_name: Name for the uploaded file.
        data: File content as bytes.
        mime_type: MIME type of the file.
        parent_folder_id: Parent folder ID to upload into.

    Returns:
        The ID of the newly created file.
    """
    metadata = {"name": file_name, "parents": [parent_folder_id]}
    media = MediaIoBaseUpload(io.BytesIO(data), mimetype=mime_type, resumable=True)
    uploaded = (
        service.files()
        .create(body=metadata, media_body=media, fields="id")
        .execute()
    )
    return uploaded.get("id")


def delete_file(service, file_id: str):
    """Moves a file to trash on Google Drive."""
    service.files().delete(fileId=file_id).execute()


# ─── Image Compression & Conversion ───────────────────────────────────────────

def compress_image(
    data: bytes,
    quality: int = 80,
    max_width: int = None,
    max_height: int = None,
) -> bytes:
    """
    Compresses an image and converts it to WebP format.

    Args:
        data: Raw image bytes.
        quality: WebP quality (1-100). Lower = smaller file, less quality.
        max_width: Optional max width. Image is resized proportionally.
        max_height: Optional max height. Image is resized proportionally.

    Returns:
        Compressed WebP image as bytes.
    """
    img = Image.open(io.BytesIO(data))

    # Convert palette/transparent images properly before saving as WebP
    if img.mode in ("P", "RGBA"):
        img = img.convert("RGBA")
    elif img.mode != "RGB":
        img = img.convert("RGB")

    # Optional proportional resize
    if max_width or max_height:
        orig_w, orig_h = img.size
        target_w = max_width or orig_w
        target_h = max_height or orig_h
        img.thumbnail((target_w, target_h), Image.LANCZOS)

    # Save as WebP
    output = io.BytesIO()
    img.save(output, format="WEBP", quality=quality, method=6)
    output.seek(0)
    return output.read()


# ─── Main Orchestration ────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Compress & convert Google Drive images to WebP remotely."
    )
    parser.add_argument(
        "--folder-id",
        required=True,
        help="Google Drive folder ID containing the images.",
    )
    parser.add_argument(
        "--quality",
        type=int,
        default=80,
        help="WebP output quality (1-100). Default: 80.",
    )
    parser.add_argument(
        "--max-width",
        type=int,
        default=None,
        help="Optional: Max image width in pixels (proportional resize).",
    )
    parser.add_argument(
        "--max-height",
        type=int,
        default=None,
        help="Optional: Max image height in pixels (proportional resize).",
    )
    parser.add_argument(
        "--min-size-kb",
        type=int,
        default=0,
        help="Only process images larger than this size in KB. Default: 0 (all).",
    )
    parser.add_argument(
        "--delete-original",
        action="store_true",
        help="Delete original files from Drive after uploading the WebP version.",
    )
    parser.add_argument(
        "--output-folder-id",
        default=None,
        help="Upload WebP files to a different folder. Defaults to the same source folder.",
    )

    args = parser.parse_args()

    output_folder = args.output_folder_id or args.folder_id

    # ── Authenticate ──
    log.info("Authenticating with Google Drive...")
    service = authenticate_gdrive()
    log.info("Authenticated successfully.")

    # ── List images ──
    files = list_images(service, args.folder_id, min_size_kb=args.min_size_kb)
    if not files:
        log.info("No images found. Exiting.")
        return

    # ── Process ──
    success_count = 0
    skip_count = 0
    fail_count = 0

    for file in tqdm(files, desc="Processing images", unit="file"):
        original_name = file["name"]
        file_id = file["id"]
        original_size = int(file.get("size", 0))

        stem = Path(original_name).stem
        webp_name = f"{stem}.webp"

        try:
            tqdm.write(f"\n📥 Downloading: {original_name} ({original_size / 1024:.1f} KB)")
            raw_data = download_file(service, file_id)

            tqdm.write(f"⚙️  Compressing & converting to WebP (quality={args.quality})...")
            webp_data = compress_image(
                raw_data,
                quality=args.quality,
                max_width=args.max_width,
                max_height=args.max_height,
            )

            webp_size = len(webp_data)
            savings_pct = (1 - webp_size / original_size) * 100 if original_size > 0 else 0

            tqdm.write(
                f"📤 Uploading: {webp_name} "
                f"({webp_size / 1024:.1f} KB | saved {savings_pct:.1f}%)"
            )
            new_id = upload_file(
                service, webp_name, webp_data, "image/webp", output_folder
            )
            tqdm.write(f"✅ Uploaded as '{webp_name}' (ID: {new_id})")

            if args.delete_original:
                delete_file(service, file_id)
                tqdm.write(f"🗑️  Deleted original: {original_name}")

            success_count += 1

        except Exception as e:
            tqdm.write(f"❌ Failed to process '{original_name}': {e}")
            log.exception(f"Error processing file '{original_name}'")
            fail_count += 1

    # ── Summary ──
    print("\n" + "─" * 50)
    print(f"✅ Processed:  {success_count} file(s)")
    print(f"⏭️  Skipped:    {skip_count} file(s)")
    print(f"❌ Failed:     {fail_count} file(s)")
    print("─" * 50)


if __name__ == "__main__":
    main()

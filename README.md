# gd-compress-using-py

A Python script to **compress images stored on Google Drive** remotely from your local machine. It downloads each image, compresses it with a configurable quality level, converts it to the modern **WebP** format (for much smaller file sizes), and uploads the result back to Drive.

---

## Features

- 🔐 **Secure OAuth 2.0 authentication** — token is cached locally after first login
- 🔍 **Scans a Drive folder** for JPEG, PNG, GIF, BMP, TIFF images
- ⚙️ **Compresses & converts to WebP** for significant file-size savings (often 30–80% smaller)
- 📐 **Optional proportional resizing** via `--max-width` / `--max-height`
- 📤 **Uploads WebP directly to Drive** (same folder or a different one)
- 🗑️ **Optionally deletes originals** with `--delete-original`
- 📊 **Progress bar** and per-file savings report

---

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Get Google Drive API credentials

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select an existing one)
3. Navigate to **APIs & Services → Library** and enable the **Google Drive API**
4. Go to **APIs & Services → OAuth consent screen** → configure (External is fine; add your email as a test user)
5. Go to **APIs & Services → Credentials → Create Credentials → OAuth client ID**
   - Application type: **Desktop app**
6. Download the JSON file and rename it to **`credentials.json`**
7. Place `credentials.json` in the same directory as `compressor.py`

### 3. Get your folder ID

Open the Google Drive folder in your browser. The URL looks like:

```
https://drive.google.com/drive/folders/1aBcDeFgHiJklMnOpQrStUvWxYz
                                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                        This is your folder ID
```

---

## Usage

```bash
python compressor.py --folder-id YOUR_FOLDER_ID [options]
```

### Options

| Flag                 | Default            | Description                                |
| -------------------- | ------------------ | ------------------------------------------ |
| `--folder-id`        | _(required)_       | Drive folder ID to scan                    |
| `--quality`          | `80`               | WebP quality (1–100). Lower = smaller file |
| `--max-width`        | None               | Resize images to max width (proportional)  |
| `--max-height`       | None               | Resize images to max height (proportional) |
| `--min-size-kb`      | `0`                | Skip images smaller than this (KB)         |
| `--delete-original`  | False              | Delete originals after uploading WebP      |
| `--output-folder-id` | _(same as source)_ | Upload WebP to a different folder          |

### Examples

```bash
# Compress all images in a folder (quality 80, keep originals)
python compressor.py --folder-id 1aBcDeFgHiJklMnOpQrStUvWxYz

# Compress only images larger than 500 KB, at quality 70, and delete originals
python compressor.py --folder-id 1aBcDeFgHiJklMnOpQrStUvWxYz \
  --min-size-kb 500 \
  --quality 70 \
  --delete-original

# Resize to max 1920px wide and upload to a separate output folder
python compressor.py --folder-id 1aBcDeFgHiJklMnOpQrStUvWxYz \
  --max-width 1920 \
  --output-folder-id 2xYzAbCdEfGhIjKl

# All options at once
python compressor.py \
  --folder-id 1aBcDeFgHiJklMnOpQrStUvWxYz \
  --quality 75 \
  --max-width 2560 \
  --min-size-kb 100 \
  --delete-original \
  --output-folder-id 2xYzAbCdEfGhIjKl
```

---

## First Run

On the first run, a **browser window will open** asking you to sign in with Google and grant Drive access. After you approve, a `token.json` file is saved locally. All future runs will reuse this token automatically.

> **Note:** `token.json` and `credentials.json` contain sensitive credentials. Do not commit them to version control.

---

## .gitignore

A `.gitignore` is included to protect your credentials.

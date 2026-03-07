# Google Drive Image Compressor & Duplicate Finder

A modern web application built with **Flask** (backend) and **Vue 3/Vite** (frontend) to optimize and manage your Google Drive storage remotely. Any Google user can log in with their Google account to securely compress images to **WebP** and find/remove duplicate files.

---

## 🚀 Features

- **Multi-tenant OAuth 2.0**: Secure "Sign In with Google" flow allowing any Gmail user to compress their files without needing to share credentials.
- **Image Compression**: Scans Drive folders for large images (JPEG, PNG, etc.) and compresses them into space-saving WebP format (often 30–80% smaller) with options to auto-delete originals.
- **Duplicate Finder**: Identify exact duplicate files by their MD5 checksums within a Google Drive folder and securely remove repetitive copies.
- **Background Jobs**: Asynchronous compression streams real-time console progress directly to your browser using Server-Sent Events (SSE).
- **Responsive Web UI**: Built with Vue 3 for a fluid, app-like experience across desktop and mobile devices.

---

## 🛠️ Tech Stack

- **Backend**: Python 3.12, Flask, Google API Client, Pillow (Image Processing)
- **Frontend**: Node.js, Vue 3, Vite, Vue Router, Vanilla CSS
- **Deployment**: Docker, Docker Compose, Dokploy / Traefik ready

---

## ⚙️ How to Run Locally

### 1. Requirements

- Node.js 18+
- Python 3.11+
- Google Cloud Console Project

### 2. Google OAuth Setup

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Navigate to **APIs & Services → Library** and enable the **Google Drive API**
3. Go to **APIs & Services → Credentials → Create Credentials → OAuth client ID**
   - Application type: **Web application**
   - Authorized redirect URIs: `http://localhost:5001/api/oauth/callback`

### 3. Environment Variables

Copy `.env.example` to `.env` and fill in the Google OAuth credentials:

```bash
cp .env.example .env
```

Ensure `APP_DOMAIN` is set correctly:

```env
# For local dev
APP_DOMAIN=http://localhost:5001

# For production
APP_DOMAIN=https://gdc.gmdhia.my.id
```

### 4. Run the Backend (Flask)

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

> The backend runs on `http://127.0.0.1:5001`.

### 5. Run the Frontend (Vue 3)

In a new terminal window:

```bash
cd frontend
npm install
npm run dev
```

> Visit the frontend at `http://localhost:5173`.

---

## 🐳 Deployment (Docker / Dokploy)

The project includes a multi-stage `Dockerfile` and `docker-compose.yml` to run the entire app (compiled Vue + Flask) in a single container.

1. Configure your `.env` with your production `APP_DOMAIN` (e.g., `https://example.com`)
2. In Google Cloud Console, add `https://example.com/api/oauth/callback` to your Authorized Redirect URIs.
3. Deploy via Docker Compose or Dokploy:

```bash
docker-compose up -d --build
```

The container listens internally on port `5001` and is pre-configured with `Traefik` labels for easy reverse-proxying.

---

## 🔒 Privacy & Security

- **Server-Side Token Storage**: Tokens are stored securely as short-lived authenticated hashes in `data/tokens/`.
- **User Segregation**: `app.py` enforces strict per-user `drive_service` access using session checks. You can only view and compress files from your own Drive.
- `token.json` or `credentials.json` file uploads are obsolete.

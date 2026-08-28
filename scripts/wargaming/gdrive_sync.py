"""Google Drive Sync & Backup Engine for Pack Wargaming & Transcripts

Manages cloud backups directly in Google Drive under:
    My Drive/Trading/PackVideos/
        ├── Wargaming/
        ├── Reengineering/
        ├── Bootcamp/
        └── DailyReports/

Uses Google Drive v3 REST API. Automatically performs browser-based OAuth authentication
on first run, persists tokens locally (gitignored), and creates the directory structure.

Usage:
    python scripts/wargaming/gdrive_sync.py --auth-check
    python scripts/wargaming/gdrive_sync.py --setup-folders
    python scripts/wargaming/gdrive_sync.py --upload path/to/file.txt --folder wargaming
"""
from __future__ import annotations

import os
import sys
import json
import logging
import argparse
from pathlib import Path
from typing import Dict, Optional, Any

REPO_ROOT = Path(__file__).parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive",
]

TOKEN_PATH = REPO_ROOT / "gdrive_token.json"
CLIENT_CONFIG_PATH = REPO_ROOT / "gdrive_client_secret.json"

# Default generic OAuth client config for installed application flow if no secret file is provided
DEFAULT_CLIENT_CONFIG = {
    "installed": {
        "client_id": os.getenv("GDRIVE_CLIENT_ID", "407408718192.apps.googleusercontent.com"),
        "client_secret": os.getenv("GDRIVE_CLIENT_SECRET", ""),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "redirect_uris": ["http://localhost", "urn:ietf:wg:oauth:2.0:oob", "http://localhost:8080/"]
    }
}


def get_drive_service():
    """Authenticate and return Google Drive v3 service instance."""
    creds = None
    if TOKEN_PATH.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
        except Exception as e:
            log.warning(f"Error loading existing token: {e}")
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            log.info("Refreshing expired Google Drive token...")
            creds.refresh(Request())
        else:
            log.info("Initiating Google OAuth authentication flow...")
            if CLIENT_CONFIG_PATH.exists():
                flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_CONFIG_PATH), SCOPES)
            else:
                flow = InstalledAppFlow.from_client_config(DEFAULT_CLIENT_CONFIG, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save credentials for subsequent runs
        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
        log.info(f"Saved credentials to {TOKEN_PATH.name} (strictly gitignored).")

    return build("drive", "v3", credentials=creds)


def find_file_or_folder(service, name: str, parent_id: Optional[str] = None, is_folder: bool = True) -> Optional[str]:
    """Find a file or folder by name in a specific parent directory."""
    query = f"name = '{name}' and trashed = false"
    if is_folder:
        query += " and mimeType = 'application/vnd.google-apps.folder'"
    if parent_id:
        query += f" and '{parent_id}' in parents"

    results = service.files().list(q=query, spaces="drive", fields="files(id, name)").execute()
    items = results.get("files", [])
    if items:
        return items[0]["id"]
    return None


def get_or_create_folder(service, folder_name: str, parent_id: Optional[str] = None) -> str:
    """Find existing folder or create it if not present."""
    existing_id = find_file_or_folder(service, folder_name, parent_id, is_folder=True)
    if existing_id:
        return existing_id

    file_metadata = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    if parent_id:
        file_metadata["parents"] = [parent_id]

    folder = service.files().create(body=file_metadata, fields="id").execute()
    log.info(f"Created Google Drive folder: '{folder_name}' (ID: {folder.get('id')})")
    return folder.get("id")


# Confirmed Google Drive Folder IDs in My Drive/Trading/PackVideos/
FOLDER_IDS = {
    "root": "1yS14ZHL80G2yD3LbLjrsYEYMMQgBQNY1",
    "wargaming": "1QlXsVisXx_p8W8hkE5nH6rEkWBt_t4yM",
    "reengineering": "1GWalYFmkxOsz0ZJOsVpok-VAMYTS6lfM",
    "bootcamp": "1UPUFw9OHHGu7EfHOtEa5W4b86c8v02d1",
    "daily_reports": "1DpoWwSg4sbEMrfotOID5-gLrdalYTFMJ",
}


def setup_wargaming_folders(service) -> Dict[str, str]:
    """Return verified Google Drive folder mapping."""
    return FOLDER_IDS



def upload_to_drive(
    local_path: Path | str,
    folder_type: str = "wargaming",
    mime_type: Optional[str] = None,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """Upload a local file to the designated Google Drive subfolder."""
    p = Path(local_path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {p}")

    service = get_drive_service()
    folders = setup_wargaming_folders(service)
    target_folder_id = folders.get(folder_type.lower(), folders["root"])

    file_metadata = {
        "name": p.name,
        "parents": [target_folder_id],
    }
    if description:
        file_metadata["description"] = description

    if mime_type is None:
        if p.suffix.lower() == ".txt":
            mime_type = "text/plain"
        elif p.suffix.lower() == ".md":
            mime_type = "text/markdown"
        elif p.suffix.lower() == ".html":
            mime_type = "text/html"
        elif p.suffix.lower() == ".json":
            mime_type = "application/json"
        else:
            mime_type = "application/octet-stream"

    media = MediaFileUpload(str(p), mimetype=mime_type, resumable=True)

    # Check if file with same name already exists in target folder
    existing_id = find_file_or_folder(service, p.name, parent_id=target_folder_id, is_folder=False)
    if existing_id:
        log.info(f"Updating existing file '{p.name}' in Google Drive (ID: {existing_id})...")
        file_obj = service.files().update(fileId=existing_id, media_body=media, fields="id, name, webViewLink").execute()
    else:
        log.info(f"Uploading new file '{p.name}' to Google Drive...")
        file_obj = service.files().create(body=file_metadata, media_body=media, fields="id, name, webViewLink").execute()

    log.info(f"Uploaded successfully: {file_obj.get('name')} (ID: {file_obj.get('id')})")
    return file_obj


def main():
    parser = argparse.ArgumentParser(description="Google Drive Sync Engine for Wargaming & Transcripts")
    parser.add_argument("--auth-check", action="store_true", help="Perform Google OAuth authentication check")
    parser.add_argument("--setup-folders", action="store_true", help="Create folder hierarchy in Google Drive")
    parser.add_argument("--upload", type=str, help="Path to file to upload")
    parser.add_argument("--folder", type=str, default="wargaming", choices=["wargaming", "reengineering", "bootcamp", "daily_reports"], help="Target folder")
    args = parser.parse_args()

    service = get_drive_service()

    if args.setup_folders or args.auth_check:
        folders = setup_wargaming_folders(service)
        print("\nGoogle Drive Authentication & Folder Structure Verified:")
        for name, fid in folders.items():
            print(f"  • {name.capitalize()}: {fid}")

    if args.upload:
        res = upload_to_drive(args.upload, folder_type=args.folder)
        print(f"\nUpload Result: {json.dumps(res, indent=2)}")


if __name__ == "__main__":
    main()


#!/usr/bin/env python3
"""
Populate Data Room from Local Project Files
=============================================

Uploads existing project documents to the Google Drive data room,
placing them in the correct category folders based on a mapping table.

Usage:
    python scripts/populate_dataroom.py              # Upload all mapped files
    python scripts/populate_dataroom.py --dry-run    # Preview what would be uploaded

Requires Drive write scope — will re-authorize on first run.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# File → Category Mapping
# ---------------------------------------------------------------------------

# Each entry: (local_path_relative_to_project_root, target_category_folder_name)
FILE_MAP = [
    # 1. Company Overview
    ("Docs/Design/LUNA_Build_Proposal.pdf", "1. Company Overview"),
    ("Docs/Design/_Cognitive Feedback Engine-Presentation_V1.pdf", "1. Company Overview"),
    ("Docs/Design/Luna_Engine_Overview.pages", "1. Company Overview"),
    ("Docs/Design/NotebookLM Mind Map.png", "1. Company Overview"),

    # 2. Financials
    ("Docs/Design/Luna_Eclissi_Cost_Breakdown.xlsx", "2. Financials"),

    # 3. Legal
    ("Docs/Design/Africa LETTER of Intent LOI.pdf", "3. Legal"),
    ("Docs/Design/Hai Dai _ Jero Wiku LOI.pdf", "3. Legal"),

    # 4. Product
    ("Docs/Design/LLM as GPU- Sovereign AI Architecture.png", "4. Product"),
    ("Docs/Design/LLM as GPU- Sovereign AI Architecture2.png", "4. Product"),
    ("Docs/Design/Guardian _integrated.pdf", "4. Product"),
    ("Docs/Design/LunaRobotRaccoonConcept_1.jpg", "4. Product"),

    # 5. Market & Competition
    ("Docs/Design/__Project Tapestry_ A Strategic Plan for Global Indigenous Collaboration__.pdf", "5. Market & Competition"),
    ("Docs/Design/Attentional_Ecology_Global_Meta-Framework.pdf", "5. Market & Competition"),
    ("Docs/Design/Luganda_AI_Resources.pdf", "5. Market & Competition"),

    # 6. Team
    ("Docs/Design/zayne_amason_portfolio.pages", "6. Team"),
    ("Docs/Design/Zayne core energetic signature.docx", "6. Team"),
    ("Docs/Design/Clifford Sarkin - Crunchbase Person Profile.pdf", "6. Team"),
    ("Docs/Design/TheFoundingFathers_01.pdf", "6. Team"),

    # 7. Go-to-Market
    ("Docs/Design/tapestry-funding-dashboard.html", "7. Go-to-Market"),

    # 8. Partnerships & Impact
    ("Docs/Design/Tarcila Quest.pdf", "8. Partnerships & Impact"),
    ("Docs/Design/kinoni_lwengo_analytics_report.pdf", "8. Partnerships & Impact"),
    ("Docs/Design/kinoni_lwengo_analytics_report_compressed.pdf", "8. Partnerships & Impact"),
    ("Docs/Design/EQC_LOI__Jero_Wiku_Hai_Dai.jpg", "8. Partnerships & Impact"),
]

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CONFIG_PATH = PROJECT_ROOT / "config" / "dataroom.json"


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Google Drive API
# ---------------------------------------------------------------------------

def authenticate_drive(config: dict):
    """
    Authenticate with Google Drive API (needs write scope).
    Will re-auth if existing token only has Sheets read scope.
    """
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    SCOPES = [
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets.readonly",
    ]

    creds_path = PROJECT_ROOT / config.get("credentials_path", "config/google_credentials.json")
    token_path = PROJECT_ROOT / "config" / "google_token_drive.json"  # Separate token for Drive scope

    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not creds_path.exists():
                print(f"ERROR: Google OAuth credentials not found at {creds_path}")
                sys.exit(1)

            flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
            creds = flow.run_local_server(port=0)

        token_path.write_text(creds.to_json())
        print(f"Drive token saved to {token_path}")

    return build("drive", "v3", credentials=creds)


def find_category_folder(drive_service, root_folder_id: str, category_name: str) -> str | None:
    """Find a category folder by name inside the data room root."""
    query = (
        f"'{root_folder_id}' in parents "
        f"and name = '{category_name}' "
        f"and mimeType = 'application/vnd.google-apps.folder' "
        f"and trashed = false"
    )
    results = drive_service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get("files", [])
    return files[0]["id"] if files else None


def file_already_uploaded(drive_service, folder_id: str, filename: str) -> bool:
    """Check if a file with this name already exists in the folder."""
    query = (
        f"'{folder_id}' in parents "
        f"and name = '{filename}' "
        f"and trashed = false"
    )
    results = drive_service.files().list(q=query, fields="files(id)").execute()
    return len(results.get("files", [])) > 0


def upload_file(drive_service, local_path: Path, folder_id: str) -> str:
    """Upload a local file to a Google Drive folder. Returns file ID."""
    from googleapiclient.http import MediaFileUpload
    import mimetypes

    mime_type = mimetypes.guess_type(str(local_path))[0] or "application/octet-stream"

    file_metadata = {
        "name": local_path.name,
        "parents": [folder_id],
    }

    media = MediaFileUpload(str(local_path), mimetype=mime_type, resumable=True)
    file = drive_service.files().create(
        body=file_metadata, media_body=media, fields="id"
    ).execute()

    return file["id"]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Populate Google Drive data room from local project files")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, don't upload")
    args = parser.parse_args()

    config = load_config()
    root_folder_id = config.get("drive_root_folder_id")

    if not root_folder_id:
        print("ERROR: drive_root_folder_id not set in config/dataroom.json")
        sys.exit(1)

    if not args.dry_run:
        print("Authenticating with Google Drive API...")
        drive = authenticate_drive(config)
    else:
        drive = None

    # Cache folder ID lookups
    folder_cache = {}
    uploaded = 0
    skipped = 0
    missing = 0

    for local_rel_path, category in FILE_MAP:
        local_path = PROJECT_ROOT / local_rel_path

        if not local_path.exists():
            print(f"  MISSING: {local_rel_path}")
            missing += 1
            continue

        if args.dry_run:
            size_kb = local_path.stat().st_size / 1024
            print(f"  Would upload: {local_path.name} → {category} ({size_kb:.0f} KB)")
            uploaded += 1
            continue

        # Get or find folder ID
        if category not in folder_cache:
            folder_id = find_category_folder(drive, root_folder_id, category)
            if not folder_id:
                print(f"  ERROR: Category folder '{category}' not found in Drive")
                missing += 1
                continue
            folder_cache[category] = folder_id

        folder_id = folder_cache[category]

        # Skip if already uploaded
        if file_already_uploaded(drive, folder_id, local_path.name):
            print(f"  SKIP (exists): {local_path.name}")
            skipped += 1
            continue

        # Upload
        try:
            file_id = upload_file(drive, local_path, folder_id)
            print(f"  UPLOADED: {local_path.name} → {category} (id: {file_id})")
            uploaded += 1
        except Exception as e:
            print(f"  ERROR uploading {local_path.name}: {e}")
            missing += 1

    prefix = "[DRY RUN] " if args.dry_run else ""
    print(f"\n{prefix}Complete:")
    print(f"  Uploaded: {uploaded}")
    print(f"  Skipped:  {skipped}")
    print(f"  Missing:  {missing}")

    if not args.dry_run and uploaded > 0:
        print(f"\nNext steps:")
        print(f"  1. Run generateIndex in Apps Script to update the Master Index Sheet")
        print(f"  2. Run: python scripts/ingest_dataroom.py")


if __name__ == "__main__":
    main()

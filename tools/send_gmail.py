"""
Send newsletter HTML via Gmail API using OAuth2.

Setup (one-time):
    1. Go to Google Cloud Console → APIs & Services → Enable Gmail API
    2. Create OAuth 2.0 credentials (Desktop app) → download as credentials.json
    3. Place credentials.json in the project root
    4. First run will open a browser for authorization → creates token.json

Usage:
    python tools/send_gmail.py --html .tmp/newsletter_2026-03-21.html --to recipients.json --subject "Your Subject"
    python tools/send_gmail.py --html .tmp/newsletter_2026-03-21.html --to "user@example.com" --subject "Your Subject"

recipients.json format:
    ["user1@example.com", "user2@example.com"]
    or
    [{"email": "user1@example.com", "name": "User One"}]
"""

import argparse
import base64
import json
import sys
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

BASE_DIR = Path(__file__).resolve().parent.parent
CREDENTIALS_FILE = BASE_DIR / "credentials.json"
TOKEN_FILE = BASE_DIR / "token.json"
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

# Gmail sending limits
GMAIL_FREE_LIMIT = 500
WORKSPACE_LIMIT = 2000


def get_gmail_service():
    creds = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                print("Error: credentials.json not found in project root.", file=sys.stderr)
                print("Download it from Google Cloud Console → APIs & Services → Credentials", file=sys.stderr)
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def load_recipients(source: str) -> list[dict]:
    path = Path(source)
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        recipients = []
        for item in data:
            if isinstance(item, str):
                recipients.append({"email": item, "name": ""})
            elif isinstance(item, dict):
                recipients.append({"email": item["email"], "name": item.get("name", "")})
        return recipients
    else:
        # Treat as comma-separated emails
        emails = [e.strip() for e in source.split(",") if e.strip()]
        return [{"email": e, "name": ""} for e in emails]


def create_message(sender: str, to_email: str, subject: str, html_content: str) -> dict:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to_email

    # Plain text fallback
    plain_text = "This newsletter is best viewed in an HTML-capable email client."
    msg.attach(MIMEText(plain_text, "plain"))
    msg.attach(MIMEText(html_content, "html"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
    return {"raw": raw}


def send_newsletter(html_path: str, recipients: list[dict], subject: str, sender: str = "me",
                    delay: float = 0.5) -> list[dict]:
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    # Check limits
    count = len(recipients)
    if count > GMAIL_FREE_LIMIT:
        print(f"Warning: {count} recipients exceeds free Gmail limit ({GMAIL_FREE_LIMIT}/day).", file=sys.stderr)
        print(f"Google Workspace limit is {WORKSPACE_LIMIT}/day.", file=sys.stderr)

    service = get_gmail_service()
    results = []

    for i, recipient in enumerate(recipients, 1):
        email = recipient["email"]
        try:
            message = create_message(sender, email, subject, html_content)
            sent = service.users().messages().send(userId="me", body=message).execute()
            results.append({"email": email, "status": "sent", "message_id": sent.get("id", "")})
            print(f"  [{i}/{count}] Sent to {email}")
        except Exception as e:
            results.append({"email": email, "status": "failed", "error": str(e)})
            print(f"  [{i}/{count}] Failed: {email} - {e}")

        if i < count:
            time.sleep(delay)

    return results


def main():
    parser = argparse.ArgumentParser(description="Send newsletter via Gmail API")
    parser.add_argument("--html", required=True, help="Path to newsletter HTML file")
    parser.add_argument("--to", required=True, help="Recipient(s): email, comma-separated emails, or JSON file path")
    parser.add_argument("--subject", required=True, help="Email subject line")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between sends in seconds (default: 0.5)")
    parser.add_argument("--dry-run", action="store_true", help="Validate inputs without sending")
    args = parser.parse_args()

    html_path = Path(args.html)
    if not html_path.exists():
        print(f"Error: HTML file not found: {args.html}", file=sys.stderr)
        sys.exit(1)

    recipients = load_recipients(args.to)
    if not recipients:
        print("Error: No recipients found", file=sys.stderr)
        sys.exit(1)

    print(f"Newsletter: {args.html}")
    print(f"Subject: {args.subject}")
    print(f"Recipients: {len(recipients)}")

    if args.dry_run:
        print("\n[DRY RUN] Would send to:")
        for r in recipients:
            name_part = f" ({r['name']})" if r['name'] else ""
            print(f"  - {r['email']}{name_part}")
        return

    print("\nSending...")
    results = send_newsletter(str(html_path), recipients, args.subject, delay=args.delay)

    # Summary
    sent = sum(1 for r in results if r["status"] == "sent")
    failed = sum(1 for r in results if r["status"] == "failed")
    print(f"\nDone: {sent} sent, {failed} failed")

    # Save report
    report_path = BASE_DIR / ".tmp" / "send_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"Report saved: {report_path}")


if __name__ == "__main__":
    main()

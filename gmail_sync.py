from __future__ import annotations

import os
import argparse
from pathlib import Path
from datetime import datetime
from email.utils import parsedate_to_datetime

import pandas as pd

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# We only need read-only access
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

JOBS_CSV = Path("jobs.csv")


def get_gmail_service():
    """
    Load Gmail API credentials and return an authenticated service object.
    On first run, opens a browser window to ask for permission.
    """
    creds = None
    token_path = Path("token.json")

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # credentials.json comes from Google Cloud Console
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with token_path.open("w") as token_file:
            token_file.write(creds.to_json())

    service = build("gmail", "v1", credentials=creds)
    return service


def gmail_search(service, query: str, max_results: int = 200):
    """
    Search Gmail with a query string. Returns a list of message metadata dicts.
    """
    messages = []
    request = service.users().messages().list(userId="me", q=query, maxResults=max_results)
    while request is not None:
        response = request.execute()
        msgs = response.get("messages", [])
        messages.extend(msgs)
        request = service.users().messages().list_next(previous_request=request, previous_response=response)
    return messages


def get_header(headers, name: str) -> str:
    """
    Extract a header value from Gmail message headers.
    """
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def parse_date(date_str: str) -> str:
    """
    Convert email Date header to YYYY-MM-DD (local date).
    """
    try:
        dt = parsedate_to_datetime(date_str)
        # convert to date only
        return dt.date().isoformat()
    except Exception:
        return ""


def load_jobs_df() -> pd.DataFrame:
    """
    Load jobs.csv if it exists, otherwise create an empty DataFrame
    with the expected columns.
    """
    if JOBS_CSV.exists():
        df = pd.read_csv(JOBS_CSV)
    else:
        df = pd.DataFrame(
            columns=[
                "company",
                "role_title",
                "job_link",
                "applied_date",
                "status",
                "job_text",
                "summary",
                "skills",
                "salary",
            ]
        )

    # Ensure all expected columns exist
    for col in [
        "company",
        "role_title",
        "job_link",
        "applied_date",
        "status",
        "job_text",
        "summary",
        "skills",
        "salary",
    ]:
        if col not in df.columns:
            df[col] = ""

    return df


def save_jobs_df(df: pd.DataFrame):
    df.to_csv(JOBS_CSV, index=False)
    print(f"Saved jobs to {JOBS_CSV}")


def scan_confirmations(service, df: pd.DataFrame) -> pd.DataFrame:
    """
    Find application confirmation emails and add them to jobs.csv
    if not already present.
    """
    print("Scanning for application confirmation emails...")

    query = (
        'subject:("application received" OR "thank you for applying" OR '
        '"we received your application" OR "your application has been submitted") '
        "newer_than:365d"
    )

    messages = gmail_search(service, query)
    print(f"Found {len(messages)} potential confirmation emails.")

    for msg_meta in messages:
        msg = service.users().messages().get(
            userId="me",
            id=msg_meta["id"],
            format="metadata",
            metadataHeaders=["From", "Subject", "Date"],
        ).execute()

        headers = msg.get("payload", {}).get("headers", [])
        subject = get_header(headers, "Subject")
        from_header = get_header(headers, "From")
        date_header = get_header(headers, "Date")
        snippet = msg.get("snippet", "")

        applied_date = parse_date(date_header)

        # Simple heuristic:
        company = from_header  # you can manually clean later
        role_title = subject
        job_text = snippet

        # Check if we already have this role_title + applied_date
        dup_mask = (df["role_title"] == role_title) & (df["applied_date"] == applied_date)
        if dup_mask.any():
            continue  # already recorded

        row = {
            "company": company,
            "role_title": role_title,
            "job_link": "",
            "applied_date": applied_date,
            "status": "Applied",
            "job_text": job_text,
            "summary": "",
            "skills": "",
            "salary": "",
        }
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)

    return df


def scan_rejections(service, df: pd.DataFrame) -> pd.DataFrame:
    """
    Find rejection emails and mark matching jobs as Rejected
    (or add new rows if we can't match).
    """
    print("Scanning for rejection emails...")

    query = (
        '("regret to inform you" OR "decided not to move forward" OR '
        '"unfortunately we will not be moving forward" OR '
        '"after careful consideration, we have decided") newer_than:365d'
    )

    messages = gmail_search(service, query)
    print(f"Found {len(messages)} potential rejection emails.")

    for msg_meta in messages:
        msg = service.users().messages().get(
            userId="me",
            id=msg_meta["id"],
            format="metadata",
            metadataHeaders=["From", "Subject", "Date"],
        ).execute()

        headers = msg.get("payload", {}).get("headers", [])
        subject = get_header(headers, "Subject")
        from_header = get_header(headers, "From")
        date_header = get_header(headers, "Date")
        snippet = msg.get("snippet", "")

        rejection_date = parse_date(date_header)

        # Try to match by exact subject (most ATS keep same subject in thread)
        mask = df["role_title"] == subject

        if mask.any():
            df.loc[mask, "status"] = "Rejected"
            # Optionally append the rejection snippet to job_text
            df.loc[mask, "job_text"] = (
                df.loc[mask, "job_text"].fillna("").astype(str) + "\n[Rejection snippet] " + snippet
            )
        else:
            # If we can't find a match, add a new row
            row = {
                "company": from_header,
                "role_title": subject,
                "job_link": "",
                "applied_date": rejection_date,
                "status": "Rejected",
                "job_text": snippet,
                "summary": "",
                "skills": "",
                "salary": "",
            }
            df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)

    return df


def main():
    parser = argparse.ArgumentParser(description="Sync job applications from Gmail into jobs.csv")
    parser.add_argument(
        "mode",
        choices=["scan-confirmations", "scan-rejections", "scan-all"],
        help="What to scan: confirmations, rejections, or both.",
    )
    args = parser.parse_args()

    service = get_gmail_service()
    df = load_jobs_df()

    if args.mode in ("scan-confirmations", "scan-all"):
        df = scan_confirmations(service, df)

    if args.mode in ("scan-rejections", "scan-all"):
        df = scan_rejections(service, df)

    save_jobs_df(df)


if __name__ == "__main__":
    main()

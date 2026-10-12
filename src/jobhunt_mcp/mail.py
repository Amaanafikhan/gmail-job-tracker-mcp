"""Mail providers: a seeded demo inbox and a read-only Gmail reader."""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Protocol


@dataclass
class Message:
    id: str
    sender: str
    subject: str
    body: str
    received_on: str  # ISO date


class MailProvider(Protocol):
    def recent_messages(self, days: int) -> list[Message]: ...


class DemoMail:
    """Realistic sample inbox so the project runs (and demos) with no credentials."""

    def recent_messages(self, days: int) -> list[Message]:
        t = date.today()
        d = lambda n: (t - timedelta(days=n)).isoformat()  # noqa: E731
        return [
            Message("demo-1", "Zoho Recruiting <careers@zohocorp.com>",
                    "Interview invitation: Python Developer at Zoho",
                    "Hi, we liked your profile. Could we schedule a call for the technical round this week?", d(0)),
            Message("demo-2", "Freshworks Talent <talent@freshworks.com>",
                    "Your application to Freshworks",
                    "Unfortunately we will not be moving forward with your application at this time.", d(1)),
            Message("demo-3", "Razorpay Hiring <hiring@razorpay.com>",
                    "Online assessment for Backend Engineer",
                    "Please complete the coding test on HackerRank within 3 days.", d(2)),
            Message("demo-4", "Swiggy Jobs <noreply@jobs.swiggy.in>",
                    "Jobs you may like", "10 new jobs match your profile.", d(0)),
        ]


class GmailMail:
    """Read-only Gmail access. Needs the `gmail` extra and a Google OAuth client file.

    Set JOBHUNT_GMAIL_CREDENTIALS (OAuth client json) and optionally
    JOBHUNT_GMAIL_TOKEN (where the cached token is stored).
    """

    SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

    def __init__(self) -> None:
        self._service = None

    def _svc(self):
        if self._service:
            return self._service
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        token_path = Path(os.environ.get("JOBHUNT_GMAIL_TOKEN", Path.home() / ".jobhunt-mcp" / "token.json"))
        creds = Credentials.from_authorized_user_file(token_path, self.SCOPES) if token_path.exists() else None
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                client = os.environ.get("JOBHUNT_GMAIL_CREDENTIALS")
                if not client:
                    raise RuntimeError("Set JOBHUNT_GMAIL_CREDENTIALS to your Google OAuth client json file.")
                creds = InstalledAppFlow.from_client_secrets_file(client, self.SCOPES).run_local_server(port=0)
            token_path.parent.mkdir(parents=True, exist_ok=True)
            token_path.write_text(creds.to_json())
        self._service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        return self._service

    def recent_messages(self, days: int) -> list[Message]:
        svc = self._svc()
        ids = svc.users().messages().list(
            userId="me", q=f"newer_than:{days}d -category:promotions -category:social", maxResults=50
        ).execute().get("messages", [])
        out: list[Message] = []
        for ref in ids:
            m = svc.users().messages().get(userId="me", id=ref["id"], format="full").execute()
            headers = {h["name"].lower(): h["value"] for h in m["payload"].get("headers", [])}
            out.append(Message(
                id=m["id"],
                sender=headers.get("from", ""),
                subject=headers.get("subject", ""),
                body=_body_text(m["payload"]) or m.get("snippet", ""),
                received_on=date.fromtimestamp(int(m["internalDate"]) / 1000).isoformat(),
            ))
        return out


def _body_text(payload: dict) -> str:
    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", "replace")
    for part in payload.get("parts", []) or []:
        text = _body_text(part)
        if text:
            return text
    return ""


def get_provider() -> MailProvider:
    mode = os.environ.get("JOBHUNT_MAIL", "demo").lower()
    return GmailMail() if mode == "gmail" else DemoMail()

"""MCP server exposing the job-application tracker as tools Alexa+ (or any MCP client) can call."""

from __future__ import annotations

import argparse
import os

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from . import db, tracker
from .mail import get_provider

mcp = MCPServer(
    "Job Hunt Assistant",
    instructions=(
        "Tracks the user's job applications. Replies are short sentences meant to be spoken aloud: "
        "read them back as-is. Company names can be partial (e.g. 'Zoho')."
    ),
)

READ = ToolAnnotations(readOnlyHint=True)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False)


@mcp.tool(annotations=WRITE)
def add_application(company: str, role: str = "", source: str = "") -> str:
    """Start tracking a job application. `source` is where you found it (LinkedIn, referral, ...)."""
    with db.connect() as conn:
        return tracker.add_application(conn, company, role, source)


@mcp.tool(annotations=READ)
def list_applications(status: str = "") -> str:
    """Summarise tracked applications, optionally only one status:
    applied, replied, assessment, interview, offer or rejected."""
    with db.connect() as conn:
        return tracker.list_applications(conn, status)


@mcp.tool(annotations=WRITE)
def update_status(company: str, status: str) -> str:
    """Set an application's status: applied, replied, assessment, interview, offer or rejected."""
    with db.connect() as conn:
        return tracker.update_status(conn, company, status)


@mcp.tool(annotations=WRITE)
def add_followup(company: str, when: str, note: str = "") -> str:
    """Schedule a follow-up. `when` is spoken-style: 'Friday', 'tomorrow', 'in 3 days', or '2026-10-30'."""
    with db.connect() as conn:
        return tracker.add_followup(conn, company, when, note)


@mcp.tool(annotations=READ)
def todays_followups() -> str:
    """List follow-ups that are due today or overdue."""
    with db.connect() as conn:
        return tracker.todays_followups(conn)


@mcp.tool(annotations=WRITE)
def complete_followup(company: str) -> str:
    """Mark all open follow-ups for a company as done."""
    with db.connect() as conn:
        return tracker.complete_followup(conn, company)


@mcp.tool(annotations=WRITE)
def check_new_replies(days: int = 7) -> str:
    """Check the inbox for new replies from companies you applied to, and update their status.
    Each reply is announced once."""
    with db.connect() as conn:
        return tracker.check_new_replies(conn, get_provider(), days)


def main() -> None:
    parser = argparse.ArgumentParser(description="Alexa+ Job Hunt Assistant MCP server")
    parser.add_argument("--transport", choices=["stdio", "streamable-http"],
                        default=os.environ.get("JOBHUNT_TRANSPORT", "stdio"))
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    args = parser.parse_args()
    if args.transport == "stdio":
        mcp.run("stdio")
    else:
        mcp.run("streamable-http", host=args.host, port=args.port)


if __name__ == "__main__":
    main()

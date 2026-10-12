# Alexa+ Job Hunt Assistant (MCP server)

An [MCP](https://modelcontextprotocol.io) server that lets an AI assistant such as Alexa+ read and update your job-application tracker by voice:

- "Any new replies from companies?"
- "Add a follow-up for the Zoho application on Friday."
- "What follow-ups do I have today?"

Every tool returns a short, natural sentence meant to be read aloud, for example *"You have 2 new replies. Zoho wants to set up an interview and Razorpay sent an assessment."*

## Tools

| Tool | What it does |
|---|---|
| `add_application(company, role?, source?)` | Start tracking an application |
| `list_applications(status?)` | Spoken summary, optionally for one status |
| `update_status(company, status)` | `applied`, `replied`, `assessment`, `interview`, `offer`, `rejected` |
| `add_followup(company, when, note?)` | `when` accepts "Friday", "tomorrow", "in 3 days", "30 October", `2026-10-30` |
| `todays_followups()` | Follow-ups due today or overdue |
| `complete_followup(company)` | Mark a company's follow-ups done |
| `check_new_replies(days?)` | Scan the inbox, match mail to applications, classify (interview / assessment / offer / rejection / other), update status, announce each reply once |

Company names can be partial ("zoho" finds "Zoho Corp"). A reply only moves an application forward; offers and rejections are never overwritten by later mail. Job-board and no-reply mail is ignored.

## Run it

Requires Python 3.10+ and the `mcp` 2.x SDK.

```bash
pip install -e ".[dev]"
pytest

# stdio (local MCP clients, e.g. Claude Desktop / Claude Code)
jobhunt-mcp

# Streamable HTTP at http://127.0.0.1:8000/mcp (for a hosted/remote client)
jobhunt-mcp --transport streamable-http --port 8000
```

### Mail source

- **Demo (default):** `JOBHUNT_MAIL=demo` uses a built-in sample inbox, so everything runs without credentials. Add Zoho, Freshworks or Razorpay and call `check_new_replies`.
- **Gmail:** `pip install -e ".[gmail]"`, then set `JOBHUNT_MAIL=gmail` and `JOBHUNT_GMAIL_CREDENTIALS=/path/to/oauth_client.json` (a Google Cloud "Desktop app" OAuth client). The first call opens a browser for consent. The scope is **read-only** (`gmail.readonly`) and the token is cached in `~/.jobhunt-mcp/token.json`.

Data lives in SQLite at `~/.jobhunt-mcp/tracker.db` (override with `JOBHUNT_DB`).

### Docker

```bash
docker build -t jobhunt-mcp .
docker run -p 8000:8000 -v jobhunt-data:/data jobhunt-mcp
```

## Status and known gaps

- The tracker logic, date parsing, reply classification and both transports (stdio and Streamable HTTP) are tested.
- **Not yet done:** connecting this server to an actual Alexa+ device or the Alexa+ developer tooling, and authentication on the HTTP endpoint. Do not expose the HTTP transport to the internet without adding auth (the SDK supports an `auth` setting).
- The Gmail provider is written against the Gmail API but has only been exercised with the demo inbox so far.
- Reply classification is keyword-based, so unusual wording falls back to "replied".

## License

MIT

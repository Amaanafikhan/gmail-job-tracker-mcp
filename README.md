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

# Streamable HTTP (MCP spec 2025-11-25): MCP endpoint at /mcp, demo page at /
jobhunt-mcp --transport streamable-http --port 8000
# then open http://127.0.0.1:8000/

# stdio (local MCP clients, e.g. Claude Desktop / Claude Code)
jobhunt-mcp
```

### The simulated Alexa+ page

Open `http://127.0.0.1:8000/` for a voice-style assistant UI. The page is a real MCP client: it performs the `initialize` handshake (protocol `2025-11-25`), lists the tools, and calls them over Streamable HTTP. The **MCP trace** panel shows every request and result. Type or tap a sample phrase, or use the mic button in browsers that support speech recognition; replies can be read aloud.

Intent matching on that page is a small set of rules standing in for Alexa+'s language model. Alexa+ itself decides which tool to call from the tool descriptions and schemas, which are in `server.py`.

### Mail source

- **Demo (default):** `JOBHUNT_MAIL=demo` uses a built-in sample inbox, so everything runs without credentials. Add Zoho, Freshworks or Razorpay and call `check_new_replies`.
- **Gmail:** `pip install -e ".[gmail]"`, then save your Google Cloud "Desktop app" OAuth client file as `~/.jobhunt-mcp/credentials.json` (or point `JOBHUNT_GMAIL_CREDENTIALS` at it), run `jobhunt-auth` once to sign in, then set `JOBHUNT_MAIL=gmail`. The scope is **read-only** (`gmail.readonly`) and the token is cached in `~/.jobhunt-mcp/token.json`.

Data lives in SQLite at `~/.jobhunt-mcp/tracker.db` (override with `JOBHUNT_DB`).

### Docker

```bash
docker build -t jobhunt-mcp .
docker run -p 8000:8000 -v jobhunt-data:/data jobhunt-mcp
```

## Status and known gaps

- Tested: tracker logic, date parsing, reply classification, the HTTP routes, the `2025-11-25` handshake, and the web client driven end to end in headless Chromium against the demo inbox.
- **Real Alexa+ is not connected.** The hackathon FAQ says the Alexa+ developer tools (MCP Toolkit, CLI, Web Simulator) are limited to select partners, so this project demonstrates the MCP server through the web client above instead. If you have access, the server is a standard Streamable HTTP MCP server; Alexa+ additionally requires a public HTTPS URL and OAuth 2.x, neither of which is implemented here.
- No authentication on the HTTP endpoint. The SDK's DNS-rebinding protection only allows `localhost` hosts by default, so a hosted deployment must configure allowed hosts and add auth.
- Gmail reading works against a real account in a manual test (50 messages fetched) but the matching rules have not been tuned on real mail. Classification is keyword-based, so unusual wording falls back to "replied".
- Friction notes for the hackathon are in `docs/friction-log.md`.

## License

MIT

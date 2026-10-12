"""The Streamable HTTP app: web client routes and the MCP spec version Alexa+ requires."""

import pytest
from starlette.testclient import TestClient

from jobhunt_mcp.server import mcp

HEADERS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}


@pytest.fixture
def client():
    with TestClient(mcp.streamable_http_app(), base_url="http://localhost:8000") as c:
        yield c


def test_web_client_and_health(client):
    page = client.get("/")
    assert page.status_code == 200 and "Job Hunt Assistant" in page.text
    assert client.get("/health").text == "ok"
    assert client.get("/favicon.ico").status_code == 204


def test_negotiates_mcp_2025_11_25_over_streamable_http(client):
    r = client.post("/mcp", headers=HEADERS, json={
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-11-25", "capabilities": {},
                   "clientInfo": {"name": "test", "version": "1"}},
    })
    assert r.status_code == 200
    assert '"protocolVersion":"2025-11-25"' in r.text

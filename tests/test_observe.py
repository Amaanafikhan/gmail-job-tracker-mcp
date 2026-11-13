import asyncio
import json

from jobhunt_mcp import observe
from jobhunt_mcp.evaluate import DEFAULT_CASES, load_cases, run


def test_observed_logs_success_soft_fail_and_error(tmp_path, monkeypatch):
    log = tmp_path / "calls.jsonl"
    monkeypatch.setenv("JOBHUNT_LOG", str(log))

    @observe.observed
    def greet(name: str) -> str:
        if name == "boom":
            raise ValueError("bad name")
        if not name:
            return "Which company did you apply to?"
        return f"Hi {name}"

    assert greet(name="Zoho") == "Hi Zoho"
    assert greet(name="").startswith("Which company")
    try:
        greet(name="boom")
    except ValueError:
        pass

    rows = observe.read_log(log)
    assert [r["tool"] for r in rows] == ["greet"] * 3
    assert rows[0]["ok"] and not rows[0]["soft_fail"] and rows[0]["args"] == {"name": "Zoho"}
    assert rows[1]["ok"] and rows[1]["soft_fail"]
    assert not rows[2]["ok"] and "bad name" in rows[2]["error"]
    report = observe.summarise(rows)
    assert "greet" in report and "Recent errors" in report and "soft fails" in report



def test_logging_off_and_signature_kept(tmp_path, monkeypatch):
    monkeypatch.setenv("JOBHUNT_LOG", "off")

    @observe.observed
    def f(company: str, days: int = 7) -> str:
        return "ok"

    import inspect
    assert list(inspect.signature(f).parameters) == ["company", "days"]
    assert f(company="x") == "ok"
    assert not list(tmp_path.iterdir())


def test_server_tools_are_logged(tmp_path, monkeypatch):
    log = tmp_path / "calls.jsonl"
    monkeypatch.setenv("JOBHUNT_LOG", str(log))
    monkeypatch.setenv("JOBHUNT_DB", str(tmp_path / "t.db"))
    from jobhunt_mcp.server import mcp

    asyncio.run(mcp.call_tool("add_application", {"company": "Zoho"}))
    rows = [json.loads(line) for line in log.read_text().splitlines()]
    assert rows[-1]["tool"] == "add_application" and rows[-1]["args"] == {"company": "Zoho", "role": "", "source": ""}


def test_eval_runs_on_bundled_cases():
    res = run(load_cases(DEFAULT_CASES))
    assert res["total"] >= 20
    assert 0 < res["accuracy"] <= 1
    # Known weak spots the eval exists to catch; update when the rules improve.
    assert "interview-rescheduled" in {m["id"] for m in res["misses"]}

"""Web API tests. TestClient runs the real app in-process."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest
from fastapi.testclient import TestClient

from curat0r.web.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_sources_lists_every_registered_source(client):
    sources = client.get("/api/sources").json()
    keys = {s["key"] for s in sources}
    assert {"github", "kaggle", "linkedin", "indeed", "glassdoor", "resume"} <= keys


def test_only_sanctioned_sources_are_auto_fetchable(client):
    auto = {s["key"] for s in client.get("/api/sources").json() if s["auto_fetchable"]}
    assert auto == {"github", "kaggle"}


def test_github_url_is_accepted(client):
    r = client.post("/api/ingest/check", json={"url": "https://github.com/WeedenAndrew"})
    assert r.status_code == 200
    assert r.json()["owner"] == "WeedenAndrew"


def test_scraping_prohibited_source_returns_451(client):
    """451 Unavailable For Legal Reasons — the refusal is legal, not technical."""
    r = client.post("/api/ingest/check", json={"url": "https://linkedin.com/in/x"})
    assert r.status_code == 451
    assert "export" in r.json()["detail"].casefold()


def test_unknown_host_is_404(client):
    r = client.post("/api/ingest/check", json={"url": "https://example.com/x"})
    assert r.status_code == 404


def test_short_posting_rejected_by_validation(client):
    r = client.post("/api/curate", json={"blocks": [{"id": "a"}], "posting": "too short"})
    assert r.status_code == 422


def test_health_reports_engine_state(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["engine"] in {"available", "missing"}


def test_index_page_served(client):
    r = client.get("/")
    assert r.status_code == 200 and "Curat" in r.text

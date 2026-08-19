"""The ingestion guard. Nothing gets fetched that we lack permission to fetch."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from curat0r.errors import IngestNotPermitted, UnknownSource
from curat0r.sources import (
    IngestMethod,
    identify,
    parse_github,
    require_auto_fetchable,
)

# ── Only GitHub may be fetched ───────────────────────────────────────────────

def test_github_is_auto_fetchable():
    source = require_auto_fetchable("https://github.com/WeedenAndrew")
    assert source.key == "github"
    assert source.method is IngestMethod.API


@pytest.mark.parametrize(
    "url",
    [
        "https://www.linkedin.com/in/someone",
        "https://www.indeed.com/viewjob?jk=abc",
        "https://www.glassdoor.com/job-listing/x",
    ],
)
def test_scraping_prohibited_sources_are_refused(url):
    with pytest.raises(IngestNotPermitted) as exc:
        require_auto_fetchable(url)
    # The refusal must tell the user what to do instead, not just say no.
    assert exc.value.guidance
    assert len(exc.value.guidance) > 20


def test_linkedin_routes_to_self_export():
    assert identify("https://linkedin.com/in/x").method is IngestMethod.USER_EXPORT


def test_job_boards_route_to_paste():
    for url in ("https://indeed.com/viewjob", "https://glassdoor.com/j/1"):
        assert identify(url).method is IngestMethod.USER_PASTED


# ── Unknown hosts are refused rather than guessed at ─────────────────────────

def test_unknown_host_is_refused():
    with pytest.raises(UnknownSource, match="not a supported source"):
        identify("https://example.com/jobs/1")


def test_non_http_url_is_refused():
    for url in ("file:///etc/passwd", "javascript:alert(1)", "not a url"):
        with pytest.raises(UnknownSource):
            identify(url)


def test_lookalike_host_does_not_match():
    """github.com.evil.test must not be treated as GitHub."""
    with pytest.raises(UnknownSource):
        identify("https://github.com.evil.test/WeedenAndrew")


def test_subdomain_of_supported_host_matches():
    assert identify("https://gist.github.com/x").key == "github"


# ── GitHub URL parsing ───────────────────────────────────────────────────────

def test_profile_url():
    target = parse_github("https://github.com/WeedenAndrew")
    assert target.owner == "WeedenAndrew" and target.is_profile


def test_repo_url():
    target = parse_github("https://github.com/WeedenAndrew/auto_Interner")
    assert (target.owner, target.repo) == ("WeedenAndrew", "auto_Interner")
    assert not target.is_profile


def test_git_suffix_stripped():
    assert parse_github("https://github.com/a/b.git").repo == "b"


def test_deep_path_is_ambiguous_and_refused():
    with pytest.raises(UnknownSource, match="profile or repository"):
        parse_github("https://github.com/a/b/blob/main/README.md")


def test_parse_github_still_enforces_the_guard():
    """Parsing must not be a way around require_auto_fetchable."""
    with pytest.raises(IngestNotPermitted):
        parse_github("https://linkedin.com/in/x")


# ── Newly registered sources ─────────────────────────────────────────────────

def test_kaggle_is_auto_fetchable():
    """Kaggle publishes an official public API, so fetching is sanctioned."""
    from curat0r.sources import IngestMethod, require_auto_fetchable
    assert require_auto_fetchable("https://kaggle.com/someone").method is IngestMethod.API


def test_base_resume_has_no_host_and_is_reached_by_key():
    from curat0r.sources import IngestMethod, by_key
    source = by_key("resume")
    assert source.method is IngestMethod.LOCAL_FILE
    assert source.hosts == ()
    assert not source.method.may_auto_fetch


def test_unknown_key_is_refused():
    from curat0r.errors import UnknownSource
    from curat0r.sources import by_key
    with pytest.raises(UnknownSource, match="no source registered"):
        by_key("monster")


def test_every_registered_source_explains_itself():
    """A refusal without guidance is a dead end for the user."""
    from curat0r.sources import REGISTRY
    for source in REGISTRY:
        assert len(source.guidance) > 20, source.key


# ── what each source contributes ─────────────────────────────────────────────

def test_work_history_and_projects_come_from_different_sources():
    """A repository is not a job. Treating one pool as both makes a corpus
    where GitHub competes with employment for the same resume slot."""
    from curat0r.sources import Contributes, sources_for
    projects = {s.key for s in sources_for(Contributes.PROJECTS)}
    work = {s.key for s in sources_for(Contributes.WORK_HISTORY)}
    assert "github" in projects and "kaggle" in projects
    assert "linkedin" in work and "indeed-profile" in work
    assert "github" not in work, "GitHub cannot supply employment dates"


def test_every_material_kind_has_at_least_one_source():
    from curat0r.sources import Contributes, coverage_gaps
    gaps = coverage_gaps()
    for kind in Contributes:
        assert gaps[kind.value], f"nothing can supply {kind.value}"


def test_indeed_profile_is_an_export_not_a_scrape():
    """Indeed prohibits scraping and a user's own profile is no exception."""
    from curat0r.sources import IngestMethod, by_key
    source = by_key("indeed-profile")
    assert source.method is IngestMethod.USER_EXPORT
    assert not source.method.may_auto_fetch
    assert "Download" in source.guidance


def test_only_sanctioned_apis_remain_auto_fetchable():
    from curat0r.sources import REGISTRY
    auto = {s.key for s in REGISTRY if s.method.may_auto_fetch}
    assert auto == {"github", "kaggle"}

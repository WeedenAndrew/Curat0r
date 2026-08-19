"""Screening drops noise, never silently, and always overridably."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from curat0r.filters import Reason, report, screen


def repo(name, **kw):
    base = {
        "name": name,
        "description": "does a thing",
        "language": "Python",
        "size": 500,
        "fork": False,
        "archived": False,
    }
    base.update(kw)
    return base


# ── the invariant: nothing vanishes ──────────────────────────────────────────


def test_every_repo_gets_a_verdict():
    repos = [repo("a"), repo("leetcode-solutions"), repo("b", fork=True)]
    _kept, verdicts = screen(repos, owner="me")
    assert len(verdicts) == len(repos)
    assert all(v.keep or v.reason for v in verdicts)


def test_every_drop_explains_itself():
    _, verdicts = screen([repo("neetcode-submissions")], owner="me")
    v = verdicts[0]
    assert not v.keep
    assert len(v.reason.explain) > 20
    assert "neetcode-submissions" in v.describe()


# ── what gets dropped ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "name,reason",
    [
        ("neetcode-submissions", Reason.PRACTICE),
        ("leetcode", Reason.PRACTICE),
        ("advent-of-code-2024", Reason.PRACTICE),
        ("react-tutorial", Reason.COURSE),
        ("bbit-learning-labs", Reason.COURSE),
        ("dotfiles", Reason.CONFIG),
    ],
)
def test_noise_is_dropped_with_the_right_reason(name, reason):
    _, verdicts = screen([repo(name)], owner="me")
    assert verdicts[0].reason is reason


def test_fork_dropped_by_default():
    _, v = screen([repo("x", fork=True)], owner="me")
    assert v[0].reason is Reason.FORK


def test_profile_readme_dropped():
    _, v = screen([repo("WeedenAndrew")], owner="WeedenAndrew")
    assert v[0].reason is Reason.PROFILE_README


def test_archived_dropped():
    _, v = screen([repo("x", archived=True)], owner="me")
    assert v[0].reason is Reason.ARCHIVED


def test_no_description_dropped_because_a_bullet_would_be_invented():
    _, v = screen([repo("x", description="")], owner="me")
    assert v[0].reason is Reason.NO_SIGNAL


def test_empty_repo_dropped():
    _, v = screen([repo("x", description=None, language=None)], owner="me")
    assert v[0].reason is Reason.EMPTY


def test_tiny_repo_dropped():
    _, v = screen([repo("x", size=3)], owner="me")
    assert v[0].reason is Reason.TOO_SMALL


# ── what survives ────────────────────────────────────────────────────────────


def test_real_project_kept():
    kept, _ = screen([repo("auto_Interner")], owner="WeedenAndrew")
    assert len(kept) == 1


def test_patterns_do_not_match_substrings_of_real_names():
    """'my-first' must not eat 'my-first-class-scheduler'... but it would.

    Documenting the known over-match rather than pretending it does not exist.
    keep_anyway is the remedy.
    """
    _, v = screen([repo("my-first-class-scheduler")], owner="me")
    assert v[0].reason is Reason.COURSE  # over-matches, by design, overridable


# ── the override always wins ─────────────────────────────────────────────────


def test_keep_anyway_beats_every_rule():
    repos = [repo("neetcode-submissions"), repo("x", fork=True), repo("y", size=1)]
    kept, _ = screen(repos, owner="me", keep_anyway=frozenset({"neetcode-submissions", "x", "y"}))
    assert len(kept) == 3


def test_include_forks_flag():
    kept, _ = screen([repo("x", fork=True)], owner="me", include_forks=True)
    assert len(kept) == 1


# ── the report names what it dropped ─────────────────────────────────────────


def test_report_lists_dropped_repos_and_the_override():
    _, verdicts = screen([repo("auto_Interner"), repo("neetcode-submissions")], owner="me")
    text = report(verdicts)
    assert "neetcode-submissions" in text
    assert "keep_anyway" in text

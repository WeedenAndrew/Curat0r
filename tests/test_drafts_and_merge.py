"""Drafts are proposals; the corpus belongs to the user."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from curat0r.drafts import drafts_from_repos, to_corpus
from curat0r.merge import merge, verified_only

REPOS = [
    {"name": "auto_Interner", "description": "Internship discovery pipeline",
     "language": "Python", "topics": ["docker"], "pushed_at": "2026-08-07T00:00:00Z",
     "size": 900, "stargazers_count": 3, "fork": False},
    {"name": "Goblin-Flip", "description": "A fantasy coin-flip game",
     "language": "Dart", "topics": [], "pushed_at": "2026-08-08T00:00:00Z",
     "size": 400, "stargazers_count": 0, "fork": False},
    {"name": "somebody-elses", "description": "forked", "language": "Go",
     "pushed_at": "2026-01-01T00:00:00Z", "size": 10, "fork": True},
]


# ── Drafts assert only what GitHub asserts ───────────────────────────────────

def test_forks_excluded_by_default():
    assert {d.title for d in drafts_from_repos(REPOS)} == {"auto_Interner", "Goblin-Flip"}


def test_everything_starts_unverified():
    assert all(not d.verified for d in drafts_from_repos(REPOS))


def test_language_maps_to_a_corpus_tag():
    by_title = {d.title: d for d in drafts_from_repos(REPOS)}
    assert "python" in by_title["auto_Interner"].tags
    assert "docker" in by_title["auto_Interner"].tags
    assert "dart" in by_title["Goblin-Flip"].tags


def test_bullets_do_not_embellish():
    """No invented seniority, scale, or impact."""
    draft = next(d for d in drafts_from_repos(REPOS) if d.title == "auto_Interner")
    blob = " ".join(draft.bullets).casefold()
    for word in ("architected", "scalable", "led", "optimized", "robust", "expert"):
        assert word not in blob


def test_low_star_count_is_not_advertised():
    draft = next(d for d in drafts_from_repos(REPOS) if d.title == "auto_Interner")
    assert "3 stars" not in " ".join(draft.bullets)


def test_emitted_shape_matches_the_engine_schema():
    corpus = to_corpus(drafts_from_repos(REPOS))
    block = corpus["blocks"][0]
    assert {"id", "kind", "title", "tags", "bullets", "recency"} <= set(block)
    assert isinstance(block["bullets"][0], dict) and "text" in block["bullets"][0]


# ── Merge protects what the user owns ────────────────────────────────────────

def test_new_blocks_are_added():
    result = merge([], [{"id": "gh-a", "title": "A"}])
    assert result.added == ("gh-a",)


def test_verified_block_is_never_overwritten():
    existing = [{"id": "gh-a", "title": "My careful title", "_verified": True}]
    incoming = [{"id": "gh-a", "title": "auto_Interner"}]
    result = merge(existing, incoming)

    assert result.protected == ("gh-a",)
    kept = next(b for b in result.blocks if b["id"] == "gh-a")
    assert kept["title"] == "My careful title"
    assert result.pending[0]["proposed"]["title"] == "auto_Interner"


def test_edited_but_unverified_block_is_also_protected():
    existing = [{"id": "gh-a", "title": "Mine", "_edited": True}]
    result = merge(existing, [{"id": "gh-a", "title": "Theirs"}])
    assert result.protected == ("gh-a",)
    assert next(b for b in result.blocks if b["id"] == "gh-a")["title"] == "Mine"


def test_untouched_draft_refreshes():
    existing = [{"id": "gh-a", "title": "old", "_verified": False}]
    result = merge(existing, [{"id": "gh-a", "title": "new"}])
    assert result.refreshed == ("gh-a",)
    assert next(b for b in result.blocks if b["id"] == "gh-a")["title"] == "new"


def test_refresh_cannot_resurrect_a_verified_flag():
    existing = [{"id": "gh-a", "title": "old", "_verified": False}]
    result = merge(existing, [{"id": "gh-a", "title": "new", "_verified": True}])
    assert next(b for b in result.blocks if b["id"] == "gh-a")["_verified"] is False


def test_identical_incoming_is_a_noop():
    existing = [{"id": "gh-a", "title": "same", "_verified": True}]
    result = merge(existing, [{"id": "gh-a", "title": "same"}])
    assert not result.added and not result.refreshed and not result.protected


def test_engine_only_sees_verified_blocks():
    blocks = [{"id": "a", "_verified": True}, {"id": "b", "_verified": False}, {"id": "c"}]
    assert [b["id"] for b in verified_only(blocks)] == ["a"]


# ── the same project from two sources ────────────────────────────────────────

def test_same_project_from_resume_and_github_collapses():
    """`Auto Interner` and `auto_Interner` are one project, not two."""
    from curat0r.merge import dedupe_across_sources
    blocks = [
        {"id": "r1", "title": "Auto Interner",
         "bullets": [{"text": "Built an automated internship pipeline using Git snapshots."},
                     {"text": "Prepared a Raspberry Pi 4B deployment."}]},
        {"id": "gh", "title": "auto_Interner", "_source": "github",
         "bullets": [{"text": "Automatic Internship application pipeline."}]},
    ]
    kept, dropped = dedupe_across_sources(blocks)
    assert len(kept) == 1
    assert kept[0]["id"] == "r1", "the richer block wins"
    assert "github" in dropped[0]


def test_dedupe_keeps_genuinely_different_projects():
    from curat0r.merge import dedupe_across_sources
    blocks = [
        {"id": "a", "title": "Goblin Flip", "bullets": [{"text": "a game"}]},
        {"id": "b", "title": "Fantasy Blackjack", "bullets": [{"text": "another game"}]},
    ]
    kept, dropped = dedupe_across_sources(blocks)
    assert len(kept) == 2 and not dropped


def test_dedupe_preserves_order():
    from curat0r.merge import dedupe_across_sources
    blocks = [{"id": str(i), "title": f"P{i}", "bullets": [{"text": "x"}]} for i in range(4)]
    kept, _ = dedupe_across_sources(blocks)
    assert [b["id"] for b in kept] == ["0", "1", "2", "3"]

"""Adjacency ranks and explains. It must never satisfy a requirement."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from curat0r.adjacency import DEFAULT, GraphAdjacency, affinity, nearest

CORPUS_TAGS = {
    "rabbitmq": ("gh-pipeline",),
    "postgresql": ("gh-pipeline",),
    "python": ("gh-pipeline", "gh-interner"),
    "css": ("gh-site",),
    "unit testing": ("gh-interner",),
}


# ── THE invariant ────────────────────────────────────────────────────────────

def test_adjacency_never_reports_an_exact_match_as_near():
    """A near match for something you actually have would imply it's a gap."""
    assert nearest("postgresql", CORPUS_TAGS) is None
    assert nearest("python", CORPUS_TAGS) is None


def test_near_match_names_the_requirement_as_still_unmet():
    match = nearest("kafka", CORPUS_TAGS)
    assert match is not None
    assert match.requirement == "kafka"     # still the thing you lack
    assert match.have == "rabbitmq"
    assert "no kafka" in match.describe()   # phrased as a gap, not a match


def test_at_most_one_near_match_is_returned():
    """Six vaguely-related technologies is noise, and noise flatters."""
    match = nearest("mysql", CORPUS_TAGS)
    assert match is not None and match.have == "postgresql"


# ── Curated families ─────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "have,want",
    [("kafka", "rabbitmq"), ("postgresql", "mysql"), ("react", "vue"),
     ("docker", "podman"), ("airflow", "dagster"), ("pytorch", "tensorflow")],
)
def test_family_members_are_adjacent(have, want):
    assert 0.4 < DEFAULT.score(have, want) < 1.0


def test_unrelated_terms_score_zero():
    assert DEFAULT.score("css", "kafka") == 0.0
    assert DEFAULT.score("swift", "postgresql") == 0.0


def test_identity_is_one():
    assert DEFAULT.score("python", "python") == 1.0


def test_normalization_handles_separators_and_case():
    assert DEFAULT.score("Unit_Testing", "unit testing") == 1.0


# ── Lexical fallback, and its false friends ──────────────────────────────────

def test_morphological_variant_matches():
    """The 'unit tests' vs 'unit testing' miss that exact matching had."""
    assert DEFAULT.score("unit testing", "unit tests") > 0.8


def test_java_is_not_javascript():
    """Lexically close, professionally unrelated. The classic false friend."""
    assert DEFAULT.score("java", "javascript") == 0.0


def test_typescript_is_not_javascript_by_spelling():
    assert DEFAULT.score("typescript", "javascript") == 0.0


def test_merely_similar_words_do_not_match():
    assert DEFAULT.score("rust", "react") == 0.0


# ── Affinity is for ordering only ────────────────────────────────────────────

def test_adjacent_block_outranks_unrelated_block():
    """A message-queue project should beat a CSS project for a Kafka role."""
    want = frozenset({"kafka"})
    assert affinity(frozenset({"rabbitmq"}), want) > affinity(frozenset({"css"}), want)


def test_exact_match_outranks_adjacent():
    want = frozenset({"kafka"})
    assert affinity(frozenset({"kafka"}), want) > affinity(frozenset({"rabbitmq"}), want)


def test_affinity_is_zero_without_overlap():
    assert affinity(frozenset({"css"}), frozenset({"kafka"})) == 0.0
    assert affinity(frozenset(), frozenset({"kafka"})) == 0.0


# ── Provider is swappable ────────────────────────────────────────────────────

def test_custom_provider_can_replace_the_graph():
    class AlwaysClose:
        def score(self, have: str, want: str) -> float:
            return 0.0 if have == want else 0.9

    match = nearest("kafka", CORPUS_TAGS, provider=AlwaysClose())
    assert match is not None and match.score == 0.9


def test_empty_family_graph_falls_back_to_lexical():
    bare = GraphAdjacency(families=())
    assert bare.score("kafka", "rabbitmq") == 0.0
    assert bare.score("unit testing", "unit tests") > 0.8


def test_plural_matches_singular_after_the_es_stemming_bug():
    """'es' before 's' stemmed 'pipelines'->'pipelin' while 'pipeline' stayed whole."""
    for singular, plural in [
        ("data pipeline", "data pipelines"),
        ("microservice", "microservices"),
        ("unit test", "unit tests"),
    ]:
        assert DEFAULT.score(singular, plural) > 0.8, (singular, plural)


def test_short_acronyms_are_never_stemmed():
    """Stripping 's' from 'css' or 'aws' would be far worse than missing a plural."""
    assert DEFAULT.score("css", "cs") == 0.0
    assert DEFAULT.score("aws", "aw") == 0.0

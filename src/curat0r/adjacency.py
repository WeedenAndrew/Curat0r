"""How close is a thing you have to a thing they want.

Exact tag matching has two failure modes. It misses trivial variants —
a posting says "unit tests", the corpus says "unit testing", no match. And it
treats every miss as equally distant: a Postgres engineer applying to a MySQL
role reads as having nothing, which is absurd.

**The rule that keeps this honest: adjacency never satisfies a requirement.**

If they want Kafka and you have RabbitMQ, Kafka is still a gap. Adjacency
changes two things and only two:

1. **Ranking.** Among blocks that cover nothing new, the adjacent one is
   surfaced first, so a message-queue project outranks a CSS project for a
   Kafka role.
2. **The gap report.** A gap is annotated with what you have nearby, so you can
   decide — "no Kafka, but you have RabbitMQ" is far more useful than "no
   Kafka", and it is still not a claim that you know Kafka.

Letting similarity close a gap would quietly reintroduce the fabrication this
whole project exists to prevent. It would be one line of code and it is the
single most dangerous line anyone could add here.

Scoring is deterministic and dependency-free: a hand-curated graph for terms
worth being right about, plus lexical similarity for everything else. The
`AdjacencyProvider` protocol lets an embedding backend replace it later without
touching selection or coverage.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

# Curated adjacency. Each frozenset is a family whose members are genuinely
# substitutable knowledge — not "both are databases", but "knowing one makes
# you productive in the other quickly". Being conservative here matters: an
# overbroad family produces flattering, useless advice.
_FAMILIES: tuple[tuple[frozenset[str], float], ...] = (
    (frozenset({"kafka", "rabbitmq", "sqs", "pulsar", "nats"}), 0.70),
    (frozenset({"postgresql", "mysql", "mariadb", "sqlite"}), 0.75),
    (frozenset({"mongodb", "dynamodb", "cassandra", "couchdb"}), 0.65),
    (frozenset({"react", "vue", "svelte", "angular"}), 0.65),
    (frozenset({"aws", "gcp", "azure"}), 0.70),
    (frozenset({"docker", "podman", "containerd"}), 0.80),
    (frozenset({"kubernetes", "nomad", "ecs"}), 0.60),
    (frozenset({"terraform", "pulumi", "cloudformation", "ansible"}), 0.60),
    (frozenset({"prometheus", "grafana", "datadog", "observability"}), 0.60),
    (frozenset({"airflow", "dagster", "prefect", "luigi"}), 0.70),
    (frozenset({"pytest", "unit testing", "junit", "jest", "vitest"}), 0.65),
    (frozenset({"fastapi", "flask", "django", "express"}), 0.60),
    (frozenset({"rest", "graphql", "grpc", "api design"}), 0.55),
    (frozenset({"pandas", "numpy", "polars", "spark", "pyspark"}), 0.60),
    (frozenset({"pytorch", "tensorflow", "jax", "scikit-learn"}), 0.65),
    (frozenset({"flutter", "react native", "swift", "kotlin"}), 0.50),
    (frozenset({"bash", "shell", "linux"}), 0.70),
    (frozenset({"etl", "elt", "data pipeline", "data engineering"}), 0.75),
    (frozenset({"ci/cd", "github actions", "jenkins", "gitlab ci"}), 0.70),
)

_ADJACENT_FLOOR = 0.45  # below this, not worth mentioning at all
_JACCARD_FLOOR = 0.60

# Suffixes stripped to unify morphological variants. Only applied to tokens
# longer than four characters, so "css", "aws", and "ci/cd" survive intact —
# mangling a short acronym is far worse than missing a plural.
#
# "es" is deliberately absent. Including it stemmed "pipelines" to "pipelin"
# while "pipeline" stayed whole, so the plural stopped matching the singular.
# Stripping a single "s" is symmetric and covers the tech vocabulary here.
_SUFFIXES = ("ing", "ed", "s")


class AdjacencyProvider(Protocol):
    """Swap in embeddings later without touching selection or coverage."""

    def score(self, have: str, want: str) -> float: ...


def _normalize(term: str) -> str:
    return " ".join(re.sub(r"[_\-]+", " ", term.casefold()).split())


def _stem(token: str) -> str:
    if len(token) <= 4:
        return token
    for suffix in _SUFFIXES:
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            return token[: -len(suffix)]
    return token


def _tokens(term: str) -> frozenset[str]:
    return frozenset(_stem(t) for t in re.split(r"[^a-z0-9+#./]+", term) if t)


def _lexical(have: str, want: str) -> float:
    """Catch morphological variants: "unit tests" vs "unit testing".

    Token comparison, not character ratio. SequenceMatcher scored that exact
    pair 0.818 — below any threshold that also excluded "java" vs "javascript"
    at 0.857. Ranking a real match below a false friend is not a threshold to
    tune, it is the wrong signal.

    Comparing stemmed tokens separates them cleanly: {unit, test} == {unit,
    test}, while {java} and {javascript} share nothing. It must stay narrow —
    this catches spelling variants of the same skill, never related skills.
    Relatedness is the curated graph's job, where it is explicit and reviewable.
    """
    left, right = _tokens(have), _tokens(want)
    if not left or not right:
        return 0.0
    if left == right:
        return 0.95
    shared = left & right
    if not shared:
        return 0.0
    jaccard = len(shared) / len(left | right)
    if jaccard < _JACCARD_FLOOR:
        return 0.0
    # Cap below an exact-family match: a partial token overlap is weaker
    # evidence than a curated adjacency judgement.
    return min(0.85, jaccard)


class GraphAdjacency:
    """Curated families first, lexical similarity as the fallback."""

    def __init__(self, families=_FAMILIES) -> None:
        self._families = families

    def score(self, have: str, want: str) -> float:
        have, want = _normalize(have), _normalize(want)
        if have == want:
            return 1.0
        best = 0.0
        for members, weight in self._families:
            if have in members and want in members:
                best = max(best, weight)
        return max(best, _lexical(have, want))


DEFAULT = GraphAdjacency()


@dataclass(frozen=True, slots=True)
class NearMatch:
    """Something the corpus has that sits near an unmet requirement."""

    requirement: str
    have: str
    score: float
    block_ids: tuple[str, ...]

    def describe(self) -> str:
        where = ", ".join(self.block_ids)
        return f"no {self.requirement}, but {self.have} ({self.score:.0%} adjacent) in {where}"


def nearest(
    requirement: str,
    corpus_tags: dict[str, tuple[str, ...]],
    provider: AdjacencyProvider = DEFAULT,
    floor: float = _ADJACENT_FLOOR,
) -> NearMatch | None:
    """Closest thing the corpus has to an unmet requirement, or None.

    `corpus_tags` maps a tag to the block ids carrying it. Returns at most one
    match: a gap report listing six vaguely-related technologies is noise, and
    noise is how people start believing the flattering version.
    """
    want = _normalize(requirement)
    best: NearMatch | None = None
    for tag, block_ids in corpus_tags.items():
        score = provider.score(tag, want)
        # An exact match is not a near match — it would mean the caller asked
        # about a requirement that is not actually a gap.
        if score >= 1.0 or score < floor:
            continue
        if best is None or score > best.score:
            best = NearMatch(want, _normalize(tag), score, tuple(sorted(block_ids)))
    return best


def affinity(
    block_tags: frozenset[str],
    requirements: frozenset[str],
    provider: AdjacencyProvider = DEFAULT,
) -> float:
    """How relevant a block is to a posting, counting adjacency.

    Used only to ORDER blocks competing for leftover page space. It cannot mark
    a requirement covered — `selection.py` still credits coverage on exact tag
    match alone.
    """
    if not block_tags or not requirements:
        return 0.0
    return sum(
        max((provider.score(tag, want) for tag in block_tags), default=0.0)
        for want in requirements
    )

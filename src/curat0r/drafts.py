"""Turning fetched data into DRAFT corpus blocks.

Ingestion produces drafts, never verified claims. That distinction carries the
whole product: the selection engine downstream is only truthful because every
block was confirmed by the person it describes. A repository description is
written by past-you at 2am and is not evidence of anything until present-you
agrees it is.

So every block here starts `verified: false`, and the emitted corpus is exactly
the JSON schema `auto_interner.corpus` already reads. The two projects share a
FORMAT, not a dependency — same arrangement as the blackjack rule vectors.
Curat0r can be rewritten in another language without touching the engine.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, Protocol

# Language/topic -> canonical corpus tag. Deliberately small: a wrong tag is
# worse than a missing one, because it makes the gap report lie.
#
# Two vocabularies feed this. GitHub's `language` field uses proper names
# ("Dockerfile", "Shell"); its `topics` use plain lowercase slugs ("docker",
# "bash"). Mapping only the first silently dropped every topic — which is half
# the signal, and the half the user chose deliberately.
_TAG_ALIASES = {
    # languages (from repo.language)
    "c#": "c#",
    "c++": "c++",
    "css": "css",
    "dart": "dart",
    "dockerfile": "docker",
    "go": "go",
    "hcl": "terraform",
    "html": "html",
    "java": "java",
    "javascript": "javascript",
    "jupyter notebook": "python",
    "kotlin": "kotlin",
    "lua": "lua",
    "luau": "lua",
    "php": "php",
    "python": "python",
    "ruby": "ruby",
    "rust": "rust",
    "shell": "bash",
    "sql": "sql",
    "swift": "swift",
    "typescript": "typescript",
    "vue": "vue",
    # topics (from repo.topics)
    "airflow": "airflow",
    "ansible": "ansible",
    "api": "api design",
    "aws": "aws",
    "azure": "azure",
    "bash": "bash",
    "ci-cd": "ci/cd",
    "django": "django",
    "docker": "docker",
    "elasticsearch": "elasticsearch",
    "etl": "etl",
    "fastapi": "fastapi",
    "flask": "flask",
    "flutter": "flutter",
    "gcp": "gcp",
    "graphql": "graphql",
    "grpc": "grpc",
    "kafka": "kafka",
    "kubernetes": "kubernetes",
    "linux": "linux",
    "microservices": "microservices",
    "mongodb": "mongodb",
    "mysql": "mysql",
    "nodejs": "node.js",
    "node-js": "node.js",
    "pandas": "pandas",
    "postgres": "postgresql",
    "postgresql": "postgresql",
    "pytest": "pytest",
    "pytorch": "pytorch",
    "react": "react",
    "redis": "redis",
    "rest-api": "rest",
    "spark": "spark",
    "sqlalchemy": "sqlalchemy",
    "tensorflow": "tensorflow",
    "terraform": "terraform",
    "testing": "unit testing",
    "websocket": "webhooks",
}


class RepoFetcher(Protocol):
    """Injected boundary so tests never touch the network."""

    def list_repos(self, owner: str) -> list[dict[str, Any]]: ...


@dataclass(frozen=True, slots=True)
class DraftBlock:
    """A proposed corpus block awaiting human verification."""

    id: str
    kind: str
    title: str
    org: str = ""
    dates: str = ""
    bullets: tuple[str, ...] = ()
    tags: frozenset[str] = field(default_factory=frozenset)
    recency: int = 0
    source: str = ""
    verified: bool = False

    def to_corpus_json(self) -> dict[str, Any]:
        """Emit the schema auto_interner.corpus.load_corpus already accepts."""
        return {
            "id": self.id,
            "kind": self.kind,
            "title": self.title,
            "org": self.org,
            "dates": self.dates,
            "tags": sorted(self.tags),
            "recency": self.recency,
            "bullets": [{"text": b, "tags": sorted(self.tags)} for b in self.bullets],
            "_source": self.source,
            "_verified": self.verified,
        }


def _tags_for(repo: dict[str, Any]) -> frozenset[str]:
    raw: list[str] = []
    if language := repo.get("language"):
        raw.append(str(language))
    raw.extend(str(t) for t in repo.get("topics", []) or [])
    return frozenset(
        _TAG_ALIASES[key] for key in (r.strip().casefold() for r in raw) if key in _TAG_ALIASES
    )


def _bullets_for(repo: dict[str, Any]) -> tuple[str, ...]:
    """Only facts GitHub actually asserts. Nothing is inferred or embellished.

    No "architected a scalable system" from a repo with four commits. The user
    writes the real bullets; these exist so the block is not empty while they do.
    """
    bullets: list[str] = []
    if description := (repo.get("description") or "").strip():
        bullets.append(description.rstrip(".") + ".")
    if language := repo.get("language"):
        stars = repo.get("stargazers_count") or 0
        line = f"Written primarily in {language}"
        if stars >= 10:
            line += f"; {stars} stars on GitHub"
        bullets.append(line + ".")
    return tuple(bullets)


def drafts_from_repos(
    repos: Iterable[dict[str, Any]],
    *,
    owner: str = "",
    include_forks: bool = False,
    min_size_kb: int = 20,
    keep_anyway: frozenset[str] = frozenset(),
    screened: bool = True,
) -> list[DraftBlock]:
    """Convert GitHub repo payloads into draft project blocks.

    Screening runs first by default - see `filters.py`. Practice dumps, course
    forks and profile READMEs are real work but they dilute the two or three
    repositories a reader is actually assessing.

    Pass `screened=False` for the raw list, or `keep_anyway={'name'}` to force
    one back in. Nothing is dropped without a reason attached.
    """
    if screened:
        from curat0r.filters import screen

        repos, _ = screen(
            repos,
            owner,
            keep_anyway=keep_anyway,
            include_forks=include_forks,
            min_size_kb=min_size_kb,
        )

    drafts: list[DraftBlock] = []
    for repo in repos:
        name = repo.get("name")
        if not name:
            continue
        pushed = str(repo.get("pushed_at") or repo.get("updated_at") or "")
        drafts.append(
            DraftBlock(
                id=f"gh-{name}".casefold(),
                kind="project",
                title=str(name),
                dates=pushed[:4],
                bullets=_bullets_for(repo),
                tags=_tags_for(repo),
                recency=int(pushed[:4]) if pushed[:4].isdigit() else 0,
                source="github",
            )
        )
    drafts.sort(key=lambda d: (-d.recency, d.id))
    return drafts


def to_corpus(drafts: Iterable[DraftBlock]) -> dict[str, Any]:
    return {
        "$comment": (
            "Drafts from Curat0r. Every block is _verified: false until you "
            "confirm it. The selection engine ignores unverified blocks."
        ),
        "blocks": [d.to_corpus_json() for d in drafts],
    }

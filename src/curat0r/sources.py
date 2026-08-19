"""Which sources may be fetched, and how.

This is the Phase 0 guard, and it exists before any fetching code so there is
never a window where automated retrieval is possible and refusal is not.

The rule the product depends on: **the tool never fetches a page it has not
been given permission to fetch.** GitHub publishes a public REST API and
sanctions programmatic access. LinkedIn, Indeed, and Glassdoor prohibit
scraping in their terms of service, and LinkedIn has litigated the point. So
those sources are still supported — the user brings the data instead:

* LinkedIn ships a self-service data export. A user downloading their own
  archive is unambiguously permitted, and it contains richer, cleaner history
  than any scrape would.
* Indeed and Glassdoor postings are pasted in. Which costs the user one
  keystroke and removes the entire legal surface.

Framed correctly this is not a limitation. A product built on scraping is one
ToS enforcement away from dead; this one is not.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlparse

from curat0r.errors import IngestNotPermitted, UnknownSource


class IngestMethod(StrEnum):
    """How data from a source may legitimately be obtained."""

    API = "api"  # sanctioned public API — safe to fetch
    USER_EXPORT = "user_export"  # user downloads their own archive and uploads it
    USER_PASTED = "user_pasted"  # user pastes the content
    LOCAL_FILE = "local_file"  # user hands us a file off their own disk

    @property
    def may_auto_fetch(self) -> bool:
        """Only a sanctioned API is fetched. Everything else the user brings.

        LOCAL_FILE is not a fetch at all, so it is false here — but it needs no
        permission either, which is why it has no host and is reached by key.
        """
        return self is IngestMethod.API


class Contributes(StrEnum):
    """What a source can supply. Work history and projects are not the same.

    LinkedIn and Indeed know where you worked and for how long. GitHub and
    Kaggle know what you built. Treating them as one pool produces a corpus
    where a repository competes with a job for the same slot.
    """

    WORK_HISTORY = "work_history"
    PROJECTS = "projects"
    EDUCATION = "education"
    POSTINGS = "postings"


@dataclass(frozen=True, slots=True)
class Source:
    key: str
    label: str
    method: IngestMethod
    hosts: tuple[str, ...]
    guidance: str
    contributes: frozenset[Contributes] = frozenset()

    def matches(self, host: str) -> bool:
        host = host.casefold().removeprefix("www.")
        return any(host == h or host.endswith(f".{h}") for h in self.hosts)


REGISTRY: tuple[Source, ...] = (
    Source(
        key="github",
        label="GitHub",
        method=IngestMethod.API,
        hosts=("github.com",),
        guidance="Fetched via the public GitHub REST API.",
        contributes=frozenset({Contributes.PROJECTS}),
    ),
    Source(
        key="kaggle",
        label="Kaggle",
        method=IngestMethod.API,
        hosts=("kaggle.com",),
        guidance="Fetched via the official Kaggle public API using your API token.",
        contributes=frozenset({Contributes.PROJECTS}),
    ),
    Source(
        key="resume",
        label="Base résumé",
        method=IngestMethod.LOCAL_FILE,
        hosts=(),
        guidance=(
            "Upload your existing résumé (.docx). Its sections become draft "
            "blocks you confirm — the fastest way to seed a corpus, because "
            "the prose is already yours."
        ),
        contributes=frozenset(
            {Contributes.WORK_HISTORY, Contributes.PROJECTS, Contributes.EDUCATION}
        ),
    ),
    Source(
        key="linkedin",
        label="LinkedIn",
        method=IngestMethod.USER_EXPORT,
        hosts=("linkedin.com",),
        guidance=(
            "LinkedIn prohibits scraping. Export your own data instead: "
            "Settings & Privacy → Data Privacy → Get a copy of your data. "
            "Upload the archive and Curat0r will read your positions, "
            "education, and skills from it."
        ),
        contributes=frozenset({Contributes.WORK_HISTORY, Contributes.EDUCATION}),
    ),
    Source(
        key="indeed",
        label="Indeed job posting",
        method=IngestMethod.USER_PASTED,
        hosts=("indeed.com",),
        guidance="Indeed prohibits scraping. Paste the job description text instead.",
        contributes=frozenset({Contributes.POSTINGS}),
    ),
    Source(
        key="indeed-profile",
        label="Indeed profile",
        method=IngestMethod.USER_EXPORT,
        hosts=(),
        guidance=(
            "Indeed prohibits scraping, and your own profile is no exception. "
            "Download it instead: Profile -> ... -> Download resume, then upload "
            "the file. Gives work history with dates."
        ),
        contributes=frozenset({Contributes.WORK_HISTORY, Contributes.EDUCATION}),
    ),
    Source(
        key="glassdoor",
        label="Glassdoor",
        method=IngestMethod.USER_PASTED,
        hosts=("glassdoor.com",),
        guidance="Glassdoor prohibits scraping. Paste the job description text instead.",
        contributes=frozenset({Contributes.POSTINGS}),
    ),
)

_BY_KEY = {source.key: source for source in REGISTRY}


def by_key(key: str) -> Source:
    """Fetch a source by key. For sources with no URL, like an uploaded file."""
    source = _BY_KEY.get(key.strip().casefold())
    if source is None:
        raise UnknownSource(f"no source registered under {key!r}")
    return source


def identify(url: str) -> Source:
    """Resolve a URL to a registered source, or refuse to guess."""
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise UnknownSource(f"{url!r} is not an http(s) URL")
    for source in REGISTRY:
        if source.matches(parsed.netloc):
            return source
    raise UnknownSource(
        f"{parsed.netloc} is not a supported source. "
        f"Supported: {', '.join(s.label for s in REGISTRY)}."
    )


def require_auto_fetchable(url: str) -> Source:
    """Gate every automated fetch. Raises with actionable guidance if refused.

    Callers must route through this rather than checking `method` themselves —
    a check that can be skipped is a check that will be.
    """
    source = identify(url)
    if not source.method.may_auto_fetch:
        raise IngestNotPermitted(source.label, source.method.value, source.guidance)
    return source


# ── GitHub URL parsing ───────────────────────────────────────────────────────

_GITHUB_USER = re.compile(r"^/([A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?)/?$")
_GITHUB_REPO = re.compile(
    r"^/([A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?)/([A-Za-z0-9._-]{1,100})/?$"
)


@dataclass(frozen=True, slots=True)
class GitHubTarget:
    owner: str
    repo: str | None = None

    @property
    def is_profile(self) -> bool:
        return self.repo is None


def parse_github(url: str) -> GitHubTarget:
    """Accept a profile or a single repo URL. Anything deeper is ambiguous."""
    require_auto_fetchable(url)
    path = urlparse(url.strip()).path
    if match := _GITHUB_REPO.match(path):
        return GitHubTarget(match.group(1), match.group(2).removesuffix(".git"))
    if match := _GITHUB_USER.match(path):
        return GitHubTarget(match.group(1))
    raise UnknownSource(f"expected a GitHub profile or repository URL, got path {path!r}")


def sources_for(kind: Contributes) -> tuple[Source, ...]:
    """Every source that can supply this kind of material."""
    return tuple(s for s in REGISTRY if kind in s.contributes)


def coverage_gaps() -> dict[str, tuple[str, ...]]:
    """What each kind of material can come from, so a thin corpus is diagnosable.

    A resume missing work history is a different problem from one missing
    projects, and the fix is a different source each time.
    """
    return {kind.value: tuple(s.label for s in sources_for(kind)) for kind in Contributes}


def describe_all() -> list[dict[str, str]]:
    """For the UI: what each source needs from the user."""
    return [
        {
            "key": s.key,
            "label": s.label,
            "method": s.method.value,
            "auto": str(s.method.may_auto_fetch).lower(),
            "guidance": s.guidance,
        }
        for s in REGISTRY
    ]

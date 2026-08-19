"""Screening repositories out of the corpus.

Not everything public is worth putting on a resume. Practice dumps, course
forks, profile READMEs and dotfiles are real work but they are not evidence of
the thing a hiring manager is trying to assess, and listing them dilutes the
two or three repositories that are.

**Nothing is dropped silently.** Every exclusion carries a reason and can be
overridden. "Uninteresting" is a judgement, and a judgement made invisibly is
one the user cannot disagree with — a practice repository is dead weight for a
backend role and genuinely relevant for one that screens on algorithms.

So this module is the same shape as `adjacency`: it proposes, it explains, and
the user has the last word.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class Reason(StrEnum):
    FORK = "fork"
    PROFILE_README = "profile_readme"
    PRACTICE = "practice"
    COURSE = "course"
    CONFIG = "config"
    EMPTY = "empty"
    TOO_SMALL = "too_small"
    ARCHIVED = "archived"
    NO_SIGNAL = "no_signal"

    @property
    def explain(self) -> str:
        return {
            Reason.FORK: "a fork - the work is someone else's unless you say otherwise",
            Reason.PROFILE_README: "your GitHub profile README, not a project",
            Reason.PRACTICE: "exercise or interview practice, not a built thing",
            Reason.COURSE: "coursework or a tutorial follow-along",
            Reason.CONFIG: "dotfiles or configuration, not a project",
            Reason.EMPTY: "no description and no language - nothing to say about it",
            Reason.TOO_SMALL: "too small to have done anything",
            Reason.ARCHIVED: "archived by you",
            Reason.NO_SIGNAL: "no description, so any bullet would be invented",
        }[self]


# Substring patterns, matched against the repo name only. Deliberately
# conservative: a false exclusion silently deletes real work from a resume,
# which is far worse than one extra line the user removes by hand.
_PRACTICE = (
    "leetcode", "neetcode", "hackerrank", "codewars", "exercism", "advent-of-code",
    "adventofcode", "aoc-20", "codingbat", "project-euler", "interview-prep",
    "algo-practice", "dsa-practice", "katas", "coding-challenge",
)
_COURSE = (
    "tutorial", "bootcamp", "coursera", "udemy", "freecodecamp", "learning-lab",
    "learning-labs", "course-", "-course", "workshop", "100-days", "30-days",
    "getting-started", "hello-world", "my-first",
)
_CONFIG = ("dotfiles", ".github", "config-", "-config", "setup-scripts")


def _matches(name: str, patterns: tuple[str, ...]) -> bool:
    lowered = name.casefold()
    return any(p in lowered for p in patterns)


@dataclass(frozen=True, slots=True)
class Verdict:
    name: str
    keep: bool
    reason: Reason | None = None

    def describe(self) -> str:
        if self.keep:
            return f"keep    {self.name}"
        return f"drop    {self.name}  - {self.reason.explain}"  # type: ignore[union-attr]


def screen(
    repos: Iterable[dict[str, Any]],
    owner: str = "",
    *,
    keep_anyway: frozenset[str] = frozenset(),
    include_forks: bool = False,
    min_size_kb: int = 20,
) -> tuple[list[dict[str, Any]], list[Verdict]]:
    """Split repos into (kept, all verdicts).

    `keep_anyway` forces inclusion by name and always wins. That escape hatch is
    the reason this can be opinionated at all: a rule with an override is a
    default, and a rule without one is a decision taken away from the user.
    """
    kept: list[dict[str, Any]] = []
    verdicts: list[Verdict] = []

    for repo in repos:
        name = str(repo.get("name") or "")
        if not name:
            continue

        if name in keep_anyway:
            kept.append(repo)
            verdicts.append(Verdict(name, True))
            continue

        reason: Reason | None = None
        if repo.get("fork") and not include_forks:
            reason = Reason.FORK
        elif repo.get("archived"):
            reason = Reason.ARCHIVED
        elif owner and name.casefold() == owner.casefold():
            reason = Reason.PROFILE_README
        elif _matches(name, _PRACTICE):
            reason = Reason.PRACTICE
        elif _matches(name, _COURSE):
            reason = Reason.COURSE
        elif _matches(name, _CONFIG):
            reason = Reason.CONFIG
        elif not repo.get("description") and not repo.get("language"):
            reason = Reason.EMPTY
        elif (repo.get("size") or 0) < min_size_kb:
            reason = Reason.TOO_SMALL
        elif not str(repo.get("description") or "").strip():
            # A block with no description yields only "Written primarily in X",
            # which is a fact about the file extension, not about the work.
            reason = Reason.NO_SIGNAL

        if reason is None:
            kept.append(repo)
            verdicts.append(Verdict(name, True))
        else:
            verdicts.append(Verdict(name, False, reason))

    return kept, verdicts


def report(verdicts: list[Verdict]) -> str:
    """Human-readable. Dropped repos are listed, never hidden."""
    kept = [v for v in verdicts if v.keep]
    dropped = [v for v in verdicts if not v.keep]
    lines = [f"{len(kept)} kept, {len(dropped)} dropped", ""]
    lines += [f"  {v.describe()}" for v in kept]
    if dropped:
        lines += ["", "  dropped - override with keep_anyway={'name'}:"]
        lines += [f"  {v.describe()}" for v in dropped]
    return "\n".join(lines)

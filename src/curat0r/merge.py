"""Merging freshly ingested drafts into an existing corpus.

Re-ingesting must never silently overwrite something the user wrote. That is
the one operation capable of destroying the corpus's value, because the corpus
IS the user's verified prose — the raw material is reproducible, their edits
are not.

Policy:

* A block the user has verified or edited is **never** overwritten. Changes
  arrive as a pending update they can accept.
* A new block is added as an unverified draft.
* An unverified block with no edits refreshes freely — nothing is lost.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class MergeResult:
    blocks: tuple[dict[str, Any], ...]
    added: tuple[str, ...]
    refreshed: tuple[str, ...]
    protected: tuple[str, ...]  # user-owned; incoming change withheld
    pending: tuple[dict[str, Any], ...]

    def summary(self) -> str:
        return (
            f"{len(self.added)} added, {len(self.refreshed)} refreshed, "
            f"{len(self.protected)} protected ({len(self.pending)} pending review)"
        )


def _is_user_owned(block: dict[str, Any]) -> bool:
    return bool(block.get("_verified")) or bool(block.get("_edited"))


def _differs(existing: dict[str, Any], incoming: dict[str, Any]) -> bool:
    keys = ("title", "org", "dates", "tags", "bullets")
    return any(existing.get(k) != incoming.get(k) for k in keys)


def merge(existing: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> MergeResult:
    by_id = {block["id"]: dict(block) for block in existing}
    added: list[str] = []
    refreshed: list[str] = []
    protected: list[str] = []
    pending: list[dict[str, Any]] = []

    for block in incoming:
        block_id = block["id"]
        current = by_id.get(block_id)

        if current is None:
            by_id[block_id] = dict(block)
            added.append(block_id)
            continue

        if not _differs(current, block):
            continue

        if _is_user_owned(current):
            # Withhold. The user decides; nothing they wrote is touched.
            protected.append(block_id)
            pending.append({"id": block_id, "proposed": dict(block)})
            continue

        # Unverified and unedited — safe to refresh, but never resurrect a
        # verified flag the incoming draft does not have.
        merged = dict(block)
        merged["_verified"] = current.get("_verified", False)
        by_id[block_id] = merged
        refreshed.append(block_id)

    return MergeResult(
        blocks=tuple(by_id.values()),
        added=tuple(added),
        refreshed=tuple(refreshed),
        protected=tuple(protected),
        pending=tuple(pending),
    )


def _title_key(block: dict[str, Any]) -> str:
    """Normalised title, for spotting the same project from two sources.

    `Auto Interner` from a resume and `auto_Interner` from GitHub are one
    project. Separators, case and spacing differ by source and mean nothing.
    """
    title = str(block.get("title") or "")
    return re.sub(r"[^a-z0-9]", "", title.casefold())


def dedupe_across_sources(blocks: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    """Collapse the same project ingested from more than one source.

    Keeps the richer block - more bullets wins, then longer prose. A resume
    entry usually beats a GitHub description because the user wrote it about
    the work rather than about the repository.

    Without this a combined corpus lists every project twice and the duplicate
    competes with real content for the page.
    """
    best: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    dropped: list[str] = []

    for block in blocks:
        key = _title_key(block)
        if not key:
            order.append(id(block))  # keep untitled blocks as-is
            best[id(block)] = block
            continue
        if key not in best:
            best[key] = block
            order.append(key)
            continue

        incumbent = best[key]

        def richness(b: dict[str, Any]) -> tuple[int, int]:
            bullets = b.get("bullets") or []
            return (len(bullets), sum(len(x.get("text", "")) for x in bullets))

        if richness(block) > richness(incumbent):
            best[key] = block
            dropped.append(f"{incumbent.get('title')} ({incumbent.get('_source', 'resume')})")
        else:
            dropped.append(f"{block.get('title')} ({block.get('_source', 'resume')})")

    return [best[k] for k in order], dropped


def verified_only(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """What the selection engine is allowed to see.

    The engine's guarantee is that every rendered line was written and confirmed
    by the user. Feeding it unverified drafts would quietly break exactly that.
    """
    return [b for b in blocks if b.get("_verified")]

"""Shared shapes for data that crosses module boundaries.

`Block` is deliberately `dict[str, Any]` rather than something narrower. A
corpus block is a heterogeneous JSON record — `id` and `title` are strings,
`recency` an int, `_verified` a bool, `bullets` a list of dicts — and the
authoritative parser for it is `auto_interner.corpus.blocks._parse_block`, which
lives in the other repository. Naming the alias says the one true thing a bare
`dict` did not: that these eight call sites are all passing the same concept
around. When Phase 1.5 brings the parser into this package, this is the single
line that becomes a `TypedDict`.

`CurateResult` is the opposite case. Its shape is fixed and produced in exactly
one place, so it is written out precisely.
"""

from __future__ import annotations

from typing import Any, TypedDict

__all__ = ["Block", "CurateResult"]

Block = dict[str, Any]


class CurateResult(TypedDict):
    """What `web.engine.curate` returns.

    Mirrors `web.schemas.CurateResponse` minus `prompts`, which the web layer
    adds after the selection engine has run.
    """

    resume: str
    score: float
    gaps: list[str]
    missed: list[str]
    shown: list[str]
    lines_used: int
    budget: int

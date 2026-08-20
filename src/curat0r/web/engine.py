"""Bridge to the selection engine.

Selection lives in `auto_interner.corpus`. Curat0r does not vendor a copy —
duplicating 750 lines of the one component whose correctness carries the
product's entire guarantee is how the two silently diverge.

Instead it is an optional install:

    pip install -e ../auto_Interner

Curat0r still only depends on the corpus JSON *format*, so a future extraction
into a shared package changes this file and nothing else.
"""

from __future__ import annotations

from curat0r.types import Block, CurateResult

_MISSING = (
    "The selection engine is not installed. From the Curat0r repo root:\n"
    "    pip install -e ../auto_Interner\n"
    "Curat0r handles ingestion, adjacency, and gaps; auto_interner.corpus "
    "handles selection."
)


class EngineUnavailable(RuntimeError):
    pass


def available() -> bool:
    try:
        import auto_interner.corpus  # noqa: F401
    except ModuleNotFoundError:
        return False
    return True


def curate(blocks_json: list[Block], posting: str, budget: int = 30) -> CurateResult:
    """Run selection over verified blocks and return resume + coverage."""
    try:
        from auto_interner.corpus import (
            build_report,
            extract_requirements,
            render_resume,
            select,
        )
        from auto_interner.corpus.blocks import _parse_block
    except ModuleNotFoundError as exc:
        raise EngineUnavailable(_MISSING) from exc

    blocks = tuple(_parse_block(b, i) for i, b in enumerate(blocks_json))
    requirements = extract_requirements(posting)
    selection = select(blocks, requirements, budget=budget)
    report = build_report(blocks, requirements, selection)

    return {
        "resume": render_resume(selection),
        "score": report.score(),
        "gaps": [s.requirement.term for s in report.gaps],
        "missed": [s.requirement.term for s in report.missed],
        "shown": [s.requirement.term for s in report.shown],
        "lines_used": selection.used,
        "budget": selection.budget,
    }

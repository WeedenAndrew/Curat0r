"""Curat0r web API.

    uvicorn curat0r.web.main:app --reload --port 8000
    http://localhost:8000

Structure follows the same discipline as Fantasy_Blackjack: typed response
models, one exception handler mapping domain errors to status codes, and no
try/except inside endpoints.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from curat0r.errors import Curat0rError, IngestNotPermitted, UnknownSource
from curat0r.gaps import Answer, GapPrompt, prompts_for_gaps
from curat0r.sources import REGISTRY, parse_github, require_auto_fetchable
from curat0r.web import engine
from curat0r.web.schemas import (
    CloseGapsRequest,
    CurateRequest,
    CurateResponse,
    ErrorOut,
    GapPromptOut,
    IngestRequest,
    SourceOut,
    TwoDocumentsOut,
)

STATIC = Path(__file__).parent / "static"

app = FastAPI(
    title="Curat0r",
    description="Curate a resume from the work you have actually done.",
    version="0.1.0",
)

_STATUS = {
    UnknownSource: status.HTTP_404_NOT_FOUND,
    # 451 is exactly right: the refusal is legal, not technical. The resource
    # exists and is reachable; we decline because its terms say not to.
    IngestNotPermitted: status.HTTP_451_UNAVAILABLE_FOR_LEGAL_REASONS,
    engine.EngineUnavailable: status.HTTP_503_SERVICE_UNAVAILABLE,
}


@app.exception_handler(Curat0rError)
async def handle_domain_error(_: Request, exc: Curat0rError) -> JSONResponse:
    return JSONResponse(
        status_code=_STATUS.get(type(exc), status.HTTP_400_BAD_REQUEST),
        content=ErrorOut(error=type(exc).__name__, detail=str(exc)).model_dump(),
    )


@app.exception_handler(engine.EngineUnavailable)
async def handle_engine_missing(_: Request, exc: engine.EngineUnavailable) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=ErrorOut(error="EngineUnavailable", detail=str(exc)).model_dump(),
    )


def _corpus_tags(blocks: list[dict]) -> dict[str, tuple[str, ...]]:
    index: dict[str, list[str]] = {}
    for block in blocks:
        for tag in block.get("tags", []):
            index.setdefault(str(tag), []).append(str(block.get("id", "?")))
    return {tag: tuple(ids) for tag, ids in index.items()}


def _prompt_out(prompt: GapPrompt) -> GapPromptOut:
    return GapPromptOut(
        requirement=prompt.requirement,
        kind=prompt.kind.value,
        question=prompt.question,
        recoverable=prompt.is_recoverable,
        near=prompt.near.have if prompt.near else None,
    )


def _curate(blocks: list[dict], posting: str, budget: int) -> CurateResponse:
    verified = [b for b in blocks if b.get("_verified")]
    result = engine.curate(verified, posting, budget)
    prompts = prompts_for_gaps(result["gaps"], _corpus_tags(verified))
    return CurateResponse(**result, prompts=[_prompt_out(p) for p in prompts])


# ── API ──────────────────────────────────────────────────────────────────────

@app.get("/api/sources", response_model=list[SourceOut], tags=["sources"])
async def list_sources() -> list[SourceOut]:
    """What each source needs from the user, and which may be fetched."""
    return [
        SourceOut(
            key=s.key, label=s.label, method=s.method.value,
            auto_fetchable=s.method.may_auto_fetch, guidance=s.guidance,
        )
        for s in REGISTRY
    ]


@app.post("/api/ingest/check", tags=["sources"])
async def check_ingest(body: IngestRequest) -> dict:
    """Ask whether a URL may be fetched. Refusals carry guidance, not just no."""
    source = require_auto_fetchable(body.url)
    target = parse_github(body.url) if source.key == "github" else None
    return {
        "source": source.key,
        "auto_fetchable": True,
        "owner": target.owner if target else None,
        "repo": target.repo if target else None,
    }


@app.post("/api/curate", response_model=CurateResponse, tags=["curate"])
async def curate(body: CurateRequest) -> CurateResponse:
    """Tailor from verified blocks. Unverified drafts are never selected."""
    return _curate(body.blocks, body.posting, body.budget)


@app.post("/api/gaps/close", response_model=TwoDocumentsOut, tags=["curate"])
async def close_gaps(body: CloseGapsRequest) -> TwoDocumentsOut:
    """Both documents. Neither contains a claim the user did not write.

    The second is not an embellished variant — it is the same selection run
    again over a corpus the user just added truthful blocks to.
    """
    before = _curate(body.blocks, body.posting, body.budget)

    answers = [Answer(a.requirement, a.text, frozenset(a.tags)) for a in body.answers]
    from curat0r.gaps import block_from_answer

    enriched = list(body.blocks) + [
        block_from_answer(a, f"gap-{i}-{a.requirement}") for i, a in enumerate(answers)
    ]
    after = _curate(enriched, body.posting, body.budget)

    answered = {a.requirement for a in answers}
    return TwoDocumentsOut(
        supported_now=before,
        after_answers=after,
        closed=len(answers),
        still_open=[g for g in before.gaps if g not in answered],
        note=(
            "Both documents contain only claims you wrote. The second differs "
            "because you remembered more, not because anything was generated."
        ),
    )


@app.get("/api/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok", "engine": "available" if engine.available() else "missing"}


# ── static site ──────────────────────────────────────────────────────────────

if STATIC.is_dir():
    app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")

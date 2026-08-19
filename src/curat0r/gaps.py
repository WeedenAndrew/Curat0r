"""Closing gaps by asking, never by writing.

There is an obvious product request here: two resumes, one honest and one that
"fills the gaps". The second is a fabricated resume. It is also unnecessary,
because the premise is usually wrong.

**Most gaps are corpus gaps, not experience gaps.** The posting wants Kubernetes;
you deployed a cluster last spring and never wrote it down. Nothing in the
corpus supports it, so the engine correctly reports a gap — but the fix is to
ask you, not to invent a bullet.

So this module produces a QUESTION per gap, never a claim. Answer it and you
own the words; leave it and the gap stays a gap. Both output documents are
fully supported at every moment. The difference between them is how much you
remembered, not how much the model made up.

Gaps are classified by how likely they are to be recoverable, because "you have
adjacent evidence, do you also have this?" is a very different question from
"you appear to have never touched this."
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from curat0r.adjacency import DEFAULT, AdjacencyProvider, NearMatch, nearest


class GapKind(StrEnum):
    LIKELY_UNWRITTEN = "likely_unwritten"
    """Adjacent evidence exists. Probably done, probably not recorded."""

    UNSUPPORTED = "unsupported"
    """Nothing nearby. Possibly a real mismatch."""


@dataclass(frozen=True, slots=True)
class GapPrompt:
    """One question about one unmet requirement."""

    requirement: str
    kind: GapKind
    question: str
    near: NearMatch | None = None

    @property
    def is_recoverable(self) -> bool:
        return self.kind is GapKind.LIKELY_UNWRITTEN


def _question_for(requirement: str, near: NearMatch | None) -> str:
    """Phrased to elicit a memory, never to suggest an answer.

    Never "describe your Kafka experience" — that presupposes it exists and
    invites invention. Always a yes/no the user can decline without friction,
    because the decline has to be as easy as the confirm or the whole thing
    drifts toward flattery.
    """
    if near is not None:
        return (
            f"This role asks for {requirement}. Your corpus has {near.have}, "
            f"which is adjacent — have you also worked with {requirement} "
            f"directly? If yes, describe it in your own words. If no, skip it."
        )
    return (
        f"This role asks for {requirement} and nothing in your corpus covers it. "
        f"Have you used it anywhere — coursework, a side project, a job you "
        f"haven't added yet? If not, skip it; a real gap is worth knowing about."
    )


def prompts_for_gaps(
    gap_terms: list[str],
    corpus_tags: dict[str, tuple[str, ...]],
    provider: AdjacencyProvider = DEFAULT,
) -> list[GapPrompt]:
    """One prompt per gap, recoverable-looking ones first.

    Ordering matters: the questions most likely to produce a real answer go
    first, so a user who quits after three has answered the best three.
    """
    prompts: list[GapPrompt] = []
    for term in gap_terms:
        near = nearest(term, corpus_tags, provider=provider)
        kind = GapKind.LIKELY_UNWRITTEN if near else GapKind.UNSUPPORTED
        prompts.append(GapPrompt(term, kind, _question_for(term, near), near))

    prompts.sort(key=lambda p: (p.kind is not GapKind.LIKELY_UNWRITTEN, p.requirement))
    return prompts


@dataclass(frozen=True, slots=True)
class Answer:
    """A user's own words about one gap. The only way a gap ever closes."""

    requirement: str
    text: str
    tags: frozenset[str]

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("an empty answer does not close a gap")


def block_from_answer(answer: Answer, block_id: str) -> dict:
    """Turn a user's answer into a corpus block.

    `_verified: true` — unlike ingested drafts, this text was typed by the user
    in response to a direct question. There is no third party to confirm it
    against and no model in the loop. They wrote it; they own it.
    """
    return {
        "id": block_id,
        "kind": "project",
        "title": answer.requirement,
        "tags": sorted(answer.tags | {answer.requirement}),
        "bullets": [{"text": answer.text.strip(), "tags": sorted(answer.tags)}],
        "recency": 0,
        "_source": "gap_interview",
        "_verified": True,
    }


@dataclass(frozen=True, slots=True)
class TwoDocuments:
    """What the UI offers: today's resume, and the one after you answer."""

    supported_now: list[dict]
    after_answers: list[dict]
    unanswered: tuple[str, ...]

    @property
    def closed(self) -> int:
        return len(self.after_answers) - len(self.supported_now)

    def describe(self) -> str:
        if not self.closed:
            return f"No gaps closed. {len(self.unanswered)} still open."
        return (
            f"{self.closed} gap(s) closed with your own words. "
            f"{len(self.unanswered)} still open — those are real."
        )


def build_two_documents(
    verified_blocks: list[dict],
    answers: list[Answer],
    all_gap_terms: list[str],
) -> TwoDocuments:
    """Both documents are fully supported. Neither contains an invented claim."""
    after = list(verified_blocks)
    for index, answer in enumerate(answers):
        after.append(block_from_answer(answer, f"gap-{index}-{answer.requirement}"))

    answered = {a.requirement for a in answers}
    return TwoDocuments(
        supported_now=list(verified_blocks),
        after_answers=after,
        unanswered=tuple(t for t in all_gap_terms if t not in answered),
    )

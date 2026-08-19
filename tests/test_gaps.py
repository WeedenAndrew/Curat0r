"""Gaps close by asking, never by writing."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from curat0r.gaps import (
    Answer,
    GapKind,
    block_from_answer,
    build_two_documents,
    prompts_for_gaps,
)

CORPUS_TAGS = {"rabbitmq": ("gh-pipeline",), "python": ("gh-pipeline",)}
VERIFIED = [{"id": "gh-pipeline", "_verified": True}]


# ── Prompts ask; they never assert ───────────────────────────────────────────


def test_prompt_never_contains_a_claim_about_the_user():
    for prompt in prompts_for_gaps(["kafka", "cobol"], CORPUS_TAGS):
        lowered = prompt.question.casefold()
        assert "?" in prompt.question
        for phrase in (
            "you have experience",
            "you are proficient",
            "you built",
            "you architected",
            "your experience with",
        ):
            assert phrase not in lowered


def test_adjacent_evidence_marks_a_gap_recoverable():
    prompt = next(p for p in prompts_for_gaps(["kafka"], CORPUS_TAGS))
    assert prompt.kind is GapKind.LIKELY_UNWRITTEN
    assert prompt.near is not None and prompt.near.have == "rabbitmq"


def test_no_adjacent_evidence_marks_a_gap_unsupported():
    prompt = next(p for p in prompts_for_gaps(["cobol"], CORPUS_TAGS))
    assert prompt.kind is GapKind.UNSUPPORTED
    assert prompt.near is None


def test_recoverable_gaps_are_asked_first():
    """A user who quits after one question should have answered the best one."""
    prompts = prompts_for_gaps(["cobol", "kafka", "fortran"], CORPUS_TAGS)
    assert prompts[0].requirement == "kafka"


def test_every_prompt_offers_an_exit():
    """Declining must be as easy as confirming, or the tool drifts to flattery."""
    for prompt in prompts_for_gaps(["kafka", "cobol"], CORPUS_TAGS):
        assert "skip it" in prompt.question.casefold()


# ── Answers become blocks the user owns ──────────────────────────────────────


def test_answer_block_is_verified_because_the_user_typed_it():
    block = block_from_answer(Answer("kafka", "Ran a 3-broker cluster.", frozenset()), "g0")
    assert block["_verified"] is True
    assert block["_source"] == "gap_interview"
    assert block["bullets"][0]["text"] == "Ran a 3-broker cluster."


def test_empty_answer_is_rejected():
    with pytest.raises(ValueError, match="does not close a gap"):
        Answer("kafka", "   ", frozenset())


def test_answer_text_is_preserved_verbatim():
    text = "Wrote a consumer that processed ~2k msgs/sec."
    block = block_from_answer(Answer("kafka", text, frozenset()), "g0")
    assert block["bullets"][0]["text"] == text


# ── Both documents are fully supported ───────────────────────────────────────


def test_second_document_contains_only_answered_gaps():
    docs = build_two_documents(
        VERIFIED,
        [Answer("kafka", "Ran a 3-broker cluster.", frozenset({"kafka"}))],
        ["kafka", "cobol"],
    )
    assert docs.closed == 1
    assert docs.unanswered == ("cobol",)


def test_unanswered_gaps_never_appear_in_either_document():
    docs = build_two_documents(VERIFIED, [], ["kafka", "cobol"])
    assert docs.supported_now == docs.after_answers
    assert docs.closed == 0
    assert set(docs.unanswered) == {"kafka", "cobol"}


def test_every_block_in_both_documents_is_verified():
    """The core invariant: no unsupported claim reaches either output."""
    docs = build_two_documents(
        VERIFIED,
        [Answer("kafka", "Ran a cluster.", frozenset({"kafka"}))],
        ["kafka"],
    )
    for document in (docs.supported_now, docs.after_answers):
        assert all(block.get("_verified") for block in document)


def test_describe_reports_remaining_gaps_as_real():
    docs = build_two_documents(
        VERIFIED, [Answer("kafka", "Ran a cluster.", frozenset())], ["kafka", "cobol"]
    )
    assert "1 gap(s) closed" in docs.describe()
    assert "those are real" in docs.describe()

"""Tests for Real-Time User Feedback Loops (Completeness & Accuracy).

Tests:
1. Binary Feedback (+/-) endpoints and recording to audit log.
2. Correction UI submission with 'What was missing or incorrect?' capturing vector DB gaps.
3. Programmed agent canonical phrase: 'I cannot find that in the provided documentation'.
4. Tracking 'I don't know' rates across conversations.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from apps.api.app.api.routes.chat import ChatFeedbackRequest, submit_chat_feedback, get_message_feedback
from packages.llm.generation import GenerationResult, RAGGenerator
from packages.llm.graph import _node_finalize
from packages.llm.graph_state import GraphState


@pytest.mark.asyncio
async def test_agent_speaks_canonical_idk_phrase_when_no_evidence():
    """Verify that when no evidence is available, generator returns canonical phrase."""
    mock_provider = MagicMock()
    mock_provider.generate = AsyncMock()
    generator = RAGGenerator(provider=mock_provider)

    result = await generator.generate(question="What is the quantum flux capacity?", evidence=[])

    assert result.abstained is True
    assert result.grounded is False
    assert "I cannot find that in the provided documentation" in result.answer
    assert "unable to find sufficient evidence" in result.answer.lower()


def test_node_finalize_canonical_idk_phrase():
    """Verify _node_finalize defaults to the canonical phrase on insufficient evidence."""
    empty_state: GraphState = {
        "question": "Tell me about alien life in 2024",
        "authorized_document_ids": [],
        "retrieval_query": "alien life",
        "retrieval_filters": {},
        "evidence": [],
        "evidence_sufficient": False,
        "query_type": "DIRECT",
        "requires_calculation": False,
        "calculation_result": None,
        "tool_calls": 0,
        "retrieval_attempts": 1,
        "result": None,
    }

    finalized = _node_finalize(empty_state)
    res = finalized.get("result")

    assert res is not None
    assert res.abstained is True
    assert "I cannot find that in the provided documentation" in res.answer


@pytest.mark.asyncio
async def test_submit_binary_feedback_thumbs_up():
    """Test thumbs-up feedback submission."""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    user = MagicMock()
    user.id = uuid.uuid4()

    req = ChatFeedbackRequest(
        message_id=str(uuid.uuid4()),
        conversation_id=str(uuid.uuid4()),
        rating="thumbs_up",
    )

    response = await submit_chat_feedback(payload=req, current_user=user, session=mock_session)

    assert response["status"] == "success"
    assert response["rating"] == "thumbs_up"
    assert mock_session.add.called
    assert mock_session.commit.called


@pytest.mark.asyncio
async def test_submit_correction_ui_feedback():
    """Test thumbs-down submission with 'What was missing or incorrect?' correction details."""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    user = MagicMock()
    user.id = uuid.uuid4()

    req = ChatFeedbackRequest(
        message_id=str(uuid.uuid4()),
        conversation_id=str(uuid.uuid4()),
        rating="thumbs_down",
        feedback_text="Missing 2025 financial disclosures for Stanford University.",
        tags=["Missing relevant facts", "Outdated documentation"],
        user_query="What were Stanford's revenues in 2025?",
    )

    response = await submit_chat_feedback(payload=req, current_user=user, session=mock_session)

    assert response["status"] == "success"
    assert response["rating"] == "thumbs_down"

    # Verify audit log entry contents
    added_entry = mock_session.add.call_args[0][0]
    assert added_entry.action == "user_feedback"
    assert added_entry.metadata_["rating"] == "thumbs_down"
    assert added_entry.metadata_["feedback_text"] == "Missing 2025 financial disclosures for Stanford University."
    assert "Missing relevant facts" in added_entry.metadata_["tags"]

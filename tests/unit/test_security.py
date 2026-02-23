"""
Security Tests — Dual-Tier Permission Bridge
=============================================

Tests for gate_content(), filter_documents(), enrollment defaults,
and degraded mode behaviour.
"""

import asyncio
import json
import pytest
from unittest.mock import MagicMock

import sys
from pathlib import Path

# Add src to path
SRC = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(SRC))

from luna.identity.bridge import BridgeResult
from luna.identity.permissions import gate_content, filter_documents, get_denial_message


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _doc(node_id="doc_1", category=None, tags=None):
    """Create a DOCUMENT node dict."""
    meta = {}
    if category is not None:
        meta["dataroom_category"] = category
    d = {"id": node_id, "node_type": "DOCUMENT", "content": "secret doc", "metadata": meta}
    if tags:
        d["tags"] = tags
    return d


def _fact(node_id="fact_1"):
    return {"id": node_id, "node_type": "FACT", "content": "coffee preference", "metadata": {}}


def _entity(node_id="entity_1"):
    return {"id": node_id, "node_type": "ENTITY", "content": "Ahab", "metadata": {}}


def _conv(node_id="conv_1"):
    return {"id": node_id, "node_type": "CONVERSATION", "content": "hello there", "metadata": {}}


def _bridge(luna_tier="admin", dr_tier=1, categories=None):
    return BridgeResult(
        entity_id="test_entity",
        luna_tier=luna_tier,
        dataroom_tier=dr_tier,
        dataroom_categories=list(range(1, 10)) if categories is None else categories,
    )


# ---------------------------------------------------------------------------
# gate_content — the central choke-point
# ---------------------------------------------------------------------------

class TestGateContent:
    """Test the gate_content() function."""

    def test_bridge_none_strips_documents(self):
        """When bridge is None (anonymous), ALL documents are stripped."""
        nodes = [_doc("d1"), _fact("f1"), _entity("e1"), _doc("d2")]
        allowed, denied = asyncio.run(
            gate_content(nodes, bridge=None, source="test")
        )
        # Facts and entities pass, documents stripped
        assert len(allowed) == 2
        assert all(n["node_type"] != "DOCUMENT" for n in allowed)
        assert len(denied) == 2
        assert all(n["node_type"] == "DOCUMENT" for n in denied)

    def test_admin_sees_all(self):
        """Admin (tier 1) sees everything including documents."""
        nodes = [_doc("d1"), _fact("f1"), _doc("d2")]
        bridge = _bridge(luna_tier="admin", dr_tier=1)
        allowed, denied = asyncio.run(
            gate_content(nodes, bridge=bridge, source="test")
        )
        assert len(allowed) == 3
        assert len(denied) == 0

    def test_strategist_sees_all(self):
        """Strategist (tier 2) sees everything."""
        bridge = _bridge(luna_tier="trusted", dr_tier=2)
        nodes = [_doc("d1", category=3), _fact("f1")]
        allowed, denied = asyncio.run(
            gate_content(nodes, bridge=bridge, source="test")
        )
        assert len(allowed) == 2
        assert len(denied) == 0

    def test_domain_lead_filtered_by_category(self):
        """Domain lead (tier 3) only sees documents in their categories."""
        bridge = _bridge(luna_tier="trusted", dr_tier=3, categories=[1, 5, 7])
        nodes = [
            _doc("d1", category=1),   # allowed
            _doc("d2", category=2),   # denied (not in [1,5,7])
            _doc("d3", category=5),   # allowed
            _fact("f1"),               # always passes
        ]
        allowed, denied = asyncio.run(
            gate_content(nodes, bridge=bridge, source="test")
        )
        allowed_ids = {n["id"] for n in allowed}
        assert "d1" in allowed_ids
        assert "d3" in allowed_ids
        assert "f1" in allowed_ids
        assert "d2" not in allowed_ids
        assert len(denied) == 1
        assert denied[0]["id"] == "d2"

    def test_empty_nodes(self):
        """Empty input returns empty output."""
        allowed, denied = asyncio.run(
            gate_content([], bridge=None, source="test")
        )
        assert allowed == []
        assert denied == []

    def test_no_documents_passes_all(self):
        """When there are no DOCUMENT nodes, everything passes regardless of bridge."""
        nodes = [_fact("f1"), _entity("e1"), _conv("c1")]
        allowed, denied = asyncio.run(
            gate_content(nodes, bridge=None, source="test")
        )
        assert len(allowed) == 3
        assert len(denied) == 0

    def test_unknown_entity_denied_all_docs(self):
        """Unknown luna_tier with tier 5 should deny categorized docs."""
        bridge = _bridge(luna_tier="unknown", dr_tier=5, categories=[])
        nodes = [_doc("d1", category=3), _fact("f1")]
        allowed, denied = asyncio.run(
            gate_content(nodes, bridge=bridge, source="test")
        )
        # Fact passes, doc denied (no categories in access)
        assert len(allowed) == 1
        assert allowed[0]["id"] == "f1"
        assert len(denied) == 1


# ---------------------------------------------------------------------------
# filter_documents (existing function, verify contract)
# ---------------------------------------------------------------------------

class TestFilterDocuments:

    def test_none_bridge_denies_all(self):
        docs = [_doc("d1"), _doc("d2")]
        allowed, denied = filter_documents(docs, bridge=None)
        assert len(allowed) == 0
        assert len(denied) == 2

    def test_admin_allows_all(self):
        docs = [_doc("d1", category=2), _doc("d2", category=8)]
        bridge = _bridge(luna_tier="admin", dr_tier=1)
        allowed, denied = filter_documents(docs, bridge)
        assert len(allowed) == 2
        assert len(denied) == 0

    def test_uncategorized_docs_pass(self):
        """Documents without a category should pass through (non-dataroom content)."""
        docs = [_doc("d1")]  # no category
        bridge = _bridge(luna_tier="friend", dr_tier=3, categories=[1])
        allowed, denied = filter_documents(docs, bridge)
        assert len(allowed) == 1  # no category = passes
        assert len(denied) == 0

    def test_tag_based_category(self):
        """Documents with dr_cat: tags are filtered correctly."""
        docs = [_doc("d1", tags=["dr_cat:2"])]
        bridge = _bridge(luna_tier="friend", dr_tier=3, categories=[1])
        allowed, denied = filter_documents(docs, bridge)
        assert len(allowed) == 0  # category 2 not in [1]
        assert len(denied) == 1


# ---------------------------------------------------------------------------
# BridgeResult properties
# ---------------------------------------------------------------------------

class TestBridgeResult:

    def test_is_sovereign(self):
        assert _bridge(dr_tier=1).is_sovereign is True
        assert _bridge(dr_tier=2).is_sovereign is False

    def test_can_see_all(self):
        assert _bridge(dr_tier=1).can_see_all is True
        assert _bridge(dr_tier=2).can_see_all is True
        assert _bridge(dr_tier=3).can_see_all is False

    def test_can_access_category(self):
        bridge = _bridge(dr_tier=3, categories=[1, 5, 7])
        assert bridge.can_access_category(1) is True
        assert bridge.can_access_category(2) is False
        assert bridge.can_access_category(5) is True

    def test_tier_1_2_bypass_categories(self):
        bridge = _bridge(dr_tier=2, categories=[])
        assert bridge.can_access_category(9) is True  # Tier 2 sees all


# ---------------------------------------------------------------------------
# Denial messages
# ---------------------------------------------------------------------------

class TestDenialMessages:

    def test_unknown_returns_none(self):
        assert get_denial_message(None) is None

    def test_admin_empty(self):
        assert get_denial_message(_bridge(luna_tier="admin")) == ""

    def test_guest_has_message(self):
        msg = get_denial_message(_bridge(luna_tier="guest"))
        assert "permissions" in msg

    def test_trusted_mentions_ahab(self):
        msg = get_denial_message(_bridge(luna_tier="trusted"))
        assert "ahab" in msg


# ---------------------------------------------------------------------------
# Enrollment defaults
# ---------------------------------------------------------------------------

class TestEnrollmentDefaults:

    def test_identity_actor_defaults_guest(self):
        """IdentityActor.enroll_from_frame should default to guest/T5."""
        from luna.actors.identity import IdentityActor
        import inspect
        sig = inspect.signature(IdentityActor.enroll_from_frame)
        assert sig.parameters["luna_tier"].default == "guest"
        assert sig.parameters["dataroom_tier"].default == 5

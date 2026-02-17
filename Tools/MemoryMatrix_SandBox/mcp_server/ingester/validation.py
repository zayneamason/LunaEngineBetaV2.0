"""
Validation - Schema validation and error handling

Validates LLM extraction output against expected schemas,
provides error handling utilities.
"""

from typing import Dict, List, Any, Optional


class ExtractionValidationError(Exception):
    """Raised when extraction output fails validation."""
    pass


# ============================================================================
# SCHEMA DEFINITIONS
# ============================================================================

NODE_TYPES = {"FACT", "DECISION", "PROBLEM", "ACTION", "OUTCOME", "INSIGHT"}
EDGE_TYPES = {"depends_on", "enables", "contradicts", "clarifies", "related_to", "derived_from"}
ENTITY_TYPES = {"person", "persona", "place", "project"}
TEXTURE_TAGS = {"working", "exploring", "debugging", "reflecting", "creating", "planning", "struggling", "celebrating"}
TIERS = {"GOLD", "SILVER", "BRONZE", "SKIP"}


# ============================================================================
# VALIDATION FUNCTIONS
# ============================================================================

def validate_extraction_schema(extraction: Dict) -> None:
    """
    Validate extraction output schema.

    Args:
        extraction: LLM extraction output

    Raises:
        ExtractionValidationError: If schema is invalid
    """
    # Check top-level keys
    required_keys = {"nodes", "entities", "edges"}
    missing = required_keys - set(extraction.keys())
    if missing:
        raise ExtractionValidationError(f"Missing required keys: {missing}")

    # Validate nodes
    if not isinstance(extraction["nodes"], list):
        raise ExtractionValidationError("'nodes' must be a list")

    for i, node in enumerate(extraction["nodes"]):
        validate_node(node, index=i)

    # Validate observations (if present)
    if "observations" in extraction:
        if not isinstance(extraction["observations"], list):
            raise ExtractionValidationError("'observations' must be a list")
        for i, obs in enumerate(extraction["observations"]):
            validate_observation(obs, index=i, max_node_index=len(extraction["nodes"])-1)

    # Validate entities
    if not isinstance(extraction["entities"], list):
        raise ExtractionValidationError("'entities' must be a list")

    for i, entity in enumerate(extraction["entities"]):
        validate_entity(entity, index=i)

    # Validate edges
    if not isinstance(extraction["edges"], list):
        raise ExtractionValidationError("'edges' must be a list")

    max_node_index = len(extraction["nodes"]) - 1
    for i, edge in enumerate(extraction["edges"]):
        validate_edge(edge, index=i, max_node_index=max_node_index)

    # Validate texture (if present)
    if "texture" in extraction:
        validate_texture(extraction["texture"])


def validate_node(node: Dict, index: int) -> None:
    """Validate a single node."""
    required = {"type", "content", "confidence"}
    missing = required - set(node.keys())
    if missing:
        raise ExtractionValidationError(f"Node {index}: missing {missing}")

    # Type must be valid
    if node["type"] not in NODE_TYPES:
        raise ExtractionValidationError(
            f"Node {index}: invalid type '{node['type']}', must be one of {NODE_TYPES}"
        )

    # Content must be non-empty string
    if not isinstance(node["content"], str) or not node["content"].strip():
        raise ExtractionValidationError(f"Node {index}: content must be non-empty string")

    # Confidence must be 0-1
    try:
        conf = float(node["confidence"])
        if not 0 <= conf <= 1:
            raise ValueError
    except (ValueError, TypeError):
        raise ExtractionValidationError(
            f"Node {index}: confidence must be float between 0 and 1"
        )

    # Tags should be list (if present)
    if "tags" in node:
        if not isinstance(node["tags"], list):
            raise ExtractionValidationError(f"Node {index}: tags must be a list")


def validate_observation(obs: Dict, index: int, max_node_index: int) -> None:
    """Validate an observation node."""
    required = {"linked_to_node_index", "content", "confidence"}
    missing = required - set(obs.keys())
    if missing:
        raise ExtractionValidationError(f"Observation {index}: missing {missing}")

    # linked_to_node_index must be valid
    try:
        linked_idx = int(obs["linked_to_node_index"])
        if not 0 <= linked_idx <= max_node_index:
            raise ValueError
    except (ValueError, TypeError):
        raise ExtractionValidationError(
            f"Observation {index}: linked_to_node_index must be valid node index (0-{max_node_index})"
        )

    # Content must be non-empty
    if not isinstance(obs["content"], str) or not obs["content"].strip():
        raise ExtractionValidationError(
            f"Observation {index}: content must be non-empty string"
        )

    # Confidence should be ~0.6 for observations
    try:
        conf = float(obs["confidence"])
        if not 0 <= conf <= 1:
            raise ValueError
    except (ValueError, TypeError):
        raise ExtractionValidationError(
            f"Observation {index}: confidence must be float between 0 and 1"
        )


def validate_entity(entity: Dict, index: int) -> None:
    """Validate a single entity."""
    required = {"name", "type"}
    missing = required - set(entity.keys())
    if missing:
        raise ExtractionValidationError(f"Entity {index}: missing {missing}")

    # Name must be non-empty
    if not isinstance(entity["name"], str) or not entity["name"].strip():
        raise ExtractionValidationError(f"Entity {index}: name must be non-empty string")

    # Type must be valid
    if entity["type"] not in ENTITY_TYPES:
        raise ExtractionValidationError(
            f"Entity {index}: invalid type '{entity['type']}', must be one of {ENTITY_TYPES}"
        )


def validate_edge(edge: Dict, index: int, max_node_index: int) -> None:
    """Validate a single edge."""
    required = {"from_node_index", "to_node_index", "edge_type"}
    missing = required - set(edge.keys())
    if missing:
        raise ExtractionValidationError(f"Edge {index}: missing {missing}")

    # Indices must be valid
    try:
        from_idx = int(edge["from_node_index"])
        to_idx = int(edge["to_node_index"])
        if not (0 <= from_idx <= max_node_index and 0 <= to_idx <= max_node_index):
            raise ValueError
    except (ValueError, TypeError):
        raise ExtractionValidationError(
            f"Edge {index}: from/to indices must be valid node indices (0-{max_node_index})"
        )

    # No self-loops
    if edge["from_node_index"] == edge["to_node_index"]:
        raise ExtractionValidationError(f"Edge {index}: self-loops not allowed")

    # Edge type must be valid
    if edge["edge_type"] not in EDGE_TYPES:
        raise ExtractionValidationError(
            f"Edge {index}: invalid edge_type '{edge['edge_type']}', must be one of {EDGE_TYPES}"
        )


def validate_texture(texture: List[str]) -> None:
    """Validate texture tags."""
    if not isinstance(texture, list):
        raise ExtractionValidationError("texture must be a list")

    if not 1 <= len(texture) <= 3:
        raise ExtractionValidationError("texture must have 1-3 tags")

    for tag in texture:
        if tag not in TEXTURE_TAGS:
            raise ExtractionValidationError(
                f"Invalid texture tag '{tag}', must be one of {TEXTURE_TAGS}"
            )


def validate_triage_result(result: List[Dict]) -> None:
    """
    Validate triage classification result.

    Args:
        result: LLM triage output (array of classifications)

    Raises:
        ExtractionValidationError: If schema is invalid
    """
    if not isinstance(result, list):
        raise ExtractionValidationError("Triage result must be a list")

    for i, item in enumerate(result):
        required = {"index", "tier", "summary", "texture"}
        missing = required - set(item.keys())
        if missing:
            raise ExtractionValidationError(f"Triage item {i}: missing {missing}")

        # Tier must be valid
        if item["tier"] not in TIERS:
            raise ExtractionValidationError(
                f"Triage item {i}: invalid tier '{item['tier']}', must be one of {TIERS}"
            )

        # Summary must be non-empty
        if not isinstance(item["summary"], str) or not item["summary"].strip():
            raise ExtractionValidationError(
                f"Triage item {i}: summary must be non-empty string"
            )

        # Texture must be valid
        if not isinstance(item["texture"], list) or not 1 <= len(item["texture"]) <= 3:
            raise ExtractionValidationError(
                f"Triage item {i}: texture must be list of 1-3 tags"
            )

        for tag in item["texture"]:
            if tag not in TEXTURE_TAGS:
                raise ExtractionValidationError(
                    f"Triage item {i}: invalid texture tag '{tag}'"
                )


# ============================================================================
# ERROR HANDLING
# ============================================================================

def safe_parse_json(text: str) -> Optional[Dict]:
    """
    Safely parse JSON, handling common LLM output issues.

    Args:
        text: Raw LLM output text

    Returns:
        Parsed dict or None if parsing fails
    """
    import json
    import re

    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to extract JSON from markdown code block
    match = re.search(r'```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try to find first JSON object/array
    for pattern in [r'\{.*\}', r'\[.*\]']:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                continue

    return None

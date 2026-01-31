"""
Probe Evaluator

Evaluates model responses against probe criteria to determine
pass/fail status and calculate scores.
"""

import re
from typing import Optional
from .models import (
    Probe,
    ProbeResult,
    EvaluationCriterion,
    EvaluationMethod,
)


class ProbeEvaluator:
    """
    Evaluates model responses against probe criteria.

    The evaluator checks both pass criteria (things that should be present)
    and fail criteria (things that should NOT be present). A response
    passes only if:
    1. At least one pass criterion matches (if any defined)
    2. No fail criteria match
    """

    def __init__(self, semantic_threshold: float = 0.7):
        """
        Initialize the evaluator.

        Args:
            semantic_threshold: Default threshold for semantic similarity
        """
        self.semantic_threshold = semantic_threshold
        self._semantic_model = None  # Lazy load if needed

    def evaluate(
        self,
        probe: Probe,
        response: str
    ) -> tuple[ProbeResult, float, list[str], list[str], list[str]]:
        """
        Evaluate a response against a probe's criteria.

        Args:
            probe: The probe with criteria to check
            response: The model's response

        Returns:
            Tuple of:
            - ProbeResult: Overall result (pass/fail/partial)
            - float: Score from 0.0 to 1.0
            - list[str]: Descriptions of passed criteria
            - list[str]: Descriptions of failed criteria
            - list[str]: Additional notes
        """
        passed_criteria: list[str] = []
        failed_criteria: list[str] = []
        notes: list[str] = []

        # Get all criteria
        all_pass_criteria = probe.get_all_pass_criteria()
        all_fail_criteria = probe.get_all_fail_criteria()

        # Check pass criteria
        pass_results: list[tuple[bool, float, str]] = []
        for criterion in all_pass_criteria:
            matched, description = self._check_criterion(criterion, response)
            if matched:
                passed_criteria.append(description)
                pass_results.append((True, criterion.weight, description))
            else:
                failed_criteria.append(f"MISSING: {description}")
                pass_results.append((False, criterion.weight, description))

        # Check fail criteria (these are things that should NOT match)
        fail_matches: list[str] = []
        for criterion in all_fail_criteria:
            matched, description = self._check_criterion(criterion, response)
            if matched:
                # This is bad - a fail criterion matched
                fail_matches.append(description)
                failed_criteria.append(f"FORBIDDEN: {description}")

        # Calculate score
        # Score is based on pass criteria met minus penalties for fail criteria matches
        if pass_results:
            total_weight = sum(r[1] for r in pass_results)
            passed_weight = sum(r[1] for r in pass_results if r[0])
            pass_score = passed_weight / total_weight if total_weight > 0 else 0.0
        else:
            # No pass criteria defined - default to pass if no fail criteria match
            pass_score = 1.0

        # Apply penalties for fail criteria matches
        fail_penalty = 0.5 * len(fail_matches)  # Each fail match costs 50%
        score = max(0.0, pass_score - fail_penalty)

        # Determine result
        if fail_matches:
            # Any fail criterion match = fail
            result = ProbeResult.FAIL
            notes.append(f"Failed due to {len(fail_matches)} forbidden content match(es)")
        elif not all_pass_criteria:
            # No pass criteria = pass (if no fail matches)
            result = ProbeResult.PASS
            notes.append("No pass criteria defined, passed by default")
        elif all(r[0] for r in pass_results):
            # All pass criteria met
            result = ProbeResult.PASS
        elif any(r[0] for r in pass_results):
            # Some pass criteria met
            result = ProbeResult.PARTIAL
            notes.append(f"Partial match: {sum(1 for r in pass_results if r[0])}/{len(pass_results)} criteria")
        else:
            # No pass criteria met
            result = ProbeResult.FAIL
            notes.append("No pass criteria matched")

        return result, score, passed_criteria, failed_criteria, notes

    def _check_criterion(
        self,
        criterion: EvaluationCriterion,
        response: str
    ) -> tuple[bool, str]:
        """
        Check if a single criterion matches the response.

        Args:
            criterion: The criterion to check
            response: The response to evaluate

        Returns:
            Tuple of (matched: bool, description: str)
        """
        method = criterion.method
        description = criterion.description or f"{method.value} check"

        if method == EvaluationMethod.CONTAINS:
            return self._check_contains(criterion, response, negate=False)

        elif method == EvaluationMethod.NOT_CONTAINS:
            return self._check_contains(criterion, response, negate=True)

        elif method == EvaluationMethod.REGEX_MATCH:
            return self._check_regex(criterion, response, negate=False)

        elif method == EvaluationMethod.REGEX_NOT_MATCH:
            return self._check_regex(criterion, response, negate=True)

        elif method == EvaluationMethod.LENGTH_RANGE:
            return self._check_length(criterion, response)

        elif method == EvaluationMethod.SEMANTIC:
            return self._check_semantic(criterion, response)

        elif method == EvaluationMethod.ALL_OF:
            return self._check_all_of(criterion, response)

        elif method == EvaluationMethod.ANY_OF:
            return self._check_any_of(criterion, response)

        elif method == EvaluationMethod.CUSTOM:
            # Custom evaluations not supported in base evaluator
            return False, f"Custom evaluation not implemented: {description}"

        return False, f"Unknown method: {method}"

    def _check_contains(
        self,
        criterion: EvaluationCriterion,
        response: str,
        negate: bool = False
    ) -> tuple[bool, str]:
        """
        Check if response contains (or doesn't contain) specified values.
        """
        if not criterion.values:
            return not negate, criterion.description or "No values to check"

        check_response = response if criterion.case_sensitive else response.lower()

        for value in criterion.values:
            check_value = value if criterion.case_sensitive else value.lower()
            found = check_value in check_response

            if negate:
                if found:
                    return False, f"Contains forbidden '{value}'"
            else:
                if found:
                    return True, f"Contains '{value}'"

        if negate:
            return True, criterion.description or "Does not contain forbidden values"
        else:
            return False, criterion.description or f"Missing required content: {criterion.values}"

    def _check_regex(
        self,
        criterion: EvaluationCriterion,
        response: str,
        negate: bool = False
    ) -> tuple[bool, str]:
        """
        Check if response matches (or doesn't match) regex pattern.
        """
        if not criterion.pattern:
            return not negate, criterion.description or "No pattern to check"

        flags = 0 if criterion.case_sensitive else re.IGNORECASE

        try:
            match = re.search(criterion.pattern, response, flags)
            found = match is not None

            if negate:
                if found:
                    return False, f"Matches forbidden pattern '{criterion.pattern}'"
                return True, criterion.description or f"Does not match forbidden pattern"
            else:
                if found:
                    return True, f"Matches pattern '{criterion.pattern}'"
                return False, criterion.description or f"Does not match required pattern"

        except re.error as e:
            return False, f"Invalid regex pattern: {e}"

    def _check_length(
        self,
        criterion: EvaluationCriterion,
        response: str
    ) -> tuple[bool, str]:
        """
        Check if response word count is within specified range.
        """
        words = response.split()
        word_count = len(words)

        min_words = criterion.min_words or 0
        max_words = criterion.max_words

        if word_count < min_words:
            return False, f"Too short: {word_count} words (min: {min_words})"

        if max_words is not None and word_count > max_words:
            return False, f"Too long: {word_count} words (max: {max_words})"

        range_str = f"[{min_words}, {max_words if max_words else '∞'}]"
        return True, f"Word count {word_count} in range {range_str}"

    def _check_semantic(
        self,
        criterion: EvaluationCriterion,
        response: str
    ) -> tuple[bool, str]:
        """
        Check semantic similarity to reference text.

        Note: This is a placeholder - actual implementation would
        use embeddings for semantic similarity.
        """
        if not criterion.reference_text:
            return False, "No reference text for semantic check"

        # Placeholder: Use simple word overlap as proxy
        # In production, use actual embeddings
        response_words = set(response.lower().split())
        reference_words = set(criterion.reference_text.lower().split())

        if not reference_words:
            return False, "Empty reference text"

        overlap = len(response_words & reference_words)
        similarity = overlap / len(reference_words)

        threshold = criterion.threshold or self.semantic_threshold
        passed = similarity >= threshold

        desc = f"Semantic similarity: {similarity:.2f} (threshold: {threshold})"
        return passed, desc

    def _check_all_of(
        self,
        criterion: EvaluationCriterion,
        response: str
    ) -> tuple[bool, str]:
        """
        Check if ALL sub-criteria match.
        """
        if not criterion.sub_criteria:
            return True, criterion.description or "No sub-criteria (vacuously true)"

        results = []
        for sub in criterion.sub_criteria:
            matched, desc = self._check_criterion(sub, response)
            results.append((matched, desc))

        all_passed = all(r[0] for r in results)

        if all_passed:
            return True, criterion.description or "All criteria matched"
        else:
            failed = [r[1] for r in results if not r[0]]
            return False, f"Not all criteria matched. Failed: {failed}"

    def _check_any_of(
        self,
        criterion: EvaluationCriterion,
        response: str
    ) -> tuple[bool, str]:
        """
        Check if ANY sub-criterion matches.
        """
        if not criterion.sub_criteria:
            return False, criterion.description or "No sub-criteria"

        for sub in criterion.sub_criteria:
            matched, desc = self._check_criterion(sub, response)
            if matched:
                return True, desc

        return False, criterion.description or "No criteria matched"


class WeightedEvaluator(ProbeEvaluator):
    """
    Extended evaluator with weighted scoring for complex assessments.
    """

    def evaluate_weighted(
        self,
        probe: Probe,
        response: str
    ) -> tuple[ProbeResult, float, dict]:
        """
        Evaluate with detailed weighted breakdown.

        Returns:
            Tuple of:
            - ProbeResult
            - Overall score
            - Detailed breakdown dict
        """
        result, score, passed, failed, notes = self.evaluate(probe, response)

        breakdown = {
            "result": result.value,
            "score": score,
            "passed_criteria": passed,
            "failed_criteria": failed,
            "notes": notes,
            "response_length": len(response.split()),
            "probe_weight": probe.weight,
            "is_required": probe.required,
        }

        return result, score, breakdown

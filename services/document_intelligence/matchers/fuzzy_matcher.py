"""
Fuzzy matching for entity resolution.

Uses fuzzy string matching algorithms to calculate similarity scores
between entity names. Leverages the shared fuzzy_matcher utilities.
"""

from typing import Optional

from lib.shared.local_assistant_shared.utils.fuzzy_matcher import (
    fuzzy_match_name,
    calculate_token_overlap,
    is_high_confidence_match,
)


class FuzzyMatcher:
    """
    Fuzzy string matching for entity names.

    Uses Levenshtein-based similarity and token overlap for robust matching.
    Returns confidence scores from 0.0 (no match) to 1.0 (perfect match).
    """

    def __init__(self, similarity_threshold: float = 0.90):
        """
        Initialize fuzzy matcher.

        Args:
            similarity_threshold: Minimum score for a match (default: 0.90)
        """
        self.similarity_threshold = similarity_threshold

    def match(self, candidate_name: str, target_name: str) -> float:
        """
        Calculate fuzzy match score between two names.

        Uses the shared fuzzy_match_name utility which handles:
        - Unicode normalization
        - Business suffix removal (Inc., LLC, Corp., etc.)
        - Punctuation removal
        - Whitespace normalization

        Args:
            candidate_name: Name from document
            target_name: Name from database

        Returns:
            Similarity score from 0.0 to 1.0

        Examples:
            >>> matcher = FuzzyMatcher()
            >>> matcher.match("Clipboard Health", "Clipboard Health Inc.")
            1.0

            >>> matcher.match("ACME Corporation", "ACME Corp")
            1.0

            >>> score = matcher.match("ACME Corp", "XYZ Corp")
            >>> score < 0.5
            True
        """
        if not candidate_name or not target_name:
            return 0.0

        return fuzzy_match_name(candidate_name, target_name, threshold=self.similarity_threshold)

    def match_with_token_overlap(
        self,
        candidate_name: str,
        target_name: str,
        fuzzy_weight: float = 0.7,
        token_weight: float = 0.3,
    ) -> float:
        """
        Calculate combined fuzzy + token overlap score.

        Uses weighted combination of fuzzy string matching and token overlap
        for more robust matching when names have reordered words.

        Args:
            candidate_name: Name from document
            target_name: Name from database
            fuzzy_weight: Weight for fuzzy score (default: 0.7)
            token_weight: Weight for token overlap (default: 0.3)

        Returns:
            Weighted similarity score from 0.0 to 1.0

        Examples:
            >>> matcher = FuzzyMatcher()
            >>> matcher.match_with_token_overlap("ACME Corp Inc.", "Inc. ACME Corp")
            # Returns high score due to token overlap
        """
        if not candidate_name or not target_name:
            return 0.0

        fuzzy_score = fuzzy_match_name(candidate_name, target_name)
        token_score = calculate_token_overlap(candidate_name, target_name)

        # Weighted average
        combined_score = (fuzzy_weight * fuzzy_score) + (token_weight * token_score)

        return round(combined_score, 3)

    def is_high_confidence(
        self,
        candidate_name: str,
        target_name: str,
        fuzzy_threshold: Optional[float] = None,
        token_threshold: float = 0.60,
    ) -> bool:
        """
        Determine if match is high confidence.

        Args:
            candidate_name: Name from document
            target_name: Name from database
            fuzzy_threshold: Custom fuzzy threshold (default: use instance threshold)
            token_threshold: Minimum token overlap (default: 0.60)

        Returns:
            True if high confidence match, False otherwise
        """
        if fuzzy_threshold is None:
            fuzzy_threshold = self.similarity_threshold

        return is_high_confidence_match(
            candidate_name,
            target_name,
            fuzzy_threshold=fuzzy_threshold,
            token_threshold=token_threshold,
        )

    def match_with_address(
        self,
        candidate_name: str,
        target_name: str,
        candidate_address: Optional[str],
        target_address: Optional[str],
        name_weight: float = 0.7,
        address_weight: float = 0.3,
    ) -> float:
        """
        Calculate combined name + address match score.

        Used for tier 4 matching when both name and address are available.
        Address similarity can help disambiguate entities with similar names.

        Args:
            candidate_name: Name from document
            target_name: Name from database
            candidate_address: Address from document
            target_address: Address from database
            name_weight: Weight for name score (default: 0.7)
            address_weight: Weight for address score (default: 0.3)

        Returns:
            Weighted similarity score from 0.0 to 1.0
        """
        name_score = self.match(candidate_name, target_name)

        # If no addresses provided, return name score only
        if not candidate_address or not target_address:
            return name_score

        # Calculate address similarity
        address_score = fuzzy_match_name(candidate_address, target_address)

        # Weighted average
        combined_score = (name_weight * name_score) + (address_weight * address_score)

        return round(combined_score, 3)

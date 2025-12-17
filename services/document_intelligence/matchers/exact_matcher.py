"""
Exact matching for entity resolution.

Provides high-confidence matching based on exact field values:
- tax_id (EIN, SSN, etc.)
- email address
- normalized name
"""

from typing import Optional


class ExactMatcher:
    """
    Exact field matching for entity resolution.

    Returns confidence score of 1.0 for exact matches, 0.0 otherwise.
    Used as first tier in cascade matching strategy.
    """

    def match_by_tax_id(self, candidate_tax_id: Optional[str], target_tax_id: Optional[str]) -> float:
        """
        Match entities by tax ID (EIN, SSN, etc.).

        Args:
            candidate_tax_id: Tax ID from document
            target_tax_id: Tax ID from database

        Returns:
            1.0 if exact match, 0.0 otherwise

        Examples:
            >>> matcher = ExactMatcher()
            >>> matcher.match_by_tax_id("12-3456789", "12-3456789")
            1.0

            >>> matcher.match_by_tax_id("12-3456789", "98-7654321")
            0.0

            >>> matcher.match_by_tax_id(None, "12-3456789")
            0.0
        """
        if not candidate_tax_id or not target_tax_id:
            return 0.0

        # Normalize tax IDs (remove dashes, spaces)
        norm_candidate = self._normalize_tax_id(candidate_tax_id)
        norm_target = self._normalize_tax_id(target_tax_id)

        return 1.0 if norm_candidate == norm_target else 0.0

    def match_by_email(self, candidate_email: Optional[str], target_email: Optional[str]) -> float:
        """
        Match entities by email address.

        Args:
            candidate_email: Email from document
            target_email: Email from database

        Returns:
            1.0 if exact match (case-insensitive), 0.0 otherwise

        Examples:
            >>> matcher = ExactMatcher()
            >>> matcher.match_by_email("john@example.com", "john@example.com")
            1.0

            >>> matcher.match_by_email("John@Example.COM", "john@example.com")
            1.0

            >>> matcher.match_by_email("john@example.com", "jane@example.com")
            0.0
        """
        if not candidate_email or not target_email:
            return 0.0

        # Email matching is case-insensitive
        return 1.0 if candidate_email.lower() == target_email.lower() else 0.0

    def match_by_normalized_name(self, candidate_name: str, target_name: str) -> float:
        """
        Match entities by normalized name.

        Args:
            candidate_name: Name from document
            target_name: Name from database

        Returns:
            1.0 if exact match after normalization, 0.0 otherwise

        Examples:
            >>> matcher = ExactMatcher()
            >>> matcher.match_by_normalized_name("ACME Corp", "acme corp")
            1.0

            >>> matcher.match_by_normalized_name("  ACME Corp.  ", "acme corp")
            1.0

            >>> matcher.match_by_normalized_name("ACME", "XYZ")
            0.0
        """
        if not candidate_name or not target_name:
            return 0.0

        norm_candidate = self._normalize_name(candidate_name)
        norm_target = self._normalize_name(target_name)

        return 1.0 if norm_candidate == norm_target else 0.0

    def _normalize_tax_id(self, tax_id: str) -> str:
        """
        Normalize tax ID for comparison.

        Removes dashes, spaces, and converts to uppercase.

        Args:
            tax_id: Raw tax ID

        Returns:
            Normalized tax ID
        """
        return tax_id.replace("-", "").replace(" ", "").strip().upper()

    def _normalize_name(self, name: str) -> str:
        """
        Normalize name for exact matching.

        Converts to lowercase, removes extra whitespace and punctuation.

        Args:
            name: Raw name

        Returns:
            Normalized name
        """
        import re

        # Convert to lowercase
        name = name.lower()

        # Remove punctuation (except spaces)
        name = re.sub(r'[^\w\s]', '', name)

        # Collapse whitespace
        name = ' '.join(name.split())

        return name.strip()

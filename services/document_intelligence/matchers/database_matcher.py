"""
Database-backed matching using PostgreSQL pg_trgm for fast text search.

Leverages PostgreSQL's trigram similarity for efficient fuzzy matching
against large datasets without loading all records into memory.
"""

from typing import List, Optional
from dataclasses import dataclass
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from memory.models import Party


@dataclass
class MatchCandidate:
    """
    Candidate match from database query.

    Attributes:
        party: Matched Party entity
        similarity: Similarity score from 0.0 to 1.0
        match_field: Field that was matched (name, tax_id, email)
    """

    party: Party
    similarity: float
    match_field: str


class DatabaseMatcher:
    """
    Fast database-backed entity matching using PostgreSQL pg_trgm.

    Uses PostgreSQL's trigram similarity operator (%) and similarity() function
    for efficient fuzzy text search against the parties table.

    Requires pg_trgm extension to be enabled:
        CREATE EXTENSION IF NOT EXISTS pg_trgm;
    """

    def __init__(self, similarity_threshold: float = 0.30):
        """
        Initialize database matcher.

        Args:
            similarity_threshold: Minimum pg_trgm similarity for results (default: 0.30)
                Lower threshold returns more candidates for further filtering.
        """
        self.similarity_threshold = similarity_threshold

    async def find_candidates_by_name(
        self,
        db: AsyncSession,
        search_name: str,
        kind: Optional[str] = None,
        limit: int = 5,
    ) -> List[MatchCandidate]:
        """
        Find candidate parties by name using trigram similarity.

        Uses PostgreSQL's % (similarity) operator for fast fuzzy matching.
        Returns top N candidates ordered by similarity score.

        Args:
            db: Database session
            search_name: Name to search for
            kind: Optional filter by party kind (org, person)
            limit: Maximum number of candidates to return (default: 5)

        Returns:
            List of MatchCandidate objects ordered by similarity (highest first)

        Examples:
            >>> candidates = await matcher.find_candidates_by_name(
            ...     db, "Clipboard Health", kind="org", limit=5
            ... )
            >>> candidates[0].similarity >= 0.9
            True
        """
        if not search_name or not search_name.strip():
            return []

        # Build query with similarity scoring
        query = select(
            Party,
            func.similarity(Party.name, search_name).label("sim_score"),
        ).where(
            # Use % operator for trigram similarity matching
            Party.name.op("%")(search_name)
        )

        # Optional filter by kind
        if kind:
            query = query.where(Party.kind == kind)

        # Order by similarity descending
        query = query.order_by(text("sim_score DESC")).limit(limit)

        # Execute query
        result = await db.execute(query)
        rows = result.all()

        # Convert to MatchCandidate objects
        candidates = []
        for party, similarity in rows:
            # Only include results above threshold
            if similarity >= self.similarity_threshold:
                candidates.append(
                    MatchCandidate(
                        party=party,
                        similarity=round(similarity, 3),
                        match_field="name",
                    )
                )

        return candidates

    async def find_by_tax_id(
        self,
        db: AsyncSession,
        tax_id: str,
    ) -> Optional[MatchCandidate]:
        """
        Find party by exact tax_id match.

        Args:
            db: Database session
            tax_id: Tax ID to search for

        Returns:
            MatchCandidate with 1.0 confidence if found, None otherwise
        """
        if not tax_id or not tax_id.strip():
            return None

        # Normalize tax ID (remove dashes, spaces)
        normalized_tax_id = tax_id.replace("-", "").replace(" ", "").strip().upper()

        # Query for exact match
        query = select(Party).where(
            func.replace(func.replace(func.upper(Party.tax_id), "-", ""), " ", "")
            == normalized_tax_id
        )

        result = await db.execute(query)
        party = result.scalar_one_or_none()

        if party:
            return MatchCandidate(
                party=party,
                similarity=1.0,
                match_field="tax_id",
            )

        return None

    async def find_by_email(
        self,
        db: AsyncSession,
        email: str,
    ) -> Optional[MatchCandidate]:
        """
        Find party by exact email match (case-insensitive).

        Args:
            db: Database session
            email: Email to search for

        Returns:
            MatchCandidate with 1.0 confidence if found, None otherwise
        """
        if not email or not email.strip():
            return None

        # Query for case-insensitive exact match
        query = select(Party).where(func.lower(Party.email) == email.lower())

        result = await db.execute(query)
        party = result.scalar_one_or_none()

        if party:
            return MatchCandidate(
                party=party,
                similarity=1.0,
                match_field="email",
            )

        return None

    async def find_by_name_and_address(
        self,
        db: AsyncSession,
        name: str,
        address: str,
        kind: Optional[str] = None,
        name_threshold: float = 0.80,
        address_threshold: float = 0.70,
        limit: int = 5,
    ) -> List[MatchCandidate]:
        """
        Find candidates using both name and address similarity.

        Useful for tier 4 matching when address is available.
        Combines name and address similarity scores.

        Args:
            db: Database session
            name: Name to search for
            address: Address to search for
            kind: Optional filter by party kind
            name_threshold: Minimum name similarity (default: 0.80)
            address_threshold: Minimum address similarity (default: 0.70)
            limit: Maximum number of candidates

        Returns:
            List of MatchCandidate objects with combined similarity scores
        """
        if not name or not address:
            return []

        # Build query with both name and address similarity
        query = (
            select(
                Party,
                func.similarity(Party.name, name).label("name_sim"),
                func.similarity(Party.address, address).label("addr_sim"),
            )
            .where(
                # Both fields must match above minimum threshold
                Party.name.op("%")(name),
                Party.address.op("%")(address),
            )
        )

        # Optional filter by kind
        if kind:
            query = query.where(Party.kind == kind)

        # Order by combined score (weighted average: 70% name, 30% address)
        query = query.order_by(
            text("(0.7 * name_sim + 0.3 * addr_sim) DESC")
        ).limit(limit)

        # Execute query
        result = await db.execute(query)
        rows = result.all()

        # Convert to MatchCandidate objects
        candidates = []
        for party, name_sim, addr_sim in rows:
            # Calculate combined score
            combined_score = 0.7 * name_sim + 0.3 * addr_sim

            # Only include if both fields meet thresholds
            if name_sim >= name_threshold and addr_sim >= address_threshold:
                candidates.append(
                    MatchCandidate(
                        party=party,
                        similarity=round(combined_score, 3),
                        match_field="name+address",
                    )
                )

        return candidates

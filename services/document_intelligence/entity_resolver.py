"""
Entity resolution with 5-tier cascade matching strategy.

Resolves vendor/party names from documents to existing database entities
using a cascading strategy from exact matches to fuzzy matching.

5-Tier Cascade:
    1. Exact match by tax_id (confidence: 1.0)
    2. Exact match by normalized name (confidence: 1.0)
    3. Fuzzy match >90% similarity (confidence: 0.90-0.99)
    4. Address + name match >80% similarity (confidence: 0.80-0.89)
    5. Manual review queue <80% confidence (create new party)
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from memory.models import Party, Role
from services.document_intelligence.matchers import (
    ExactMatcher,
    FuzzyMatcher,
    DatabaseMatcher,
)


@dataclass
class ResolutionResult:
    """
    Result of entity resolution process.

    Attributes:
        matched: True if existing party found, False if new party created
        party: Resolved or newly created Party entity
        confidence: Confidence score from 0.0 to 1.0
        reason: Explanation of how match was determined
        tier: Which tier of cascade produced the match (1-5)
    """

    matched: bool
    party: Party
    confidence: float
    reason: str
    tier: int


class EntityResolver:
    """
    Entity resolver with 5-tier cascade matching.

    Resolves vendor/party names from documents to existing database entities.
    Uses progressively more flexible matching strategies until a match is found
    or a new entity is created.

    Matching Tiers:
        1. Exact tax_id match (1.0 confidence)
        2. Exact normalized name match (1.0 confidence)
        3. Fuzzy name match >90% (0.90-0.99 confidence)
        4. Name + address match >80% (0.80-0.89 confidence)
        5. Create new party <80% (0.0 confidence, matched=False)

    Examples:
        >>> resolver = EntityResolver()
        >>> result = await resolver.resolve_vendor(
        ...     db, name="Clipboard Health", tax_id="12-3456789"
        ... )
        >>> result.matched
        True
        >>> result.confidence
        1.0
        >>> result.tier
        1
    """

    def __init__(
        self,
        fuzzy_threshold: float = 0.90,
        address_threshold: float = 0.80,
        db_similarity_threshold: float = 0.30,
    ):
        """
        Initialize entity resolver.

        Args:
            fuzzy_threshold: Minimum fuzzy match score for tier 3 (default: 0.90)
            address_threshold: Minimum combined score for tier 4 (default: 0.80)
            db_similarity_threshold: PostgreSQL pg_trgm threshold (default: 0.30)
        """
        self.fuzzy_threshold = fuzzy_threshold
        self.address_threshold = address_threshold

        # Initialize matchers
        self.exact_matcher = ExactMatcher()
        self.fuzzy_matcher = FuzzyMatcher(similarity_threshold=fuzzy_threshold)
        self.db_matcher = DatabaseMatcher(similarity_threshold=db_similarity_threshold)

    async def resolve_vendor(
        self,
        db: AsyncSession,
        name: Optional[str] = None,
        vendor_name: Optional[str] = None,  # For backwards compatibility
        address: Optional[str] = None,
        tax_id: Optional[str] = None,
        email: Optional[str] = None,
        vendor_info: Optional[Dict[str, Any]] = None,  # For backwards compatibility
    ) -> ResolutionResult:
        """
        Resolve vendor (organization) from document data.

        Supports both new API (name, address, tax_id) and old API (vendor_name, vendor_info)
        for backwards compatibility with existing pipeline code.

        Args:
            db: Database session
            name: Vendor name (new API)
            vendor_name: Vendor name (old API, for backwards compatibility)
            address: Optional vendor address
            tax_id: Optional tax ID (EIN)
            email: Optional email address
            vendor_info: Optional vendor info dict (old API)

        Returns:
            ResolutionResult with matched party and confidence score
        """
        # Handle backwards compatibility
        if vendor_name and not name:
            name = vendor_name

        if vendor_info:
            address = address or vendor_info.get("address")
            tax_id = tax_id or vendor_info.get("tax_id")
            email = email or vendor_info.get("email")

        if not name:
            raise ValueError("Vendor name is required")

        return await self.resolve_party(
            db=db,
            kind="org",
            name=name,
            address=address,
            tax_id=tax_id,
            email=email,
        )

    async def resolve_party(
        self,
        db: AsyncSession,
        kind: str,
        name: str,
        address: Optional[str] = None,
        tax_id: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> ResolutionResult:
        """
        Resolve party (vendor, customer, contact) using 5-tier cascade.

        Tries progressively more flexible matching strategies:
            1. Exact tax_id match
            2. Exact normalized name match
            3. Fuzzy name match >90%
            4. Name + address match >80%
            5. Create new party

        Args:
            db: Database session
            kind: Party kind ("org" or "person")
            name: Party name
            address: Optional address
            tax_id: Optional tax ID
            email: Optional email
            phone: Optional phone
            metadata: Optional metadata dict

        Returns:
            ResolutionResult with matched/created party and confidence score
        """
        # TIER 1: Exact tax_id match
        if tax_id:
            result = await self._tier1_tax_id_match(db, tax_id)
            if result:
                return result

        # TIER 2: Exact normalized name match
        result = await self._tier2_exact_name_match(db, kind, name)
        if result:
            return result

        # TIER 3: Fuzzy name match >90%
        result = await self._tier3_fuzzy_name_match(db, kind, name)
        if result:
            return result

        # TIER 4: Name + address match >80%
        if address:
            result = await self._tier4_name_address_match(db, kind, name, address)
            if result:
                return result

        # TIER 5: Create new party (no match found)
        return await self._tier5_create_new_party(
            db=db,
            kind=kind,
            name=name,
            address=address,
            tax_id=tax_id,
            email=email,
            phone=phone,
            metadata=metadata,
        )

    async def _tier1_tax_id_match(
        self,
        db: AsyncSession,
        tax_id: str,
    ) -> Optional[ResolutionResult]:
        """
        Tier 1: Exact tax_id match.

        Highest confidence match - tax IDs are unique identifiers.

        Returns:
            ResolutionResult with 1.0 confidence if found, None otherwise
        """
        candidate = await self.db_matcher.find_by_tax_id(db, tax_id)

        if candidate and candidate.similarity == 1.0:
            return ResolutionResult(
                matched=True,
                party=candidate.party,
                confidence=1.0,
                reason=f"Exact match on tax_id: {tax_id}",
                tier="1",
            )

        return None

    async def _tier2_exact_name_match(
        self,
        db: AsyncSession,
        kind: str,
        name: str,
    ) -> Optional[ResolutionResult]:
        """
        Tier 2: Exact normalized name match.

        Uses database query for exact match after normalization
        (lowercase, punctuation removal, whitespace collapse).

        Returns:
            ResolutionResult with 1.0 confidence if found, None otherwise
        """
        # Get top candidates from database
        candidates = await self.db_matcher.find_candidates_by_name(
            db=db,
            search_name=name,
            kind=kind,
            limit=10,  # Check more candidates for exact match
        )

        # Check for exact match using ExactMatcher
        for candidate in candidates:
            if self.exact_matcher.match_by_normalized_name(name, candidate.party.name) == 1.0:
                return ResolutionResult(
                    matched=True,
                    party=candidate.party,
                    confidence=1.0,
                    reason=f"Exact normalized name match: '{name}' == '{candidate.party.name}'",
                    tier="2",
                )

        return None

    async def _tier3_fuzzy_name_match(
        self,
        db: AsyncSession,
        kind: str,
        name: str,
    ) -> Optional[ResolutionResult]:
        """
        Tier 3: Fuzzy name match >90% similarity.

        Uses fuzzy string matching for names with minor variations
        (typos, abbreviations, business suffixes).

        Returns:
            ResolutionResult with 0.90-0.99 confidence if found, None otherwise
        """
        # Get top candidates from database
        candidates = await self.db_matcher.find_candidates_by_name(
            db=db,
            search_name=name,
            kind=kind,
            limit=5,
        )

        # Find best fuzzy match above threshold
        best_match = None
        best_score = 0.0

        for candidate in candidates:
            fuzzy_score = self.fuzzy_matcher.match(name, candidate.party.name)

            # Must meet threshold
            if fuzzy_score >= self.fuzzy_threshold and fuzzy_score > best_score:
                best_match = candidate
                best_score = fuzzy_score

        if best_match and best_score >= self.fuzzy_threshold:
            return ResolutionResult(
                matched=True,
                party=best_match.party,
                confidence=round(best_score, 3),
                reason=f"Fuzzy name match ({best_score:.2%}): '{name}' ≈ '{best_match.party.name}'",
                tier="3",
            )

        return None

    async def _tier4_name_address_match(
        self,
        db: AsyncSession,
        kind: str,
        name: str,
        address: str,
    ) -> Optional[ResolutionResult]:
        """
        Tier 4: Name + address match >80% similarity.

        Uses combined name and address similarity for disambiguation
        when multiple parties have similar names.

        Returns:
            ResolutionResult with 0.80-0.89 confidence if found, None otherwise
        """
        # Get candidates with both name and address
        candidates = await self.db_matcher.find_by_name_and_address(
            db=db,
            name=name,
            address=address,
            kind=kind,
            name_threshold=0.80,
            address_threshold=0.70,
            limit=5,
        )

        # Find best match above threshold
        best_match = None
        best_score = 0.0

        for candidate in candidates:
            # Combined score already calculated by DatabaseMatcher
            combined_score = candidate.similarity

            if combined_score >= self.address_threshold and combined_score > best_score:
                best_match = candidate
                best_score = combined_score

        if best_match and best_score >= self.address_threshold:
            return ResolutionResult(
                matched=True,
                party=best_match.party,
                confidence=round(best_score, 3),
                reason=f"Name + address match ({best_score:.2%}): '{name}' + '{address[:30]}...'",
                tier="4",
            )

        return None

    async def _tier5_create_new_party(
        self,
        db: AsyncSession,
        kind: str,
        name: str,
        address: Optional[str] = None,
        tax_id: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> ResolutionResult:
        """
        Tier 5: Create new party (no match found).

        When confidence is <80% for all matching strategies,
        create a new party entity. This goes into manual review queue.

        Returns:
            ResolutionResult with matched=False and 0.0 confidence
        """
        # Create new party
        new_party = Party(
            id=uuid.uuid4(),
            kind=kind,
            name=name,
            address=address,
            tax_id=tax_id,
            email=email,
            phone=phone,
            metadata_=metadata or {},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        # Add to database
        db.add(new_party)
        await db.flush()  # Flush instead of commit (pipeline manages transaction)

        return ResolutionResult(
            matched=False,
            party=new_party,
            confidence=0.0,
            reason=f"No match found - created new {kind}: '{name}'",
            tier="5",
        )

    async def get_or_create_role(
        self,
        db: AsyncSession,
        party_id: uuid.UUID,
        role_name: str = "vendor",
        user_id: Optional[uuid.UUID] = None
    ) -> Tuple[Role, bool]:
        """Get or create a role for a party.

        Args:
            db: Database session
            party_id: Party ID
            role_name: Role name (e.g., "vendor", "customer")
            user_id: Optional user ID

        Returns:
            Tuple of (Role, created)
        """
        # Check if role already exists
        result = await db.execute(
            select(Role).where(
                Role.party_id == party_id,
                Role.role_name == role_name
            )
        )
        existing_role = result.scalar_one_or_none()

        if existing_role:
            return existing_role, False

        # Create new role
        new_role = Role(
            id=uuid.uuid4(),
            party_id=party_id,
            user_id=user_id,
            role_name=role_name,
            context=None,
            permissions=None,
            created_at=datetime.utcnow()
        )

        db.add(new_role)
        await db.flush()

        return new_role, True

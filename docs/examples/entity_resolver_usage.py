"""
Example usage of Entity Resolver with 5-tier cascade matching.

Demonstrates the complete entity resolution workflow from vendor extraction
to database resolution with confidence scoring.
"""

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from services.document_intelligence.entity_resolver import EntityResolver
from memory.models import Base


async def main():
    """Example entity resolution workflow."""

    # Setup database connection
    database_url = "postgresql+asyncpg://user:password@localhost:5432/assistant"
    engine = create_async_engine(database_url, echo=True)

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # Initialize resolver with custom thresholds
        resolver = EntityResolver(
            fuzzy_threshold=0.90,  # Tier 3: 90% similarity required
            address_threshold=0.80,  # Tier 4: 80% combined score required
            db_similarity_threshold=0.30,  # PostgreSQL pg_trgm threshold
        )

        print("=" * 80)
        print("Entity Resolver - 5-Tier Cascade Example")
        print("=" * 80)

        # ========== TIER 1: Exact tax_id match ==========
        print("\n[Tier 1] Exact tax_id match:")
        print("-" * 40)

        result = await resolver.resolve_vendor(
            db=db,
            name="Unknown Vendor Name",
            tax_id="12-3456789",  # Existing vendor's tax ID
        )

        print(f"Matched: {result.matched}")
        print(f"Confidence: {result.confidence:.2f}")
        print(f"Tier: {result.tier}")
        print(f"Reason: {result.reason}")
        print(f"Party: {result.party.name}")

        # ========== TIER 2: Exact normalized name match ==========
        print("\n[Tier 2] Exact normalized name match:")
        print("-" * 40)

        result = await resolver.resolve_vendor(
            db=db,
            name="CLIPBOARD HEALTH",  # Different case, no tax_id
        )

        print(f"Matched: {result.matched}")
        print(f"Confidence: {result.confidence:.2f}")
        print(f"Tier: {result.tier}")
        print(f"Reason: {result.reason}")
        print(f"Party: {result.party.name}")

        # ========== TIER 3: Fuzzy name match >90% ==========
        print("\n[Tier 3] Fuzzy name match >90%:")
        print("-" * 40)

        result = await resolver.resolve_vendor(
            db=db,
            name="Clipboard Health Inc",  # With business suffix
        )

        print(f"Matched: {result.matched}")
        print(f"Confidence: {result.confidence:.2f}")
        print(f"Tier: {result.tier}")
        print(f"Reason: {result.reason}")
        print(f"Party: {result.party.name}")

        # ========== TIER 4: Name + address match >80% ==========
        print("\n[Tier 4] Name + address match >80%:")
        print("-" * 40)

        result = await resolver.resolve_vendor(
            db=db,
            name="ACME Corp",  # Slight variation
            address="123 Main St, New York, NY",  # Abbreviated address
        )

        print(f"Matched: {result.matched}")
        print(f"Confidence: {result.confidence:.2f}")
        print(f"Tier: {result.tier}")
        print(f"Reason: {result.reason}")
        print(f"Party: {result.party.name}")

        # ========== TIER 5: Create new party ==========
        print("\n[Tier 5] Create new party (no match):")
        print("-" * 40)

        result = await resolver.resolve_vendor(
            db=db,
            name="Brand New Vendor Inc",
            tax_id="99-9999999",
            address="999 New Street, Boston, MA 02101",
            email="contact@newvendor.com",
        )

        print(f"Matched: {result.matched}")
        print(f"Confidence: {result.confidence:.2f}")
        print(f"Tier: {result.tier}")
        print(f"Reason: {result.reason}")
        print(f"Party: {result.party.name}")

        await db.commit()

        # ========== Cascade demonstration ==========
        print("\n" + "=" * 80)
        print("Cascade Demonstration: Resolver tries all tiers until match")
        print("=" * 80)

        # This vendor exists in database with tax_id="12-3456789"
        # But we don't provide tax_id, so it will cascade through tiers

        result = await resolver.resolve_vendor(
            db=db,
            name="clipboard health",  # lowercase, no tax_id
        )

        print(f"\nSearch: 'clipboard health' (no tax_id provided)")
        print(f"Tier 1 (tax_id): SKIPPED (no tax_id provided)")
        print(f"Tier 2 (exact name): MATCHED! -> {result.reason}")
        print(f"Final result: {result.party.name} (confidence: {result.confidence:.2f})")

        # ========== Deduplication example ==========
        print("\n" + "=" * 80)
        print("Deduplication: Multiple variations resolve to same entity")
        print("=" * 80)

        variations = [
            "Clipboard Health",
            "CLIPBOARD HEALTH",
            "Clipboard Health Inc",
            "Clipboard Health (Twomagnets Inc.)",
        ]

        print("\nAll variations should resolve to the same party:")
        for name in variations:
            result = await resolver.resolve_vendor(db=db, name=name)
            print(f"  '{name}' -> {result.party.name} (tier {result.tier}, {result.confidence:.2f})")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

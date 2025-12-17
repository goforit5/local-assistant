"""
Integration tests for entity resolution with real database.

Tests entity resolver against actual PostgreSQL database with pg_trgm extension.
Validates vendor deduplication accuracy and concurrent resolution handling.
"""

import pytest
import uuid
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from memory.models import Base, Party
from services.document_intelligence.entity_resolver import EntityResolver


@pytest.fixture(scope="module")
async def test_engine():
    """Create test database engine."""
    # Use test database URL from environment
    database_url = "postgresql+asyncpg://test:test@localhost:5432/test_assistant"

    engine = create_async_engine(
        database_url,
        poolclass=NullPool,  # No connection pooling for tests
        echo=False,
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
async def db_session(test_engine):
    """Create a database session for each test."""
    async_session = sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        # Enable pg_trgm extension
        try:
            await session.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
            await session.commit()
        except Exception:
            # Extension might already exist
            await session.rollback()

        yield session

        # Cleanup - delete all parties after each test
        await session.execute(text("DELETE FROM parties"))
        await session.commit()


@pytest.fixture
def resolver():
    """Create EntityResolver instance."""
    return EntityResolver(
        fuzzy_threshold=0.90,
        address_threshold=0.80,
        db_similarity_threshold=0.30,
    )


@pytest.fixture
async def seed_vendors(db_session):
    """Seed database with test vendor data."""
    vendors = [
        Party(
            id=uuid.uuid4(),
            kind="org",
            name="Clipboard Health",
            tax_id="12-3456789",
            address="P.O. Box 103125, Pasadena, CA 91189",
            email="contact@clipboardhealth.com",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        ),
        Party(
            id=uuid.uuid4(),
            kind="org",
            name="ACME Corporation",
            tax_id="98-7654321",
            address="123 Main Street, New York, NY 10001",
            email="info@acme.com",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        ),
        Party(
            id=uuid.uuid4(),
            kind="org",
            name="Global Tech Solutions LLC",
            tax_id="45-6789012",
            address="456 Tech Blvd, San Francisco, CA 94102",
            email="support@globaltech.com",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        ),
        Party(
            id=uuid.uuid4(),
            kind="org",
            name="XYZ Industries",
            tax_id=None,
            address="789 Industrial Way, Chicago, IL 60601",
            email="contact@xyzind.com",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        ),
    ]

    for vendor in vendors:
        db_session.add(vendor)

    await db_session.commit()

    return vendors


class TestEntityResolutionIntegration:
    """Integration tests for entity resolution."""

    async def test_tier1_exact_tax_id_match(self, resolver, db_session, seed_vendors):
        """Test Tier 1: Exact tax_id match with real database."""
        result = await resolver.resolve_vendor(
            db=db_session,
            name="Some Random Name",  # Name doesn't matter
            tax_id="12-3456789",  # Clipboard Health's tax ID
        )

        assert result.matched is True
        assert result.confidence == 1.0
        assert result.tier == 1
        assert result.party.name == "Clipboard Health"
        assert "tax_id" in result.reason.lower()

    async def test_tier2_exact_normalized_name_match(self, resolver, db_session, seed_vendors):
        """Test Tier 2: Exact normalized name match."""
        result = await resolver.resolve_vendor(
            db=db_session,
            name="CLIPBOARD HEALTH",  # Different case, no tax_id
        )

        assert result.matched is True
        assert result.confidence == 1.0
        assert result.tier == 2
        assert result.party.name == "Clipboard Health"

    async def test_tier3_fuzzy_name_match(self, resolver, db_session, seed_vendors):
        """Test Tier 3: Fuzzy name match with business suffix variation."""
        result = await resolver.resolve_vendor(
            db=db_session,
            name="Global Tech Solutions",  # Without LLC suffix
        )

        assert result.matched is True
        assert result.confidence >= 0.90
        assert result.tier == 3
        assert result.party.name == "Global Tech Solutions LLC"

    async def test_tier3_fuzzy_with_parenthetical(self, resolver, db_session, seed_vendors):
        """Test Tier 3: Fuzzy match with parenthetical content."""
        # Add vendor with parenthetical
        party = Party(
            id=uuid.uuid4(),
            kind="org",
            name="Clipboard Health (Twomagnets Inc.)",
            tax_id="12-9999999",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(party)
        await db_session.commit()

        result = await resolver.resolve_vendor(
            db=db_session,
            name="Clipboard Health",  # Without parenthetical
        )

        assert result.matched is True
        # Should match either the original or the parenthetical one
        assert "Clipboard Health" in result.party.name

    async def test_tier4_name_address_match(self, resolver, db_session, seed_vendors):
        """Test Tier 4: Combined name + address matching."""
        result = await resolver.resolve_vendor(
            db=db_session,
            name="ACME Corp",  # Slight variation
            address="123 Main St, New York, NY",  # Abbreviated address
        )

        assert result.matched is True
        assert result.confidence >= 0.80
        # Could be tier 2, 3, or 4 depending on fuzzy match score
        assert result.tier in [2, 3, 4]
        assert result.party.name == "ACME Corporation"

    async def test_tier5_create_new_vendor(self, resolver, db_session, seed_vendors):
        """Test Tier 5: Create new vendor when no match found."""
        initial_count = len(seed_vendors)

        result = await resolver.resolve_vendor(
            db=db_session,
            name="Brand New Vendor Inc",
            tax_id="11-1111111",
            address="999 New Street, Boston, MA 02101",
        )

        assert result.matched is False
        assert result.confidence == 0.0
        assert result.tier == 5
        assert result.party.name == "Brand New Vendor Inc"

        # Verify party was created in database
        result2 = await resolver.resolve_vendor(
            db=db_session,
            name="Brand New Vendor Inc",
        )
        assert result2.matched is True
        assert result2.tier == 2  # Should find exact match now

    async def test_vendor_deduplication_accuracy(self, resolver, db_session):
        """Test vendor deduplication accuracy with real-world variations.

        Target: >90% accuracy on detecting duplicates.
        """
        # Create a vendor
        original = Party(
            id=uuid.uuid4(),
            kind="org",
            name="Clipboard Health",
            tax_id="12-3456789",
            address="P.O. Box 103125, Pasadena, CA 91189",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(original)
        await db_session.commit()

        # Test variations that should match (true positives)
        variations = [
            ("Clipboard Health", True),  # Exact
            ("CLIPBOARD HEALTH", True),  # Case variation
            ("Clipboard Health Inc", True),  # With suffix
            ("Clipboard Health Inc.", True),  # With suffix and period
            ("Clipboard Health (Twomagnets Inc.)", True),  # With parenthetical
            ("clipboard health", True),  # Lowercase
            ("Clipbord Health", True),  # Typo (should still match with fuzzy)
            ("Completely Different Vendor", False),  # Should NOT match
            ("XYZ Corporation", False),  # Should NOT match
        ]

        correct = 0
        total = len(variations)

        for name, should_match in variations:
            result = await resolver.resolve_vendor(db=db_session, name=name)

            # Check if result matches expectation
            if should_match and result.matched and result.party.id == original.id:
                correct += 1
            elif not should_match and (not result.matched or result.party.id != original.id):
                correct += 1

        accuracy = correct / total
        assert accuracy >= 0.90, f"Deduplication accuracy {accuracy:.2%} < 90%"

    async def test_concurrent_resolution_requests(self, resolver, db_session, seed_vendors):
        """Test handling concurrent resolution requests.

        Simulates multiple simultaneous vendor lookups.
        """
        import asyncio

        # Simulate concurrent requests for same vendor
        tasks = [
            resolver.resolve_vendor(db=db_session, name="Clipboard Health"),
            resolver.resolve_vendor(db=db_session, name="ACME Corporation"),
            resolver.resolve_vendor(db=db_session, name="Global Tech Solutions"),
            resolver.resolve_vendor(db=db_session, name="Clipboard Health"),  # Duplicate
            resolver.resolve_vendor(db=db_session, name="ACME Corp"),  # Variation
        ]

        results = await asyncio.gather(*tasks)

        # All should succeed
        assert all(r.matched for r in results)

        # First and fourth should match same party
        assert results[0].party.id == results[3].party.id

    async def test_special_characters_and_unicode(self, resolver, db_session):
        """Test handling special characters and Unicode in vendor names."""
        # Create vendor with special characters
        party = Party(
            id=uuid.uuid4(),
            kind="org",
            name="Café René's Bakery & Bistro",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(party)
        await db_session.commit()

        # Test Unicode matching
        result = await resolver.resolve_vendor(
            db=db_session,
            name="Cafe Rene's Bakery & Bistro",  # Without accents
        )

        assert result.matched is True
        assert "Café René" in result.party.name

    async def test_address_disambiguation(self, resolver, db_session):
        """Test address helps disambiguate vendors with similar names."""
        # Create two vendors with similar names but different addresses
        party1 = Party(
            id=uuid.uuid4(),
            kind="org",
            name="ABC Services",
            address="123 Main St, New York, NY 10001",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        party2 = Party(
            id=uuid.uuid4(),
            kind="org",
            name="ABC Services",
            address="456 Oak Ave, Los Angeles, CA 90001",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(party1)
        db_session.add(party2)
        await db_session.commit()

        # Resolve with NY address - should match party1
        result1 = await resolver.resolve_vendor(
            db=db_session,
            name="ABC Services",
            address="123 Main Street, New York, NY",
        )

        # Resolve with LA address - should match party2
        result2 = await resolver.resolve_vendor(
            db=db_session,
            name="ABC Services",
            address="456 Oak Avenue, Los Angeles, CA",
        )

        assert result1.party.id == party1.id
        assert result2.party.id == party2.id

    async def test_case_insensitive_tax_id_matching(self, resolver, db_session):
        """Test tax_id matching is case-insensitive and handles formatting."""
        party = Party(
            id=uuid.uuid4(),
            kind="org",
            name="Test Corp",
            tax_id="ab-1234567",  # Lowercase
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(party)
        await db_session.commit()

        # Try matching with uppercase and different formatting
        result = await resolver.resolve_vendor(
            db=db_session,
            name="Different Name",
            tax_id="AB1234567",  # Uppercase, no dash
        )

        assert result.matched is True
        assert result.tier == 1
        assert result.party.id == party.id

    async def test_empty_database_creates_new_party(self, resolver, db_session):
        """Test creating party in empty database."""
        # Database should be empty (cleaned up by fixture)

        result = await resolver.resolve_vendor(
            db=db_session,
            name="First Vendor",
            tax_id="00-0000000",
        )

        assert result.matched is False
        assert result.tier == 5
        assert result.party.name == "First Vendor"

        # Verify it was persisted
        await db_session.commit()  # Commit the transaction

        result2 = await resolver.resolve_vendor(
            db=db_session,
            name="First Vendor",
        )
        assert result2.matched is True

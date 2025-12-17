"""
Comprehensive unit tests for entity resolver with 5-tier cascade matching.

Tests all matching tiers, confidence scoring, and edge cases.
"""

import pytest
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from services.document_intelligence.entity_resolver import EntityResolver, ResolutionResult
from services.document_intelligence.matchers import ExactMatcher, FuzzyMatcher, DatabaseMatcher
from services.document_intelligence.matchers.database_matcher import MatchCandidate
from memory.models import Party


class TestExactMatcher:
    """Tests for ExactMatcher."""

    def test_match_by_tax_id_exact(self):
        """Test exact tax_id match."""
        matcher = ExactMatcher()
        assert matcher.match_by_tax_id("12-3456789", "12-3456789") == 1.0

    def test_match_by_tax_id_normalized(self):
        """Test tax_id match with different formatting."""
        matcher = ExactMatcher()
        # Should normalize by removing dashes and spaces
        assert matcher.match_by_tax_id("12-3456789", "123456789") == 1.0
        assert matcher.match_by_tax_id("12 3456789", "12-3456789") == 1.0

    def test_match_by_tax_id_no_match(self):
        """Test tax_id mismatch."""
        matcher = ExactMatcher()
        assert matcher.match_by_tax_id("12-3456789", "98-7654321") == 0.0

    def test_match_by_tax_id_none(self):
        """Test tax_id match with None values."""
        matcher = ExactMatcher()
        assert matcher.match_by_tax_id(None, "12-3456789") == 0.0
        assert matcher.match_by_tax_id("12-3456789", None) == 0.0
        assert matcher.match_by_tax_id(None, None) == 0.0

    def test_match_by_email_exact(self):
        """Test exact email match."""
        matcher = ExactMatcher()
        assert matcher.match_by_email("john@example.com", "john@example.com") == 1.0

    def test_match_by_email_case_insensitive(self):
        """Test email match is case-insensitive."""
        matcher = ExactMatcher()
        assert matcher.match_by_email("John@Example.COM", "john@example.com") == 1.0

    def test_match_by_email_no_match(self):
        """Test email mismatch."""
        matcher = ExactMatcher()
        assert matcher.match_by_email("john@example.com", "jane@example.com") == 0.0

    def test_match_by_normalized_name_exact(self):
        """Test exact normalized name match."""
        matcher = ExactMatcher()
        assert matcher.match_by_normalized_name("ACME Corp", "acme corp") == 1.0

    def test_match_by_normalized_name_with_punctuation(self):
        """Test name match ignores punctuation."""
        matcher = ExactMatcher()
        assert matcher.match_by_normalized_name("ACME Corp.", "acme corp") == 1.0
        assert matcher.match_by_normalized_name("ACME, Corp!", "acme corp") == 1.0

    def test_match_by_normalized_name_with_whitespace(self):
        """Test name match handles whitespace."""
        matcher = ExactMatcher()
        assert matcher.match_by_normalized_name("  ACME   Corp  ", "acme corp") == 1.0

    def test_match_by_normalized_name_no_match(self):
        """Test normalized name mismatch."""
        matcher = ExactMatcher()
        assert matcher.match_by_normalized_name("ACME Corp", "XYZ Corp") == 0.0


class TestFuzzyMatcher:
    """Tests for FuzzyMatcher."""

    def test_match_identical_names(self):
        """Test fuzzy match with identical names."""
        matcher = FuzzyMatcher(similarity_threshold=0.90)
        score = matcher.match("Clipboard Health", "Clipboard Health")
        assert score == 1.0

    def test_match_with_business_suffix(self):
        """Test fuzzy match handles business suffixes."""
        matcher = FuzzyMatcher(similarity_threshold=0.90)
        # Should normalize and match despite different suffixes
        score = matcher.match("ACME Corporation", "ACME Corp")
        assert score >= 0.95

    def test_match_with_parenthetical(self):
        """Test fuzzy match handles parenthetical content."""
        matcher = FuzzyMatcher(similarity_threshold=0.90)
        score = matcher.match("Clipboard Health", "Clipboard Health (Twomagnets Inc.)")
        assert score >= 0.95

    def test_match_typo_variation(self):
        """Test fuzzy match detects typos."""
        matcher = FuzzyMatcher(similarity_threshold=0.90)
        score = matcher.match("Clipboard Health", "Clipbord Health")
        # Should be high but not perfect
        assert 0.85 <= score < 1.0

    def test_match_completely_different(self):
        """Test fuzzy match with completely different names."""
        matcher = FuzzyMatcher(similarity_threshold=0.90)
        score = matcher.match("ACME Corp", "XYZ Industries")
        assert score < 0.5

    def test_match_empty_string(self):
        """Test fuzzy match with empty strings."""
        matcher = FuzzyMatcher()
        assert matcher.match("", "ACME") == 0.0
        assert matcher.match("ACME", "") == 0.0
        assert matcher.match("", "") == 0.0

    def test_match_with_token_overlap(self):
        """Test combined fuzzy + token overlap matching."""
        matcher = FuzzyMatcher()
        # Words in different order should still have some overlap
        score = matcher.match_with_token_overlap("ACME Corp Inc", "Inc ACME Corp")
        # Token overlap is weighted with fuzzy, score should be moderate
        assert score >= 0.40

    def test_is_high_confidence_true(self):
        """Test high confidence detection."""
        matcher = FuzzyMatcher(similarity_threshold=0.90)
        assert matcher.is_high_confidence("Clipboard Health Inc", "Clipboard Health")

    def test_is_high_confidence_false(self):
        """Test low confidence detection."""
        matcher = FuzzyMatcher(similarity_threshold=0.90)
        assert not matcher.is_high_confidence("ACME Corp", "XYZ Corp")

    def test_match_with_address_both_provided(self):
        """Test name + address matching."""
        matcher = FuzzyMatcher()
        score = matcher.match_with_address(
            candidate_name="ACME Corp",
            target_name="ACME Corporation",
            candidate_address="123 Main St, San Francisco, CA",
            target_address="123 Main Street, San Francisco, CA",
        )
        # Should be high due to both name and address similarity
        assert score >= 0.85

    def test_match_with_address_only_name(self):
        """Test address matching falls back to name only."""
        matcher = FuzzyMatcher()
        score = matcher.match_with_address(
            candidate_name="ACME Corp",
            target_name="ACME Corporation",
            candidate_address=None,
            target_address="123 Main St",
        )
        # Should return just name score
        assert score >= 0.90


class TestDatabaseMatcher:
    """Tests for DatabaseMatcher."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return AsyncMock()

    @pytest.fixture
    def matcher(self):
        """Create a DatabaseMatcher instance."""
        return DatabaseMatcher(similarity_threshold=0.30)

    @pytest.fixture
    def sample_party(self):
        """Create a sample Party for testing."""
        return Party(
            id=uuid.uuid4(),
            kind="org",
            name="Clipboard Health",
            tax_id="12-3456789",
            address="123 Main St, San Francisco, CA",
            email="contact@clipboardhealth.com",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

    async def test_find_candidates_by_name_success(self, matcher, mock_db, sample_party):
        """Test finding candidates by name."""
        # Mock database response
        mock_result = MagicMock()
        mock_result.all.return_value = [(sample_party, 0.95)]
        mock_db.execute.return_value = mock_result

        candidates = await matcher.find_candidates_by_name(
            db=mock_db,
            search_name="Clipboard Health",
            kind="org",
            limit=5,
        )

        assert len(candidates) == 1
        assert candidates[0].party.name == "Clipboard Health"
        assert candidates[0].similarity == 0.95
        assert candidates[0].match_field == "name"

    async def test_find_candidates_by_name_empty_search(self, matcher, mock_db):
        """Test finding candidates with empty search name."""
        candidates = await matcher.find_candidates_by_name(
            db=mock_db,
            search_name="",
            kind="org",
        )
        assert len(candidates) == 0

    async def test_find_candidates_by_name_below_threshold(self, matcher, mock_db, sample_party):
        """Test filtering candidates below similarity threshold."""
        # Mock database response with low similarity
        mock_result = MagicMock()
        mock_result.all.return_value = [(sample_party, 0.25)]  # Below 0.30 threshold
        mock_db.execute.return_value = mock_result

        candidates = await matcher.find_candidates_by_name(
            db=mock_db,
            search_name="Some Other Name",
            kind="org",
        )

        # Should filter out results below threshold
        assert len(candidates) == 0

    async def test_find_by_tax_id_success(self, matcher, mock_db, sample_party):
        """Test finding party by exact tax_id."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_party
        mock_db.execute.return_value = mock_result

        candidate = await matcher.find_by_tax_id(db=mock_db, tax_id="12-3456789")

        assert candidate is not None
        assert candidate.party.tax_id == "12-3456789"
        assert candidate.similarity == 1.0
        assert candidate.match_field == "tax_id"

    async def test_find_by_tax_id_not_found(self, matcher, mock_db):
        """Test tax_id not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        candidate = await matcher.find_by_tax_id(db=mock_db, tax_id="99-9999999")
        assert candidate is None

    async def test_find_by_tax_id_empty(self, matcher, mock_db):
        """Test tax_id search with empty value."""
        candidate = await matcher.find_by_tax_id(db=mock_db, tax_id="")
        assert candidate is None

    async def test_find_by_email_success(self, matcher, mock_db, sample_party):
        """Test finding party by email."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_party
        mock_db.execute.return_value = mock_result

        candidate = await matcher.find_by_email(db=mock_db, email="contact@clipboardhealth.com")

        assert candidate is not None
        assert candidate.party.email == "contact@clipboardhealth.com"
        assert candidate.similarity == 1.0
        assert candidate.match_field == "email"

    async def test_find_by_name_and_address_success(self, matcher, mock_db, sample_party):
        """Test finding candidates by name and address."""
        mock_result = MagicMock()
        # (party, name_sim, addr_sim)
        mock_result.all.return_value = [(sample_party, 0.90, 0.85)]
        mock_db.execute.return_value = mock_result

        candidates = await matcher.find_by_name_and_address(
            db=mock_db,
            name="Clipboard Health",
            address="123 Main St, San Francisco, CA",
            kind="org",
        )

        assert len(candidates) == 1
        assert candidates[0].party.name == "Clipboard Health"
        # Combined score: 0.7 * 0.90 + 0.3 * 0.85 = 0.885
        assert 0.88 <= candidates[0].similarity <= 0.89
        assert candidates[0].match_field == "name+address"

    async def test_find_by_name_and_address_empty(self, matcher, mock_db):
        """Test name+address search with missing data."""
        candidates = await matcher.find_by_name_and_address(
            db=mock_db,
            name="",
            address="123 Main St",
        )
        assert len(candidates) == 0

        candidates = await matcher.find_by_name_and_address(
            db=mock_db,
            name="ACME",
            address="",
        )
        assert len(candidates) == 0


class TestEntityResolver:
    """Tests for EntityResolver with 5-tier cascade."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = AsyncMock()
        # Mock flush and refresh for party creation
        db.flush = AsyncMock()
        db.refresh = AsyncMock()
        return db

    @pytest.fixture
    def resolver(self):
        """Create an EntityResolver instance."""
        return EntityResolver(
            fuzzy_threshold=0.90,
            address_threshold=0.80,
            db_similarity_threshold=0.30,
        )

    @pytest.fixture
    def sample_party(self):
        """Create a sample Party for testing."""
        return Party(
            id=uuid.uuid4(),
            kind="org",
            name="Clipboard Health",
            tax_id="12-3456789",
            address="123 Main St, San Francisco, CA",
            email="contact@clipboardhealth.com",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

    async def test_tier1_tax_id_match(self, resolver, mock_db, sample_party):
        """Test Tier 1: Exact tax_id match."""
        # Mock database matcher to return exact tax_id match
        with patch.object(
            resolver.db_matcher,
            "find_by_tax_id",
            return_value=MatchCandidate(party=sample_party, similarity=1.0, match_field="tax_id"),
        ):
            result = await resolver.resolve_vendor(
                db=mock_db,
                name="Some Vendor Name",  # Name doesn't matter with tax_id
                tax_id="12-3456789",
            )

            assert result.matched is True
            assert result.confidence == 1.0
            assert result.tier == 1
            assert "tax_id" in result.reason
            assert result.party.tax_id == "12-3456789"

    async def test_tier2_exact_name_match(self, resolver, mock_db, sample_party):
        """Test Tier 2: Exact normalized name match."""
        # Mock database matcher to return candidates
        with patch.object(
            resolver.db_matcher,
            "find_candidates_by_name",
            return_value=[MatchCandidate(party=sample_party, similarity=0.95, match_field="name")],
        ):
            # Mock exact matcher to return 1.0 for normalized match
            with patch.object(
                resolver.exact_matcher,
                "match_by_normalized_name",
                return_value=1.0,
            ):
                result = await resolver.resolve_vendor(
                    db=mock_db,
                    name="Clipboard Health",  # Exact match
                )

                assert result.matched is True
                assert result.confidence == 1.0
                assert result.tier == 2
                assert "normalized name match" in result.reason

    async def test_tier3_fuzzy_name_match(self, resolver, mock_db, sample_party):
        """Test Tier 3: Fuzzy name match >90%."""
        # Mock database matcher
        with patch.object(
            resolver.db_matcher,
            "find_candidates_by_name",
            return_value=[MatchCandidate(party=sample_party, similarity=0.85, match_field="name")],
        ):
            # Mock exact matcher to return no match
            with patch.object(resolver.exact_matcher, "match_by_normalized_name", return_value=0.0):
                # Mock fuzzy matcher to return high score
                with patch.object(resolver.fuzzy_matcher, "match", return_value=0.95):
                    result = await resolver.resolve_vendor(
                        db=mock_db,
                        name="Clipboard Health Inc",  # Fuzzy match
                    )

                    assert result.matched is True
                    assert result.confidence >= 0.90
                    assert result.tier == 3
                    assert "Fuzzy name match" in result.reason

    async def test_tier4_name_address_match(self, resolver, mock_db, sample_party):
        """Test Tier 4: Name + address match >80%."""
        # Mock database matcher to return no exact/fuzzy matches for name alone
        with patch.object(resolver.db_matcher, "find_candidates_by_name", return_value=[]):
            # Mock name+address matcher
            with patch.object(
                resolver.db_matcher,
                "find_by_name_and_address",
                return_value=[
                    MatchCandidate(party=sample_party, similarity=0.85, match_field="name+address")
                ],
            ):
                result = await resolver.resolve_vendor(
                    db=mock_db,
                    name="Clipboard Health Corp",
                    address="123 Main Street, SF, CA",
                )

                assert result.matched is True
                assert result.confidence >= 0.80
                assert result.tier == 4
                assert "address match" in result.reason

    async def test_tier5_create_new_party(self, resolver, mock_db):
        """Test Tier 5: Create new party when no match found."""
        # Mock all matchers to return no matches
        with patch.object(resolver.db_matcher, "find_by_tax_id", return_value=None):
            with patch.object(resolver.db_matcher, "find_candidates_by_name", return_value=[]):
                with patch.object(resolver.db_matcher, "find_by_name_and_address", return_value=[]):
                    result = await resolver.resolve_vendor(
                        db=mock_db,
                        name="Brand New Vendor",
                        address="456 New St",
                        tax_id="99-9999999",
                    )

                    assert result.matched is False
                    assert result.confidence == 0.0
                    assert result.tier == 5
                    assert "No match found" in result.reason
                    assert result.party.name == "Brand New Vendor"

                    # Verify party was added to database
                    mock_db.add.assert_called_once()
                    mock_db.flush.assert_called_once()

    async def test_resolve_vendor_backwards_compatibility(self, resolver, mock_db):
        """Test backwards compatibility with old API (vendor_name, vendor_info)."""
        with patch.object(resolver.db_matcher, "find_by_tax_id", return_value=None):
            with patch.object(resolver.db_matcher, "find_candidates_by_name", return_value=[]):
                with patch.object(resolver.db_matcher, "find_by_name_and_address", return_value=[]):
                    result = await resolver.resolve_vendor(
                        db=mock_db,
                        vendor_name="Old API Vendor",  # Old parameter
                        vendor_info={  # Old parameter
                            "address": "789 Old St",
                            "tax_id": "11-1111111",
                            "email": "old@example.com",
                        },
                    )

                    assert result.party.name == "Old API Vendor"
                    assert result.party.address == "789 Old St"
                    assert result.party.tax_id == "11-1111111"
                    assert result.party.email == "old@example.com"

    async def test_resolve_vendor_missing_name(self, resolver, mock_db):
        """Test error when vendor name is missing."""
        with pytest.raises(ValueError, match="Vendor name is required"):
            await resolver.resolve_vendor(db=mock_db, name=None)

    async def test_resolve_party_person_kind(self, resolver, mock_db):
        """Test resolving a person (not organization)."""
        with patch.object(resolver.db_matcher, "find_candidates_by_name", return_value=[]):
            result = await resolver.resolve_party(
                db=mock_db,
                kind="person",
                name="John Doe",
                email="john@example.com",
            )

            assert result.party.kind == "person"
            assert result.party.name == "John Doe"

    async def test_cascade_stops_at_first_match(self, resolver, mock_db, sample_party):
        """Test that cascade stops at first successful tier."""
        # Mock tier 1 to succeed
        with patch.object(
            resolver.db_matcher,
            "find_by_tax_id",
            return_value=MatchCandidate(party=sample_party, similarity=1.0, match_field="tax_id"),
        ) as mock_tier1:
            # Mock tier 2 (should not be called)
            with patch.object(
                resolver.db_matcher, "find_candidates_by_name", return_value=[]
            ) as mock_tier2:
                result = await resolver.resolve_vendor(
                    db=mock_db,
                    name="Any Name",
                    tax_id="12-3456789",
                )

                assert result.tier == 1
                mock_tier1.assert_called_once()
                # Tier 2 should NOT be called since tier 1 succeeded
                mock_tier2.assert_not_called()

    async def test_unicode_handling(self, resolver, mock_db):
        """Test entity resolver handles Unicode characters."""
        with patch.object(resolver.db_matcher, "find_candidates_by_name", return_value=[]):
            result = await resolver.resolve_vendor(
                db=mock_db,
                name="Café René's Bakery",  # Unicode characters
            )

            assert result.party.name == "Café René's Bakery"

    async def test_special_characters_in_name(self, resolver, mock_db):
        """Test entity resolver handles special characters."""
        with patch.object(resolver.db_matcher, "find_candidates_by_name", return_value=[]):
            result = await resolver.resolve_vendor(
                db=mock_db,
                name="ACME Corp. & Sons, LLC!",  # Special characters
            )

            assert result.party.name == "ACME Corp. & Sons, LLC!"

    async def test_empty_string_address(self, resolver, mock_db):
        """Test resolver handles empty string address (skips tier 4)."""
        with patch.object(resolver.db_matcher, "find_candidates_by_name", return_value=[]):
            result = await resolver.resolve_vendor(
                db=mock_db,
                name="Test Vendor",
                address="",  # Empty string should be treated as None
            )

            # Should skip tier 4 and go to tier 5
            assert result.tier == 5

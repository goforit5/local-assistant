"""
Text matching algorithms for aligning GPT-4o extracted values with PDF coordinates.

This module provides fuzzy matching and smart heuristics to match extracted
field values to their precise locations in the PDF document.
"""

import re
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from difflib import SequenceMatcher

from services.vision.bbox_extractor import BBoxExtractor, WordBBox


@dataclass
class MatchResult:
    """Result of matching extracted value to PDF coordinates."""
    field_name: str
    value: Any
    bbox: Optional[WordBBox]
    confidence: float  # 0-1
    match_method: str  # "exact", "fuzzy", "numeric", "phrase", "none"


class TextMatcher:
    """Match extracted text values to PDF coordinates."""

    # Header fields that are always on page 1
    HEADER_FIELDS_PAGE_1 = {
        'VendorName', 'VendorAddress', 'VendorTaxId',
        'CustomerName', 'CustomerId', 'CustomerAddress', 'ShippingAddress',
        'InvoiceId', 'InvoiceDate', 'DueDate', 'PurchaseOrder', 'PaymentTerms'
    }

    def __init__(self, extractor: BBoxExtractor, fuzzy_threshold: float = 0.85):
        """
        Initialize text matcher.

        Args:
            extractor: BBoxExtractor instance with cached word data
            fuzzy_threshold: Minimum similarity ratio for fuzzy matching (0-1)
        """
        self.extractor = extractor
        self.fuzzy_threshold = fuzzy_threshold

    def _infer_page_hint(self, field_name: str) -> Optional[int]:
        """
        Infer page number for a field based on its name.

        Args:
            field_name: Name of the field

        Returns:
            Page number (1-indexed) or None
        """
        # Header fields are always on page 1
        if field_name in self.HEADER_FIELDS_PAGE_1:
            return 1

        # Financial totals usually on first or last page, default to None
        return None

    def match_field(
        self,
        field_name: str,
        value: Any,
        page_hint: Optional[int] = None
    ) -> MatchResult:
        """
        Match a field value to its bounding box in the PDF.

        Args:
            field_name: Name of the field (e.g., "InvoiceDate")
            value: Extracted value
            page_hint: Optional page number hint (1-indexed)

        Returns:
            MatchResult with bbox and confidence
        """
        # Handle null/None values
        if value is None or value == "":
            return MatchResult(
                field_name=field_name,
                value=value,
                bbox=None,
                confidence=0.0,
                match_method="none"
            )

        # Infer page hint if not provided
        if page_hint is None:
            page_hint = self._infer_page_hint(field_name)

        # Use field-specific matching strategies for complex fields
        if 'Address' in field_name:
            return self._match_address(field_name, value, page_hint)

        if field_name in ['VendorName', 'CustomerName']:
            return self._match_company_name(field_name, value, page_hint)

        # Default matching strategies for simple fields

        # 1. Numeric match (for currency, amounts)
        if isinstance(value, (int, float)):
            bbox = self.extractor.find_numeric_bbox(value, page=page_hint)
            if bbox:
                return MatchResult(
                    field_name=field_name,
                    value=value,
                    bbox=bbox,
                    confidence=0.98,
                    match_method="numeric"
                )

        # 2. Exact text match (highest confidence)
        if isinstance(value, str):
            bbox = self.extractor.find_text_bbox(value, page=page_hint, case_sensitive=False)
            if bbox:
                return MatchResult(
                    field_name=field_name,
                    value=value,
                    bbox=bbox,
                    confidence=1.0,
                    match_method="exact"
                )

            # 3. Try phrase match for multi-word values
            if ' ' in value:
                bbox = self.extractor.find_phrase_bbox(value, page=page_hint, case_sensitive=False)
                if bbox:
                    return MatchResult(
                        field_name=field_name,
                        value=value,
                        bbox=bbox,
                        confidence=0.95,
                        match_method="phrase"
                    )

            # 4. Fuzzy match (for OCR errors, formatting differences)
            bbox, similarity = self._fuzzy_match(value, page=page_hint)
            if bbox and similarity >= self.fuzzy_threshold:
                return MatchResult(
                    field_name=field_name,
                    value=value,
                    bbox=bbox,
                    confidence=similarity,
                    match_method="fuzzy"
                )

        # 5. No match found
        return MatchResult(
            field_name=field_name,
            value=value,
            bbox=None,
            confidence=0.0,
            match_method="none"
        )

    def match_invoice_fields(
        self,
        extracted_data: Dict[str, Any],
        page_hints: Optional[Dict[str, int]] = None
    ) -> Dict[str, MatchResult]:
        """
        Match all invoice fields to their bounding boxes.

        Args:
            extracted_data: Dictionary of extracted invoice data from GPT-4o
            page_hints: Optional dict mapping field names to page numbers

        Returns:
            Dictionary mapping field names to MatchResults
        """
        page_hints = page_hints or {}
        results = {}

        # Process top-level fields
        for field_name, field_value in extracted_data.items():
            # Skip nested structures (handle separately)
            if isinstance(field_value, (list, dict)):
                if field_name == "Items":
                    # Handle line items
                    results[field_name] = self._match_line_items(field_value)
                continue

            # Extract value if it's a {value, bbox} structure
            if isinstance(field_value, dict) and 'value' in field_value:
                value = field_value['value']
            else:
                value = field_value

            page_hint = page_hints.get(field_name)
            match = self.match_field(field_name, value, page_hint=page_hint)
            results[field_name] = match

        return results

    def _match_line_items(self, items: List[Dict[str, Any]]) -> List[Dict[str, MatchResult]]:
        """
        Match line item fields to bounding boxes.

        Args:
            items: List of line item dictionaries

        Returns:
            List of dictionaries mapping field names to MatchResults
        """
        results = []

        for item_idx, item in enumerate(items):
            item_results = {}

            for field_name, field_value in item.items():
                # Extract value if it's a {value, bbox} structure
                if isinstance(field_value, dict) and 'value' in field_value:
                    value = field_value['value']
                else:
                    value = field_value

                # Use page hint from bbox if available
                page_hint = None
                if isinstance(field_value, dict) and 'bbox' in field_value:
                    page_hint = field_value['bbox'].get('page')

                match = self.match_field(f"Items[{item_idx}].{field_name}", value, page_hint=page_hint)
                item_results[field_name] = match

            results.append(item_results)

        return results

    def _match_address(
        self,
        field_name: str,
        value: str,
        page: Optional[int] = None
    ) -> MatchResult:
        """
        Match address field using location-aware and unique identifier matching.

        Key insight: Addresses have unique parts (PO Box numbers, street numbers)
        that we can use to locate them, then use location to disambiguate.

        Args:
            field_name: Name of the address field
            value: Address value (may be single string or multi-line)
            page: Page number hint

        Returns:
            MatchResult
        """
        # Get all words for location filtering
        all_words = self.extractor.extract_words()
        if page:
            all_words = [w for w in all_words if w.page == page]

        if not all_words:
            return MatchResult(field_name=field_name, value=value, bbox=None, confidence=0.0, match_method="none")

        # Determine Y-range based on field type
        is_vendor = 'Vendor' in field_name
        page_height = max(w.y1 for w in all_words)

        if is_vendor:
            y_min, y_max = 0, page_height * 0.25  # Top 25%
        else:
            y_min, y_max = page_height * 0.25, page_height * 0.50  # Middle 25-50%

        # Strategy 1: Find unique identifier (PO Box number, street number)
        # Extract first 2-4 significant words that might be unique
        words = value.split()

        # Look for PO Box pattern
        if 'P.O.' in value or 'Box' in value:
            # Find "Box" followed by number
            for i, word in enumerate(words):
                if word.lower() in ['box', 'p.o.'] and i + 1 < len(words):
                    # Next word should be the box number
                    box_num = words[i + 1].replace(',', '')

                    # Find this unique box number in correct location
                    for w in all_words:
                        if w.text == box_num and y_min <= w.y0 <= y_max:
                            # Found the box number in correct location!
                            return MatchResult(
                                field_name=field_name,
                                value=value,
                                bbox=w,
                                confidence=0.95,
                                match_method="unique_identifier"
                            )

        # Strategy 2: Find street number (first number in address)
        for i, word in enumerate(words):
            if word.replace(',', '').isdigit() and len(word) >= 3:
                # This is likely a street number
                street_num = word.replace(',', '')

                # Find this number in correct location
                for w in all_words:
                    if w.text == street_num and y_min <= w.y0 <= y_max:
                        return MatchResult(
                            field_name=field_name,
                            value=value,
                            bbox=w,
                            confidence=0.92,
                            match_method="street_number"
                        )

        # Strategy 3: Multi-line bbox with location filter
        bbox = self.extractor.find_multiline_bbox(value, page=page, case_sensitive=False)
        if bbox and y_min <= bbox.y0 <= y_max:
            return MatchResult(
                field_name=field_name,
                value=value,
                bbox=bbox,
                confidence=0.90,
                match_method="multiline"
            )

        # No match found
        return MatchResult(
            field_name=field_name,
            value=value,
            bbox=None,
            confidence=0.0,
            match_method="none"
        )

    def _match_company_name(
        self,
        field_name: str,
        value: str,
        page: Optional[int] = None
    ) -> MatchResult:
        """
        Match company name using location-aware matching.

        The key insight: "Clipboard Health" appears multiple times on an invoice:
        1. In vendor header (top of page)
        2. In bill-to customer section (middle of page)
        3. Possibly in line item descriptions

        We need to find the RIGHT occurrence based on field type.

        Args:
            field_name: Name of the company field
            value: Company name value
            page: Page number hint

        Returns:
            MatchResult
        """
        # Get all words for location filtering
        all_words = self.extractor.extract_words()
        if page:
            all_words = [w for w in all_words if w.page == page]

        if not all_words:
            return MatchResult(field_name=field_name, value=value, bbox=None, confidence=0.0, match_method="none")

        # Determine if this is vendor (top of page) or customer (middle of page)
        is_vendor = 'Vendor' in field_name

        # Get page dimensions for Y-coordinate filtering
        page_height = max(w.y1 for w in all_words)

        # Vendor names are in top 25% of page
        # Customer names are in middle 25-50% of page
        if is_vendor:
            y_min, y_max = 0, page_height * 0.25
        else:
            y_min, y_max = page_height * 0.25, page_height * 0.50

        # Strategy 1: Find first significant word in the correct location
        # "Clipboard Health (Twomagnets Inc.)" → look for "Clipboard" in header area
        words = value.replace('(', ' ').replace(')', ' ').split()
        significant_words = [w for w in words if len(w) > 3 and w not in ['Inc.', 'LLC', 'Corp', 'Inc']]

        if significant_words:
            first_word = significant_words[0]

            # Find all occurrences of first word
            for word in all_words:
                if word.text.lower() == first_word.lower():
                    # Check if in correct Y-range
                    if y_min <= word.y0 <= y_max:
                        return MatchResult(
                            field_name=field_name,
                            value=value,
                            bbox=word,
                            confidence=0.92,
                            match_method="location_aware"
                        )

        # Strategy 2: Try phrase match with cleaned value in correct location
        if '(' in value:
            clean_value = value.split('(')[0].strip()
            bbox = self.extractor.find_phrase_bbox(clean_value, page=page, case_sensitive=False)
            if bbox and y_min <= bbox.y0 <= y_max:
                return MatchResult(
                    field_name=field_name,
                    value=value,
                    bbox=bbox,
                    confidence=0.90,
                    match_method="cleaned_phrase"
                )

        # No match found
        return MatchResult(
            field_name=field_name,
            value=value,
            bbox=None,
            confidence=0.0,
            match_method="none"
        )

    def _fuzzy_match(
        self,
        text: str,
        page: Optional[int] = None,
        top_n: int = 1
    ) -> Tuple[Optional[WordBBox], float]:
        """
        Find best fuzzy match for text.

        Args:
            text: Text to match
            page: Optional page number (1-indexed)
            top_n: Number of top matches to consider

        Returns:
            Tuple of (best_match_bbox, similarity_score)
        """
        words = self.extractor.extract_words()

        # Filter by page if specified
        if page is not None:
            words = [w for w in words if w.page == page]

        if not words:
            return None, 0.0

        # Normalize text for comparison
        search_text = self._normalize_text(text)

        # Calculate similarity scores
        matches = []
        for word in words:
            word_text = self._normalize_text(word.text)
            similarity = SequenceMatcher(None, search_text, word_text).ratio()

            if similarity > 0.5:  # Only consider somewhat similar matches
                matches.append((word, similarity))

        # Also try matching against phrases (combinations of consecutive words)
        phrase_matches = self._fuzzy_match_phrases(text, words)
        matches.extend(phrase_matches)

        if not matches:
            return None, 0.0

        # Sort by similarity and return best
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches[0]

    def _fuzzy_match_phrases(
        self,
        text: str,
        words: List[WordBBox],
        max_phrase_length: int = 5
    ) -> List[Tuple[WordBBox, float]]:
        """
        Try fuzzy matching against multi-word phrases.

        Args:
            text: Text to match
            words: List of word boxes to combine
            max_phrase_length: Maximum number of words to combine

        Returns:
            List of (combined_bbox, similarity) tuples
        """
        matches = []
        search_text = self._normalize_text(text)

        # Try combining consecutive words
        for i in range(len(words)):
            for length in range(2, min(max_phrase_length + 1, len(words) - i + 1)):
                phrase_words = words[i:i + length]

                # Only combine words on same page and same line (similar y-coordinates)
                if not self._are_words_on_same_line(phrase_words):
                    continue

                combined_bbox = self.extractor._combine_word_boxes(phrase_words)
                combined_text = self._normalize_text(combined_bbox.text)

                similarity = SequenceMatcher(None, search_text, combined_text).ratio()

                if similarity > 0.6:  # Slightly higher threshold for phrases
                    matches.append((combined_bbox, similarity))

        return matches

    def _are_words_on_same_line(
        self,
        words: List[WordBBox],
        y_tolerance: float = 3.0
    ) -> bool:
        """
        Check if words are on the same line.

        Args:
            words: List of word boxes
            y_tolerance: Maximum y-coordinate difference (in points)

        Returns:
            True if all words are on same line
        """
        if len(words) <= 1:
            return True

        # Check page
        pages = set(w.page for w in words)
        if len(pages) > 1:
            return False

        # Check y-coordinates
        y_coords = [w.y0 for w in words]
        y_range = max(y_coords) - min(y_coords)

        return y_range <= y_tolerance

    def _normalize_text(self, text: str) -> str:
        """
        Normalize text for comparison (lowercase, remove special chars).

        Args:
            text: Text to normalize

        Returns:
            Normalized text
        """
        # Lowercase
        text = text.lower()

        # Remove common punctuation (but keep spaces)
        text = re.sub(r'[^\w\s.-]', '', text)

        # Normalize whitespace
        text = ' '.join(text.split())

        return text

    def create_bbox_dict(
        self,
        extracted_data: Dict[str, Any],
        match_results: Dict[str, MatchResult],
        include_confidence: bool = True
    ) -> Dict[str, Any]:
        """
        Create final data structure with bounding boxes merged in.

        Args:
            extracted_data: Original GPT-4o extracted data
            match_results: Matching results from match_invoice_fields
            include_confidence: Whether to include confidence scores

        Returns:
            Data with bbox coordinates added (normalized 0-1 format)
        """
        result = {}

        for field_name, field_value in extracted_data.items():
            # Handle line items separately
            if field_name == "Items" and isinstance(field_value, list):
                result[field_name] = self._create_items_with_bbox(
                    field_value,
                    match_results.get(field_name, []),
                    include_confidence
                )
                continue

            # Get match result
            match = match_results.get(field_name)

            if match and match.bbox:
                # Get page dimensions for normalization
                page_width, page_height = self.extractor.get_page_dimensions(match.bbox.page)

                # Create field with bbox
                field_dict = {
                    "value": match.value,
                    "bbox": match.bbox.to_normalized(page_width, page_height)
                }

                if include_confidence:
                    field_dict["confidence"] = match.confidence

                result[field_name] = field_dict
            else:
                # No bbox found, just include value
                result[field_name] = {"value": field_value} if isinstance(field_value, (str, int, float)) else field_value

        return result

    def _create_items_with_bbox(
        self,
        items: List[Dict[str, Any]],
        item_matches: List[Dict[str, MatchResult]],
        include_confidence: bool
    ) -> List[Dict[str, Any]]:
        """
        Create line items with bounding boxes.

        Args:
            items: Original line items
            item_matches: Match results for each item
            include_confidence: Whether to include confidence

        Returns:
            Line items with bbox data
        """
        result = []

        for item_idx, item in enumerate(items):
            item_result = {}

            matches = item_matches[item_idx] if item_idx < len(item_matches) else {}

            for field_name, field_value in item.items():
                match = matches.get(field_name)

                if match and match.bbox:
                    page_width, page_height = self.extractor.get_page_dimensions(match.bbox.page)

                    field_dict = {
                        "value": match.value,
                        "bbox": match.bbox.to_normalized(page_width, page_height)
                    }

                    if include_confidence:
                        field_dict["confidence"] = match.confidence

                    item_result[field_name] = field_dict
                else:
                    item_result[field_name] = {"value": field_value} if isinstance(field_value, (str, int, float)) else field_value

            result.append(item_result)

        return result

"""
Bounding box coordinate extraction from PDF documents using pdfplumber.

This module extracts precise text-level coordinates from PDF files, providing
100% accurate bounding boxes for text-based PDFs (as opposed to GPT-4o vision
which provides ~70-80% accuracy).
"""

import pdfplumber
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path


@dataclass
class WordBBox:
    """Represents a word with its bounding box coordinates."""
    text: str
    page: int  # 1-indexed
    x0: float  # Left edge (points)
    y0: float  # Top edge (points)
    x1: float  # Right edge (points)
    y1: float  # Bottom edge (points)

    @property
    def width(self) -> float:
        """Width in points."""
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        """Height in points."""
        return self.y1 - self.y0

    def to_normalized(self, page_width: float, page_height: float) -> dict:
        """Convert to normalized coordinates (0-1)."""
        return {
            "page": self.page,
            "x": self.x0 / page_width,
            "y": self.y0 / page_height,
            "width": self.width / page_width,
            "height": self.height / page_height
        }


class BBoxExtractor:
    """Extract precise bounding box coordinates from PDF documents."""

    def __init__(self, pdf_path: str):
        """
        Initialize extractor with PDF file.

        Args:
            pdf_path: Path to PDF file
        """
        self.pdf_path = Path(pdf_path)
        self._words_cache: Optional[List[WordBBox]] = None
        self._page_dimensions: Dict[int, Tuple[float, float]] = {}

    def extract_words(self, use_cache: bool = True) -> List[WordBBox]:
        """
        Extract all words with bounding boxes from PDF.

        Args:
            use_cache: Whether to use cached results

        Returns:
            List of WordBBox objects
        """
        if use_cache and self._words_cache is not None:
            return self._words_cache

        words = []

        with pdfplumber.open(self.pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                # Store page dimensions
                self._page_dimensions[page_num] = (page.width, page.height)

                # Extract words with bounding boxes
                page_words = page.extract_words(
                    x_tolerance=3,
                    y_tolerance=3,
                    keep_blank_chars=False,
                    use_text_flow=True,
                    extra_attrs=["fontname", "size"]
                )

                for word in page_words:
                    words.append(WordBBox(
                        text=word['text'],
                        page=page_num,
                        x0=word['x0'],
                        y0=word['top'],
                        x1=word['x1'],
                        y1=word['bottom']
                    ))

        self._words_cache = words
        return words

    def get_page_dimensions(self, page_num: int) -> Tuple[float, float]:
        """
        Get page dimensions in points.

        Args:
            page_num: 1-indexed page number

        Returns:
            Tuple of (width, height) in points
        """
        if page_num not in self._page_dimensions:
            # Extract if not cached
            self.extract_words(use_cache=False)

        return self._page_dimensions.get(page_num, (612, 792))  # Default letter size

    def find_text_bbox(
        self,
        text: str,
        page: Optional[int] = None,
        case_sensitive: bool = False
    ) -> Optional[WordBBox]:
        """
        Find bounding box for exact text match.

        Args:
            text: Text to find
            page: Optional page number to search (1-indexed)
            case_sensitive: Whether to use case-sensitive matching

        Returns:
            WordBBox if found, None otherwise
        """
        words = self.extract_words()

        search_text = text if case_sensitive else text.lower()

        for word in words:
            if page is not None and word.page != page:
                continue

            word_text = word.text if case_sensitive else word.text.lower()

            if word_text == search_text:
                return word

        return None

    def find_phrase_bbox(
        self,
        phrase: str,
        page: Optional[int] = None,
        case_sensitive: bool = False,
        max_gap: float = 10.0
    ) -> Optional[WordBBox]:
        """
        Find bounding box for multi-word phrase by combining word boxes.

        Args:
            phrase: Multi-word phrase to find
            page: Optional page number (1-indexed)
            case_sensitive: Whether to use case-sensitive matching
            max_gap: Maximum horizontal gap between words (in points)

        Returns:
            Combined WordBBox if found, None otherwise
        """
        words = self.extract_words()
        phrase_words = phrase.split()

        if not phrase_words:
            return None

        search_words = phrase_words if case_sensitive else [w.lower() for w in phrase_words]

        # Find starting positions
        for i, word in enumerate(words):
            if page is not None and word.page != page:
                continue

            word_text = word.text if case_sensitive else word.text.lower()

            if word_text != search_words[0]:
                continue

            # Try to match subsequent words
            matched_words = [word]
            j = i + 1

            for search_word in search_words[1:]:
                # Look for next word within max_gap
                found = False
                while j < len(words) and words[j].page == word.page:
                    next_word = words[j]
                    next_text = next_word.text if case_sensitive else next_word.text.lower()

                    # Check if words are close enough
                    if next_word.x0 - matched_words[-1].x1 > max_gap:
                        break

                    if next_text == search_word:
                        matched_words.append(next_word)
                        found = True
                        j += 1
                        break

                    j += 1

                if not found:
                    break

            # If we matched all words, combine their bboxes
            if len(matched_words) == len(search_words):
                return self._combine_word_boxes(matched_words)

        return None

    def _combine_word_boxes(self, words: List[WordBBox]) -> WordBBox:
        """
        Combine multiple word boxes into a single bounding box.

        Args:
            words: List of WordBBox objects to combine

        Returns:
            Combined WordBBox
        """
        if not words:
            raise ValueError("Cannot combine empty word list")

        min_x0 = min(w.x0 for w in words)
        min_y0 = min(w.y0 for w in words)
        max_x1 = max(w.x1 for w in words)
        max_y1 = max(w.y1 for w in words)

        combined_text = ' '.join(w.text for w in words)

        return WordBBox(
            text=combined_text,
            page=words[0].page,
            x0=min_x0,
            y0=min_y0,
            x1=max_x1,
            y1=max_y1
        )

    def find_numeric_bbox(
        self,
        value: float,
        page: Optional[int] = None,
        formats: Optional[List[str]] = None
    ) -> Optional[WordBBox]:
        """
        Find bounding box for numeric value (handles currency, decimals).

        Args:
            value: Numeric value to find
            page: Optional page number (1-indexed)
            formats: List of format strings to try (e.g., ["${:.2f}", "{:.2f}"])

        Returns:
            WordBBox if found, None otherwise
        """
        if formats is None:
            formats = [
                "${:,.2f}",  # $1,234.56
                "{:,.2f}",   # 1,234.56
                "${:.2f}",   # $1234.56
                "{:.2f}",    # 1234.56
            ]

        # Try each format
        for fmt in formats:
            try:
                formatted = fmt.format(value)
                result = self.find_text_bbox(formatted, page=page, case_sensitive=True)
                if result:
                    return result
            except (ValueError, TypeError):
                continue

        return None

    def is_text_based_pdf(self) -> bool:
        """
        Determine if PDF is text-based (vs scanned image).

        Returns:
            True if PDF has extractable text, False if scanned
        """
        words = self.extract_words()

        # Heuristic: If we found at least 10 words, it's text-based
        return len(words) >= 10

    def get_text_coverage(self) -> float:
        """
        Calculate percentage of page covered by text.

        Returns:
            Coverage ratio (0-1)
        """
        words = self.extract_words()

        if not words:
            return 0.0

        # Group by page
        pages = {}
        for word in words:
            if word.page not in pages:
                pages[word.page] = []
            pages[word.page].append(word)

        # Calculate average coverage across pages
        coverages = []
        for page_num, page_words in pages.items():
            page_width, page_height = self.get_page_dimensions(page_num)
            page_area = page_width * page_height

            # Total area covered by text
            text_area = sum(w.width * w.height for w in page_words)

            coverage = min(1.0, text_area / page_area)
            coverages.append(coverage)

        return sum(coverages) / len(coverages) if coverages else 0.0

    def find_partial_bbox(
        self,
        text: str,
        page: Optional[int] = None,
        min_words: int = 3,
        case_sensitive: bool = False
    ) -> Optional[WordBBox]:
        """
        Find bounding box by matching the first few words of text.

        Useful for long addresses or company names where the full text
        might not match due to formatting differences.

        Args:
            text: Text to match
            page: Optional page number (1-indexed)
            min_words: Minimum number of words to try matching
            case_sensitive: Whether to use case-sensitive matching

        Returns:
            WordBBox if found, None otherwise
        """
        words_in_text = text.split()

        if len(words_in_text) < min_words:
            # Text too short for partial matching, try exact
            return self.find_text_bbox(text, page=page, case_sensitive=case_sensitive)

        # Try increasingly shorter prefixes
        for num_words in range(len(words_in_text), min_words - 1, -1):
            prefix = ' '.join(words_in_text[:num_words])

            # Try phrase match first
            bbox = self.find_phrase_bbox(prefix, page=page, case_sensitive=case_sensitive)
            if bbox:
                return bbox

        return None

    def find_multiline_bbox(
        self,
        text: str,
        page: Optional[int] = None,
        max_vertical_gap: float = 20.0,
        case_sensitive: bool = False
    ) -> Optional[WordBBox]:
        """
        Find bounding box for text that spans multiple lines.

        This handles addresses and other fields that are formatted
        across multiple lines in the PDF.

        Args:
            text: Text to find (can contain embedded newlines or be single string)
            page: Optional page number (1-indexed)
            max_vertical_gap: Maximum vertical gap between lines (in points)
            case_sensitive: Whether to use case-sensitive matching

        Returns:
            Combined WordBBox if found, None otherwise
        """
        # First, try to find the starting anchor (first few words)
        words_in_text = text.replace('\n', ' ').split()

        if len(words_in_text) < 2:
            return self.find_text_bbox(text, page=page, case_sensitive=case_sensitive)

        # Find first 2-3 words as anchor
        anchor_words = min(3, len(words_in_text))
        anchor_text = ' '.join(words_in_text[:anchor_words])

        anchor_bbox = self.find_phrase_bbox(anchor_text, page=page, case_sensitive=case_sensitive)

        if not anchor_bbox:
            return None

        # Now expand to include nearby text (same x-alignment, vertically close)
        all_words = self.extract_words()

        # Filter to same page
        page_words = [w for w in all_words if w.page == anchor_bbox.page]

        # Find all words within vertical proximity of anchor
        matching_words = [anchor_bbox]

        # Define x-tolerance for "same column" (addresses are usually left-aligned)
        x_tolerance = 30.0  # points

        # Find words below the anchor within the same column
        anchor_bottom = anchor_bbox.y1

        for word in page_words:
            # Skip if not roughly same x-position
            if abs(word.x0 - anchor_bbox.x0) > x_tolerance:
                continue

            # Check if vertically close
            if word.y0 >= anchor_bbox.y0 and word.y0 - anchor_bottom <= max_vertical_gap:
                matching_words.append(word)
                anchor_bottom = max(anchor_bottom, word.y1)

        if len(matching_words) > 1:
            return self._combine_word_boxes(matching_words)

        return anchor_bbox

    def find_flexible_phrase_bbox(
        self,
        phrase: str,
        page: Optional[int] = None,
        case_sensitive: bool = False,
        allow_line_breaks: bool = True,
        max_gap: float = 30.0
    ) -> Optional[WordBBox]:
        """
        Find phrase with more flexible matching rules.

        This version allows for larger gaps between words and can
        handle line breaks in addresses.

        Args:
            phrase: Phrase to find
            page: Optional page number (1-indexed)
            case_sensitive: Whether to use case-sensitive matching
            allow_line_breaks: Whether to allow words on different lines
            max_gap: Maximum gap between words (in points)

        Returns:
            Combined WordBBox if found, None otherwise
        """
        words = self.extract_words()
        phrase_words = phrase.split()

        if not phrase_words:
            return None

        search_words = phrase_words if case_sensitive else [w.lower() for w in phrase_words]

        # Filter by page
        if page is not None:
            words = [w for w in words if w.page == page]

        # Find starting positions
        for i, word in enumerate(words):
            word_text = word.text if case_sensitive else word.text.lower()

            if word_text != search_words[0]:
                continue

            # Try to match subsequent words
            matched_words = [word]
            j = i + 1

            for search_word in search_words[1:]:
                found = False

                while j < len(words) and words[j].page == word.page:
                    next_word = words[j]
                    next_text = next_word.text if case_sensitive else next_word.text.lower()

                    # Calculate gap (horizontal and vertical)
                    horizontal_gap = next_word.x0 - matched_words[-1].x1
                    vertical_gap = abs(next_word.y0 - matched_words[-1].y0)

                    # Check if words are close enough
                    if allow_line_breaks:
                        # Allow vertical movement (line breaks)
                        if horizontal_gap > max_gap and vertical_gap < 5.0:
                            # Same line, too far apart
                            break
                        if vertical_gap > 20.0:
                            # Different line, too far apart vertically
                            break
                    else:
                        # Must be on same line
                        if horizontal_gap > max_gap or vertical_gap > 5.0:
                            break

                    if next_text == search_word:
                        matched_words.append(next_word)
                        found = True
                        j += 1
                        break

                    j += 1

                if not found:
                    break

            # If we matched all words, return combined bbox
            if len(matched_words) == len(search_words):
                return self._combine_word_boxes(matched_words)

        return None

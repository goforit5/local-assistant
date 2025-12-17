"""
Document classifier for determining document types.

Classifies documents based on filename, MIME type, and content analysis.
"""

from enum import Enum
from pathlib import Path
from typing import Optional, Tuple


class DocumentType(str, Enum):
    """Document type classifications."""
    INVOICE = "invoice"
    RECEIPT = "receipt"
    CONTRACT = "contract"
    FORM = "form"
    LETTER = "letter"
    STATEMENT = "statement"
    OTHER = "other"


class DocumentClassifier:
    """Classifies documents based on filename and content.

    Uses a multi-tier classification strategy:
    1. Filename analysis (keywords like "invoice", "receipt")
    2. Extension analysis (.pdf, .jpg, .png)
    3. Content-based classification (future: use LLM)

    Example:
        classifier = DocumentClassifier()
        doc_type, confidence = classifier.classify(
            filename="invoice_240470.pdf",
            mime_type="application/pdf"
        )
        # Returns: (DocumentType.INVOICE, 0.95)
    """

    # Keywords for each document type
    KEYWORDS = {
        DocumentType.INVOICE: [
            "invoice",
            "inv",
            "bill",
            "payment_due",
            "amount_due",
        ],
        DocumentType.RECEIPT: [
            "receipt",
            "rcpt",
            "transaction",
            "proof_of_purchase",
        ],
        DocumentType.CONTRACT: [
            "contract",
            "agreement",
            "terms",
            "sow",
            "statement_of_work",
        ],
        DocumentType.FORM: [
            "form",
            "application",
            "questionnaire",
            "survey",
        ],
        DocumentType.LETTER: [
            "letter",
            "correspondence",
            "memo",
            "memorandum",
        ],
        DocumentType.STATEMENT: [
            "statement",
            "account_statement",
            "bank_statement",
            "report",
        ],
    }

    def classify(
        self,
        filename: str,
        mime_type: Optional[str] = None,
        content_preview: Optional[str] = None
    ) -> Tuple[DocumentType, float]:
        """Classify a document based on available information.

        Args:
            filename: Name of the file
            mime_type: MIME type (e.g., "application/pdf")
            content_preview: First few lines of text content (optional)

        Returns:
            Tuple of (DocumentType, confidence_score)
            Confidence is 0.0 to 1.0, where:
                0.90-1.0 = Very high confidence
                0.75-0.89 = High confidence
                0.60-0.74 = Medium confidence
                0.0-0.59 = Low confidence (falls back to OTHER)

        Example:
            doc_type, confidence = classifier.classify(
                filename="Invoice_240470.pdf",
                mime_type="application/pdf"
            )
            print(f"{doc_type}: {confidence:.2f}")  # INVOICE: 0.95
        """
        # Normalize filename to lowercase
        filename_lower = filename.lower()

        # Extract base name without extension
        base_name = Path(filename_lower).stem

        # Check for keywords in filename
        matches = {}
        for doc_type, keywords in self.KEYWORDS.items():
            match_count = sum(1 for keyword in keywords if keyword in base_name)
            if match_count > 0:
                matches[doc_type] = match_count

        # If we have matches, return the highest
        if matches:
            best_match = max(matches, key=matches.get)
            # Higher confidence if multiple keywords match
            confidence = min(0.95, 0.75 + (matches[best_match] * 0.10))
            return best_match, confidence

        # Check content preview if available
        if content_preview:
            content_lower = content_preview.lower()
            content_matches = {}
            for doc_type, keywords in self.KEYWORDS.items():
                match_count = sum(
                    1 for keyword in keywords
                    if keyword.replace("_", " ") in content_lower
                )
                if match_count > 0:
                    content_matches[doc_type] = match_count

            if content_matches:
                best_match = max(content_matches, key=content_matches.get)
                confidence = min(0.85, 0.65 + (content_matches[best_match] * 0.10))
                return best_match, confidence

        # Default to OTHER with low confidence
        return DocumentType.OTHER, 0.50

    def get_suggested_extraction_type(self, doc_type: DocumentType) -> str:
        """Get the suggested extraction type for the document type.

        This maps document types to extraction types used by the Vision API.

        Args:
            doc_type: Classified document type

        Returns:
            Extraction type string (e.g., "invoice", "receipt", "document")

        Example:
            extraction_type = classifier.get_suggested_extraction_type(
                DocumentType.INVOICE
            )
            # Returns: "invoice"
        """
        extraction_mapping = {
            DocumentType.INVOICE: "invoice",
            DocumentType.RECEIPT: "receipt",
            DocumentType.CONTRACT: "document",
            DocumentType.FORM: "form",
            DocumentType.LETTER: "document",
            DocumentType.STATEMENT: "document",
            DocumentType.OTHER: "document",
        }
        return extraction_mapping.get(doc_type, "document")

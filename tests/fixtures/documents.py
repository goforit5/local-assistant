"""Document test fixtures for E2E and integration tests."""

import pytest
from typing import AsyncGenerator, Dict, Any
from decimal import Decimal
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from memory.models import Base


@pytest.fixture
def sample_invoice_pdf() -> bytes:
    """Generate a minimal valid PDF with invoice content.

    Returns:
        bytes: Valid PDF file content for testing
    """
    pdf_content = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/Resources <<
/Font <<
/F1 <<
/Type /Font
/Subtype /Type1
/BaseFont /Helvetica
>>
>>
>>
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj
4 0 obj
<<
/Length 200
>>
stream
BT
/F1 12 Tf
50 750 Td
(INVOICE) Tj
0 -20 Td
(From: Acme Corp) Tj
0 -20 Td
(123 Main St, San Francisco, CA 94102) Tj
0 -20 Td
(Invoice #: INV-2025-001) Tj
0 -20 Td
(Due Date: 2025-12-15) Tj
0 -20 Td
(Total: $1,250.00) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000315 00000 n
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
565
%%EOF
"""
    return pdf_content


@pytest.fixture
def sample_invoice_pdf_different_vendor() -> bytes:
    """Generate a minimal valid PDF with different vendor.

    Returns:
        bytes: Valid PDF file content for testing
    """
    pdf_content = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/Resources <<
/Font <<
/F1 <<
/Type /Font
/Subtype /Type1
/BaseFont /Helvetica
>>
>>
>>
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj
4 0 obj
<<
/Length 200
>>
stream
BT
/F1 12 Tf
50 750 Td
(INVOICE) Tj
0 -20 Td
(From: TechSupplies Inc) Tj
0 -20 Td
(456 Oak Ave, Seattle, WA 98101) Tj
0 -20 Td
(Invoice #: TS-2025-042) Tj
0 -20 Td
(Due Date: 2025-12-20) Tj
0 -20 Td
(Total: $850.50) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000315 00000 n
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
565
%%EOF
"""
    return pdf_content


@pytest.fixture
def mock_vision_response_acme() -> Dict[str, Any]:
    """Mock GPT-4o vision API response for Acme Corp invoice.

    Returns:
        dict: Structured extraction data matching VisionResult format
    """
    return {
        "content": """INVOICE

From: Acme Corp
123 Main St
San Francisco, CA 94102

Invoice #: INV-2025-001
Date: 2025-11-26
Due Date: 2025-12-15

Items:
- Professional Services (40 hours @ $30/hr): $1,200.00
- Materials: $50.00

Subtotal: $1,250.00
Tax: $0.00
Total: $1,250.00

Payment Terms: Net 30 days
""",
        "model": "gpt-4o",
        "cost": Decimal("0.0025"),
        "pages_processed": 1,
        "structured_data": {
            "vendor_name": "Acme Corp",
            "vendor_address": "123 Main St, San Francisco, CA 94102",
            "invoice_number": "INV-2025-001",
            "invoice_date": "2025-11-26",
            "due_date": "2025-12-15",
            "total": 1250.00,
            "subtotal": 1250.00,
            "tax": 0.00,
            "currency": "USD",
            "line_items": [
                {
                    "description": "Professional Services (40 hours @ $30/hr)",
                    "quantity": 40,
                    "unit_price": 30.00,
                    "total": 1200.00
                },
                {
                    "description": "Materials",
                    "quantity": 1,
                    "unit_price": 50.00,
                    "total": 50.00
                }
            ],
            "payment_terms": "Net 30 days"
        }
    }


@pytest.fixture
def mock_vision_response_techsupplies() -> Dict[str, Any]:
    """Mock GPT-4o vision API response for TechSupplies Inc invoice.

    Returns:
        dict: Structured extraction data matching VisionResult format
    """
    return {
        "content": """INVOICE

From: TechSupplies Inc
456 Oak Ave
Seattle, WA 98101

Invoice #: TS-2025-042
Date: 2025-11-26
Due Date: 2025-12-20

Items:
- Computer Accessories: $750.50
- Shipping: $100.00

Subtotal: $850.50
Tax: $0.00
Total: $850.50

Payment Terms: Net 15 days
""",
        "model": "gpt-4o",
        "cost": Decimal("0.0025"),
        "pages_processed": 1,
        "structured_data": {
            "vendor_name": "TechSupplies Inc",
            "vendor_address": "456 Oak Ave, Seattle, WA 98101",
            "invoice_number": "TS-2025-042",
            "invoice_date": "2025-11-26",
            "due_date": "2025-12-20",
            "total": 850.50,
            "subtotal": 850.50,
            "tax": 0.00,
            "currency": "USD",
            "line_items": [
                {
                    "description": "Computer Accessories",
                    "quantity": 1,
                    "unit_price": 750.50,
                    "total": 750.50
                },
                {
                    "description": "Shipping",
                    "quantity": 1,
                    "unit_price": 100.00,
                    "total": 100.00
                }
            ],
            "payment_terms": "Net 15 days"
        }
    }


@pytest.fixture
def mock_vision_response_fuzzy_match() -> Dict[str, Any]:
    """Mock vision response with vendor name that fuzzy matches existing vendor.

    Returns:
        dict: Structured extraction with similar vendor name (Acme Corporation vs Acme Corp)
    """
    return {
        "content": """INVOICE

From: Acme Corporation
123 Main Street
San Francisco, CA 94102

Invoice #: INV-2025-002
Date: 2025-11-26
Due Date: 2025-12-25

Total: $2,500.00
""",
        "model": "gpt-4o",
        "cost": Decimal("0.0025"),
        "pages_processed": 1,
        "structured_data": {
            "vendor_name": "Acme Corporation",
            "vendor_address": "123 Main Street, San Francisco, CA 94102",
            "invoice_number": "INV-2025-002",
            "invoice_date": "2025-11-26",
            "due_date": "2025-12-25",
            "total": 2500.00,
            "subtotal": 2500.00,
            "tax": 0.00,
            "currency": "USD"
        }
    }

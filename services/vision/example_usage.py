"""Example usage of Vision Service."""

import asyncio
from pydantic import BaseModel
from typing import List, Optional

from services.vision import create_vision_service, VisionConfig, OCRConfig
from providers import OpenAIProvider, ProviderConfig


class InvoiceLineItem(BaseModel):
    """Invoice line item schema."""
    description: str
    quantity: float
    unit_price: float
    amount: float


class InvoiceSchema(BaseModel):
    """Invoice data schema."""
    vendor_name: str
    invoice_number: str
    date: str
    due_date: Optional[str] = None
    subtotal: float
    tax: float
    total: float
    line_items: List[InvoiceLineItem]


async def example_basic_usage():
    """Basic document processing example."""
    print("=== Basic Usage Example ===\n")

    provider = OpenAIProvider(ProviderConfig(api_key="your-api-key-here"))
    await provider.initialize()

    vision_service = await create_vision_service(
        provider=provider,
        vision_config={"model": "gpt-4o", "max_tokens": 4096},
        enable_ocr_fallback=False
    )

    try:
        document = await vision_service.document_handler.load_document("invoice.pdf")
        print(f"Loaded: {document.filename}")
        print(f"Pages: {document.total_pages}")
        print(f"Size: {document.file_size_mb:.2f} MB\n")

        result = await vision_service.processor.process_document(
            document=document,
            prompt="Extract all text from this invoice"
        )

        print(f"Extracted content:\n{result.content}\n")
        print(f"Cost: ${result.cost:.4f}")
        print(f"Provider: {result.provider}")
        print(f"Model: {result.model}")

    finally:
        await vision_service.close()
        await provider.close()


async def example_structured_extraction():
    """Structured data extraction example."""
    print("\n=== Structured Extraction Example ===\n")

    provider = OpenAIProvider(ProviderConfig(api_key="your-api-key-here"))
    await provider.initialize()

    vision_service = await create_vision_service(
        provider=provider,
        vision_config=VisionConfig(
            model="gpt-4o",
            max_tokens=4096,
            temperature=0.0,
            cost_limit_per_document=0.50
        ),
        ocr_config=OCRConfig(
            engine="pytesseract",
            languages=["eng"],
            confidence_threshold=0.85
        ),
        enable_ocr_fallback=True
    )

    try:
        document = await vision_service.document_handler.load_document("invoice.pdf")

        result = await vision_service.extractor.extract_with_schema(
            document=document,
            schema=InvoiceSchema,
            additional_instructions="Extract all financial details accurately"
        )

        print(f"Validation: {'PASSED' if result.validated else 'FAILED'}")
        if result.validation_errors:
            print(f"Errors: {result.validation_errors}")

        print(f"\nExtracted Data:")
        print(f"  Vendor: {result.data.get('vendor_name')}")
        print(f"  Invoice #: {result.data.get('invoice_number')}")
        print(f"  Date: {result.data.get('date')}")
        print(f"  Total: ${result.data.get('total'):.2f}")
        print(f"\nLine Items: {len(result.data.get('line_items', []))}")

        print(f"\nProcessing Cost: ${result.vision_result.cost:.4f}")
        print(f"OCR Used: {result.vision_result.ocr_fallback_used}")

    finally:
        await vision_service.close()
        await provider.close()


async def example_dict_config():
    """Example using dict configs (easiest for YAML/JSON)."""
    print("\n=== Dict Config Example ===\n")

    config = {
        "vision": {
            "model": "gpt-4o",
            "use_ocr_fallback": True,
            "max_tokens": 4096,
            "temperature": 0.0
        },
        "ocr": {
            "engine": "pytesseract",
            "languages": ["eng", "spa"],
            "confidence_threshold": 0.80
        },
        "document": {
            "max_file_size_mb": 10.0,
            "enable_caching": True,
            "pdf_dpi": 300
        }
    }

    provider = OpenAIProvider(ProviderConfig(api_key="your-api-key-here"))
    await provider.initialize()

    vision_service = await create_vision_service(
        provider=provider,
        vision_config=config["vision"],
        ocr_config=config["ocr"],
        document_config=config["document"]
    )

    try:
        document = await vision_service.document_handler.load_document("receipt.jpg")
        result = await vision_service.processor.analyze_document(
            document=document,
            analysis_type="receipt"
        )

        print(f"Analysis:\n{result.content}\n")
        print(f"Cost: ${result.cost:.4f}")

    finally:
        await vision_service.close()
        await provider.close()


async def example_multi_page():
    """Multi-page PDF processing example."""
    print("\n=== Multi-Page Processing Example ===\n")

    provider = OpenAIProvider(ProviderConfig(api_key="your-api-key-here"))
    await provider.initialize()

    vision_service = await create_vision_service(
        provider=provider,
        vision_config={
            "model": "gpt-4o",
            "cost_limit_per_document": 1.00
        }
    )

    try:
        document = await vision_service.document_handler.load_document("contract.pdf")
        print(f"Processing {document.total_pages} pages...\n")

        result = await vision_service.processor.process_document(
            document=document,
            prompt="Summarize the key points from each page"
        )

        print(f"Processed {result.pages_processed} of {document.total_pages} pages")
        print(f"Total cost: ${result.cost:.4f}\n")
        print(f"Summary:\n{result.content}")

    finally:
        await vision_service.close()
        await provider.close()


if __name__ == "__main__":
    print("Vision Service Usage Examples\n")
    print("Note: Replace 'your-api-key-here' with actual API key")
    print("      and provide actual document paths\n")

    # Uncomment to run examples:
    # asyncio.run(example_basic_usage())
    # asyncio.run(example_structured_extraction())
    # asyncio.run(example_dict_config())
    # asyncio.run(example_multi_page())

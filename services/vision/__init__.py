"""Vision Service - Document processing with AI vision models.

This service provides DRY OOP patterns for vision-based document processing
with easy argument passing for agent integration.

Example usage:
    ```python
    from services.vision import create_vision_service
    from providers import OpenAIProvider, ProviderConfig

    # Create provider
    provider = OpenAIProvider(ProviderConfig(api_key="..."))
    await provider.initialize()

    # Create vision service from dict config
    vision_service = await create_vision_service(
        provider=provider,
        vision_config={"model": "gpt-4o", "max_tokens": 4096},
        ocr_config={"engine": "pytesseract", "languages": ["eng"]},
        enable_ocr_fallback=True
    )

    # Load and process document
    document = await vision_service.document_handler.load_document("invoice.pdf")
    result = await vision_service.processor.process_document(
        document=document,
        prompt="Extract all invoice details"
    )

    print(f"Extracted: {result.content}")
    print(f"Cost: ${result.cost:.4f}")
    ```

For structured extraction:
    ```python
    from pydantic import BaseModel

    class InvoiceSchema(BaseModel):
        vendor_name: str
        invoice_number: str
        total_amount: float
        date: str

    result = await vision_service.extractor.extract_with_schema(
        document=document,
        schema=InvoiceSchema
    )

    print(result.data)  # Validated dict
    ```
"""

from __future__ import annotations

from typing import Optional, Dict, Any
from dataclasses import asdict

from providers.base import BaseProvider

from .config import (
    VisionConfig,
    OCRConfig,
    DocumentConfig,
    StructuredExtractionConfig
)
from .processor import VisionProcessor, VisionResult
from .ocr import OCREngine, OCRResult
from .document import DocumentHandler, Document, DocumentPage
from .structured import StructuredExtractor, ExtractionResult
from .models import Invoice, Receipt, Form, LineItem


__all__ = [
    "VisionConfig",
    "OCRConfig",
    "DocumentConfig",
    "StructuredExtractionConfig",
    "VisionProcessor",
    "VisionResult",
    "OCREngine",
    "OCRResult",
    "DocumentHandler",
    "Document",
    "DocumentPage",
    "StructuredExtractor",
    "ExtractionResult",
    "Invoice",
    "Receipt",
    "Form",
    "LineItem",
    "create_vision_service",
    "VisionService",
]


class VisionService:
    """Complete vision service with all components."""

    def __init__(
        self,
        processor: VisionProcessor,
        document_handler: DocumentHandler,
        extractor: StructuredExtractor,
        ocr_engine: Optional[OCREngine] = None
    ):
        """Initialize vision service.

        Args:
            processor: Vision processor instance
            document_handler: Document handler instance
            extractor: Structured extractor instance
            ocr_engine: Optional OCR engine
        """
        self.processor = processor
        self.document_handler = document_handler
        self.extractor = extractor
        self.ocr_engine = ocr_engine

    async def close(self) -> None:
        """Clean up all resources."""
        await self.processor.close()
        await self.document_handler.close()
        await self.extractor.close()
        if self.ocr_engine:
            await self.ocr_engine.close()


async def create_vision_service(
    provider: BaseProvider,
    vision_config: Optional[Dict[str, Any] | VisionConfig] = None,
    ocr_config: Optional[Dict[str, Any] | OCRConfig] = None,
    document_config: Optional[Dict[str, Any] | DocumentConfig] = None,
    extraction_config: Optional[Dict[str, Any] | StructuredExtractionConfig] = None,
    enable_ocr_fallback: bool = True
) -> VisionService:
    """Factory function to create vision service from configs.

    This is the main entry point for creating a vision service. Accepts either
    dataclass instances or dicts for easy agent argument passing.

    Args:
        provider: Initialized AI provider (OpenAI, Anthropic, etc.)
        vision_config: Vision configuration dict or VisionConfig instance
        ocr_config: OCR configuration dict or OCRConfig instance
        document_config: Document configuration dict or DocumentConfig instance
        extraction_config: Extraction configuration dict or StructuredExtractionConfig instance
        enable_ocr_fallback: Whether to enable OCR fallback

    Returns:
        Fully configured VisionService instance

    Example:
        ```python
        # From dicts (easy for YAML/JSON configs)
        service = await create_vision_service(
            provider=provider,
            vision_config={"model": "gpt-4o", "max_tokens": 4096},
            ocr_config={"engine": "pytesseract"}
        )

        # From dataclasses (easy for code)
        service = await create_vision_service(
            provider=provider,
            vision_config=VisionConfig(model="gpt-4o"),
            ocr_config=OCRConfig(engine="pytesseract")
        )
        ```
    """
    v_config = (
        VisionConfig(**vision_config) if isinstance(vision_config, dict)
        else vision_config or VisionConfig()
    )

    o_config = (
        OCRConfig(**ocr_config) if isinstance(ocr_config, dict)
        else ocr_config or OCRConfig()
    )

    d_config = (
        DocumentConfig(**document_config) if isinstance(document_config, dict)
        else document_config or DocumentConfig()
    )

    e_config = (
        StructuredExtractionConfig(**extraction_config) if isinstance(extraction_config, dict)
        else extraction_config or StructuredExtractionConfig()
    )

    ocr_engine = None
    if enable_ocr_fallback or v_config.use_ocr_fallback:
        ocr_engine = OCREngine(config=o_config)
        await ocr_engine.initialize()

    document_handler = DocumentHandler(config=d_config)

    processor = VisionProcessor(
        provider=provider,
        config=v_config,
        ocr_engine=ocr_engine
    )

    extractor = StructuredExtractor(
        processor=processor,
        config=e_config
    )

    return VisionService(
        processor=processor,
        document_handler=document_handler,
        extractor=extractor,
        ocr_engine=ocr_engine
    )

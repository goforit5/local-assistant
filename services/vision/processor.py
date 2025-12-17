"""Core vision processing using AI providers."""

import asyncio
import time
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from providers.base import BaseProvider, Message
from .config import VisionConfig
from .document import Document, DocumentPage
from .ocr import OCREngine, OCRResult


@dataclass
class VisionResult:
    """Vision processing result."""

    content: str
    pages_processed: int
    cost: float
    provider: str
    model: str
    metadata: Dict[str, Any]
    ocr_fallback_used: bool = False


class VisionProcessor:
    """Process documents using vision AI."""

    def __init__(
        self,
        provider: BaseProvider,
        config: VisionConfig,
        ocr_engine: Optional[OCREngine] = None
    ):
        """Initialize vision processor.

        Args:
            provider: AI provider instance (OpenAI, Anthropic, etc.)
            config: Vision configuration
            ocr_engine: Optional OCR engine for fallback
        """
        self.provider = provider
        self.config = config
        self.ocr_engine = ocr_engine
        self._total_cost = 0.0

    async def process_document(
        self,
        document: Document,
        prompt: str,
        **kwargs
    ) -> VisionResult:
        """Process entire document with vision AI.

        Args:
            document: Document to process
            prompt: Processing instruction
            **kwargs: Additional processing parameters

        Returns:
            Vision processing result
        """
        if document.total_pages == 1:
            return await self._process_single_page(document.pages[0], prompt, **kwargs)
        else:
            return await self._process_multi_page(document, prompt, **kwargs)

    async def _process_single_page(
        self,
        page: DocumentPage,
        prompt: str,
        **kwargs
    ) -> VisionResult:
        """Process single page."""
        # Extract detail parameter for vision API
        detail = kwargs.pop('detail', 'auto')
        messages = self._build_vision_messages(prompt, [page], detail=detail)

        try:
            response = await self.provider.chat(
                messages=messages,
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                **kwargs
            )

            self._total_cost += response.cost

            if response.cost > self.config.cost_limit_per_document:
                raise ValueError(
                    f"Cost ${response.cost:.4f} exceeds limit "
                    f"${self.config.cost_limit_per_document:.4f}"
                )

            return VisionResult(
                content=response.content,
                pages_processed=1,
                cost=response.cost,
                provider=response.provider,
                model=response.model,
                metadata={
                    "usage": response.usage,
                    "latency": response.latency,
                    "page_dimensions": (page.width, page.height)
                },
                ocr_fallback_used=False
            )

        except Exception as e:
            if self.config.use_ocr_fallback and self.ocr_engine:
                return await self._fallback_to_ocr(page, prompt, error=str(e))
            raise

    async def _process_multi_page(
        self,
        document: Document,
        prompt: str,
        **kwargs
    ) -> VisionResult:
        """Process multi-page document by sending all pages in ONE API call.

        This is the professional approach used by AI invoice processing systems:
        - GPT-4o supports up to 16 images in a single request
        - Model sees full document context for better extraction
        - Single API call is faster and cheaper than per-page processing
        - Eliminates redundant extraction of header/footer info across pages
        """
        start_time = time.time()

        # Extract detail parameter for vision API
        detail = kwargs.pop('detail', 'auto')

        # Build single message with ALL pages as images
        messages = self._build_vision_messages(prompt, document.pages, detail=detail)

        try:
            response = await self.provider.chat(
                messages=messages,
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                **kwargs
            )

            self._total_cost += response.cost

            if response.cost > self.config.cost_limit_per_document:
                raise ValueError(
                    f"Cost ${response.cost:.4f} exceeds limit "
                    f"${self.config.cost_limit_per_document:.4f}"
                )

            return VisionResult(
                content=response.content,
                pages_processed=document.total_pages,
                cost=response.cost,
                provider=response.provider,
                model=response.model,
                metadata={
                    "usage": response.usage,
                    "latency": response.latency,
                    "total_pages": document.total_pages,
                    "processing_mode": "multi_page_single_call"
                },
                ocr_fallback_used=False
            )

        except Exception as e:
            if self.config.use_ocr_fallback and self.ocr_engine:
                # Fallback to OCR for first page only as example
                return await self._fallback_to_ocr(document.pages[0], prompt, error=str(e))
            raise

    async def _fallback_to_ocr(
        self,
        page: DocumentPage,
        prompt: str,
        error: str
    ) -> VisionResult:
        """Fallback to OCR when vision AI fails."""
        if not self.ocr_engine:
            raise ValueError(f"OCR fallback not available. Original error: {error}")

        ocr_result = await self.ocr_engine.extract_text(page.image_data)

        if not ocr_result.success:
            raise ValueError(
                f"OCR fallback failed. Vision error: {error}, "
                f"OCR error: {ocr_result.metadata.get('error', 'unknown')}"
            )

        content = f"[OCR Extracted Text]\n{ocr_result.text}"

        return VisionResult(
            content=content,
            pages_processed=1,
            cost=0.0,
            provider="ocr_fallback",
            model=self.ocr_engine.config.engine,
            metadata={
                "ocr_confidence": ocr_result.confidence,
                "ocr_metadata": ocr_result.metadata,
                "original_error": error
            },
            ocr_fallback_used=True
        )

    def _build_vision_messages(
        self,
        prompt: str,
        pages: List[DocumentPage],
        detail: str = "auto"
    ) -> List[Message]:
        """Build messages for vision API.

        For OpenAI format with base64 images.
        """
        content_parts = [{"type": "text", "text": prompt}]

        for page in pages:
            image_url_config = {
                "url": f"data:image/{page.format};base64,{page.to_base64()}"
            }
            # Add detail parameter if not auto (OpenAI vision API)
            if detail != "auto":
                image_url_config["detail"] = detail

            content_parts.append({
                "type": "image_url",
                "image_url": image_url_config
            })

        return [Message(
            role="user",
            content=content_parts
        )]

    async def extract_text(
        self,
        document: Document,
        **kwargs
    ) -> VisionResult:
        """Extract all text from document.

        Args:
            document: Document to extract from
            **kwargs: Additional parameters

        Returns:
            Extracted text result
        """
        prompt = "Extract all text from this document. Return only the text content."
        return await self.process_document(document, prompt, **kwargs)

    async def analyze_document(
        self,
        document: Document,
        analysis_type: str = "general",
        **kwargs
    ) -> VisionResult:
        """Analyze document content.

        Args:
            document: Document to analyze
            analysis_type: Type of analysis (general, invoice, receipt, etc.)
            **kwargs: Additional parameters

        Returns:
            Analysis result
        """
        prompts = {
            "general": "Analyze this document and provide a detailed summary.",
            "invoice": "Extract invoice information including date, vendor, items, and total.",
            "receipt": "Extract receipt details including merchant, items, and amounts.",
            "contract": "Summarize key terms, parties, and obligations in this contract.",
        }

        prompt = prompts.get(analysis_type, prompts["general"])
        return await self.process_document(document, prompt, **kwargs)

    @property
    def total_cost(self) -> float:
        """Get total accumulated cost."""
        return self._total_cost

    def reset_cost_tracking(self) -> None:
        """Reset cost counter."""
        self._total_cost = 0.0

    async def close(self) -> None:
        """Clean up resources."""
        if self.ocr_engine:
            await self.ocr_engine.close()

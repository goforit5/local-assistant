"""OCR engine for fallback text extraction."""

import base64
from typing import Optional, Dict, Any
from dataclasses import dataclass
from io import BytesIO

from .config import OCRConfig


@dataclass
class OCRResult:
    """OCR extraction result."""

    text: str
    confidence: float
    metadata: Dict[str, Any]
    success: bool


class OCREngine:
    """OCR engine with multiple backend support."""

    def __init__(self, config: OCRConfig):
        """Initialize OCR engine.

        Args:
            config: OCR configuration
        """
        self.config = config
        self._engine = None

    async def initialize(self) -> None:
        """Initialize OCR backend."""
        if self.config.engine == "pytesseract":
            try:
                import pytesseract
                self._engine = pytesseract
            except ImportError:
                raise ImportError(
                    "pytesseract not installed. Install with: pip install pytesseract"
                )
        elif self.config.engine == "easyocr":
            try:
                import easyocr
                self._engine = easyocr.Reader(self.config.languages)
            except ImportError:
                raise ImportError(
                    "easyocr not installed. Install with: pip install easyocr"
                )
        else:
            raise ValueError(f"Unsupported OCR engine: {self.config.engine}")

    async def extract_text(
        self,
        image_data: bytes,
        **kwargs
    ) -> OCRResult:
        """Extract text from image using OCR.

        Args:
            image_data: Raw image bytes
            **kwargs: Additional OCR parameters

        Returns:
            OCR extraction result
        """
        if not self._engine:
            await self.initialize()

        try:
            if self.config.engine == "pytesseract":
                result = await self._extract_pytesseract(image_data, **kwargs)
            elif self.config.engine == "easyocr":
                result = await self._extract_easyocr(image_data, **kwargs)
            else:
                raise ValueError(f"Unsupported OCR engine: {self.config.engine}")

            return result

        except Exception as e:
            return OCRResult(
                text="",
                confidence=0.0,
                metadata={"error": str(e)},
                success=False
            )

    async def _extract_pytesseract(
        self,
        image_data: bytes,
        **kwargs
    ) -> OCRResult:
        """Extract text using pytesseract."""
        from PIL import Image

        img = Image.open(BytesIO(image_data))

        if self.config.preprocessing:
            img = self._preprocess_image(img)

        lang = "+".join(self.config.languages)
        text = self._engine.image_to_string(img, lang=lang)

        data = self._engine.image_to_data(img, lang=lang, output_type=self._engine.Output.DICT)
        confidences = [c for c in data["conf"] if c != -1]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        return OCRResult(
            text=text.strip(),
            confidence=avg_confidence / 100.0,
            metadata={
                "engine": "pytesseract",
                "languages": self.config.languages,
                "word_count": len(data["text"])
            },
            success=avg_confidence >= self.config.confidence_threshold * 100
        )

    async def _extract_easyocr(
        self,
        image_data: bytes,
        **kwargs
    ) -> OCRResult:
        """Extract text using easyocr."""
        from PIL import Image
        import numpy as np

        img = Image.open(BytesIO(image_data))
        img_array = np.array(img)

        results = self._engine.readtext(img_array)

        text = " ".join([result[1] for result in results])
        confidences = [result[2] for result in results]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        return OCRResult(
            text=text.strip(),
            confidence=avg_confidence,
            metadata={
                "engine": "easyocr",
                "languages": self.config.languages,
                "detections": len(results)
            },
            success=avg_confidence >= self.config.confidence_threshold
        )

    def _preprocess_image(self, img):
        """Preprocess image for better OCR accuracy."""
        from PIL import ImageEnhance, ImageFilter

        img = img.convert("L")
        img = img.filter(ImageFilter.MedianFilter())

        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2.0)

        return img

    async def close(self) -> None:
        """Clean up OCR resources."""
        self._engine = None

"""Configuration dataclasses for Vision Service."""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class VisionConfig:
    """Main vision service configuration."""

    model: str = "gpt-4o"
    use_ocr_fallback: bool = True
    ocr_confidence_threshold: float = 0.85
    cost_limit_per_document: float = 0.50
    max_tokens: int = 4096
    temperature: float = 0.0
    timeout: int = 300

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "model": self.model,
            "use_ocr_fallback": self.use_ocr_fallback,
            "ocr_confidence_threshold": self.ocr_confidence_threshold,
            "cost_limit_per_document": self.cost_limit_per_document,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "timeout": self.timeout,
        }


@dataclass
class OCRConfig:
    """OCR engine configuration."""

    engine: str = "pytesseract"
    languages: list[str] = field(default_factory=lambda: ["eng"])
    confidence_threshold: float = 0.85
    preprocessing: bool = True
    dpi: int = 300

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "engine": self.engine,
            "languages": self.languages,
            "confidence_threshold": self.confidence_threshold,
            "preprocessing": self.preprocessing,
            "dpi": self.dpi,
        }


@dataclass
class DocumentConfig:
    """Document handling configuration."""

    supported_formats: list[str] = field(
        default_factory=lambda: ["pdf", "png", "jpg", "jpeg", "tiff", "bmp"]
    )
    max_file_size_mb: float = 20.0
    enable_caching: bool = True
    cache_ttl_seconds: int = 3600
    pdf_dpi: int = 300

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "supported_formats": self.supported_formats,
            "max_file_size_mb": self.max_file_size_mb,
            "enable_caching": self.enable_caching,
            "cache_ttl_seconds": self.cache_ttl_seconds,
            "pdf_dpi": self.pdf_dpi,
        }


@dataclass
class StructuredExtractionConfig:
    """Configuration for structured data extraction."""

    max_retries: int = 3
    validation_mode: str = "strict"  # strict, lenient, none
    enable_fallback: bool = True
    parallel_processing: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "max_retries": self.max_retries,
            "validation_mode": self.validation_mode,
            "enable_fallback": self.enable_fallback,
            "parallel_processing": self.parallel_processing,
        }

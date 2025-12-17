"""Document handling for vision service."""

from __future__ import annotations

import base64
import hashlib
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from io import BytesIO

from .config import DocumentConfig


@dataclass
class DocumentPage:
    """Single document page."""

    image_data: bytes
    page_number: int
    format: str
    width: int
    height: int

    def to_base64(self) -> str:
        """Convert image to base64."""
        return base64.b64encode(self.image_data).decode("utf-8")

    def get_hash(self) -> str:
        """Get content hash."""
        return hashlib.sha256(self.image_data).hexdigest()


@dataclass
class Document:
    """Document container."""

    pages: List[DocumentPage]
    filename: str
    total_pages: int
    file_size_bytes: int
    metadata: Dict[str, Any]

    @property
    def file_size_mb(self) -> float:
        """Get file size in MB."""
        return self.file_size_bytes / (1024 * 1024)


class DocumentHandler:
    """Handle document loading and conversion."""

    def __init__(self, config: DocumentConfig):
        """Initialize document handler.

        Args:
            config: Document configuration
        """
        self.config = config
        self._cache: Dict[str, Document] = {}

    async def load_document(
        self,
        file_path: str | Path,
        **kwargs
    ) -> Document:
        """Load document from file.

        Args:
            file_path: Path to document file
            **kwargs: Additional loading parameters

        Returns:
            Loaded document
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"Document not found: {file_path}")

        file_size = file_path.stat().st_size
        if file_size / (1024 * 1024) > self.config.max_file_size_mb:
            raise ValueError(
                f"File size ({file_size / (1024 * 1024):.2f} MB) exceeds "
                f"limit ({self.config.max_file_size_mb} MB)"
            )

        file_hash = self._get_file_hash(file_path)
        if self.config.enable_caching and file_hash in self._cache:
            return self._cache[file_hash]

        suffix = file_path.suffix.lower().lstrip(".")
        if suffix not in self.config.supported_formats:
            raise ValueError(
                f"Unsupported format: {suffix}. "
                f"Supported: {', '.join(self.config.supported_formats)}"
            )

        if suffix == "pdf":
            document = await self._load_pdf(file_path, **kwargs)
        else:
            document = await self._load_image(file_path, **kwargs)

        if self.config.enable_caching:
            self._cache[file_hash] = document

        return document

    async def load_from_bytes(
        self,
        data: bytes,
        format: str,
        filename: str = "document",
        **kwargs
    ) -> Document:
        """Load document from bytes.

        Args:
            data: Raw document bytes
            format: Document format (pdf, png, jpg, etc.)
            filename: Document filename
            **kwargs: Additional loading parameters

        Returns:
            Loaded document
        """
        if format.lower() not in self.config.supported_formats:
            raise ValueError(
                f"Unsupported format: {format}. "
                f"Supported: {', '.join(self.config.supported_formats)}"
            )

        if format.lower() == "pdf":
            document = await self._load_pdf_bytes(data, filename, **kwargs)
        else:
            document = await self._load_image_bytes(data, format, filename, **kwargs)

        return document

    async def _load_pdf(self, file_path: Path, **kwargs) -> Document:
        """Load PDF document."""
        try:
            from pdf2image import convert_from_path
        except ImportError:
            raise ImportError(
                "pdf2image not installed. Install with: pip install pdf2image"
            )

        images = convert_from_path(
            file_path,
            dpi=self.config.pdf_dpi,
            **kwargs
        )

        pages = []
        for i, img in enumerate(images):
            img_bytes = BytesIO()
            img.save(img_bytes, format="PNG")
            img_bytes.seek(0)

            pages.append(DocumentPage(
                image_data=img_bytes.read(),
                page_number=i + 1,
                format="png",
                width=img.width,
                height=img.height
            ))

        return Document(
            pages=pages,
            filename=file_path.name,
            total_pages=len(pages),
            file_size_bytes=file_path.stat().st_size,
            metadata={"source": "pdf", "dpi": self.config.pdf_dpi}
        )

    async def _load_pdf_bytes(
        self,
        data: bytes,
        filename: str,
        **kwargs
    ) -> Document:
        """Load PDF from bytes."""
        try:
            from pdf2image import convert_from_bytes
        except ImportError:
            raise ImportError(
                "pdf2image not installed. Install with: pip install pdf2image"
            )

        images = convert_from_bytes(
            data,
            dpi=self.config.pdf_dpi,
            **kwargs
        )

        pages = []
        for i, img in enumerate(images):
            img_bytes = BytesIO()
            img.save(img_bytes, format="PNG")
            img_bytes.seek(0)

            pages.append(DocumentPage(
                image_data=img_bytes.read(),
                page_number=i + 1,
                format="png",
                width=img.width,
                height=img.height
            ))

        return Document(
            pages=pages,
            filename=filename,
            total_pages=len(pages),
            file_size_bytes=len(data),
            metadata={"source": "pdf_bytes", "dpi": self.config.pdf_dpi}
        )

    async def _load_image(self, file_path: Path, **kwargs) -> Document:
        """Load image document."""
        from PIL import Image

        img = Image.open(file_path)
        img_bytes = file_path.read_bytes()

        page = DocumentPage(
            image_data=img_bytes,
            page_number=1,
            format=file_path.suffix.lower().lstrip("."),
            width=img.width,
            height=img.height
        )

        return Document(
            pages=[page],
            filename=file_path.name,
            total_pages=1,
            file_size_bytes=len(img_bytes),
            metadata={"source": "image"}
        )

    async def _load_image_bytes(
        self,
        data: bytes,
        format: str,
        filename: str,
        **kwargs
    ) -> Document:
        """Load image from bytes."""
        from PIL import Image

        img = Image.open(BytesIO(data))

        page = DocumentPage(
            image_data=data,
            page_number=1,
            format=format.lower(),
            width=img.width,
            height=img.height
        )

        return Document(
            pages=[page],
            filename=filename,
            total_pages=1,
            file_size_bytes=len(data),
            metadata={"source": "image_bytes"}
        )

    def _get_file_hash(self, file_path: Path) -> str:
        """Get file content hash."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def clear_cache(self) -> None:
        """Clear document cache."""
        self._cache.clear()

    async def close(self) -> None:
        """Clean up resources."""
        self.clear_cache()

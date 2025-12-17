# Vision Service

DRY OOP-based document processing with AI vision models, optimized for agent arg passing.

## Features

- **Dataclass configs** - Easy dict-to-args conversion for all configurations
- **Factory pattern** - `create_vision_service(**kwargs)` for simple instantiation
- **Async-first** - All I/O operations are async
- **Type hints** - Full typing for IDE autocomplete
- **Provider agnostic** - Works with OpenAI, Anthropic, Google providers
- **OCR fallback** - Automatic fallback to pytesseract/easyocr
- **Structured extraction** - Pydantic schema-based data extraction
- **Cost tracking** - Built-in cost monitoring per document

## Quick Start

```python
from services.vision import create_vision_service
from providers import OpenAIProvider, ProviderConfig

# Initialize provider
provider = OpenAIProvider(ProviderConfig(api_key="sk-..."))
await provider.initialize()

# Create vision service from dicts (easy for YAML/JSON configs)
vision_service = await create_vision_service(
    provider=provider,
    vision_config={
        "model": "gpt-4o",
        "max_tokens": 4096,
        "cost_limit_per_document": 0.50
    },
    ocr_config={
        "engine": "pytesseract",
        "languages": ["eng"]
    },
    enable_ocr_fallback=True
)

# Load and process document
document = await vision_service.document_handler.load_document("invoice.pdf")
result = await vision_service.processor.process_document(
    document=document,
    prompt="Extract all text and key information"
)

print(f"Content: {result.content}")
print(f"Cost: ${result.cost:.4f}")
print(f"Pages: {result.pages_processed}")
```

## Structured Extraction

```python
from pydantic import BaseModel

class InvoiceSchema(BaseModel):
    vendor_name: str
    invoice_number: str
    total_amount: float
    date: str
    line_items: list[dict]

# Extract with schema validation
result = await vision_service.extractor.extract_with_schema(
    document=document,
    schema=InvoiceSchema
)

if result.validated:
    print(f"Invoice: {result.data['invoice_number']}")
    print(f"Total: ${result.data['total_amount']}")
else:
    print(f"Validation errors: {result.validation_errors}")
```

## Configuration

All configs are dataclasses that accept either dict or dataclass instances:

### VisionConfig
```python
from services.vision import VisionConfig

config = VisionConfig(
    model="gpt-4o",
    use_ocr_fallback=True,
    ocr_confidence_threshold=0.85,
    cost_limit_per_document=0.50,
    max_tokens=4096,
    temperature=0.0,
    timeout=300
)
```

### OCRConfig
```python
from services.vision import OCRConfig

config = OCRConfig(
    engine="pytesseract",  # or "easyocr"
    languages=["eng"],
    confidence_threshold=0.85,
    preprocessing=True,
    dpi=300
)
```

### DocumentConfig
```python
from services.vision import DocumentConfig

config = DocumentConfig(
    supported_formats=["pdf", "png", "jpg", "jpeg", "tiff", "bmp"],
    max_file_size_mb=20.0,
    enable_caching=True,
    cache_ttl_seconds=3600,
    pdf_dpi=300
)
```

### StructuredExtractionConfig
```python
from services.vision import StructuredExtractionConfig

config = StructuredExtractionConfig(
    max_retries=3,
    validation_mode="strict",  # strict, lenient, none
    enable_fallback=True,
    parallel_processing=False
)
```

## Architecture

```
services/vision/
├── __init__.py          # Factory: create_vision_service()
├── config.py            # Dataclass configs
├── processor.py         # VisionProcessor - core AI processing
├── ocr.py              # OCREngine - fallback text extraction
├── document.py         # DocumentHandler - file loading/conversion
└── structured.py       # StructuredExtractor - schema-based extraction
```

## Provider Integration

The service uses your existing BaseProvider interface:

```python
# OpenAI GPT-4o Vision
from providers import OpenAIProvider

provider = OpenAIProvider(ProviderConfig(api_key="..."))
vision = await create_vision_service(provider=provider)

# Cost tracking is automatic
result = await vision.processor.process_document(doc, "Extract text")
print(f"Total cost so far: ${vision.processor.total_cost:.4f}")
```

## Advanced Usage

### Multi-page processing
```python
# Automatic handling of multi-page PDFs
document = await vision_service.document_handler.load_document("contract.pdf")
print(f"Pages: {document.total_pages}")

# Process all pages (respects cost limit)
result = await vision_service.processor.process_document(
    document=document,
    prompt="Summarize each page"
)
```

### OCR fallback
```python
# Automatically falls back to OCR if vision API fails
result = await vision_service.processor.process_document(
    document=document,
    prompt="Extract text"
)

if result.ocr_fallback_used:
    print("Used OCR fallback")
```

### Custom schemas
```python
# Register schemas for reuse
vision_service.extractor.register_schema("invoice", InvoiceSchema)
vision_service.extractor.register_schema("receipt", ReceiptSchema)

# Use registered schemas
result = await vision_service.extractor.extract(
    document=document,
    schema_name="invoice"
)
```

## Error Handling

```python
try:
    document = await vision_service.document_handler.load_document(path)
    result = await vision_service.processor.process_document(document, prompt)
except FileNotFoundError:
    print("Document not found")
except ValueError as e:
    print(f"Validation error: {e}")
except Exception as e:
    print(f"Processing error: {e}")
```

## Cleanup

```python
# Clean up resources
await vision_service.close()
```

## Dependencies

Required:
- `Pillow` - Image processing
- `pdf2image` - PDF to image conversion
- `pydantic` - Schema validation

Optional:
- `pytesseract` - OCR fallback (requires tesseract binary)
- `easyocr` - Advanced OCR fallback

Install:
```bash
pip install Pillow pdf2image pydantic pytesseract easyocr
```

# Vision Service Architecture

## Design Principles

1. **DRY (Don't Repeat Yourself)** - Shared base patterns, reusable configs
2. **OOP with Composition** - Each class has single responsibility
3. **Easy Arg Passing** - Dataclasses accept dicts or instances
4. **Async-First** - All I/O is non-blocking
5. **Type Safe** - Full type hints for IDE support

## Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     create_vision_service()                      │
│                    (Factory Function)                            │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
         ┌───────────────────────────────┐
         │      VisionService            │
         │  (Composite Container)        │
         └───────────────┬───────────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
         ▼               ▼               ▼
┌────────────────┐ ┌─────────────┐ ┌──────────────┐
│ VisionProcessor│ │ DocumentHandler│ StructuredExtractor│
│                │ │             │ │              │
│ - provider     │ │ - config    │ │ - processor  │
│ - config       │ │ - cache     │ │ - schemas    │
│ - ocr_engine   │ │             │ │ - config     │
└────────┬───────┘ └──────┬──────┘ └──────┬───────┘
         │                │               │
         │                │               │
         ▼                ▼               │
┌────────────────┐ ┌─────────────┐       │
│   OCREngine    │ │  Document   │       │
│                │ │             │       │
│ - config       │ │ - pages[]   │       │
│ - engine       │ │ - metadata  │       │
└────────────────┘ └──────┬──────┘       │
                          │              │
                          ▼              │
                   ┌─────────────┐       │
                   │ DocumentPage│       │
                   │             │       │
                   │ - image_data│       │
                   │ - metadata  │       │
                   └─────────────┘       │
                                         │
                    ┌────────────────────┘
                    │
                    ▼
            ┌──────────────┐
            │ Pydantic     │
            │ Schemas      │
            └──────────────┘
```

## Data Flow

### 1. Basic Document Processing
```
File Path
   │
   ▼
DocumentHandler.load_document()
   │
   ▼
Document (with pages)
   │
   ▼
VisionProcessor.process_document()
   │
   ├─► Provider.chat() ──► VisionResult
   │
   └─► (if fails) ──► OCREngine.extract_text() ──► OCRResult
```

### 2. Structured Extraction
```
Document + Schema
   │
   ▼
StructuredExtractor.extract_with_schema()
   │
   ▼
VisionProcessor.process_document()
   │
   ▼
JSON Response
   │
   ▼
Pydantic Validation
   │
   ▼
ExtractionResult (validated data)
```

## Configuration Pattern

All configs use the same pattern for easy dict→args conversion:

```python
@dataclass
class Config:
    field1: type = default
    field2: type = default
    
    def to_dict(self) -> Dict[str, Any]:
        return {...}

# Usage 1: Direct instantiation
config = Config(field1=value1, field2=value2)

# Usage 2: From dict (YAML/JSON)
config = Config(**yaml_dict)

# Usage 3: Mixed
create_service(config=Config(...))
create_service(config={"field1": value1})  # Auto-converted
```

## Class Responsibilities

### VisionProcessor
- Core AI vision processing
- Provider communication
- Cost tracking
- OCR fallback orchestration

### DocumentHandler
- Load files (PDF, images)
- Convert PDFs to images
- Caching
- Format validation

### OCREngine
- Text extraction fallback
- Multiple backend support (pytesseract, easyocr)
- Confidence scoring
- Image preprocessing

### StructuredExtractor
- Schema-based extraction
- JSON parsing
- Pydantic validation
- Retry logic

## Provider Integration

The service is provider-agnostic via BaseProvider interface:

```python
class VisionProcessor:
    def __init__(self, provider: BaseProvider, ...):
        self.provider = provider  # Any provider works
        
    async def process_document(self, ...):
        response = await self.provider.chat(
            messages=self._build_vision_messages(...),
            model=self.config.model,
            ...
        )
        # Returns standard CompletionResponse
```

## Key Design Decisions

### 1. Why Dataclasses?
- Easy dict conversion: `Config(**dict)`
- Immutable by default (frozen=True optional)
- Type hints for IDE support
- No boilerplate __init__

### 2. Why Factory Function?
- Single entry point: `create_vision_service()`
- Handles initialization order
- Accepts dicts or instances
- Easy for agents to call

### 3. Why Composition?
- Each class has single purpose
- Easy to test individually
- Flexible to swap components
- Clear dependencies

### 4. Why Async?
- Non-blocking I/O
- Parallel processing support
- Future-proof for streaming
- Better for agents

## Extension Points

### Add New OCR Engine
```python
# In ocr.py
async def _extract_custom(self, image_data, **kwargs) -> OCRResult:
    # Your implementation
    pass
```

### Add New Document Format
```python
# In document.py
async def _load_custom_format(self, file_path, **kwargs) -> Document:
    # Your implementation
    pass
```

### Add New Provider
Just implement BaseProvider interface - no changes to vision service needed!

## Testing Strategy

Each component can be tested independently:

```python
# Test OCR
ocr = OCREngine(config=OCRConfig(engine="pytesseract"))
await ocr.initialize()
result = await ocr.extract_text(image_bytes)

# Test Document Handler
handler = DocumentHandler(config=DocumentConfig())
doc = await handler.load_document("test.pdf")

# Test Vision Processor (mock provider)
processor = VisionProcessor(mock_provider, config)
result = await processor.process_document(doc, prompt)
```

## Performance Considerations

1. **Caching** - DocumentHandler caches by file hash
2. **Lazy Init** - OCR engines initialized only when needed
3. **Streaming** - Provider interface supports streaming
4. **Parallel** - Multi-page can be processed in parallel (future)
5. **Cost Limits** - Built-in cost tracking prevents overruns

## Security Notes

- File size limits enforced
- Format validation on load
- No arbitrary code execution
- Provider API keys handled by provider layer
- Image data never logged


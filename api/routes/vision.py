"""Vision service endpoints."""

import os
import json
import tempfile
from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

from api.state import app_state
from services.vision.processor import VisionProcessor, VisionResult
from services.vision.document import DocumentHandler
from services.vision.config import VisionConfig, DocumentConfig
from services.vision.models import Invoice, Receipt
from services.vision.bbox_extractor import BBoxExtractor
from services.vision.text_matcher import TextMatcher

router = APIRouter()


class VisionResponse(BaseModel):
    content: str
    pages_processed: int
    cost: float
    provider: str
    model: str


@router.post("/extract", response_model=VisionResponse)
async def extract_document(
    file: UploadFile = File(...),
    extract_type: str = Form("structured"),
    detail: str = Form("auto"),
    model: str = Form("gpt-4o"),
    include_bbox: bool = Form(False)
):
    """Extract data from uploaded document with optional bounding boxes."""
    try:
        openai_provider = app_state.get("openai")
        if not openai_provider:
            raise HTTPException(status_code=500, detail="OpenAI provider not initialized")

        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        try:
            # Load document using DocumentHandler
            doc_config = DocumentConfig()
            doc_handler = DocumentHandler(config=doc_config)
            document = await doc_handler.load_document(tmp_path)

            # Build prompt based on extract_type
            bbox_instruction = ""
            if include_bbox:
                bbox_instruction = """

BOUNDING BOX REQUIREMENTS:
For EACH extracted field, include the bounding box coordinates in normalized format (0-1):
- page: 1-indexed page number where the field appears
- x: normalized x-coordinate of top-left corner (0 = left edge, 1 = right edge)
- y: normalized y-coordinate of top-left corner (0 = top edge, 1 = bottom edge)
- width: normalized width (0-1)
- height: normalized height (0-1)

Structure each field as: {"value": <extracted_value>, "bbox": {"page": N, "x": 0.X, "y": 0.Y, "width": 0.W, "height": 0.H}}"""

            prompts = {
                "structured": f"Extract all text and structure from this document in a clear, organized format.{bbox_instruction}",
                "invoice": f"""Extract complete invoice data from this multi-page invoice document.

IMPORTANT CONTEXT:
- The vendor information, invoice number, and date typically appear on page 1 only
- Line items span across multiple pages - consolidate ALL line items from ALL pages
- The subtotal and total typically appear on the last page
- Do NOT repeat vendor/header information for each page

Return ONE consolidated JSON object with:
- Vendor details from the first page
- ALL line items aggregated from every page
- Financial totals from the last page

Ensure all monetary values are accurate to 2 decimal places.{bbox_instruction}""",
                "ocr": f"Extract all visible text from this document.{bbox_instruction}",
                "tables": f"Extract all tables from this document in markdown format.{bbox_instruction}"
            }
            prompt = prompts.get(extract_type, prompts["structured"])

            # Process document
            config = VisionConfig(model=model)
            processor = VisionProcessor(provider=openai_provider, config=config)

            # For invoice extraction, use structured output with JSON schema
            if extract_type == "invoice":
                # Use regular invoice schema (without bbox) for GPT-4o extraction
                # We'll add bboxes via hybrid approach if requested
                invoice_schema = Invoice.model_json_schema()

                # OpenAI structured outputs format per API docs
                # NOTE: strict=False allows optional fields with anyOf/null
                response_format = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "invoice_extraction",
                        "description": "Structured invoice data extraction",
                        "schema": invoice_schema,
                        "strict": False
                    }
                }

                # Pass response_format and detail as kwargs
                result = await processor.process_document(
                    document,
                    prompt,
                    detail=detail,
                    response_format=response_format
                )

                # If bounding boxes requested, use hybrid approach
                if include_bbox:
                    try:
                        # Parse extracted invoice data
                        extracted_data = json.loads(result.content)

                        # Use hybrid approach: pdfplumber for precise coordinates
                        extractor = BBoxExtractor(tmp_path)

                        # DEBUG: Log extracted words
                        words = extractor.extract_words()
                        print(f"\n🔍 DEBUG: Extracted {len(words)} words from PDF")
                        print(f"📄 First 20 words: {[w.text for w in words[:20]]}")

                        # Check if PDF is text-based
                        if extractor.is_text_based_pdf():
                            # Use pdfplumber for accurate coordinates
                            matcher = TextMatcher(extractor)
                            match_results = matcher.match_invoice_fields(extracted_data)

                            # DEBUG: Log match results
                            print(f"\n📊 MATCH RESULTS:")
                            for field_name, match in match_results.items():
                                if isinstance(match, list):
                                    print(f"  {field_name}: {len(match)} items")
                                    # Check line items in detail
                                    for idx, item_matches in enumerate(match):
                                        print(f"    Item {idx}:")
                                        for item_field, item_match in item_matches.items():
                                            status = "✅" if item_match.bbox else "❌"
                                            print(f"      {status} {item_field}: {item_match.match_method}")
                                else:
                                    status = "✅" if match.bbox else "❌"
                                    if match.bbox:
                                        # Show what text was actually matched
                                        print(f"  {status} {field_name}: {match.match_method} (conf: {match.confidence:.2f})")
                                        print(f"      Matched PDF text: '{match.bbox.text[:50]}...'")
                                        print(f"      Looking for value: '{str(match.value)[:50]}...'")
                                    else:
                                        print(f"  {status} {field_name}: {match.match_method} (conf: {match.confidence:.2f})")

                            # Merge bboxes into extracted data
                            data_with_bbox = matcher.create_bbox_dict(
                                extracted_data,
                                match_results,
                                include_confidence=True
                            )

                            # DEBUG: Log final data structure
                            print(f"\n📦 FINAL DATA STRUCTURE:")
                            for field_name, field_value in data_with_bbox.items():
                                if isinstance(field_value, dict) and 'bbox' in field_value:
                                    print(f"  ✅ {field_name}: has bbox (pg {field_value['bbox']['page']})")
                                elif isinstance(field_value, list):
                                    print(f"  📋 {field_name}: {len(field_value)} items")
                                else:
                                    print(f"  ❌ {field_name}: NO bbox")

                            # Update result content with bbox-enhanced data
                            result = VisionResult(
                                content=json.dumps(data_with_bbox, indent=2),
                                pages_processed=result.pages_processed,
                                cost=result.cost,
                                provider=result.provider,
                                model=f"{result.model} + pdfplumber",
                                metadata={
                                    **result.metadata,
                                    "bbox_method": "hybrid_pdfplumber",
                                    "text_coverage": extractor.get_text_coverage()
                                }
                            )
                        else:
                            # Scanned PDF - fall back to GPT-4o bbox (lower accuracy)
                            # Could integrate with Azure Document Intelligence here
                            result.metadata["bbox_method"] = "scanned_pdf_fallback"
                            result.metadata["bbox_warning"] = "Scanned PDF detected - bbox accuracy may be lower"

                    except Exception as e:
                        # If hybrid approach fails, log and continue with original result
                        print(f"⚠️ Hybrid bbox extraction failed: {e}")
                        result.metadata["bbox_error"] = str(e)
                        result.metadata["bbox_method"] = "hybrid_failed"

            else:
                # For other types, pass detail only
                result = await processor.process_document(document, prompt, detail=detail)

            return VisionResponse(
                content=result.content,
                pages_processed=result.pages_processed,
                cost=result.cost,
                provider=result.provider,
                model=result.model
            )

        finally:
            # Cleanup temp file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ocr")
async def ocr_document(
    file: UploadFile = File(...),
):
    """OCR text extraction from document."""
    try:
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        try:
            document = await Document.from_file(tmp_path)

            return {
                "text": "OCR text would go here",  # Implement OCR
                "pages": document.total_pages
            }

        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

"""
Document Processing Pipeline - E2E orchestrator with ACID transactions.

Coordinates the complete document processing workflow:
1. Store file (content-addressable storage)
2. Create signal (idempotency check)
3. Extract via Vision API
4. Classify document
5. Resolve vendor (entity resolver)
6. Create commitment (if applicable)
7. Create document links
8. Log interactions
9. Update signal status
10. Commit transaction (ACID guarantee)
"""

import time
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import uuid

from memory.models import Document, DocumentLink
from services.document_intelligence.storage import ContentAddressableStorage
from services.document_intelligence.signal_processor import SignalProcessor
from services.document_intelligence.entity_resolver import EntityResolver
from services.document_intelligence.commitment_manager import CommitmentManager
from services.document_intelligence.interaction_logger import InteractionLogger
from services.vision.processor import VisionProcessor
from services.vision.document import DocumentHandler
from services.vision.config import DocumentConfig


@dataclass
class PipelineResult:
    """Result of document processing pipeline.

    Attributes:
        document_id: Created document ID
        signal_id: Created signal ID
        vendor_id: Resolved vendor party ID (optional)
        commitment_id: Created commitment ID (optional)
        interaction_ids: List of logged interaction IDs
        metrics: Pipeline execution metrics
        error: Error message if pipeline failed (optional)
    """

    document_id: Optional[uuid.UUID]
    signal_id: Optional[uuid.UUID]
    vendor_id: Optional[uuid.UUID]
    commitment_id: Optional[uuid.UUID]
    interaction_ids: List[uuid.UUID]
    metrics: Dict[str, Any]
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        """Check if pipeline succeeded."""
        return self.error is None


class DocumentProcessingPipeline:
    """Orchestrates end-to-end document processing with ACID transactions.

    This is the main entry point for document uploads. It coordinates:
    - File storage (content-addressable)
    - Signal creation (idempotency)
    - Vision AI extraction
    - Document classification
    - Entity resolution (vendor lookup/creation)
    - Commitment creation (auto-create from invoices)
    - Document linking (polymorphic references)
    - Interaction logging (audit trail)
    - Signal lifecycle management

    All operations happen within a single database transaction for ACID guarantees.

    Example:
        pipeline = DocumentProcessingPipeline(
            storage=storage,
            signal_processor=signal_processor,
            vision_processor=vision_processor,
            entity_resolver=entity_resolver,
            commitment_manager=commitment_manager,
            interaction_logger=interaction_logger
        )

        result = await pipeline.process_document_upload(
            db=db_session,
            file_bytes=pdf_bytes,
            filename="invoice.pdf",
            mime_type="application/pdf",
            user_id=user_uuid
        )

        if result.success:
            print(f"Document processed: {result.document_id}")
            print(f"Vendor: {result.vendor_id}")
            print(f"Commitment: {result.commitment_id}")
        else:
            print(f"Error: {result.error}")
    """

    def __init__(
        self,
        storage: ContentAddressableStorage,
        signal_processor: SignalProcessor,
        vision_processor: VisionProcessor,
        entity_resolver: EntityResolver,
        commitment_manager: CommitmentManager,
        interaction_logger: InteractionLogger
    ):
        """Initialize document processing pipeline.

        Args:
            storage: Content-addressable storage service
            signal_processor: Signal processor for idempotency
            vision_processor: Vision API processor for extraction
            entity_resolver: Entity resolver for vendor lookup
            commitment_manager: Commitment manager for obligation creation
            interaction_logger: Interaction logger for audit trail
        """
        self.storage = storage
        self.signal_processor = signal_processor
        self.vision_processor = vision_processor
        self.entity_resolver = entity_resolver
        self.commitment_manager = commitment_manager
        self.interaction_logger = interaction_logger

    async def process_document_upload(
        self,
        db: AsyncSession,
        file_bytes: bytes,
        filename: str,
        mime_type: str,
        user_id: Optional[uuid.UUID] = None
    ) -> PipelineResult:
        """Process document upload with full E2E workflow.

        All operations happen within the provided database session's transaction.
        The caller is responsible for committing or rolling back the transaction.

        Workflow:
        1. Store file (content-addressable storage)
        2. Create signal (idempotency check)
        3. Extract via Vision API
        4. Classify document
        5. Resolve vendor (if applicable)
        6. Create commitment (if invoice)
        7. Create document links
        8. Log interactions
        9. Update signal status
        10. Return result (caller commits transaction)

        Args:
            db: Database session (transaction managed by caller)
            file_bytes: Raw file bytes
            filename: Original filename
            mime_type: MIME type (e.g., "application/pdf")
            user_id: Optional user ID

        Returns:
            PipelineResult with created entities and metrics

        Example:
            async with db.begin():  # Start transaction
                result = await pipeline.process_document_upload(
                    db=db,
                    file_bytes=pdf_bytes,
                    filename="invoice.pdf",
                    mime_type="application/pdf"
                )
                if result.success:
                    await db.commit()  # Commit on success
                else:
                    await db.rollback()  # Rollback on error
        """
        start_time = time.time()
        interaction_ids = []
        metrics = {}

        try:
            # Step 1: Store file (content-addressable storage)
            storage_result = await self.storage.store(
                file_bytes=file_bytes,
                filename=filename,
                mime_type=mime_type
            )
            sha256 = storage_result.sha256
            storage_path = storage_result.storage_path
            deduplicated = storage_result.deduplicated

            metrics["storage"] = {
                "sha256": sha256,
                "deduplicated": deduplicated,
                "size_bytes": len(file_bytes)
            }

            # Step 2: Create signal (idempotency check)
            signal = await self.signal_processor.create_signal(
                db=db,
                source="vision_upload",
                payload={
                    "filename": filename,
                    "mime_type": mime_type,
                    "size": len(file_bytes)
                },
                dedupe_key=sha256
            )

            # Check if signal was already processed
            if signal.status == "attached":
                # Document already processed, fetch existing document ID from links
                from sqlalchemy import select
                from memory.models import DocumentLink

                link_query = select(DocumentLink).where(
                    DocumentLink.entity_type == "signal",
                    DocumentLink.entity_id == signal.id,
                    DocumentLink.link_type == "extracted_from"
                )
                link_result = await db.execute(link_query)
                link = link_result.scalar_one_or_none()

                existing_document_id = link.document_id if link else None

                metrics["idempotent_skip"] = True
                return PipelineResult(
                    document_id=existing_document_id,
                    signal_id=signal.id,
                    vendor_id=None,
                    commitment_id=None,
                    interaction_ids=[],
                    metrics=metrics
                )

            # Update signal to processing
            await self.signal_processor.update_signal_status(
                db=db,
                signal_id=signal.id,
                status="processing"
            )

            # Step 3: Extract via Vision API
            extraction_start = time.time()

            # Load document for vision processing
            doc_config = DocumentConfig()
            doc_handler = DocumentHandler(config=doc_config)
            # Extract file extension from filename
            file_ext = filename.split('.')[-1] if '.' in filename else 'pdf'
            vision_doc = await doc_handler.load_from_bytes(
                data=file_bytes,
                format=file_ext,
                filename=filename
            )

            # Extract structured data
            vision_result = await self.vision_processor.analyze_document(
                document=vision_doc,
                analysis_type="invoice"  # Default to invoice, can be made dynamic
            )

            extraction_duration = time.time() - extraction_start

            # Parse extraction result (simplified - real implementation would use structured extraction)
            extraction_data = self._parse_vision_result(vision_result.content)

            metrics["extraction"] = {
                "cost": float(vision_result.cost),
                "model": vision_result.model,
                "duration_seconds": extraction_duration,
                "pages_processed": vision_result.pages_processed
            }

            # Step 4: Classify document
            doc_type, confidence = self.signal_processor.classify_document(
                filename=filename,
                mime_type=mime_type
            )
            extraction_type = self.signal_processor.get_extraction_type(doc_type)

            metrics["classification"] = {
                "document_type": str(doc_type),
                "extraction_type": extraction_type,
                "confidence": confidence
            }

            # Create Document record
            document = Document(
                id=uuid.uuid4(),
                path=storage_path,
                content=vision_result.content[:1000],  # Store preview
                content_hash=sha256,
                sha256=sha256,
                source="vision_upload",
                mime_type=mime_type,
                file_size=len(file_bytes),
                storage_uri=f"file://{storage_path}",
                extraction_type=extraction_type,
                extraction_data=extraction_data,
                extraction_cost=vision_result.cost,
                extracted_at=datetime.utcnow(),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )

            db.add(document)
            await db.flush()  # Get document ID

            # Step 5: Resolve vendor (if applicable)
            vendor_id = None
            role_id = None

            vendor_name = extraction_data.get("vendor_name") or extraction_data.get("vendor")
            if vendor_name:
                vendor_info = {
                    "address": extraction_data.get("vendor_address"),
                    "tax_id": extraction_data.get("vendor_tax_id"),
                    "phone": extraction_data.get("vendor_phone"),
                    "email": extraction_data.get("vendor_email")
                }

                # Resolve vendor using new API (returns ResolutionResult)
                resolution_result = await self.entity_resolver.resolve_vendor(
                    db=db,
                    vendor_name=vendor_name,
                    vendor_info=vendor_info
                )
                vendor_id = resolution_result.party.id

                # Create vendor role
                role, role_created = await self.entity_resolver.get_or_create_role(
                    db=db,
                    party_id=resolution_result.party.id,
                    role_name="vendor",
                    user_id=user_id
                )
                role_id = role.id

                metrics["vendor_resolution"] = {
                    "vendor_id": str(vendor_id),
                    "vendor_name": vendor_name,
                    "created_new": not resolution_result.matched,
                    "confidence": resolution_result.confidence,
                    "tier": resolution_result.tier
                }

                # Log vendor creation (only if new)
                if not resolution_result.matched:
                    interaction = await self.interaction_logger.log_entity_created(
                        db=db,
                        entity_type="party",
                        entity_id=resolution_result.party.id,
                        metadata={
                            "name": vendor_name,
                            "kind": "org",
                            "created_new": True
                        }
                    )
                    interaction_ids.append(interaction.id)

            # Step 6: Create commitment (if invoice)
            commitment_id = None
            if extraction_type == "invoice" and role_id:
                commitment = await self.commitment_manager.create_invoice_commitment(
                    db=db,
                    role_id=role_id,
                    invoice_data=extraction_data,
                    vendor_name=vendor_name or "Unknown Vendor"
                )
                commitment_id = commitment.id

                metrics["commitment"] = {
                    "commitment_id": str(commitment_id),
                    "title": commitment.title,
                    "priority": commitment.priority,
                    "due_date": str(commitment.due_date) if commitment.due_date else None
                }

                # Log commitment creation
                interaction = await self.interaction_logger.log_entity_created(
                    db=db,
                    entity_type="commitment",
                    entity_id=commitment.id,
                    metadata={
                        "title": commitment.title,
                        "priority": commitment.priority,
                        "commitment_type": commitment.commitment_type
                    }
                )
                interaction_ids.append(interaction.id)

            # Step 7: Create document links
            links_created = []

            # Link to signal
            signal_link = DocumentLink(
                id=uuid.uuid4(),
                document_id=document.id,
                entity_type="signal",
                entity_id=signal.id,
                link_type="extracted_from",
                metadata_={"source": "vision_upload"},
                created_at=datetime.utcnow()
            )
            db.add(signal_link)
            links_created.append("signal")

            # Link to vendor (if exists)
            if vendor_id:
                vendor_link = DocumentLink(
                    id=uuid.uuid4(),
                    document_id=document.id,
                    entity_type="party",
                    entity_id=vendor_id,
                    link_type="vendor",
                    metadata_={"vendor_name": vendor_name},
                    created_at=datetime.utcnow()
                )
                db.add(vendor_link)
                links_created.append("vendor")

            # Link to commitment (if exists)
            if commitment_id:
                commitment_link = DocumentLink(
                    id=uuid.uuid4(),
                    document_id=document.id,
                    entity_type="commitment",
                    entity_id=commitment_id,
                    link_type="obligation",
                    metadata_={},
                    created_at=datetime.utcnow()
                )
                db.add(commitment_link)
                links_created.append("commitment")

            await db.flush()

            metrics["links"] = {
                "count": len(links_created),
                "types": links_created
            }

            # Step 8: Log interactions
            # Log upload
            upload_interaction = await self.interaction_logger.log_upload(
                db=db,
                user_id=user_id,
                document_id=document.id,
                metadata={
                    "filename": filename,
                    "size": len(file_bytes),
                    "mime_type": mime_type,
                    "source": "vision_upload"
                }
            )
            interaction_ids.append(upload_interaction.id)

            # Log extraction
            extraction_interaction = await self.interaction_logger.log_extraction(
                db=db,
                document_id=document.id,
                cost=float(vision_result.cost),
                model=vision_result.model,
                duration=extraction_duration,
                metadata={
                    "pages_processed": vision_result.pages_processed,
                    "extraction_type": extraction_type
                }
            )
            interaction_ids.append(extraction_interaction.id)

            # Step 9: Update signal status
            await self.signal_processor.update_signal_status(
                db=db,
                signal_id=signal.id,
                status="attached",
                processed_at=datetime.utcnow()
            )

            # Step 10: Calculate final metrics
            total_duration = time.time() - start_time
            metrics["pipeline"] = {
                "total_duration_seconds": total_duration,
                "success": True
            }

            # Return result (caller commits transaction)
            return PipelineResult(
                document_id=document.id,
                signal_id=signal.id,
                vendor_id=vendor_id,
                commitment_id=commitment_id,
                interaction_ids=interaction_ids,
                metrics=metrics
            )

        except Exception as e:
            # Log error
            error_msg = str(e)
            metrics["pipeline"] = {
                "total_duration_seconds": time.time() - start_time,
                "success": False,
                "error": error_msg
            }

            # Try to log error interaction
            try:
                error_interaction = await self.interaction_logger.log_error(
                    db=db,
                    error_type="pipeline_error",
                    error_message=error_msg,
                    metadata={
                        "filename": filename,
                        "step": "unknown",
                        "metrics": metrics
                    }
                )
                interaction_ids.append(error_interaction.id)
            except Exception:
                # If error logging fails, continue
                pass

            # Return error result
            return PipelineResult(
                document_id=None,
                signal_id=None,
                vendor_id=None,
                commitment_id=None,
                interaction_ids=interaction_ids,
                metrics=metrics,
                error=error_msg
            )

    def _parse_vision_result(self, content: str) -> Dict[str, Any]:
        """Parse vision API result into structured data.

        This is a simplified parser. A production implementation would:
        - Use structured extraction with JSON schema
        - Handle multiple document types
        - Validate extracted data
        - Apply business rules

        Args:
            content: Raw vision API response

        Returns:
            Structured extraction data
        """
        # Simple keyword extraction (production would use structured extraction)
        data = {}

        # Try to extract common invoice fields
        lines = content.lower().split('\n')

        for line in lines:
            # Vendor name
            if 'vendor' in line or 'from' in line or 'bill from' in line:
                # Extract vendor name (simplified)
                parts = line.split(':')
                if len(parts) > 1:
                    data['vendor_name'] = parts[1].strip()

            # Invoice number
            if 'invoice' in line and '#' in line:
                parts = line.split('#')
                if len(parts) > 1:
                    data['invoice_number'] = parts[1].strip().split()[0]

            # Total amount
            if 'total' in line or 'amount due' in line:
                # Extract amount (simplified - look for $ or numbers)
                import re
                amounts = re.findall(r'\$?\d+[,\d]*\.?\d*', line)
                if amounts:
                    amount_str = amounts[-1].replace('$', '').replace(',', '')
                    try:
                        data['total'] = float(amount_str)
                    except ValueError:
                        pass

            # Due date
            if 'due' in line and 'date' in line:
                # Extract date (simplified)
                import re
                dates = re.findall(r'\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}', line)
                if dates:
                    data['due_date'] = dates[0]

        # Fallback defaults
        data.setdefault('vendor_name', 'Unknown Vendor')
        data.setdefault('invoice_number', 'N/A')
        data.setdefault('total', 0.0)

        return data

"""Structured data extraction from documents."""

import json
from typing import Dict, Any, Type, Optional, List
from dataclasses import dataclass
from pydantic import BaseModel, ValidationError

from .processor import VisionProcessor, VisionResult
from .document import Document
from .config import StructuredExtractionConfig


@dataclass
class ExtractionResult:
    """Structured extraction result."""

    data: Dict[str, Any]
    validated: bool
    schema_name: str
    vision_result: VisionResult
    validation_errors: Optional[List[str]] = None


class StructuredExtractor:
    """Extract structured data using vision AI and Pydantic schemas."""

    def __init__(
        self,
        processor: VisionProcessor,
        config: Optional[StructuredExtractionConfig] = None
    ):
        """Initialize structured extractor.

        Args:
            processor: Vision processor instance
            config: Extraction configuration
        """
        self.processor = processor
        self.config = config or StructuredExtractionConfig()
        self._schemas: Dict[str, Type[BaseModel]] = {}

    def register_schema(
        self,
        name: str,
        schema: Type[BaseModel]
    ) -> None:
        """Register a Pydantic schema for extraction.

        Args:
            name: Schema identifier
            schema: Pydantic model class
        """
        self._schemas[name] = schema

    async def extract(
        self,
        document: Document,
        schema_name: str,
        additional_instructions: Optional[str] = None,
        **kwargs
    ) -> ExtractionResult:
        """Extract structured data from document.

        Args:
            document: Document to extract from
            schema_name: Name of registered schema to use
            additional_instructions: Extra extraction instructions
            **kwargs: Additional processing parameters

        Returns:
            Extraction result with validated data
        """
        if schema_name not in self._schemas:
            raise ValueError(f"Schema '{schema_name}' not registered")

        schema = self._schemas[schema_name]

        for attempt in range(self.config.max_retries):
            try:
                prompt = self._build_extraction_prompt(
                    schema,
                    additional_instructions
                )

                vision_result = await self.processor.process_document(
                    document=document,
                    prompt=prompt,
                    **kwargs
                )

                data = self._parse_json_response(vision_result.content)

                if self.config.validation_mode != "none":
                    validated_data, errors = self._validate_data(data, schema)

                    if errors and self.config.validation_mode == "strict":
                        if attempt < self.config.max_retries - 1:
                            continue

                        return ExtractionResult(
                            data=data,
                            validated=False,
                            schema_name=schema_name,
                            vision_result=vision_result,
                            validation_errors=errors
                        )

                    return ExtractionResult(
                        data=validated_data,
                        validated=True,
                        schema_name=schema_name,
                        vision_result=vision_result,
                        validation_errors=errors if errors else None
                    )
                else:
                    return ExtractionResult(
                        data=data,
                        validated=False,
                        schema_name=schema_name,
                        vision_result=vision_result
                    )

            except Exception as e:
                if attempt == self.config.max_retries - 1:
                    raise
                continue

        raise ValueError(f"Failed to extract after {self.config.max_retries} attempts")

    async def extract_with_schema(
        self,
        document: Document,
        schema: Type[BaseModel],
        additional_instructions: Optional[str] = None,
        **kwargs
    ) -> ExtractionResult:
        """Extract using ad-hoc schema (without registration).

        Args:
            document: Document to extract from
            schema: Pydantic model class
            additional_instructions: Extra extraction instructions
            **kwargs: Additional processing parameters

        Returns:
            Extraction result
        """
        schema_name = schema.__name__
        self.register_schema(schema_name, schema)

        return await self.extract(
            document=document,
            schema_name=schema_name,
            additional_instructions=additional_instructions,
            **kwargs
        )

    def _build_extraction_prompt(
        self,
        schema: Type[BaseModel],
        additional_instructions: Optional[str] = None
    ) -> str:
        """Build extraction prompt from schema."""
        schema_json = schema.model_json_schema()

        prompt_parts = [
            "Extract the following information from this document.",
            "Return the data as a valid JSON object matching this schema:\n",
            json.dumps(schema_json, indent=2),
            "\nRules:",
            "- Return ONLY valid JSON, no additional text",
            "- Use null for missing/unavailable fields",
            "- Follow the exact field names and types specified",
        ]

        if additional_instructions:
            prompt_parts.append(f"\nAdditional instructions:\n{additional_instructions}")

        return "\n".join(prompt_parts)

    def _parse_json_response(self, content: str) -> Dict[str, Any]:
        """Parse JSON from AI response."""
        content = content.strip()

        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]

        content = content.strip()

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON response: {e}\nContent: {content}")

    def _validate_data(
        self,
        data: Dict[str, Any],
        schema: Type[BaseModel]
    ) -> tuple[Dict[str, Any], Optional[List[str]]]:
        """Validate extracted data against schema."""
        try:
            validated = schema(**data)
            return validated.model_dump(), None
        except ValidationError as e:
            errors = [f"{err['loc']}: {err['msg']}" for err in e.errors()]

            if self.config.validation_mode == "lenient":
                return data, errors
            else:
                return data, errors

    def get_registered_schemas(self) -> List[str]:
        """Get list of registered schema names."""
        return list(self._schemas.keys())

    async def close(self) -> None:
        """Clean up resources."""
        await self.processor.close()

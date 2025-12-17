"""ResultFusion - Merge and synthesize results from multiple services."""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class FusedResult:
    """Unified result from multiple services."""
    primary_result: Any
    supporting_results: List[Dict[str, Any]]
    synthesis: str
    metadata: Dict[str, Any]
    sources: List[str]
    confidence: float
    timestamp: datetime


class ResultFusion:
    """Merge results from multiple services into unified response."""

    def __init__(self):
        """Initialize result fusion."""
        self.fusion_strategies = {
            "concatenate": self._concatenate_results,
            "synthesize": self._synthesize_results,
            "prioritize": self._prioritize_results,
            "merge": self._merge_structured_results
        }

    async def fuse_results(
        self,
        results: List[Any],
        strategy: str = "synthesize",
        metadata: Optional[Dict[str, Any]] = None
    ) -> FusedResult:
        """Fuse multiple service results into unified response.

        Args:
            results: List of results from different services
            strategy: Fusion strategy (concatenate, synthesize, prioritize, merge)
            metadata: Additional metadata about the results

        Returns:
            FusedResult with unified response
        """
        if not results:
            return self._empty_result()

        # Filter out errors
        valid_results = [r for r in results if not isinstance(r, dict) or "error" not in r]
        error_results = [r for r in results if isinstance(r, dict) and "error" in r]

        if not valid_results:
            return self._error_result(error_results)

        # Apply fusion strategy
        fusion_func = self.fusion_strategies.get(strategy, self._synthesize_results)
        primary, synthesis = fusion_func(valid_results)

        # Calculate confidence
        confidence = self._calculate_confidence(valid_results, error_results)

        # Extract sources
        sources = self._extract_sources(valid_results, metadata)

        return FusedResult(
            primary_result=primary,
            supporting_results=[
                {"index": i, "result": r}
                for i, r in enumerate(valid_results[1:])
            ],
            synthesis=synthesis,
            metadata=metadata or {},
            sources=sources,
            confidence=confidence,
            timestamp=datetime.now()
        )

    def _concatenate_results(self, results: List[Any]) -> tuple[Any, str]:
        """Simply concatenate all results.

        Args:
            results: List of results

        Returns:
            (primary_result, synthesis_text)
        """
        primary = results[0]

        synthesis_parts = []
        for i, result in enumerate(results, 1):
            if isinstance(result, str):
                synthesis_parts.append(f"Result {i}: {result}")
            elif isinstance(result, dict):
                synthesis_parts.append(f"Result {i}: {result.get('content', result)}")
            else:
                synthesis_parts.append(f"Result {i}: {str(result)}")

        synthesis = "\n\n".join(synthesis_parts)

        return primary, synthesis

    def _synthesize_results(self, results: List[Any]) -> tuple[Any, str]:
        """Synthesize results with context and connections.

        Args:
            results: List of results

        Returns:
            (primary_result, synthesis_text)
        """
        primary = results[0]

        synthesis_parts = ["# Synthesized Results\n"]

        for i, result in enumerate(results, 1):
            if isinstance(result, dict):
                content = result.get("content", result.get("result", str(result)))
                source = result.get("service", f"Service {i}")
                synthesis_parts.append(f"## From {source}:\n{content}")
            elif isinstance(result, str):
                synthesis_parts.append(f"## Result {i}:\n{result}")
            else:
                synthesis_parts.append(f"## Result {i}:\n{str(result)}")

        if len(results) > 1:
            synthesis_parts.append("\n## Summary:")
            synthesis_parts.append(
                f"Successfully combined {len(results)} results from multiple services."
            )

        synthesis = "\n\n".join(synthesis_parts)

        return primary, synthesis

    def _prioritize_results(self, results: List[Any]) -> tuple[Any, str]:
        """Prioritize first result, provide others as context.

        Args:
            results: List of results

        Returns:
            (primary_result, synthesis_text)
        """
        primary = results[0]

        synthesis = f"Primary result: {self._format_result(primary)}\n"

        if len(results) > 1:
            synthesis += f"\nSupporting information from {len(results) - 1} additional source(s):\n"
            for i, result in enumerate(results[1:], 1):
                synthesis += f"\n{i}. {self._format_result(result)}"

        return primary, synthesis

    def _merge_structured_results(self, results: List[Any]) -> tuple[Any, str]:
        """Merge structured data from multiple results.

        Args:
            results: List of results

        Returns:
            (merged_result, synthesis_text)
        """
        merged = {}

        for result in results:
            if isinstance(result, dict):
                merged.update(result)

        # Generate synthesis
        synthesis = f"Merged {len(results)} structured results:\n"
        for key, value in merged.items():
            synthesis += f"\n- {key}: {value}"

        primary = merged if merged else results[0]

        return primary, synthesis

    def _format_result(self, result: Any) -> str:
        """Format a result for display.

        Args:
            result: Result to format

        Returns:
            Formatted string
        """
        if isinstance(result, str):
            return result
        elif isinstance(result, dict):
            return result.get("content", result.get("result", str(result)))
        else:
            return str(result)

    def _calculate_confidence(
        self,
        valid_results: List[Any],
        error_results: List[Any]
    ) -> float:
        """Calculate confidence score based on results.

        Args:
            valid_results: List of successful results
            error_results: List of failed results

        Returns:
            Confidence score 0.0-1.0
        """
        total = len(valid_results) + len(error_results)
        if total == 0:
            return 0.0

        success_rate = len(valid_results) / total

        # Boost confidence if multiple services agree
        if len(valid_results) > 1:
            agreement_boost = 0.1 * (len(valid_results) - 1)
            success_rate = min(1.0, success_rate + agreement_boost)

        return round(success_rate, 2)

    def _extract_sources(
        self,
        results: List[Any],
        metadata: Optional[Dict[str, Any]]
    ) -> List[str]:
        """Extract source services from results.

        Args:
            results: List of results
            metadata: Result metadata

        Returns:
            List of source service names
        """
        sources = []

        for result in results:
            if isinstance(result, dict) and "service" in result:
                sources.append(result["service"])

        if metadata and "services" in metadata:
            sources.extend(metadata["services"])

        return list(set(sources)) if sources else ["unknown"]

    def _empty_result(self) -> FusedResult:
        """Create empty result for no results case."""
        return FusedResult(
            primary_result=None,
            supporting_results=[],
            synthesis="No results to fuse.",
            metadata={},
            sources=[],
            confidence=0.0,
            timestamp=datetime.now()
        )

    def _error_result(self, errors: List[Dict[str, Any]]) -> FusedResult:
        """Create error result when all services failed."""
        error_messages = [e.get("error", "Unknown error") for e in errors]

        return FusedResult(
            primary_result={"error": "All services failed"},
            supporting_results=[{"index": i, "error": e} for i, e in enumerate(errors)],
            synthesis=f"All services encountered errors:\n" + "\n".join(f"- {e}" for e in error_messages),
            metadata={"all_errors": errors},
            sources=["error"],
            confidence=0.0,
            timestamp=datetime.now()
        )

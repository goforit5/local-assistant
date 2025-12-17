from abc import ABC, abstractmethod
from typing import Dict, List, Tuple, Optional
import re


class RoutingStrategy(ABC):
    """Abstract base class for routing strategies."""

    @abstractmethod
    def route(self, task_description: str, available_services: List[str]) -> List[Tuple[str, float]]:
        """
        Route a task to appropriate services.

        Args:
            task_description: Description of the task to route
            available_services: List of available service names

        Returns:
            List of (service_name, confidence_score) tuples, sorted by confidence
        """
        pass


class KeywordStrategy(RoutingStrategy):
    """Route based on keyword matching."""

    def __init__(self):
        """Initialize with keyword mappings."""
        self._keyword_map: Dict[str, List[str]] = {
            "chat": ["chat", "conversation", "talk", "ask", "question", "discuss"],
            "vision": ["image", "picture", "photo", "visual", "screenshot", "pdf", "extract", "ocr", "analyze image"],
            "reasoning": ["think", "reason", "analyze", "complex", "problem", "solve", "logic", "plan"],
            "responses": ["search", "web", "browse", "computer", "click", "type", "navigate", "automation"]
        }

    def add_keyword(self, service: str, keyword: str) -> None:
        """Add a keyword mapping for a service."""
        if service not in self._keyword_map:
            self._keyword_map[service] = []
        self._keyword_map[service].append(keyword.lower())

    def route(self, task_description: str, available_services: List[str]) -> List[Tuple[str, float]]:
        """Route based on keyword matching."""
        task_lower = task_description.lower()
        scores: Dict[str, float] = {}

        for service in available_services:
            if service not in self._keyword_map:
                continue

            keywords = self._keyword_map[service]
            matches = sum(1 for keyword in keywords if keyword in task_lower)

            if matches > 0:
                confidence = min(matches / len(keywords), 1.0)
                scores[service] = confidence

        results = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return results


class CapabilityStrategy(RoutingStrategy):
    """Route based on service capabilities."""

    def __init__(self):
        """Initialize with capability mappings."""
        self._capabilities: Dict[str, List[str]] = {
            "chat": ["text_generation", "conversation", "qa"],
            "vision": ["image_analysis", "pdf_extraction", "ocr", "visual_understanding"],
            "reasoning": ["complex_problem_solving", "planning", "logical_reasoning"],
            "responses": ["web_interaction", "browser_automation", "search", "computer_use"]
        }

    def add_capability(self, service: str, capability: str) -> None:
        """Add a capability for a service."""
        if service not in self._capabilities:
            self._capabilities[service] = []
        self._capabilities[service].append(capability)

    def route(self, task_description: str, available_services: List[str]) -> List[Tuple[str, float]]:
        """Route based on capability matching."""
        task_lower = task_description.lower()
        scores: Dict[str, float] = {}

        capability_patterns = {
            "image_analysis": r"\b(image|photo|picture|visual|screenshot)\b",
            "pdf_extraction": r"\b(pdf|extract|document)\b",
            "web_interaction": r"\b(web|browser|search|navigate|click)\b",
            "complex_problem_solving": r"\b(complex|analyze|problem|solve)\b",
            "planning": r"\b(plan|strategy|approach|steps)\b",
        }

        for service in available_services:
            if service not in self._capabilities:
                continue

            service_capabilities = self._capabilities[service]
            matches = 0

            for capability in service_capabilities:
                if capability in capability_patterns:
                    pattern = capability_patterns[capability]
                    if re.search(pattern, task_lower):
                        matches += 1

            if matches > 0:
                confidence = min(matches / len(service_capabilities), 1.0)
                scores[service] = confidence

        results = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return results


class CompositeStrategy(RoutingStrategy):
    """Combine multiple routing strategies."""

    def __init__(self, strategies: Optional[List[RoutingStrategy]] = None):
        """
        Initialize with list of strategies.

        Args:
            strategies: List of routing strategies to combine
        """
        self._strategies = strategies or []

    def add_strategy(self, strategy: RoutingStrategy) -> None:
        """Add a routing strategy."""
        self._strategies.append(strategy)

    def route(self, task_description: str, available_services: List[str]) -> List[Tuple[str, float]]:
        """Combine results from all strategies."""
        combined_scores: Dict[str, List[float]] = {}

        for strategy in self._strategies:
            results = strategy.route(task_description, available_services)
            for service, score in results:
                if service not in combined_scores:
                    combined_scores[service] = []
                combined_scores[service].append(score)

        averaged_scores = {
            service: sum(scores) / len(scores)
            for service, scores in combined_scores.items()
        }

        results = sorted(averaged_scores.items(), key=lambda x: x[1], reverse=True)
        return results

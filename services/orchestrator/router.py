"""ServiceRouter - Intelligent routing based on task classification."""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import yaml
from pathlib import Path


@dataclass
class RouteDecision:
    """Routing decision with confidence and alternatives."""
    primary_service: str
    confidence: float
    alternative_services: List[str]
    reasoning: str
    model_override: Optional[str] = None


class ServiceRouter:
    """Route tasks to appropriate services based on capabilities."""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize router with model registry config.

        Args:
            config_path: Path to models_registry.yaml
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "models_registry.yaml"

        self.config = self._load_config(config_path)
        self.routing_strategy = self.config.get("routing", {})

        # Service capability matrix
        self.service_capabilities = {
            "vision": {
                "keywords": ["image", "pdf", "document", "ocr", "scan", "photo", "screenshot", "extract data"],
                "models": ["gpt-4o", "claude-sonnet-4-5", "gemini-2-5-flash"],
                "use_cases": ["document_ocr", "image_analysis", "pdf_processing"]
            },
            "computer": {
                "keywords": ["search", "browse", "click", "navigate", "web", "google", "automate", "ui"],
                "models": ["computer-use-preview", "claude-sonnet-4-5"],
                "use_cases": ["browser_automation", "web_tasks", "ui_interaction"]
            },
            "reasoning": {
                "keywords": ["plan", "design", "analyze", "verify", "complex", "multi-step", "architecture"],
                "models": ["o1-mini", "gpt-4o"],
                "use_cases": ["complex_reasoning", "multi_step_planning", "verification"]
            },
            "chat": {
                "keywords": ["explain", "tell", "what", "how", "summarize", "write", "generate", "convert"],
                "models": ["claude-sonnet-4-5", "gpt-4o", "gemini-2-5-flash"],
                "use_cases": ["primary_chat", "code_generation", "general_query"]
            }
        }

    def _load_config(self, config_path: Path) -> Dict[str, Any]:
        """Load routing configuration from YAML."""
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"Warning: Could not load config from {config_path}: {e}")
            return {}

    def route_task(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None
    ) -> RouteDecision:
        """Route task to appropriate service with confidence score.

        Args:
            task: Task description
            context: Additional context (files, previous results, etc.)

        Returns:
            RouteDecision with service assignment
        """
        task_lower = task.lower()
        scores = {}

        # Score each service based on keyword matching
        for service, capabilities in self.service_capabilities.items():
            score = 0
            matches = []

            for keyword in capabilities["keywords"]:
                if keyword in task_lower:
                    score += 1
                    matches.append(keyword)

            scores[service] = {
                "score": score,
                "matches": matches
            }

        # Get top services
        sorted_services = sorted(
            scores.items(),
            key=lambda x: x[1]["score"],
            reverse=True
        )

        # Determine primary service
        if sorted_services[0][1]["score"] > 0:
            primary = sorted_services[0][0]
            confidence = min(sorted_services[0][1]["score"] / 3.0, 1.0)
            matches = sorted_services[0][1]["matches"]
        else:
            # Default to chat
            primary = "chat"
            confidence = 0.5
            matches = ["general_query"]

        # Get alternative services
        alternatives = [
            s[0] for s in sorted_services[1:3]
            if s[1]["score"] > 0
        ]

        # Select best model for the service
        model_override = self._select_model(primary, task, context)

        return RouteDecision(
            primary_service=primary,
            confidence=confidence,
            alternative_services=alternatives,
            reasoning=f"Matched keywords: {', '.join(matches)}",
            model_override=model_override
        )

    def _select_model(
        self,
        service: str,
        task: str,
        context: Optional[Dict[str, Any]]
    ) -> Optional[str]:
        """Select best model for service based on routing strategy.

        Args:
            service: Service name
            task: Task description
            context: Additional context

        Returns:
            Model ID or None for default
        """
        strategy = self.routing_strategy.get("default_strategy", "capability_based")

        if strategy == "capability_based":
            # Use model from capability mapping
            mapping = self.routing_strategy.get("strategies", {}).get(
                "capability_based", {}
            )
            return mapping.get(service)

        elif strategy == "cost_optimized":
            # Use cheapest model
            priority = self.routing_strategy.get("strategies", {}).get(
                "cost_optimized", {}
            ).get("priority", [])

            service_models = self.service_capabilities[service]["models"]
            for model in priority:
                model_key = model.replace("-", "_").replace(".", "_")
                if any(model_key in sm for sm in service_models):
                    return model

        elif strategy == "quality_first":
            # Use highest quality model
            priority = self.routing_strategy.get("strategies", {}).get(
                "quality_first", {}
            ).get("priority", [])

            service_models = self.service_capabilities[service]["models"]
            for model in priority:
                model_key = model.replace("-", "_").replace(".", "_")
                if any(model_key in sm for sm in service_models):
                    return model

        return None

    def classify_task_type(self, task: str) -> Dict[str, Any]:
        """Classify task into multiple dimensions.

        Args:
            task: Task description

        Returns:
            Dictionary with classification details
        """
        route = self.route_task(task)

        classification = {
            "primary_service": route.primary_service,
            "confidence": route.confidence,
            "requires_vision": any(
                kw in task.lower()
                for kw in self.service_capabilities["vision"]["keywords"]
            ),
            "requires_computer_use": any(
                kw in task.lower()
                for kw in self.service_capabilities["computer"]["keywords"]
            ),
            "requires_reasoning": any(
                kw in task.lower()
                for kw in self.service_capabilities["reasoning"]["keywords"]
            ),
            "is_compound": any(
                sep in task.lower()
                for sep in ["and then", "after", "then", "also"]
            ),
            "estimated_complexity": self._estimate_complexity(task)
        }

        return classification

    def _estimate_complexity(self, task: str) -> str:
        """Estimate task complexity: simple, medium, complex.

        Args:
            task: Task description

        Returns:
            Complexity level
        """
        complexity_indicators = {
            "complex": ["multi-step", "complex", "plan", "design", "analyze multiple"],
            "medium": ["and", "then", "also", "extract", "process"],
            "simple": ["what", "how", "explain", "tell"]
        }

        task_lower = task.lower()

        for level, indicators in complexity_indicators.items():
            if any(indicator in task_lower for indicator in indicators):
                return level

        return "simple"

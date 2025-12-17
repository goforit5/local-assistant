from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TaskConfig:
    """Configuration for task execution."""
    max_parallel: int = 3
    timeout_seconds: int = 300
    retry_on_failure: bool = True
    max_retries: int = 2


@dataclass
class RoutingConfig:
    """Configuration for task routing."""
    use_keyword_matching: bool = True
    use_capability_matching: bool = True
    fallback_service: Optional[str] = "chat"
    confidence_threshold: float = 0.5


@dataclass
class ExecutionConfig:
    """Combined configuration for orchestrator."""
    task_config: TaskConfig = field(default_factory=TaskConfig)
    routing_config: RoutingConfig = field(default_factory=RoutingConfig)

    @classmethod
    def create(
        cls,
        max_parallel: int = 3,
        timeout_seconds: int = 300,
        retry_on_failure: bool = True,
        max_retries: int = 2,
        use_keyword_matching: bool = True,
        use_capability_matching: bool = True,
        fallback_service: Optional[str] = "chat",
        confidence_threshold: float = 0.5
    ) -> "ExecutionConfig":
        """Factory method for easy configuration creation."""
        return cls(
            task_config=TaskConfig(
                max_parallel=max_parallel,
                timeout_seconds=timeout_seconds,
                retry_on_failure=retry_on_failure,
                max_retries=max_retries
            ),
            routing_config=RoutingConfig(
                use_keyword_matching=use_keyword_matching,
                use_capability_matching=use_capability_matching,
                fallback_service=fallback_service,
                confidence_threshold=confidence_threshold
            )
        )

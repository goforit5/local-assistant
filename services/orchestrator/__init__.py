"""Orchestrator Service - Multi-service coordination with task decomposition."""

from .pipeline import TaskDecomposer, SubTask
from .router import ServiceRouter
from .fusion import ResultFusion
from .config import TaskConfig, RoutingConfig, ExecutionConfig
from .registry import ServiceRegistry
from .strategies import RoutingStrategy, KeywordStrategy, CapabilityStrategy, CompositeStrategy
from .task_router import TaskRouter as NewTaskRouter
from .executor import TaskExecutor, TaskResult

__all__ = [
    "TaskDecomposer", "SubTask", "ServiceRouter", "ResultFusion", "Orchestrator",
    "TaskConfig", "RoutingConfig", "ExecutionConfig",
    "ServiceRegistry", "RoutingStrategy", "KeywordStrategy", "CapabilityStrategy", "CompositeStrategy",
    "NewTaskRouter", "TaskExecutor", "TaskResult",
    "create_orchestrator"
]


class Orchestrator:
    """Main orchestrator for coordinating multiple AI services."""

    def __init__(
        self,
        chat_service=None,
        vision_service=None,
        reasoning_service=None,
        computer_service=None
    ):
        """Initialize orchestrator with available services.

        Args:
            chat_service: Chat service instance
            vision_service: Vision service instance
            reasoning_service: Reasoning service instance
            computer_service: Computer use service instance
        """
        self.services = {
            "chat": chat_service,
            "vision": vision_service,
            "reasoning": reasoning_service,
            "computer": computer_service
        }

        self.decomposer = TaskDecomposer()
        self.router = ServiceRouter()
        self.fusion = ResultFusion()

    async def execute(self, task_description: str, parallel: bool = True):
        """Execute a task through the orchestration pipeline.

        Args:
            task_description: Natural language task description
            parallel: Whether to execute independent subtasks in parallel

        Returns:
            Unified result from all services
        """
        subtasks = await self.decomposer.decompose_task(task_description)

        if parallel:
            results = await self._execute_parallel(subtasks)
        else:
            results = await self._execute_sequential(subtasks)

        return await self.fusion.fuse_results(results)

    async def _execute_parallel(self, subtasks: list[SubTask]) -> list:
        """Execute independent subtasks in parallel."""
        import asyncio

        async def execute_subtask(subtask: SubTask):
            service = self.services.get(subtask.service)
            if not service:
                return {"error": f"Service {subtask.service} not available"}

            try:
                return await service.execute(subtask.task)
            except Exception as e:
                return {"error": str(e)}

        tasks = [execute_subtask(st) for st in subtasks]
        return await asyncio.gather(*tasks, return_exceptions=True)

    async def _execute_sequential(self, subtasks: list[SubTask]) -> list:
        """Execute subtasks sequentially."""
        results = []

        for subtask in subtasks:
            service = self.services.get(subtask.service)
            if not service:
                results.append({"error": f"Service {subtask.service} not available"})
                continue

            try:
                result = await service.execute(subtask.task)
                results.append(result)
            except Exception as e:
                results.append({"error": str(e)})

        return results


def create_orchestrator(
    services: dict,
    config: Optional[ExecutionConfig] = None,
    strategy: Optional[RoutingStrategy] = None
) -> TaskExecutor:
    """
    Factory function to create an orchestrator with DRY OOP patterns.

    Args:
        services: Dictionary mapping service names to service instances
                 e.g., {"chat": chat_service, "vision": vision_service}
        config: ExecutionConfig instance (or use defaults)
        strategy: Custom routing strategy (optional)

    Returns:
        TaskExecutor ready to execute tasks

    Example:
        orchestrator = create_orchestrator(
            services={"chat": chat_svc, "vision": vision_svc},
            config=ExecutionConfig.create(max_parallel=5, timeout_seconds=600)
        )
        result = await orchestrator.execute("Extract text from this PDF")
    """
    if config is None:
        config = ExecutionConfig()

    registry = ServiceRegistry(services)

    router = NewTaskRouter(
        registry=registry,
        strategy=strategy,
        config=config.routing_config
    )

    executor = TaskExecutor(
        router=router,
        config=config.task_config
    )

    return executor

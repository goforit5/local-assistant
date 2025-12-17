import asyncio
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from .task_router import TaskRouter
from .config import TaskConfig


@dataclass
class TaskResult:
    """Result of task execution."""
    service_name: str
    success: bool
    result: Any
    error: Optional[str] = None
    execution_time: float = 0.0


class TaskExecutor:
    """Executes tasks using routed services with parallel execution support."""

    def __init__(
        self,
        router: TaskRouter,
        config: Optional[TaskConfig] = None
    ):
        """
        Initialize task executor.

        Args:
            router: TaskRouter instance for routing tasks
            config: TaskConfig instance for execution settings
        """
        self._router = router
        self._config = config or TaskConfig()

    async def execute(
        self,
        task_description: str,
        **kwargs: Any
    ) -> TaskResult:
        """
        Execute a single task.

        Args:
            task_description: Description of the task
            **kwargs: Additional arguments to pass to the service

        Returns:
            TaskResult with execution details
        """
        import time

        service_name = self._router.route(task_description)

        if not service_name:
            return TaskResult(
                service_name="none",
                success=False,
                result=None,
                error="No suitable service found"
            )

        service = self._router._registry.get(service_name)

        if not service:
            return TaskResult(
                service_name=service_name,
                success=False,
                result=None,
                error=f"Service '{service_name}' not found in registry"
            )

        start_time = time.time()
        retry_count = 0

        while retry_count <= (self._config.max_retries if self._config.retry_on_failure else 0):
            try:
                if asyncio.iscoroutinefunction(service):
                    result = await asyncio.wait_for(
                        service(task_description, **kwargs),
                        timeout=self._config.timeout_seconds
                    )
                elif callable(service):
                    result = await asyncio.wait_for(
                        asyncio.to_thread(service, task_description, **kwargs),
                        timeout=self._config.timeout_seconds
                    )
                else:
                    if hasattr(service, 'execute'):
                        execute_method = getattr(service, 'execute')
                        if asyncio.iscoroutinefunction(execute_method):
                            result = await asyncio.wait_for(
                                execute_method(task_description, **kwargs),
                                timeout=self._config.timeout_seconds
                            )
                        else:
                            result = await asyncio.wait_for(
                                asyncio.to_thread(execute_method, task_description, **kwargs),
                                timeout=self._config.timeout_seconds
                            )
                    else:
                        raise AttributeError(f"Service '{service_name}' is not callable and has no execute method")

                execution_time = time.time() - start_time

                return TaskResult(
                    service_name=service_name,
                    success=True,
                    result=result,
                    execution_time=execution_time
                )

            except asyncio.TimeoutError:
                error_msg = f"Task timed out after {self._config.timeout_seconds} seconds"
                if retry_count < self._config.max_retries and self._config.retry_on_failure:
                    retry_count += 1
                    continue
                else:
                    execution_time = time.time() - start_time
                    return TaskResult(
                        service_name=service_name,
                        success=False,
                        result=None,
                        error=error_msg,
                        execution_time=execution_time
                    )

            except Exception as e:
                error_msg = f"Error executing task: {str(e)}"
                if retry_count < self._config.max_retries and self._config.retry_on_failure:
                    retry_count += 1
                    continue
                else:
                    execution_time = time.time() - start_time
                    return TaskResult(
                        service_name=service_name,
                        success=False,
                        result=None,
                        error=error_msg,
                        execution_time=execution_time
                    )

        execution_time = time.time() - start_time
        return TaskResult(
            service_name=service_name,
            success=False,
            result=None,
            error=f"Task failed after {retry_count} retries",
            execution_time=execution_time
        )

    async def execute_parallel(
        self,
        tasks: List[str],
        **kwargs: Any
    ) -> List[TaskResult]:
        """
        Execute multiple tasks in parallel.

        Args:
            tasks: List of task descriptions
            **kwargs: Additional arguments to pass to services

        Returns:
            List of TaskResults
        """
        semaphore = asyncio.Semaphore(self._config.max_parallel)

        async def execute_with_semaphore(task: str) -> TaskResult:
            async with semaphore:
                return await self.execute(task, **kwargs)

        results = await asyncio.gather(
            *[execute_with_semaphore(task) for task in tasks],
            return_exceptions=True
        )

        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(
                    TaskResult(
                        service_name="unknown",
                        success=False,
                        result=None,
                        error=str(result)
                    )
                )
            else:
                processed_results.append(result)

        return processed_results

    async def execute_subtasks(
        self,
        subtasks: List[Dict[str, Any]],
        parallel: bool = True
    ) -> List[TaskResult]:
        """
        Execute multiple subtasks with individual configurations.

        Args:
            subtasks: List of dicts with 'task' and optional 'kwargs'
            parallel: Whether to execute in parallel or sequentially

        Returns:
            List of TaskResults
        """
        if parallel:
            semaphore = asyncio.Semaphore(self._config.max_parallel)

            async def execute_subtask_with_semaphore(subtask: Dict[str, Any]) -> TaskResult:
                async with semaphore:
                    task_desc = subtask.get('task', '')
                    task_kwargs = subtask.get('kwargs', {})
                    return await self.execute(task_desc, **task_kwargs)

            results = await asyncio.gather(
                *[execute_subtask_with_semaphore(st) for st in subtasks],
                return_exceptions=True
            )
        else:
            results = []
            for subtask in subtasks:
                task_desc = subtask.get('task', '')
                task_kwargs = subtask.get('kwargs', {})
                try:
                    result = await self.execute(task_desc, **task_kwargs)
                    results.append(result)
                except Exception as e:
                    results.append(
                        TaskResult(
                            service_name="unknown",
                            success=False,
                            result=None,
                            error=str(e)
                        )
                    )

        processed_results = []
        for result in results:
            if isinstance(result, Exception):
                processed_results.append(
                    TaskResult(
                        service_name="unknown",
                        success=False,
                        result=None,
                        error=str(result)
                    )
                )
            else:
                processed_results.append(result)

        return processed_results

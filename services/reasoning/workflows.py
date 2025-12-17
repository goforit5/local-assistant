"""WorkflowExecutor - Multi-step execution with checkpoints."""

from typing import Any, Callable, Dict, List, Literal, Optional
from dataclasses import dataclass, field
from datetime import datetime
import asyncio

from providers.openai_provider import OpenAIProvider
from .planner import ReasoningPlanner, PlanStep


@dataclass
class StepResult:
    """Result of executing a workflow step."""
    step_number: int
    status: Literal["pending", "running", "completed", "failed", "skipped"]
    output: Optional[Any] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    execution_time: Optional[float] = None


@dataclass
class CheckpointData:
    """Checkpoint data for workflow recovery."""
    workflow_id: str
    step_number: int
    timestamp: datetime
    completed_steps: List[int]
    step_results: Dict[int, StepResult]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowResult:
    """Complete workflow execution result."""
    workflow_id: str
    status: Literal["completed", "failed", "partial"]
    steps: List[StepResult]
    total_steps: int
    completed_steps: int
    failed_steps: int
    total_time: float
    checkpoints: List[CheckpointData]
    metadata: Dict[str, Any]


class WorkflowExecutor:
    """Multi-step workflow execution with checkpoints and recovery."""

    def __init__(self, provider: OpenAIProvider, planner: Optional[ReasoningPlanner] = None):
        self.provider = provider
        self.planner = planner or ReasoningPlanner(provider)
        self._checkpoints: Dict[str, List[CheckpointData]] = {}

    async def execute_workflow(
        self,
        steps: List[PlanStep],
        step_executor: Callable[[PlanStep, Dict[int, Any]], Any],
        workflow_id: Optional[str] = None,
        checkpoint_interval: int = 5,
        continue_on_failure: bool = False
    ) -> WorkflowResult:
        """Execute multi-step workflow with checkpoints.

        Args:
            steps: Plan steps to execute
            step_executor: Async function to execute each step
            workflow_id: Unique workflow identifier
            checkpoint_interval: Save checkpoint every N steps
            continue_on_failure: Continue execution if step fails

        Returns:
            WorkflowResult with execution details
        """
        workflow_id = workflow_id or f"workflow_{datetime.now().timestamp()}"
        start_time = datetime.now()

        step_results: Dict[int, StepResult] = {}
        step_outputs: Dict[int, Any] = {}
        completed_steps: List[int] = []
        checkpoints: List[CheckpointData] = []

        # Initialize all steps as pending
        for step in steps:
            step_results[step.step_number] = StepResult(
                step_number=step.step_number,
                status="pending"
            )

        # Execute steps
        for step in steps:
            # Check dependencies
            if not self._dependencies_met(step, completed_steps):
                step_results[step.step_number].status = "skipped"
                step_results[step.step_number].error = "Dependencies not met"
                if not continue_on_failure:
                    break
                continue

            # Execute step
            result = await self._execute_step(step, step_executor, step_outputs)
            step_results[step.step_number] = result

            if result.status == "completed":
                completed_steps.append(step.step_number)
                step_outputs[step.step_number] = result.output

                # Create checkpoint
                if len(completed_steps) % checkpoint_interval == 0:
                    checkpoint = self._create_checkpoint(
                        workflow_id,
                        step.step_number,
                        completed_steps,
                        step_results
                    )
                    checkpoints.append(checkpoint)

            elif result.status == "failed":
                if not continue_on_failure:
                    break

        # Final checkpoint
        final_checkpoint = self._create_checkpoint(
            workflow_id,
            len(steps),
            completed_steps,
            step_results
        )
        checkpoints.append(final_checkpoint)

        # Calculate statistics
        end_time = datetime.now()
        total_time = (end_time - start_time).total_seconds()

        failed_steps = sum(
            1 for r in step_results.values() if r.status == "failed"
        )

        status = "completed"
        if failed_steps > 0:
            status = "failed" if len(completed_steps) == 0 else "partial"

        return WorkflowResult(
            workflow_id=workflow_id,
            status=status,
            steps=list(step_results.values()),
            total_steps=len(steps),
            completed_steps=len(completed_steps),
            failed_steps=failed_steps,
            total_time=total_time,
            checkpoints=checkpoints,
            metadata={
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "checkpoint_interval": checkpoint_interval,
                "continue_on_failure": continue_on_failure
            }
        )

    async def resume_workflow(
        self,
        workflow_id: str,
        step_executor: Callable[[PlanStep, Dict[int, Any]], Any],
        steps: List[PlanStep]
    ) -> WorkflowResult:
        """Resume workflow from last checkpoint.

        Args:
            workflow_id: Workflow to resume
            step_executor: Step execution function
            steps: Original workflow steps

        Returns:
            WorkflowResult
        """
        # Get last checkpoint
        if workflow_id not in self._checkpoints:
            raise ValueError(f"No checkpoints found for workflow {workflow_id}")

        checkpoint = self._checkpoints[workflow_id][-1]

        # Filter to uncompleted steps
        remaining_steps = [
            s for s in steps
            if s.step_number not in checkpoint.completed_steps
        ]

        # Execute remaining steps
        return await self.execute_workflow(
            steps=remaining_steps,
            step_executor=step_executor,
            workflow_id=workflow_id
        )

    async def _execute_step(
        self,
        step: PlanStep,
        executor: Callable[[PlanStep, Dict[int, Any]], Any],
        step_outputs: Dict[int, Any]
    ) -> StepResult:
        """Execute single step."""
        result = StepResult(
            step_number=step.step_number,
            status="running",
            started_at=datetime.now()
        )

        try:
            output = await executor(step, step_outputs)
            result.status = "completed"
            result.output = output

        except Exception as e:
            result.status = "failed"
            result.error = str(e)

        finally:
            result.completed_at = datetime.now()
            if result.started_at and result.completed_at:
                result.execution_time = (
                    result.completed_at - result.started_at
                ).total_seconds()

        return result

    def _dependencies_met(
        self,
        step: PlanStep,
        completed_steps: List[int]
    ) -> bool:
        """Check if step dependencies are met."""
        if not step.dependencies:
            return True
        return all(dep in completed_steps for dep in step.dependencies)

    def _create_checkpoint(
        self,
        workflow_id: str,
        step_number: int,
        completed_steps: List[int],
        step_results: Dict[int, StepResult]
    ) -> CheckpointData:
        """Create workflow checkpoint."""
        checkpoint = CheckpointData(
            workflow_id=workflow_id,
            step_number=step_number,
            timestamp=datetime.now(),
            completed_steps=completed_steps.copy(),
            step_results=step_results.copy()
        )

        # Store checkpoint
        if workflow_id not in self._checkpoints:
            self._checkpoints[workflow_id] = []
        self._checkpoints[workflow_id].append(checkpoint)

        return checkpoint

    def get_checkpoints(self, workflow_id: str) -> List[CheckpointData]:
        """Get all checkpoints for a workflow."""
        return self._checkpoints.get(workflow_id, [])

    def clear_checkpoints(self, workflow_id: str) -> None:
        """Clear checkpoints for a workflow."""
        if workflow_id in self._checkpoints:
            del self._checkpoints[workflow_id]

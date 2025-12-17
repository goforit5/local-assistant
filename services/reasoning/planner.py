"""ReasoningPlanner - o1-mini wrapper for multi-step planning."""

from typing import Dict, List, Literal, Optional
from dataclasses import dataclass

from providers.openai_provider import OpenAIProvider
from providers.base import Message, CompletionResponse


@dataclass
class PlanStep:
    """Individual step in a plan."""
    step_number: int
    description: str
    dependencies: List[int]
    expected_output: str
    estimated_complexity: Literal["low", "medium", "high"]


@dataclass
class TaskPlan:
    """Complete task plan."""
    task_description: str
    steps: List[PlanStep]
    total_steps: int
    reasoning_tokens: int
    metadata: Dict[str, any]


class ReasoningPlanner:
    """Multi-step planning using o1-mini reasoning."""

    def __init__(self, provider: OpenAIProvider, model: str = "o1-mini-2024-09-12"):
        self.provider = provider
        self.model = model

    async def plan_task(
        self,
        description: str,
        reasoning_effort: Literal["low", "medium", "high"] = "high",
        max_tokens: int = 10000
    ) -> TaskPlan:
        """Generate step-by-step plan for a task.

        Args:
            description: Task description to plan
            reasoning_effort: Reasoning depth (low/medium/high)
            max_tokens: Maximum output tokens

        Returns:
            TaskPlan with detailed steps
        """
        prompt = f"""Analyze this task and create a detailed step-by-step execution plan:

TASK: {description}

Provide a structured plan with:
1. Numbered steps in logical execution order
2. Dependencies between steps (which steps must complete before others)
3. Expected output for each step
4. Complexity estimate (low/medium/high) for each step

Format your response as:
STEP N: [description]
DEPENDENCIES: [step numbers or "none"]
EXPECTED OUTPUT: [what this step produces]
COMPLEXITY: [low/medium/high]

Be thorough and consider edge cases, error handling, and validation needs."""

        messages = [Message(role="user", content=prompt)]

        response = await self.provider.chat(
            messages=messages,
            model=self.model,
            max_tokens=max_tokens,
            temperature=1.0,
            reasoning_effort=reasoning_effort
        )

        # Parse response into structured plan
        steps = self._parse_plan_response(response.content)

        return TaskPlan(
            task_description=description,
            steps=steps,
            total_steps=len(steps),
            reasoning_tokens=response.usage.get("output_tokens", 0),
            metadata={
                "reasoning_effort": reasoning_effort,
                "model": self.model,
                "cost": response.cost,
                "latency": response.latency
            }
        )

    async def reason_about(
        self,
        problem: str,
        reasoning_effort: Literal["low", "medium", "high"] = "high",
        max_tokens: int = 10000,
        context: Optional[str] = None
    ) -> CompletionResponse:
        """General reasoning about a problem.

        Args:
            problem: Problem to reason about
            reasoning_effort: Reasoning depth
            max_tokens: Maximum output tokens
            context: Optional additional context

        Returns:
            CompletionResponse with reasoning
        """
        content = problem
        if context:
            content = f"CONTEXT:\n{context}\n\nPROBLEM:\n{problem}"

        messages = [Message(role="user", content=content)]

        return await self.provider.chat(
            messages=messages,
            model=self.model,
            max_tokens=max_tokens,
            temperature=1.0,
            reasoning_effort=reasoning_effort
        )

    def _parse_plan_response(self, response: str) -> List[PlanStep]:
        """Parse o1-mini response into structured steps."""
        steps = []
        current_step = None

        for line in response.split("\n"):
            line = line.strip()
            if not line:
                continue

            if line.startswith("STEP "):
                # Save previous step
                if current_step:
                    steps.append(current_step)

                # Parse step number and description
                parts = line.split(":", 1)
                step_num = int(parts[0].replace("STEP", "").strip())
                description = parts[1].strip() if len(parts) > 1 else ""

                current_step = {
                    "step_number": step_num,
                    "description": description,
                    "dependencies": [],
                    "expected_output": "",
                    "complexity": "medium"
                }

            elif current_step:
                if line.startswith("DEPENDENCIES:"):
                    deps_text = line.replace("DEPENDENCIES:", "").strip()
                    if deps_text.lower() != "none":
                        # Parse dependency numbers
                        current_step["dependencies"] = [
                            int(d.strip()) for d in deps_text.split(",")
                            if d.strip().isdigit()
                        ]

                elif line.startswith("EXPECTED OUTPUT:"):
                    current_step["expected_output"] = line.replace("EXPECTED OUTPUT:", "").strip()

                elif line.startswith("COMPLEXITY:"):
                    complexity = line.replace("COMPLEXITY:", "").strip().lower()
                    if complexity in ["low", "medium", "high"]:
                        current_step["complexity"] = complexity

        # Add final step
        if current_step:
            steps.append(current_step)

        # Convert to PlanStep objects
        return [
            PlanStep(
                step_number=s["step_number"],
                description=s["description"],
                dependencies=s["dependencies"],
                expected_output=s["expected_output"],
                estimated_complexity=s["complexity"]
            )
            for s in steps
        ]

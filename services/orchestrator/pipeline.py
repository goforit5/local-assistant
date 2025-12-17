"""TaskDecomposer - Break complex tasks into service-specific subtasks."""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import re


@dataclass
class SubTask:
    """Subtask with service assignment."""
    task_id: str
    task: str
    service: str  # chat, vision, reasoning, computer
    priority: int = 0
    dependencies: List[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []
        if self.metadata is None:
            self.metadata = {}


class TaskDecomposer:
    """Decompose complex tasks into subtasks with service assignments."""

    def __init__(self):
        """Initialize task decomposer with service patterns."""
        self.service_patterns = {
            "vision": [
                r"extract.*(?:from|in).*(?:pdf|image|document|screenshot|photo)",
                r"analyze.*(?:image|photo|screenshot|document|pdf)",
                r"read.*(?:pdf|document|image)",
                r"ocr",
                r"scan.*document",
                r"what.*(?:see|shown|visible).*(?:image|photo|picture)",
            ],
            "computer": [
                r"(?:search|browse|visit|open).*(?:google|web|website|url)",
                r"click.*(?:button|link)",
                r"navigate to",
                r"fill.*form",
                r"download.*from",
                r"interact with.*(?:ui|interface|browser)",
                r"automate.*(?:browser|task)",
            ],
            "reasoning": [
                r"plan.*(?:implementation|approach|strategy)",
                r"design.*(?:architecture|system)",
                r"(?:analyze|evaluate).*(?:options|alternatives)",
                r"verify.*(?:logic|correctness)",
                r"multi-?step.*(?:problem|solution)",
                r"complex.*(?:reasoning|analysis)",
                r"break down",
            ],
            "chat": [
                r"explain",
                r"tell me about",
                r"what is",
                r"how to",
                r"summarize",
                r"convert.*(?:to|into)",
                r"write.*(?:text|message|email)",
                r"generate.*(?:text|content)",
            ]
        }

        self.compound_keywords = {
            "and then": "sequential",
            "after": "sequential",
            "first": "sequential",
            "then": "sequential",
            "finally": "sequential",
            "also": "parallel",
            "additionally": "parallel",
            "both": "parallel",
        }

    async def decompose_task(self, description: str) -> List[SubTask]:
        """Break down task into subtasks with service assignments.

        Args:
            description: Natural language task description

        Returns:
            List of SubTask objects with service assignments
        """
        description_lower = description.lower()

        # Check if it's a compound task
        is_compound = any(keyword in description_lower for keyword in self.compound_keywords.keys())

        if is_compound:
            return self._decompose_compound_task(description)
        else:
            return self._decompose_simple_task(description)

    def _decompose_simple_task(self, description: str) -> List[SubTask]:
        """Decompose a simple single-service task."""
        service = self._classify_service(description)

        subtask = SubTask(
            task_id="task_1",
            task=description,
            service=service,
            priority=1
        )

        return [subtask]

    def _decompose_compound_task(self, description: str) -> List[SubTask]:
        """Decompose compound task into multiple subtasks."""
        # Split by common delimiters
        delimiters = r"(?:and then|after that|then|also|additionally|furthermore|\.|;)"
        parts = re.split(delimiters, description, flags=re.IGNORECASE)

        subtasks = []
        prev_task_id = None

        for idx, part in enumerate(parts):
            part = part.strip()
            if not part or len(part) < 5:
                continue

            task_id = f"task_{idx + 1}"
            service = self._classify_service(part)

            # Determine dependencies based on context
            dependencies = []
            if prev_task_id and self._has_dependency(parts[idx-1] if idx > 0 else "", part):
                dependencies.append(prev_task_id)

            subtask = SubTask(
                task_id=task_id,
                task=part,
                service=service,
                priority=idx + 1,
                dependencies=dependencies
            )

            subtasks.append(subtask)
            prev_task_id = task_id

        return subtasks if subtasks else self._decompose_simple_task(description)

    def _classify_service(self, task: str) -> str:
        """Classify which service should handle the task.

        Args:
            task: Task description

        Returns:
            Service name: chat, vision, reasoning, or computer
        """
        task_lower = task.lower()

        # Check patterns in priority order
        for service, patterns in self.service_patterns.items():
            for pattern in patterns:
                if re.search(pattern, task_lower):
                    return service

        # Default to chat for general queries
        return "chat"

    def _has_dependency(self, prev_task: str, current_task: str) -> bool:
        """Check if current task depends on previous task.

        Args:
            prev_task: Previous task description
            current_task: Current task description

        Returns:
            True if there's a dependency
        """
        # Check for explicit dependency keywords
        dependency_keywords = [
            "after", "then", "using", "with the", "from the",
            "based on", "according to", "following"
        ]

        current_lower = current_task.lower()
        return any(keyword in current_lower for keyword in dependency_keywords)

    def route_task(self, task: str) -> str:
        """Quick route a single task to appropriate service.

        Args:
            task: Task description

        Returns:
            Service name
        """
        return self._classify_service(task)

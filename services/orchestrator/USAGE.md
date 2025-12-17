# Orchestrator Service - DRY OOP Pattern Usage

## Quick Start

```python
from services.orchestrator import create_orchestrator, ExecutionConfig, TaskConfig

# Example service implementations
class ChatService:
    async def execute(self, task, **kwargs):
        return f"Chat response: {task}"

class VisionService:
    async def execute(self, task, **kwargs):
        return f"Vision analysis: {task}"

# Create orchestrator with simple dictionary
orchestrator = create_orchestrator(
    services={
        "chat": ChatService(),
        "vision": VisionService(),
    },
    config=ExecutionConfig.create(max_parallel=5, timeout_seconds=300)
)

# Execute a task (automatically routed to appropriate service)
result = await orchestrator.execute("Extract text from this PDF")
print(result.service_name)  # "vision"
print(result.success)       # True
print(result.result)        # Vision analysis result
```

## Architecture Patterns

### 1. Service Registry Pattern
Manages all available services in a centralized registry:

```python
from services.orchestrator import ServiceRegistry

registry = ServiceRegistry({
    "chat": chat_service,
    "vision": vision_service,
    "reasoning": reasoning_service
})

# Query registry
print(registry.list_services())  # ["chat", "vision", "reasoning"]
print(registry.has("chat"))      # True
service = registry.get("chat")
```

### 2. Config Dataclasses
Type-safe configuration with dataclasses:

```python
from services.orchestrator import TaskConfig, RoutingConfig, ExecutionConfig

# Individual configs
task_config = TaskConfig(
    max_parallel=3,
    timeout_seconds=300,
    retry_on_failure=True,
    max_retries=2
)

routing_config = RoutingConfig(
    use_keyword_matching=True,
    use_capability_matching=True,
    fallback_service="chat",
    confidence_threshold=0.5
)

# Combined config
config = ExecutionConfig(
    task_config=task_config,
    routing_config=routing_config
)

# Or use factory method
config = ExecutionConfig.create(
    max_parallel=5,
    timeout_seconds=600,
    confidence_threshold=0.7
)
```

### 3. Strategy Pattern
Pluggable routing strategies:

```python
from services.orchestrator import (
    KeywordStrategy,
    CapabilityStrategy,
    CompositeStrategy,
    create_orchestrator
)

# Use keyword-only strategy
keyword_strategy = KeywordStrategy()
keyword_strategy.add_keyword("vision", "invoice")

# Use capability-only strategy
capability_strategy = CapabilityStrategy()

# Use composite strategy (combines multiple)
composite = CompositeStrategy([keyword_strategy, capability_strategy])

# Create orchestrator with custom strategy
orchestrator = create_orchestrator(
    services={"chat": chat_svc, "vision": vision_svc},
    strategy=composite
)
```

### 4. Builder Pattern
Easy construction via factory function:

```python
from services.orchestrator import create_orchestrator, ExecutionConfig

# Minimal setup (uses defaults)
orchestrator = create_orchestrator(
    services={"chat": chat_svc}
)

# Custom configuration
orchestrator = create_orchestrator(
    services={"chat": chat_svc, "vision": vision_svc},
    config=ExecutionConfig.create(max_parallel=10)
)

# Full customization
from services.orchestrator import KeywordStrategy

orchestrator = create_orchestrator(
    services=services_dict,
    config=ExecutionConfig.create(max_parallel=5, timeout_seconds=600),
    strategy=KeywordStrategy()
)
```

### 5. Async Parallel Execution
Execute multiple tasks concurrently:

```python
# Single task
result = await orchestrator.execute("Analyze this image")

# Multiple parallel tasks (respects max_parallel limit)
tasks = [
    "Extract PDF data",
    "Search the web for info",
    "Generate a summary"
]
results = await orchestrator.execute_parallel(tasks)

# Process results
for result in results:
    if result.success:
        print(f"{result.service_name}: {result.result}")
    else:
        print(f"Error: {result.error}")

# Execute subtasks with individual configs
subtasks = [
    {"task": "Extract PDF", "kwargs": {"pages": [1, 2, 3]}},
    {"task": "Search web", "kwargs": {"max_results": 5}},
]
results = await orchestrator.execute_subtasks(subtasks, parallel=True)
```

## Service Integration Example

```python
from services.orchestrator import create_orchestrator, ExecutionConfig

# Define your service interfaces
class ChatService:
    async def execute(self, task, **kwargs):
        # Call LLM API
        return {"response": "chat result"}

class VisionService:
    async def execute(self, task, **kwargs):
        # Call vision API
        return {"extracted_text": "PDF content"}

class ReasoningService:
    async def execute(self, task, **kwargs):
        # Call reasoning API
        return {"solution": "complex answer"}

class ComputerService:
    async def execute(self, task, **kwargs):
        # Browser automation
        return {"search_results": [...]}

# Create orchestrator
orchestrator = create_orchestrator(
    services={
        "chat": ChatService(),
        "vision": VisionService(),
        "reasoning": ReasoningService(),
        "responses": ComputerService()  # Note: "responses" for computer use
    },
    config=ExecutionConfig.create(
        max_parallel=3,
        timeout_seconds=300,
        retry_on_failure=True,
        confidence_threshold=0.6
    )
)

# Execute tasks (auto-routed based on keywords)
result1 = await orchestrator.execute("Extract text from invoice.pdf")
# Routes to: vision

result2 = await orchestrator.execute("Search Google for latest news")
# Routes to: responses (computer use)

result3 = await orchestrator.execute("Design a multi-step solution for this problem")
# Routes to: reasoning

result4 = await orchestrator.execute("Explain how async works")
# Routes to: chat
```

## Keyword Routing Reference

### Vision Service
Keywords: `image`, `picture`, `photo`, `visual`, `screenshot`, `pdf`, `extract`, `ocr`, `analyze image`

### Computer/Responses Service
Keywords: `search`, `web`, `browse`, `computer`, `click`, `type`, `navigate`, `automation`

### Reasoning Service
Keywords: `think`, `reason`, `analyze`, `complex`, `problem`, `solve`, `logic`, `plan`

### Chat Service
Keywords: `chat`, `conversation`, `talk`, `ask`, `question`, `discuss`

Fallback: If no keywords match, routes to `chat` by default (configurable).

## Type Safety

All components use full type hints:

```python
from typing import Dict, Any
from services.orchestrator import TaskResult

async def process_task(orchestrator, task: str) -> TaskResult:
    result: TaskResult = await orchestrator.execute(task)

    # Type-safe access
    service_name: str = result.service_name
    success: bool = result.success
    output: Any = result.result
    error: Optional[str] = result.error
    execution_time: float = result.execution_time

    return result
```

## Error Handling

```python
result = await orchestrator.execute("Some task")

if not result.success:
    print(f"Task failed on {result.service_name}: {result.error}")
    if result.execution_time > 100:
        print("Task took too long")
else:
    print(f"Success in {result.execution_time:.2f}s: {result.result}")
```

## Advanced: Custom Routing Strategy

```python
from services.orchestrator import RoutingStrategy
from typing import List, Tuple

class MyCustomStrategy(RoutingStrategy):
    def route(self, task_description: str, available_services: List[str]) -> List[Tuple[str, float]]:
        # Custom logic
        if "urgent" in task_description.lower():
            return [("chat", 1.0)]

        # Return list of (service_name, confidence_score)
        return [("vision", 0.8), ("chat", 0.6)]

orchestrator = create_orchestrator(
    services=services_dict,
    strategy=MyCustomStrategy()
)
```

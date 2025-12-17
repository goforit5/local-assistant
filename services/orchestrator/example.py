"""Example usage of the Orchestrator service."""

import asyncio
from services.orchestrator import Orchestrator, TaskDecomposer, ServiceRouter, ResultFusion


async def example_task_decomposition():
    """Demonstrate task decomposition."""
    print("=" * 70)
    print("TASK DECOMPOSITION EXAMPLES")
    print("=" * 70)

    decomposer = TaskDecomposer()

    test_tasks = [
        "Extract data from invoice.pdf",
        "Search Google for Python tutorials",
        "Plan implementation of authentication system",
        "Explain how async works in Python",
        "Extract data from PDF and then search Google for the company name",
        "Analyze this image and also plan the next steps",
    ]

    for task in test_tasks:
        print(f"\nTask: {task}")
        subtasks = await decomposer.decompose_task(task)
        print(f"Decomposed into {len(subtasks)} subtask(s):")
        for st in subtasks:
            deps = f" (depends on: {', '.join(st.dependencies)})" if st.dependencies else ""
            print(f"  [{st.task_id}] {st.service}: {st.task}{deps}")


async def example_service_routing():
    """Demonstrate intelligent routing."""
    print("\n" + "=" * 70)
    print("SERVICE ROUTING EXAMPLES")
    print("=" * 70)

    router = ServiceRouter()

    test_tasks = [
        "Extract invoice data from PDF document",
        "Search Google and click the first result",
        "Plan a multi-step implementation approach",
        "What is the capital of France?",
        "Analyze this screenshot and tell me what you see",
    ]

    for task in test_tasks:
        print(f"\nTask: {task}")
        decision = router.route_task(task)
        print(f"  Primary Service: {decision.primary_service} (confidence: {decision.confidence:.2f})")
        print(f"  Reasoning: {decision.reasoning}")
        if decision.alternative_services:
            print(f"  Alternatives: {', '.join(decision.alternative_services)}")
        if decision.model_override:
            print(f"  Model Override: {decision.model_override}")

        # Also show classification
        classification = router.classify_task_type(task)
        print(f"  Complexity: {classification['estimated_complexity']}")
        print(f"  Requires Vision: {classification['requires_vision']}")
        print(f"  Requires Computer: {classification['requires_computer_use']}")
        print(f"  Requires Reasoning: {classification['requires_reasoning']}")


async def example_result_fusion():
    """Demonstrate result fusion."""
    print("\n" + "=" * 70)
    print("RESULT FUSION EXAMPLES")
    print("=" * 70)

    fusion = ResultFusion()

    # Example 1: Multiple text results
    print("\nExample 1: Synthesize multiple text results")
    results1 = [
        {"service": "vision", "content": "Extracted invoice total: $1,250.00"},
        {"service": "chat", "content": "This appears to be a standard invoice format"},
        {"service": "reasoning", "content": "All required fields are present"}
    ]

    fused1 = await fusion.fuse_results(results1, strategy="synthesize")
    print(f"Confidence: {fused1.confidence}")
    print(f"Sources: {', '.join(fused1.sources)}")
    print(f"Synthesis:\n{fused1.synthesis}")

    # Example 2: Prioritize results
    print("\n\nExample 2: Prioritize first result")
    results2 = [
        "Main answer: Python is a high-level programming language",
        "Additional info: Created by Guido van Rossum in 1991",
        "Fun fact: Named after Monty Python"
    ]

    fused2 = await fusion.fuse_results(results2, strategy="prioritize")
    print(f"Confidence: {fused2.confidence}")
    print(f"Synthesis:\n{fused2.synthesis}")

    # Example 3: Handle errors
    print("\n\nExample 3: Handle mixed results with errors")
    results3 = [
        {"service": "vision", "content": "Successfully extracted data"},
        {"service": "computer", "error": "Browser timeout"},
        {"service": "reasoning", "content": "Analysis complete"}
    ]

    fused3 = await fusion.fuse_results(results3, strategy="synthesize")
    print(f"Confidence: {fused3.confidence}")
    print(f"Valid results: {len([r for r in results3 if 'error' not in r])}")
    print(f"Synthesis:\n{fused3.synthesis[:200]}...")


async def main():
    """Run all examples."""
    await example_task_decomposition()
    await example_service_routing()
    await example_result_fusion()

    print("\n" + "=" * 70)
    print("ORCHESTRATOR EXAMPLES COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())

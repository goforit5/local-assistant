"""Main CLI entry point."""

import os
import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = typer.Typer(
    name="assistant",
    help="🦄 Local AI Assistant - Unicorn-grade AI with vision, reasoning, and computer use",
    no_args_is_help=True,
)

console = Console()


def check_env_vars() -> bool:
    """Check if required environment variables are set."""
    required_vars = ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY"]
    missing = [var for var in required_vars if not os.getenv(var)]

    if missing:
        console.print("[bold red]Error:[/bold red] Missing required environment variables:")
        for var in missing:
            console.print(f"  - {var}")
        console.print("\n[dim]Copy .env.example to .env and add your API keys[/dim]")
        return False
    return True


@app.command()
def chat(
    message: str = typer.Argument(..., help="Message to send to the assistant"),
    model: str = typer.Option("auto", "--model", "-m", help="Model to use (auto, sonnet, gpt-4o, gemini)"),
    stream: bool = typer.Option(False, "--stream", "-s", help="Stream the response"),
    max_cost: float = typer.Option(1.0, "--max-cost", help="Maximum cost per request"),
):
    """💬 Chat with the AI assistant."""
    if not check_env_vars():
        raise typer.Exit(1)

    asyncio.run(_chat_async(message, model, stream, max_cost))


async def _chat_async(message: str, model: str, stream: bool, max_cost: float):
    """Async chat implementation."""
    from providers.anthropic_provider import AnthropicProvider
    from providers.google_provider import GoogleProvider
    from providers.base import ProviderConfig, Message
    from services.chat import ChatRouter, ChatSession
    from observability.costs import get_cost_tracker, CostWindow

    console.print(Panel(f"[bold]Message:[/bold] {message}", title="💬 Chat", border_style="green"))

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Initializing providers...", total=None)

            # Initialize providers
            anthropic_config = ProviderConfig(api_key=os.getenv("ANTHROPIC_API_KEY"))
            google_config = ProviderConfig(api_key=os.getenv("GOOGLE_API_KEY"))

            primary = AnthropicProvider(anthropic_config)
            fallback = GoogleProvider(google_config)

            await primary.initialize()
            await fallback.initialize()

            progress.update(task, description="Creating chat session...")

            # Create router and session
            router = ChatRouter(primary=primary, fallback=fallback)
            session = ChatSession(conversation_id="cli-session", router=router)

            progress.update(task, description="Sending message...")

            # Send message
            response = await session.send_message(message, model=model)

            progress.update(task, description="Complete!", completed=True)

        # Display response
        console.print("\n[bold cyan]Assistant:[/bold cyan]")
        console.print(Panel(response.content, border_style="cyan"))

        # Display cost info
        cost_tracker = get_cost_tracker()
        await cost_tracker.add_cost(response.cost, response.provider, response.model)

        console.print(f"\n[dim]Model: {response.model} | "
                     f"Provider: {response.provider} | "
                     f"Tokens: {response.usage.get('total_tokens', 0)} | "
                     f"Cost: ${response.cost:.4f} | "
                     f"Latency: {response.latency:.2f}s[/dim]")

        # Check cost limits
        total_today = await cost_tracker.get_total(CostWindow.DAILY)
        console.print(f"[dim]Today's total: ${total_today:.4f}[/dim]")

        # Cleanup
        await router.close()

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)


@app.command()
def vision(
    operation: str = typer.Argument(..., help="Operation: extract, ocr"),
    file_path: str = typer.Argument(..., help="Path to document or image"),
    doc_type: str = typer.Option("text", "--type", "-t", help="Document type: text, invoice, receipt, table, form"),
    output_format: str = typer.Option("json", "--output", "-o", help="Output format: json, markdown"),
):
    """🔭 Vision service - Process documents and images."""
    if not check_env_vars():
        raise typer.Exit(1)

    asyncio.run(_vision_async(operation, file_path, doc_type, output_format))


async def _vision_async(operation: str, file_path: str, doc_type: str, output_format: str):
    """Async vision implementation."""
    from providers.openai_provider import OpenAIProvider
    from providers.base import ProviderConfig
    from services.vision import create_vision_service
    from observability.costs import get_cost_tracker
    import json

    console.print(Panel(
        f"[bold]Operation:[/bold] {operation}\n"
        f"[bold]File:[/bold] {file_path}\n"
        f"[bold]Type:[/bold] {doc_type}",
        title="🔭 Vision",
        border_style="blue"
    ))

    if not Path(file_path).exists():
        console.print(f"[bold red]Error:[/bold red] File not found: {file_path}")
        raise typer.Exit(1)

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Initializing vision service...", total=None)

            # Initialize provider
            openai_config = ProviderConfig(api_key=os.getenv("OPENAI_API_KEY"))
            provider = OpenAIProvider(openai_config)
            await provider.initialize()

            progress.update(task, description="Creating vision service...")

            # Create vision service
            vision_service = await create_vision_service(
                provider=provider,
                vision_config={"model": "gpt-4o-2024-11-20"},
                enable_ocr_fallback=True
            )

            progress.update(task, description=f"Loading document: {Path(file_path).name}...")

            # Load document
            document = await vision_service.document_handler.load_document(file_path)

            progress.update(task, description="Processing document...")

            # Process based on operation
            if operation == "extract":
                result = await vision_service.processor.process_document(
                    document=document,
                    prompt=f"Extract all information from this {doc_type} document."
                )
            elif operation == "ocr":
                result = await vision_service.ocr_engine.extract_text(file_path)
                result = {"text": result[0], "confidence": result[1]}
            else:
                console.print(f"[bold red]Error:[/bold red] Unknown operation: {operation}")
                raise typer.Exit(1)

            progress.update(task, description="Complete!", completed=True)

        # Display result
        console.print("\n[bold green]Result:[/bold green]")
        if output_format == "json":
            console.print(json.dumps(result if isinstance(result, dict) else {"content": str(result)}, indent=2))
        else:
            console.print(str(result))

        # Track cost if available
        if hasattr(result, 'cost'):
            cost_tracker = get_cost_tracker()
            await cost_tracker.add_cost(result.cost, "openai", "gpt-4o")
            console.print(f"\n[dim]Cost: ${result.cost:.4f}[/dim]")

        await provider.close()

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)


@app.command()
def computer(
    task: str = typer.Argument(..., help="Task to perform"),
    env: str = typer.Option("browser", "--env", "-e", help="Environment: browser, desktop_mac"),
    url: Optional[str] = typer.Option(None, "--url", "-u", help="Starting URL for browser tasks"),
):
    """🤖 Computer use - Automate browser and desktop tasks."""
    if not check_env_vars():
        raise typer.Exit(1)

    asyncio.run(_computer_async(task, env, url))


async def _computer_async(task: str, env: str, url: Optional[str]):
    """Async computer use implementation."""
    from providers.base import ProviderConfig
    from services.responses import ComputerUseExecutor

    console.print(Panel(
        f"[bold]Task:[/bold] {task}\n"
        f"[bold]Environment:[/bold] {env}\n"
        f"[bold]URL:[/bold] {url or 'N/A'}",
        title="🤖 Computer Use",
        border_style="cyan"
    ))

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress_task = progress.add_task("Initializing computer use...", total=None)

            # Initialize executor
            config = ProviderConfig(api_key=os.getenv("OPENAI_API_KEY"))
            executor = ComputerUseExecutor(config)
            await executor.initialize()

            progress.update(progress_task, description="Executing task...")

            # Execute task
            result = await executor.execute_task(
                task_description=task,
                environment=env,
                url=url
            )

            progress.update(progress_task, description="Complete!", completed=True)

        # Display result
        console.print("\n[bold green]Execution Result:[/bold green]")
        console.print(Panel(str(result), border_style="green"))

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)


@app.command()
def reason(
    problem: str = typer.Argument(..., help="Problem to reason about"),
    detail: str = typer.Option("high", "--detail", "-d", help="Reasoning effort: high, medium, low"),
):
    """🧠 Reasoning service - Complex multi-step reasoning."""
    if not check_env_vars():
        raise typer.Exit(1)

    asyncio.run(_reason_async(problem, detail))


async def _reason_async(problem: str, detail: str):
    """Async reasoning implementation."""
    from providers.openai_provider import OpenAIProvider
    from providers.base import ProviderConfig
    from services.reasoning import ReasoningPlanner

    console.print(Panel(
        f"[bold]Problem:[/bold] {problem}\n"
        f"[bold]Detail:[/bold] {detail}",
        title="🧠 Reasoning",
        border_style="magenta"
    ))

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Initializing reasoning service...", total=None)

            # Initialize provider
            config = ProviderConfig(api_key=os.getenv("OPENAI_API_KEY"))
            provider = OpenAIProvider(config)
            await provider.initialize()

            progress.update(task, description="Creating reasoning plan...")

            # Create planner
            planner = ReasoningPlanner(provider)

            progress.update(task, description="Reasoning about problem...")

            # Plan task
            result = await planner.plan_task(problem, reasoning_effort=detail)

            progress.update(task, description="Complete!", completed=True)

        # Display result
        console.print("\n[bold yellow]Reasoning Plan:[/bold yellow]")
        console.print(Panel(str(result), border_style="yellow"))

        await provider.close()

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)


@app.command()
def costs(
    today: bool = typer.Option(False, "--today", help="Show today's costs"),
    breakdown: bool = typer.Option(False, "--breakdown", "-b", help="Show detailed breakdown"),
):
    """💰 Cost tracking - Monitor spending across providers."""
    asyncio.run(_costs_async(today, breakdown))


async def _costs_async(today: bool, breakdown: bool):
    """Async cost tracking."""
    from observability.costs import get_cost_tracker, CostWindow

    console.print(Panel("[bold]Cost Tracking Dashboard[/bold]", border_style="yellow"))

    try:
        tracker = get_cost_tracker()

        # Get totals
        request_total = await tracker.get_total(CostWindow.PER_REQUEST)
        hourly_total = await tracker.get_total(CostWindow.HOURLY)
        daily_total = await tracker.get_total(CostWindow.DAILY)

        # Display summary
        table = Table(title="Cost Summary")
        table.add_column("Window", style="cyan")
        table.add_column("Total Cost", justify="right", style="yellow")
        table.add_column("Limit", justify="right", style="red")

        table.add_row("Current Request", f"${request_total:.4f}", "$1.00")
        table.add_row("Current Hour", f"${hourly_total:.4f}", "$10.00")
        table.add_row("Today", f"${daily_total:.4f}", "$50.00")

        console.print(table)

        # Breakdown by provider
        if breakdown:
            breakdown_data = await tracker.get_breakdown_by_provider(CostWindow.DAILY)

            if breakdown_data:
                console.print("\n[bold]Breakdown by Provider:[/bold]")
                provider_table = Table()
                provider_table.add_column("Provider", style="cyan")
                provider_table.add_column("Cost", justify="right", style="yellow")

                for provider, cost in breakdown_data.items():
                    provider_table.add_column(provider, f"${cost:.4f}")

                console.print(provider_table)
            else:
                console.print("\n[dim]No cost data available yet.[/dim]")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)


@app.command()
def status():
    """📊 System status - Check services and configuration."""
    console.print(Panel("[bold]System Status Check[/bold]", border_style="green"))

    # Check Docker services
    import subprocess

    try:
        result = subprocess.run(
            ["docker-compose", "ps", "--format", "json"],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            console.print("[green]✓[/green] Docker Compose is running")
        else:
            console.print("[yellow]⚠[/yellow] Docker Compose not running")
            console.print("[dim]Run 'make docker-up' to start services[/dim]")
    except Exception:
        console.print("[yellow]⚠[/yellow] Could not check Docker status")

    # Check environment variables
    console.print("\n[bold]Environment Variables:[/bold]")
    env_vars = {
        "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY"),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "GOOGLE_API_KEY": os.getenv("GOOGLE_API_KEY"),
    }

    for var, value in env_vars.items():
        if value:
            console.print(f"[green]✓[/green] {var}: {value[:10]}...")
        else:
            console.print(f"[red]✗[/red] {var}: Not set")

    # Service URLs
    console.print("\n[bold]Service URLs:[/bold]")
    console.print("📊 Grafana: http://localhost:3000")
    console.print("📈 Prometheus: http://localhost:9090")
    console.print("🔍 Jaeger: http://localhost:16686")
    console.print("💾 ChromaDB: http://localhost:8000")


@app.command()
def monitor():
    """📈 Monitor system metrics."""
    console.print(Panel("[bold]System Metrics URLs[/bold]", border_style="blue"))
    console.print("\n📊 [bold]Grafana:[/bold] http://localhost:3000")
    console.print("   Dashboard for visualizing metrics\n")
    console.print("📈 [bold]Prometheus:[/bold] http://localhost:9090")
    console.print("   Raw metrics and queries\n")
    console.print("🔍 [bold]Jaeger:[/bold] http://localhost:16686")
    console.print("   Distributed tracing\n")
    console.print("[dim]Ensure Docker services are running: make docker-up[/dim]")


def main():
    """Entry point."""
    app()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
List Planner Tasks

Fetches and displays all Planner tasks assigned to the user.
Usage: python3 scripts/graph/list_planner_tasks.py [--details] [--filter-tier TIER]
"""

import sys
import asyncio
import argparse
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.table import Table

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from services.microsoft_graph.auth import create_authenticator_from_env
from services.microsoft_graph.base_client import GraphBaseClient
from services.microsoft_graph.planner_client import PlannerClient

console = Console()


async def main():
    parser = argparse.ArgumentParser(description="List Microsoft Planner tasks")
    parser.add_argument("--details", action="store_true", help="Include task details")
    parser.add_argument("--filter-tier", type=int, help="Filter by tier (0-3)")
    parser.add_argument("--filter-bucket", help="Filter by bucket name")
    parser.add_argument("--priority-max", type=int, help="Filter by max priority")
    args = parser.parse_args()

    console.print("\n[bold cyan]Microsoft Planner Tasks[/bold cyan]\n")

    try:
        # Authenticate
        authenticator = create_authenticator_from_env()

        async with GraphBaseClient(authenticator) as base_client:
            planner = PlannerClient(base_client)

            # Fetch tasks
            console.print("[yellow]Fetching tasks...[/yellow]")
            tasks = await planner.get_my_tasks(include_details=args.details)

            # Apply client-side filters (Planner doesn't support $filter)
            if args.filter_bucket:
                tasks = [t for t in tasks if t.get("bucketId") == args.filter_bucket]

            if args.priority_max is not None:
                tasks = planner.filter_tasks(tasks, priority_max=args.priority_max)

            # Sort by due date
            tasks = planner.sort_tasks(tasks, by="dueDateTime")

            # Display
            if not tasks:
                console.print("[yellow]No tasks found[/yellow]")
                return 0

            table = Table(title=f"Planner Tasks ({len(tasks)} total)")
            table.add_column("Title", style="cyan", no_wrap=False)
            table.add_column("Priority", justify="right", style="magenta")
            table.add_column("Due Date", style="green")
            table.add_column("% Done", justify="right", style="yellow")
            table.add_column("Plan ID", style="dim")

            for task in tasks:
                title = task["title"]
                priority = task.get("priority", "N/A")
                due = task.get("dueDateTime", "N/A")
                if due != "N/A":
                    due = datetime.fromisoformat(due.replace("Z", "+00:00")).strftime("%Y-%m-%d")
                percent = f"{task.get('percentComplete', 0)}%"
                plan_id = task.get("planId", "")[:12] + "..."

                table.add_row(title, str(priority), due, percent, plan_id)

            console.print(table)

            # Show details if requested
            if args.details:
                console.print("\n[bold]Task Details:[/bold]\n")
                for task in tasks[:5]:  # Show first 5
                    console.print(f"[cyan]{task['title']}[/cyan]")
                    if "details" in task:
                        desc = task["details"].get("description", "No description")
                        console.print(f"  {desc[:100]}...")
                    console.print()

            return 0

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

#!/usr/bin/env python3
"""
List All Planner Plans

Uses app-only permissions to list all Planner plans in the organization.
"""

import sys
import os
import asyncio
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from services.microsoft_graph.auth import create_authenticator_from_env
from services.microsoft_graph.base_client import GraphBaseClient
from rich.console import Console
from rich.table import Table

console = Console()


async def main():
    console.print("\n[bold cyan]Microsoft Planner Plans[/bold cyan]\n")

    try:
        # Authenticate
        authenticator = create_authenticator_from_env()

        async with GraphBaseClient(authenticator) as client:
            # Get all groups (where plans live)
            console.print("[yellow]Fetching groups...[/yellow]")
            groups_response = await client.get("/groups")
            groups = groups_response.get("value", [])

            console.print(f"[green]Found {len(groups)} groups[/green]\n")

            all_plans = []

            for group in groups[:10]:  # Limit to first 10 groups
                group_id = group["id"]
                group_name = group.get("displayName", "Unknown")

                try:
                    # Get plans for this group
                    plans_response = await client.get(f"/groups/{group_id}/planner/plans")
                    plans = plans_response.get("value", [])

                    for plan in plans:
                        plan["group_name"] = group_name
                        all_plans.append(plan)

                except Exception as e:
                    console.print(f"[dim]Skipping group {group_name}: {str(e)}[/dim]")

            # Display plans
            if not all_plans:
                console.print("[yellow]No Planner plans found[/yellow]")
                console.print("\n[dim]Note: You may need user-delegated permissions to access plans.[/dim]")
                return 0

            table = Table(title=f"Planner Plans ({len(all_plans)} total)")
            table.add_column("Plan Name", style="cyan", no_wrap=False)
            table.add_column("Group", style="green")
            table.add_column("Plan ID", style="dim")

            for plan in all_plans:
                table.add_row(
                    plan.get("title", "Untitled"),
                    plan.get("group_name", "Unknown"),
                    plan["id"][:20] + "..."
                )

            console.print(table)
            console.print()

            return 0

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

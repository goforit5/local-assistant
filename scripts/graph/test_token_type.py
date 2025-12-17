#!/usr/bin/env python3
"""
Test Token Type and Permissions

Checks what type of token we have (app-only vs user-delegated)
and what endpoints we can access.
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
    console.print("\n[bold cyan]Testing Microsoft Graph Token[/bold cyan]\n")

    try:
        # Authenticate
        authenticator = create_authenticator_from_env()
        token = authenticator.get_access_token()

        console.print(f"[green]✓ Got access token ({len(token)} chars)[/green]")

        # Check account info
        account_info = authenticator.get_account_info()
        if account_info:
            console.print(f"[green]✓ Token Type: User-Delegated[/green]")
            console.print(f"  Username: {account_info['username']}")
        else:
            console.print(f"[yellow]⚠ Token Type: App-Only (no user context)[/yellow]")

        console.print()

        async with GraphBaseClient(authenticator) as client:
            # Test various endpoints
            tests = [
                ("/me", "My Profile (User-Delegated)"),
                ("/me/todo/lists", "My To Do Lists (User-Delegated)"),
                ("/me/planner/tasks", "My Planner Tasks (User-Delegated)"),
                ("/users", "All Users (App-Only or Delegated with permissions)"),
                ("/groups", "All Groups (App-Only or Delegated with permissions)"),
            ]

            table = Table(title="Endpoint Access Tests")
            table.add_column("Endpoint", style="cyan")
            table.add_column("Description", style="dim")
            table.add_column("Status", style="bold")

            for endpoint, description in tests:
                try:
                    response = await client.get(endpoint)
                    if "value" in response:
                        count = len(response["value"])
                        table.add_row(endpoint, description, f"[green]✓ Success ({count} items)[/green]")
                    else:
                        table.add_row(endpoint, description, "[green]✓ Success[/green]")
                except Exception as e:
                    error_msg = str(e)
                    if "403" in error_msg:
                        table.add_row(endpoint, description, "[red]✗ 403 Forbidden[/red]")
                    elif "401" in error_msg:
                        table.add_row(endpoint, description, "[red]✗ 401 Unauthorized[/red]")
                    else:
                        table.add_row(endpoint, description, f"[red]✗ {error_msg[:30]}...[/red]")

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

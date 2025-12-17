"""
Microsoft Planner Client

Provides high-level interface to Microsoft Planner API.

Key Features (based on 2025 research):
- List plans, buckets, and tasks
- Batch fetching of task details (20 at a time)
- Client-side filtering (Planner doesn't support $filter)
- Business Scenarios API support (external integrations)
- Container support (groups, drive items, etc.)

Limitations:
- Premium Planner features not available via API
- No $filter support - must filter client-side
- Task details require separate API calls (use batching!)
- Rate limits apply (10k requests / 10 min)

API Endpoints:
- /me/planner/tasks - All tasks assigned to user
- /planner/plans/{id} - Plan details
- /planner/plans/{id}/buckets - Buckets in a plan
- /planner/plans/{id}/tasks - Tasks in a plan
- /planner/tasks/{id}/details - Task details (checklists, references)
"""

import structlog
from typing import List, Dict, Any, Optional
from datetime import datetime, date

logger = structlog.get_logger(__name__)


class PlannerClient:
    """Client for Microsoft Planner API operations."""

    def __init__(self, base_client):
        """
        Initialize Planner client.

        Args:
            base_client: GraphBaseClient instance
        """
        self.client = base_client
        logger.info("planner_client_initialized")

    async def get_my_tasks(
        self,
        include_details: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Get all Planner tasks assigned to the authenticated user.

        Args:
            include_details: Fetch task details (checklists, references) via batch

        Returns:
            List of task dicts with optional details
        """
        logger.info("fetching_my_planner_tasks")

        # Get tasks
        tasks = await self.client.get_paginated("/me/planner/tasks")

        logger.info("planner_tasks_retrieved", count=len(tasks))

        # Optionally fetch details in batch
        if include_details and tasks:
            tasks = await self._enrich_tasks_with_details(tasks)

        return tasks

    async def get_plan(self, plan_id: str) -> Dict[str, Any]:
        """
        Get plan details.

        Args:
            plan_id: Plan ID

        Returns:
            Plan dict
        """
        logger.debug("fetching_plan", plan_id=plan_id)
        return await self.client.get(f"/planner/plans/{plan_id}")

    async def get_plan_buckets(self, plan_id: str) -> List[Dict[str, Any]]:
        """
        Get all buckets in a plan.

        Buckets represent workflow stages (e.g., "Intake", "In Progress", "Done").

        Args:
            plan_id: Plan ID

        Returns:
            List of bucket dicts
        """
        logger.debug("fetching_plan_buckets", plan_id=plan_id)
        response = await self.client.get(f"/planner/plans/{plan_id}/buckets")
        return response.get("value", [])

    async def get_plan_tasks(
        self,
        plan_id: str,
        include_details: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Get all tasks in a plan.

        Args:
            plan_id: Plan ID
            include_details: Fetch task details via batch

        Returns:
            List of task dicts
        """
        logger.debug("fetching_plan_tasks", plan_id=plan_id)

        response = await self.client.get(f"/planner/plans/{plan_id}/tasks")
        tasks = response.get("value", [])

        if include_details and tasks:
            tasks = await self._enrich_tasks_with_details(tasks)

        return tasks

    async def get_task(
        self,
        task_id: str,
        include_details: bool = True,
    ) -> Dict[str, Any]:
        """
        Get single task.

        Args:
            task_id: Task ID
            include_details: Fetch task details

        Returns:
            Task dict
        """
        logger.debug("fetching_task", task_id=task_id)

        task = await self.client.get(f"/planner/tasks/{task_id}")

        if include_details:
            details = await self.get_task_details(task_id)
            task["details"] = details

        return task

    async def get_task_details(self, task_id: str) -> Dict[str, Any]:
        """
        Get task details (description, checklist, references).

        Task details are stored separately and require additional API call.

        Args:
            task_id: Task ID

        Returns:
            Task details dict
        """
        logger.debug("fetching_task_details", task_id=task_id)
        return await self.client.get(f"/planner/tasks/{task_id}/details")

    async def _enrich_tasks_with_details(
        self,
        tasks: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Enrich tasks with details using batch requests.

        This is the recommended approach per research:
        "You can get the list of tasks and then launch a number of batched
        queries to get details of those tasks (note that 20 is currently
        the max number of items in the batch query)."

        Args:
            tasks: List of task dicts

        Returns:
            List of task dicts with 'details' field added
        """
        if not tasks:
            return tasks

        logger.info("enriching_tasks_with_details", count=len(tasks))

        # Build batch requests (max 20 per batch)
        batch_requests = []
        for i, task in enumerate(tasks):
            task_id = task["id"]
            batch_requests.append({
                "id": str(i),
                "method": "GET",
                "url": f"/planner/tasks/{task_id}/details",
            })

        # Execute batch (will auto-split if > 20)
        batch_responses = await self.client.batch(batch_requests)

        # Match responses to tasks
        details_by_idx = {}
        for response in batch_responses:
            idx = int(response["id"])
            if response.get("status") == 200:
                details_by_idx[idx] = response["body"]
            else:
                logger.warning(
                    "task_details_fetch_failed",
                    task_id=tasks[idx]["id"],
                    status=response.get("status"),
                )

        # Add details to tasks
        for i, task in enumerate(tasks):
            if i in details_by_idx:
                task["details"] = details_by_idx[i]

        logger.info("tasks_enriched", success_count=len(details_by_idx))
        return tasks

    async def create_task(
        self,
        plan_id: str,
        bucket_id: str,
        title: str,
        assignments: Optional[Dict[str, Dict]] = None,
        due_date: Optional[date] = None,
        start_date: Optional[date] = None,
        priority: Optional[int] = None,
        percent_complete: Optional[int] = 0,
    ) -> Dict[str, Any]:
        """
        Create a new Planner task.

        Args:
            plan_id: Plan ID
            bucket_id: Bucket ID
            title: Task title
            assignments: Dict of user IDs to assignment details
            due_date: Due date
            start_date: Start date
            priority: Priority (0-10, where 0 is highest)
            percent_complete: Completion percentage (0-100)

        Returns:
            Created task dict

        Example:
            >>> task = await client.create_task(
            >>>     plan_id="plan123",
            >>>     bucket_id="bucket456",
            >>>     title="Implement feature X",
            >>>     assignments={
            >>>         "user-id-123": {
            >>>             "@odata.type": "#microsoft.graph.plannerAssignment",
            >>>             "orderHint": " !"
            >>>         }
            >>>     },
            >>>     due_date=date(2025, 12, 31),
            >>>     priority=1,
            >>> )
        """
        logger.info("creating_task", plan_id=plan_id, title=title)

        task_data: Dict[str, Any] = {
            "planId": plan_id,
            "bucketId": bucket_id,
            "title": title,
            "percentComplete": percent_complete,
        }

        if assignments:
            task_data["assignments"] = assignments

        if due_date:
            task_data["dueDateTime"] = due_date.isoformat() + "T00:00:00Z"

        if start_date:
            task_data["startDateTime"] = start_date.isoformat() + "T00:00:00Z"

        if priority is not None:
            task_data["priority"] = priority

        task = await self.client.post("/planner/tasks", task_data)
        logger.info("task_created", task_id=task["id"])
        return task

    async def update_task(
        self,
        task_id: str,
        etag: str,
        updates: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Update a Planner task.

        IMPORTANT: Planner uses optimistic concurrency control.
        You MUST provide the current ETag from the task object.

        Args:
            task_id: Task ID
            etag: Current ETag (from task's @odata.etag field)
            updates: Fields to update

        Returns:
            Updated task dict

        Example:
            >>> task = await client.get_task(task_id)
            >>> updated = await client.update_task(
            >>>     task_id=task_id,
            >>>     etag=task["@odata.etag"],
            >>>     updates={"percentComplete": 50}
            >>> )
        """
        logger.info("updating_task", task_id=task_id)

        # Add ETag header for optimistic concurrency
        response = await self.client.patch(
            f"/planner/tasks/{task_id}",
            json_data=updates,
            params={"If-Match": etag},
        )

        logger.info("task_updated", task_id=task_id)
        return response

    async def delete_task(self, task_id: str, etag: str) -> None:
        """
        Delete a Planner task.

        Args:
            task_id: Task ID
            etag: Current ETag
        """
        logger.info("deleting_task", task_id=task_id)

        await self.client.delete(
            f"/planner/tasks/{task_id}",
            params={"If-Match": etag},
        )

        logger.info("task_deleted", task_id=task_id)

    def filter_tasks(
        self,
        tasks: List[Dict[str, Any]],
        bucket_id: Optional[str] = None,
        assigned_to_user_id: Optional[str] = None,
        priority_max: Optional[int] = None,
        due_before: Optional[datetime] = None,
        due_after: Optional[datetime] = None,
        percent_complete_min: Optional[int] = None,
        percent_complete_max: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Filter tasks client-side.

        IMPORTANT: Per research findings, "Planner doesn't support filters
        at this time." Microsoft Graph ignores $filter parameter for Planner.
        Must filter client-side.

        Args:
            tasks: List of tasks to filter
            bucket_id: Filter by bucket
            assigned_to_user_id: Filter by assigned user
            priority_max: Filter by max priority (inclusive)
            due_before: Filter by due date before
            due_after: Filter by due date after
            percent_complete_min: Filter by min completion
            percent_complete_max: Filter by max completion

        Returns:
            Filtered list of tasks
        """
        filtered = tasks

        if bucket_id:
            filtered = [t for t in filtered if t.get("bucketId") == bucket_id]

        if assigned_to_user_id:
            filtered = [
                t for t in filtered
                if assigned_to_user_id in t.get("assignments", {})
            ]

        if priority_max is not None:
            filtered = [
                t for t in filtered
                if t.get("priority", 5) <= priority_max
            ]

        if due_before:
            filtered = [
                t for t in filtered
                if t.get("dueDateTime") and
                datetime.fromisoformat(t["dueDateTime"].replace("Z", "+00:00")) < due_before
            ]

        if due_after:
            filtered = [
                t for t in filtered
                if t.get("dueDateTime") and
                datetime.fromisoformat(t["dueDateTime"].replace("Z", "+00:00")) > due_after
            ]

        if percent_complete_min is not None:
            filtered = [
                t for t in filtered
                if t.get("percentComplete", 0) >= percent_complete_min
            ]

        if percent_complete_max is not None:
            filtered = [
                t for t in filtered
                if t.get("percentComplete", 0) <= percent_complete_max
            ]

        logger.debug(
            "tasks_filtered",
            input_count=len(tasks),
            output_count=len(filtered),
        )

        return filtered

    def sort_tasks(
        self,
        tasks: List[Dict[str, Any]],
        by: str = "dueDateTime",
        reverse: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Sort tasks by field.

        Args:
            tasks: List of tasks to sort
            by: Field to sort by (dueDateTime, priority, percentComplete, etc.)
            reverse: Sort descending

        Returns:
            Sorted list of tasks
        """
        def get_sort_key(task: Dict[str, Any]) -> Any:
            value = task.get(by)
            if value is None:
                return "" if isinstance(by, str) else 0
            return value

        return sorted(tasks, key=get_sort_key, reverse=reverse)

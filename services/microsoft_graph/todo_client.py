"""
Microsoft To Do Client

Provides high-level interface to Microsoft To Do API.

Key Features:
- List To Do lists and tasks
- Access "Assigned to you" view (shows Planner tasks)
- Support for recurrence patterns
- Linked resources (emails, files, etc.)
- Categories and importance
- Delta query support for efficient sync

API Endpoints:
- /me/todo/lists - All To Do lists
- /me/todo/lists/{id}/tasks - Tasks in a list
- /me/todo/lists/delta - Delta sync for lists
- /me/todo/lists/{id}/tasks/delta - Delta sync for tasks
"""

import structlog
from typing import List, Dict, Any, Optional
from datetime import datetime, date

logger = structlog.get_logger(__name__)


class TodoClient:
    """Client for Microsoft To Do API operations."""

    def __init__(self, base_client):
        """
        Initialize To Do client.

        Args:
            base_client: GraphBaseClient instance
        """
        self.client = base_client
        logger.info("todo_client_initialized")

    async def get_lists(self) -> List[Dict[str, Any]]:
        """
        Get all To Do lists for the user.

        Returns:
            List of To Do list dicts
        """
        logger.info("fetching_todo_lists")

        response = await self.client.get("/me/todo/lists")
        lists = response.get("value", [])

        logger.info("todo_lists_retrieved", count=len(lists))
        return lists

    async def get_list(self, list_id: str) -> Dict[str, Any]:
        """
        Get single To Do list.

        Args:
            list_id: List ID

        Returns:
            To Do list dict
        """
        logger.debug("fetching_todo_list", list_id=list_id)
        return await self.client.get(f"/me/todo/lists/{list_id}")

    async def get_tasks(
        self,
        list_id: str,
        filter_query: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get tasks from a To Do list.

        Args:
            list_id: List ID
            filter_query: Optional OData filter (e.g., "status ne 'completed'")

        Returns:
            List of task dicts
        """
        logger.debug("fetching_todo_tasks", list_id=list_id, filter=filter_query)

        params = {}
        if filter_query:
            params["$filter"] = filter_query

        response = await self.client.get(
            f"/me/todo/lists/{list_id}/tasks",
            params=params if params else None,
        )

        tasks = response.get("value", [])
        logger.debug("todo_tasks_retrieved", count=len(tasks))
        return tasks

    async def get_all_tasks(
        self,
        include_completed: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Get all tasks across all To Do lists.

        Args:
            include_completed: Include completed tasks

        Returns:
            List of task dicts with 'list_id' and 'list_name' added
        """
        logger.info("fetching_all_todo_tasks")

        lists = await self.get_lists()
        all_tasks = []

        for todo_list in lists:
            list_id = todo_list["id"]
            list_name = todo_list["displayName"]

            filter_query = None if include_completed else "status ne 'completed'"

            tasks = await self.get_tasks(list_id, filter_query)

            # Add list context to tasks
            for task in tasks:
                task["list_id"] = list_id
                task["list_name"] = list_name

            all_tasks.extend(tasks)

        logger.info("all_todo_tasks_retrieved", count=len(all_tasks))
        return all_tasks

    async def get_task(
        self,
        list_id: str,
        task_id: str,
    ) -> Dict[str, Any]:
        """
        Get single task.

        Args:
            list_id: List ID
            task_id: Task ID

        Returns:
            Task dict
        """
        logger.debug("fetching_todo_task", list_id=list_id, task_id=task_id)
        return await self.client.get(f"/me/todo/lists/{list_id}/tasks/{task_id}")

    async def create_task(
        self,
        list_id: str,
        title: str,
        body: Optional[str] = None,
        due_date: Optional[date] = None,
        reminder_date: Optional[datetime] = None,
        importance: str = "normal",  # "low", "normal", "high"
        categories: Optional[List[str]] = None,
        recurrence: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a new To Do task.

        Args:
            list_id: List ID to create task in
            title: Task title
            body: Task body/description
            due_date: Due date
            reminder_date: Reminder date/time
            importance: Importance level (low, normal, high)
            categories: List of category strings
            recurrence: Recurrence pattern dict

        Returns:
            Created task dict

        Example:
            >>> task = await client.create_task(
            >>>     list_id="list123",
            >>>     title="Call dentist",
            >>>     due_date=date(2025, 12, 10),
            >>>     importance="high",
            >>>     categories=["Personal", "Health"],
            >>>     reminder_date=datetime(2025, 12, 10, 9, 0),
            >>> )
        """
        logger.info("creating_todo_task", list_id=list_id, title=title)

        task_data: Dict[str, Any] = {
            "title": title,
            "importance": importance,
            "status": "notStarted",
        }

        if body:
            task_data["body"] = {
                "content": body,
                "contentType": "text",
            }

        if due_date:
            task_data["dueDateTime"] = {
                "dateTime": due_date.isoformat() + "T00:00:00",
                "timeZone": "UTC",
            }

        if reminder_date:
            task_data["reminderDateTime"] = {
                "dateTime": reminder_date.isoformat(),
                "timeZone": "UTC",
            }
            task_data["isReminderOn"] = True

        if categories:
            task_data["categories"] = categories

        if recurrence:
            task_data["recurrence"] = recurrence

        task = await self.client.post(
            f"/me/todo/lists/{list_id}/tasks",
            json_data=task_data,
        )

        logger.info("todo_task_created", task_id=task["id"])
        return task

    async def update_task(
        self,
        list_id: str,
        task_id: str,
        updates: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Update a To Do task.

        Args:
            list_id: List ID
            task_id: Task ID
            updates: Fields to update

        Returns:
            Updated task dict

        Example:
            >>> updated = await client.update_task(
            >>>     list_id="list123",
            >>>     task_id="task456",
            >>>     updates={
            >>>         "status": "completed",
            >>>         "completedDateTime": {
            >>>             "dateTime": datetime.now().isoformat(),
            >>>             "timeZone": "UTC"
            >>>         }
            >>>     }
            >>> )
        """
        logger.info("updating_todo_task", list_id=list_id, task_id=task_id)

        task = await self.client.patch(
            f"/me/todo/lists/{list_id}/tasks/{task_id}",
            json_data=updates,
        )

        logger.info("todo_task_updated", task_id=task_id)
        return task

    async def complete_task(
        self,
        list_id: str,
        task_id: str,
    ) -> Dict[str, Any]:
        """
        Mark task as completed.

        Args:
            list_id: List ID
            task_id: Task ID

        Returns:
            Updated task dict
        """
        logger.info("completing_todo_task", task_id=task_id)

        return await self.update_task(
            list_id=list_id,
            task_id=task_id,
            updates={
                "status": "completed",
                "completedDateTime": {
                    "dateTime": datetime.utcnow().isoformat(),
                    "timeZone": "UTC",
                }
            }
        )

    async def delete_task(
        self,
        list_id: str,
        task_id: str,
    ) -> None:
        """
        Delete a To Do task.

        Args:
            list_id: List ID
            task_id: Task ID
        """
        logger.info("deleting_todo_task", task_id=task_id)

        await self.client.delete(f"/me/todo/lists/{list_id}/tasks/{task_id}")

        logger.info("todo_task_deleted", task_id=task_id)

    async def get_linked_resources(
        self,
        list_id: str,
        task_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Get linked resources for a task.

        Linked resources can be:
        - Email messages
        - OneDrive files
        - SharePoint documents
        - External URLs

        Args:
            list_id: List ID
            task_id: Task ID

        Returns:
            List of linked resource dicts
        """
        logger.debug("fetching_linked_resources", task_id=task_id)

        response = await self.client.get(
            f"/me/todo/lists/{list_id}/tasks/{task_id}/linkedResources"
        )

        return response.get("value", [])

    async def add_linked_resource(
        self,
        list_id: str,
        task_id: str,
        web_url: str,
        display_name: str,
        application_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Add linked resource to task.

        Args:
            list_id: List ID
            task_id: Task ID
            web_url: URL of the resource
            display_name: Display name
            application_name: Application name (e.g., "Outlook", "OneDrive")

        Returns:
            Created linked resource dict
        """
        logger.info("adding_linked_resource", task_id=task_id, url=web_url)

        resource_data = {
            "webUrl": web_url,
            "displayName": display_name,
        }

        if application_name:
            resource_data["applicationName"] = application_name

        resource = await self.client.post(
            f"/me/todo/lists/{list_id}/tasks/{task_id}/linkedResources",
            json_data=resource_data,
        )

        logger.info("linked_resource_added", resource_id=resource["id"])
        return resource

    def filter_tasks(
        self,
        tasks: List[Dict[str, Any]],
        importance: Optional[str] = None,
        status: Optional[str] = None,
        has_due_date: Optional[bool] = None,
        due_before: Optional[datetime] = None,
        due_after: Optional[datetime] = None,
        categories: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Filter To Do tasks client-side.

        Args:
            tasks: List of tasks to filter
            importance: Filter by importance (low, normal, high)
            status: Filter by status (notStarted, inProgress, completed, etc.)
            has_due_date: Filter tasks with/without due date
            due_before: Filter by due date before
            due_after: Filter by due date after
            categories: Filter by categories (task must have all)

        Returns:
            Filtered list of tasks
        """
        filtered = tasks

        if importance:
            filtered = [t for t in filtered if t.get("importance") == importance]

        if status:
            filtered = [t for t in filtered if t.get("status") == status]

        if has_due_date is not None:
            if has_due_date:
                filtered = [t for t in filtered if t.get("dueDateTime")]
            else:
                filtered = [t for t in filtered if not t.get("dueDateTime")]

        if due_before:
            filtered = [
                t for t in filtered
                if t.get("dueDateTime") and
                datetime.fromisoformat(
                    t["dueDateTime"]["dateTime"]
                ) < due_before
            ]

        if due_after:
            filtered = [
                t for t in filtered
                if t.get("dueDateTime") and
                datetime.fromisoformat(
                    t["dueDateTime"]["dateTime"]
                ) > due_after
            ]

        if categories:
            filtered = [
                t for t in filtered
                if all(cat in t.get("categories", []) for cat in categories)
            ]

        logger.debug(
            "todo_tasks_filtered",
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
        Sort To Do tasks.

        Args:
            tasks: List of tasks to sort
            by: Field to sort by (dueDateTime, importance, status, title, etc.)
            reverse: Sort descending

        Returns:
            Sorted list of tasks
        """
        def get_sort_key(task: Dict[str, Any]) -> Any:
            value = task.get(by)

            # Handle nested structures
            if isinstance(value, dict) and "dateTime" in value:
                return value["dateTime"]

            if value is None:
                return "" if isinstance(by, str) else 0

            return value

        return sorted(tasks, key=get_sort_key, reverse=reverse)

    @staticmethod
    def create_recurrence_pattern(
        pattern_type: str,  # "daily", "weekly", "monthly", "yearly"
        interval: int = 1,
        days_of_week: Optional[List[str]] = None,
        day_of_month: Optional[int] = None,
        month: Optional[int] = None,
        range_type: str = "noEnd",  # "noEnd", "endDate", "numbered"
        range_end_date: Optional[date] = None,
        range_number_of_occurrences: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Create recurrence pattern for To Do task.

        Args:
            pattern_type: Type of recurrence
            interval: Interval between occurrences
            days_of_week: For weekly (e.g., ["monday", "wednesday", "friday"])
            day_of_month: For monthly (1-31)
            month: For yearly (1-12)
            range_type: When recurrence ends
            range_end_date: End date for endDate range type
            range_number_of_occurrences: Number for numbered range type

        Returns:
            Recurrence pattern dict

        Example:
            >>> # Every weekday
            >>> pattern = TodoClient.create_recurrence_pattern(
            >>>     pattern_type="weekly",
            >>>     interval=1,
            >>>     days_of_week=["monday", "tuesday", "wednesday", "thursday", "friday"],
            >>> )
            >>>
            >>> # 15th of every month
            >>> pattern = TodoClient.create_recurrence_pattern(
            >>>     pattern_type="monthly",
            >>>     interval=1,
            >>>     day_of_month=15,
            >>>     range_type="endDate",
            >>>     range_end_date=date(2026, 12, 31),
            >>> )
        """
        pattern: Dict[str, Any] = {
            "type": pattern_type,
            "interval": interval,
        }

        if days_of_week:
            pattern["daysOfWeek"] = days_of_week

        if day_of_month:
            pattern["dayOfMonth"] = day_of_month

        if month:
            pattern["month"] = month

        range_data: Dict[str, Any] = {
            "type": range_type,
            "startDate": date.today().isoformat(),
        }

        if range_type == "endDate" and range_end_date:
            range_data["endDate"] = range_end_date.isoformat()

        if range_type == "numbered" and range_number_of_occurrences:
            range_data["numberOfOccurrences"] = range_number_of_occurrences

        return {
            "pattern": pattern,
            "range": range_data,
        }

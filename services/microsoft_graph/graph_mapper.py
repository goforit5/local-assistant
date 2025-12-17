"""
Graph Mapper

Bidirectional mapping between Microsoft Graph entities and Life Graph models.

Handles:
- Planner task → Commitment
- To Do task → Commitment
- Commitment → Planner task
- Commitment → To Do task
- Category → Tier mapping
- Bucket → Status mapping
- Priority score calculation
"""

import structlog
from typing import Dict, Any, Optional
from datetime import datetime, date
from uuid import UUID

logger = structlog.get_logger(__name__)


class GraphMapper:
    """Maps between Microsoft Graph and Life Graph entities."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize mapper with configuration.

        Args:
            config: Microsoft Graph configuration dict
        """
        self.config = config
        self.planner_config = config.get("planner", {})
        self.todo_config = config.get("todo", {})
        self.mapping_config = config.get("lifegraph_mapping", {})

        # Build lookup tables
        self.category_to_tier = self._build_category_tier_map()
        self.bucket_to_status = self.planner_config.get("bucket_mappings", {})
        self.importance_to_priority = self.todo_config.get("importance_mapping", {})

        logger.info("graph_mapper_initialized")

    def _build_category_tier_map(self) -> Dict[str, int]:
        """Build category to tier lookup table."""
        category_mappings = self.planner_config.get("category_mappings", {})
        return {
            cat: mapping["tier"]
            for cat, mapping in category_mappings.items()
            if "tier" in mapping
        }

    def planner_task_to_commitment(
        self,
        task: Dict[str, Any],
        plan_name: Optional[str] = None,
        bucket_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Map Planner task to Commitment model.

        Args:
            task: Planner task dict
            plan_name: Plan display name (optional)
            bucket_name: Bucket display name (optional)

        Returns:
            Commitment dict ready for database insert
        """
        task_id = task["id"]
        title = task["title"]

        logger.debug("mapping_planner_task", task_id=task_id, title=title)

        # Extract tier from categories (category1, category2, etc.)
        tier = self._extract_tier_from_planner_categories(task)

        # Map priority (Planner: 0-10, where 0 is highest)
        planner_priority = task.get("priority", 5)
        priority_weight = self.planner_config.get("priority_mapping", {}).get(
            planner_priority, 0.5
        )

        # Map bucket to status
        bucket_id = task.get("bucketId")
        status = self.bucket_to_status.get(bucket_name, "not_started") if bucket_name else "not_started"

        # Parse dates
        due_date = self._parse_graph_date(task.get("dueDateTime"))
        start_date = self._parse_graph_date(task.get("startDateTime"))
        completed_date = self._parse_graph_date(task.get("completedDateTime"))

        # Description from details
        description = None
        if "details" in task:
            description = task["details"].get("description")

        # Build commitment dict
        commitment = {
            # Core fields
            "title": title,
            "description": description,
            "type": "obligation",  # Planner tasks are work obligations
            "status": "completed" if task.get("percentComplete") == 100 else status,

            # Dates
            "target_date": due_date,
            "start_date": start_date,
            "completed_at": completed_date,

            # Priority
            "tier": tier,
            "priority_score": priority_weight,

            # Progress
            "completion_percentage": task.get("percentComplete", 0),

            # Graph metadata
            "graph_source": "planner",
            "graph_task_id": task_id,
            "graph_plan_id": task.get("planId"),
            "graph_bucket_id": bucket_id,
            "graph_etag": task.get("@odata.etag"),

            # Additional context
            "area": self._get_plan_area(plan_name),
            "domain": self._get_plan_domain(plan_name),

            # Timestamps
            "last_synced_at": datetime.utcnow(),
        }

        # Add assignments (assignees)
        assignments = task.get("assignments", {})
        if assignments:
            # assignments is dict of user_id -> assignment_info
            commitment["assigned_to_user_ids"] = list(assignments.keys())

        return commitment

    def todo_task_to_commitment(
        self,
        task: Dict[str, Any],
        list_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Map To Do task to Commitment model.

        Args:
            task: To Do task dict
            list_name: List display name (optional)

        Returns:
            Commitment dict ready for database insert
        """
        task_id = task["id"]
        title = task["title"]

        logger.debug("mapping_todo_task", task_id=task_id, title=title)

        # Map importance to priority
        importance = task.get("importance", "normal")
        priority_weight = self.importance_to_priority.get(importance, 0.5)

        # Determine tier from categories or importance
        tier = self._extract_tier_from_todo_categories(task)
        if tier is None:
            tier = 2 if importance == "high" else 3

        # Map status
        todo_status = task.get("status", "notStarted")
        status_mapping = self.todo_config.get("status_mapping", {})
        status = status_mapping.get(todo_status, "not_started")

        # Parse dates
        due_date = None
        if task.get("dueDateTime"):
            due_date = self._parse_graph_datetime_obj(task["dueDateTime"])

        completed_date = None
        if task.get("completedDateTime"):
            completed_date = self._parse_graph_datetime_obj(task["completedDateTime"])

        # Description
        description = None
        if task.get("body"):
            description = task["body"].get("content")

        # Build commitment dict
        commitment = {
            # Core fields
            "title": title,
            "description": description,
            "type": "task",  # To Do tasks are personal tasks
            "status": status,

            # Dates
            "target_date": due_date,
            "completed_at": completed_date,

            # Priority
            "tier": tier,
            "priority_score": priority_weight,

            # Graph metadata
            "graph_source": "todo",
            "graph_task_id": task_id,
            "graph_list_id": task.get("list_id") or task.get("listId"),

            # Additional context
            "area": self._get_list_area(list_name),
            "domain": self._get_list_domain(list_name),

            # Timestamps
            "last_synced_at": datetime.utcnow(),
        }

        # Add categories
        if task.get("categories"):
            commitment["tags"] = task["categories"]

        # Add recurrence info
        if task.get("recurrence"):
            commitment["is_recurring"] = True
            commitment["recurrence_pattern"] = task["recurrence"]

        return commitment

    def commitment_to_planner_task(
        self,
        commitment: Dict[str, Any],
        plan_id: str,
        bucket_id: str,
    ) -> Dict[str, Any]:
        """
        Map Commitment to Planner task (for creating/updating in Planner).

        Args:
            commitment: Commitment dict
            plan_id: Target plan ID
            bucket_id: Target bucket ID

        Returns:
            Planner task dict ready for API
        """
        logger.debug(
            "mapping_commitment_to_planner",
            commitment_id=commitment.get("id"),
            title=commitment.get("title"),
        )

        # Map tier to category
        tier = commitment.get("tier")
        categories = self._tier_to_planner_categories(tier)

        # Map priority score to Planner priority (0-10)
        priority_score = commitment.get("priority_score", 0.5)
        planner_priority = self._priority_score_to_planner_priority(priority_score)

        # Build task data
        task_data = {
            "planId": plan_id,
            "bucketId": bucket_id,
            "title": commitment["title"],
            "priority": planner_priority,
        }

        # Optional fields
        if commitment.get("target_date"):
            task_data["dueDateTime"] = commitment["target_date"].isoformat() + "T00:00:00Z"

        if commitment.get("start_date"):
            task_data["startDateTime"] = commitment["start_date"].isoformat() + "T00:00:00Z"

        if commitment.get("completion_percentage") is not None:
            task_data["percentComplete"] = commitment["completion_percentage"]

        # Categories (for tier labels)
        if categories:
            task_data["appliedCategories"] = categories

        return task_data

    def commitment_to_todo_task(
        self,
        commitment: Dict[str, Any],
        list_id: str,
    ) -> Dict[str, Any]:
        """
        Map Commitment to To Do task (for creating/updating in To Do).

        Args:
            commitment: Commitment dict
            list_id: Target list ID

        Returns:
            To Do task dict ready for API
        """
        logger.debug(
            "mapping_commitment_to_todo",
            commitment_id=commitment.get("id"),
            title=commitment.get("title"),
        )

        # Map priority to importance
        priority_score = commitment.get("priority_score", 0.5)
        importance = "high" if priority_score > 0.7 else "normal" if priority_score > 0.3 else "low"

        # Map status
        status = commitment.get("status", "not_started")
        todo_status = {
            "not_started": "notStarted",
            "in_progress": "inProgress",
            "completed": "completed",
            "blocked": "waitingOnOthers",
            "deferred": "deferred",
        }.get(status, "notStarted")

        # Build task data
        task_data = {
            "title": commitment["title"],
            "importance": importance,
            "status": todo_status,
        }

        # Optional fields
        if commitment.get("description"):
            task_data["body"] = {
                "content": commitment["description"],
                "contentType": "text",
            }

        if commitment.get("target_date"):
            task_data["dueDateTime"] = {
                "dateTime": commitment["target_date"].isoformat() + "T00:00:00",
                "timeZone": "UTC",
            }

        # Categories (include tier)
        categories = []
        if commitment.get("tier") is not None:
            categories.append(f"Tier {commitment['tier']}")
        if commitment.get("tags"):
            categories.extend(commitment["tags"])
        if categories:
            task_data["categories"] = categories

        return task_data

    def _extract_tier_from_planner_categories(self, task: Dict[str, Any]) -> Optional[int]:
        """Extract tier from Planner task categories."""
        # Look for category1, category2, etc. that map to tiers
        for category_key, tier in self.category_to_tier.items():
            # Planner uses appliedCategories dict: {category1: true, category2: false, ...}
            applied = task.get("appliedCategories", {})
            if applied.get(category_key):
                return tier
        return None

    def _extract_tier_from_todo_categories(self, task: Dict[str, Any]) -> Optional[int]:
        """Extract tier from To Do task categories."""
        categories = task.get("categories", [])
        for cat in categories:
            # Look for "Tier 0", "Tier 1", etc.
            if cat.startswith("Tier "):
                try:
                    return int(cat.split()[1])
                except (IndexError, ValueError):
                    pass
        return None

    def _tier_to_planner_categories(self, tier: Optional[int]) -> Dict[str, bool]:
        """Convert tier to Planner categories dict."""
        if tier is None:
            return {}

        # Find category that maps to this tier
        for category_key, mapped_tier in self.category_to_tier.items():
            if mapped_tier == tier:
                return {category_key: True}

        return {}

    def _priority_score_to_planner_priority(self, score: float) -> int:
        """Convert priority score (0.0-1.0) to Planner priority (0-10)."""
        # Invert: high score (1.0) -> low priority number (0)
        return int((1.0 - score) * 10)

    def _get_plan_area(self, plan_name: Optional[str]) -> Optional[str]:
        """Get area for a plan."""
        if not plan_name:
            return None
        plans = self.planner_config.get("plans", [])
        for plan in plans:
            if plan["name"] == plan_name:
                return plan.get("area")
        return None

    def _get_plan_domain(self, plan_name: Optional[str]) -> Optional[str]:
        """Get domain for a plan."""
        if not plan_name:
            return None
        plans = self.planner_config.get("plans", [])
        for plan in plans:
            if plan["name"] == plan_name:
                return plan.get("domain")
        return None

    def _get_list_area(self, list_name: Optional[str]) -> Optional[str]:
        """Get area for a To Do list."""
        if not list_name:
            return None
        lists = self.todo_config.get("lists", [])
        for lst in lists:
            if lst["name"] == list_name:
                return lst.get("area")
        return None

    def _get_list_domain(self, list_name: Optional[str]) -> Optional[str]:
        """Get domain for a To Do list."""
        if not list_name:
            return None
        lists = self.todo_config.get("lists", [])
        for lst in lists:
            if lst["name"] == list_name:
                return lst.get("domain")
        return None

    def _parse_graph_date(self, date_str: Optional[str]) -> Optional[date]:
        """Parse Graph API date string to date object."""
        if not date_str:
            return None
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return dt.date()
        except (ValueError, AttributeError):
            return None

    def _parse_graph_datetime_obj(self, date_obj: Dict[str, Any]) -> Optional[date]:
        """Parse Graph API datetime object to date."""
        if not date_obj or "dateTime" not in date_obj:
            return None
        try:
            dt = datetime.fromisoformat(date_obj["dateTime"])
            return dt.date()
        except (ValueError, AttributeError):
            return None

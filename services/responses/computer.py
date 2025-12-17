"""Computer use executor for OpenAI Responses API automation."""

import asyncio
import time
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path
import yaml

from .client import ResponsesClient
from .safety import SafetyChecker, SafetyLevel
from .screenshots import ScreenshotManager
from providers.base import ProviderConfig


class ComputerUseExecutor:
    """Executes computer use automation tasks with safety checks and screenshots."""

    def __init__(
        self,
        provider_config: ProviderConfig,
        computer_use_config_path: str = "./config/computer_use.yaml",
    ):
        """Initialize computer use executor.

        Args:
            provider_config: Provider configuration
            computer_use_config_path: Path to computer use config
        """
        self.provider_config = provider_config
        self.config_path = computer_use_config_path
        self.config = self._load_config()

        # Initialize components
        self.client = ResponsesClient(provider_config)
        self.safety_checker = SafetyChecker(config_path=computer_use_config_path)
        self.screenshot_manager = self._initialize_screenshot_manager()

        # Session tracking
        self.session_id: Optional[str] = None
        self.conversation_history: List[Dict[str, Any]] = []
        self.action_history: List[Dict[str, Any]] = []
        self.session_start_time: Optional[datetime] = None
        self.total_cost = 0.0

    def _load_config(self) -> Dict:
        """Load computer use configuration.

        Returns:
            Configuration dictionary
        """
        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)

    def _initialize_screenshot_manager(self) -> ScreenshotManager:
        """Initialize screenshot manager from config.

        Returns:
            ScreenshotManager instance
        """
        screenshot_config = self.config.get("action_config", {}).get("screenshot", {})
        audit_config = self.config.get("audit", {}).get("screenshot_logging", {})

        return ScreenshotManager(
            save_path=audit_config.get("save_path", "./logs/screenshots"),
            save_to_disk=screenshot_config.get("save_to_disk", True),
            format=screenshot_config.get("format", "png"),
            retention_days=audit_config.get("retention_days", 7),
            max_size_mb=audit_config.get("max_size_mb", 1000),
            include_timestamp=screenshot_config.get("include_timestamp", True),
        )

    async def initialize(self) -> None:
        """Initialize executor and client."""
        await self.client.initialize()
        self.session_id = f"session_{int(time.time())}"
        self.session_start_time = datetime.now()

    async def execute_task(
        self,
        task_description: str,
        environment: str = None,
        max_steps: int = 20,
        url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute a computer use task.

        Args:
            task_description: Natural language task description
            environment: Environment type (browser, desktop_mac, etc.)
            max_steps: Maximum number of action steps
            url: Optional starting URL for browser environment

        Returns:
            Task execution result with actions and screenshots
        """
        if not environment:
            environment = self.config.get("openai_computer_use", {}).get(
                "default_environment", "browser"
            )

        env_config = self.config.get("openai_computer_use", {}).get(
            "environments", {}
        ).get(environment, {})

        # Build initial prompt
        initial_prompt = self._build_task_prompt(task_description, url)

        # Check safety before starting
        if url:
            url_check = self.safety_checker.check_domain(url)
            if not url_check.passed:
                return {
                    "success": False,
                    "error": f"Safety check failed: {url_check.reason}",
                    "safety_check": url_check.__dict__,
                }

        # Execute action loop
        result = await self._execute_action_loop(
            initial_prompt=initial_prompt,
            environment=environment,
            display_width=env_config.get("display_width", 1920),
            display_height=env_config.get("display_height", 1080),
            max_steps=max_steps,
        )

        return result

    async def _execute_action_loop(
        self,
        initial_prompt: str,
        environment: str,
        display_width: int,
        display_height: int,
        max_steps: int,
    ) -> Dict[str, Any]:
        """Execute the main action loop.

        Args:
            initial_prompt: Initial task prompt
            environment: Environment type
            display_width: Display width
            display_height: Display height
            max_steps: Maximum steps

        Returns:
            Execution result
        """
        step_count = 0
        completed = False
        error = None
        actions_taken = []

        try:
            while step_count < max_steps and not completed:
                step_count += 1

                # Get response from Responses API
                response = await self.client.create_response(
                    input_text=initial_prompt if step_count == 1 else "Continue",
                    environment=environment,
                    display_width=display_width,
                    display_height=display_height,
                    reasoning=self.config.get("reasoning", {}).get("summary", "concise"),
                    truncation=self.config.get("truncation", {}).get("strategy", "auto"),
                    conversation=self.conversation_history if step_count > 1 else None,
                )

                # Update conversation history
                self.conversation_history.append({
                    "role": "assistant",
                    "response_id": response["response_id"],
                    "output": response["output"],
                })

                # Process tool calls (actions)
                tool_calls = response.get("tool_calls", [])

                for tool_call in tool_calls:
                    action_result = await self._process_action(tool_call, environment)
                    actions_taken.append(action_result)

                    # Check if action failed
                    if not action_result.get("success", True):
                        error = action_result.get("error")
                        break

                # Update cost
                usage = response.get("usage", {})
                self.total_cost += self._calculate_cost(usage)

                # Check if task completed
                if response.get("status") == "completed":
                    completed = True
                    break

                # Wait before next step
                await asyncio.sleep(
                    self.config.get("timeouts", {}).get("screenshot_wait", 2)
                )

        except Exception as e:
            error = str(e)

        # Build final result
        result = {
            "success": completed and error is None,
            "session_id": self.session_id,
            "steps_taken": step_count,
            "actions_taken": len(actions_taken),
            "actions": actions_taken,
            "completed": completed,
            "total_cost": round(self.total_cost, 4),
            "duration_seconds": (
                datetime.now() - self.session_start_time
            ).total_seconds() if self.session_start_time else 0,
        }

        if error:
            result["error"] = error

        return result

    async def _process_action(
        self,
        tool_call: Dict[str, Any],
        environment: str,
    ) -> Dict[str, Any]:
        """Process a single action from tool call.

        Args:
            tool_call: Tool call data
            environment: Environment type

        Returns:
            Action result
        """
        action_type = tool_call.get("action", "unknown")
        action_start = time.time()

        # Safety check for action
        action_check = self.safety_checker.check_action(action_type, tool_call)

        if not action_check.passed:
            return {
                "success": False,
                "action": action_type,
                "error": f"Action blocked: {action_check.reason}",
                "safety_check": action_check.__dict__,
                "timestamp": datetime.now().isoformat(),
            }

        # If action requires confirmation, log warning
        if action_check.requires_acknowledgment:
            self._log_action_warning(action_type, action_check.reason)

        # Check text input safety
        if "text" in tool_call and tool_call["text"]:
            text_check = self.safety_checker.check_text_input(tool_call["text"])
            if not text_check.passed:
                return {
                    "success": False,
                    "action": action_type,
                    "error": f"Text input blocked: {text_check.reason}",
                    "safety_check": text_check.__dict__,
                    "timestamp": datetime.now().isoformat(),
                }

        # Execute action (in real implementation, this would interact with browser/desktop)
        # For now, we simulate action execution
        action_result = {
            "success": True,
            "action": action_type,
            "coordinate": tool_call.get("coordinate"),
            "text": tool_call.get("text"),
            "output": tool_call.get("output"),
            "timestamp": datetime.now().isoformat(),
            "duration_ms": int((time.time() - action_start) * 1000),
        }

        # Capture screenshot after action
        if self.config.get("action_config", {}).get("screenshot", {}).get("auto_capture", True):
            screenshot_result = await self._capture_post_action_screenshot(
                action_type,
                action_result
            )
            action_result["screenshot"] = screenshot_result

        # Add to action history
        self.action_history.append(action_result)

        return action_result

    async def _capture_post_action_screenshot(
        self,
        action_type: str,
        action_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Capture screenshot after action.

        Args:
            action_type: Type of action
            action_result: Action execution result

        Returns:
            Screenshot info
        """
        # Wait for page to stabilize
        wait_time = self.config.get("timeouts", {}).get("screenshot_wait", 2)
        await asyncio.sleep(wait_time)

        # In real implementation, capture actual screenshot
        # For now, generate placeholder
        placeholder_data = f"data:image/png;base64,PLACEHOLDER_{action_type}"

        screenshot_info = await self.screenshot_manager.capture_screenshot(
            screenshot_data=placeholder_data,
            action_type=action_type,
            metadata={
                "action_result": action_result,
                "session_id": self.session_id,
            }
        )

        return screenshot_info

    def _build_task_prompt(
        self,
        task_description: str,
        url: Optional[str] = None,
    ) -> str:
        """Build initial task prompt.

        Args:
            task_description: User task description
            url: Optional starting URL

        Returns:
            Formatted prompt
        """
        prompt = f"Task: {task_description}\n\n"

        if url:
            prompt += f"Starting URL: {url}\n\n"

        prompt += "Execute this task step by step. Take screenshots after each action."

        return prompt

    def _calculate_cost(self, usage: Dict[str, int]) -> float:
        """Calculate cost from token usage.

        Args:
            usage: Token usage dictionary

        Returns:
            Cost in dollars
        """
        # Use pricing from OpenAI provider
        pricing = {
            "input_per_1m": 2.50,
            "output_per_1m": 10.00,
        }

        input_cost = (usage.get("input_tokens", 0) / 1_000_000) * pricing["input_per_1m"]
        output_cost = (usage.get("output_tokens", 0) / 1_000_000) * pricing["output_per_1m"]

        return input_cost + output_cost

    def _log_action_warning(self, action_type: str, reason: str) -> None:
        """Log action warning.

        Args:
            action_type: Type of action
            reason: Warning reason
        """
        if self.config.get("audit", {}).get("enabled", True):
            print(f"[WARNING] Action '{action_type}': {reason}")

    def get_session_summary(self) -> Dict[str, Any]:
        """Get session summary.

        Returns:
            Session statistics
        """
        return {
            "session_id": self.session_id,
            "start_time": self.session_start_time.isoformat() if self.session_start_time else None,
            "duration_seconds": (
                datetime.now() - self.session_start_time
            ).total_seconds() if self.session_start_time else 0,
            "total_actions": len(self.action_history),
            "total_cost": round(self.total_cost, 4),
            "screenshots_captured": len(self.screenshot_manager._screenshot_cache),
            "safety_summary": self.safety_checker.get_safety_summary(),
        }

    async def close(self) -> None:
        """Clean up resources."""
        await self.client.close()

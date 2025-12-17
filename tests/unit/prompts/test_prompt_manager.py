"""Unit tests for PromptManager."""

import shutil
import tempfile
from pathlib import Path

import pytest
import yaml

from lib.shared.local_assistant_shared.prompts import PromptManager


@pytest.fixture(autouse=True)
def clear_prompt_cache():
    """Clear .prompt_cache before each test to avoid stale data."""
    cache_dir = Path(".prompt_cache")
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
    yield
    # Cleanup after test
    if cache_dir.exists():
        shutil.rmtree(cache_dir)


def test_prompt_manager_loads_prompt():
    """Test PromptManager loads a versioned prompt."""
    # Create temporary prompts directory
    with tempfile.TemporaryDirectory() as tmpdir:
        prompts_dir = Path(tmpdir)
        service_dir = prompts_dir / "test-service"
        service_dir.mkdir()

        # Create prompt file
        prompt_data = {
            "name": "test_prompt",
            "version": "1.0.0",
            "description": "Test prompt",
            "system_prompt": "You are a test assistant.",
            "user_prompt": "Hello, {{ name }}!",
            "output_schema": {"type": "object"},
            "variables": [{"name": "name", "type": "string", "required": True}],
            "performance": {"target_latency_ms": 100},
            "metadata": {"created_date": "2025-11-06"},
        }

        prompt_path = service_dir / "test_prompt_v1.0.0.yaml"
        with open(prompt_path, "w") as f:
            yaml.dump(prompt_data, f)

        # Load prompt
        manager = PromptManager(backend="local", prompts_dir=str(prompts_dir))
        prompt = manager.load_prompt(
            service_name="test-service", prompt_name="test_prompt", version="1.0.0"
        )

        # Verify
        assert prompt.name == "test_prompt"
        assert prompt.version == "1.0.0"
        assert prompt.system_prompt == "You are a test assistant."


def test_prompt_manager_renders_template():
    """Test PromptManager renders Jinja2 templates."""
    # Create temporary prompts directory
    with tempfile.TemporaryDirectory() as tmpdir:
        prompts_dir = Path(tmpdir)
        service_dir = prompts_dir / "test-service"
        service_dir.mkdir()

        # Create prompt file
        prompt_data = {
            "name": "test_prompt",
            "version": "1.0.0",
            "description": "Test prompt",
            "system_prompt": "You are a test assistant.",
            "user_prompt": "Hello, {{ name }}! Your score is {{ score }}.",
            "output_schema": {"type": "object"},
            "variables": [
                {"name": "name", "type": "string", "required": True},
                {"name": "score", "type": "number", "required": True},
            ],
            "performance": {"target_latency_ms": 100},
            "metadata": {"created_date": "2025-11-06"},
        }

        prompt_path = service_dir / "test_prompt_v1.0.0.yaml"
        with open(prompt_path, "w") as f:
            yaml.dump(prompt_data, f)

        # Load prompt and render
        manager = PromptManager(backend="local", prompts_dir=str(prompts_dir))
        prompt = manager.load_prompt(
            service_name="test-service", prompt_name="test_prompt", version="1.0.0"
        )

        rendered = prompt.render(name="Alice", score=42)

        # Verify (strip to handle any whitespace from YAML)
        assert rendered.strip() == "Hello, Alice! Your score is 42."


def test_prompt_manager_validates_required_variables():
    """Test PromptManager validates required template variables."""
    # Create temporary prompts directory
    with tempfile.TemporaryDirectory() as tmpdir:
        prompts_dir = Path(tmpdir)
        service_dir = prompts_dir / "test-service"
        service_dir.mkdir()

        # Create prompt file
        prompt_data = {
            "name": "test_prompt",
            "version": "1.0.0",
            "description": "Test prompt",
            "system_prompt": "You are a test assistant.",
            "user_prompt": "Hello, {{ name }}!",
            "output_schema": {"type": "object"},
            "variables": [{"name": "name", "type": "string", "required": True}],
            "performance": {"target_latency_ms": 100},
            "metadata": {"created_date": "2025-11-06"},
        }

        prompt_path = service_dir / "test_prompt_v1.0.0.yaml"
        with open(prompt_path, "w") as f:
            yaml.dump(prompt_data, f)

        # Load prompt
        manager = PromptManager(backend="local", prompts_dir=str(prompts_dir))
        prompt = manager.load_prompt(
            service_name="test-service", prompt_name="test_prompt", version="1.0.0"
        )

        # Try to render without required variable
        with pytest.raises(KeyError):
            prompt.render()  # Missing 'name' variable


def test_prompt_hash():
    """Test prompt hash generation for provenance."""
    # Create temporary prompts directory
    with tempfile.TemporaryDirectory() as tmpdir:
        prompts_dir = Path(tmpdir)
        service_dir = prompts_dir / "test-service"
        service_dir.mkdir()

        # Create prompt file
        prompt_data = {
            "name": "test_prompt",
            "version": "1.0.0",
            "description": "Test prompt",
            "system_prompt": "You are a test assistant.",
            "user_prompt": "Hello, {{ name }}!",
            "output_schema": {"type": "object"},
            "variables": [{"name": "name", "type": "string", "required": True}],
            "performance": {"target_latency_ms": 100},
            "metadata": {"created_date": "2025-11-06"},
        }

        prompt_path = service_dir / "test_prompt_v1.0.0.yaml"
        with open(prompt_path, "w") as f:
            yaml.dump(prompt_data, f)

        # Load prompt
        manager = PromptManager(backend="local", prompts_dir=str(prompts_dir))
        prompt = manager.load_prompt(
            service_name="test-service", prompt_name="test_prompt", version="1.0.0"
        )

        # Get hash
        prompt_hash = prompt.hash()

        # Verify
        assert isinstance(prompt_hash, str)
        assert len(prompt_hash) == 8  # 8-character truncated hash


def test_prompt_get_id():
    """Test prompt ID generation."""
    # Create temporary prompts directory
    with tempfile.TemporaryDirectory() as tmpdir:
        prompts_dir = Path(tmpdir)
        service_dir = prompts_dir / "test-service"
        service_dir.mkdir()

        # Create prompt file
        prompt_data = {
            "name": "test_prompt",
            "version": "1.0.0",
            "description": "Test prompt",
            "system_prompt": "You are a test assistant.",
            "user_prompt": "Hello!",
            "output_schema": {"type": "object"},
            "variables": [],
            "performance": {"target_latency_ms": 100},
            "metadata": {"created_date": "2025-11-06"},
        }

        prompt_path = service_dir / "test_prompt_v1.0.0.yaml"
        with open(prompt_path, "w") as f:
            yaml.dump(prompt_data, f)

        # Load prompt
        manager = PromptManager(backend="local", prompts_dir=str(prompts_dir))
        prompt = manager.load_prompt(
            service_name="test-service", prompt_name="test_prompt", version="1.0.0"
        )

        # Get ID
        prompt_id = prompt.get_id()

        # Verify
        assert prompt_id == "test-service/test_prompt:1.0.0"

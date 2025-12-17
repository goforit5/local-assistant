"""Unit tests for ConfigLoader."""

import tempfile
from pathlib import Path

import pytest
import yaml
from pydantic import BaseModel

from lib.shared.local_assistant_shared.config import ConfigLoader


class SimpleConfig(BaseModel):
    """Simple test config model."""

    name: str
    version: str
    count: int


class NestedConfig(BaseModel):
    """Nested test config model."""

    database: dict
    settings: dict


def test_config_loader_loads_valid_config():
    """Test ConfigLoader loads a valid YAML config."""
    # Create temporary config file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        config_data = {"name": "test-config", "version": "1.0.0", "count": 42}
        yaml.dump(config_data, f)
        config_path = f.name

    try:
        # Load config
        loader = ConfigLoader(SimpleConfig, config_path)
        config = loader.load()

        # Verify
        assert config.name == "test-config"
        assert config.version == "1.0.0"
        assert config.count == 42
    finally:
        # Cleanup
        Path(config_path).unlink()


def test_config_loader_caches_config():
    """Test ConfigLoader caches loaded config."""
    # Create temporary config file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        config_data = {"name": "test-config", "version": "1.0.0", "count": 42}
        yaml.dump(config_data, f)
        config_path = f.name

    try:
        # Load config twice
        loader = ConfigLoader(SimpleConfig, config_path)
        config1 = loader.load()
        config2 = loader.load()

        # Verify same instance (cached)
        assert config1 is config2
    finally:
        # Cleanup
        Path(config_path).unlink()


def test_config_loader_reload_bypasses_cache():
    """Test ConfigLoader reload() bypasses cache."""
    # Create temporary config file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        config_data = {"name": "test-config", "version": "1.0.0", "count": 42}
        yaml.dump(config_data, f)
        config_path = f.name

    try:
        # Load config
        loader = ConfigLoader(SimpleConfig, config_path)
        config1 = loader.load()

        # Modify file
        with open(config_path, "w") as f:
            config_data["count"] = 100
            yaml.dump(config_data, f)

        # Reload
        config2 = loader.reload()

        # Verify different instance with new value
        assert config1 is not config2
        assert config1.count == 42
        assert config2.count == 100
    finally:
        # Cleanup
        Path(config_path).unlink()


def test_config_loader_raises_on_missing_file():
    """Test ConfigLoader raises FileNotFoundError on missing file."""
    loader = ConfigLoader(SimpleConfig, "/nonexistent/config.yaml")

    with pytest.raises(FileNotFoundError):
        loader.load()


def test_config_loader_raises_on_invalid_config():
    """Test ConfigLoader raises ValidationError on invalid config."""
    # Create temporary config file with invalid data
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        # Missing required fields
        config_data = {"name": "test-config"}
        yaml.dump(config_data, f)
        config_path = f.name

    try:
        # Load config
        loader = ConfigLoader(SimpleConfig, config_path)

        with pytest.raises(Exception):  # Pydantic ValidationError
            loader.load()
    finally:
        # Cleanup
        Path(config_path).unlink()


def test_config_loader_handles_nested_config():
    """Test ConfigLoader handles nested config structures."""
    # Create temporary config file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        config_data = {
            "database": {"host": "localhost", "port": 5432},
            "settings": {"debug": True, "max_connections": 10},
        }
        yaml.dump(config_data, f)
        config_path = f.name

    try:
        # Load config
        loader = ConfigLoader(NestedConfig, config_path)
        config = loader.load()

        # Verify
        assert config.database["host"] == "localhost"
        assert config.database["port"] == 5432
        assert config.settings["debug"] is True
        assert config.settings["max_connections"] == 10
    finally:
        # Cleanup
        Path(config_path).unlink()

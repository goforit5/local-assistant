#!/usr/bin/env python3
"""
Config Validation Script

Loads all configuration files and validates them with Pydantic.
Exits with code 0 on success, 1 on failure.

Usage:
    python scripts/validate_config.py
"""

import sys
from pathlib import Path

# Add project root to path (must be before imports)  # noqa: E402
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from lib.shared.local_assistant_shared.config import (  # noqa: E402
    CommitmentPriorityConfig,
    ConfigLoader,
    DocumentIntelligenceConfig,
    EntityResolutionConfig,
    StorageConfig,
)


def validate_all_configs() -> bool:
    """
    Validate all configuration files.

    Returns:
        True if all configs are valid, False otherwise
    """
    configs = [
        (
            "document_intelligence_config.yaml",
            DocumentIntelligenceConfig,
            "Document Intelligence Config",
        ),
        (
            "entity_resolution_config.yaml",
            EntityResolutionConfig,
            "Entity Resolution Config",
        ),
        (
            "commitment_priority_config.yaml",
            CommitmentPriorityConfig,
            "Commitment Priority Config",
        ),
        (
            "storage_config.yaml",
            StorageConfig,
            "Storage Config",
        ),
    ]

    all_valid = True

    print("=" * 80)
    print("Configuration Validation")
    print("=" * 80)
    print()

    for config_file, config_class, display_name in configs:
        config_path = project_root / "config" / config_file
        print(f"Validating {display_name}...")
        print(f"  Path: {config_path}")

        try:
            loader = ConfigLoader(config_class, str(config_path))
            _ = loader.load()  # Load to validate
            print("  ✅ Valid")
            print()
        except FileNotFoundError as e:
            print(f"  ❌ File not found: {e}")
            print()
            all_valid = False
        except Exception as e:
            print(f"  ❌ Validation failed: {e}")
            print()
            all_valid = False

    print("=" * 80)
    if all_valid:
        print("✅ All configurations are valid!")
        print("=" * 80)
        return True
    else:
        print("❌ Some configurations are invalid. See errors above.")
        print("=" * 80)
        return False


if __name__ == "__main__":
    success = validate_all_configs()
    sys.exit(0 if success else 1)

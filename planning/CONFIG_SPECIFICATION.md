# Configuration Specification: Life Graph Integration
**Version**: 1.0.0
**Date**: 2025-11-06
**Status**: Planning Phase

---

## Overview

This document defines the complete configuration architecture following **unicorn-grade DRY principles**. All configuration is versioned, YAML-based, and follows the patterns established in `/Users/andrew/Projects/brokerage_structured_output/microservices/`.

### Design Principles
1. **Single Source of Truth**: One config file per concern
2. **Version Everything**: Semantic versioning for all prompts/configs
3. **Environment Aware**: Dev/staging/prod configs via env vars
4. **Type-Safe Loading**: Pydantic models for all configs
5. **Hot Reload**: Config changes without restart (dev mode)

---

## Configuration File Structure

```
local_assistant/
├── config/
│   ├── models_registry.yaml           # Model specs + pricing (SHARED)
│   ├── document_intelligence_config.yaml  # Pipeline configuration
│   ├── entity_resolution_config.yaml      # Fuzzy matching params
│   ├── commitment_priority_config.yaml    # Priority weights
│   ├── storage_config.yaml                 # File storage settings
│   │
│   └── prompts/
│       ├── entity-resolution/
│       │   ├── vendor_matching_v1.0.0.yaml
│       │   └── party_deduplication_v1.0.0.yaml
│       ├── commitment-creation/
│       │   ├── invoice_to_commitment_v1.0.0.yaml
│       │   └── priority_explanation_v1.0.0.yaml
│       └── validation/
│           ├── validate_vendor_v1.0.0.yaml
│           └── validate_commitment_v1.0.0.yaml
│
├── lib/shared/
│   └── local_assistant_shared/
│       ├── config/
│       │   ├── __init__.py
│       │   ├── model_registry.py          # Load models_registry.yaml
│       │   ├── pipeline_config.py         # Load pipeline configs
│       │   └── config_loader.py           # Base loader with caching
│       └── prompts/
│           ├── __init__.py
│           └── prompt_manager.py          # 3-tier caching (REUSE PATTERN)
│
└── .env.example                            # Environment template
```

---

## Core Configuration Files

### 1. `models_registry.yaml` (REUSE EXISTING)

**Location**: `lib/shared/config/models_registry.yaml`

**Purpose**: Single source of truth for all AI models

**Structure** (already exists in brokerage project):
```yaml
vision_models:
  gpt-4o:
    provider: openai
    model_id: gpt-4o
    cost:
      input_per_1m: 2.50
      output_per_1m: 10.00
    defaults:
      max_tokens: 32768
      temperature: 0.0

reasoning_models:
  o4-mini:
    provider: openai
    model_id: o4-mini
    cost:
      input_per_1m: 1.50
      output_per_1m: 6.00
    defaults:
      max_tokens: 65536
      temperature: 1.0
```

**Usage**:
```python
from local_assistant_shared.config import ModelRegistry

registry = ModelRegistry()
model = registry.get_model("gpt-4o")
print(f"Cost: ${model.cost.input_per_1m}/1M tokens")
```

---

### 2. `document_intelligence_config.yaml`

**Location**: `config/document_intelligence_config.yaml`

**Purpose**: Configure document processing pipeline

```yaml
# Document Intelligence Pipeline Configuration
# Version: 1.0.0
# Last Updated: 2025-11-06

pipeline:
  name: document-intelligence
  version: 1.0.0
  description: Document upload → entity resolution → commitment creation

# Vision Extraction Step
vision_extraction:
  enabled: true
  models:
    - gpt-4o  # Primary vision model
  overrides:
    gpt-4o:
      max_tokens: 16384
      temperature: 0.0
  cost_limits:
    per_document_warn: 0.05   # Warn if extraction > $0.05
    per_document_max: 0.10    # Fail if extraction > $0.10
  timeout_seconds: 60

# Signal Processing
signal_processing:
  enabled: true
  dedupe_window_days: 7       # Ignore duplicate uploads within 7 days
  classification:
    confidence_threshold: 0.80  # Require 80%+ confidence for auto-classification
    fallback_to_manual: true    # Queue low-confidence for review

# Entity Resolution
entity_resolution:
  vendor_matching:
    fuzzy_threshold: 0.90      # 90%+ similarity = match
    use_trigram_index: true    # Use PostgreSQL pg_trgm
    max_candidates: 5          # Return top 5 matches
    cache_ttl_seconds: 3600    # Cache vendor lookups for 1 hour
  party_deduplication:
    check_tax_id: true
    check_address: true
    confidence_levels:
      exact_match: 1.00         # name + tax_id match
      high_confidence: 0.90     # fuzzy name + address match
      medium_confidence: 0.80   # fuzzy name only
      low_confidence: 0.60      # queue for manual review

# Commitment Creation
commitment_creation:
  auto_create_for_types:
    - invoice                  # Always create "Pay Invoice" commitment
    - bill                     # Always create "Pay Bill" commitment
    - tax_notice               # Always create "File Taxes" commitment
  default_role_domain: Finance  # Default domain if not specified
  priority_calculation:
    time_weight: 0.30          # 30% weight for time pressure
    severity_weight: 0.25      # 25% weight for severity/risk
    amount_weight: 0.15        # 15% weight for dollar amount
    effort_weight: 0.15        # 15% weight for estimated hours
    dependency_weight: 0.10    # 10% weight for blockers
    preference_weight: 0.05    # 5% weight for user boost

# Document Storage
storage:
  backend: local               # "local" | "s3" | "gcs"
  local:
    base_path: ./data/documents
    max_file_size_mb: 50
  content_addressable: true    # Use SHA-256 as filename
  retention_days: null         # null = keep forever

# Interaction Logging
interaction_logging:
  enabled: true
  include_cost: true
  include_metadata: true
  audit_trail: immutable       # Append-only, never delete

# Performance
performance:
  max_concurrent_extractions: 5
  database_pool_size: 10
  cache_entity_lookups: true
```

---

### 3. `entity_resolution_config.yaml`

**Location**: `config/entity_resolution_config.yaml`

**Purpose**: Fine-tune fuzzy matching algorithms

```yaml
# Entity Resolution Configuration
# Version: 1.0.0
# Last Updated: 2025-11-06

fuzzy_matching:
  algorithm: fuzzywuzzy         # "fuzzywuzzy" | "levenshtein" | "trigram"
  name_similarity:
    threshold: 0.90              # 90%+ = match
    use_token_sort: true         # "ACME Corp" = "Corp ACME"
    use_partial_ratio: false     # Partial substring matching
  address_similarity:
    threshold: 0.85              # 85%+ = match
    normalize:
      remove_punctuation: true
      lowercase: true
      expand_abbreviations: true  # "St" → "Street", "Ave" → "Avenue"

deduplication:
  strategies:
    - name: exact_match
      priority: 1
      matchers:
        - field: name
          exact: true
        - field: tax_id
          exact: true
    - name: high_confidence
      priority: 2
      matchers:
        - field: name
          fuzzy: true
          threshold: 0.95
        - field: address
          fuzzy: true
          threshold: 0.90
    - name: medium_confidence
      priority: 3
      matchers:
        - field: name
          fuzzy: true
          threshold: 0.85

manual_review_queue:
  enabled: true
  confidence_threshold: 0.80     # < 80% confidence → manual review
  queue_table: entity_review_queue
  notification: false            # Future: email admin

caching:
  enabled: true
  backend: memory                # "memory" | "redis"
  ttl_seconds: 3600              # 1 hour
  max_entries: 10000
```

---

### 4. `commitment_priority_config.yaml`

**Location**: `config/commitment_priority_config.yaml`

**Purpose**: Define priority calculation algorithm

```yaml
# Commitment Priority Calculation Configuration
# Version: 1.0.0
# Last Updated: 2025-11-06
# Algorithm: Weighted sum of factors (0-100 scale)

priority_weights:
  time_pressure: 0.30      # 30% weight
  severity: 0.25           # 25% weight
  amount: 0.15             # 15% weight
  effort: 0.15             # 15% weight
  dependency: 0.10         # 10% weight
  user_preference: 0.05    # 5% weight

# Time Pressure Factor (days until due)
time_pressure:
  scoring:
    - days_remaining: 0      # Overdue
      score: 100
    - days_remaining: 1      # Due today/tomorrow
      score: 95
    - days_remaining: 3      # Due in 3 days
      score: 85
    - days_remaining: 7      # Due in 1 week
      score: 70
    - days_remaining: 14     # Due in 2 weeks
      score: 50
    - days_remaining: 30     # Due in 1 month
      score: 30
    - days_remaining: 90     # Due in 3 months
      score: 10

# Severity Factor (domain-based risk)
severity:
  domains:
    Legal: 10                # Highest risk (lawsuits, compliance)
    Finance: 8               # High risk (late fees, credit)
    Health: 9                # Very high risk (medical urgency)
    Compliance: 10           # Regulatory requirements
    Admin: 5                 # Medium risk
    Personal: 3              # Low risk

# Amount Factor (logarithmic scale)
amount:
  thresholds:
    - min: 0
      max: 100
      score: 10
    - min: 100
      max: 1000
      score: 30
    - min: 1000
      max: 10000
      score: 60
    - min: 10000
      max: 100000
      score: 90
    - min: 100000
      max: null              # $100k+
      score: 100

# Effort Factor (estimated hours)
effort:
  scoring:
    - hours: 0.25            # < 15 minutes
      score: 10
    - hours: 1               # < 1 hour
      score: 30
    - hours: 4               # Half day
      score: 60
    - hours: 8               # Full day
      score: 80
    - hours: 16              # 2+ days
      score: 90

# Dependency Factor
dependency:
  has_blockers: 50           # If blocked by other commitments
  blocks_others: 80          # If blocking other commitments
  no_dependencies: 0         # Independent task

# User Preference
user_preference:
  flagged_important: 20      # User manually marked as important
  default: 0

# Reason String Template
reason_template: |
  {time_reason}{severity_reason}{amount_reason}

  # Examples:
  # "Due in 2 days, legal requirement, $12,419.83"
  # "Overdue, high financial risk"
  # "Due in 1 week, blocking 3 other tasks"
```

---

### 5. `storage_config.yaml`

**Location**: `config/storage_config.yaml`

**Purpose**: Configure document storage backends

```yaml
# Document Storage Configuration
# Version: 1.0.0
# Last Updated: 2025-11-06

# Active backend
active_backend: local        # "local" | "s3" | "gcs"

# Local Filesystem Backend (MVP)
local:
  base_path: ./data/documents
  directory_structure: flat  # "flat" | "nested"  (flat = all in one dir)
  filename_format: "{sha256}.{ext}"
  max_file_size_mb: 50
  allowed_mime_types:
    - application/pdf
    - image/png
    - image/jpeg
    - image/tiff
  permissions:
    mode: 0644               # Read/write for owner, read for group/others

# AWS S3 Backend (Future)
s3:
  bucket: local-assistant-documents
  region: us-east-1
  prefix: documents/         # S3 key prefix
  storage_class: STANDARD    # "STANDARD" | "INTELLIGENT_TIERING" | "GLACIER"
  encryption: AES256
  versioning: true           # Enable S3 versioning
  lifecycle_rules:
    transition_to_glacier_days: 90
    expire_days: null        # null = keep forever

# Google Cloud Storage Backend (Future)
gcs:
  bucket: local-assistant-documents
  prefix: documents/
  storage_class: STANDARD
  versioning: true

# Content Addressable Storage
content_addressable:
  enabled: true
  hash_algorithm: sha256     # "sha256" | "blake2b"
  dedupe_check: true         # Check if file exists before storing

# Cleanup
cleanup:
  orphaned_files:
    enabled: false           # Delete files not referenced in DB
    dry_run: true
    schedule: "0 2 * * 0"    # Weekly at 2 AM Sunday (cron)
```

---

## Prompt Configuration Files

### Prompt File Structure

Following brokerage project's pattern: `config/prompts/{service}/{prompt_name}_v{version}.yaml`

#### Example: `config/prompts/entity-resolution/vendor_matching_v1.0.0.yaml`

```yaml
# Prompt Configuration: Vendor Matching
# Service: entity-resolution
# Version: 1.0.0

name: vendor_matching
version: 1.0.0
description: Validate and merge vendor candidates from fuzzy matching

system_prompt: |
  You are an expert entity resolution system specializing in vendor matching and deduplication.
  Your task is to determine if two vendor records represent the same entity.

  Matching Criteria:
  - Name similarity (>90% = high confidence)
  - Address match (street, city, state)
  - Tax ID match (100% match if present)
  - Domain/website match

  Provide a clear yes/no decision with confidence score and reasoning.

user_prompt: |
  Determine if these vendor records are the same entity:

  **Candidate Vendor** (from document):
  - Name: {{ candidate_name }}
  - Address: {{ candidate_address }}
  - Tax ID: {{ candidate_tax_id }}

  **Existing Vendor** (from database):
  - Name: {{ existing_name }}
  - Address: {{ existing_address }}
  - Tax ID: {{ existing_tax_id }}

  Are these the same vendor?

output_schema:
  type: object
  required:
    - is_match
    - confidence
    - reasoning
    - recommended_action
  properties:
    is_match:
      type: boolean
      description: "True if same vendor, false otherwise"
    confidence:
      type: number
      description: "Confidence score (0.0-1.0)"
    reasoning:
      type: string
      description: "Detailed explanation for decision"
    recommended_action:
      type: string
      enum: ["merge", "create_new", "manual_review"]
    conflicts:
      type: array
      description: "List of conflicting fields (if any)"
      items:
        type: object
        properties:
          field:
            type: string
          candidate_value:
            type: string
          existing_value:
            type: string
  additionalProperties: false

variables:
  - name: candidate_name
    type: string
    required: true
    description: "Vendor name from document"
  - name: candidate_address
    type: string
    required: false
    description: "Vendor address from document"
  - name: candidate_tax_id
    type: string
    required: false
    description: "Vendor tax ID from document"
  - name: existing_name
    type: string
    required: true
    description: "Vendor name from database"
  - name: existing_address
    type: string
    required: false
    description: "Vendor address from database"
  - name: existing_tax_id
    type: string
    required: false
    description: "Vendor tax ID from database"

performance:
  target_latency_ms: 500
  target_accuracy: 0.95
  cost_per_call_usd: 0.001

metadata:
  created_date: 2025-11-06
  last_modified: 2025-11-06
  author: AI Dev Team
  changelog:
    - version: 1.0.0
      date: 2025-11-06
      changes: "Initial version"
```

---

## Configuration Loading (Python)

### Config Loader Base Class

**Location**: `lib/shared/local_assistant_shared/config/config_loader.py`

```python
"""
ConfigLoader - Base class for loading YAML configs with caching.

UNICORN Pattern: DRY config loading with type safety.
"""

import yaml
from pathlib import Path
from typing import TypeVar, Generic, Optional
from pydantic import BaseModel

T = TypeVar('T', bound=BaseModel)


class ConfigLoader(Generic[T]):
    """
    Type-safe YAML config loader with caching.

    Usage:
        class PipelineConfig(BaseModel):
            name: str
            version: str

        loader = ConfigLoader(PipelineConfig, "config/pipeline_config.yaml")
        config = loader.load()
        print(config.name)
    """

    def __init__(self, model_class: type[T], config_path: str):
        self.model_class = model_class
        self.config_path = Path(config_path)
        self._cache: Optional[T] = None

    def load(self, force_reload: bool = False) -> T:
        """
        Load config from YAML with caching.

        Args:
            force_reload: Bypass cache and reload from disk

        Returns:
            Validated config instance
        """
        if self._cache is not None and not force_reload:
            return self._cache

        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Config file not found: {self.config_path}"
            )

        with open(self.config_path, 'r') as f:
            data = yaml.safe_load(f)

        # Validate with Pydantic
        self._cache = self.model_class(**data)
        return self._cache

    def reload(self) -> T:
        """Force reload config (useful for hot reload in dev)."""
        return self.load(force_reload=True)
```

### Usage Example

```python
from local_assistant_shared.config import ConfigLoader
from pydantic import BaseModel


class DocumentIntelligenceConfig(BaseModel):
    pipeline: dict
    vision_extraction: dict
    entity_resolution: dict


# Load config
loader = ConfigLoader(
    DocumentIntelligenceConfig,
    "config/document_intelligence_config.yaml"
)
config = loader.load()

# Access config
print(f"Pipeline: {config.pipeline['name']} v{config.pipeline['version']}")
print(f"Fuzzy threshold: {config.entity_resolution['vendor_matching']['fuzzy_threshold']}")

# Hot reload in dev
if ENV == "development":
    config = loader.reload()
```

---

## Environment Variables

### `.env.example`

```bash
# ============================================
# Life Graph + Document Intelligence
# ============================================

# Database (PostgreSQL)
DATABASE_URL=postgresql://assistant:assistant@localhost:5433/assistant

# Document Storage
STORAGE_BACKEND=local  # "local" | "s3" | "gcs"
STORAGE_BASE_PATH=./data/documents
STORAGE_MAX_FILE_SIZE_MB=50

# Entity Resolution
ENTITY_FUZZY_THRESHOLD=0.90
ENTITY_CACHE_TTL_SECONDS=3600

# Commitment Priority
PRIORITY_TIME_WEIGHT=0.30
PRIORITY_SEVERITY_WEIGHT=0.25

# Prompts
PROMPTS_DIR=./config/prompts
PROMPTS_CACHE_TTL_SECONDS=3600

# AI Models (OpenAI)
OPENAI_API_KEY=sk-...
OPENAI_MAX_TOKENS=16384
OPENAI_TEMPERATURE=0.0

# Observability
LOG_LEVEL=INFO
STRUCTURED_LOGGING=true
PROMETHEUS_PORT=9090

# Cost Limits
COST_LIMIT_PER_DOCUMENT=0.10
COST_WARN_PER_DOCUMENT=0.05

# Application
ENVIRONMENT=development  # "development" | "staging" | "production"
```

---

## Config Validation

### Startup Validation Script

**Location**: `scripts/validate_config.py`

```python
#!/usr/bin/env python3
"""
Validate all configuration files at startup.

Usage:
    python scripts/validate_config.py
"""

import sys
from pathlib import Path
from local_assistant_shared.config import (
    ModelRegistry,
    ConfigLoader,
    PromptManager
)


def validate_configs():
    """Validate all config files and prompts."""
    errors = []

    # 1. Validate model registry
    try:
        registry = ModelRegistry()
        print(f"✅ Model Registry: {len(registry.list_all_models())} models loaded")
    except Exception as e:
        errors.append(f"❌ Model Registry: {e}")

    # 2. Validate pipeline config
    try:
        from config.models import DocumentIntelligenceConfig
        loader = ConfigLoader(DocumentIntelligenceConfig, "config/document_intelligence_config.yaml")
        config = loader.load()
        print(f"✅ Pipeline Config: {config.pipeline['name']} v{config.pipeline['version']}")
    except Exception as e:
        errors.append(f"❌ Pipeline Config: {e}")

    # 3. Validate prompts
    try:
        manager = PromptManager(backend="local", prompts_dir="config/prompts")
        prompts = manager.list_prompts()
        print(f"✅ Prompts: {len(prompts)} prompt files found")
    except Exception as e:
        errors.append(f"❌ Prompts: {e}")

    # 4. Report results
    if errors:
        print("\n❌ Configuration validation FAILED:")
        for error in errors:
            print(f"  {error}")
        sys.exit(1)
    else:
        print("\n✅ All configurations valid!")
        sys.exit(0)


if __name__ == "__main__":
    validate_configs()
```

---

## Hot Reload (Development)

### File Watcher

```python
# Watch config files for changes and reload
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class ConfigReloadHandler(FileSystemEventHandler):
    def __init__(self, loader: ConfigLoader):
        self.loader = loader

    def on_modified(self, event):
        if event.src_path.endswith('.yaml'):
            print(f"📝 Config changed: {event.src_path}")
            try:
                self.loader.reload()
                print("✅ Config reloaded successfully")
            except Exception as e:
                print(f"❌ Config reload failed: {e}")


# Usage in dev mode
if ENV == "development":
    observer = Observer()
    handler = ConfigReloadHandler(config_loader)
    observer.schedule(handler, path="config/", recursive=True)
    observer.start()
```

---

## Migration from Hardcoded Values

### Before (Hardcoded ❌)
```python
# services/document_intelligence/pipeline.py
FUZZY_THRESHOLD = 0.90  # BAD: Hardcoded magic number
MAX_FILE_SIZE = 50 * 1024 * 1024  # BAD: Buried in code
```

### After (Config-Driven ✅)
```python
# services/document_intelligence/pipeline.py
from local_assistant_shared.config import config

fuzzy_threshold = config.entity_resolution.vendor_matching.fuzzy_threshold
max_file_size = config.storage.local.max_file_size_mb * 1024 * 1024
```

---

## Summary

### Config Files Hierarchy
```
1. models_registry.yaml          # Shared (brokerage + local_assistant)
2. document_intelligence_config.yaml  # Pipeline orchestration
3. entity_resolution_config.yaml     # Fuzzy matching params
4. commitment_priority_config.yaml   # Priority algorithm
5. storage_config.yaml               # File storage backends
6. prompts/*.yaml                    # Versioned prompts (Jinja2 templates)
```

### Loading Order
```
1. Environment variables (.env)
2. Model registry (shared)
3. Pipeline configs (service-specific)
4. Prompts (lazy-loaded on first use)
```

### Key Benefits
- ✅ **DRY**: No hardcoded values in code
- ✅ **Versioned**: Semantic versioning for all prompts
- ✅ **Type-Safe**: Pydantic validation at load time
- ✅ **Observable**: Log all config loads
- ✅ **Testable**: Easy to mock configs in tests
- ✅ **Hot Reload**: Dev mode watches for changes

---

**Next Steps**: Review DATABASE_MIGRATION_PLAN.md for schema migration details.

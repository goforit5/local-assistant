# Agent Skills Documentation

**Source**: https://docs.claude.com/en/docs/claude-developer-platform/agent-skills

**Last Updated**: 2025-10-19

---

## Overview

Agent Skills is Anthropic's framework for giving Claude structured capabilities and tools. This subfolder contains documentation on using Agent Skills in the Brokerage Ensemble project.

## Documentation Files

1. **[Overview](01_overview.md)** - Core concepts, capabilities, and use cases
2. **[Quickstart](02_quickstart.md)** - Getting started guide with examples
3. **[Best Practices](03_best_practices.md)** - Recommended patterns and anti-patterns

## What are Agent Skills?

Agent Skills allow you to:
- Define structured tools/capabilities for Claude
- Enable Claude to interact with external systems
- Build multi-step agentic workflows
- Combine multiple skills for complex tasks

## Quick Navigation

### For New Users
1. Start with [Overview](01_overview.md) to understand core concepts
2. Follow [Quickstart](02_quickstart.md) to see working examples
3. Apply [Best Practices](03_best_practices.md) in implementation

### For Implementation
- **Code Patterns**: See Quickstart for copy-paste examples
- **Integration**: Check Best Practices for project-specific guidelines
- **API Calls**: Reference [Anthropic Messages API](../../anthropic_api_messages.md)

## Usage in Brokerage Ensemble

Agent Skills can be used for:
- **Document Processing**: Structured extraction from brokerage statements
- **Validation**: Multi-step verification workflows
- **Error Recovery**: Self-healing data extraction
- **Quality Assurance**: Automated checking with multiple tools

## Integration Points

**Our Infrastructure**:
- `APIClientManager` - Centralized Anthropic client initialization
- `AnthropicProvider` - Provider abstraction for Agent Skills
- `CostTracker` - Token and cost tracking for Agent Skills calls
- `ProviderFactory` - Factory pattern for provider creation

**Example**:
```python
from Sources.Core.APIClientManager import APIClientManager
from Sources.Providers.ProviderFactory import ProviderFactory

# Initialize infrastructure
api_manager = APIClientManager()
provider_factory = ProviderFactory(api_manager, cost_tracker)
anthropic_provider = provider_factory.get_provider('anthropic')

# Use Agent Skills via provider
# TODO: Add example once implemented
```

## Related Documentation

### Anthropic Platform
- **[Claude Developer Platform](../README.md)** - Platform overview
- **[Messages API](../../anthropic_api_messages.md)** - Core API reference
- **[Messages API Examples](../../anthropic_api_messages_examples.md)** - Code examples

### Project Documentation
- **[Testing Strategy](../../../../../Testing/TESTING_STRATEGY.md)** - Testing guidelines
- **[Provider Abstraction](../../../../../Sources/Providers/)** - Provider pattern

---

**Purpose**: These docs provide copy-paste patterns for implementing Agent Skills in our pipeline, ensuring consistency with our architecture and best practices.

**Maintained by**: Brokerage Ensemble Team

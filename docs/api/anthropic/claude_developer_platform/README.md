# Claude Developer Platform API Documentation

**Source**: https://docs.claude.com/en/docs/claude-developer-platform

**Last Updated**: 2025-10-19

---

## Overview

This folder contains documentation for the **Claude Developer Platform** - Anthropic's platform for building AI-powered applications with Claude.

The Claude Developer Platform provides:
- **Agent Skills**: Tools and capabilities for AI agents
- **Model Context Protocol (MCP)**: Standard for connecting AI to data sources
- **Messages API**: Core API for Claude interactions
- **Extended thinking**: Advanced reasoning capabilities

## Documentation Structure

### Agent Skills
- [Overview](agent_skills/01_overview.md) - Core concepts and capabilities
- [Quickstart](agent_skills/02_quickstart.md) - Getting started guide
- [Best Practices](agent_skills/03_best_practices.md) - Recommended patterns

### Model Context Protocol (MCP)
*Coming soon*

## Purpose

These documents serve as reference material for implementing Claude Developer Platform features in the Brokerage Ensemble project. The documentation includes:

- Official API patterns from Claude Docs
- Working code examples tested with Anthropic's APIs
- Implementation notes specific to our project
- Cross-references to related documentation

## Relationship to Other APIs

**Claude Developer Platform** is Anthropic's full developer platform that includes:
- Messages API (core API for Claude)
- Agent Skills (tools/capabilities framework)
- MCP (data source connections)
- Extended thinking (reasoning features)

This folder focuses on **platform-level features** that build on top of the core Messages API.

For lower-level API calls, see:
- [Anthropic Messages API](../anthropic_api_messages.md) - Core API patterns
- [OpenAI API](../../openai/) - Alternative provider
- [Google Gemini API](../../google/) - Alternative provider

## Usage Guidelines

When implementing Claude Developer Platform features:

1. **Start with Agent Skills Overview** - Understand capabilities
2. **Follow Quickstart** - Copy proven code patterns
3. **Apply Best Practices** - Avoid common pitfalls
4. **Reference Messages API** - For underlying API calls

**DO**:
- ✅ Copy working patterns from these docs
- ✅ Use Agent Skills for structured tool usage
- ✅ Follow Anthropic's recommended patterns
- ✅ Track costs via our CostTracker

**DON'T**:
- ❌ Improvise API patterns (use our docs)
- ❌ Skip error handling
- ❌ Ignore token limits
- ❌ Use deprecated patterns

## Related Documentation

### Anthropic
- **Messages API**: [../anthropic_api_messages.md](../anthropic_api_messages.md)
- **Messages API Examples**: [../anthropic_api_messages_examples.md](../anthropic_api_messages_examples.md)
- **Usage & Cost**: [../anthropic_api_usage_cost.md](../anthropic_api_usage_cost.md)

### Other Providers
- **OpenAI**: [../../openai/](../../openai/)
- **Google Gemini**: [../../google/](../../google/)

### Project Documentation
- **Provider Abstraction**: [../../../../Sources/Providers/](../../../../Sources/Providers/)
- **API Client Manager**: [../../../../Sources/Core/APIClientManager.py](../../../../Sources/Core/APIClientManager.py)

---

**Maintained by**: Brokerage Ensemble Team
**Last Updated**: 2025-10-19

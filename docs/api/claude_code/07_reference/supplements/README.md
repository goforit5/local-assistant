# Claude Code Reference Supplements

> **Community Research & Real-World Findings**

## About This Directory

This directory contains **community-contributed research, gotchas, and best practices** discovered through real-world usage of Claude Code. These are **NOT official Anthropic documentation** but represent practical findings from production use.

### Purpose

- **Document edge cases** not covered in official docs
- **Share solutions** to common problems
- **Provide battle-tested patterns** from real projects
- **Capture tribal knowledge** for the community

### How to Use

1. **Check official docs first**: [Claude Code Documentation](https://docs.claude.com/en/docs/claude-code)
2. **If stuck, check supplements**: Look for relevant gotchas/patterns here
3. **Contribute findings**: Add your own discoveries (see Contributing below)

## Available Supplements

### Slash Commands
- **[slash_commands_bash_execution_gotchas.md](slash_commands_bash_execution_gotchas.md)** - Command substitution security errors, executable vs documentation patterns

*More supplements to be added as we discover patterns worth sharing*

## Document Format

Each supplement follows this structure:

```markdown
---
type: supplement
category: [category-name]
title: [Clear descriptive title]
status: community-research | battle-tested | experimental
last_updated: YYYY-MM-DD
contributors: [Team/Individual names]
applies_to: [What feature this applies to]
---

# Title

> Community Research Note (Not Official Documentation)

## Problem
Clear description of the issue/gotcha

## Solution
Step-by-step solution with examples

## Best Practices
Recommended patterns

## Related Official Documentation
Links to relevant official docs
```

## Status Definitions

- **`community-research`**: Initial findings, use with caution, needs more validation
- **`battle-tested`**: Proven in production, multiple projects, safe to use
- **`experimental`**: Exploring solutions, may change, use at own risk
- **`deprecated`**: No longer relevant (official docs updated, or approach outdated)

## Contributing

### When to Create a Supplement

✅ **Good candidates:**
- Solved a problem not covered in official docs
- Discovered a non-obvious pattern
- Found a gotcha that wasted significant debugging time
- Identified a best practice from production experience

❌ **Not suitable:**
- Duplicates official documentation
- Personal preferences without technical justification
- Untested theories
- Project-specific configurations

### How to Contribute

1. **Create a new `.md` file** in this directory
2. **Follow the document format** above
3. **Include real examples** from your code
4. **Add to this README** under "Available Supplements"
5. **Keep it concise** - focus on the problem/solution
6. **Update `last_updated`** when you revise

### Quality Standards

- **Reproducible**: Others can replicate the problem/solution
- **Practical**: Based on real-world usage, not theory
- **Clear**: Easy to understand and apply
- **Referenced**: Links to official docs where relevant
- **Maintained**: Update if official docs change

## Relationship to Official Docs

### Official Claude Code Documentation
- **Source**: Anthropic
- **Authority**: Canonical reference
- **Coverage**: Comprehensive feature documentation
- **Link**: https://docs.claude.com/en/docs/claude-code

### These Supplements
- **Source**: Community practitioners
- **Authority**: Real-world experience
- **Coverage**: Gaps, gotchas, patterns
- **Link**: This directory

**Always check official docs first. Use supplements for edge cases and patterns.**

## Disclaimer

⚠️ **Important Notes:**

1. **Not Official**: These are community findings, not Anthropic documentation
2. **Use at Own Risk**: Test in your environment before production use
3. **May Become Outdated**: Claude Code evolves, supplements may need updates
4. **No Warranty**: Contributors provide information as-is
5. **Check Official Docs**: Always verify against current official documentation

## Feedback & Questions

If you find these supplements helpful or have suggestions:
- Open an issue in the project repository
- Contribute your own findings
- Report outdated information

---

**Maintained by**: HGMT Development Team & Community Contributors
**Started**: October 2025
**Philosophy**: Share knowledge, save debugging time, build better with Claude Code

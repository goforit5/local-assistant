---
type: supplement
category: slash-commands
title: Bash Command Execution Gotchas
status: community-research
last_updated: 2025-10-22
contributors: HGMT Team
applies_to: Custom Slash Commands
---

# Slash Commands: Bash Command Execution Gotchas

> **📝 Community Research Note**
>
> This is NOT official Claude Code documentation. These are findings from real-world usage and troubleshooting.
> Use at your own discretion.

## Problem: Command Substitution Security Errors

### Error Message

```
Error: Bash command permission check failed for pattern "!`command $(substitution)`":
Command contains $() command substitution
```

### Root Cause

Claude Code's security system prevents execution of bash commands with command substitution (`$()`, backticks) when they appear in slash command files with the `!` prefix.

**Why this happens:**
- The `!` prefix tells Claude to **execute** the command immediately when the slash command loads
- Commands with `$()` are flagged as potentially unsafe for auto-execution
- This is a security feature, not a bug

## Solution: Documentation vs Execution Pattern

### Pattern 1: Execute Commands (Use `!` Prefix)

**When to use:** You want Claude to run the command and use the output in context.

```markdown
---
allowed-tools: Bash(git:*), Bash(gh:*)
description: Git commit workflow
---

## Context

- Current branch: !`git branch --show-current`
- Git status: !`git status --short`
- Recent commits: !`git log --oneline -3`

## Task
Create a commit based on the above context.
```

**✅ Works for:** Simple commands without substitution
**❌ Fails for:** Commands with `$(...)` or complex pipes

---

### Pattern 2: Document Commands (Use Code Blocks)

**When to use:** You want to show what command to run, but NOT execute it automatically.

```markdown
---
description: Sprint workflow
---

## CI/CD Status Check

Run this command to check workflow status:

    gh run list --branch $(git branch --show-current) --limit 5 --json conclusion,name,createdAt -q '.[] | "\(.conclusion | ascii_upcase) - \(.name)"'

## Branch Protection Check

    gh api repos/$(gh repo view --json nameWithOwner -q .nameWithOwner)/branches/main/protection

## Next Steps
Based on the above information, Claude will determine next actions.
```

**✅ Works for:** Documentation, reference commands, complex substitutions
**❌ Not suitable for:** Commands you want executed immediately

## When To Use Each Approach

| Scenario | Use `!` Prefix | Use Code Blocks |
|----------|---------------|-----------------|
| Simple git commands | ✅ | ❌ |
| Commands with `$()` substitution | ❌ | ✅ |
| Reference documentation | ❌ | ✅ |
| Commands that need current context | ✅ | ❌ |
| Commands Claude should run later | ❌ | ✅ |
| Multi-line complex commands | ❌ | ✅ |

## Real-World Example

### ❌ This Will Fail

```markdown
### CI Status Check
!`gh run list --branch $(git branch --show-current) --limit 5`
```

**Error:** Command substitution blocked by security checks

---

### ✅ This Works (Documentation Approach)

```markdown
### CI Status Check

Check the current branch's workflow status:

    gh run list --branch $(git branch --show-current) --limit 5

Claude will review this and determine if the workflow needs attention.
```

**Why it works:** Code block is documentation, not executed by `!` prefix

---

### ✅ Alternative: Break Into Steps

```markdown
### CI Status Check

- Current branch: !`git branch --show-current`

Then run this command manually or via Claude:

    gh run list --branch BRANCH_NAME --limit 5
```

**Why it works:** Simple command executed, complex command documented

## Best Practices

### 1. **Executable Context Commands**
Use `!` prefix for simple, safe commands that provide context:
```markdown
- Current directory: !`pwd`
- Git status: !`git status --short`
- Recent commits: !`git log --oneline -5`
```

### 2. **Reference Documentation**
Use code blocks for complex commands with substitution:
```markdown
Check workflow status:

    gh run list --branch $(git branch --show-current) --limit 5
```

### 3. **Hybrid Approach**
Combine both for optimal workflow:
```markdown
## Current Context

- Branch: !`git branch --show-current`
- Status: !`git status --short`

## Commands to Run

Based on the context above, you may need to run:

    gh run list --branch $(git branch --show-current)
    gh pr checks
```

## Technical Details

### Why Command Substitution is Blocked

1. **Security**: `$()` can execute arbitrary commands
2. **Determinism**: Output may vary based on environment state
3. **Debugging**: Hard to trace what was executed
4. **Permissions**: May bypass permission checks

### Indented Code Block Format

Claude Code recognizes indented blocks (4 spaces or 1 tab) as documentation:

```markdown
This is regular text.

    This is a code block (4 spaces or 1 tab)
    Commands here are NOT executed automatically
    They serve as reference/documentation

Back to regular text.
```

### Frontmatter `allowed-tools` Still Required

Even with code blocks, declare tools in frontmatter:

```markdown
---
allowed-tools: Bash(git:*), Bash(gh:*), Read, Write
description: My workflow
---
```

This allows Claude to execute documented commands when appropriate.

## Troubleshooting

### "Command contains $() command substitution"
- **Fix:** Convert `!backticks` to indented code block
- **Example:** See Pattern 2 above

### "Permission denied for bash command"
- **Fix:** Add to `allowed-tools` in frontmatter
- **Example:** `allowed-tools: Bash(gh:*)`

### Command not executing when expected
- **Check:** Is it in a code block? Code blocks are documentation only
- **Fix:** Use `!backticks` if you want execution

### Getting outdated context
- **Issue:** Using code blocks means Claude doesn't have real-time data
- **Fix:** Use `!` prefix for context commands, code blocks for actions

## Related Official Documentation

- [Slash Commands Reference](/en/docs/claude-code/slash-commands)
- [IAM Permissions](/en/docs/claude-code/iam)
- [Bash Tool Usage](/en/docs/claude-code/tools#bash)

---

**Last Updated:** October 22, 2025
**Tested With:** Claude Code v1.0.124+
**Contributors:** HGMT Development Team
**Status:** Community Research (Not Official Documentation)

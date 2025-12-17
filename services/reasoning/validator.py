"""LogicValidator - Code and logic verification using o1-mini."""

from typing import Dict, List, Literal, Optional
from dataclasses import dataclass

from providers.openai_provider import OpenAIProvider
from providers.base import Message


@dataclass
class ValidationIssue:
    """Single validation issue."""
    severity: Literal["error", "warning", "info"]
    category: str
    description: str
    line_number: Optional[int] = None
    suggestion: Optional[str] = None


@dataclass
class ValidationResult:
    """Complete validation result."""
    is_valid: bool
    score: float  # 0.0 to 1.0
    issues: List[ValidationIssue]
    summary: str
    reasoning_tokens: int
    metadata: Dict[str, any]


class LogicValidator:
    """Code and logic verification using o1-mini reasoning."""

    def __init__(self, provider: OpenAIProvider, model: str = "o1-mini-2024-09-12"):
        self.provider = provider
        self.model = model

    async def verify_logic(
        self,
        code: str,
        requirements: str,
        reasoning_effort: Literal["low", "medium", "high"] = "high",
        max_tokens: int = 10000,
        language: Optional[str] = None
    ) -> ValidationResult:
        """Verify code logic against requirements.

        Args:
            code: Code to verify
            requirements: Requirements/specifications
            reasoning_effort: Reasoning depth
            max_tokens: Maximum output tokens
            language: Programming language (auto-detected if None)

        Returns:
            ValidationResult with issues and score
        """
        lang_hint = f" (Language: {language})" if language else ""

        prompt = f"""Verify this code against the requirements{lang_hint}:

REQUIREMENTS:
{requirements}

CODE:
```
{code}
```

Analyze thoroughly and provide:
1. Does the code correctly implement all requirements?
2. Logic errors, edge cases, or bugs
3. Security vulnerabilities
4. Performance issues
5. Code quality concerns

Format your response as:
VALID: [YES/NO]
SCORE: [0.0-1.0]

ISSUES:
[SEVERITY] [CATEGORY]: [description]
LINE: [line number if applicable]
SUGGESTION: [how to fix]

SUMMARY:
[Overall assessment]"""

        messages = [Message(role="user", content=prompt)]

        response = await self.provider.chat(
            messages=messages,
            model=self.model,
            max_tokens=max_tokens,
            temperature=1.0,
            reasoning_effort=reasoning_effort
        )

        # Parse response
        result = self._parse_validation_response(response.content)
        result.reasoning_tokens = response.usage.get("output_tokens", 0)
        result.metadata = {
            "reasoning_effort": reasoning_effort,
            "model": self.model,
            "cost": response.cost,
            "latency": response.latency,
            "language": language
        }

        return result

    async def verify_implementation(
        self,
        implementation: str,
        specification: str,
        reasoning_effort: Literal["low", "medium", "high"] = "high"
    ) -> ValidationResult:
        """Verify implementation matches specification.

        Args:
            implementation: Code implementation
            specification: Expected behavior/spec
            reasoning_effort: Reasoning depth

        Returns:
            ValidationResult
        """
        return await self.verify_logic(
            code=implementation,
            requirements=specification,
            reasoning_effort=reasoning_effort
        )

    async def find_bugs(
        self,
        code: str,
        reasoning_effort: Literal["low", "medium", "high"] = "high",
        context: Optional[str] = None
    ) -> ValidationResult:
        """Find potential bugs in code.

        Args:
            code: Code to analyze
            reasoning_effort: Reasoning depth
            context: Optional additional context

        Returns:
            ValidationResult with potential bugs
        """
        context_section = f"\nCONTEXT:\n{context}\n" if context else ""

        requirements = f"""{context_section}
Find all potential bugs, logic errors, edge cases, security issues, and quality concerns in this code.
Consider: null/undefined handling, type safety, race conditions, resource leaks, error handling, boundary conditions."""

        return await self.verify_logic(
            code=code,
            requirements=requirements,
            reasoning_effort=reasoning_effort
        )

    def _parse_validation_response(self, response: str) -> ValidationResult:
        """Parse o1-mini validation response."""
        is_valid = False
        score = 0.0
        issues = []
        summary = ""

        current_issue = None
        in_summary = False
        summary_lines = []

        for line in response.split("\n"):
            line = line.strip()

            if line.startswith("VALID:"):
                is_valid = "YES" in line.upper()

            elif line.startswith("SCORE:"):
                try:
                    score = float(line.replace("SCORE:", "").strip())
                except ValueError:
                    score = 0.0

            elif line.startswith("SUMMARY:"):
                in_summary = True
                continue

            elif in_summary:
                if line:
                    summary_lines.append(line)

            elif line.startswith("[") and "]" in line:
                # Parse issue: [SEVERITY] CATEGORY: description
                if current_issue:
                    issues.append(current_issue)

                parts = line.split("]", 1)
                severity = parts[0].replace("[", "").strip().lower()

                if severity not in ["error", "warning", "info"]:
                    severity = "warning"

                remainder = parts[1].strip() if len(parts) > 1 else ""

                if ":" in remainder:
                    category, description = remainder.split(":", 1)
                    category = category.strip()
                    description = description.strip()
                else:
                    category = "general"
                    description = remainder

                current_issue = {
                    "severity": severity,
                    "category": category,
                    "description": description,
                    "line_number": None,
                    "suggestion": None
                }

            elif current_issue:
                if line.startswith("LINE:"):
                    try:
                        current_issue["line_number"] = int(
                            line.replace("LINE:", "").strip()
                        )
                    except ValueError:
                        pass

                elif line.startswith("SUGGESTION:"):
                    current_issue["suggestion"] = line.replace("SUGGESTION:", "").strip()

        # Add final issue
        if current_issue:
            issues.append(current_issue)

        summary = " ".join(summary_lines) if summary_lines else "Validation complete."

        return ValidationResult(
            is_valid=is_valid,
            score=score,
            issues=[
                ValidationIssue(
                    severity=i["severity"],
                    category=i["category"],
                    description=i["description"],
                    line_number=i["line_number"],
                    suggestion=i["suggestion"]
                )
                for i in issues
            ],
            summary=summary,
            reasoning_tokens=0,  # Set by caller
            metadata={}  # Set by caller
        )

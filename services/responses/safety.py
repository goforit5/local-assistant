"""Safety checker for computer use actions with domain filtering and malicious detection."""

import re
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from enum import Enum
import yaml


class SafetyLevel(Enum):
    """Safety check result levels."""
    ALLOWED = "allowed"
    WARNING = "warning"
    BLOCKED = "blocked"


@dataclass
class SafetyCheck:
    """Result of a safety check."""
    level: SafetyLevel
    passed: bool
    reason: str
    check_type: str
    requires_acknowledgment: bool = False


class SafetyChecker:
    """Validates computer use actions against safety policies."""

    def __init__(self, config_path: str = None, config_dict: Dict = None):
        """Initialize safety checker.

        Args:
            config_path: Path to computer_use.yaml config file
            config_dict: Or provide config as dictionary
        """
        self.config = self._load_config(config_path, config_dict)
        self.allowed_domains = self._compile_domain_patterns(
            self.config.get("safety", {}).get("allowed_domains", [])
        )
        self.blocked_domains = self._compile_domain_patterns(
            self.config.get("safety", {}).get("blocked_domains", [])
        )
        self.sensitive_domains = self._compile_domain_patterns(
            self.config.get("safety", {}).get("sensitive_domains", [])
        )
        self.blocked_actions = set(
            self.config.get("safety", {}).get("blocked_actions", [])
        )
        self.require_confirmation = set(
            self.config.get("safety", {}).get("require_confirmation", [])
        )

    def _load_config(
        self,
        config_path: Optional[str],
        config_dict: Optional[Dict]
    ) -> Dict:
        """Load configuration from file or dict.

        Args:
            config_path: Path to YAML config
            config_dict: Config dictionary

        Returns:
            Configuration dictionary
        """
        if config_dict:
            return config_dict

        if config_path:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)

        # Default minimal config
        return {
            "safety": {
                "enabled": True,
                "allowed_domains": ["*"],
                "blocked_domains": [],
                "sensitive_domains": [],
                "blocked_actions": [],
                "require_confirmation": [],
            }
        }

    def _compile_domain_patterns(self, domains: List[str]) -> List[re.Pattern]:
        """Compile domain patterns into regex.

        Args:
            domains: List of domain patterns (supports wildcards)

        Returns:
            List of compiled regex patterns
        """
        patterns = []
        for domain in domains:
            # Convert wildcard pattern to regex
            # *.example.com -> ^.*\.example\.com$
            pattern = domain.replace(".", r"\.")
            pattern = pattern.replace("*", ".*")
            pattern = f"^{pattern}$"
            patterns.append(re.compile(pattern, re.IGNORECASE))
        return patterns

    def check_domain(self, url: str) -> SafetyCheck:
        """Check if URL domain is allowed.

        Args:
            url: URL to check

        Returns:
            SafetyCheck result
        """
        if not self.config.get("safety", {}).get("enabled", True):
            return SafetyCheck(
                level=SafetyLevel.ALLOWED,
                passed=True,
                reason="Safety checks disabled",
                check_type="domain"
            )

        domain = self._extract_domain(url)

        # Check blocked domains first
        if self._matches_any_pattern(domain, self.blocked_domains):
            return SafetyCheck(
                level=SafetyLevel.BLOCKED,
                passed=False,
                reason=f"Domain '{domain}' is blocked",
                check_type="domain",
                requires_acknowledgment=True
            )

        # Check sensitive domains
        if self._matches_any_pattern(domain, self.sensitive_domains):
            return SafetyCheck(
                level=SafetyLevel.WARNING,
                passed=True,
                reason=f"Domain '{domain}' is sensitive (financial/auth)",
                check_type="domain",
                requires_acknowledgment=True
            )

        # Check allowed domains
        if self.allowed_domains:
            if self._matches_any_pattern(domain, self.allowed_domains):
                return SafetyCheck(
                    level=SafetyLevel.ALLOWED,
                    passed=True,
                    reason=f"Domain '{domain}' is allowed",
                    check_type="domain"
                )
            else:
                return SafetyCheck(
                    level=SafetyLevel.BLOCKED,
                    passed=False,
                    reason=f"Domain '{domain}' not in allowlist",
                    check_type="domain",
                    requires_acknowledgment=True
                )

        # No restrictions, allow by default
        return SafetyCheck(
            level=SafetyLevel.ALLOWED,
            passed=True,
            reason="No domain restrictions configured",
            check_type="domain"
        )

    def check_action(
        self,
        action_type: str,
        action_details: Optional[Dict] = None
    ) -> SafetyCheck:
        """Check if action is allowed.

        Args:
            action_type: Type of action (e.g., 'click', 'type', 'scroll')
            action_details: Additional action context

        Returns:
            SafetyCheck result
        """
        if not self.config.get("safety", {}).get("enabled", True):
            return SafetyCheck(
                level=SafetyLevel.ALLOWED,
                passed=True,
                reason="Safety checks disabled",
                check_type="action"
            )

        # Check blocked actions
        if action_type in self.blocked_actions:
            return SafetyCheck(
                level=SafetyLevel.BLOCKED,
                passed=False,
                reason=f"Action '{action_type}' is blocked",
                check_type="action",
                requires_acknowledgment=True
            )

        # Check actions requiring confirmation
        if action_type in self.require_confirmation:
            return SafetyCheck(
                level=SafetyLevel.WARNING,
                passed=True,
                reason=f"Action '{action_type}' requires confirmation",
                check_type="action",
                requires_acknowledgment=True
            )

        return SafetyCheck(
            level=SafetyLevel.ALLOWED,
            passed=True,
            reason=f"Action '{action_type}' is allowed",
            check_type="action"
        )

    def check_text_input(self, text: str) -> SafetyCheck:
        """Check if text input contains malicious patterns.

        Args:
            text: Text to check

        Returns:
            SafetyCheck result
        """
        if not self.config.get("safety", {}).get("enabled", True):
            return SafetyCheck(
                level=SafetyLevel.ALLOWED,
                passed=True,
                reason="Safety checks disabled",
                check_type="text_input"
            )

        # Check for SQL injection patterns
        sql_patterns = [
            r"';?\s*(DROP|DELETE|INSERT|UPDATE|SELECT)\s+",
            r"--",
            r"/\*.*\*/",
            r"UNION\s+SELECT",
        ]

        for pattern in sql_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return SafetyCheck(
                    level=SafetyLevel.WARNING,
                    passed=True,
                    reason="Text contains SQL-like patterns",
                    check_type="text_input",
                    requires_acknowledgment=True
                )

        # Check for XSS patterns
        xss_patterns = [
            r"<script[^>]*>",
            r"javascript:",
            r"onerror\s*=",
            r"onclick\s*=",
        ]

        for pattern in xss_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return SafetyCheck(
                    level=SafetyLevel.WARNING,
                    passed=True,
                    reason="Text contains script-like patterns",
                    check_type="text_input",
                    requires_acknowledgment=True
                )

        return SafetyCheck(
            level=SafetyLevel.ALLOWED,
            passed=True,
            reason="Text input is safe",
            check_type="text_input"
        )

    def check_screenshot_content(
        self,
        screenshot_analysis: str
    ) -> SafetyCheck:
        """Check screenshot for malicious or adversarial content.

        Args:
            screenshot_analysis: LLM analysis of screenshot content

        Returns:
            SafetyCheck result
        """
        if not self.config.get("safety", {}).get("enabled", True):
            return SafetyCheck(
                level=SafetyLevel.ALLOWED,
                passed=True,
                reason="Safety checks disabled",
                check_type="screenshot"
            )

        # Keywords indicating potential issues
        malicious_keywords = [
            "phishing",
            "malware",
            "ransomware",
            "credential theft",
            "fake login",
            "scam",
            "fraudulent",
        ]

        analysis_lower = screenshot_analysis.lower()

        for keyword in malicious_keywords:
            if keyword in analysis_lower:
                return SafetyCheck(
                    level=SafetyLevel.BLOCKED,
                    passed=False,
                    reason=f"Screenshot may contain malicious content: {keyword}",
                    check_type="screenshot",
                    requires_acknowledgment=True
                )

        return SafetyCheck(
            level=SafetyLevel.ALLOWED,
            passed=True,
            reason="Screenshot appears safe",
            check_type="screenshot"
        )

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL.

        Args:
            url: Full URL

        Returns:
            Domain string
        """
        # Simple domain extraction
        # Remove protocol
        domain = re.sub(r'^https?://', '', url)
        # Remove path and query
        domain = domain.split('/')[0]
        domain = domain.split('?')[0]
        # Remove port
        domain = domain.split(':')[0]
        return domain

    def _matches_any_pattern(
        self,
        domain: str,
        patterns: List[re.Pattern]
    ) -> bool:
        """Check if domain matches any pattern.

        Args:
            domain: Domain to check
            patterns: List of regex patterns

        Returns:
            True if matches any pattern
        """
        return any(pattern.match(domain) for pattern in patterns)

    def get_safety_summary(self) -> Dict:
        """Get summary of safety configuration.

        Returns:
            Dictionary with safety settings
        """
        return {
            "enabled": self.config.get("safety", {}).get("enabled", True),
            "allowed_domains_count": len(self.allowed_domains),
            "blocked_domains_count": len(self.blocked_domains),
            "sensitive_domains_count": len(self.sensitive_domains),
            "blocked_actions": list(self.blocked_actions),
            "require_confirmation": list(self.require_confirmation),
        }

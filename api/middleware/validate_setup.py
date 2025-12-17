#!/usr/bin/env python3
"""Validation script for rate limiting setup.

Run this script to verify all components are correctly configured.
"""

import os
import sys
from pathlib import Path

# Colors for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'


def check_file(path: str, description: str) -> bool:
    """Check if file exists."""
    if Path(path).exists():
        print(f"{GREEN}✓{RESET} {description}: {path}")
        return True
    else:
        print(f"{RED}✗{RESET} {description}: {path} NOT FOUND")
        return False


def check_env_var(var: str, description: str) -> bool:
    """Check if environment variable exists."""
    value = os.getenv(var)
    if value:
        masked_value = value[:10] + "..." if len(value) > 10 else value
        print(f"{GREEN}✓{RESET} {description}: {masked_value}")
        return True
    else:
        print(f"{YELLOW}⚠{RESET} {description}: Not set (will use default)")
        return False


def validate_yaml_syntax(path: str) -> bool:
    """Validate YAML file syntax."""
    try:
        import yaml
        with open(path, 'r') as f:
            yaml.safe_load(f)
        print(f"{GREEN}✓{RESET} YAML syntax valid: {path}")
        return True
    except Exception as e:
        print(f"{RED}✗{RESET} YAML syntax error in {path}: {e}")
        return False


def check_redis_connection() -> bool:
    """Check Redis connection."""
    try:
        import redis.asyncio as redis
        import asyncio

        async def test_redis():
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            if "localhost:6379" in redis_url:
                redis_url = redis_url.replace("localhost:6379", "localhost:6380")

            client = await redis.from_url(redis_url, encoding="utf-8", decode_responses=True)
            result = await client.ping()
            await client.close()
            return result

        result = asyncio.run(test_redis())
        if result:
            print(f"{GREEN}✓{RESET} Redis connection successful")
            return True
    except Exception as e:
        print(f"{RED}✗{RESET} Redis connection failed: {e}")
        print(f"{YELLOW}  → Make sure Redis is running: docker-compose up -d redis{RESET}")
        return False


def main():
    """Run all validation checks."""
    print("=" * 80)
    print("RATE LIMITING SETUP VALIDATION")
    print("=" * 80)

    base_dir = Path(__file__).parent.parent.parent
    checks = []

    print("\n1. Checking files...")
    checks.append(check_file(
        str(base_dir / "api/middleware/rate_limit.py"),
        "Rate limiting middleware"
    ))
    checks.append(check_file(
        str(base_dir / "config/rate_limits.yaml"),
        "Rate limits configuration"
    ))
    checks.append(check_file(
        str(base_dir / "api/middleware/__init__.py"),
        "Middleware package marker"
    ))
    checks.append(check_file(
        str(base_dir / "tests/test_rate_limit.py"),
        "Test suite"
    ))

    print("\n2. Checking dependencies...")
    try:
        import redis
        print(f"{GREEN}✓{RESET} redis package installed")
        checks.append(True)
    except ImportError:
        print(f"{RED}✗{RESET} redis package not installed")
        print(f"{YELLOW}  → Run: pip install redis>=5.0.0{RESET}")
        checks.append(False)

    try:
        import yaml
        print(f"{GREEN}✓{RESET} pyyaml package installed")
        checks.append(True)
    except ImportError:
        print(f"{RED}✗{RESET} pyyaml package not installed")
        print(f"{YELLOW}  → Run: pip install pyyaml>=6.0.0{RESET}")
        checks.append(False)

    try:
        from fastapi.middleware.cors import CORSMiddleware
        print(f"{GREEN}✓{RESET} fastapi package installed")
        checks.append(True)
    except ImportError:
        print(f"{RED}✗{RESET} fastapi package not installed")
        checks.append(False)

    print("\n3. Checking environment...")
    check_env_var("REDIS_URL", "Redis URL")

    print("\n4. Validating configuration...")
    if Path(base_dir / "config/rate_limits.yaml").exists():
        checks.append(validate_yaml_syntax(str(base_dir / "config/rate_limits.yaml")))

    print("\n5. Testing Redis connection...")
    checks.append(check_redis_connection())

    print("\n6. Checking .env file...")
    env_path = base_dir / ".env"
    if env_path.exists():
        print(f"{GREEN}✓{RESET} .env file exists")
        with open(env_path, 'r') as f:
            content = f.read()
            if "REDIS_URL" in content:
                print(f"{GREEN}✓{RESET} REDIS_URL defined in .env")
            else:
                print(f"{YELLOW}⚠{RESET} REDIS_URL not in .env (will use default)")
    else:
        print(f"{RED}✗{RESET} .env file not found")

    print("\n" + "=" * 80)
    passed = sum(checks)
    total = len(checks)

    if passed == total:
        print(f"{GREEN}ALL CHECKS PASSED ({passed}/{total}){RESET}")
        print("\nNext steps:")
        print("1. Integrate middleware into api/main.py:")
        print("   from api.middleware.rate_limit import RateLimitMiddleware, get_redis_url")
        print("   app.add_middleware(RateLimitMiddleware, redis_url=get_redis_url())")
        print("\n2. Start application: uvicorn api.main:app --reload")
        print("\n3. Test: curl -v http://localhost:8000/api/health")
        return 0
    else:
        print(f"{RED}SOME CHECKS FAILED ({passed}/{total} passed){RESET}")
        print("\nPlease fix the issues above before proceeding.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

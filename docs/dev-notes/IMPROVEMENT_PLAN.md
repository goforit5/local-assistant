# 🦄 Unicorn-Grade Improvement Plan
**Making Local Assistant Production-Ready with DRY Principles**

---

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [DRY Principles Applied](#dry-principles-applied)
3. [Phase 1: Critical Changes](#phase-1-critical-changes)
4. [Phase 2: High Priority](#phase-2-high-priority)
5. [Phase 3: Medium Priority](#phase-3-medium-priority)
6. [Phase 4: Low Priority](#phase-4-low-priority)
7. [Implementation Roadmap](#implementation-roadmap)
8. [Before/After Examples](#beforeafter-examples)
9. [Validation Criteria](#validation-criteria)

---

## Executive Summary

### Current State
- **Completion**: ~90% (excellent foundation)
- **Code Quality**: High (clean architecture, type hints, async)
- **Main Gaps**: Testing, security hardening, performance optimization

### Target State
- **Completion**: 100% production-ready
- **DRY Score**: Eliminate 80%+ code duplication
- **Test Coverage**: 85%+
- **Security**: JWT auth, rate limiting, secrets management
- **Performance**: Redis caching, query optimization, <200ms p95 latency

### Estimated Effort
- **Phase 1 (Critical)**: 52 hours (~1.5 weeks)
- **Phase 2 (High)**: 48 hours (~1.5 weeks)
- **Phase 3 (Medium)**: 36 hours (~1 week)
- **Phase 4 (Low)**: 24 hours (~3 days)
- **Total**: 160 hours (~4 weeks for complete unicorn status)

---

## DRY Principles Applied

### What is DRY?
**Don't Repeat Yourself** - Every piece of knowledge should have a single, unambiguous, authoritative representation.

### Current Violations (To Fix)

#### 1. **Configuration Duplication**
**Problem**: Each service loads its own YAML files independently
```python
# Currently repeated in multiple files:
vision_config = yaml.safe_load(open("config/vision_config.yaml"))
computer_config = yaml.safe_load(open("config/computer_use.yaml"))
```

**Solution**: Single configuration loader
```python
# New centralized approach:
from lib.shared.local_assistant_shared.config import get_config

config = get_config()  # Loads ALL configs once at startup
vision_settings = config.vision
computer_settings = config.computer_use
```

#### 2. **Provider Initialization Duplication**
**Problem**: Each provider has custom initialization logic
```python
# Currently in api/main.py:
anthropic = AnthropicProvider(ProviderConfig(api_key=os.getenv("ANTHROPIC_API_KEY")))
openai = OpenAIProvider(ProviderConfig(api_key=os.getenv("OPENAI_API_KEY")))
google = GoogleProvider(ProviderConfig(api_key=os.getenv("GOOGLE_API_KEY")))
```

**Solution**: Factory pattern
```python
# New approach:
from providers.factory import create_provider

anthropic = create_provider("anthropic")  # Reads from config
openai = create_provider("openai")
google = create_provider("google")
```

#### 3. **Hardcoded String Literals**
**Problem**: Status values, error messages, constants scattered everywhere
```python
# Currently:
signal.status = "processing"
if commitment.state == "pending":
error_msg = "Document extraction failed"
```

**Solution**: Centralized constants and enums
```python
# New approach:
from lib.shared.local_assistant_shared.enums import SignalStatus, CommitmentState
from lib.shared.local_assistant_shared.messages import ErrorMessages

signal.status = SignalStatus.PROCESSING
if commitment.state == CommitmentState.PENDING:
error_msg = ErrorMessages.EXTRACTION_FAILED
```

#### 4. **Validation Logic Duplication**
**Problem**: File validation repeated in multiple routes
```python
# Currently in api/routes/vision.py and api/routes/documents.py:
if not file.filename.endswith(('.pdf', '.png', '.jpg')):
    raise ValueError("Invalid file type")
if file.size > 25 * 1024 * 1024:
    raise ValueError("File too large")
```

**Solution**: Reusable validator service
```python
# New approach:
from services.validation import FileValidator

validator = FileValidator.from_config()
validator.validate(file)  # Raises ValidationError if invalid
```

#### 5. **Error Response Duplication**
**Problem**: Different error formats per endpoint
```python
# Currently:
return {"error": "something failed"}  # Some endpoints
raise HTTPException(status_code=400, detail="error")  # Other endpoints
return JSONResponse({"message": "error"}, status_code=500)  # Yet others
```

**Solution**: Standardized error model
```python
# New approach:
from api.models.errors import ErrorResponse

raise ErrorResponse(
    code="ERR_VISION_001",
    message="Document extraction failed",
    details=str(e),
    request_id=request_id
)
```

#### 6. **Cache Key Construction Duplication**
**Problem**: Manual cache key building everywhere
```python
# Currently:
cache_key = f"vendor:{vendor_name}:{tax_id}"
cache_key = f"document:extraction:{sha256}"
cache_key = f"commitment:{user_id}:{role_id}"
```

**Solution**: Centralized cache key builder
```python
# New approach:
from memory.cache_keys import CacheKeys

key = CacheKeys.vendor_lookup(name=vendor_name, tax_id=tax_id)
key = CacheKeys.document_extraction(sha256=sha256)
key = CacheKeys.commitment(user_id=user_id, role_id=role_id)
```

---

## Phase 1: Critical Changes

**Estimated Time**: 52 hours (~1.5 weeks)
**Must complete before production deployment**

### 1.1 Security Hardening (16 hours)

#### SEC-001: JWT Authentication
**Why**: Currently no authentication - anyone can access API

**Implementation**:
```python
# File: api/auth/jwt.py
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext

class JWTManager:
    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.pwd_context = CryptContext(schemes=["bcrypt"])

    def create_token(self, user_id: str, expires_hours: int = 24) -> str:
        expire = datetime.utcnow() + timedelta(hours=expires_hours)
        return jwt.encode(
            {"sub": user_id, "exp": expire},
            self.secret_key,
            algorithm=self.algorithm
        )

    def verify_token(self, token: str) -> str:
        """Returns user_id if valid, raises JWTError if invalid"""
        payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
        return payload["sub"]
```

**Middleware**:
```python
# File: api/auth/middleware.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    """Dependency to get current user from JWT token"""
    try:
        jwt_manager = get_jwt_manager()  # From config
        user_id = jwt_manager.verify_token(credentials.credentials)
        return user_id
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )
```

**Usage in routes**:
```python
# File: api/routes/documents.py
from api.auth.middleware import get_current_user

@router.post("/upload")
async def upload_document(
    file: UploadFile,
    user_id: str = Depends(get_current_user)  # Add this to EVERY protected route
):
    # Now user_id is authenticated
    ...
```

**Config**:
```yaml
# File: config/auth.yaml
jwt:
  algorithm: HS256
  expiration_hours: 24
  secret_key: ${JWT_SECRET_KEY}  # From environment

# In .env:
JWT_SECRET_KEY=your-super-secret-key-change-in-production
```

---

#### SEC-002: Rate Limiting
**Why**: Prevent API abuse and DOS attacks

**Implementation**:
```python
# File: api/middleware/rate_limit.py
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="redis://localhost:6380"  # From config
)

# In api/main.py:
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Per-endpoint usage:
@router.post("/chat")
@limiter.limit("20/minute")  # 20 requests per minute per IP
async def chat(request: Request, ...):
    ...
```

**Config-driven approach** (DRY):
```yaml
# File: config/rate_limits.yaml
global:
  requests_per_minute: 100
  requests_per_hour: 1000

endpoints:
  /api/chat:
    rpm: 20
    rph: 200

  /api/vision/extract:
    rpm: 10  # Expensive operation
    rph: 50

  /api/reasoning/solve:
    rpm: 5
    rph: 20
```

**Load limits from config**:
```python
# File: api/middleware/rate_limit.py
from lib.shared.local_assistant_shared.config import get_config

config = get_config()

def get_rate_limit(endpoint: str) -> str:
    """Get rate limit for endpoint from config"""
    limits = config.rate_limits.endpoints.get(endpoint)
    if limits:
        return f"{limits['rpm']}/minute;{limits['rph']}/hour"
    return f"{config.rate_limits.global.rpm}/minute"

# Usage:
@router.post("/chat")
@limiter.limit(get_rate_limit("/api/chat"))
async def chat(...):
    ...
```

---

#### SEC-003: Secrets Management
**Why**: API keys in .env files are not secure for production

**Implementation**:
```python
# File: lib/shared/local_assistant_shared/secrets/manager.py
from abc import ABC, abstractmethod
from typing import Dict, Optional

class SecretsProvider(ABC):
    @abstractmethod
    async def get_secret(self, key: str) -> Optional[str]:
        pass

    @abstractmethod
    async def get_secrets(self, prefix: str) -> Dict[str, str]:
        pass

class EnvSecretsProvider(SecretsProvider):
    """Load from environment variables (dev/local)"""
    async def get_secret(self, key: str) -> Optional[str]:
        return os.getenv(key)

class AWSSecretsProvider(SecretsProvider):
    """Load from AWS Secrets Manager (production)"""
    def __init__(self, region: str, secret_name: str):
        self.client = boto3.client('secretsmanager', region_name=region)
        self.secret_name = secret_name
        self._cache = {}

    async def get_secret(self, key: str) -> Optional[str]:
        if not self._cache:
            response = self.client.get_secret_value(SecretId=self.secret_name)
            self._cache = json.loads(response['SecretString'])
        return self._cache.get(key)

class VaultSecretsProvider(SecretsProvider):
    """Load from HashiCorp Vault"""
    def __init__(self, url: str, token: str, path: str):
        self.client = hvac.Client(url=url, token=token)
        self.path = path

    async def get_secret(self, key: str) -> Optional[str]:
        response = self.client.secrets.kv.v2.read_secret_version(path=self.path)
        return response['data']['data'].get(key)

# Factory:
def create_secrets_provider(config) -> SecretsProvider:
    provider_type = config.secrets.provider
    if provider_type == "env":
        return EnvSecretsProvider()
    elif provider_type == "aws_secrets":
        return AWSSecretsProvider(
            region=config.secrets.aws_secrets.region,
            secret_name=config.secrets.aws_secrets.secret_name
        )
    elif provider_type == "vault":
        return VaultSecretsProvider(
            url=config.secrets.vault.url,
            token=os.getenv("VAULT_TOKEN"),
            path=config.secrets.vault.path
        )
    else:
        raise ValueError(f"Unknown secrets provider: {provider_type}")
```

**Usage** (replaces all `os.getenv()` calls):
```python
# Old way:
anthropic_key = os.getenv("ANTHROPIC_API_KEY")

# New way:
secrets = get_secrets_provider()
anthropic_key = await secrets.get_secret("ANTHROPIC_API_KEY")
```

**Config**:
```yaml
# File: config/secrets.yaml
provider: env  # env, aws_secrets, vault

aws_secrets:
  region: us-west-2
  secret_name: local-assistant/prod/api-keys

vault:
  url: https://vault.company.com:8200
  path: secret/local-assistant
```

---

#### SEC-004: File Upload Validation
**Why**: Prevent malicious file uploads

**Implementation**:
```python
# File: services/validation/file_validator.py
import magic  # python-magic for mime detection

class FileValidator:
    def __init__(self, config):
        self.max_size_bytes = config.max_file_size_mb * 1024 * 1024
        self.allowed_mime_types = set(config.allowed_mime_types)
        self.magic_bytes_validation = config.magic_bytes_validation

    def validate(self, file: UploadFile) -> None:
        """Validate file, raise ValidationError if invalid"""
        # 1. Size check
        file.file.seek(0, 2)  # Seek to end
        size = file.file.tell()
        file.file.seek(0)  # Reset

        if size > self.max_size_bytes:
            raise ValidationError(
                f"File too large: {size} bytes (max: {self.max_size_bytes})"
            )

        # 2. Magic bytes check (true MIME type)
        if self.magic_bytes_validation:
            mime = magic.from_buffer(file.file.read(2048), mime=True)
            file.file.seek(0)

            if mime not in self.allowed_mime_types:
                raise ValidationError(
                    f"Invalid file type: {mime} (allowed: {self.allowed_mime_types})"
                )

        # 3. Extension check
        ext = file.filename.split('.')[-1].lower()
        if not self._is_valid_extension(ext):
            raise ValidationError(f"Invalid extension: {ext}")

        # 4. PDF structure validation (if PDF)
        if mime == "application/pdf":
            self._validate_pdf_structure(file)

    def _validate_pdf_structure(self, file: UploadFile):
        """Check if PDF is valid (not corrupted)"""
        try:
            pdf = pypdf.PdfReader(file.file)
            _ = len(pdf.pages)  # Try to read pages
            file.file.seek(0)
        except Exception as e:
            raise ValidationError(f"Invalid PDF structure: {e}")
```

**Config**:
```yaml
# File: config/file_validation.yaml
max_file_size_mb: 25
allowed_mime_types:
  - application/pdf
  - image/png
  - image/jpeg
  - image/jpg
magic_bytes_validation: true
virus_scan_enabled: false  # Optional ClamAV integration
```

**Usage** (DRY - single validator for all routes):
```python
# In any route:
from services.validation import get_file_validator

validator = get_file_validator()

@router.post("/upload")
async def upload(file: UploadFile):
    validator.validate(file)  # Raises ValidationError if invalid
    # Continue with processing...
```

---

### 1.2 Testing Foundation (24 hours)

#### TEST-001: Unit Tests for Services
**Why**: Currently minimal test coverage (~30%)

**Implementation Strategy**:
```python
# File: tests/conftest.py (centralized fixtures - DRY!)
import pytest
from unittest.mock import Mock, AsyncMock

@pytest.fixture
def mock_openai_provider():
    """Reusable mock for OpenAI provider"""
    provider = Mock()
    provider.chat = AsyncMock(return_value=CompletionResponse(
        content="Test response",
        model="gpt-4o",
        provider="openai",
        usage={"input_tokens": 100, "output_tokens": 50},
        cost=0.0025,
        latency=0.5,
        timestamp=datetime.utcnow()
    ))
    return provider

@pytest.fixture
def mock_vision_processor(mock_openai_provider):
    """Reusable mock for vision processor"""
    from services.vision.processor import VisionProcessor
    from services.vision.config import VisionConfig

    config = VisionConfig(
        model="gpt-4o",
        max_tokens=4096,
        cost_limit_per_document=1.0
    )
    return VisionProcessor(
        provider=mock_openai_provider,
        config=config
    )

@pytest.fixture
async def test_db():
    """Test database with migrations applied"""
    # Create test database
    engine = create_async_engine("postgresql://test:test@localhost/test_db")

    # Run migrations
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
```

**Test examples**:
```python
# File: tests/unit/services/test_vision_processor.py
import pytest
from services.vision.processor import VisionProcessor

class TestVisionProcessor:
    """Test vision processing service"""

    @pytest.mark.asyncio
    async def test_process_single_page(self, mock_vision_processor):
        """Test processing single-page document"""
        document = create_test_document(pages=1)

        result = await mock_vision_processor.process_document(
            document=document,
            prompt="Extract text"
        )

        assert result.pages_processed == 1
        assert result.cost > 0
        assert result.content is not None

    @pytest.mark.asyncio
    async def test_process_multi_page(self, mock_vision_processor):
        """Test processing multi-page document"""
        document = create_test_document(pages=5)

        result = await mock_vision_processor.process_document(
            document=document,
            prompt="Extract invoice data"
        )

        assert result.pages_processed == 5
        # Should be single API call (not 5 calls)
        assert mock_vision_processor.provider.chat.call_count == 1

    @pytest.mark.asyncio
    async def test_cost_limit_exceeded(self, mock_vision_processor):
        """Test cost limit enforcement"""
        mock_vision_processor.config.cost_limit_per_document = 0.001

        document = create_test_document(pages=10)

        with pytest.raises(ValueError, match="Cost .* exceeds limit"):
            await mock_vision_processor.process_document(document, "Extract")
```

**Target Coverage**:
- VisionProcessor: 85%+
- DocumentProcessingPipeline: 90%+
- EntityResolver: 85%+
- CommitmentManager: 85%+
- All providers: 80%+

---

#### TEST-002: Integration Tests
**Why**: Test API endpoints with real database

**Implementation**:
```python
# File: tests/integration/test_document_upload_flow.py
import pytest
from httpx import AsyncClient
from api.main import app

@pytest.mark.asyncio
async def test_document_upload_end_to_end(test_db, test_file):
    """Test complete document upload → vendor → commitment flow"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Upload document
        with open(test_file, "rb") as f:
            response = await client.post(
                "/api/v1/documents/upload",
                files={"file": ("invoice.pdf", f, "application/pdf")},
                data={"extraction_type": "invoice"}
            )

        assert response.status_code == 200
        result = response.json()

        # Verify document created
        assert "document_id" in result
        assert result["vendor"]["matched"] is True  # Vendor was found/created
        assert result["commitment"]["priority"] > 0

        # Verify database state
        async with test_db.begin() as conn:
            # Check document exists
            doc = await conn.execute(
                select(Document).where(Document.id == result["document_id"])
            )
            assert doc is not None

            # Check vendor exists
            vendor = await conn.execute(
                select(Party).where(Party.id == result["vendor"]["id"])
            )
            assert vendor is not None

            # Check commitment exists
            commitment = await conn.execute(
                select(Commitment).where(Commitment.id == result["commitment"]["id"])
            )
            assert commitment is not None

            # Check links created
            links = await conn.execute(
                select(DocumentLink).where(
                    DocumentLink.document_id == result["document_id"]
                )
            )
            assert len(links.all()) >= 3  # signal, vendor, commitment
```

**Coverage Target**: 90%+ of all API endpoints

---

#### TEST-003: E2E Tests with Real APIs
**Why**: Validate actual provider integrations

**Implementation**:
```python
# File: tests/e2e/test_api_integration.py
import pytest
import os

# Only run if explicitly enabled
pytestmark = pytest.mark.skipif(
    os.getenv("RUN_E2E_TESTS") != "true",
    reason="E2E tests disabled (set RUN_E2E_TESTS=true)"
)

@pytest.mark.asyncio
async def test_anthropic_chat():
    """Test real Anthropic API call"""
    provider = AnthropicProvider(
        ProviderConfig(api_key=os.getenv("ANTHROPIC_API_KEY"))
    )

    response = await provider.chat(
        messages=[Message(role="user", content="Say 'test successful'")],
        model="claude-sonnet-4-5",
        max_tokens=100
    )

    assert "test successful" in response.content.lower()
    assert response.cost > 0
    assert response.cost < 0.01  # Sanity check
```

---

### 1.3 Error Handling & Resilience (12 hours)

#### ERR-001: Circuit Breaker Pattern
**Why**: Prevent cascading failures when external APIs are down

**Implementation**:
```python
# File: lib/shared/local_assistant_shared/resilience/circuit_breaker.py
from enum import Enum
from datetime import datetime, timedelta
import asyncio

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery

class CircuitBreaker:
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        timeout_seconds: int = 60,
        half_open_max_calls: int = 3
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.half_open_max_calls = half_open_max_calls

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        self.half_open_calls = 0

    async def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection"""
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                self.half_open_calls = 0
            else:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker '{self.name}' is OPEN"
                )

        if self.state == CircuitState.HALF_OPEN:
            if self.half_open_calls >= self.half_open_max_calls:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker '{self.name}' max half-open calls exceeded"
                )
            self.half_open_calls += 1

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def _on_success(self):
        """Handle successful call"""
        if self.state == CircuitState.HALF_OPEN:
            # Recovery successful
            self.state = CircuitState.CLOSED
            self.failure_count = 0
        self.failure_count = max(0, self.failure_count - 1)

    def _on_failure(self):
        """Handle failed call"""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN

    def _should_attempt_reset(self) -> bool:
        """Check if we should try to recover"""
        if not self.last_failure_time:
            return True

        elapsed = datetime.utcnow() - self.last_failure_time
        return elapsed > timedelta(seconds=self.timeout_seconds)
```

**Usage in providers**:
```python
# File: providers/base.py
class BaseProvider(ABC):
    def __init__(self, config: ProviderConfig):
        self.config = config
        self.circuit_breaker = CircuitBreaker(
            name=self.__class__.__name__,
            failure_threshold=config.circuit_breaker_threshold,
            timeout_seconds=config.circuit_breaker_timeout
        )

    async def chat(self, messages, model, **kwargs) -> CompletionResponse:
        """Wrap actual API call with circuit breaker"""
        return await self.circuit_breaker.call(
            self._chat_impl,  # Actual implementation
            messages,
            model,
            **kwargs
        )

    @abstractmethod
    async def _chat_impl(self, messages, model, **kwargs):
        """Actual API call (to be implemented by subclasses)"""
        pass
```

**Config**:
```yaml
# File: config/resilience.yaml
circuit_breaker:
  default:
    failure_threshold: 5
    timeout_seconds: 60
    half_open_max_calls: 3

  per_provider:
    anthropic:
      failure_threshold: 5
      timeout_seconds: 60
    openai:
      failure_threshold: 5
      timeout_seconds: 60
    google:
      failure_threshold: 3  # Faster recovery for cost-optimized fallback
      timeout_seconds: 30
```

---

#### ERR-002: Retry Logic with Exponential Backoff
**Why**: Transient failures should be retried automatically

**Implementation** (DRY - using tenacity library):
```python
# File: lib/shared/local_assistant_shared/resilience/retry.py
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)
import logging

logger = logging.getLogger(__name__)

def create_retry_decorator(config):
    """Create retry decorator from config (DRY!)"""
    return retry(
        stop=stop_after_attempt(config.max_attempts),
        wait=wait_exponential(
            multiplier=config.initial_wait_seconds,
            max=config.max_wait_seconds
        ),
        retry=retry_if_exception_type((
            TimeoutError,
            ConnectionError,
            RateLimitError
        )),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )

# Usage in providers:
from lib.shared.local_assistant_shared.resilience import create_retry_decorator

class AnthropicProvider(BaseProvider):
    def __init__(self, config):
        super().__init__(config)
        self.retry = create_retry_decorator(config.retry)

    @retry  # Automatically retries on failure
    async def _chat_impl(self, messages, model, **kwargs):
        # Actual API call
        ...
```

**Config**:
```yaml
# File: config/retry.yaml
default:
  max_attempts: 3
  initial_wait_seconds: 1
  max_wait_seconds: 10
  exponential_base: 2
  jitter: true

per_error_type:
  rate_limit:
    max_attempts: 5
    initial_wait_seconds: 30  # Wait longer for rate limits

  timeout:
    max_attempts: 3
    initial_wait_seconds: 2

  connection:
    max_attempts: 4
    initial_wait_seconds: 1
```

---

#### ERR-003: Standardized Error Responses
**Why**: Consistent error format across all endpoints

**Implementation**:
```python
# File: api/models/errors.py
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict, Any

class ErrorResponse(BaseModel):
    """Standardized error response model"""
    error_code: str
    message: str
    details: Optional[str] = None
    request_id: Optional[str] = None
    timestamp: datetime = datetime.utcnow()
    suggested_action: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

# Error codes catalog
class ErrorCodes:
    # Vision errors
    VISION_EXTRACTION_FAILED = "ERR_VISION_001"
    VISION_INVALID_FILE = "ERR_VISION_002"
    VISION_COST_EXCEEDED = "ERR_VISION_003"

    # Document errors
    DOCUMENT_NOT_FOUND = "ERR_DOC_001"
    DOCUMENT_UPLOAD_FAILED = "ERR_DOC_002"

    # Entity resolution errors
    VENDOR_RESOLUTION_FAILED = "ERR_ENTITY_001"

    # Auth errors
    AUTH_INVALID_TOKEN = "ERR_AUTH_001"
    AUTH_TOKEN_EXPIRED = "ERR_AUTH_002"

# Helper function
def create_error_response(
    code: str,
    message: str,
    details: Optional[str] = None,
    suggested_action: Optional[str] = None,
    request_id: Optional[str] = None
) -> ErrorResponse:
    """DRY helper to create error responses"""
    return ErrorResponse(
        error_code=code,
        message=message,
        details=details,
        request_id=request_id,
        suggested_action=suggested_action
    )
```

**Global error handler**:
```python
# File: api/main.py
from api.models.errors import ErrorResponse, ErrorCodes, create_error_response

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch all unhandled exceptions"""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

    # Map exception types to error codes
    error_map = {
        ValidationError: ErrorCodes.VALIDATION_FAILED,
        FileNotFoundError: ErrorCodes.DOCUMENT_NOT_FOUND,
        JWTError: ErrorCodes.AUTH_INVALID_TOKEN,
        # ... more mappings
    }

    error_code = error_map.get(type(exc), "ERR_UNKNOWN")

    error_response = create_error_response(
        code=error_code,
        message=str(exc),
        details=traceback.format_exc(),
        request_id=request_id,
        suggested_action="Check logs for details or contact support"
    )

    # Log error
    logger.error(
        "Unhandled exception",
        extra={
            "error_code": error_code,
            "request_id": request_id,
            "path": request.url.path,
            "exception": str(exc)
        }
    )

    return JSONResponse(
        status_code=500,
        content=error_response.dict()
    )
```

**Usage in routes** (consistent format):
```python
@router.post("/upload")
async def upload(file: UploadFile, request: Request):
    request_id = request.headers.get("X-Request-ID")

    try:
        # ... processing
        pass
    except ValidationError as e:
        raise HTTPException(
            status_code=400,
            detail=create_error_response(
                code=ErrorCodes.VISION_INVALID_FILE,
                message="Invalid file format",
                details=str(e),
                request_id=request_id,
                suggested_action="Upload a PDF, PNG, or JPG file"
            ).dict()
        )
```

---

## Phase 2: High Priority

**Estimated Time**: 48 hours (~1.5 weeks)
**Complete after Phase 1, before launch**

### 2.1 Performance Optimization (20 hours)

#### PERF-001: Redis Caching Layer
**Why**: Reduce database load and improve response times

**Implementation**:
```python
# File: memory/cache.py
import redis.asyncio as redis
import json
from typing import Optional, Any
from datetime import timedelta

class CacheManager:
    def __init__(self, redis_url: str, default_ttl: int = 3600):
        self.redis = redis.from_url(redis_url)
        self.default_ttl = default_ttl

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        value = await self.redis.get(key)
        if value:
            return json.loads(value)
        return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> None:
        """Set value in cache with TTL"""
        ttl = ttl or self.default_ttl
        await self.redis.setex(
            key,
            timedelta(seconds=ttl),
            json.dumps(value)
        )

    async def delete(self, key: str) -> None:
        """Delete key from cache"""
        await self.redis.delete(key)

    async def invalidate_pattern(self, pattern: str) -> None:
        """Invalidate all keys matching pattern"""
        keys = await self.redis.keys(pattern)
        if keys:
            await self.redis.delete(*keys)

# File: memory/cache_keys.py (DRY - centralized key builder)
class CacheKeys:
    """Centralized cache key construction (DRY principle!)"""

    @staticmethod
    def vendor_lookup(name: str, tax_id: Optional[str] = None) -> str:
        """Cache key for vendor lookups"""
        if tax_id:
            return f"vendor:lookup:{name}:{tax_id}"
        return f"vendor:lookup:{name}"

    @staticmethod
    def document_extraction(sha256: str) -> str:
        """Cache key for document extractions"""
        return f"document:extraction:{sha256}"

    @staticmethod
    def commitment_list(user_id: str, filters: str = "") -> str:
        """Cache key for commitment lists"""
        return f"commitment:list:{user_id}:{filters}"

    @staticmethod
    def vendor_commitments(vendor_id: str) -> str:
        """Cache key for vendor commitments"""
        return f"vendor:{vendor_id}:commitments"
```

**Usage in services** (DRY pattern):
```python
# File: services/document_intelligence/entity_resolver.py
from memory.cache import get_cache_manager
from memory.cache_keys import CacheKeys

class EntityResolver:
    def __init__(self, cache: CacheManager):
        self.cache = cache

    async def resolve_vendor(self, db, vendor_name, vendor_info):
        # Check cache first
        cache_key = CacheKeys.vendor_lookup(
            name=vendor_name,
            tax_id=vendor_info.get("tax_id")
        )

        cached = await self.cache.get(cache_key)
        if cached:
            return ResolutionResult(**cached)

        # Not in cache, do expensive lookup
        result = await self._fuzzy_match_vendor(db, vendor_name, vendor_info)

        # Cache result
        await self.cache.set(cache_key, result.dict(), ttl=86400)  # 24 hours

        return result
```

**Config**:
```yaml
# File: config/cache.yaml
enabled: true
redis_url: ${REDIS_URL}
default_ttl_seconds: 3600

cache_types:
  vendor_lookup:
    ttl: 86400  # 24 hours (vendors don't change often)

  document_extraction:
    ttl: 604800  # 7 days (extraction results are immutable)

  commitment_list:
    ttl: 300  # 5 minutes (frequently changing)

  vendor_commitments:
    ttl: 600  # 10 minutes
```

---

#### PERF-002: Database Query Optimization
**Why**: Eliminate N+1 queries and slow queries

**Current Problem**:
```python
# N+1 query problem:
commitments = await db.execute(select(Commitment))
for commitment in commitments:
    vendor = await db.execute(  # N queries!
        select(Party).where(Party.id == commitment.counterparty_id)
    )
```

**Solution** (eager loading):
```python
# Optimized with joinedload:
from sqlalchemy.orm import joinedload

commitments = await db.execute(
    select(Commitment)
    .options(joinedload(Commitment.role).joinedload(Role.party))  # Single query!
)
```

**Add to models.py**:
```python
# File: memory/models.py
class Commitment(Base):
    # Add relationship with eager loading hint
    role: Mapped["Role"] = relationship(
        "Role",
        back_populates="commitments",
        lazy="joined"  # Always eager load
    )
```

**Indexes to add**:
```sql
-- File: migrations/versions/005_add_performance_indexes.py
"""Add performance indexes

Revision ID: 005
"""

def upgrade():
    # Case-insensitive name search
    op.execute("""
        CREATE INDEX idx_parties_name_lower
        ON parties(LOWER(name))
    """)

    # Compound index for priority queries
    op.execute("""
        CREATE INDEX idx_commitments_priority_due
        ON commitments(priority DESC, due_date)
        WHERE state = 'pending'
    """)

    # Covering index for vendor lookups
    op.execute("""
        CREATE INDEX idx_parties_lookup
        ON parties(name, tax_id)
        INCLUDE (id, kind, address)
    """)
```

**Database config**:
```yaml
# File: config/database.yaml
connection_pool:
  pool_size: 10
  max_overflow: 20
  pool_timeout: 30
  pool_recycle: 3600  # Recycle connections every hour

query_logging:
  enabled: true
  slow_query_threshold_ms: 100  # Log queries >100ms

optimization:
  statement_cache_size: 500
  echo: false  # Set to true for debugging
```

---

### 2.2 Configuration DRY Improvements (16 hours)

#### DRY-001: Centralize Configuration Loading
**Why**: Currently each service loads configs independently (violation of DRY)

**Current Problem**:
```python
# Repeated in multiple files:
with open("config/vision_config.yaml") as f:
    vision_config = yaml.safe_load(f)

with open("config/computer_use.yaml") as f:
    computer_config = yaml.safe_load(f)
```

**Solution**:
```python
# File: lib/shared/local_assistant_shared/config/loader.py (enhance existing)
from pydantic import BaseModel
from typing import Dict, Any
import yaml
from pathlib import Path

class VisionConfig(BaseModel):
    model: str
    max_tokens: int
    temperature: float
    cost_limit_per_document: float

class ComputerUseConfig(BaseModel):
    sandbox_enabled: bool
    allowed_domains: list[str]
    # ... more fields

class RateLimitsConfig(BaseModel):
    global_rpm: int
    endpoints: Dict[str, Dict[str, int]]

class AppConfig(BaseModel):
    """Unified application configuration"""
    vision: VisionConfig
    computer_use: ComputerUseConfig
    rate_limits: RateLimitsConfig
    database: DatabaseConfig
    cache: CacheConfig
    secrets: SecretsConfig
    resilience: ResilienceConfig
    # ... all configs

class ConfigLoader:
    """Single config loader (DRY principle!)"""
    _instance: Optional['ConfigLoader'] = None
    _config: Optional[AppConfig] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def load(self, config_dir: Path = Path("config")) -> AppConfig:
        """Load all configs once at startup"""
        if self._config is not None:
            return self._config

        configs = {}

        # Load all YAML files
        for yaml_file in config_dir.glob("*.yaml"):
            with open(yaml_file) as f:
                key = yaml_file.stem  # e.g., "vision_config" -> "vision"
                configs[key] = yaml.safe_load(f)

        # Validate and parse with Pydantic
        self._config = AppConfig(**configs)

        return self._config

    def reload(self):
        """Hot reload configs"""
        self._config = None
        return self.load()

# Global getter (DRY!)
_loader = ConfigLoader()

def get_config() -> AppConfig:
    """Get application config (lazy loaded)"""
    return _loader.load()
```

**Usage everywhere** (DRY!):
```python
# Before (repeated everywhere):
with open("config/vision_config.yaml") as f:
    config = yaml.safe_load(f)
    model = config["model"]

# After (single source of truth):
from lib.shared.local_assistant_shared.config import get_config

config = get_config()
model = config.vision.model  # Type-safe!
```

---

#### DRY-002: Eliminate Hardcoded Strings
**Why**: Magic strings scattered everywhere make code brittle

**Solution**:
```python
# File: lib/shared/local_assistant_shared/enums.py
from enum import Enum

class SignalStatus(str, Enum):
    NEW = "new"
    PROCESSING = "processing"
    ATTACHED = "attached"
    ERROR = "error"

class CommitmentState(str, Enum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    ACTIVE = "active"
    PAUSED = "paused"
    FULFILLED = "fulfilled"
    CANCELED = "canceled"

class CommitmentType(str, Enum):
    OBLIGATION = "obligation"
    RESPONSIBILITY = "responsibility"
    GOAL = "goal"
    ROUTINE = "routine"

class DocumentType(str, Enum):
    INVOICE = "invoice"
    RECEIPT = "receipt"
    CONTRACT = "contract"
    FORM = "form"

class ExtractionType(str, Enum):
    STRUCTURED = "structured"
    INVOICE = "invoice"
    OCR = "ocr"
    TABLES = "tables"

# File: lib/shared/local_assistant_shared/constants.py
class ModelNames:
    # Vision models
    GPT_4O = "gpt-4o"
    CLAUDE_SONNET_45 = "claude-sonnet-4-5-20250929"
    GEMINI_25_FLASH = "gemini-2.5-flash"

    # Reasoning models
    O4_MINI = "o4-mini"
    GPT_5 = "gpt-5"

class CostLimits:
    PER_REQUEST = 1.00
    PER_HOUR = 10.00
    PER_DAY = 50.00

# File: lib/shared/local_assistant_shared/messages.yaml
# Error messages (externalized for i18n)
errors:
  vision:
    extraction_failed: "Document extraction failed: {details}"
    invalid_file: "Invalid file type: {mime_type}"
    cost_exceeded: "Extraction cost ${cost} exceeds limit ${limit}"

  auth:
    invalid_token: "Invalid authentication token"
    token_expired: "Authentication token expired"

# Loader:
class Messages:
    _messages: Dict[str, Any] = None

    @classmethod
    def load(cls):
        if cls._messages is None:
            with open("lib/shared/local_assistant_shared/messages.yaml") as f:
                cls._messages = yaml.safe_load(f)

    @classmethod
    def get(cls, key: str, **kwargs) -> str:
        cls.load()
        # Navigate nested dict: "errors.vision.extraction_failed"
        value = cls._messages
        for part in key.split('.'):
            value = value[part]
        return value.format(**kwargs)
```

**Before/After**:
```python
# Before (magic strings):
signal.status = "processing"
if commitment.state == "pending":
    error_msg = "Document extraction failed"

# After (enums and constants):
from lib.shared.local_assistant_shared.enums import SignalStatus, CommitmentState
from lib.shared.local_assistant_shared.messages import Messages

signal.status = SignalStatus.PROCESSING
if commitment.state == CommitmentState.PENDING:
    error_msg = Messages.get("errors.vision.extraction_failed", details=str(e))
```

---

#### DRY-003: Unify Provider Configuration
**Why**: Each provider has custom initialization (DRY violation)

**Solution** (Factory Pattern):
```python
# File: providers/factory.py
from typing import Dict, Type
from providers.base import BaseProvider, ProviderConfig
from providers.anthropic_provider import AnthropicProvider
from providers.openai_provider import OpenAIProvider
from providers.google_provider import GoogleProvider

class ProviderFactory:
    """Factory for creating providers (DRY!)"""

    _registry: Dict[str, Type[BaseProvider]] = {
        "anthropic": AnthropicProvider,
        "openai": OpenAIProvider,
        "google": GoogleProvider,
    }

    @classmethod
    def create(cls, provider_name: str) -> BaseProvider:
        """Create provider from config"""
        config = get_config()
        secrets = get_secrets_provider()

        # Get provider class
        provider_class = cls._registry.get(provider_name)
        if not provider_class:
            raise ValueError(f"Unknown provider: {provider_name}")

        # Get API key from secrets
        api_key_name = f"{provider_name.upper()}_API_KEY"
        api_key = await secrets.get_secret(api_key_name)

        # Get provider-specific config from models registry
        provider_config_dict = config.models_registry.get_provider_config(provider_name)

        # Create provider config
        provider_config = ProviderConfig(
            api_key=api_key,
            **provider_config_dict
        )

        # Instantiate provider
        return provider_class(provider_config)

    @classmethod
    def register(cls, name: str, provider_class: Type[BaseProvider]):
        """Register custom provider"""
        cls._registry[name] = provider_class

# Usage in api/main.py:
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Before (manual initialization):
    # anthropic = AnthropicProvider(ProviderConfig(api_key=os.getenv("ANTHROPIC_API_KEY")))
    # openai = OpenAIProvider(ProviderConfig(api_key=os.getenv("OPENAI_API_KEY")))
    # google = GoogleProvider(ProviderConfig(api_key=os.getenv("GOOGLE_API_KEY")))

    # After (factory):
    app_state["anthropic"] = await ProviderFactory.create("anthropic")
    app_state["openai"] = await ProviderFactory.create("openai")
    app_state["google"] = await ProviderFactory.create("google")

    yield
```

---

## Phase 3: Medium Priority

**Estimated Time**: 36 hours (~1 week)
**Complete after Phase 2 for full production readiness**

### 3.1 Deployment Automation (16 hours)

#### Kubernetes Manifests
```yaml
# File: k8s/api-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: local-assistant-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: local-assistant-api
  template:
    metadata:
      labels:
        app: local-assistant-api
    spec:
      containers:
      - name: api
        image: local-assistant-api:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: local-assistant-secrets
              key: database-url
        livenessProbe:
          httpGet:
            path: /api/health/live
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /api/health/ready
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
```

#### CI/CD Pipeline
```yaml
# File: .github/workflows/ci.yaml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -e ".[dev]"

      - name: Lint
        run: ruff check .

      - name: Format check
        run: ruff format --check .

      - name: Type check
        run: mypy .

      - name: Test
        run: pytest --cov=. --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

---

## Phase 4: Low Priority

**Estimated Time**: 24 hours (~3 days)
**Nice-to-have features for future**

- Batch processing queue (Celery)
- Webhook support
- Multi-tenant support
- Advanced analytics

---

## Implementation Roadmap

### Week 1: Security & Testing Foundation
- Days 1-2: JWT authentication + rate limiting
- Days 3-4: Secrets management + file validation
- Day 5: Unit tests (services)

### Week 2: Resilience & Testing
- Days 1-2: Circuit breaker + retry logic
- Days 3-4: Integration tests
- Day 5: E2E tests + error handling

### Week 3: Performance & DRY
- Days 1-2: Redis caching + query optimization
- Days 3-4: Configuration centralization
- Day 5: Provider factory + constants cleanup

### Week 4: Deployment & Documentation
- Days 1-2: Kubernetes manifests + CI/CD
- Days 3-4: Documentation (ADRs, API reference)
- Day 5: Load testing + final validation

---

## Before/After Examples

### Example 1: Configuration Loading
```python
# BEFORE (DRY Violation - repeated 10+ times):
with open("config/vision_config.yaml") as f:
    config = yaml.safe_load(f)
    model = config["model"]  # No type safety

# AFTER (DRY Compliant - single source):
from lib.shared.local_assistant_shared.config import get_config

config = get_config()
model = config.vision.model  # Type-safe, auto-complete
```

### Example 2: Error Handling
```python
# BEFORE (Inconsistent formats):
return {"error": "failed"}
raise HTTPException(status_code=400, detail="error")
return JSONResponse({"message": "error"}, status_code=500)

# AFTER (Standardized):
from api.models.errors import create_error_response, ErrorCodes

raise HTTPException(
    status_code=400,
    detail=create_error_response(
        code=ErrorCodes.VISION_INVALID_FILE,
        message="Invalid file",
        suggested_action="Upload PDF/PNG/JPG"
    ).dict()
)
```

### Example 3: Cache Keys
```python
# BEFORE (Manual construction everywhere):
cache_key = f"vendor:{name}:{tax_id}"
cache_key = f"document:extraction:{sha256}"
cache_key = f"commitment:{user_id}:{role_id}"

# AFTER (Centralized builder):
from memory.cache_keys import CacheKeys

key = CacheKeys.vendor_lookup(name=name, tax_id=tax_id)
key = CacheKeys.document_extraction(sha256=sha256)
key = CacheKeys.commitment(user_id=user_id, role_id=role_id)
```

---

## Validation Criteria

### Code Quality Metrics
- ✅ Test coverage: 85%+
- ✅ Type coverage: 90%+
- ✅ Cyclomatic complexity: <10
- ✅ Duplicate code: <5%
- ✅ Security vulnerabilities: 0

### Performance Metrics
- ✅ API P95 latency: <200ms
- ✅ API P99 latency: <500ms
- ✅ Database query P95: <50ms
- ✅ Zero N+1 queries
- ✅ Cache hit rate: >80%

### Security Checklist
- ✅ JWT authentication implemented
- ✅ Rate limiting enabled
- ✅ Secrets in secrets manager (not .env)
- ✅ File uploads validated (magic bytes)
- ✅ No secrets in code/config
- ✅ HTTPS enforced in production

### DRY Compliance
- ✅ Single configuration loader
- ✅ No hardcoded strings (use enums/constants)
- ✅ Centralized error handling
- ✅ Reusable validators
- ✅ Provider factory pattern
- ✅ Shared cache key builder

### Deployment Readiness
- ✅ Kubernetes manifests complete
- ✅ CI/CD pipeline working
- ✅ Health checks implemented
- ✅ Monitoring dashboards configured
- ✅ Documentation complete
- ✅ Load testing passed (100 concurrent users)

---

## Summary

This improvement plan transforms Local Assistant from 90% → 100% production-ready while adhering to DRY principles:

**Key Improvements**:
1. **Security**: JWT auth, rate limiting, secrets management
2. **Testing**: 85%+ coverage across unit/integration/e2e
3. **Performance**: Redis caching, query optimization, <200ms latency
4. **DRY**: Centralized configs, enums, error handling, validation
5. **Deployment**: K8s, CI/CD, health checks, monitoring

**Timeline**: 4 weeks for complete unicorn-grade status

**Result**: Production-ready, maintainable, scalable AI assistant with zero technical debt.

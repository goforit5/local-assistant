# Test Suite

Comprehensive test suite for the Local AI Assistant.

## Structure

```
tests/
├── unit/                  # Unit tests (isolated component tests)
│   ├── providers/        # Provider tests
│   ├── services/         # Service tests
│   ├── memory/          # Memory layer tests
│   └── observability/   # Observability tests
├── integration/          # Integration tests (component interaction)
└── e2e/                 # End-to-end tests (full workflows)
```

## Running Tests

### Install dev dependencies
```bash
source .venv/bin/activate
uv pip install -r requirements-dev.txt
```

### Run all tests
```bash
pytest
```

### Run with coverage
```bash
pytest --cov=. --cov-report=html
```

### Run specific test file
```bash
pytest tests/unit/providers/test_anthropic.py
```

### Run specific test
```bash
pytest tests/unit/providers/test_anthropic.py::TestAnthropicProvider::test_calculate_cost
```

### Run by marker
```bash
pytest -m asyncio  # Run only async tests
pytest -m "not slow"  # Skip slow tests
```

## Test Categories

### Unit Tests
- Test individual components in isolation
- Mock external dependencies
- Fast execution
- High code coverage

### Integration Tests
- Test component interactions
- May use real services (Redis, PostgreSQL)
- Test data flow between layers

### E2E Tests
- Test complete user workflows
- Test CLI commands
- Test full service orchestration
- May require external services running

## Writing Tests

### Test Fixtures
Use fixtures defined in `conftest.py`:
- `anthropic_provider` - Mock Anthropic provider
- `openai_provider` - Mock OpenAI provider
- `chat_router` - Chat router with mocks
- `cost_tracker` - Cost tracker instance
- `sample_messages` - Sample message list

### Example Test
```python
import pytest

@pytest.mark.asyncio
async def test_chat_router(chat_router, sample_messages):
    """Test chat routing."""
    response = await chat_router.chat(sample_messages)
    assert response is not None
```

## Coverage Goals

- **Unit tests**: 80%+ coverage
- **Integration tests**: Key workflows
- **E2E tests**: Critical user paths

## CI/CD Integration

Tests run automatically on:
- Pull requests
- Pushes to main
- Nightly builds

## Debugging Tests

### Verbose output
```bash
pytest -vv
```

### Show print statements
```bash
pytest -s
```

### Debug specific test
```bash
pytest --pdb tests/unit/providers/test_anthropic.py::test_cost
```

### Async debugging
```bash
pytest --asyncio-mode=auto -vv
```

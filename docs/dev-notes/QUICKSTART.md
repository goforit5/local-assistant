# 🚀 Quickstart Guide

Get up and running with Local AI Assistant in 5 minutes.

## Prerequisites

```bash
# Check Python version (3.11+ required)
python3 --version

# Check Docker
docker --version
docker-compose --version
```

## 1. Setup Environment

```bash
# Navigate to project
cd local_assistant

# Copy environment template
cp .env.example .env

# Edit with your API keys
nano .env  # or use your favorite editor
```

Add your API keys:

```bash
ANTHROPIC_API_KEY=sk-ant-xxx...
OPENAI_API_KEY=sk-xxx...
GOOGLE_API_KEY=AIxxx...
```

## 2. Install

```bash
# Quick setup (recommended)
make setup

# Or manual:
pip install -e ".[dev]"
docker-compose up -d
```

## 3. Verify Installation

```bash
# Check services
make status

# Or manually:
docker-compose ps

# Should see 6 services running:
# ✅ postgres
# ✅ redis
# ✅ chroma
# ✅ prometheus
# ✅ grafana
# ✅ jaeger
```

## 4. First Commands

```bash
# Help
assistant --help

# System status
assistant status

# Check costs (should be $0.00 initially)
assistant costs --today
```

## 5. Test Services

### Vision Service

```bash
# Create a test image (requires screenshot or PDF)
# Download sample invoice
curl -o test_invoice.pdf https://example.com/sample_invoice.pdf

# Extract structured data
assistant vision extract test_invoice.pdf --type invoice --output json
```

### Chat Service

```bash
# Simple chat
assistant chat "Hello! How are you?"

# With streaming
assistant chat "Explain quantum computing in simple terms" --stream

# With specific model
assistant chat "Write a Python function to reverse a string" --model sonnet
```

### Computer Use

```bash
# Browser automation
assistant computer "Search for Python tutorials on Google" --env browser --live

# With confirmation required
assistant computer "Fill out a form on example.com" --require-confirmation
```

### Reasoning

```bash
# Complex reasoning
assistant reason "Design a caching strategy for a social media feed"

# With context
assistant reason "Optimize this code" --context myfile.py --detail high
```

## 6. Monitor System

### Grafana Dashboards

```bash
# Open Grafana (auto-login: admin/admin)
make monitor

# Or manually:
open http://localhost:3000
```

### Prometheus Metrics

```bash
make prometheus

# Or:
open http://localhost:9090
```

### Jaeger Tracing

```bash
make jaeger

# Or:
open http://localhost:16686
```

## 7. Cost Tracking

```bash
# View costs
assistant costs --today --breakdown

# By model
assistant costs --by-model

# Set alert
assistant config set-limit --per-day 20.00
```

## Common Issues

### Services won't start

```bash
# Check Docker
docker-compose logs

# Restart
docker-compose restart

# Full reset
make docker-clean
make docker-up
```

### API errors

```bash
# Verify keys
assistant config verify

# Check rate limits
assistant status --providers
```

### High costs

```bash
# Review usage
assistant costs --last-hour --detailed

# Switch to cost-optimized mode
assistant config set-strategy cost_optimized
```

## Next Steps

1. **Configure Models**: Edit `config/models_registry.yaml`
2. **Set Cost Limits**: Edit cost limits in `config/models_registry.yaml`
3. **Customize Safety**: Edit `config/computer_use.yaml`
4. **Add Custom Skills**: Create YAML files in `config/skills/`
5. **Explore Dashboards**: Create custom Grafana dashboards

## Development Mode

```bash
# Install dev dependencies
make install-dev

# Run tests
make test

# Format code
make format

# Run all checks
make check

# Start with hot reload
watchmedo auto-restart -d . -p '*.py' -- assistant chat "test"
```

## Architecture Overview

```
┌─────────────────────────────────────────┐
│           CLI Interface                 │
│   (Typer + Rich for beautiful output)  │
└─────────────────────────────────────────┘
                  │
┌─────────────────────────────────────────┐
│         Service Orchestrator            │
│  (Routes tasks to appropriate services) │
└─────────────────────────────────────────┘
        │         │         │         │
    ┌───┴───┐ ┌──┴───┐ ┌──┴───┐ ┌──┴───┐
    │Vision │ │Comp. │ │Reason│ │Chat  │
    │Service│ │ Use  │ │Service│ │Service│
    └───┬───┘ └──┬───┘ └──┬───┘ └──┬───┘
        │         │         │         │
    ┌───┴─────────┴─────────┴─────────┴───┐
    │        Provider Abstraction          │
    │  (Anthropic │ OpenAI │ Google)      │
    └──────────────────────────────────────┘
                  │
    ┌─────────────┴─────────────┐
    │     Storage Layer         │
    │ Postgres │ Redis │ Chroma │
    └───────────────────────────┘
```

## Configuration Files

- **`config/models_registry.yaml`**: Model definitions, pricing, routing
- **`config/vision_config.yaml`**: OCR settings, document types
- **`config/computer_use.yaml`**: Safety rules, allowed domains
- **`.env`**: API keys and environment variables

## Useful Commands

```bash
# Show all commands
make help

# Start services
make docker-up

# Stop services
make docker-down

# View logs
make docker-logs

# Check status
make status

# Monitor costs
make costs

# Clean everything
make clean
make docker-clean
```

## Support

- **Issues**: Check logs with `docker-compose logs -f`
- **Configuration**: Review YAML files in `config/`
- **Documentation**: See full [README.md](README.md)

---

**Ready to build amazing things! 🦄**

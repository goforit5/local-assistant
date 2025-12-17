<div align="center">

# 🦄 Local AI Assistant

**Production-ready AI agent framework with vision, reasoning, and computer use**

![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Code Style](https://img.shields.io/badge/code%20style-ruff-black)

[Features](#-features) • [Quick Start](#-quick-start) • [Documentation](#-usage) • [Architecture](#-architecture)

</div>

---

## 📋 Table of Contents

- [Features](#-features)
- [Architecture](#-architecture)
- [Quick Start](#-quick-start)
- [Usage](#-usage)
  - [Vision Service](#vision-service)
  - [Computer Use](#computer-use)
  - [Reasoning](#reasoning)
  - [Chat](#chat)
  - [Cost Tracking](#cost-tracking)
- [Configuration](#-configuration)
- [Observability](#-observability)
- [Safety Features](#-safety-features)
- [Development](#-development)
- [Project Structure](#-project-structure)
- [Troubleshooting](#-troubleshooting)
- [Contributing](#-contributing)

## ✨ Features

- **🔭 Vision Service**: Universal document reader (PDFs, images, invoices, forms) using GPT-4o + Tesseract/EasyOCR
- **🤖 Computer Use**: Browser and desktop automation via OpenAI Responses API
- **🧠 Reasoning**: Complex multi-step planning with o1-mini
- **💬 Smart Chat**: Claude Sonnet 4.5 (primary) + Gemini Flash 2.5 (fallback)
- **💰 Cost Tracking**: Penny-level precision across all providers
- **📊 Observability**: Built-in Grafana dashboards, Prometheus metrics, distributed tracing
- **🔒 Safety**: Sandboxed execution, allowlists, safety checks, audit logging

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        CLI / TUI                            │
│            (Beautiful interface with Rich)                  │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                      Orchestrator                           │
│         (Multi-service task coordination)                   │
└─────────────────────────────────────────────────────────────┘
         │              │              │              │
    ┌────┴────┐   ┌────┴────┐   ┌────┴────┐   ┌────┴────┐
    │ Vision  │   │Computer │   │Reasoning│   │  Chat   │
    │ Service │   │   Use   │   │ Service │   │ Service │
    │(GPT-4o) │   │(OpenAI) │   │(o1-mini)│   │(Sonnet) │
    └─────────┘   └─────────┘   └─────────┘   └─────────┘
                            │
          ┌─────────────────┴─────────────────┐
          │         Provider Layer            │
          │  Anthropic │ OpenAI │ Google     │
          └───────────────────────────────────┘
                            │
          ┌─────────────────┴─────────────────┐
          │        Storage Layer              │
          │  Postgres │ Redis │ ChromaDB     │
          └───────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- API Keys: Anthropic, OpenAI, Google

### Installation

```bash
# Clone the repository
cd local_assistant

# Copy environment template
cp .env.example .env

# Edit .env and add your API keys
nano .env

# Install with uv (recommended) or pip
pip install uv
uv pip install -e ".[dev]"

# Or with pip
pip install -e ".[dev]"

# Start infrastructure
docker-compose up -d

# Verify services
docker-compose ps

# Run the assistant
assistant --help
```

### First Run

```bash
# Simple chat
assistant chat "Hello, introduce yourself"

# Process a document
assistant vision extract invoice.pdf --type structured

# Computer use
assistant computer "Search for Python tutorials on Google" --env browser

# Reasoning task
assistant reason "How would you architect a distributed cache?"

# Check costs
assistant costs --today --breakdown
```

## 📖 Usage

### Vision Service

Extract structured data from any document:

```bash
# Extract invoice data
assistant vision extract invoice.pdf --type invoice --output json

# OCR image
assistant vision ocr screenshot.png --save-to output.txt

# Batch processing
assistant vision batch ./documents/*.pdf --type tables --parallel 5

# With specific model
assistant vision extract form.pdf --model gpt-4o --detail high
```

### Computer Use

Automate browser and desktop tasks:

```bash
# Browser automation
assistant computer "Book a flight to SF next week" --env browser --live

# Continue previous session
assistant computer "Now search for hotels" --continue-from <response_id>

# With safety checks
assistant computer "Fill out this form" --require-confirmation --audit

# Desktop automation (Mac/Windows/Ubuntu)
assistant computer "Open VSCode and create a new file" --env desktop_mac
```

### Reasoning

Complex problem-solving with o1-mini:

```bash
# Multi-step reasoning
assistant reason "Design a fault-tolerant distributed system"

# Code verification
assistant reason verify code.py --spec requirements.md

# Planning
assistant reason plan "Build a web scraper for e-commerce sites" --steps 10

# With context
assistant reason "Optimize this algorithm" --context problem.py --detail high
```

### Chat

General conversation with smart routing:

```bash
# Default (Sonnet 4.5)
assistant chat "Write a Python script to parse CSV files"

# Explicit model
assistant chat "Quick question about Git" --model gemini

# Streaming
assistant chat "Explain quantum computing" --stream --live

# With cost limit
assistant chat "Generate 10 code examples" --max-cost 0.50
```

### Cost Tracking

Monitor spending across providers:

```bash
# Today's costs
assistant costs --today

# Detailed breakdown
assistant costs --breakdown --by-model --by-service

# Last hour
assistant costs --last-hour --format json

# Set alerts
assistant costs set-alert --threshold 10.00 --period day --action notify
```

## 🔧 Configuration

### Model Selection

Edit [config/models_registry.yaml](config/models_registry.yaml):

```yaml
routing:
  strategies:
    capability_based:
      vision: gpt-4o
      reasoning: o1-mini
      computer_use: computer-use-preview
      chat: claude-sonnet-4-5
      fallback: gemini-2-5-flash
```

### Cost Limits

Edit [config/models_registry.yaml](config/models_registry.yaml):

```yaml
cost_limits:
  per_request: {warn: 0.50, max: 1.00}
  per_hour: {warn: 5.00, max: 10.00}
  per_day: {warn: 20.00, max: 50.00}
```

### Safety Rules

Edit [config/computer_use.yaml](config/computer_use.yaml):

```yaml
safety:
  allowed_domains:
    - "*.google.com"
    - "*.github.com"
  require_confirmation:
    - financial_transaction
    - account_creation
```

## 📊 Observability

### Grafana Dashboards

Access at [http://localhost:3000](http://localhost:3000)

- **Agent Performance**: Latency, tokens, error rates
- **Cost Tracking**: Real-time spend by provider/model
- **Computer Use**: Action success rate, safety checks
- **System Health**: Service status, resource usage

### Prometheus Metrics

Access at [http://localhost:9090](http://localhost:9090)

### Jaeger Tracing

Access at [http://localhost:16686](http://localhost:16686)

### CLI Monitoring

```bash
# Real-time TUI dashboard
assistant monitor --live

# Export metrics
assistant metrics --format json --output metrics.json

# View traces
assistant trace --follow --filter "service=vision"
```

## 🛡️ Safety Features

### Sandboxing

All computer use runs in isolated environments:

- Browser: Chromium sandbox with restricted file system
- Desktop: Docker containers with limited permissions
- Network: Allowlist-based domain filtering

### Audit Logging

Every action is logged:

```bash
# View audit log
assistant audit --today --service computer_use

# Export audit trail
assistant audit export --format csv --output audit.csv
```

### Safety Checks

- **Malicious instructions**: Detects prompt injection
- **Irrelevant domains**: Warns on off-task navigation
- **Sensitive domains**: Requires human confirmation
- **Action blocklist**: Prevents dangerous operations

## 🏃 Development

### Setup Development Environment

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Start services in dev mode
docker-compose up -d

# Run with hot reload
watchmedo auto-restart -d . -p '*.py' -- python -m cli.main
```

### Running Tests

```bash
# Run all tests
pytest

# With coverage
pytest --cov=services --cov=providers --cov-report=html

# Specific service
pytest tests/services/test_vision.py -v
```

### Code Quality

```bash
# Format code
ruff format .

# Lint
ruff check .

# Type checking
mypy .
```

## 📁 Project Structure

```
local_assistant/
├── services/           # Core services
│   ├── vision/        # Document processing
│   ├── responses/     # Computer use
│   ├── reasoning/     # o1-mini reasoning
│   ├── chat/          # Chat with routing
│   └── orchestrator/  # Multi-service coordination
├── providers/          # AI provider wrappers
│   ├── anthropic_provider.py
│   ├── openai_provider.py
│   └── google_provider.py
├── config/             # Configuration files
│   ├── models_registry.yaml
│   ├── vision_config.yaml
│   └── computer_use.yaml
├── memory/             # Storage layer
├── observability/      # Telemetry
├── cli/                # CLI interface
└── docker-compose.yml  # Infrastructure
```

## 🔑 Environment Variables

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=AI...

# Optional
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
CHROMA_HOST=localhost
CHROMA_PORT=8000

# Cost Limits
COST_LIMIT_PER_REQUEST=1.00
COST_LIMIT_PER_HOUR=10.00
COST_LIMIT_PER_DAY=50.00

# Safety
COMPUTER_USE_SANDBOX=true
REQUIRE_CONFIRMATION_FOR_SENSITIVE=true
```

## 📝 Examples

### Multi-Modal Task

```bash
# Process document + reasoning + action
assistant process invoice.pdf \
  "Extract totals, verify calculations, and email summary to [email protected]" \
  --services vision,reasoning,computer_use \
  --live
```

### Batch Document Processing

```bash
# Process 100 invoices in parallel
assistant vision batch ./invoices/*.pdf \
  --type invoice \
  --parallel 10 \
  --output ./results \
  --format json
```

### Complex Automation

```bash
# Research + summarize + save
assistant orchestrate \
  "Research latest AI papers on agentic systems, \
   summarize top 10, \
   create markdown report, \
   save to research.md" \
  --budget 5.00 \
  --tui
```

## 🐛 Troubleshooting

### Services won't start

```bash
# Check Docker status
docker-compose ps

# View logs
docker-compose logs -f

# Restart services
docker-compose restart
```

### API errors

```bash
# Verify API keys
assistant config verify

# Check rate limits
assistant status --providers

# Test individual provider
assistant test openai
```

### High costs

```bash
# Review recent requests
assistant costs --last-hour --detailed

# Adjust limits
assistant config set-limit --per-hour 5.00

# Switch to cost-optimized routing
assistant config set-strategy cost_optimized
```

## 🤝 Contributing

Contributions are welcome! Here's how you can help:

### Ways to Contribute

- 🐛 **Report bugs**: Open an issue describing the bug and how to reproduce it
- 💡 **Suggest features**: Share ideas for new features or improvements
- 📖 **Improve docs**: Help make the documentation clearer and more comprehensive
- 🔧 **Submit PRs**: Fix bugs, add features, or improve code quality

### Development Workflow

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (`pytest`)
5. Run linting (`ruff check . && ruff format .`)
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

### Code Standards

- Follow existing code style (enforced by Ruff)
- Add tests for new features
- Update documentation as needed
- Keep commits atomic and well-described

## 📄 License

MIT License - See [LICENSE](LICENSE) file for details

## 🙏 Acknowledgments

Built with amazing tools and services:

- [Anthropic](https://www.anthropic.com/) - Claude models (Sonnet, Opus, Haiku)
- [OpenAI](https://openai.com/) - GPT-4o, o1-mini, Computer Use API
- [Google AI](https://ai.google.dev/) - Gemini models
- [ChromaDB](https://www.trychroma.com/) - Vector database for semantic search
- [FastAPI](https://fastapi.tiangolo.com/) - Modern web framework
- [Typer](https://typer.tiangolo.com/) - CLI framework

---

<div align="center">

**Built with ❤️ for AI-powered automation**

*Optimized for developer productivity and cost efficiency*

[⬆ Back to Top](#-local-ai-assistant)

</div>

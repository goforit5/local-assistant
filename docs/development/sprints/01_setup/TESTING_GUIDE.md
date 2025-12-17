# Testing Guide - Ready to Test!

## ✅ Your Environment is Ready

Since you've already added your API keys to `.env`, you're all set to test! Here's what to test and how.

---

## 🚀 Quick Pre-Test Checklist

```bash
# 1. Verify you're in the right directory
cd /Users/andrew/Projects/AGENTS/local_assistant

# 2. Activate virtual environment
source .venv/bin/activate

# 3. Verify Docker services are running
docker-compose ps
# Should show 5 services running (postgres, redis, chroma, prometheus, grafana)

# 4. Check system status
python3 -m cli.main status
# Should show all API keys are set ✓
```

---

## 🎯 Features to Test (Priority Order)

### Test 1: Cost Tracking (Baseline - Test First!)
**Why first**: Establishes baseline, no API costs

```bash
python3 -m cli.main costs
```

**Expected Output**:
```
┏━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━┓
┃ Window           ┃ Total Cost ┃ Limit  ┃
┡━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━┩
│ Current Request  │ $0.0000    │ $1.00  │
│ Current Hour     │ $0.0000    │ $10.00 │
│ Today            │ $0.0000    │ $50.00 │
└──────────────────┴────────────┴────────┘
```

**What to check**:
- ✅ Table displays properly
- ✅ All costs start at $0.00
- ✅ Limits are shown correctly

---

### Test 2: Chat Service (Core Feature - ~$0.01 cost)
**Why second**: Tests basic provider integration and routing

```bash
python3 -m cli.main chat "What is 2+2?"
```

**Expected Output**:
```
╭──────────── 💬 Chat ────────────╮
│ Message: What is 2+2?           │
╰─────────────────────────────────╯

⠋ Initializing providers...
⠙ Creating chat session...
⠹ Sending message...

╭──────────────────────────────────╮
│ Assistant:                        │
│                                  │
│ 2 + 2 equals 4.                 │
╰──────────────────────────────────╯

Model: claude-sonnet-4-20250514 | Provider: anthropic | Tokens: 25 | Cost: $0.0012 | Latency: 0.85s

Today's total: $0.0012
```

**What to check**:
- ✅ Progress spinner shows each step
- ✅ Response from Claude Sonnet appears
- ✅ Cost is calculated and displayed
- ✅ Today's total updates
- ✅ No errors in console

**Try different messages**:
```bash
# Test conversation understanding
python3 -m cli.main chat "Explain async/await in Python in one sentence"

# Test code generation
python3 -m cli.main chat "Write a Python function to check if a number is prime"

# Test reasoning
python3 -m cli.main chat "Why is the sky blue?"
```

---

### Test 3: System Status Check (No Cost)
**Why third**: Validates infrastructure health

```bash
python3 -m cli.main status
```

**Expected Output**:
```
╭─────── System Status Check ──────╮
│ Docker Compose is running ✓      │
╰──────────────────────────────────╯

Environment Variables:
✓ ANTHROPIC_API_KEY: sk-ant-xxx...
✓ OPENAI_API_KEY: sk-xxx...
✓ GOOGLE_API_KEY: AIxxx...

Service URLs:
📊 Grafana: http://localhost:3001
📈 Prometheus: http://localhost:9091
🔍 Jaeger: http://localhost:16686
💾 ChromaDB: http://localhost:8002
```

**What to check**:
- ✅ All API keys show as set (✓)
- ✅ Docker Compose is running
- ✅ All service URLs are displayed

---

### Test 4: Chat with Fallback Testing (~$0.005 cost)
**Purpose**: Test smart routing and fallback logic

```bash
# This should use Claude Sonnet (primary)
python3 -m cli.main chat "Short test" --model auto
```

**What to check**:
- ✅ Provider shown is "anthropic"
- ✅ Model is "claude-sonnet-4-20250514"

**Advanced**: If you want to test fallback manually, you can temporarily remove ANTHROPIC_API_KEY from .env and retry. It should automatically fall back to Gemini.

---

### Test 5: Cost Tracking After Usage (~$0 cost)
**Purpose**: Verify cost accumulation

```bash
python3 -m cli.main costs --breakdown
```

**Expected Output**:
```
╭───── Cost Tracking Dashboard ─────╮
╰───────────────────────────────────╯

┏━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━┓
┃ Window           ┃ Total Cost ┃ Limit  ┃
┡━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━┩
│ Current Request  │ $0.0000    │ $1.00  │
│ Current Hour     │ $0.0025    │ $10.00 │
│ Today            │ $0.0025    │ $50.00 │
└──────────────────┴────────────┴────────┘

Breakdown by Provider:
┏━━━━━━━━━━━━┳━━━━━━━━━━┓
┃ Provider   ┃ Cost     ┃
┡━━━━━━━━━━━━╇━━━━━━━━━━┩
│ anthropic  │ $0.0025  │
└────────────┴──────────┘
```

**What to check**:
- ✅ Hourly and daily costs have updated
- ✅ Breakdown shows anthropic with accumulated costs
- ✅ Costs match sum of previous chat commands

---

### Test 6: Vision Service (Advanced - ~$0.02-0.05 cost)
**Purpose**: Test document processing with GPT-4o

**First, create a test image**:
```bash
# Option 1: Use Python to create a simple test image
python3 -c "
from PIL import Image, ImageDraw, ImageFont
img = Image.new('RGB', (400, 200), color='white')
d = ImageDraw.Draw(img)
d.text((10, 10), 'Test Invoice\nTotal: \$100.00\nDate: 2025-10-30', fill='black')
img.save('/tmp/test_invoice.png')
print('Created: /tmp/test_invoice.png')
"
```

**Then test vision extraction**:
```bash
python3 -m cli.main vision extract /tmp/test_invoice.png --type invoice
```

**Expected Output**:
```
╭─────── 🔭 Vision ──────────────╮
│ Operation: extract             │
│ File: /tmp/test_invoice.png    │
│ Type: invoice                  │
╰────────────────────────────────╯

⠋ Initializing vision service...
⠙ Creating vision service...
⠹ Loading document: test_invoice.png...
⠸ Processing document...

Result:
{
  "text": "Test Invoice\nTotal: $100.00\nDate: 2025-10-30",
  "extracted_data": {
    "total": 100.00,
    "date": "2025-10-30"
  }
}

Cost: $0.0234
```

**What to check**:
- ✅ Document loads successfully
- ✅ GPT-4o extracts text correctly
- ✅ Cost is tracked
- ✅ JSON output is well-formatted

**Note**: If you don't have a test image, skip this for now. Vision is more complex and requires actual image files.

---

### Test 7: Reasoning Service (Advanced - ~$0.03-0.08 cost)
**Purpose**: Test o1-mini complex reasoning

```bash
python3 -m cli.main reason "Plan a simple todo app architecture" --detail high
```

**Expected Output**:
```
╭──────── 🧠 Reasoning ───────────╮
│ Problem: Plan a simple todo... │
│ Detail: high                    │
╰─────────────────────────────────╯

⠋ Initializing reasoning service...
⠙ Creating reasoning plan...
⠹ Reasoning about problem...

Reasoning Plan:
╭────────────────────────────────────────────────────╮
│ TaskPlan(                                          │
│   steps=[                                          │
│     PlanStep(                                      │
│       step_number=1,                               │
│       description="Design database schema",        │
│       dependencies=[],                             │
│       estimated_complexity="medium"                │
│     ),                                             │
│     PlanStep(                                      │
│       step_number=2,                               │
│       description="Create REST API",               │
│       dependencies=[1],                            │
│       estimated_complexity="medium"                │
│     ),                                             │
│     ...                                            │
│   ]                                                │
│ )                                                  │
╰────────────────────────────────────────────────────╯
```

**What to check**:
- ✅ Multi-step plan is generated
- ✅ Dependencies between steps are shown
- ✅ Reasoning appears logical
- ✅ Cost is higher (o1-mini uses more tokens)

---

### Test 8: Monitoring URLs (No Cost)
**Purpose**: Verify observability stack

```bash
python3 -m cli.main monitor
```

**Expected Output**:
```
╭─── System Metrics URLs ───╮
│                            │
│ 📊 Grafana: http://localhost:3001 │
│    Dashboard for visualizing...     │
│                                     │
│ 📈 Prometheus: http://localhost:9091│
│    Raw metrics and queries          │
│                                     │
│ 🔍 Jaeger: http://localhost:16686  │
│    Distributed tracing              │
╰─────────────────────────────────────╯
```

**Then open in browser**:
```bash
# Open Grafana
open http://localhost:3001
# Login: admin/admin

# Open Prometheus
open http://localhost:9091

# Open ChromaDB
open http://localhost:8002
```

**What to check**:
- ✅ Grafana loads and shows dashboards
- ✅ Prometheus shows metrics targets
- ✅ ChromaDB API responds

---

## 🧪 Advanced Testing Scenarios

### Scenario 1: Cost Limit Testing
**Purpose**: Verify cost limits work

```bash
# Check current limits
grep COST_LIMIT .env

# Run multiple cheap requests to approach warn threshold
for i in {1..10}; do
  python3 -m cli.main chat "Hi" --model auto
done

# Check costs
python3 -m cli.main costs --breakdown
```

**What to check**:
- ✅ Costs accumulate correctly
- ✅ Warning appears if approaching limits
- ✅ Breakdown shows all requests

### Scenario 2: Fallback Testing
**Purpose**: Test automatic fallback to Gemini

```bash
# Temporarily rename Anthropic key to simulate failure
mv .env .env.backup
cp .env.backup .env
sed -i.bak 's/ANTHROPIC_API_KEY=.*/ANTHROPIC_API_KEY=invalid/' .env

# Try chat (should fallback to Gemini)
python3 -m cli.main chat "Hello"

# Restore original .env
mv .env.backup .env
```

**What to check**:
- ✅ Falls back to Gemini automatically
- ✅ Provider shown is "google"
- ✅ Lower cost (Gemini is cheaper)

### Scenario 3: Error Handling
**Purpose**: Verify graceful error messages

```bash
# Test with invalid file path
python3 -m cli.main vision extract /nonexistent/file.pdf

# Test with missing required argument
python3 -m cli.main chat

# Test with invalid model
python3 -m cli.main chat "Hi" --model invalid_model
```

**What to check**:
- ✅ Clear error messages
- ✅ No stack traces shown to user
- ✅ Helpful hints provided

---

## 📊 What to Look For (Success Criteria)

### Visual UI Elements (Rich Formatting)
- ✅ **Panels**: Bordered boxes for input/output
- ✅ **Spinners**: Animated progress indicators
- ✅ **Tables**: Well-formatted cost/status tables
- ✅ **Colors**: Green for success, red for errors, yellow for warnings
- ✅ **Progress**: Step-by-step status updates

### Functional Requirements
- ✅ **Responses**: Relevant AI responses to queries
- ✅ **Cost Tracking**: Accurate penny-level tracking
- ✅ **Routing**: Correct provider selection
- ✅ **Fallback**: Automatic fallback on failures
- ✅ **Error Handling**: Graceful errors with helpful messages

### Performance
- ✅ **Latency**: Responses in 1-3 seconds for simple queries
- ✅ **Docker**: Services start in 3-5 seconds
- ✅ **CLI**: Commands respond immediately

---

## 🐛 Common Issues & Solutions

### Issue 1: "No module named 'providers'"
**Solution**:
```bash
# Make sure you're in the right directory
cd /Users/andrew/Projects/AGENTS/local_assistant

# Activate environment
source .venv/bin/activate

# Verify packages are installed
python3 -c "import providers; print('OK')"
```

### Issue 2: "Connection refused" errors
**Solution**:
```bash
# Check Docker services are running
docker-compose ps

# Restart if needed
docker-compose down && docker-compose up -d

# Wait 10 seconds for health checks
sleep 10
```

### Issue 3: High costs displayed
**Solution**:
- This is expected! GPT-4o and Claude Sonnet cost $2.50-$3.00 per 1M tokens
- Each short chat is $0.001-$0.005
- Vision extraction is $0.02-$0.05
- Reasoning with o1-mini is $0.03-$0.10
- Daily limit is $50, hourly is $10

### Issue 4: API rate limits
**Solution**:
```bash
# Wait 60 seconds between requests if you hit limits
# Or use cost_optimized strategy for Gemini (cheaper, higher limits)
python3 -m cli.main chat "Hi" --model gemini
```

---

## 📈 Expected Costs for Full Testing

| Test | Estimated Cost | Risk |
|------|---------------|------|
| Test 1: Cost Tracking | $0.00 | None |
| Test 2: Basic Chat | $0.01 | Low |
| Test 3: System Status | $0.00 | None |
| Test 4: Fallback Test | $0.005 | Low |
| Test 5: Cost Check | $0.00 | None |
| Test 6: Vision (optional) | $0.03 | Low |
| Test 7: Reasoning (optional) | $0.08 | Medium |
| Test 8: Monitoring | $0.00 | None |
| **TOTAL** | **~$0.13** | **Very Low** |

**Budget**: You have $50/day limit, so full testing costs <0.3% of daily budget.

---

## ✅ Testing Checklist

**Basic Tests** (Required - 10 min):
- [ ] Test 1: Cost tracking baseline
- [ ] Test 2: Chat service with short message
- [ ] Test 3: System status check
- [ ] Test 5: Cost tracking after usage

**Intermediate Tests** (Recommended - 10 min):
- [ ] Test 4: Multiple chat messages
- [ ] Test 8: Open monitoring URLs in browser
- [ ] Advanced Scenario 1: Multiple requests to test cost accumulation

**Advanced Tests** (Optional - 15 min):
- [ ] Test 6: Vision service (if you have test images)
- [ ] Test 7: Reasoning service
- [ ] Advanced Scenario 2: Fallback testing
- [ ] Advanced Scenario 3: Error handling

---

## 🎓 After Testing

### If Everything Works
1. Celebrate! 🎉 You have a working AI assistant!
2. Review costs: `python3 -m cli.main costs --breakdown`
3. Explore Grafana: http://localhost:3001
4. Read usage examples in `/Users/andrew/Projects/AGENTS/local_assistant/DEPLOYMENT_READY.md`

### If Something Fails
1. Check the error message carefully
2. Verify API keys in `.env`
3. Check Docker services: `docker-compose ps`
4. Review logs: `docker-compose logs <service-name>`
5. Consult troubleshooting section above

### Next Steps
1. Write custom workflows
2. Add more providers
3. Create Grafana dashboards
4. Increase test coverage
5. Deploy to production

---

## 📞 Need Help?

**Check These Files**:
- `/Users/andrew/Projects/AGENTS/local_assistant/DEPLOYMENT_READY.md` - Complete usage guide
- `/Users/andrew/Projects/AGENTS/local_assistant/IMPLEMENTATION_COMPLETE.md` - Architecture details
- `/Users/andrew/Projects/AGENTS/local_assistant/docs/development/sprints/01_setup/DEV_LOG.md` - Development history

**Common Commands Reference**:
```bash
# System status
python3 -m cli.main status

# View all commands
python3 -m cli.main --help

# View command help
python3 -m cli.main chat --help

# Check costs
python3 -m cli.main costs

# Restart Docker
docker-compose restart

# View Docker logs
docker-compose logs -f
```

---

**Your UI is ready! Start with Test 1 (costs) and Test 2 (chat) to validate everything works.** 🚀

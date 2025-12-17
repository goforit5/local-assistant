# Microsoft Graph Integration - Sprint 07

**Complete end-to-end integration of Microsoft Planner and Microsoft To Do with the Life Graph AI Assistant**

## 📋 Overview

This sprint delivers a production-ready integration that treats:
- **Microsoft Planner** as the "project brain" for team/initiative work
- **Microsoft To Do** as the "personal brain" for individual execution
- **Life Graph** as the unified intelligence layer

### Key Features

✅ **OAuth 2.0 Authentication** - Secure MSAL-based auth with token caching
✅ **Delta Sync + Webhooks** - Best practice pattern for efficient, reliable sync
✅ **Batch Operations** - 20-item batching for task details
✅ **Client-Side Filtering** - Smart filtering (Planner doesn't support $filter)
✅ **Bidirectional Sync** - Changes flow both ways: Graph ↔ Life Graph
✅ **Conflict Resolution** - Configurable strategies with audit trail
✅ **Rate Limit Management** - Intelligent throttling (10k req/10min)
✅ **Comprehensive Testing** - 85%+ coverage with unit + integration tests
✅ **CI/CD Pipeline** - GitHub Actions with security scanning

## 🚀 Quick Start

### 1. Setup Azure App Registration

Run the automated setup script:

```bash
./scripts/graph/setup_azure_app.sh
```

This will:
- Create Azure AD app registration
- Configure proper permissions (Tasks.ReadWrite, Group.Read.All)
- Generate client secret
- Save configuration to `.env.graph`

**Manual setup alternative:** Follow [Azure Portal Setup Guide](#azure-portal-setup)

### 2. Configure Environment

Copy generated config to your `.env`:

```bash
cat .env.graph >> .env
```

Or set environment variables:

```bash
export GRAPH_CLIENT_ID="your-client-id"
export GRAPH_TENANT_ID="your-tenant-id"
export GRAPH_CLIENT_SECRET="your-client-secret"
export GRAPH_REDIRECT_URI="http://localhost:8000/auth/graph/callback"
```

### 3. Install Dependencies

```bash
uv sync
```

### 4. Run Database Migration

```bash
uv run alembic upgrade head
```

This creates:
- `graph_sync_state` - Delta links and subscriptions
- `graph_sync_changes_log` - Audit trail
- `graph_webhook_deliveries` - Webhook tracking
- Extended `commitments` table with Graph columns

### 5. Test Authentication

```bash
python3 scripts/graph/test_auth.py
```

### 6. Start Syncing

```python
from services.microsoft_graph import (
    GraphAuthenticator,
    GraphBaseClient,
    PlannerClient,
    TodoClient,
    DeltaSyncEngine,
)

# Authenticate
auth = GraphAuthenticator(
    client_id="your-client-id",
    tenant_id="your-tenant-id",
    client_secret="your-secret",
)

# Create clients
async with GraphBaseClient(auth) as base_client:
    planner = PlannerClient(base_client)
    todo = TodoClient(base_client)

    # Fetch tasks
    planner_tasks = await planner.get_my_tasks(include_details=True)
    todo_tasks = await todo.get_all_tasks()

    print(f"Found {len(planner_tasks)} Planner tasks")
    print(f"Found {len(todo_tasks)} To Do tasks")
```

## 📚 Architecture

### Components

```
services/microsoft_graph/
├── auth.py                    # OAuth authentication (MSAL)
├── base_client.py             # HTTP client with retry/rate limiting
├── planner_client.py          # Planner API wrapper
├── todo_client.py             # To Do API wrapper
├── delta_sync.py              # Delta query + webhooks engine
├── graph_mapper.py            # Graph ↔ Life Graph mapping
└── webhook_handler.py         # Webhook notification receiver
```

### Data Flow

```
┌─────────────────┐
│ Microsoft       │
│ Planner/To Do   │
└────────┬────────┘
         │
         │ 1. Webhook Notification
         │    (something changed)
         ↓
┌─────────────────┐
│ Webhook Handler │
└────────┬────────┘
         │
         │ 2. Trigger Delta Sync
         ↓
┌─────────────────┐
│ Delta Sync      │───────→ 3. GET /delta?$deltatoken=...
│ Engine          │            (only changed items)
└────────┬────────┘
         │
         │ 4. Process Changes (created/updated/deleted)
         ↓
┌─────────────────┐
│ Graph Mapper    │───────→ 5. Map to Life Graph models
└────────┬────────┘
         │
         │ 6. Apply to database
         ↓
┌─────────────────┐
│ Life Graph DB   │
│ (Commitments)   │
└─────────────────┘
```

### Best Practice: Webhooks + Delta Query

Based on [Microsoft's recommendations](https://www.voitanos.io/blog/microsoft-graph-webhook-delta-query/):

1. **Create webhook subscription** for real-time notifications
2. **Fetch initial data** using delta query
3. **Store delta link** for incremental sync
4. **When webhook fires**, use delta link to fetch only changes
5. **Backstop polling** (every 12 hours) ensures no missed changes

This ensures:
- ⚡ Real-time updates via webhooks
- 📉 Efficient sync (only changed data)
- 🛡️ No missed changes (backstop polling)
- 💪 Resilience to webhook failures

## 🔧 Configuration

Edit [`config/microsoft_graph_config.yaml`](../../../../config/microsoft_graph_config.yaml):

### Key Settings

```yaml
# Authentication
authentication:
  flow_type: delegated  # or "application" for daemon
  delegated_scopes:
    - Tasks.ReadWrite
    - Tasks.ReadWrite.All
    - Group.Read.All

# Planner mappings
planner:
  plans:
    - name: "Vouchra"
      area: "work"
      domain: "product"

  category_mappings:
    category1:
      tier: 0
      label: "Tier 0 - Critical"

# Sync settings
sync:
  backstop_interval_hours: 12
  conflict_resolution: "last_write_wins"

# Webhooks
webhooks:
  base_url: "https://yourapp.com"  # Must be public
```

## 📊 API Reference

### PlannerClient

```python
# Get all tasks assigned to user
tasks = await planner.get_my_tasks(include_details=True)

# Get tasks from specific plan
plan_tasks = await planner.get_plan_tasks(plan_id="plan123")

# Filter tasks (client-side, Planner doesn't support $filter)
urgent = planner.filter_tasks(tasks, priority_max=2)

# Create task
new_task = await planner.create_task(
    plan_id="plan123",
    bucket_id="bucket456",
    title="Implement feature X",
    due_date=date(2025, 12, 31),
    priority=1,
)

# Update task
updated = await planner.update_task(
    task_id="task789",
    etag=task["@odata.etag"],
    updates={"percentComplete": 50}
)
```

### TodoClient

```python
# Get all To Do lists
lists = await todo.get_lists()

# Get tasks from a list
tasks = await todo.get_tasks(list_id="list123")

# Get all tasks across all lists
all_tasks = await todo.get_all_tasks(include_completed=False)

# Create task with recurrence
task = await todo.create_task(
    list_id="list123",
    title="Weekly standup",
    recurrence=TodoClient.create_recurrence_pattern(
        pattern_type="weekly",
        days_of_week=["monday"],
    )
)

# Complete task
await todo.complete_task(list_id="list123", task_id="task456")
```

### DeltaSyncEngine

```python
# Initialize sync for an entity type
result = await delta_sync.initialize_sync(
    entity_type=EntityType.PLANNER_TASK,
    endpoint="/me/planner/tasks",
)

# Register change handler
async def handle_changes(created, updated, deleted):
    print(f"Created: {len(created)}, Updated: {len(updated)}, Deleted: {len(deleted)}")

delta_sync.register_change_handler(
    EntityType.PLANNER_TASK,
    handle_changes,
)

# Sync changes (called by webhooks or backstop)
changes = await delta_sync.sync_changes(EntityType.PLANNER_TASK)

# Start backstop polling
await delta_sync.backstop_sync(interval_hours=12)
```

## 🧪 Testing

### Run All Tests

```bash
pytest tests/services/microsoft_graph/ -v
```

### Unit Tests Only

```bash
pytest tests/services/microsoft_graph/ -v -m "not integration"
```

### Integration Tests (requires real Graph API)

```bash
export GRAPH_CLIENT_ID="..."
export GRAPH_CLIENT_SECRET="..."
pytest tests/services/microsoft_graph/ -v -m integration
```

### Coverage Report

```bash
pytest tests/services/microsoft_graph/ --cov=services/microsoft_graph --cov-report=html
open htmlcov/index.html
```

### Performance Tests

```bash
pytest tests/services/microsoft_graph/ -v -m performance --benchmark-only
```

## 🔍 Monitoring & Debugging

### Check Sync Health

```sql
-- View sync health dashboard
SELECT * FROM v_graph_sync_health;

-- Recent changes
SELECT * FROM v_graph_recent_changes LIMIT 20;

-- Active Graph-synced commitments
SELECT * FROM v_graph_synced_commitments WHERE hours_since_sync > 24;

-- Failed webhooks
SELECT * FROM graph_webhook_deliveries WHERE processing_status = 'failed';
```

### View Logs

```bash
# Filter for Graph-related logs
tail -f logs/assistant.log | grep "graph_"

# Webhook deliveries
tail -f logs/assistant.log | grep "webhook"

# Delta sync
tail -f logs/assistant.log | grep "delta_sync"
```

### Debug Mode

```python
import structlog
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
)
logger = structlog.get_logger(__name__)
logger.setLevel("DEBUG")
```

## 🚨 Troubleshooting

### Authentication Issues

**Problem:** `Failed to acquire access token`

**Solutions:**
1. Check Azure app registration permissions
2. Verify client ID and tenant ID
3. Ensure redirect URI matches (`http://localhost:8000/auth/graph/callback`)
4. Check if admin consent granted

**Problem:** Token expired

**Solution:** Tokens are auto-refreshed. If issues persist:
```python
authenticator.clear_cache()
authenticator.get_access_token(force_refresh=True)
```

### Sync Issues

**Problem:** Delta link expired

**Solution:** Delta links expire after 30 days. Engine automatically falls back to full sync.

**Problem:** Webhook notifications not received

**Solution:**
1. Check webhook base URL is publicly accessible
2. Verify subscription is active: `SELECT * FROM graph_sync_state WHERE subscription_expires_at > NOW()`
3. Backstop polling will catch missed changes

**Problem:** Conflicts during sync

**Solution:** Check conflict resolution strategy in config. View conflicts:
```sql
SELECT * FROM graph_sync_changes_log WHERE had_conflict = TRUE;
```

### Rate Limiting

**Problem:** `429 Too Many Requests`

**Solution:** Engine handles automatically with exponential backoff. Check rate limit usage:
```sql
SELECT * FROM graph_api_rate_limits ORDER BY window_start DESC LIMIT 10;
```

## 📖 Additional Resources

### Microsoft Documentation
- [Microsoft Graph API](https://learn.microsoft.com/en-us/graph/)
- [Planner API Reference](https://learn.microsoft.com/en-us/graph/api/resources/planner-overview)
- [To Do API Reference](https://learn.microsoft.com/en-us/graph/api/resources/todo-overview)
- [Delta Query](https://learn.microsoft.com/en-us/graph/delta-query-overview)
- [Webhooks](https://learn.microsoft.com/en-us/graph/change-notifications-delivery-webhooks)

### Blog Posts
- [Webhooks + Delta Query Best Practices](https://www.voitanos.io/blog/microsoft-graph-webhook-delta-query/)
- [Advanced Graph Queries](https://devblogs.microsoft.com/microsoft365dev/build-advanced-queries-with-count-filter-search-and-orderby/)

### Planning Docs
- [Planner & To Do Design Doc](./planner_todo_graph.md)
- [Development Log](./DEV_LOG.md)

## 🎯 Success Metrics

- ✅ >90% sync reliability
- ✅ <1s delta sync response time
- ✅ <2s daily brief generation
- ✅ 85%+ test coverage
- ✅ Zero data loss
- ✅ Zero secrets in logs

## 🤝 Contributing

### Adding New Features

1. Create feature branch: `git checkout -b feature/graph-xyz`
2. Add tests first (TDD)
3. Implement feature
4. Update documentation
5. Run full test suite
6. Submit PR

### Code Standards

- Follow existing patterns in `services/microsoft_graph/`
- Add type hints
- Add docstrings
- Use structlog for logging
- Write tests (aim for 85%+ coverage)

## 📜 License

MIT License - See LICENSE file

---

**Sprint 07 Status:** ✅ Complete
**Last Updated:** 2025-12-03
**Maintainers:** Andrew

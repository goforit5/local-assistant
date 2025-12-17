Software Development Session Initialization

## 📋 Sprint-Based Development Workflow

This project uses a **structured sprint system** with daily dev logs. Follow this workflow to start each development session:

### 1. Orient to Sprint Structure
- **Sprint folder**: `docs/development/sprints/`
- **Current sprints**:
  - `01_setup/` - ✅ Complete (AI Assistant MVP)
  - `02_lifegraph_foundation/` - Foundation & Database (Days 1-5)
  - `03_lifegraph_services/` - Core Services (Days 6-10)
  - `04_lifegraph_api_ui/` - API & UI (Days 11-15)
  - `05_lifegraph_production/` - Production Ready (Days 16-20)
  - `06_document_viewer_bbox/` - Document Viewer with BBox

### 2. Start Development Session

**Read current sprint DEV_LOG** to determine progress:
1. Scan **Development Session Timeline** section for latest completed day
2. Find first incomplete day/task with `[ ]` checkbox
3. Review **Day X** section for:
   - Tasks & subtasks
   - Acceptance criteria
   - Files to create/modify
   - Technical notes

**Check supporting docs** (if applicable):
- `MIGRATION_GUIDE.md` (Sprint 02) - Database migration reference
- `TESTING_GUIDE.md` (Sprint 01) - Testing patterns
- Planning docs in `planning/` folder

### 3. Development Workflow


# 1. Implement tasks from DEV_LOG
# 2. Run tests after each change
# 3. Run linting
# 4. Update DEV_LOG with:
#    - Completed tasks (check boxes)
#    - Files created/modified
#    - Technical decisions
#    - Challenges encountered

# 5. Mark day complete when all acceptance criteria met


### 4. Daily Completion Checklist

Before marking day complete:
- [ ] All tasks completed
- [ ] All acceptance criteria met
- [ ] Tests pass (`pytest`)
- [ ] Linting clean (`ruff check`)
- [ ] DEV_LOG updated with changes
- [ ] Technical decisions documented

### 5. Key Instructions

- **Update DEV_LOG in real-time**: Track progress as you work
- **Follow existing patterns**: Check Sprint 01 for reference implementation
- **No-stop implementation**: All details documented in DEV_LOGs
- **Daily focus**: Complete one day at a time, verify before moving on
- **Test continuously**: Run tests after each significant change

## 📚 Essential Reading

Before starting each sprint, review:
1. Sprint's `DEV_LOG.md` - Daily task breakdown
2. Previous sprint's `DEV_LOG.md` - Patterns and decisions
3. Relevant planning docs - Architecture and specs
4. Supporting guides (MIGRATION_GUIDE, TESTING_GUIDE, etc.)
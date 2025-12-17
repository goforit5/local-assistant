# Local Assistant UI Testing Checklist

Complete end-to-end feature testing guide for all services.

---

## 🚀 Setup

### Prerequisites
- [ ] API keys configured in `.env` (Anthropic, OpenAI, Google)
- [ ] Docker services running (`docker-compose up -d`)
- [ ] Backend dependencies installed (`pip install -e .`)
- [ ] UI dependencies installed (`cd ui && npm install`)

### Start Application
```bash
# Option 1: Python script
python3 start.py

# Option 2: Shell script
./start.sh

# Option 3: Manual
# Terminal 1: python3 -m uvicorn api.main:app --reload
# Terminal 2: cd ui && npm run dev
```

**Expected:**
- API running at http://localhost:8000
- UI running at http://localhost:3001
- API docs at http://localhost:8000/docs

---

## 1️⃣ Chat Service

### Features to Test

#### Basic Chat
- [ ] **Send simple message**
  - Enter: "Hello, introduce yourself"
  - Expected: Assistant responds with introduction
  - Model: Claude Sonnet 4.5 (primary)

- [ ] **Multi-turn conversation**
  - Message 1: "What's 2+2?"
  - Message 2: "Multiply that by 3"
  - Expected: Context maintained across messages

- [ ] **Long response**
  - Enter: "Explain quantum computing in detail"
  - Expected: Complete response rendered correctly

#### UI Elements
- [ ] Messages display correctly (user right, assistant left)
- [ ] Loading indicator shows during request
- [ ] Typing animation appears before response
- [ ] Auto-scroll to bottom on new messages
- [ ] Input disabled during loading
- [ ] Send button disabled when empty

#### Error Handling
- [ ] **API unreachable**
  - Stop API server
  - Send message
  - Expected: Error message displayed

- [ ] **Empty message**
  - Expected: Send button disabled

---

## 2️⃣ Vision Service

### Features to Test

#### Document Upload
- [ ] **Click upload zone**
  - Expected: File picker opens
  - Accepts: .pdf, .png, .jpg, .jpeg

- [ ] **Upload PDF document**
  - Select: Any multi-page PDF
  - Expected: Filename displayed in upload zone

- [ ] **Upload image**
  - Select: .png or .jpg file
  - Expected: Filename displayed

#### Extraction Types
- [ ] **Structured extraction**
  - Upload: Any document
  - Type: Structured
  - Expected: Organized text output

- [ ] **Invoice extraction**
  - Upload: Invoice PDF/image
  - Type: Invoice
  - Expected: Vendor, date, items, totals extracted

- [ ] **OCR extraction**
  - Upload: Image with text
  - Type: OCR
  - Expected: All visible text extracted

- [ ] **Tables extraction**
  - Upload: Document with tables
  - Type: Tables
  - Expected: Tables in markdown format

#### Processing
- [ ] **Extract button disabled** when no file selected
- [ ] **Loading state** shows "Processing..."
- [ ] **Result card** displays after completion
- [ ] **Metadata shown**: Pages, Cost, Model
- [ ] **Error handling**: Invalid file type

#### Test Files Needed
- Sample invoice PDF
- Image with clear text
- Multi-page PDF with tables
- Corrupted/invalid file (for error testing)

---

## 3️⃣ Reasoning Service

### Features to Test

#### Problem Solving
- [ ] **Simple problem**
  - Problem: "How do I reverse a string in Python?"
  - Expected: Code solution with explanation

- [ ] **Complex problem**
  - Problem: "Design a distributed cache system with fault tolerance"
  - Max Steps: 10
  - Detail: High
  - Expected: Multi-step reasoning with architecture

- [ ] **Math problem**
  - Problem: "Solve for x: 2x + 5 = 15"
  - Expected: Step-by-step solution

#### Settings
- [ ] **Max steps slider** (1-20)
  - Test: Set to 5, 10, 15
  - Expected: Reflected in API request

- [ ] **Detail level dropdown**
  - Options: Low, Medium, High
  - Expected: Changes request parameter

#### UI Elements
- [ ] Button disabled when textarea empty
- [ ] Loading state: "Reasoning..."
- [ ] Result displays in pre-formatted text
- [ ] Metadata: Steps, Cost, Model shown
- [ ] Solution is scrollable for long responses

#### Error Cases
- [ ] Empty problem statement
- [ ] Very long problem (5000+ chars)
- [ ] Invalid parameters

---

## 4️⃣ Computer Use Service

### Features to Test

#### Instructions
- [ ] **Browser automation**
  - Instruction: "Search for Python tutorials on Google"
  - Environment: Browser
  - Expected: Simulated action plan

- [ ] **Desktop automation**
  - Instruction: "Open Calculator and compute 50 * 30"
  - Environment: Desktop Mac
  - Expected: Step-by-step actions

- [ ] **Form filling**
  - Instruction: "Fill out contact form with test data"
  - Expected: Safety warnings for sensitive actions

#### Environment Selection
- [ ] **Browser** selected by default
- [ ] **Desktop Mac** selectable
- [ ] **Desktop Windows** selectable
- [ ] Selection reflected in API request

#### Safety Settings
- [ ] **Require confirmation** checkbox
  - Default: Checked
  - Toggle: On/Off works

- [ ] **Audit logging** checkbox
  - Default: Checked
  - Toggle: On/Off works

- [ ] Safety card has warning styling (orange border)

#### Results
- [ ] Result displays action plan
- [ ] Metadata shows: Actions count, Cost, Model
- [ ] Safety checks displayed (all false for safe instructions)

#### Error Cases
- [ ] Empty instruction
- [ ] Potentially dangerous instruction (check safety warnings)

---

## 5️⃣ Costs Dashboard

### Features to Test

#### Summary Stats
- [ ] **Today's cost** displays correctly
  - Expected: $4.67 (or actual from API)

- [ ] **This Week** displays
  - Expected: $23.14 (mock data)

- [ ] **Total requests** shown
  - Expected: 190 (or actual)

- [ ] **Average cost** calculated
  - Expected: $0.025 (total / requests)

#### Service Breakdown
- [ ] **Chat service** row
  - Shows: Requests count, Cost, Model name

- [ ] **Vision service** row
  - Shows: Requests count, Cost, Model name

- [ ] **Reasoning service** row
  - Shows: Requests count, Cost, Model name

- [ ] **Computer Use service** row
  - Shows: Requests count, Cost, Model name

#### Cost Limits
- [ ] **Per Request limit** shown ($1.00)
- [ ] **Per Hour limit** shown ($10.00)
- [ ] **Per Day limit** shown ($50.00)

#### Data Updates
- [ ] Stats update after chat message sent
- [ ] Stats update after vision extraction
- [ ] Stats update after reasoning task
- [ ] Breakdown refreshes on view load

---

## 6️⃣ Sidebar & Navigation

### Features to Test

#### Navigation
- [ ] **Chat tab** - switches to chat view
- [ ] **Vision tab** - switches to vision view
- [ ] **Reasoning tab** - switches to reasoning view
- [ ] **Computer Use tab** - switches to computer view
- [ ] **Costs tab** - switches to costs view

#### Active States
- [ ] Active tab highlighted in blue
- [ ] Active tab has white text
- [ ] Inactive tabs gray
- [ ] Hover states work on all tabs

#### Footer Stats
- [ ] **Requests count** updates after operations
- [ ] **Cost** updates after operations
- [ ] Icons display correctly

---

## 7️⃣ API Integration

### Health Check
- [ ] Visit http://localhost:8000/api/health
  - Expected: `{"status": "healthy", "version": "0.1.0"}`

### API Docs
- [ ] Visit http://localhost:8000/docs
  - Expected: Interactive Swagger UI
  - All endpoints listed: chat, vision, reasoning, computer, costs

### Endpoints Testing (via UI)
- [ ] `POST /api/chat/` - Chat messages work
- [ ] `POST /api/vision/extract` - Document upload works
- [ ] `POST /api/reasoning/solve` - Problem solving works
- [ ] `POST /api/computer/execute` - Computer tasks work
- [ ] `GET /api/costs/summary` - Stats load correctly
- [ ] `GET /api/costs/breakdown` - Breakdown loads
- [ ] `GET /api/costs/limits` - Limits load

---

## 8️⃣ Cross-Feature Testing

### Cost Tracking Integration
- [ ] **Chat message** increments request count
- [ ] **Vision extraction** adds to costs
- [ ] **Reasoning task** adds to costs
- [ ] **Computer use** adds to costs
- [ ] Dashboard reflects all operations

### Concurrent Usage
- [ ] Send chat message + upload document simultaneously
- [ ] Multiple tabs open with different features
- [ ] Rapid successive requests

---

## 9️⃣ Performance & UX

### Loading States
- [ ] All buttons show loading text when active
- [ ] Loading indicators visible during requests
- [ ] No UI freezing during operations

### Responsiveness
- [ ] UI renders correctly at different window sizes
- [ ] Sidebar stays fixed
- [ ] Content scrolls properly
- [ ] Mobile viewport (if applicable)

### Animations
- [ ] Typing indicator animates smoothly
- [ ] Messages fade in
- [ ] Hover effects smooth
- [ ] Transitions feel natural

---

## 🔟 Error Scenarios

### Network Issues
- [ ] **API offline**
  - Stop backend
  - Try any operation
  - Expected: User-friendly error

- [ ] **Slow network**
  - Simulate delay
  - Expected: Loading states persist

### Invalid Inputs
- [ ] **Empty inputs** - buttons disabled
- [ ] **Invalid file types** - error shown
- [ ] **Oversized files** - error shown

### API Errors
- [ ] **500 errors** - gracefully handled
- [ ] **Rate limits** - user notified
- [ ] **Missing API keys** - error shown

---

## 📊 Production Readiness

### Configuration
- [ ] Environment variables loaded correctly
- [ ] CORS configured for UI origin
- [ ] API key validation works
- [ ] Cost limits enforced

### Security
- [ ] No API keys exposed in UI
- [ ] File uploads validated
- [ ] Safety checks enabled for computer use
- [ ] Audit logging works

### Monitoring
- [ ] Costs tracked accurately
- [ ] Request counts correct
- [ ] Model usage logged
- [ ] Error logging works

---

## ✅ Sign-Off Checklist

### All Features Working
- [ ] Chat service fully functional
- [ ] Vision service fully functional
- [ ] Reasoning service fully functional
- [ ] Computer Use service fully functional
- [ ] Costs dashboard accurate

### Quality
- [ ] No console errors
- [ ] No broken UI elements
- [ ] All loading states work
- [ ] Error handling robust

### Documentation
- [ ] README updated
- [ ] API keys documented
- [ ] Setup instructions clear
- [ ] Known issues documented

---

## 🐛 Bug Tracking Template

```markdown
**Feature:** [Chat/Vision/Reasoning/Computer/Costs]
**Action:** [What you did]
**Expected:** [What should happen]
**Actual:** [What actually happened]
**Reproducible:** [Yes/No]
**Console Errors:** [Any errors]
**Screenshots:** [If applicable]
```

---

**Testing Complete!** 🎉

Total Features: 50+
All services integrated and working end-to-end.

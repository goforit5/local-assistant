# Life Graph - User Guide

**Version**: 1.0.0
**Last Updated**: November 2025
**Status**: Production Ready

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Uploading Documents](#uploading-documents)
3. [Understanding Results](#understanding-results)
4. [Commitments Dashboard](#commitments-dashboard)
5. [Vendor History](#vendor-history)
6. [Filtering and Sorting](#filtering-and-sorting)
7. [Exporting Data](#exporting-data)
8. [FAQs](#faqs)
9. [Troubleshooting](#troubleshooting)

---

## Getting Started

### What is Life Graph?

Life Graph is an **intelligent document processing system** that automatically:
- ✅ Extracts data from invoices, receipts, and contracts
- ✅ Identifies vendors and matches them to existing records
- ✅ Creates actionable commitments with priority scores
- ✅ Maintains complete audit trail of all actions

### Accessing the Application

**Web Interface**:
```
http://localhost:5173
```

**API Documentation**:
```
http://localhost:8000/docs
```

---

## Uploading Documents

### Supported Document Types

- **Invoices**: Vendor bills, service invoices, utility bills
- **Receipts**: Purchase receipts, payment confirmations
- **Contracts**: Service agreements, vendor contracts
- **Forms**: Tax forms, legal documents

### Supported File Formats

- **PDF** (`.pdf`) - Recommended
- **Images** (`.jpg`, `.png`) - For scanned documents

### How to Upload

1. **Navigate to Upload Page**
   - Click "Upload Document" button in main menu
   - Or drag-and-drop onto the upload area

2. **Select Document Type**
   - Choose extraction type: Invoice, Receipt, or Contract
   - This helps the system extract the right fields

3. **Upload File**
   - Click "Browse" or drag file into drop zone
   - Wait for processing (typically 2-5 seconds)

4. **Review Results**
   - See extracted data, vendor match, and commitment

---

## Understanding Results

After uploading a document, you'll see a **result card** with three sections:

### 1. Vendor Card

Shows the identified vendor information:

**Matched Existing Vendor** 🎯:
```
┌─────────────────────────────────────┐
│ Clipboard Health (Twomagnets Inc.) │
│ ✓ Matched Existing (95% confidence)│
│ P.O. Box 103125, Pasadena CA       │
│ hello@clipboardhealth.com          │
│                                     │
│ [View History] [View Documents]    │
└─────────────────────────────────────┘
```

**Created New Vendor** ✨:
```
┌─────────────────────────────────────┐
│ New Vendor LLC                      │
│ ⭐ Created New Vendor                │
│ 123 Main St, City, State           │
│                                     │
│ [Edit Details]                     │
└─────────────────────────────────────┘
```

**What the confidence score means**:
- **90-100%**: High confidence match (automatically approved)
- **75-89%**: Medium confidence (review recommended)
- **<75%**: Low confidence (likely new vendor)

### 2. Commitment Card

Shows the obligation created from the invoice:

```
┌─────────────────────────────────────┐
│ Pay Invoice #240470                 │
│ Priority: 85 🔴 HIGH                 │
│                                     │
│ Reason:                             │
│ "Due in 2 days, legal risk,        │
│  $12,419.83"                        │
│                                     │
│ Due: Feb 28, 2024 (in 2 days)     │
│ Amount: $12,419.83                  │
│                                     │
│ [Mark as Fulfilled] [View Timeline]│
└─────────────────────────────────────┘
```

**Priority color coding**:
- 🔴 **Red (75-100)**: High priority - needs immediate attention
- 🟡 **Yellow (50-74)**: Medium priority - address soon
- 🟢 **Green (0-49)**: Low priority - no urgency

**Priority factors**:
- ⏰ **Time Pressure**: How soon is it due?
- ⚠️ **Severity/Risk**: Finance, legal, health (higher = more important)
- 💰 **Amount**: Higher amounts = higher priority
- ⏱️ **Effort**: Estimated time to complete
- 🔗 **Dependency**: Blocked by other commitments?
- ⭐ **User Preference**: Manual boost flag

### 3. Extraction Card

Shows technical details about the extraction:

```
┌─────────────────────────────────────┐
│ Extraction Details                  │
│                                     │
│ Model: GPT-4o                       │
│ Cost: $0.0048                       │
│ Pages: 2                            │
│ Duration: 1.8s                      │
│                                     │
│ [Download Original PDF]             │
└─────────────────────────────────────┘
```

---

## Commitments Dashboard

The **Commitments Dashboard** is your central hub for managing all obligations.

### Accessing the Dashboard

1. Click "Commitments" in the main menu
2. Or navigate to `http://localhost:5173/commitments`

### Dashboard Layout

```
┌─────────────────────────────────────────────────────────┐
│                  COMMITMENTS DASHBOARD                   │
├─────────────────────────────────────────────────────────┤
│  Filters:                                                │
│  State: [Active ▼]  Domain: [All ▼]  Priority: [50+]   │
│                                                          │
│  Sort: [Priority ▼]  Results: 15 commitments  [Refresh]│
├─────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────┐                   │
│  │ Pay Invoice #240470              │ Priority: 85 🔴  │
│  │ Clipboard Health                 │                   │
│  │ Due: Feb 28, 2024 (in 2 days)  │                   │
│  │ Amount: $12,419.83               │                   │
│  │ [Mark as Fulfilled]              │                   │
│  └─────────────────────────────────┘                   │
│                                                          │
│  ┌─────────────────────────────────┐                   │
│  │ Pay Invoice #240471              │ Priority: 72 🟡  │
│  │ Another Vendor                   │                   │
│  │ Due: Mar 15, 2024               │                   │
│  │ [Mark as Fulfilled]              │                   │
│  └─────────────────────────────────┘                   │
└─────────────────────────────────────────────────────────┘
```

### Quick Actions

**Mark as Fulfilled**:
- Click "Mark as Fulfilled" button
- Commitment state changes to "fulfilled"
- Timestamp recorded for audit trail

**View Timeline**:
- See all interactions related to this commitment
- View upload history, matches, and state changes

---

## Vendor History

### Viewing Vendor Details

1. Click on vendor name in any result card
2. Or navigate to Vendors page and search

### Vendor Detail Page

```
┌─────────────────────────────────────────────────────────┐
│ Clipboard Health (Twomagnets Inc.)                      │
│ P.O. Box 103125, Pasadena CA                           │
│ hello@clipboardhealth.com                               │
├─────────────────────────────────────────────────────────┤
│ Statistics:                                              │
│ • Total Documents: 47                                    │
│ • Active Commitments: 3                                  │
│ • Total Amount: $156,429.18                             │
├─────────────────────────────────────────────────────────┤
│ Recent Documents:                                        │
│ • Invoice #240470 - Feb 26, 2024 - $12,419.83          │
│ • Invoice #240469 - Feb 12, 2024 - $11,287.45          │
│ • Invoice #240468 - Jan 28, 2024 - $13,105.22          │
└─────────────────────────────────────────────────────────┘
```

---

## Filtering and Sorting

### Filter Options

#### By State
- **Active**: Commitments not yet fulfilled
- **Fulfilled**: Completed commitments
- **Canceled**: Canceled commitments
- **Paused**: Temporarily paused

#### By Domain
- **Finance**: Bills, invoices, payments
- **Legal**: Contracts, agreements
- **Health**: Medical bills, insurance
- **Personal**: Personal obligations
- **Work**: Work-related commitments

#### By Priority
- **High (75+)**: Critical items
- **Medium (50-74)**: Important items
- **Low (<50)**: Non-urgent items

### Sort Options

- **Priority (High to Low)**: Default - most urgent first
- **Due Date (Soonest First)**: Time-based sorting
- **Amount (High to Low)**: Value-based sorting
- **Recently Created**: Newest first

---

## Exporting Data

### Timeline Export

Export your complete audit trail to CSV or JSON:

1. Navigate to Interactions page
2. Set date range (optional)
3. Choose format: CSV or JSON
4. Click "Export"

**CSV Format**:
```csv
id,type,entity,cost,duration,timestamp,metadata
abc123,document_upload,document,0.0048,1850,2024-02-26T10:30:00Z,"{...}"
def456,vendor_match,vendor,0.0000,45,2024-02-26T10:30:01Z,"{...}"
```

**JSON Format**:
```json
[
  {
    "id": "abc123",
    "type": "document_upload",
    "entity_type": "document",
    "entity_id": "uuid",
    "cost": 0.0048,
    "duration_ms": 1850,
    "timestamp": "2024-02-26T10:30:00Z",
    "metadata": {...}
  }
]
```

---

## FAQs

### Q: How does vendor matching work?

**A**: The system uses a 5-tier cascade:
1. Exact tax ID match (100% confidence)
2. Exact normalized name (95%)
3. Fuzzy name match >90% similarity
4. Address + name combination >80%
5. Manual review queue (<80%)

### Q: Can I upload the same file twice?

**A**: Yes! The system uses **content-addressable storage** (SHA-256 hashing). If you upload the same file twice, it will:
- Detect duplication automatically
- Not re-extract data (saves cost!)
- Create a new signal pointing to existing document

### Q: How is priority calculated?

**A**: Priority is a weighted score (0-100) based on 6 factors:
- **Time Pressure (30%)**: Days until due
- **Severity/Risk (25%)**: Domain importance
- **Amount (15%)**: Dollar value
- **Effort (15%)**: Estimated hours
- **Dependency (10%)**: Blockers
- **User Preference (5%)**: Manual boost

### Q: What happens if vendor matching fails?

**A**: If confidence is below 80%, the system:
- Creates a new vendor record
- Tags it for manual review
- Allows you to merge vendors later

### Q: Can I edit vendor details?

**A**: Yes! Click "Edit Details" on any vendor card to:
- Update name, email, phone, address
- Add tax ID for future matching
- Add notes

### Q: How do I search for commitments?

**A**: Use the filters on Commitments Dashboard:
1. Select state (active, fulfilled, etc)
2. Select domain (finance, legal, etc)
3. Adjust priority slider
4. Results update automatically

---

## Troubleshooting

### Problem: Upload is slow (>10 seconds)

**Possible Causes**:
- Large PDF file (>10 MB)
- Multiple pages (>20 pages)
- Vision API rate limit

**Solutions**:
- Compress PDF before upload
- Split multi-page documents
- Wait 30 seconds between uploads

### Problem: Vendor not matched correctly

**Causes**:
- Vendor name differs significantly
- No tax ID on invoice
- Address format differs

**Solutions**:
- Manually merge vendors in Vendors page
- Add tax ID to vendor record
- Update vendor name to standardized format

### Problem: Priority seems wrong

**Causes**:
- Due date not extracted correctly
- Amount parsed incorrectly
- Domain not set

**Solutions**:
- Manually edit commitment
- Adjust priority manually
- Set domain explicitly

### Problem: Cannot mark as fulfilled

**Causes**:
- Commitment already fulfilled
- Database connection issue
- Permission issue

**Solutions**:
- Refresh page
- Check commitment state
- Contact administrator

---

## Support

### Getting Help

- **Documentation**: Check [Developer Guide](DEVELOPER_GUIDE.md) for technical details
- **API Reference**: Visit `/docs` for interactive API documentation
- **GitHub Issues**: Report bugs or request features

### Contacting Support

- **Email**: support@example.com
- **GitHub**: [Repository Issues](https://github.com/...)
- **Slack**: #lifegraph-support

---

**Enjoy using Life Graph!** 🚀

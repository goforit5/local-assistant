# Interactive Document Viewer with Bounding Box Highlighting

## Overview

An interactive document viewer that displays PDFs with clickable bounding boxes highlighting extracted data fields. When hovering over fields in the sidebar, the corresponding areas in the PDF are highlighted, providing visual feedback for invoice data extraction.

## Architecture

### Object-Oriented Design

Following DRY (Don't Repeat Yourself) principles with reusable class abstractions:

#### Backend Classes
- **Schema Definition** (`schemas/invoice_with_bbox.json`)
  - Reusable `BoundingBox` definition using JSON Schema `$defs`
  - `FieldWithBBox` wrapper for any field type
  - Normalized coordinates (0-1) for resolution independence

#### Frontend Classes

**DocumentViewer Component** (`ui/src/components/DocumentViewer.jsx`):
- `CoordinateTransformer`: Handles coordinate system conversions
  - `normalizedToPixels()`: Converts normalized (0-1) coords to pixel coordinates
  - `pixelsToNormalized()`: Inverse transformation
- `BoundingBoxOverlay`: SVG layer for rendering interactive boxes
- `PDFPageRenderer`: Manages individual page rendering with react-pdf
- `DocumentViewer`: Main orchestrator component

**ExtractedDataSidebar Component** (`ui/src/components/ExtractedDataSidebar.jsx`):
- `FieldIconMapper`: Maps field types to icons and colors
  - `getIcon()`: Returns appropriate icon component
  - `getFieldColor()`: Returns color scheme by field type
- `FieldFormatter`: Handles value formatting
  - `format()`: Formats currency, dates, and other field types
- `FieldItem`: Displays individual fields with hover support
- `CollapsibleSection`: Groups related fields

### Data Flow

```
1. User uploads PDF → Creates blob URL
2. API extracts with bbox → Returns JSON with normalized coordinates
3. DocumentViewer renders PDF → react-pdf provides page dimensions
4. CoordinateTransformer converts → Normalized coords → Pixel coords
5. BoundingBoxOverlay renders → SVG rectangles at pixel positions
6. User hovers sidebar field → State updates → Highlights box in PDF
```

## Features

### ✅ Implemented

1. **PDF Rendering**
   - Multi-page support with react-pdf
   - Zoom controls (50% - 300%)
   - Responsive page dimensions

2. **Interactive Bounding Boxes**
   - Normalized coordinate system (resolution-independent)
   - SVG overlays with hover effects
   - Per-page bbox filtering

3. **Data Extraction**
   - GPT-4o vision API with structured output
   - Optional bbox extraction flag
   - Invoice schema with bbox support

4. **Sidebar Navigation**
   - Collapsible sections (Vendor, Customer, Invoice, Financial, Line Items)
   - Color-coded field types
   - Formatted values (currency, dates)
   - Page number indicators

5. **Bi-directional Highlighting**
   - Hover sidebar → Highlights PDF bbox
   - Hover PDF bbox → Highlights sidebar field

6. **Responsive Design**
   - Desktop: Side-by-side layout
   - Tablet: Stacked with scrolling
   - Mobile: Full-width sections

7. **Unit Tests**
   - Vitest + React Testing Library
   - Component unit tests
   - Utility class tests
   - 100% class coverage

## Usage

### API Endpoint

```bash
POST /api/vision/extract
Content-Type: multipart/form-data

file: <PDF file>
extract_type: invoice
detail: auto
include_bbox: true
```

### Response Format

```json
{
  "VendorName": {
    "value": "Acme Corp",
    "bbox": {
      "page": 1,
      "x": 0.1,
      "y": 0.05,
      "width": 0.3,
      "height": 0.04
    }
  },
  "InvoiceTotal": {
    "value": 1500.50,
    "bbox": {
      "page": 2,
      "x": 0.7,
      "y": 0.9,
      "width": 0.2,
      "height": 0.03
    }
  }
}
```

### Component Usage

```jsx
import DocumentViewer from './components/DocumentViewer'
import ExtractedDataSidebar from './components/ExtractedDataSidebar'

function App() {
  const [hoveredField, setHoveredField] = useState(null)

  return (
    <div className="viewer-layout">
      <DocumentViewer
        pdfUrl={pdfUrl}
        boundingBoxes={prepareBoundingBoxes(extractedData)}
        hoveredField={hoveredField}
        onFieldHover={setHoveredField}
      />
      <ExtractedDataSidebar
        extractedData={extractedData}
        hoveredField={hoveredField}
        onFieldHover={setHoveredField}
      />
    </div>
  )
}
```

## Testing

### Run Tests

```bash
# Run tests once
npm test

# Watch mode
npm test -- --watch

# With coverage
npm run test:coverage

# UI mode
npm run test:ui
```

### Test Coverage

- ✅ DocumentViewer component rendering
- ✅ CoordinateTransformer class methods
- ✅ BoundingBox overlay rendering
- ✅ Zoom controls
- ✅ ExtractedDataSidebar rendering
- ✅ FieldIconMapper class
- ✅ FieldFormatter class
- ✅ Hover interactions
- ✅ Collapsible sections

## Dependencies

### Frontend
- `react-pdf`: PDF rendering
- `pdfjs-dist`: PDF.js library
- `lucide-react`: Icons

### Backend
- `pdf2image`: PDF to image conversion
- `PIL`: Image processing

### Testing
- `vitest`: Test runner
- `@testing-library/react`: React testing utilities
- `@testing-library/jest-dom`: DOM matchers
- `jsdom`: DOM environment

## Best Practices Applied

### 1. DRY (Don't Repeat Yourself)
- Reusable `BoundingBox` schema definition
- Shared `CoordinateTransformer` class
- Generic `FieldWithBBox` pattern
- Centralized formatting in `FieldFormatter`

### 2. Object-Oriented Design
- Static utility classes for pure functions
- Encapsulated components with clear responsibilities
- Composition over inheritance

### 3. Separation of Concerns
- Coordinate logic separated from rendering
- Formatting logic separated from display
- State management centralized in parent

### 4. Testability
- Pure functions for easy unit testing
- Exported classes for testing
- Mocked external dependencies
- Comprehensive test coverage

### 5. Performance
- Normalized coordinates reduce recalculation
- SVG overlays (performant for many boxes)
- React memoization opportunities
- Efficient re-rendering

## Configuration

### Backend Schema Path
```python
# api/routes/vision.py
schema_path = "schemas/invoice_with_bbox.json"
```

### PDF.js Worker
```javascript
// ui/src/components/DocumentViewer.jsx
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`
```

### Color Scheme
```javascript
// ui/src/components/ExtractedDataSidebar.jsx
FieldIconMapper.getFieldColor(fieldName) {
  // Financial: Green (#48BB78)
  // Dates: Blue (#4299E1)
  // Addresses: Orange (#ED8936)
  // Parties: Purple (#9F7AEA)
}
```

## Future Enhancements

### Potential Improvements
1. **Click to zoom** - Click bbox to zoom and center on that area
2. **Confidence scores** - Visual indicators for extraction confidence
3. **Multi-select** - Select multiple fields to compare
4. **Export annotations** - Export bbox data for training
5. **Edit mode** - Correct extracted data inline
6. **Field validation** - Real-time validation of extracted values
7. **Comparison mode** - Compare extracted vs. actual document values
8. **Keyboard navigation** - Arrow keys to navigate between fields

## Troubleshooting

### PDF not rendering
- Check PDF.js worker URL
- Verify blob URL is created correctly
- Check browser console for errors

### Bounding boxes misaligned
- Verify normalized coordinates are 0-1
- Check page dimensions are correct
- Ensure coordinate transformation is applied

### Tests failing
- Run `npm install` to ensure dependencies
- Check vitest config setup
- Verify mock implementations

## License

Part of the local_assistant project.

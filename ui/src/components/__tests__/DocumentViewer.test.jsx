import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import '@testing-library/jest-dom'
import DocumentViewer from '../DocumentViewer'

// Mock react-pdf
vi.mock('react-pdf', () => ({
  Document: ({ children, onLoadSuccess }) => {
    // Simulate document load
    setTimeout(() => onLoadSuccess({ numPages: 2 }), 0)
    return <div data-testid="mock-document">{children}</div>
  },
  Page: ({ pageNumber, onLoadSuccess }) => {
    // Simulate page load
    setTimeout(() => {
      if (onLoadSuccess) {
        onLoadSuccess({
          getViewport: () => ({ width: 800, height: 1000 })
        })
      }
    }, 0)
    return <div data-testid={`mock-page-${pageNumber}`}>Page {pageNumber}</div>
  },
  pdfjs: {
    GlobalWorkerOptions: { workerSrc: '' },
    version: '3.0.0'
  }
}))

describe('DocumentViewer', () => {
  const mockPdfUrl = 'blob:http://localhost/test.pdf'
  const mockBoundingBoxes = [
    {
      fieldName: 'InvoiceTotal',
      bbox: { page: 1, x: 0.1, y: 0.2, width: 0.3, height: 0.05 }
    },
    {
      fieldName: 'VendorName',
      bbox: { page: 1, x: 0.1, y: 0.1, width: 0.4, height: 0.05 }
    }
  ]

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders empty state when no PDF URL provided', () => {
    render(<DocumentViewer pdfUrl={null} />)
    expect(screen.getByText('No document loaded')).toBeInTheDocument()
  })

  it('renders document when PDF URL is provided', async () => {
    render(<DocumentViewer pdfUrl={mockPdfUrl} />)
    expect(await screen.findByTestId('mock-document')).toBeInTheDocument()
  })

  it('renders zoom controls', () => {
    render(<DocumentViewer pdfUrl={mockPdfUrl} />)
    expect(screen.getByText('-')).toBeInTheDocument()
    expect(screen.getByText('+')).toBeInTheDocument()
    expect(screen.getByText('Reset')).toBeInTheDocument()
  })

  it('displays correct initial zoom level', () => {
    render(<DocumentViewer pdfUrl={mockPdfUrl} />)
    expect(screen.getByText('100%')).toBeInTheDocument()
  })

  it('passes bounding boxes to overlay component', () => {
    const { container } = render(
      <DocumentViewer
        pdfUrl={mockPdfUrl}
        boundingBoxes={mockBoundingBoxes}
      />
    )
    // Component should render without errors with bounding boxes
    expect(container).toBeInTheDocument()
  })

  it('handles field hover callback', () => {
    const handleHover = vi.fn()
    render(
      <DocumentViewer
        pdfUrl={mockPdfUrl}
        boundingBoxes={mockBoundingBoxes}
        onFieldHover={handleHover}
      />
    )
    expect(handleHover).not.toHaveBeenCalled()
  })
})

describe('CoordinateTransformer', () => {
  it('transforms normalized coordinates to pixels correctly', async () => {
    const { CoordinateTransformer } = await import('../DocumentViewer')

    const bbox = { x: 0.5, y: 0.5, width: 0.2, height: 0.1 }
    const pageWidth = 800
    const pageHeight = 1000

    const result = CoordinateTransformer.normalizedToPixels(bbox, pageWidth, pageHeight)

    expect(result).toEqual({
      x: 400,
      y: 500,
      width: 160,
      height: 100
    })
  })

  it('transforms pixel coordinates to normalized correctly', async () => {
    const { CoordinateTransformer } = await import('../DocumentViewer')

    const coords = { x: 400, y: 500, width: 160, height: 100 }
    const pageWidth = 800
    const pageHeight = 1000

    const result = CoordinateTransformer.pixelsToNormalized(coords, pageWidth, pageHeight)

    expect(result).toEqual({
      x: 0.5,
      y: 0.5,
      width: 0.2,
      height: 0.1
    })
  })

  it('handles edge case with zero dimensions', async () => {
    const { CoordinateTransformer } = await import('../DocumentViewer')

    const bbox = { x: 0, y: 0, width: 0, height: 0 }
    const result = CoordinateTransformer.normalizedToPixels(bbox, 800, 1000)

    expect(result).toEqual({
      x: 0,
      y: 0,
      width: 0,
      height: 0
    })
  })
})

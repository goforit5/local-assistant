import { useState, useRef, useEffect } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'

// Configure PDF.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`

// Note: CSS imports removed as they're not needed for basic functionality
// The component provides its own styling via App.css

/**
 * BoundingBox data structure
 * @typedef {Object} BoundingBox
 * @property {number} page - 1-indexed page number
 * @property {number} x - Normalized x coordinate (0-1)
 * @property {number} y - Normalized y coordinate (0-1)
 * @property {number} width - Normalized width (0-1)
 * @property {number} height - Normalized height (0-1)
 */

/**
 * Coordinate transformer for bounding boxes
 */
export class CoordinateTransformer {
  /**
   * Convert normalized coordinates to pixel coordinates
   * @param {BoundingBox} bbox - Normalized bounding box
   * @param {number} pageWidth - Page width in pixels
   * @param {number} pageHeight - Page height in pixels
   * @returns {Object} Pixel coordinates {x, y, width, height}
   */
  static normalizedToPixels(bbox, pageWidth, pageHeight) {
    return {
      x: bbox.x * pageWidth,
      y: bbox.y * pageHeight,
      width: bbox.width * pageWidth,
      height: bbox.height * pageHeight
    }
  }

  /**
   * Convert pixel coordinates to normalized coordinates
   * @param {Object} coords - Pixel coordinates
   * @param {number} pageWidth - Page width in pixels
   * @param {number} pageHeight - Page height in pixels
   * @returns {BoundingBox} Normalized bounding box
   */
  static pixelsToNormalized(coords, pageWidth, pageHeight) {
    return {
      x: coords.x / pageWidth,
      y: coords.y / pageHeight,
      width: coords.width / pageWidth,
      height: coords.height / pageHeight
    }
  }
}

/**
 * BoundingBoxOverlay component - renders SVG overlay with bounding boxes
 */
function BoundingBoxOverlay({ boundingBoxes, pageNumber, pageWidth, pageHeight, hoveredField, onBoxHover, debugMode = false }) {
  if (!boundingBoxes || boundingBoxes.length === 0) return null

  // Filter boxes for current page
  const pageBoxes = boundingBoxes.filter(box => box.bbox?.page === pageNumber)

  return (
    <svg
      className="bbox-overlay"
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: pageWidth,
        height: pageHeight,
        pointerEvents: 'none'
      }}
    >
      {pageBoxes.map((box, idx) => {
        const pixels = CoordinateTransformer.normalizedToPixels(
          box.bbox,
          pageWidth,
          pageHeight
        )

        const isHovered = hoveredField === box.fieldName

        // Debug logging for misalignment issues
        if (isHovered) {
          console.log('🎯 Rendering bbox:', {
            fieldName: box.fieldName,
            normalized: box.bbox,
            pixels,
            viewport: { width: pageWidth, height: pageHeight }
          })
        }

        // Only render bbox if it's being hovered or debug mode
        if (!isHovered && !debugMode) return null

        return (
          <g key={`bbox-${idx}`}>
            <rect
              x={pixels.x}
              y={pixels.y}
              width={pixels.width}
              height={pixels.height}
              fill={isHovered ? "rgba(66, 153, 225, 0.3)" : "rgba(255, 0, 0, 0.1)"}
              stroke={isHovered ? "#4299E1" : "#ff0000"}
              strokeWidth={isHovered ? 2 : 1}
              strokeDasharray={isHovered ? "none" : "5,5"}
              style={{
                pointerEvents: 'none',
                transition: 'all 0.2s ease'
              }}
            />
            {debugMode && (
              <text
                x={pixels.x}
                y={pixels.y - 5}
                fontSize="10"
                fill="#ff0000"
                style={{ pointerEvents: 'none' }}
              >
                {box.fieldName}
              </text>
            )}
          </g>
        )
      })}
    </svg>
  )
}

/**
 * PDFPageRenderer - handles rendering of individual PDF pages
 */
function PDFPageRenderer({ pageNumber, scale, onPageLoad, children }) {
  const [dimensions, setDimensions] = useState(null)

  const handleLoadSuccess = (page) => {
    const viewport = page.getViewport({ scale })
    const dims = {
      width: viewport.width,
      height: viewport.height
    }
    setDimensions(dims)
    onPageLoad(pageNumber, dims)
  }

  return (
    <div className="pdf-page-container" style={{ position: 'relative', marginBottom: '20px' }}>
      <Page
        pageNumber={pageNumber}
        scale={scale}
        onLoadSuccess={handleLoadSuccess}
        renderTextLayer={true}
        renderAnnotationLayer={false}
        renderMode="canvas"
        canvasBackground="white"
      />
      {dimensions && children(dimensions)}
    </div>
  )
}

/**
 * Main DocumentViewer component
 */
export default function DocumentViewer({
  pdfUrl,
  boundingBoxes = [],
  hoveredField = null,
  onFieldHover = () => {}
}) {
  const [numPages, setNumPages] = useState(null)
  const [currentPage, setCurrentPage] = useState(1)
  const [scale, setScale] = useState(1.0)
  const [pageDimensions, setPageDimensions] = useState({})
  const [debugMode, setDebugMode] = useState(false)
  const containerRef = useRef(null)

  const onDocumentLoadSuccess = ({ numPages }) => {
    setNumPages(numPages)
    setCurrentPage(1) // Reset to first page
  }

  const handlePageLoad = (pageNum, dimensions) => {
    setPageDimensions(prev => ({
      ...prev,
      [pageNum]: dimensions
    }))
  }

  const handleZoomIn = () => setScale(prev => Math.min(prev + 0.2, 3.0))
  const handleZoomOut = () => setScale(prev => Math.max(prev - 0.2, 0.5))
  const handleZoomReset = () => setScale(1.0)

  const handlePrevPage = () => setCurrentPage(prev => Math.max(prev - 1, 1))
  const handleNextPage = () => setCurrentPage(prev => Math.min(prev + 1, numPages || 1))

  if (!pdfUrl) {
    return (
      <div className="document-viewer-empty">
        <p>No document loaded</p>
      </div>
    )
  }

  return (
    <div className="document-viewer" ref={containerRef}>
      <div className="document-viewer-controls">
        <button onClick={handleZoomOut} className="zoom-btn">-</button>
        <span className="zoom-level">{Math.round(scale * 100)}%</span>
        <button onClick={handleZoomIn} className="zoom-btn">+</button>
        <button onClick={handleZoomReset} className="zoom-btn">Reset</button>
        <button
          onClick={() => setDebugMode(!debugMode)}
          className="zoom-btn"
          style={{
            backgroundColor: debugMode ? '#4299E1' : undefined,
            color: debugMode ? 'white' : undefined
          }}
        >
          {debugMode ? '🐛 Debug ON' : '🐛 Debug'}
        </button>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button
            onClick={handlePrevPage}
            className="zoom-btn"
            disabled={currentPage === 1}
          >
            ← Prev
          </button>
          <span className="page-count">
            {numPages ? `Page ${currentPage} of ${numPages}` : ''}
          </span>
          <button
            onClick={handleNextPage}
            className="zoom-btn"
            disabled={currentPage === numPages}
          >
            Next →
          </button>
        </div>
      </div>

      <div className="document-viewer-content">
        <Document
          file={pdfUrl}
          onLoadSuccess={onDocumentLoadSuccess}
          loading={<div className="pdf-loading">Loading PDF...</div>}
          error={<div className="pdf-error">Failed to load PDF</div>}
        >
          {numPages && (
            <PDFPageRenderer
              key={`page-${currentPage}`}
              pageNumber={currentPage}
              scale={scale}
              onPageLoad={handlePageLoad}
            >
              {(dimensions) => (
                <BoundingBoxOverlay
                  boundingBoxes={boundingBoxes}
                  pageNumber={currentPage}
                  pageWidth={dimensions.width}
                  pageHeight={dimensions.height}
                  hoveredField={hoveredField}
                  onBoxHover={onFieldHover}
                  debugMode={debugMode}
                />
              )}
            </PDFPageRenderer>
          )}
        </Document>
      </div>
    </div>
  )
}

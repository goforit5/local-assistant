import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom'
import ExtractedDataSidebar from '../ExtractedDataSidebar'

describe('ExtractedDataSidebar', () => {
  const mockData = {
    VendorName: {
      value: 'Acme Corp',
      bbox: { page: 1, x: 0.1, y: 0.1, width: 0.3, height: 0.05 }
    },
    InvoiceId: {
      value: 'INV-12345',
      bbox: { page: 1, x: 0.5, y: 0.1, width: 0.2, height: 0.05 }
    },
    InvoiceTotal: {
      value: 1500.50,
      bbox: { page: 1, x: 0.7, y: 0.8, width: 0.2, height: 0.05 }
    },
    InvoiceDate: {
      value: '2024-01-15',
      bbox: { page: 1, x: 0.5, y: 0.2, width: 0.2, height: 0.05 }
    },
    Items: [
      {
        Description: { value: 'Widget A' },
        Amount: { value: 100.00 }
      }
    ]
  }

  it('renders empty state when no data provided', () => {
    render(<ExtractedDataSidebar extractedData={null} />)
    expect(screen.getByText('No extracted data available')).toBeInTheDocument()
  })

  it('renders extracted data title', () => {
    render(<ExtractedDataSidebar extractedData={mockData} />)
    expect(screen.getByText('Extracted Data')).toBeInTheDocument()
  })

  it('renders vendor information section', () => {
    render(<ExtractedDataSidebar extractedData={mockData} />)
    expect(screen.getByText('Vendor Information')).toBeInTheDocument()
    expect(screen.getByText('Acme Corp')).toBeInTheDocument()
  })

  it('renders invoice details section', () => {
    render(<ExtractedDataSidebar extractedData={mockData} />)
    expect(screen.getByText('Invoice Details')).toBeInTheDocument()
    expect(screen.getByText('INV-12345')).toBeInTheDocument()
  })

  it('formats currency fields correctly', () => {
    render(<ExtractedDataSidebar extractedData={mockData} />)
    expect(screen.getByText('$1500.50')).toBeInTheDocument()
  })

  it('formats date fields correctly', () => {
    render(<ExtractedDataSidebar extractedData={mockData} />)
    // Date should be formatted as "Jan 15, 2024"
    expect(screen.getByText(/Jan 15, 2024/)).toBeInTheDocument()
  })

  it('calls onFieldHover when hovering over field with bbox', () => {
    const handleHover = vi.fn()
    render(
      <ExtractedDataSidebar
        extractedData={mockData}
        onFieldHover={handleHover}
      />
    )

    const vendorField = screen.getByText('Acme Corp').closest('.field-item')
    fireEvent.mouseEnter(vendorField)
    expect(handleHover).toHaveBeenCalledWith('VendorName')

    fireEvent.mouseLeave(vendorField)
    expect(handleHover).toHaveBeenCalledWith(null)
  })

  it('does not call onFieldHover for fields without bbox', () => {
    const handleHover = vi.fn()
    const dataWithoutBbox = {
      VendorName: 'Plain Text Value'
    }

    render(
      <ExtractedDataSidebar
        extractedData={dataWithoutBbox}
        onFieldHover={handleHover}
      />
    )

    const vendorField = screen.getByText('Plain Text Value').closest('.field-item')
    fireEvent.mouseEnter(vendorField)
    expect(handleHover).not.toHaveBeenCalled()
  })

  it('highlights hovered field', () => {
    render(
      <ExtractedDataSidebar
        extractedData={mockData}
        hoveredField="VendorName"
      />
    )

    const vendorField = screen.getByText('Acme Corp').closest('.field-item')
    expect(vendorField).toHaveClass('hovered')
  })

  it('renders line items section when items present', () => {
    render(<ExtractedDataSidebar extractedData={mockData} />)
    expect(screen.getByText('Line Items (1)')).toBeInTheDocument()
  })

  it('collapses and expands sections', () => {
    render(<ExtractedDataSidebar extractedData={mockData} />)

    const lineItemsButton = screen.getByText('Line Items (1)')
    fireEvent.click(lineItemsButton)

    // Section should expand and show items
    expect(screen.getByText('Widget A')).toBeInTheDocument()
  })
})

describe('FieldIconMapper', () => {
  it('returns DollarSign icon for financial fields', async () => {
    const { FieldIconMapper } = await import('../ExtractedDataSidebar')
    const icon = FieldIconMapper.getIcon('InvoiceTotal')
    expect(icon).toBeDefined()
  })

  it('returns Calendar icon for date fields', async () => {
    const { FieldIconMapper } = await import('../ExtractedDataSidebar')
    const icon = FieldIconMapper.getIcon('InvoiceDate')
    expect(icon).toBeDefined()
  })

  it('returns correct color for field types', async () => {
    const { FieldIconMapper } = await import('../ExtractedDataSidebar')

    expect(FieldIconMapper.getFieldColor('InvoiceTotal')).toBe('#48BB78')
    expect(FieldIconMapper.getFieldColor('InvoiceDate')).toBe('#4299E1')
    expect(FieldIconMapper.getFieldColor('VendorAddress')).toBe('#ED8936')
  })
})

describe('FieldFormatter', () => {
  it('formats currency values correctly', async () => {
    const { FieldFormatter } = await import('../ExtractedDataSidebar')

    expect(FieldFormatter.format('InvoiceTotal', 1500.5)).toBe('$1500.50')
    expect(FieldFormatter.format('Amount', 100)).toBe('$100.00')
  })

  it('formats date strings correctly', async () => {
    const { FieldFormatter } = await import('../ExtractedDataSidebar')

    const formatted = FieldFormatter.format('InvoiceDate', '2024-01-15')
    expect(formatted).toMatch(/Jan 15, 2024/)
  })

  it('handles null and undefined values', async () => {
    const { FieldFormatter } = await import('../ExtractedDataSidebar')

    expect(FieldFormatter.format('AnyField', null)).toBe('N/A')
    expect(FieldFormatter.format('AnyField', undefined)).toBe('N/A')
  })

  it('returns string representation for non-special fields', async () => {
    const { FieldFormatter } = await import('../ExtractedDataSidebar')

    expect(FieldFormatter.format('VendorName', 'Acme Corp')).toBe('Acme Corp')
    expect(FieldFormatter.format('InvoiceId', 'INV-123')).toBe('INV-123')
  })
})

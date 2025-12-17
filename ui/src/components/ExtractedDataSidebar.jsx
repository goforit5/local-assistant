import { useState } from 'react'
import { ChevronDown, ChevronRight, DollarSign, FileText, Calendar, MapPin } from 'lucide-react'

/**
 * Field icon mapper - returns appropriate icon for field type
 */
export class FieldIconMapper {
  static getIcon(fieldName) {
    const iconMap = {
      // Financial fields
      'InvoiceTotal': DollarSign,
      'SubTotal': DollarSign,
      'TotalTax': DollarSign,
      'AmountDue': DollarSign,
      'Amount': DollarSign,
      'UnitPrice': DollarSign,
      'TotalDiscount': DollarSign,

      // Date fields
      'InvoiceDate': Calendar,
      'DueDate': Calendar,
      'Date': Calendar,

      // Address fields
      'VendorAddress': MapPin,
      'CustomerAddress': MapPin,
      'ShippingAddress': MapPin,

      // Default
      'default': FileText
    }

    return iconMap[fieldName] || iconMap.default
  }

  static getFieldColor(fieldName) {
    if (fieldName.includes('Total') || fieldName.includes('Amount') || fieldName.includes('Price')) {
      return '#48BB78' // Green for money
    }
    if (fieldName.includes('Date')) {
      return '#4299E1' // Blue for dates
    }
    if (fieldName.includes('Address')) {
      return '#ED8936' // Orange for addresses
    }
    if (fieldName.includes('Vendor') || fieldName.includes('Customer')) {
      return '#9F7AEA' // Purple for parties
    }
    return '#718096' // Gray for other fields
  }
}

/**
 * Field formatter - formats field values based on type
 */
export class FieldFormatter {
  static format(fieldName, value) {
    if (value === null || value === undefined) return 'N/A'

    // Currency fields
    if (fieldName.includes('Total') || fieldName.includes('Amount') || fieldName.includes('Price')) {
      if (typeof value === 'number') {
        return `$${value.toFixed(2)}`
      }
    }

    // Date fields
    if (fieldName.includes('Date') && typeof value === 'string') {
      try {
        const date = new Date(value)
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
      } catch (e) {
        return value
      }
    }

    return String(value)
  }
}

/**
 * FieldItem component - represents a single extracted field
 */
function FieldItem({ fieldName, fieldData, onHover, isHovered }) {
  // Extract actual field name from Items[X].FieldName format
  const actualFieldName = fieldName.includes('.')
    ? fieldName.split('.').pop()
    : fieldName

  const Icon = FieldIconMapper.getIcon(actualFieldName)
  const color = FieldIconMapper.getFieldColor(actualFieldName)

  // Handle both {value, bbox} structure and plain values
  const value = fieldData?.value !== undefined ? fieldData.value : fieldData
  const hasBBox = fieldData?.bbox !== undefined

  const formattedValue = FieldFormatter.format(actualFieldName, value)
  const displayName = actualFieldName.replace(/([A-Z])/g, ' $1').trim()

  return (
    <div
      className={`field-item ${isHovered ? 'hovered' : ''} ${!hasBBox ? 'no-bbox' : ''}`}
      onMouseEnter={() => hasBBox && onHover(fieldName)}
      onMouseLeave={() => hasBBox && onHover(null)}
      style={{
        padding: '12px',
        borderRadius: '6px',
        marginBottom: '8px',
        backgroundColor: isHovered ? 'rgba(66, 153, 225, 0.1)' : 'transparent',
        border: isHovered ? '1px solid #4299E1' : '1px solid transparent',
        cursor: hasBBox ? 'pointer' : 'default',
        transition: 'all 0.2s ease'
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <Icon size={16} color={color} />
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: '12px', color: '#718096', marginBottom: '2px' }}>
            {displayName}
          </div>
          <div style={{ fontSize: '14px', fontWeight: '500', color: '#2D3748' }}>
            {formattedValue}
          </div>
        </div>
        {hasBBox && (
          <div style={{ fontSize: '10px', color: '#A0AEC0' }}>
            pg {fieldData.bbox.page}
          </div>
        )}
      </div>
    </div>
  )
}

/**
 * CollapsibleSection component - groups related fields
 */
function CollapsibleSection({ title, children, defaultOpen = true }) {
  const [isOpen, setIsOpen] = useState(defaultOpen)

  return (
    <div className="collapsible-section" style={{ marginBottom: '16px' }}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '8px',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          fontSize: '14px',
          fontWeight: '600',
          color: '#2D3748',
          textAlign: 'left'
        }}
      >
        {isOpen ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        {title}
      </button>
      {isOpen && (
        <div style={{ paddingLeft: '8px', marginTop: '8px' }}>
          {children}
        </div>
      )}
    </div>
  )
}

/**
 * Main ExtractedDataSidebar component
 */
export default function ExtractedDataSidebar({ extractedData, hoveredField, onFieldHover }) {
  if (!extractedData) {
    return (
      <div className="extracted-data-sidebar empty">
        <p style={{ textAlign: 'center', color: '#A0AEC0', padding: '20px' }}>
          No extracted data available
        </p>
      </div>
    )
  }

  // Group fields by category
  const vendorFields = ['VendorName', 'VendorAddress', 'VendorTaxId']
  const customerFields = ['CustomerName', 'CustomerId', 'CustomerAddress', 'ShippingAddress']
  const invoiceFields = ['InvoiceId', 'InvoiceDate', 'DueDate', 'PurchaseOrder', 'PaymentTerms']
  const financialFields = ['SubTotal', 'TotalTax', 'TotalDiscount', 'InvoiceTotal', 'AmountDue', 'PreviousUnpaidBalance']

  const renderFields = (fieldNames) => {
    return fieldNames
      .filter(name => extractedData[name] !== undefined && extractedData[name] !== null)
      .map(name => (
        <FieldItem
          key={name}
          fieldName={name}
          fieldData={extractedData[name]}
          onHover={onFieldHover}
          isHovered={hoveredField === name}
        />
      ))
  }

  const renderLineItems = () => {
    const items = extractedData.Items
    if (!items || items.length === 0) return null

    return items.map((item, idx) => (
      <div key={`item-${idx}`} style={{
        padding: '12px',
        borderRadius: '6px',
        backgroundColor: '#F7FAFC',
        marginBottom: '8px'
      }}>
        {Object.entries(item).map(([key, value]) => {
          // Create unique identifier for line item fields
          const uniqueFieldName = `Items[${idx}].${key}`
          return (
            <FieldItem
              key={uniqueFieldName}
              fieldName={uniqueFieldName}
              fieldData={value}
              onHover={onFieldHover}
              isHovered={hoveredField === uniqueFieldName}
            />
          )
        })}
      </div>
    ))
  }

  return (
    <div className="extracted-data-sidebar" style={{
      height: '100%',
      overflowY: 'auto',
      padding: '16px',
      backgroundColor: '#FFFFFF'
    }}>
      <h3 style={{
        fontSize: '18px',
        fontWeight: '700',
        color: '#2D3748',
        marginBottom: '20px'
      }}>
        Extracted Data
      </h3>

      <CollapsibleSection title="Vendor Information" defaultOpen={true}>
        {renderFields(vendorFields)}
      </CollapsibleSection>

      <CollapsibleSection title="Customer Information" defaultOpen={true}>
        {renderFields(customerFields)}
      </CollapsibleSection>

      <CollapsibleSection title="Invoice Details" defaultOpen={true}>
        {renderFields(invoiceFields)}
      </CollapsibleSection>

      <CollapsibleSection title="Financial Summary" defaultOpen={true}>
        {renderFields(financialFields)}
      </CollapsibleSection>

      {extractedData.Items && extractedData.Items.length > 0 && (
        <CollapsibleSection title={`Line Items (${extractedData.Items.length})`} defaultOpen={false}>
          {renderLineItems()}
        </CollapsibleSection>
      )}
    </div>
  )
}

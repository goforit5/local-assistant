"""Pydantic models for structured document extraction.

OpenAI Structured Outputs requires additionalProperties: false on all objects.
We use ConfigDict(extra='forbid') to achieve this.
"""

from datetime import date
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class LineItem(BaseModel):
    """Invoice line item."""

    model_config = ConfigDict(extra='forbid')

    Date: Optional[str] = Field(None, description="Date of service or delivery (YYYY-MM-DD format)")
    Description: str = Field(..., description="Full description of the item or service")
    Quantity: Optional[float] = Field(None, description="Quantity or hours")
    Unit: Optional[str] = Field(None, description="Unit of measure (hours, each, etc.)")
    UnitPrice: Optional[float] = Field(None, description="Price per unit")
    Amount: float = Field(..., description="Total amount for this line item")
    ProductCode: Optional[str] = Field(None, description="Product or service code")
    Tax: Optional[float] = Field(None, description="Tax amount for this line item")
    TaxRate: Optional[str] = Field(None, description="Tax rate percentage")


class PaymentDetails(BaseModel):
    """Payment information."""

    model_config = ConfigDict(extra='forbid')

    BankAccountNumber: Optional[str] = None
    IBAN: Optional[str] = None
    SWIFT: Optional[str] = None
    RoutingNumber: Optional[str] = None


class TaxDetail(BaseModel):
    """Tax breakdown."""

    model_config = ConfigDict(extra='forbid')

    TaxType: Optional[str] = Field(None, description="Type of tax (Sales, VAT, GST, etc.)")
    Rate: Optional[str] = Field(None, description="Tax rate percentage")
    Amount: Optional[float] = Field(None, description="Tax amount")


class Invoice(BaseModel):
    """Complete invoice data model (Azure Document Intelligence compatible)."""

    model_config = ConfigDict(extra='forbid')

    # Vendor Information
    VendorName: str = Field(..., description="Name of the vendor or supplier")
    VendorAddress: Optional[str] = Field(None, description="Full address of the vendor")
    VendorTaxId: Optional[str] = Field(None, description="Tax ID or EIN of the vendor")

    # Customer Information
    CustomerName: Optional[str] = Field(None, description="Name of the customer or bill-to party")
    CustomerId: Optional[str] = Field(None, description="Customer account number or ID")
    CustomerAddress: Optional[str] = Field(None, description="Full billing address")
    ShippingAddress: Optional[str] = Field(None, description="Shipping address if different")

    # Invoice Details
    InvoiceId: str = Field(..., description="Unique invoice number or identifier")
    InvoiceDate: str = Field(..., description="Invoice issue date (YYYY-MM-DD format)")
    DueDate: Optional[str] = Field(None, description="Payment due date (YYYY-MM-DD format)")
    PurchaseOrder: Optional[str] = Field(None, description="Purchase order number")

    # Line Items (aggregated from ALL pages)
    Items: List[LineItem] = Field(..., description="All line items from the entire invoice")

    # Financial Totals
    SubTotal: Optional[float] = Field(None, description="Subtotal before tax and discounts")
    TotalTax: Optional[float] = Field(None, description="Total tax amount")
    TotalDiscount: Optional[float] = Field(None, description="Total discount amount")
    InvoiceTotal: float = Field(..., description="Final total amount due")
    AmountDue: Optional[float] = Field(None, description="Outstanding amount (may differ if partial payment made)")
    PreviousUnpaidBalance: Optional[float] = Field(None, description="Previous balance carried forward")

    # Payment Information
    PaymentTerms: Optional[str] = Field(None, description="Payment terms (Net 30, etc.)")
    PaymentDetails: Optional[PaymentDetails] = None
    TaxDetails: Optional[List[TaxDetail]] = None

    # Metadata
    Currency: str = Field(default="USD", description="Currency code (USD, EUR, etc.)")
    Notes: Optional[str] = Field(None, description="Additional notes or instructions")


class Receipt(BaseModel):
    """Receipt data model."""

    model_config = ConfigDict(extra='forbid')

    Merchant: str = Field(..., description="Merchant or store name")
    MerchantAddress: Optional[str] = None
    Date: str = Field(..., description="Receipt date (YYYY-MM-DD format)")
    Time: Optional[str] = None

    Items: List[LineItem] = Field(..., description="Items purchased")

    SubTotal: Optional[float] = None
    TotalTax: Optional[float] = None
    Total: float = Field(..., description="Total amount paid")

    PaymentMethod: Optional[str] = Field(None, description="Payment method used")
    Currency: str = Field(default="USD")


class Form(BaseModel):
    """Generic form data model."""

    model_config = ConfigDict(extra='forbid')

    FormType: Optional[str] = Field(None, description="Type of form")
    Fields: dict = Field(..., description="Form fields as key-value pairs")
    Checkboxes: Optional[dict] = Field(None, description="Checkbox states")
    Signatures: Optional[List[str]] = Field(None, description="Signature locations or presence")

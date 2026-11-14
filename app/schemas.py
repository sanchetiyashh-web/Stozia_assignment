"""Pydantic models describe what valid input looks like.

FastAPI uses these classes to check every request body automatically.
If the data is invalid, FastAPI replies with HTTP 422 and a list of errors,
and our endpoint code never runs. The CSV import reuses the same
QuoteCreate model, so a quote is validated the same way wherever it comes from.
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator

ALLOWED_CURRENCIES = ["USD", "EUR", "GBP", "INR", "CNY", "JPY"]


class RFQCreate(BaseModel):
    """Data needed to create an RFQ (Request For Quotation)."""

    # Remove spaces at the start/end of every text field, so "   " counts as empty.
    model_config = ConfigDict(str_strip_whitespace=True)

    item_name: str = Field(min_length=1, max_length=200)
    specification: str = Field(min_length=1, max_length=500)  # material / specification
    quantity: int = Field(gt=0, le=10_000_000)
    delivery_expectation: str = Field(min_length=1, max_length=200)  # e.g. "Within 30 days"
    notes: str = Field(default="", max_length=1000)


class QuoteCreate(BaseModel):
    """Data needed to add one supplier quote to an RFQ."""

    model_config = ConfigDict(str_strip_whitespace=True)

    supplier_name: str = Field(min_length=1, max_length=200)
    # allow_inf_nan=False rejects values like "inf" or "nan".
    unit_price: float = Field(gt=0, le=1_000_000_000, allow_inf_nan=False)
    currency: str
    lead_time_days: int = Field(ge=0, le=3650)
    payment_terms: str = Field(min_length=1, max_length=200)  # e.g. "Net 30"
    remarks: str = Field(default="", max_length=1000)

    @field_validator("currency")
    @classmethod
    def check_currency(cls, value: str) -> str:
        """Accept 'usd' or 'USD', but only from the list of supported currencies."""
        value = value.upper()
        if value not in ALLOWED_CURRENCIES:
            raise ValueError(f"must be one of {', '.join(ALLOWED_CURRENCIES)}")
        return value

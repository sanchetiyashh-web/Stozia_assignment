"""Quote comparison logic: total price and best-quote selection.

Rules:
- Total Price = Unit Price x RFQ Quantity (rounded to 2 decimals).
- The best quote is the one with the lowest total price.
- Prices in different currencies cannot be compared fairly without exchange
  rates, so the best quote is picked separately for each currency.
- If two quotes have the same total, the shorter lead time wins; if that is
  also equal, the quote that was added first wins.
"""


def build_comparison(rfq, quotes):
    """Return the RFQ, its quotes (with total_price and is_best), and a currency flag."""
    quantity = rfq["quantity"]

    rows = []
    for quote in quotes:
        row = dict(quote)
        row["total_price"] = round(quote["unit_price"] * quantity, 2)
        row["is_best"] = False
        rows.append(row)

    # Sort so that, inside each currency, the cheapest quote comes first.
    rows.sort(key=lambda row: (row["currency"], row["total_price"], row["lead_time_days"], row["id"]))

    # After sorting, the first quote we meet for each currency is the best one.
    seen_currencies = set()
    for row in rows:
        if row["currency"] not in seen_currencies:
            row["is_best"] = True
            seen_currencies.add(row["currency"])

    return {
        "rfq": dict(rfq),
        "quotes": rows,
        "mixed_currencies": len(seen_currencies) > 1,
    }

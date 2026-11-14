"""Fill the database with example RFQs and quotes.

Run with:  python seed.py
It only adds data when the database has no RFQs yet, so running it twice is safe.
"""

from app.database import get_connection, init_db, insert_quote, insert_rfq
from app.schemas import QuoteCreate, RFQCreate

SAMPLE_DATA = [
    {
        "rfq": RFQCreate(
            item_name="Steel Mounting Bracket",
            specification="Mild steel IS 2062, 5 mm thick, zinc plated",
            quantity=500,
            delivery_expectation="Within 30 days",
            notes="Drawing BRK-104 rev B attached to email",
        ),
        "quotes": [
            QuoteCreate(supplier_name="Acme Metals", unit_price=12.50, currency="USD",
                        lead_time_days=14, payment_terms="Net 30", remarks="Includes packaging"),
            QuoteCreate(supplier_name="Bharat Forge Works", unit_price=11.75, currency="USD",
                        lead_time_days=21, payment_terms="50% advance", remarks="Free delivery"),
            QuoteCreate(supplier_name="Precision Parts Co", unit_price=13.10, currency="USD",
                        lead_time_days=7, payment_terms="Net 45", remarks="ISO 9001 certified"),
        ],
    },
    {
        "rfq": RFQCreate(
            item_name="Aluminium Housing",
            specification="Aluminium 6061-T6, CNC machined, anodised black",
            quantity=200,
            delivery_expectation="By end of next month",
            notes="",
        ),
        "quotes": [
            QuoteCreate(supplier_name="Euro CNC GmbH", unit_price=41.00, currency="EUR",
                        lead_time_days=28, payment_terms="Net 30", remarks=""),
            QuoteCreate(supplier_name="Pune Precision", unit_price=3150.00, currency="INR",
                        lead_time_days=20, payment_terms="Net 15", remarks="Anodising outsourced"),
            QuoteCreate(supplier_name="Rhine Machining", unit_price=39.50, currency="EUR",
                        lead_time_days=35, payment_terms="Net 60", remarks="Tooling cost extra"),
        ],
    },
]


def seed():
    init_db()
    connection = get_connection()
    rfq_count = connection.execute("SELECT COUNT(*) FROM rfqs").fetchone()[0]
    if rfq_count > 0:
        print(f"Database already has {rfq_count} RFQ(s). Nothing was added.")
        connection.close()
        return

    for item in SAMPLE_DATA:
        rfq_id = insert_rfq(connection, item["rfq"])
        for quote in item["quotes"]:
            insert_quote(connection, rfq_id, quote)
    connection.commit()
    connection.close()
    print(f"Added {len(SAMPLE_DATA)} RFQs with sample quotes.")


if __name__ == "__main__":
    seed()

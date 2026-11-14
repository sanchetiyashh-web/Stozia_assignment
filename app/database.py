"""Everything related to the SQLite database lives in this file.

We use Python's built-in `sqlite3` module, so no extra database server or ORM
is needed. The whole database is a single file (stozia.db by default).
"""

import os
import sqlite3

from app.schemas import QuoteCreate, RFQCreate

# The database file path. It can be changed with the DATABASE_PATH
# environment variable (the tests use this to work on a temporary database).
DATABASE_PATH = os.environ.get("DATABASE_PATH", "stozia.db")


def get_connection():
    """Open a new connection to the SQLite database file."""
    # check_same_thread=False: FastAPI may run the dependency and the endpoint
    # in different worker threads. Each request still gets its own connection.
    connection = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    # Lets us read columns by name, e.g. row["item_name"].
    connection.row_factory = sqlite3.Row
    # SQLite only enforces foreign keys when this is switched on.
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def get_db():
    """FastAPI dependency: gives each request a connection and always closes it."""
    connection = get_connection()
    try:
        yield connection
    finally:
        connection.close()


def init_db():
    """Create the tables if they do not exist yet."""
    connection = get_connection()
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS rfqs (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name            TEXT    NOT NULL,
            specification        TEXT    NOT NULL,
            quantity             INTEGER NOT NULL CHECK (quantity > 0),
            delivery_expectation TEXT    NOT NULL,
            notes                TEXT    NOT NULL DEFAULT '',
            created_at           TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS quotes (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            rfq_id         INTEGER NOT NULL REFERENCES rfqs(id) ON DELETE CASCADE,
            supplier_name  TEXT    NOT NULL,
            unit_price     REAL    NOT NULL CHECK (unit_price > 0),
            currency       TEXT    NOT NULL,
            lead_time_days INTEGER NOT NULL CHECK (lead_time_days >= 0),
            payment_terms  TEXT    NOT NULL,
            remarks        TEXT    NOT NULL DEFAULT '',
            created_at     TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    connection.close()


# ---------- Small helper functions used by the API and the seed script ----------


def insert_rfq(connection, rfq: RFQCreate):
    """Insert one RFQ and return its new id. The caller must commit."""
    cursor = connection.execute(
        """
        INSERT INTO rfqs (item_name, specification, quantity, delivery_expectation, notes)
        VALUES (?, ?, ?, ?, ?)
        """,
        (rfq.item_name, rfq.specification, rfq.quantity, rfq.delivery_expectation, rfq.notes),
    )
    return cursor.lastrowid


def insert_quote(connection, rfq_id: int, quote: QuoteCreate):
    """Insert one supplier quote for an RFQ and return its new id. The caller must commit."""
    cursor = connection.execute(
        """
        INSERT INTO quotes
            (rfq_id, supplier_name, unit_price, currency, lead_time_days, payment_terms, remarks)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            rfq_id,
            quote.supplier_name,
            quote.unit_price,
            quote.currency,
            quote.lead_time_days,
            quote.payment_terms,
            quote.remarks,
        ),
    )
    return cursor.lastrowid

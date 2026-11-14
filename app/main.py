"""FastAPI application: all API endpoints, plus serving the frontend files.

Run with:  uvicorn app.main:app --reload
"""

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles

from app.comparison import build_comparison
from app.csv_import import parse_quotes_csv
from app.database import get_db, init_db, insert_quote, insert_rfq
from app.schemas import QuoteCreate, RFQCreate

MAX_CSV_SIZE_BYTES = 1_000_000  # 1 MB is plenty for a list of quotes
STATIC_FOLDER = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(title="Stozia Supplier Quote Comparison")

# Make sure the tables exist before the first request arrives.
init_db()


def get_rfq_or_404(db, rfq_id: int):
    """Load an RFQ or stop the request with a clear 404 error."""
    rfq = db.execute("SELECT * FROM rfqs WHERE id = ?", (rfq_id,)).fetchone()
    if rfq is None:
        raise HTTPException(status_code=404, detail=f"RFQ with id {rfq_id} was not found.")
    return rfq


# ------------------------------- RFQs -------------------------------


@app.get("/api/rfqs")
def list_rfqs(db=Depends(get_db)):
    """List all RFQs (newest first) with how many quotes each one has."""
    rows = db.execute(
        """
        SELECT rfqs.*, COUNT(quotes.id) AS quote_count
        FROM rfqs
        LEFT JOIN quotes ON quotes.rfq_id = rfqs.id
        GROUP BY rfqs.id
        ORDER BY rfqs.id DESC
        """
    ).fetchall()
    return [dict(row) for row in rows]


@app.post("/api/rfqs", status_code=201)
def create_rfq(rfq: RFQCreate, db=Depends(get_db)):
    """Create a new RFQ. FastAPI has already validated `rfq` using RFQCreate."""
    new_id = insert_rfq(db, rfq)
    db.commit()
    return dict(get_rfq_or_404(db, new_id))


@app.get("/api/rfqs/{rfq_id}")
def get_rfq(rfq_id: int, db=Depends(get_db)):
    """Get one RFQ."""
    return dict(get_rfq_or_404(db, rfq_id))


# ------------------------------ Quotes ------------------------------


@app.post("/api/rfqs/{rfq_id}/quotes", status_code=201)
def add_quote(rfq_id: int, quote: QuoteCreate, db=Depends(get_db)):
    """Add one supplier quote to an RFQ."""
    get_rfq_or_404(db, rfq_id)
    new_id = insert_quote(db, rfq_id, quote)
    db.commit()
    row = db.execute("SELECT * FROM quotes WHERE id = ?", (new_id,)).fetchone()
    return dict(row)


@app.get("/api/rfqs/{rfq_id}/comparison")
def compare_quotes(rfq_id: int, db=Depends(get_db)):
    """All quotes for an RFQ with total prices, cheapest first, best quote marked."""
    rfq = get_rfq_or_404(db, rfq_id)
    quotes = db.execute("SELECT * FROM quotes WHERE rfq_id = ?", (rfq_id,)).fetchall()
    return build_comparison(rfq, quotes)


@app.post("/api/rfqs/{rfq_id}/quotes/import")
def import_quotes_csv(rfq_id: int, file: UploadFile, db=Depends(get_db)):
    """Import supplier quotes from a CSV file.

    All-or-nothing: if any row is invalid, no quotes are saved and every
    problem is returned, so the user can fix the file and upload it again.
    """
    get_rfq_or_404(db, rfq_id)

    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a .csv file.")

    file_bytes = file.file.read()
    if len(file_bytes) > MAX_CSV_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="The file is too large (maximum 1 MB).")

    quotes, errors = parse_quotes_csv(file_bytes)
    if errors:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "No quotes were imported. Fix these problems and upload the file again.",
                "errors": errors,
            },
        )

    for quote in quotes:
        insert_quote(db, rfq_id, quote)
    db.commit()  # one commit for all rows: either every quote is saved or none
    return {"imported_count": len(quotes)}


# ----------------------------- Frontend -----------------------------
# Serve index.html, app.js and style.css from the "static" folder at "/".
# This must come after the API routes, otherwise it would catch /api requests.
app.mount("/", StaticFiles(directory=STATIC_FOLDER, html=True), name="frontend")

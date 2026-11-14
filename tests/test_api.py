"""API tests. Run with:  python -m pytest

Each test gets its own empty temporary database, so tests never touch stozia.db.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import database
from app.main import app

SAMPLE_DATA_FOLDER = Path(__file__).resolve().parent.parent / "sample_data"

VALID_RFQ = {
    "item_name": "Steel Bracket",
    "specification": "Mild steel, 5 mm",
    "quantity": 100,
    "delivery_expectation": "Within 30 days",
    "notes": "",
}


def make_quote(supplier_name, unit_price, currency="USD", lead_time_days=10):
    return {
        "supplier_name": supplier_name,
        "unit_price": unit_price,
        "currency": currency,
        "lead_time_days": lead_time_days,
        "payment_terms": "Net 30",
        "remarks": "",
    }


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATABASE_PATH", str(tmp_path / "test.db"))
    database.init_db()
    return TestClient(app)


@pytest.fixture
def rfq_id(client):
    response = client.post("/api/rfqs", json=VALID_RFQ)
    return response.json()["id"]


# ------------------------------- RFQs -------------------------------


def test_create_and_list_rfq(client):
    response = client.post("/api/rfqs", json=VALID_RFQ)
    assert response.status_code == 201
    created = response.json()
    assert created["item_name"] == "Steel Bracket"
    assert created["quantity"] == 100

    rfqs = client.get("/api/rfqs").json()
    assert len(rfqs) == 1
    assert rfqs[0]["quote_count"] == 0

    assert client.get(f"/api/rfqs/{created['id']}").status_code == 200


@pytest.mark.parametrize(
    "bad_field",
    [
        {"quantity": 0},
        {"quantity": -5},
        {"quantity": 2.5},
        {"quantity": "abc"},
        {"item_name": "   "},
        {"specification": ""},
    ],
)
def test_create_rfq_rejects_invalid_data(client, bad_field):
    response = client.post("/api/rfqs", json={**VALID_RFQ, **bad_field})
    assert response.status_code == 422


def test_create_rfq_rejects_missing_field(client):
    data = dict(VALID_RFQ)
    del data["delivery_expectation"]
    assert client.post("/api/rfqs", json=data).status_code == 422


def test_unknown_rfq_returns_404(client):
    assert client.get("/api/rfqs/999").status_code == 404
    assert client.get("/api/rfqs/999/comparison").status_code == 404
    assert client.post("/api/rfqs/999/quotes", json=make_quote("A", 1)).status_code == 404


# ------------------------------ Quotes ------------------------------


def test_add_quote_normalises_currency(client, rfq_id):
    response = client.post(f"/api/rfqs/{rfq_id}/quotes", json=make_quote("Acme", 12.5, currency="usd"))
    assert response.status_code == 201
    assert response.json()["currency"] == "USD"


@pytest.mark.parametrize(
    "bad_field",
    [
        {"unit_price": 0},
        {"unit_price": -1},
        {"unit_price": "free"},
        {"currency": "XYZ"},
        {"lead_time_days": -1},
        {"lead_time_days": 1.5},
        {"supplier_name": ""},
        {"payment_terms": "  "},
    ],
)
def test_add_quote_rejects_invalid_data(client, rfq_id, bad_field):
    response = client.post(f"/api/rfqs/{rfq_id}/quotes", json={**make_quote("Acme", 10), **bad_field})
    assert response.status_code == 422


# ---------------------------- Comparison ----------------------------


def test_comparison_calculates_totals_and_best_quote(client, rfq_id):
    client.post(f"/api/rfqs/{rfq_id}/quotes", json=make_quote("Expensive", 15.00))
    client.post(f"/api/rfqs/{rfq_id}/quotes", json=make_quote("Cheapest", 11.75))
    client.post(f"/api/rfqs/{rfq_id}/quotes", json=make_quote("Middle", 12.10))

    comparison = client.get(f"/api/rfqs/{rfq_id}/comparison").json()
    quotes = comparison["quotes"]

    assert [quote["supplier_name"] for quote in quotes] == ["Cheapest", "Middle", "Expensive"]
    assert [quote["total_price"] for quote in quotes] == [1175.0, 1210.0, 1500.0]  # quantity is 100
    assert [quote["is_best"] for quote in quotes] == [True, False, False]
    assert comparison["mixed_currencies"] is False


def test_comparison_tie_goes_to_shorter_lead_time(client, rfq_id):
    client.post(f"/api/rfqs/{rfq_id}/quotes", json=make_quote("Slow", 10, lead_time_days=30))
    client.post(f"/api/rfqs/{rfq_id}/quotes", json=make_quote("Fast", 10, lead_time_days=5))

    quotes = client.get(f"/api/rfqs/{rfq_id}/comparison").json()["quotes"]
    best = [quote["supplier_name"] for quote in quotes if quote["is_best"]]
    assert best == ["Fast"]


def test_comparison_with_mixed_currencies_marks_best_per_currency(client, rfq_id):
    client.post(f"/api/rfqs/{rfq_id}/quotes", json=make_quote("Euro A", 40, currency="EUR"))
    client.post(f"/api/rfqs/{rfq_id}/quotes", json=make_quote("Euro B", 39, currency="EUR"))
    client.post(f"/api/rfqs/{rfq_id}/quotes", json=make_quote("India A", 3000, currency="INR"))

    comparison = client.get(f"/api/rfqs/{rfq_id}/comparison").json()
    best = sorted(quote["supplier_name"] for quote in comparison["quotes"] if quote["is_best"])
    assert best == ["Euro B", "India A"]
    assert comparison["mixed_currencies"] is True


def test_comparison_with_no_quotes(client, rfq_id):
    comparison = client.get(f"/api/rfqs/{rfq_id}/comparison").json()
    assert comparison["quotes"] == []
    assert comparison["mixed_currencies"] is False


# ---------------------------- CSV import ----------------------------


def upload(client, rfq_id, filename, content: bytes):
    return client.post(
        f"/api/rfqs/{rfq_id}/quotes/import",
        files={"file": (filename, content, "text/csv")},
    )


def test_import_sample_csv(client, rfq_id):
    content = (SAMPLE_DATA_FOLDER / "sample_quotes.csv").read_bytes()
    response = upload(client, rfq_id, "sample_quotes.csv", content)
    assert response.status_code == 200
    assert response.json() == {"imported_count": 10}

    quotes = client.get(f"/api/rfqs/{rfq_id}/comparison").json()["quotes"]
    assert len(quotes) == 10
    assert quotes[0]["supplier_name"] == "Bharat Forge Works"  # 11.75 is the lowest price
    assert quotes[0]["is_best"] is True


def test_import_csv_with_errors_saves_nothing(client, rfq_id):
    content = (SAMPLE_DATA_FOLDER / "sample_quotes_with_errors.csv").read_bytes()
    response = upload(client, rfq_id, "bad.csv", content)
    assert response.status_code == 400

    errors = response.json()["detail"]["errors"]
    assert any(error.startswith("Line 3, supplier_name") for error in errors)
    assert any(error.startswith("Line 4, unit_price") for error in errors)
    assert any(error.startswith("Line 5, currency") for error in errors)
    assert any(error.startswith("Line 5, lead_time_days") for error in errors)

    # The valid row on line 2 must NOT have been saved either (all-or-nothing).
    assert client.get(f"/api/rfqs/{rfq_id}/comparison").json()["quotes"] == []


def test_import_csv_missing_column(client, rfq_id):
    content = b"supplier_name,unit_price,currency\nAcme,10,USD\n"
    response = upload(client, rfq_id, "quotes.csv", content)
    assert response.status_code == 400
    assert "lead_time_days" in response.json()["detail"]["errors"][0]


def test_import_csv_handles_excel_bom_and_header_case(client, rfq_id):
    content = "﻿Supplier_Name, Unit_Price,Currency,Lead_Time_Days,Payment_Terms\nAcme,10,USD,5,Net 30\n"
    response = upload(client, rfq_id, "quotes.csv", content.encode("utf-8"))
    assert response.status_code == 200
    assert response.json() == {"imported_count": 1}


@pytest.mark.parametrize(
    "filename, content",
    [
        ("quotes.txt", b"supplier_name,unit_price\n"),  # wrong file type
        ("empty.csv", b""),  # empty file
        ("header_only.csv", b"supplier_name,unit_price,currency,lead_time_days,payment_terms\n"),
        ("binary.csv", b"\xff\xfe\x00\x01"),  # not UTF-8 text
    ],
)
def test_import_rejects_bad_files(client, rfq_id, filename, content):
    response = upload(client, rfq_id, filename, content)
    assert response.status_code == 400


def test_import_into_unknown_rfq(client):
    response = upload(client, 999, "quotes.csv", b"x\n")
    assert response.status_code == 404


# ----------------------------- Frontend -----------------------------


def test_frontend_is_served(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Supplier Quote Comparison" in response.text

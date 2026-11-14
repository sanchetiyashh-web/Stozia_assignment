# Supplier Quote Comparison Tool

This is my submission for the Stozia full-stack assignment. It's a small web app where a procurement person can create an RFQ, add quotes from different suppliers, and see them side by side. The app works out the total price for each quote (unit price × RFQ quantity) and highlights the cheapest one.

I used Python with FastAPI for the backend, SQLite for storage, and a plain HTML/JavaScript page for the frontend. FastAPI serves the page too, so you only need to start one thing.

## Setup

You'll need Python 3.10 or newer. The commands below are for Windows PowerShell. On macOS or Linux, activate the venv with `source .venv/bin/activate` instead.

```powershell
cd Stovia_assignment
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If PowerShell refuses to run `Activate.ps1`, you can skip activating and call the venv's Python directly, like `.venv\Scripts\python -m uvicorn app.main:app --reload`.

## Adding sample data

```powershell
python seed.py
```

This puts two RFQs into the database with three quotes each. The second one has quotes in EUR and INR, so you can see what happens with mixed currencies. If the database already has RFQs, the script doesn't add anything, so running it twice is fine.

## Running the app

```powershell
python -m uvicorn app.main:app --reload
```

Open http://localhost:8000 for the app. FastAPI also generates API docs at http://localhost:8000/docs, where you can try every endpoint from the browser.

The database is a single file, `stozia.db`, created in the project folder the first time the app runs. To start fresh, stop the server and delete that file. You don't need any config. If you want the database somewhere else, set the `DATABASE_PATH` environment variable.

## Running the tests

```powershell
python -m pytest
```

The tests create their own temporary database, so your real data isn't touched.

## How to use it

1. On the first screen, fill in the RFQ form: item name, material/specification, quantity, delivery expectation, and notes if you have any. Click Create RFQ.
2. Click Open next to the RFQ.
3. Add quotes one at a time with the form, or import a CSV file.
4. The comparison table updates as you go. The cheapest quote shows up green with a "Best quote" label.

## Folder layout

```
app/
  main.py         API endpoints, and serves the frontend
  schemas.py      validation rules for RFQs and quotes
  database.py     SQLite connection, creating tables, insert helpers
  comparison.py   total price and picking the best quote
  csv_import.py   reading and checking CSV files
static/
  index.html, app.js, style.css    the frontend
sample_data/
  sample_quotes.csv              10 valid quotes
  sample_quotes_with_errors.csv  has mistakes on purpose, to show the error messages
tests/test_api.py   automated tests
seed.py             adds the sample RFQs
```

## Database

There are two tables. Each RFQ can have many quotes.

`rfqs`

| column | type | rules |
|---|---|---|
| id | integer | primary key |
| item_name | text | required, up to 200 characters |
| specification | text | required, up to 500 characters |
| quantity | integer | required, more than 0 |
| delivery_expectation | text | required, free text like "Within 30 days" |
| notes | text | optional |
| created_at | text | filled in automatically |

`quotes`

| column | type | rules |
|---|---|---|
| id | integer | primary key |
| rfq_id | integer | points to rfqs.id |
| supplier_name | text | required |
| unit_price | real | required, more than 0 |
| currency | text | USD, EUR, GBP, INR, CNY or JPY ("usd" is accepted too) |
| lead_time_days | integer | required, 0 or more |
| payment_terms | text | required, e.g. "Net 30" |
| remarks | text | optional |
| created_at | text | filled in automatically |

I don't store the total price. It gets calculated each time you look at the comparison, so it can't drift away from the RFQ quantity.

## API

| Method | Path | What it does |
|---|---|---|
| GET | `/api/rfqs` | list RFQs, newest first, with how many quotes each has |
| POST | `/api/rfqs` | create an RFQ |
| GET | `/api/rfqs/{rfq_id}` | get one RFQ |
| POST | `/api/rfqs/{rfq_id}/quotes` | add a quote |
| GET | `/api/rfqs/{rfq_id}/comparison` | quotes with total price and best-quote flag, cheapest first |
| POST | `/api/rfqs/{rfq_id}/quotes/import` | upload a CSV (form field name: `file`) |

### Example requests

These work in Git Bash, macOS/Linux and Command Prompt. In Windows PowerShell 5.1, type `curl.exe` instead of `curl`, because plain `curl` there points to a different command.

```bash
# create an RFQ
curl -X POST http://localhost:8000/api/rfqs -H "Content-Type: application/json" -d "{\"item_name\": \"Hex Bolt M10\", \"specification\": \"Stainless steel 304\", \"quantity\": 1000, \"delivery_expectation\": \"Within 2 weeks\", \"notes\": \"\"}"

# add a quote to RFQ 1
curl -X POST http://localhost:8000/api/rfqs/1/quotes -H "Content-Type: application/json" -d "{\"supplier_name\": \"Acme Metals\", \"unit_price\": 0.85, \"currency\": \"USD\", \"lead_time_days\": 10, \"payment_terms\": \"Net 30\", \"remarks\": \"\"}"

# compare the quotes for RFQ 1
curl http://localhost:8000/api/rfqs/1/comparison

# import the sample CSV into RFQ 1
curl -F "file=@sample_data/sample_quotes.csv" http://localhost:8000/api/rfqs/1/quotes/import
```

Here's a shortened comparison response:

```json
{
  "rfq": {"id": 1, "item_name": "Steel Mounting Bracket", "quantity": 500},
  "quotes": [
    {"supplier_name": "Bharat Forge Works", "unit_price": 11.75, "currency": "USD", "total_price": 5875.0, "is_best": true},
    {"supplier_name": "Acme Metals", "unit_price": 12.5, "currency": "USD", "total_price": 6250.0, "is_best": false}
  ],
  "mixed_currencies": false
}
```

### Errors

- 422 means the data you sent didn't pass validation, like quantity 0 or a currency the app doesn't know. This is FastAPI's standard format: `{"detail": [{"loc": ["body", "quantity"], "msg": "Input should be greater than 0"}]}`
- 404 means the RFQ doesn't exist: `{"detail": "RFQ with id 99 was not found."}`
- 400 means something was wrong with the CSV upload. When rows fail, you get the full list: `{"detail": {"message": "No quotes were imported...", "errors": ["Line 3, supplier_name: ..."]}}`. A wrong file type, an empty file or a file that's too big gets a single message instead.

On the page, these show up as red text under whichever form you submitted.

## How the best quote is picked

Total price is `unit_price × quantity`, rounded to 2 decimal places. The quotes are sorted cheapest first and the top one is marked best.

If two quotes cost the same, the one with the shorter lead time wins. If that's also the same, the one added first wins.

Mixed currencies needed a decision. I can't compare 100 USD with 100 INR without exchange rates, and I didn't want to make rates up. So the app picks a best quote for each currency separately and shows a yellow warning that the quotes aren't all in the same currency.

## CSV import

The file has to be UTF-8 with a header row. Column order doesn't matter and the header isn't case sensitive.

```
supplier_name,unit_price,currency,lead_time_days,payment_terms,remarks
Acme Metals,12.50,USD,14,Net 30,Price includes packaging
Delta Components,11.90,usd,10,Net 60,
```

`remarks` can be left out. The other five columns are required. Each row goes through the same validation as the quote form.

The import is all or nothing. If even one row is bad, nothing gets saved, and you get a list of every problem with its line number, like `Line 4, unit_price: Input should be greater than 0`. I went this way so you never end up with half a file imported and have to work out which rows made it in. Fix the file and upload it again.

It also deals with wrong file types, empty files, a header with no rows under it, missing columns, rows with too many values, files that aren't UTF-8, the hidden BOM character Excel adds, completely blank rows (these are skipped) and files over 1 MB.

There are two sample files in `sample_data/`:
- `sample_quotes.csv` imports 10 quotes. Bharat Forge Works at 11.75 is the cheapest.
- `sample_quotes_with_errors.csv` imports nothing and shows the error list.

## Assumptions and tradeoffs

- I only did CSV import. The assignment mentions PDF and Excel too. For Excel, you can "Save As → CSV UTF-8" and upload that. Pulling tables out of PDFs is unreliable and would need extra libraries, so I left it out.
- Delivery expectation is free text. People write it in lots of ways ("Within 30 days", "By 15 Dec"), so I didn't force a date. The downside is the app can't check it against supplier lead times.
- Prices are stored as floats and totals are rounded to 2 decimals. That's fine for comparing quotes. A real accounting system should use exact decimals.
- You can't edit or delete RFQs or quotes, since the assignment didn't ask for it. A supplier can quote more than once (say, a revised price). Importing the same CSV twice will add the quotes twice.
- I wrote plain SQL with SQLite instead of using an ORM. There's nothing to install and you can read exactly what each query does. For a bigger app with many users I'd switch to PostgreSQL.
- The frontend is plain HTML and JavaScript with no build step. A bigger UI would probably want React or similar.
- No login, deployment, permissions or fancy styling, as the assignment said.

## FastAPI and Python notes

Some notes on the main ideas in the code, mostly for my own reference.

- Routes: a function with a decorator like `@app.post("/api/rfqs")` runs when a request hits that URL. Whatever dict or list it returns is sent back as JSON.
- Path parameters: in `/api/rfqs/{rfq_id}`, FastAPI pulls `rfq_id` out of the URL and turns it into an int, because the function says `rfq_id: int`.
- Pydantic models (`schemas.py`): classes that say what valid data looks like, e.g. `quantity: int = Field(gt=0)`. When an endpoint takes one of these, FastAPI checks the request body and sends back a 422 by itself if something's wrong. `@field_validator` is how I added the currency check.
- `Depends(get_db)`: FastAPI runs `get_db()` first and hands its result, a database connection, to the endpoint. Because `get_db` uses `yield`, the line after it (closing the connection) still runs after the response, even if there was an error.
- `HTTPException`: raising `HTTPException(status_code=404, detail="...")` stops the request and sends that error back.
- `UploadFile`: how FastAPI receives an uploaded file. It needs the `python-multipart` package. I read the bytes with `file.file.read()`.
- `StaticFiles`: `app.mount("/", StaticFiles(...))` lets FastAPI serve the HTML, JS and CSS, so the frontend and backend run from one server.
- The `?` in SQL: values are passed separately from the query text, e.g. `execute("... WHERE id = ?", (rfq_id,))`. This stops SQL injection.
- `commit()`: nothing is saved until you commit. The CSV import inserts every row and then commits once, and that's what makes it all or nothing.
- `TestClient`: lets the tests send requests to the app without starting a real server.

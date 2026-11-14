"""Reading supplier quotes from a CSV file.

Expected format (first line is the header, column order does not matter):

    supplier_name,unit_price,currency,lead_time_days,payment_terms,remarks
    Acme Metals,12.50,USD,14,Net 30,Includes packaging

`remarks` is optional; every other column is required.
Every row is checked with the same QuoteCreate model used by the API.
"""

import csv
import io

from pydantic import ValidationError

from app.schemas import QuoteCreate

REQUIRED_COLUMNS = ["supplier_name", "unit_price", "currency", "lead_time_days", "payment_terms"]
OPTIONAL_COLUMNS = ["remarks"]


def parse_quotes_csv(file_bytes: bytes):
    """Turn CSV file content into a list of valid quotes and a list of error messages.

    Returns (quotes, errors). If `errors` is not empty, nothing should be saved.
    """
    # "utf-8-sig" also handles the invisible BOM character Excel adds to CSV files.
    try:
        text = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        return [], ["The file is not valid UTF-8 text. Please save it as 'CSV UTF-8'."]

    reader = csv.DictReader(io.StringIO(text))

    if not reader.fieldnames:
        return [], ["The file is empty. The first line must be the header row."]

    # Make header matching forgiving: " Unit_Price " is treated as "unit_price".
    headers = [header.strip().lower() for header in reader.fieldnames]
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in headers]
    if missing_columns:
        return [], [
            "Missing required column(s): " + ", ".join(missing_columns)
            + ". Expected header: " + ",".join(REQUIRED_COLUMNS + OPTIONAL_COLUMNS)
        ]
    reader.fieldnames = headers

    quotes = []
    errors = []
    for row in reader:
        # reader.line_num is the line in the file (line 1 is the header).
        line_number = reader.line_num

        # DictReader puts extra values (more values than headers) under the key None.
        if None in row:
            errors.append(f"Line {line_number}: has more values than there are columns.")
            continue

        values = {column: (row.get(column) or "") for column in REQUIRED_COLUMNS + OPTIONAL_COLUMNS}

        # Ignore rows where every cell is blank (e.g. ",,,,," at the end of a file).
        if all(value.strip() == "" for value in values.values()):
            continue

        try:
            quotes.append(QuoteCreate(**values))
        except ValidationError as error:
            for problem in error.errors():
                field_name = problem["loc"][0]
                errors.append(f"Line {line_number}, {field_name}: {problem['msg']}")

    if not quotes and not errors:
        errors.append("The file has a header but no quote rows.")

    return quotes, errors

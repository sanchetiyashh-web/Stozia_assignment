// Frontend logic: plain JavaScript that talks to the FastAPI backend with fetch().

let currentRfqId = null;

// ---------------------------- Helpers ----------------------------

// Call the API. Returns the JSON data, or throws an Error with readable messages.
async function callApi(path, options = {}) {
  const response = await fetch(path, options);
  let data = null;
  try {
    data = await response.json();
  } catch (error) {
    // The response had no JSON body.
  }
  if (!response.ok) {
    throw new Error(formatApiError(data));
  }
  return data;
}

// FastAPI sends errors in different shapes; turn each one into plain text.
function formatApiError(data) {
  if (!data || data.detail === undefined) {
    return "Something went wrong. Please try again.";
  }
  const detail = data.detail;
  if (typeof detail === "string") {
    return detail; // e.g. "RFQ with id 5 was not found."
  }
  if (Array.isArray(detail)) {
    // 422 validation errors: [{loc: ["body", "quantity"], msg: "..."}, ...]
    return detail.map((item) => `${item.loc[item.loc.length - 1]}: ${item.msg}`).join("\n");
  }
  if (detail.errors) {
    // Our CSV import errors: {message: "...", errors: ["Line 2, ...", ...]}
    return [detail.message, ...detail.errors].join("\n");
  }
  return JSON.stringify(detail);
}

// Escape text before putting it into HTML, so user input cannot inject HTML.
function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value === null || value === undefined ? "" : String(value);
  return div.innerHTML;
}

function showMessage(elementId, text, type) {
  const element = document.getElementById(elementId);
  element.textContent = text;
  element.className = "message " + type;
}

function formatMoney(amount) {
  return Number(amount).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 });
}

// ---------------------------- RFQ list ----------------------------

async function loadRfqList() {
  try {
    const rfqs = await callApi("/api/rfqs");
    const tableBody = document.getElementById("rfq-table-body");
    if (rfqs.length === 0) {
      tableBody.innerHTML = '<tr><td colspan="7">No RFQs yet. Create one above.</td></tr>';
      return;
    }
    tableBody.innerHTML = rfqs.map((rfq) => `
      <tr>
        <td>${rfq.id}</td>
        <td>${escapeHtml(rfq.item_name)}</td>
        <td>${escapeHtml(rfq.specification)}</td>
        <td>${rfq.quantity}</td>
        <td>${escapeHtml(rfq.delivery_expectation)}</td>
        <td>${rfq.quote_count}</td>
        <td><button type="button" onclick="openRfq(${rfq.id})">Open</button></td>
      </tr>`).join("");
  } catch (error) {
    showMessage("rfq-list-message", error.message, "error");
  }
}

document.getElementById("rfq-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.target;
  const formData = Object.fromEntries(new FormData(form));
  try {
    const rfq = await callApi("/api/rfqs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(formData),
    });
    form.reset();
    showMessage("rfq-form-message", `RFQ #${rfq.id} created.`, "success");
    await loadRfqList();
  } catch (error) {
    showMessage("rfq-form-message", error.message, "error");
  }
});

// ------------------------- One RFQ (detail) -------------------------

async function openRfq(rfqId) {
  currentRfqId = rfqId;
  document.getElementById("rfq-list-section").hidden = true;
  document.getElementById("rfq-detail-section").hidden = false;
  // Clear old success/error messages from a previously opened RFQ.
  showMessage("quote-form-message", "", "");
  showMessage("csv-form-message", "", "");
  await loadComparison();
}

async function loadComparison() {
  try {
    const comparison = await callApi(`/api/rfqs/${currentRfqId}/comparison`);
    renderRfqDetails(comparison.rfq);
    renderQuoteTable(comparison.quotes);
    document.getElementById("currency-warning").hidden = !comparison.mixed_currencies;
  } catch (error) {
    showMessage("quote-form-message", error.message, "error");
  }
}

function renderRfqDetails(rfq) {
  document.getElementById("rfq-title").textContent = `RFQ #${rfq.id}: ${rfq.item_name}`;
  document.getElementById("rfq-details").innerHTML = `
    <dt>Material / specification</dt><dd>${escapeHtml(rfq.specification)}</dd>
    <dt>Quantity</dt><dd>${rfq.quantity}</dd>
    <dt>Delivery expectation</dt><dd>${escapeHtml(rfq.delivery_expectation)}</dd>
    <dt>Notes</dt><dd>${escapeHtml(rfq.notes) || "-"}</dd>`;
}

function renderQuoteTable(quotes) {
  const tableBody = document.getElementById("quote-table-body");
  if (quotes.length === 0) {
    tableBody.innerHTML = '<tr><td colspan="8">No quotes yet. Add one below or import a CSV file.</td></tr>';
    return;
  }
  tableBody.innerHTML = quotes.map((quote) => `
    <tr class="${quote.is_best ? "best-quote" : ""}">
      <td>${escapeHtml(quote.supplier_name)}</td>
      <td>${formatMoney(quote.unit_price)}</td>
      <td>${escapeHtml(quote.currency)}</td>
      <td>${formatMoney(quote.total_price)}</td>
      <td>${quote.lead_time_days}</td>
      <td>${escapeHtml(quote.payment_terms)}</td>
      <td>${escapeHtml(quote.remarks)}</td>
      <td>${quote.is_best ? '<span class="badge">Best quote</span>' : ""}</td>
    </tr>`).join("");
}

document.getElementById("quote-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.target;
  const formData = Object.fromEntries(new FormData(form));
  try {
    await callApi(`/api/rfqs/${currentRfqId}/quotes`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(formData),
    });
    form.reset();
    showMessage("quote-form-message", "Quote added.", "success");
    await loadComparison();
  } catch (error) {
    showMessage("quote-form-message", error.message, "error");
  }
});

document.getElementById("csv-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.target;
  try {
    // FormData with a file is sent as multipart/form-data (the browser sets the header).
    const result = await callApi(`/api/rfqs/${currentRfqId}/quotes/import`, {
      method: "POST",
      body: new FormData(form),
    });
    form.reset();
    showMessage("csv-form-message", `Imported ${result.imported_count} quote(s).`, "success");
    await loadComparison();
  } catch (error) {
    showMessage("csv-form-message", error.message, "error");
  }
});

document.getElementById("back-button").addEventListener("click", async () => {
  currentRfqId = null;
  document.getElementById("rfq-detail-section").hidden = true;
  document.getElementById("rfq-list-section").hidden = false;
  await loadRfqList();
});

// Load the RFQ list when the page opens.
loadRfqList();

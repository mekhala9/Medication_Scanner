// ============================================================
//  SCRIPT.JS — Frontend Logic
//
//  What this file does:
//    - Handles image upload and webcam capture
//    - Sends image to Flask backend via POST /scan
//    - Displays scan results as a card on the same page
//    - Loads and displays scan history via GET /history
//    - Handles View, Delete and Download actions
//
//  How this file connects to the rest of the app:
//    index.html loads this file at the bottom of the page
//    This file talks to Flask (app.py) via HTTP fetch calls:
//      POST   /scan         → send image, get result
//      GET    /history      → get list of past scans
//      GET    /scan/<id>    → get one past scan by ID
//      DELETE /scan/<id>    → delete one past scan
//
//  Sections in this file:
//    1. Global variables
//    2. Image upload handler
//    3. Scan function (POST /scan)
//    4. Show results
//    5. Raw text toggle
//    6. Download JSON
//    7. History (GET /history, GET /scan/<id>, DELETE /scan/<id>)
//    8. Webcam functions
//    9. Helper functions
// ============================================================


// ── 1. Global variables ───────────────────────────────────────
// currentResult → stores the last scan result so Download JSON can use it
// webcamStream  → stores the active camera stream so we can stop it later
// webcamFile    → stores the captured photo as a File object
let currentResult = null;
let webcamStream  = null;


// ── 2. Image upload ───────────────────────────────────────────
// Listens for when user selects a file using the Upload Image button
// Clears any webcam capture so old webcam file doesn't interfere
document.getElementById("file-input").addEventListener("change", function() {
  window.webcamFile = null;   // clear any previous webcam capture
  handleImageSelected(this.files[0]);
});

function handleImageSelected(file) {
  // Called when user selects a file OR after webcam capture
  // Shows the image in the preview box and enables the Scan button
  if (!file) return;

  // FileReader converts the file to a data URL so we can show it as an image
  const reader = new FileReader();
  reader.onload = function(e) {
    const img    = document.getElementById("preview-img");
    const holder = document.getElementById("placeholder");
    img.src           = e.target.result;
    img.style.display = "block";
    holder.style.display = "none";  // hide the "No image selected" placeholder
  };
  reader.readAsDataURL(file);

  // Enable the Scan Label button now that an image is ready
  document.getElementById("scan-btn").disabled = false;

  // Hide any previous results and status messages
  document.getElementById("results-card").style.display = "none";
  document.getElementById("status-msg").style.display   = "none";
}


// ── 3. Scan function ──────────────────────────────────────────
// Called when user clicks "Scan Label"
// Sends the image to Flask POST /scan and handles the response
async function startScan() {
  // Check which file to use — uploaded file or webcam capture
  const fileInput = document.getElementById("file-input").files[0];
  const file      = fileInput || window.webcamFile;
  if (!file) { showStatus("Please select an image first", "error"); return; }

  // Show loading state
  showStatus("Scanning label with GPT-4o Vision... this may take 15-20 seconds ⏳", "loading");
  document.getElementById("scan-btn").disabled    = true;
  document.getElementById("scan-btn").textContent = "Scanning...";
  document.getElementById("results-card").style.display = "none";

  // FormData is how browsers send files over HTTP
  // We attach the image file with the key "image" — app.py reads it as request.files["image"]
  const formData = new FormData();
  formData.append("image", file);

  try {
    // POST the image to Flask /scan route
    // fetch() is the browser's built-in HTTP request function
    const response = await fetch("/scan", { method: "POST", body: formData });
    const result   = await response.json();   // parse the JSON response from Flask

    if (result.drug_name === "N/A") {
      // No medication label detected — show error instead of empty results
      showStatus("No medication label detected. Please upload a clear photo of a medication bottle.", "error");
    } else if (result.status === "error") {
      showStatus("Error: " + result.message, "error");
    } else {
      showStatus("Scan complete!", "success");
      showResults(result);   // display the results card
      loadHistory();         // refresh the history list
    }

  } catch (error) {
    showStatus("Connection error: " + error.message, "error");
  } finally {
    // Always re-enable the scan button when done — success or failure
    document.getElementById("scan-btn").disabled    = false;
    document.getElementById("scan-btn").textContent = "🔍 Scan Label";
  }
}


// ── 4. Show results ───────────────────────────────────────────
// Called after a successful scan
// Fills the results card with data from the scan result dictionary
function showResults(result) {
  currentResult = result;   // save for Download JSON

  // Show the results card
  const card = document.getElementById("results-card");
  card.style.display = "block";

  // Set the drug name as the card title
  document.getElementById("results-drug-name").textContent =
    result.drug_name !== "N/A" ? result.drug_name : "Scan Results";

  // ── Fill label fields (from GPT-4o Vision) ──
  const infoGrid = document.getElementById("info-grid");
  infoGrid.innerHTML = "";   // clear previous results

  const labelFields = [
    { key: "drug_name",    label: "Drug Name"    },
    { key: "generic_name", label: "Generic Name" },
    { key: "dosage",       label: "Dosage"       },
    { key: "expiry_date",  label: "Expiry Date"  },
    { key: "manufacturer", label: "Manufacturer" },
    { key: "quantity",     label: "Quantity"     },
    { key: "instructions", label: "Instructions", full: true },  // spans full width
    { key: "warnings",     label: "Warnings",     full: true },  // spans full width
  ];

  labelFields.forEach(field => {
    const value = result[field.key] || "N/A";
    const div   = document.createElement("div");
    // full-width class makes the item span both grid columns
    div.className = "info-item" + (field.full ? " full-width" : "");
    div.innerHTML  = `<div class="label">${field.label}</div><div class="value">${value}</div>`;
    infoGrid.appendChild(div);
  });

  // ── Fill FDA fields (from OpenFDA API) ──
  const fdaGrid = document.getElementById("fda-grid");
  fdaGrid.innerHTML = "";   // clear previous results

  [
    { key: "fda_purpose",      label: "Purpose / Indication" },
    { key: "fda_side_effects", label: "Side Effects"         },
    { key: "fda_warnings",     label: "FDA Warnings"         },
  ].forEach(field => {
    const div = document.createElement("div");
    div.className = "fda-item";
    div.innerHTML  = `<div class="label">${field.label}</div><div class="value">${result[field.key] || "N/A"}</div>`;
    fdaGrid.appendChild(div);
  });

  // Fill the raw text box (hidden by default)
  document.getElementById("raw-text").textContent = result.raw_text || "";

  // Smoothly scroll to the results card
  card.scrollIntoView({ behavior: "smooth", block: "start" });
}


// ── 5. Raw text toggle ────────────────────────────────────────
// Shows or hides the raw text extracted by GPT-4o from the label
// Called when user clicks "Show extracted text" button
function toggleRaw() {
  const rawDiv = document.getElementById("raw-text");
  const btn    = document.querySelector(".btn-ghost");
  if (rawDiv.style.display === "none") {
    rawDiv.style.display = "block";
    btn.textContent = "Hide extracted text ▴";
  } else {
    rawDiv.style.display = "none";
    btn.textContent = "Show extracted text ▾";
  }
}


// ── 6. Download JSON ──────────────────────────────────────────
// Downloads the current scan result as a .json file
// Called when user clicks "Download JSON" button
function downloadResult() {
  if (!currentResult) return;

  // Create a Blob (binary large object) from the JSON string
  const blob = new Blob([JSON.stringify(currentResult, null, 2)], { type: "application/json" });

  // Create a temporary download link and click it programmatically
  const url  = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href     = url;
  link.download = "scan_" + (currentResult.drug_name || "result").replace(/\s+/g, "_") + ".json";
  link.click();

  // Release the temporary URL from memory
  URL.revokeObjectURL(url);
}


// ── 7. History ────────────────────────────────────────────────
// Functions for loading, displaying, viewing and deleting past scans

async function loadHistory() {
  // Calls GET /history in Flask (app.py)
  // Flask returns list of scans from database.py get_scan_history()
  try {
    const response = await fetch("/history");
    const history  = await response.json();
    renderHistory(history);
  } catch (error) {
    console.error("Failed to load history:", error);
  }
}

function renderHistory(history) {
  // Builds the history list in the DOM from the array returned by /history
  const list = document.getElementById("history-list");

  if (!history || history.length === 0) {
    list.innerHTML = '<p class="empty-msg">No recent scans</p>';
    return;
  }

  list.innerHTML = "";   // clear existing list

  history.forEach(item => {
    const daysLeft = item.days_left;
    // Green badge if more than 1 day left, amber if expiring today
    const expClass = daysLeft <= 1 ? "expiry-low" : "expiry-ok";
    const expText  = daysLeft === 1 ? "Expires today" : daysLeft + " days left";

    const div = document.createElement("div");
    div.className = "history-item";
    div.innerHTML = `
      <div class="history-info">
        <div class="drug">${item.drug_name}
          <span class="expiry-badge ${expClass}">${expText}</span>
        </div>
        <div class="meta">Scanned on ${formatDateTime(item.scanned_at_full || item.scanned_at)}</div>
      </div>
      <div class="history-actions">
        <button class="btn-view"   onclick="viewScan(${item.id})">View</button>
        <button class="btn-delete" onclick="deleteScan(${item.id})">Delete</button>
      </div>`;
    list.appendChild(div);
  });
}

async function viewScan(id) {
  // Calls GET /scan/<id> in Flask to load a past scan result
  // Then displays it in the results card just like a new scan
  try {
    const response = await fetch("/scan/" + id);
    const result   = await response.json();
    if (result.status !== "error") {
      showResults(result);
      showStatus("Loaded from history", "success");
    }
  } catch (error) {
    showStatus("Could not load scan", "error");
  }
}

async function deleteScan(id) {
  // Calls DELETE /scan/<id> in Flask to remove a scan from the database
  // Then refreshes the history list
  if (!confirm("Delete this scan from history?")) return;
  try {
    await fetch("/scan/" + id, { method: "DELETE" });
    loadHistory();   // refresh the list after deleting
  } catch (error) {
    showStatus("Could not delete scan", "error");
  }
}


// ── 8. Webcam functions ───────────────────────────────────────

async function openWebcam() {
  // Shows the webcam modal and starts the camera stream
  // getUserMedia is the browser API that requests camera access
  document.getElementById("webcam-modal").style.display = "flex";
  try {
    webcamStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
    document.getElementById("webcam-video").srcObject = webcamStream;
  } catch (error) {
    alert("Could not access webcam.\nError: " + error.message);
    closeWebcam();
  }
}

function closeWebcam() {
  // Stops the camera stream and hides the modal
  // Important: always stop tracks to release the camera
  if (webcamStream) {
    webcamStream.getTracks().forEach(t => t.stop());
    webcamStream = null;
  }
  document.getElementById("webcam-modal").style.display = "none";
  document.getElementById("webcam-video").srcObject     = null;
}

function capturePhoto() {
  // Takes a still photo from the live webcam feed
  // Draws the current video frame onto a hidden canvas
  // then converts it to a JPEG File object for scanning
  const video  = document.getElementById("webcam-video");
  const canvas = document.getElementById("webcam-canvas");

  // Wait until camera feed is fully loaded before capturing
  if (video.readyState < 2) { alert("Camera still loading. Please wait."); return; }

  // Set canvas size to match the video dimensions
  canvas.width  = video.videoWidth  || 640;
  canvas.height = video.videoHeight || 480;

  // Draw the current video frame onto the canvas (takes a snapshot)
  canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);

  // Convert canvas to JPEG blob then to File object
  // File object works exactly like a normal uploaded file
  canvas.toBlob(function(blob) {
    if (!blob) { alert("Could not capture. Please try again."); return; }

    const file   = new File([blob], "webcam_capture.jpg", { type: "image/jpeg" });
    const url    = URL.createObjectURL(blob);
    const img    = document.getElementById("preview-img");
    const holder = document.getElementById("placeholder");

    // Show captured photo in preview box
    img.src = url;
    img.style.display    = "block";
    holder.style.display = "none";

    // Store as webcamFile so startScan() can use it
    window.webcamFile = file;

    // Clear file input so old uploaded file doesn't override webcam capture
    document.getElementById("file-input").value = "";

    // Enable scan button and reset UI
    document.getElementById("scan-btn").disabled          = false;
    document.getElementById("results-card").style.display = "none";
    document.getElementById("status-msg").style.display   = "none";

    closeWebcam();  // stop camera and hide modal
  }, "image/jpeg", 0.9);  // 0.9 = 90% JPEG quality
}


// ── 9. Helper functions ───────────────────────────────────────

function showStatus(message, type) {
  // Shows a status banner below the buttons
  // type can be: "loading", "success", "error"
  // style.css defines the colour for each type
  const el = document.getElementById("status-msg");
  el.textContent   = message;
  el.className     = "status-msg status-" + type;
  el.style.display = "block";
}

function formatDateTime(dateTimeStr) {
  // Formats a full ISO timestamp for display in history
  // e.g. "2026-05-17T22:30:00" → "May 17, 2026 at 10:30 PM"
  if (!dateTimeStr) return "Unknown";
  const date = new Date(dateTimeStr.length <= 10
    ? dateTimeStr + "T12:00:00"   // date only — add noon to avoid timezone shift
    : dateTimeStr                  // full timestamp
  );
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) +
         " at " + date.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });
}


// ── Load history when page first opens ───────────────────────
// This runs immediately when the page loads
// Populates the Recent Scans section with any saved scans
loadHistory();
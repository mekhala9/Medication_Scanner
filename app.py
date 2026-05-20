# ============================================================
#  APP.PY — Flask Web Server
#
#  This is the ENTRY POINT of the application.
#  Run this file to start the web server:
#    python app.py
#  Then open: http://med-scanner.local
#
#  What this file does:
#    - Creates the Flask web server
#    - Defines 5 routes (URLs) the browser can call
#    - Connects the frontend (HTML/JS) to the backend (scanner.py)
#    - Connects to the database (database.py) for scan history
#
#  How frontend and backend connect:
#    Browser (index.html + script.js)
#        │
#        │  HTTP requests (GET, POST, DELETE)
#        ▼
#    Flask routes defined here (app.py)
#        │
#        ├── scanner.py   → AI scanning logic
#        └── database.py  → scan history storage
# ============================================================


import os
from flask import Flask, request, jsonify, render_template
from scanner import scan_medication
from database import create_table, save_scan, get_scan_history, get_scan_by_id, delete_scan

# ── App setup ─────────────────────────────────────────────────

app = Flask(__name__)

# Maximum image upload size = 16MB
# Prevents users uploading files that are too large
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

# Only these image formats are accepted
ALLOWED = {"jpg", "jpeg", "png", "webp"}

# ── Helper function ───────────────────────────────────────────
def allowed(filename):
    # Check if the uploaded file has an allowed extension
    # Example: "bottle.jpg" → True  |  "file.pdf" → False
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED

# ── Database setup ────────────────────────────────────────────

# Create the scans table in SQLite when the app starts
# If the table already exists, this does nothing — safe to run every time
with app.app_context():
    create_table()

# ============================================================
#  ROUTES
#  A route is a URL path the browser can visit or call.
#  Flask runs the function below each route when that URL is hit.
# ============================================================
 
# ── Route 1 — Home page
@app.route("/")
def home():
    # Called when user opens http://med-scanner.local
    # Returns the main HTML page from the templates/ folder
    return render_template("index.html")

# ── Route 2 — Scan a medication image
@app.route("/scan", methods=["POST"])
def scan():
    # Called by script.js when user clicks "Scan Label"
    # Receives the image file, runs the AI pipeline, saves result
    # Returns the scan result as JSON back to the browser
 
    # Check an image file was actually included in the request
    if "image" not in request.files:
        return jsonify({"status": "error", "message": "No image uploaded"}), 400
    image_file = request.files["image"]
    # Check the file wasn't empty
    if image_file.filename == "":
        return jsonify({"status": "error", "message": "No file selected"}), 400
    # Check the file type is allowed
    if not allowed(image_file.filename):
        return jsonify({"status": "error", "message": "Only JPG, PNG and WEBP files allowed"}), 400
    # Check the OpenAI API key is set in the terminal
    if not os.environ.get("OPENAI_API_KEY"):
        return jsonify({"status": "error", "message": "OPENAI_API_KEY not set"}), 500
    try:
        print("Processing: " + image_file.filename)
        # Run the full scanning pipeline (scanner.py)
        # This makes 2 API calls: GPT-4o Vision + OpenFDA
        result = scan_medication(image_file)
        # Save the result to SQLite database (database.py)
        save_scan(result)
        print("Done: " + result.get("drug_name", "unknown"))
        return jsonify(result)
    except Exception as e:
        print("ERROR: " + str(e))
        return jsonify({"status": "error", "message": str(e)}), 500

# ── Route 3 — Get scan history
@app.route("/history", methods=["GET"])
def history():
    # Called by script.js when the page loads
    # Returns list of all scans from the last 5 days
    return jsonify(get_scan_history())

# ── Route 4 — View one past scan
@app.route("/scan/<int:scan_id>", methods=["GET"])
def get_scan(scan_id):
    # Called by script.js when user clicks "View" on a history item
    # Returns the full result for that specific scan ID
    result = get_scan_by_id(scan_id)
    if result:
        return jsonify(result)
    return jsonify({"status": "error", "message": "Scan not found"}), 404

# ── Route 5 — Delete one past scan
@app.route("/scan/<int:scan_id>", methods=["DELETE"])
def remove_scan(scan_id):
    # Called by script.js when user clicks "Delete" on a history item
    # Permanently removes that scan from the database
    delete_scan(scan_id)
    return jsonify({"status": "deleted"})

# ── Start the server
if __name__ == "__main__":
    print("\n============================================")
    print("  MEDICATION SCANNER — Starting")
    print("Open: http://med-scanner.local")
    print("============================================\n")
    app.run(debug=True, port=80, host="0.0.0.0")


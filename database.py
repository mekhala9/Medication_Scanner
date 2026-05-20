# ============================================================
#  DATABASE.PY — SQLite Storage
#
#  What this file does:
#    1. Creates a local SQLite database file (scans.db)
#    2. Saves each scan result with today's date
#    3. Automatically deletes scans older than 5 days
#    4. Retrieves scan history for the user to view
#
#  Why SQLite?
#    - Built into Python — no pip install needed
#    - Saves data to a simple local file (scans.db)
#    - Data survives when you restart the app
#    - Perfect for small local apps like this one
#
#  How it connects to the rest of the app:
#    app.py imports all functions from this file
#    save_scan()        → called after every successful scan
#    get_scan_history() → called when page loads (GET /history)
#    get_scan_by_id()   → called when user clicks View
#    delete_scan()      → called when user clicks Delete
# ============================================================
 
import sqlite3
import json
from datetime import datetime, timedelta

# Name of our database file — saved in the same folder as app.py
DATABASE_FILE = "scans.db"

# How many days to keep a scan before auto-deleting it
EXPIRY_DAYS = 5


def get_connection():
    """
    Open a connection to the SQLite database file.
    If scans.db doesn't exist yet, SQLite creates it automatically.
    """
    conn = sqlite3.connect(DATABASE_FILE)
    # Row factory makes results return as dictionaries
    # instead of plain tuples — easier to work with
    conn.row_factory = sqlite3.Row
    return conn


def create_table():
    """
    Create the scans table if it doesn't already exist.
    Called once when the app starts.

    Table columns:
      id          → auto-incrementing unique number for each scan
      drug_name   → name of the drug scanned (for display in history)
      result_json → the full scan result stored as a JSON string
      scanned_at  → when the scan was done
      expires_at  → when this scan should be deleted (scanned + 5 days)
    """
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scans (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            drug_name   TEXT,
            result_json TEXT,
            scanned_at  TEXT,
            expires_at  TEXT
        )
    """)
    conn.commit()
    conn.close()


def delete_expired_scans():
    """
    Delete any scans older than 5 days.
    Called automatically every time the app loads or a new scan is saved.
    The user never sees this happening — it runs silently in the background.
    """
    now = datetime.now().isoformat()
    conn = get_connection()
    conn.execute("DELETE FROM scans WHERE expires_at < ?", (now,))
    conn.commit()
    conn.close()


def save_scan(result):
    """
    Save a new scan result to the database.
    Also runs delete_expired_scans() first to keep the database clean.

    Parameters:
      result → the dictionary returned by scanner.py's scan_medication()
    """
    # Clean up old scans first
    delete_expired_scans()

    now        = datetime.now()
    expires_at = now + timedelta(days=EXPIRY_DAYS)

    conn = get_connection()
    conn.execute(
        """
        INSERT INTO scans (drug_name, result_json, scanned_at, expires_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            result.get("drug_name", "Unknown"),   # short name for history list
            json.dumps(result),                    # full result as JSON string
            now.isoformat(),                       # e.g. "2025-05-16T14:30:00"
            expires_at.isoformat(),                # e.g. "2025-05-21T14:30:00"
        )
    )
    conn.commit()
    conn.close()


def get_scan_history():
    """
    Return all scans that have not yet expired.
    Results are ordered newest first.

    Returns a list of dictionaries like:
    [
      {
        "id": 1,
        "drug_name": "Hydrochlorothiazide",
        "scanned_at": "2025-05-16T14:30:00",
        "expires_at": "2025-05-21T14:30:00",
        "days_left": 4
      },
      ...
    ]
    """
    # Clean up expired scans first
    delete_expired_scans()

    now  = datetime.now()
    conn = get_connection()

    rows = conn.execute(
        "SELECT * FROM scans ORDER BY scanned_at DESC"
    ).fetchall()
    conn.close()

    history = []
    for row in rows:
        expires_at = datetime.fromisoformat(row["expires_at"])
        days_left  = (expires_at - now).days + 1  # +1 so today counts as 1 day

        history.append({
            "id":         row["id"],
            "drug_name":  row["drug_name"],
            "scanned_at": row["scanned_at"][:10], "scanned_at_full": row["scanned_at"],  # just the date part
            "expires_at": row["expires_at"][:10],
            "days_left":  max(days_left, 1),        # show at least 1 day
        })

    return history


def get_scan_by_id(scan_id):
    """
    Retrieve one specific scan result by its ID.
    Used when the user clicks "View" on a past scan in the history.

    Returns the full result dictionary or None if not found.
    """
    conn = get_connection()
    row  = conn.execute(
        "SELECT result_json FROM scans WHERE id = ?", (scan_id,)
    ).fetchone()
    conn.close()

    if row:
        return json.loads(row["result_json"])
    return None


def delete_scan(scan_id):
    """
    Manually delete one scan by ID.
    Called when the user clicks the Delete button.
    """
    conn = get_connection()
    conn.execute("DELETE FROM scans WHERE id = ?", (scan_id,))
    conn.commit()
    conn.close()


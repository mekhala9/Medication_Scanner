# 💊 Medication Scanner 

A web application that scans medication labels using AI and returns structured drug information instantly.

## What it does ??

- Upload a photo or capture using webcam
- GPT-4o Vision reads the medication label
- OpenFDA API enriches with purpose, side effects and warnings
- Results displayed on the same page
- Scan history saved for 5 days with timestamps
- Download results as JSON

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, Flask |
| AI Vision | GPT-4o Vision (OpenAI) |
| Drug Database | OpenFDA API (free) |
| Storage | SQLite |
| Image Processing | Pillow |
| Frontend | HTML, CSS, JavaScript |
| Camera | getUserMedia Browser API |

## Project Structure

```
medication_scanner/
├── app.py              → Flask web server (5 routes)
├── scanner.py          → AI logic (GPT-4o Vision + OpenFDA)
├── database.py         → SQLite storage (5 day expiry)
├── requirements.txt    → Python dependencies
├── templates/
│   └── index.html      → Single page frontend
└── static/
    ├── css/style.css   → Styling
    └── js/script.js    → Frontend logic
```

## How to Run ??

**Step 1 — Clone the repository**
```
git clone https://github.com/mekhala9/Medication_Scanner.git
cd Medication_Scanner
```

**Step 2 — Create virtual environment**
```
python -m venv venv
venv\Scripts\activate
```

**Step 3 — Install dependencies**
```
pip install -r requirements.txt
```

**Step 4 — Set OpenAI API key**
```
$env:OPENAI_API_KEY="sk-your-key-here"
```

**Step 5 — Run the app**
```
python app.py
```

**Step 6 — Open browser**
```
http://localhost:80 or https://med-scanner.local
```

## API Calls

| Call | API | Purpose |
|---|---|---|
| 1 | GPT-4o Vision | Reads label image, returns structured JSON |
| 2 | OpenFDA API | Enriches with purpose, side effects, warnings |

## Output Fields

**From Label (GPT-4o Vision):**
- Drug Name, Generic Name, Dosage
- Instructions, Warnings, Expiry Date
- Manufacturer, Quantity

**From FDA Database (OpenFDA):**
- Purpose / Indication
- Side Effects
- FDA Warnings

## Edge Cases Handled

- Non-medication images → error message shown
- Wrong file type → rejected before scanning
- Drug not in FDA → returns "Not found" gracefully
- Webcam unavailable → clear error message
- JSON parse failure → safe N/A defaults returned

## Related Project

[Smart Clinical Summary Agent](https://github.com/mekhala9/Smart_clinical_Agent)
```

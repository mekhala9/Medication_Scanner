# ============================================================
#  SCANNER.PY — Core AI Logic
#
#  What this file does:
#    Step 1 → Prepare image (convert to base64)
#    Step 2 → GPT-4o Vision reads AND parses label (API Call 1)
#    Step 3 → OpenFDA enriches drug info           (API Call 2)
#    Step 4 → Returns one clean dictionary
#
#  How it connects to the rest of the app:
#    app.py calls scan_medication(image_file)
#    This file does all the AI work and returns a dictionary
#    app.py then saves that dictionary to the database
#    and sends it back to the browser as JSON
#
#  API Calls made here:
#    API Call 1 → OpenAI GPT-4o Vision
#                 Reads the label image and returns structured JSON
#    API Call 2 → OpenFDA API (free, no key needed)
#                 Looks up drug purpose, side effects, warnings
# ============================================================

import os
import json
import base64
import re
import requests
from openai import OpenAI
from PIL import Image
import io

# ── Settings

VISION_MODEL = "gpt-4o"
PARSE_MODEL  = "gpt-4o-mini"
OPENFDA_URL  = "https://api.fda.gov/drug/label.json"
MY_API_KEY   = os.environ.get("OPENAI_API_KEY", "")


# ── Step 1: Prepare image ─────────────────────────────────────

def prepare_image(image_file):
    # Convert the uploaded image to base64 so we can send it
    # to OpenAI Vision API over the internet as text
    #
    # Why base64?
    # APIs communicate as text — base64 converts binary image
    # data into a text string that fits inside a JSON body
    image = Image.open(image_file)

    # Convert RGBA/P to RGB — strips the transparency channel
    # OpenAI Vision works best with plain RGB
    if image.mode in ("RGBA", "P"):
        image = image.convert("RGB")

    # Save into memory buffer (not to disk)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    buffer.seek(0)

    # Convert bytes → base64 text string
    return base64.b64encode(buffer.read()).decode("utf-8")


# ── Step 2 — API Call 1: GPT-4o Vision

def extract_and_parse(image_base64):
    # Send the image to GPT-4o Vision and ask it to BOTH
    # read the label AND return structured JSON in one single call
    #
    # Why combine reading and parsing in one call?
    # Previously we extracted raw text first then parsed it separately.
    # GPT-4o reading the image directly and returning structured JSON
    # gives much more accurate results.
    #
    # Why "product label" language instead of "medication label"?
    # OpenAI content policy sometimes refuses medical prompts.
    # Using neutral language avoids refusals.
    client = OpenAI(api_key=MY_API_KEY)

    prompt = (
        "You are a product label reader assistant.\n"
        "Look at this over-the-counter product label image carefully.\n"
        "Read all the printed text on the label and extract the information into JSON.\n"
        "No extra text, no markdown, no explanation — just JSON.\n\n"
        "Return exactly this JSON structure:\n"
        "{\n"
        '  "drug_name":    "the main product name shown on the label",\n'
        '  "generic_name": "the generic or chemical name if shown, else N/A",\n'
        '  "dosage":       "the strength and form e.g. 500mg tablet, 25mg/5ml",\n'
        '  "instructions": "how and when to use it",\n'
        '  "warnings":     "any warnings or precautions printed on label",\n'
        '  "expiry_date":  "the expiry or best before date if shown, else N/A",\n'
        '  "manufacturer": "the company or brand name if shown, else N/A",\n'
        '  "quantity":     "number of tablets, capsules or ml if shown, else N/A",\n'
        '  "raw_text":     "all the text you can read from the label"\n'
        "}\n\n"
        "Rules:\n"
        "- Read ALL parts of the label carefully\n"
        "- Write N/A only if a field is genuinely not visible\n"
        "- For drug_name use the largest most prominent name on the label\n"
        "- Return valid JSON only — no refusals, this is a standard product label"
    )

    response = client.chat.completions.create(
        model=VISION_MODEL,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type":      "image_url",
                    "image_url": {
                        "url":    f"data:image/jpeg;base64,{image_base64}",
                        "detail": "high"
                    }
                }
            ]
        }],
        temperature=0.1,
        max_tokens=1000,
    )

    # Extract GPT's response and clean any markdown code fences
    text = response.choices[0].message.content.strip()
    text = text.replace("```json", "").replace("```", "").strip()

    try:
        # Convert JSON string → Python dictionary
        return json.loads(text)
    except json.JSONDecodeError:
        # If JSON parsing fails return safe defaults so app doesn't crash
        return {
            "drug_name":    "Could not parse",
            "generic_name": "N/A",
            "dosage":       "N/A",
            "instructions": "N/A",
            "warnings":     "N/A",
            "expiry_date":  "N/A",
            "manufacturer": "N/A",
            "quantity":     "N/A",
            "raw_text":     text,
        }


# ── Step 3 — API Call 2: OpenFDA enrichment ─────────────────────────────

def clean_drug_name(name):
     # Strip dosage info from drug name before searching OpenFDA
    # OpenFDA cannot find "Hydrochlorothiazide 25 MG Oral Tablet"
    # but can find "Hydrochlorothiazide"
    cleaned = re.split(
        r'\s+\d+[\d./]*\s*(MG|ML|MCG|IU|%|Day|tablet|capsule|oral|pack)',
        name, flags=re.IGNORECASE
    )[0].strip()

    cleaned = re.sub(
        r'\s+(oral|tablet|capsule|solution|suspension|injection|pack|cream|patch).*$',
        '', cleaned, flags=re.IGNORECASE
    ).strip()

    return cleaned if cleaned else name


def lookup_fda(drug_name):
    # Call OpenFDA API — free, no key needed
    # Try 4 search strategies to maximise chance of finding the drug
    # because drug names can be stored under brand name or generic name
    cleaned = clean_drug_name(drug_name)

    search_options = [
        ("openfda.brand_name",   cleaned),             # full brand name
        ("openfda.generic_name", cleaned),             # full generic name
        ("openfda.brand_name",   cleaned.split()[0]),  # first word only
        ("openfda.generic_name", cleaned.split()[0]),  # first word only
    ]

    for field, term in search_options:
        try:
            resp = requests.get(
                OPENFDA_URL,
                params={"search": f'{field}:"{term}"', "limit": 1},
                timeout=10
            )
            if resp.status_code == 200:
                results = resp.json().get("results", [])
                if results:
                    label = results[0]
                    # FDA stores each field as a list
                    # We take the first item and cap at 400 chars
                    def first(key):
                        return (label.get(key, ["N/A"])[0])[:2000]
                    return {
                        "fda_purpose":      first("purpose") or first("indications_and_usage"),
                        "fda_side_effects": first("adverse_reactions"),
                        "fda_warnings":     first("warnings"),
                    }
        except requests.RequestException:
            # If this search strategy fails, try the next one
            pass
    # If all 4 strategies fail return safe defaults
    return {
        "fda_purpose":      "Not found in FDA database",
        "fda_side_effects": "Not found in FDA database",
        "fda_warnings":     "Not found in FDA database",
    }


# ── Step 4 — Main scan function ────────────────────────────────────────

def scan_medication(image_file):
    # Main function called by app.py
    # Runs the full pipeline and returns one clean dictionary
    # app.py saves this to database and sends it to the browser

    if not MY_API_KEY:
        raise EnvironmentError("OPENAI_API_KEY not set")

    print("  [1/3] Preparing image...")
    image_base64 = prepare_image(image_file)

    print("  [2/3] Reading and parsing label with GPT-4o Vision...")
    parsed = extract_and_parse(image_base64)
    print("  GPT-4o raw response parsed: " + str(parsed)[:200])

    print("  [3/3] Enriching with OpenFDA...")
    drug_name = parsed.get("drug_name", "")
    # Only call OpenFDA if we actually found a drug name
    fda_info  = lookup_fda(drug_name) if drug_name and drug_name not in ("N/A", "Could not parse") else {}


    # Combine label data + FDA data into one final dictionary
    # .get(key, "N/A") means: give me the value, or "N/A" if not found
    return {
        "drug_name":        parsed.get("drug_name",    "N/A"),
        "generic_name":     parsed.get("generic_name", "N/A"),
        "dosage":           parsed.get("dosage",       "N/A"),
        "instructions":     parsed.get("instructions", "N/A"),
        "warnings":         parsed.get("warnings",     "N/A"),
        "expiry_date":      parsed.get("expiry_date",  "N/A"),
        "manufacturer":     parsed.get("manufacturer", "N/A"),
        "quantity":         parsed.get("quantity",     "N/A"),
        "fda_purpose":      fda_info.get("fda_purpose",      "N/A"),
        "fda_side_effects": fda_info.get("fda_side_effects",  "N/A"),
        "fda_warnings":     fda_info.get("fda_warnings",      "N/A"),
        "raw_text":         parsed.get("raw_text",     ""),
        "status":           "success",
    }


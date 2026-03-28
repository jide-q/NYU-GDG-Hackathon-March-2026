"""
Data loader for DCWP delivery worker datasets.
Loads survey data and quarterly aggregated tables into text format
that gets injected into the system prompt.

If data files aren't present, returns hardcoded summary statistics
from the DCWP reports so the agent still works without the raw data.
"""

import os
import json

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def load_data_context() -> tuple[str, str]:
    """
    Load DCWP data and return (survey_context, quarterly_context) strings.
    Falls back to hardcoded summaries if files aren't present.
    """
    survey_context = _load_survey_data()
    quarterly_context = _load_quarterly_data()
    return survey_context, quarterly_context


def _load_survey_data() -> str:
    """Load the DCWP delivery worker survey summary."""
    # Try loading processed JSON first
    json_path = os.path.join(DATA_DIR, "survey_summary.json")
    if os.path.exists(json_path):
        with open(json_path) as f:
            return json.dumps(json.load(f), indent=2)

    # Fallback: hardcoded summary from DCWP November 2022 report
    return """
Key findings from the DCWP Delivery Worker Survey (7,956 respondents across 9 languages):

DEMOGRAPHICS:
- Majority are male immigrants, average age 30-40
- Most common countries of origin: Mexico, Guatemala, China, Ecuador, Senegal, Guinea, Mali
- Languages: Spanish (largest group), Mandarin, French, English, Bengali, Arabic, Korean, Russian, Urdu
- ~65% use e-bikes or regular bicycles, ~20% use cars, ~15% use mopeds/motorcycles

WORKING CONDITIONS (BEFORE minimum pay law):
- Average pay BEFORE tips: $7.09/hour (some as low as $5.39/hr)
- Average tips: $4.90/hour
- Average total: $11.99/hour
- Most workers work 6-7 days per week
- Average 10+ hours per day
- 49% reported at least one accident in the past year
- 54% experienced theft of their vehicle, food, or equipment
- Many report not receiving itemized pay statements

EXPENSES:
- E-bike costs: $1,000-$3,000 purchase price, $50-200/month maintenance
- Phone plan: $50-100/month (essential for work)
- Insulated bags: $20-50 (supposed to be provided free after 6 deliveries)
- Vehicle insurance: varies widely
- Workers who own vehicles earn more per hour but have higher expenses

PLATFORM USAGE:
- DoorDash: most popular
- UberEats: second most popular  
- Grubhub: third
- Many workers use 2-3 platforms simultaneously
"""


def _load_quarterly_data() -> str:
    """Load the DCWP quarterly aggregated platform data."""
    # Try loading processed JSON
    json_path = os.path.join(DATA_DIR, "quarterly_summary.json")
    if os.path.exists(json_path):
        with open(json_path) as f:
            return json.dumps(json.load(f), indent=2)

    # Try loading the XLSX directly
    xlsx_path = os.path.join(DATA_DIR, "Restaurant-Delivery-App-Data-Quarterly.xlsx")
    if os.path.exists(xlsx_path):
        try:
            import pandas as pd
            df = pd.read_excel(xlsx_path)
            return df.to_string(index=False, max_rows=100)
        except Exception as e:
            print(f"[data_loader] Could not read XLSX: {e}")

    # Fallback: hardcoded summary from DCWP quarterly reports
    return """
Quarterly Platform Data Summary (from DCWP mandatory reporting by delivery apps):

IMPACT OF MINIMUM PAY LAW:
- Q1 2023 (before law): Average worker pay ~$11.72/hr before tips
- Q1 2024 (after law): Average worker pay ~$19.26/hr before tips (64% increase!)
- Worker earnings increased significantly after the minimum pay rate took effect

PLATFORM EARNINGS (approximate, from Q1 2024):
- DoorDash: largest platform by worker count
- UberEats: second largest  
- Grubhub: third largest
- FanTuan and HungryPanda: serve primarily Chinese-speaking workers

TIP TRENDS:
- After minimum pay law, total tips decreased from ~$9.9M/week to ~$3.4M/week
- This is because apps redesigned tip prompts (some argue to offset higher base pay)
- Individual tip amounts per delivery declined
- Workers' TOTAL earnings (base + tips) still increased significantly

WORKER COUNT TRENDS:
- Total active delivery workers: approximately 60,000-80,000 in NYC
- Some platforms reduced active worker counts after minimum pay law
- Average weekly hours per worker remained relatively stable

DELIVERY VOLUME:
- Total deliveries remained roughly stable after minimum pay law
- Consumer prices increased slightly on some platforms
- Some platforms added surcharges citing the minimum pay law
"""


def process_survey_zip(zip_path: str, output_path: str):
    """
    Process the raw DCWP survey ZIP into a summary JSON.
    Run this manually: python data_loader.py process_survey path/to/zip
    """
    import zipfile
    import pandas as pd

    with zipfile.ZipFile(zip_path, 'r') as z:
        z.extractall(os.path.join(DATA_DIR, "survey_raw"))

    # Find CSV files in extracted data
    csv_files = []
    for root, dirs, files in os.walk(os.path.join(DATA_DIR, "survey_raw")):
        for f in files:
            if f.endswith('.csv'):
                csv_files.append(os.path.join(root, f))

    summary = {"files_found": len(csv_files), "tables": {}}

    for csv_file in csv_files:
        try:
            df = pd.read_csv(csv_file)
            table_name = os.path.basename(csv_file).replace('.csv', '')
            summary["tables"][table_name] = {
                "rows": len(df),
                "columns": list(df.columns),
                "sample": df.head(3).to_dict(orient="records")
            }
        except Exception as e:
            print(f"Could not process {csv_file}: {e}")

    with open(output_path, 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"Processed {len(csv_files)} files → {output_path}")


def process_quarterly_xlsx(xlsx_path: str, output_path: str):
    """
    Process the quarterly XLSX into a summary JSON.
    Run this manually: python data_loader.py process_quarterly path/to/xlsx
    """
    import pandas as pd

    df = pd.read_excel(xlsx_path)
    summary = {
        "rows": len(df),
        "columns": list(df.columns),
        "data": df.to_dict(orient="records")
    }

    with open(output_path, 'w') as f:
        json.dump(summary, f, indent=2, default=str)

    print(f"Processed {len(df)} rows → {output_path}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3:
        cmd = sys.argv[1]
        path = sys.argv[2]
        if cmd == "process_survey":
            process_survey_zip(path, os.path.join(DATA_DIR, "survey_summary.json"))
        elif cmd == "process_quarterly":
            process_quarterly_xlsx(path, os.path.join(DATA_DIR, "quarterly_summary.json"))
        else:
            print(f"Unknown command: {cmd}")
    else:
        # Quick test
        s, q = load_data_context()
        print(f"Survey context: {len(s)} chars")
        print(f"Quarterly context: {len(q)} chars")

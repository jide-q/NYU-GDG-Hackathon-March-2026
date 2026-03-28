# Data Directory

Place the DCWP data files here:

## Required Downloads

1. **Survey Data** — Download from: https://www.nyc.gov/site/dca/workers/Delivery-Worker-Public-Hearing-Minimum-Pay-Rate.page
   - Click "Download Survey Data" → save the ZIP file here
   - Then process it: `python data_loader.py process_survey data/Delivery-Worker-Study-Survey-Data.zip`

2. **Quarterly Tables** — Download from the same page above
   - Click "Download Restaurant Delivery App Aggregated Tables" → save XLSX here
   - Then process it: `python data_loader.py process_quarterly data/Restaurant-Delivery-App-Data-Quarterly.xlsx`

## If you don't have time to download

The agent still works without these files — it falls back to hardcoded summaries
from the DCWP reports. The hardcoded data covers all the key statistics.

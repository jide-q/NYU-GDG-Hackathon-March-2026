# 🏃 QUICKSTART — Follow these steps in order

## Step 0: Get your API key (2 minutes)

1. Open https://aistudio.google.com/apikey in Chrome
2. Sign in with a personal Gmail account
3. Click "Create API key" → "Create key in new project"
4. Copy the key — you need it in Step 2


## Step 1: Set up the project (3 minutes)

```bash
# Clone or download this repo
cd deliver-assist

# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate      # Mac/Linux
# .venv\Scripts\activate       # Windows

# Install dependencies
pip install -r requirements.txt
```


## Step 2: Add your API key (1 minute)

```bash
cp .env.example .env
```

Open `.env` in any editor, replace `your-api-key-here` with your actual key:
```
GOOGLE_API_KEY=AIzaSy...your-actual-key
```


## Step 3: Run locally (1 minute)

```bash
python main.py
```

Open **http://localhost:8080** in Chrome. Click the microphone button and start talking.

**Test these:**
- Say "Hello" → agent responds in English
- Say "Hola, cuanto me deben pagar?" → agent responds in Spanish
- Say "I worked 40 hours and got paid 700 dollars before tips" → agent calculates compliance


## Step 4 (optional): Load real DCWP data (10 minutes)

1. Go to https://www.nyc.gov/site/dca/workers/Delivery-Worker-Public-Hearing-Minimum-Pay-Rate.page
2. Download "Survey Data" (ZIP) → save to `data/` folder
3. Download "Aggregated Tables" (XLSX) → save to `data/` folder
4. Process:
```bash
python data_loader.py process_survey data/Delivery-Worker-Study-Survey-Data.zip
python data_loader.py process_quarterly data/Restaurant-Delivery-App-Data-Quarterly.xlsx
```
5. Restart the server — the processed data is now in the agent's context

**If you skip this step, the agent still works.** It uses hardcoded summaries.


## Step 5: Deploy to Cloud Run (10 minutes)

```bash
# Make sure gcloud CLI is installed: https://cloud.google.com/sdk/docs/install
# Log in to your Google Cloud account
gcloud auth login

# One-command deploy
./deploy.sh YOUR_PROJECT_ID YOUR_API_KEY
```

The script will print a public URL. That's your deployed app.

**Screenshot the terminal output** — you need it as proof of GCP deployment.


## Step 6: Record the demo video (30 minutes)

Use OBS, QuickTime, or Loom. Max 4 minutes. Structure:

| Time | What to show |
|------|-------------|
| 0:00-0:20 | Hook: "80,000 delivery workers, many don't speak English, many underpaid" |
| 0:20-0:35 | Show the app, explain what it does |
| 0:35-1:15 | Demo: English conversation about rights |
| 1:15-2:00 | Demo: Switch to Spanish, then French — show language detection |
| 2:00-2:40 | Demo: "I made $700 for 45 hours" — show pay calculator tool call |
| 2:40-3:15 | Demo: Point camera at a pay stub — show image analysis |
| 3:15-3:35 | Flash architecture diagram |
| 3:35-4:00 | Impact: stats, scalability, what's next |

**Record a backup video.** Live demos can fail.


## Step 7: Submit

Go to the hackathon submission page and provide:
- [ ] Team name and members
- [ ] Project name: "DeliverAssist"
- [ ] GitHub repo URL (make it public)
- [ ] Demo video (upload to YouTube, set as unlisted or public)
- [ ] Architecture diagram (in docs/architecture.mermaid — render it at mermaid.live)
- [ ] GCP deployment proof (terminal screenshot from deploy.sh)

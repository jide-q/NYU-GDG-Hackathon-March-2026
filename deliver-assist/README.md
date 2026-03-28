# DeliverAssist — Multilingual Voice Agent for NYC Delivery Workers

A real-time multilingual voice agent that helps NYC's ~80,000 delivery workers understand their rights, check if they're being underpaid, and scan pay stubs — in 7+ languages via live conversation.

## Problem

NYC delivery workers earn as little as $5.39/hr before tips. Most are immigrants who speak limited English. They don't know their legal rights or how to detect wage theft. Filing complaints requires navigating English-only bureaucratic systems.

## Solution

DeliverAssist is a voice-first AI agent powered by Gemini Live API that workers can talk to in their own language. It answers rights questions, calculates whether they're being underpaid against the $21.44/hr NYC minimum, and reads pay stubs via phone camera — all in real-time conversation.

## Features

- **Real-time voice conversation** in 7+ languages (English, Spanish, French, Arabic, Hindi/Urdu, Turkish, Mandarin)
- **Automatic language detection** — speak any supported language and the agent responds in kind
- **Pay calculator** — tell the agent your hours and pay, get an instant compliance check
- **Pay stub scanner** — point your camera at a pay stub, the agent reads and analyzes it
- **Worker rights knowledge base** — grounded in DCWP open data and NYC labor law

## Supported Languages

| Language | Voice Support | NYC Worker Coverage |
|----------|:---:|---|
| English | ✅ | Universal |
| Spanish | ✅ | Largest delivery worker group |
| French | ✅ | West African francophone workers (Senegal, Guinea, Mali, Côte d'Ivoire) |
| Arabic | ✅ | North African & Middle Eastern workers |
| Hindi/Urdu | ✅ | South Asian workers |
| Turkish | ✅ | Turkish community workers |
| Mandarin | ✅ | Chinese delivery workers |
| Yoruba | 🔄 | Via English fallback |
| Bambara/Mandingo | 🔄 | Via French fallback (francophone region) |
| Pular/Fulani | 🔄 | Via French fallback (francophone region) |
| Nigerian Pidgin | 🔄 | Via English fallback (high mutual intelligibility) |

## Tech Stack

- **Gemini 2.5 Flash** with Native Audio (Live API bidi-streaming)
- **Google ADK** (Agent Development Kit)
- **FastAPI** WebSocket proxy
- **Google Cloud Run** for deployment
- **DCWP Open Data** (delivery worker survey + quarterly aggregated tables)

## Data Sources

- [DCWP Delivery Worker Survey Data](https://www.nyc.gov/site/dca/workers/Delivery-Worker-Public-Hearing-Minimum-Pay-Rate.page) — 7,956 worker responses
- [DCWP Quarterly Aggregated Tables](https://www.nyc.gov/site/dca/workers/Delivery-Worker-Public-Hearing-Minimum-Pay-Rate.page) — Platform earnings data (DoorDash, UberEats, Grubhub, etc.)
- NYC Administrative Code § 20-1522 (Minimum Pay Rate for Delivery Workers)

## Setup & Run

### Prerequisites
- Python 3.11+
- A Gemini API key from [AI Studio](https://aistudio.google.com/apikey)

### Local Development

```bash
# 1. Clone the repo
git clone https://github.com/YOUR_TEAM/deliver-assist.git
cd deliver-assist

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment
cp .env.example .env
# Edit .env and add your GOOGLE_API_KEY

# 5. Run the server
python main.py
# Open http://localhost:8080 in Chrome (needs microphone access)
```

### Deploy to Google Cloud Run

```bash
gcloud run deploy deliver-assist \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars="GOOGLE_API_KEY=your-key-here"
```

## Architecture

```
User (Phone/Laptop)
  ├── Microphone → PCM Audio ──────────────┐
  ├── Camera → JPEG Frames ────────────────┤
  └── Browser UI ◄── Audio Playback ◄──────┤
                                            ▼
                    Google Cloud Run (FastAPI + WebSocket)
                    ├── Session Manager
                    ├── System Prompt (Rights KB + DCWP Data)
                    └── Tool Handler (Pay Calculator)
                                            ▼
                    Gemini 2.5 Flash Native Audio (Live API)
                    ├── Language Detection (70+ languages)
                    ├── Voice Response Generation
                    ├── Image Understanding (Pay Stubs)
                    └── Function Calling (Pay Calculator)
```

## Team Members

- [Your names here]

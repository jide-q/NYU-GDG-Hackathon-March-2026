## Team
Team Members:
- Olajide Yusuf    yusuforeoluwa69@gmail.com      oyusuf@stevens.edu
- Ibrahim Diakite  cheick.diakite2000@gmail.com
- Hamidou Ballo    hamidouwb@gmail.com

# DeliverAssist

> A voice AI that speaks your language and fights for your pay.

NYC has ~80,000 food delivery workers. Most are immigrants. Many don't speak English well enough to read a pay stub, navigate a complaint form, or know that the law says they're owed **$21.44/hr before tips** — right now, today. They just accept whatever they get.

DeliverAssist is for Mamadou. For the Senegalese guy on the e-bike in the rain who doesn't know he's being shortchanged $0.44 an hour. For the Guatemalan rider who can't figure out why his weekly check doesn't add up. For anyone who works hard and just wants to be paid fairly — but the system is in a language they don't speak.

You talk to it. It talks back. In your language.

---

## What It Does

**Talk to it in any language.** Spanish, French, Arabic, Wolof — it detects what you're speaking and responds in kind. No setup, no language selection. Just talk.

**Ask about your pay.** "I worked 32 hours and made $640 before tips, is that fair?" It runs the math against the NYC minimum pay law and tells you straight — compliant or not, and by how much.

**Point your camera at a pay stub.** The agent reads it, parses the numbers, and tells you if something looks off. Right through the camera on your phone.

**Get a video explainer.** After a conversation, hit the video button and DeliverAssist generates a short animated explainer — scenes, dialogue, visual cues — breaking down your exact situation so you can watch it later or share it with a coworker.

---

## The Problem We're Solving

NYC passed a landmark minimum pay law for app-based delivery workers in 2023. The current rate (as of April 1, 2025) is **$21.44/hr before tips**. But:

- Most workers don't know the exact number
- Pay stubs from DoorDash, UberEats, Grubhub are confusing on purpose
- Filing a complaint with the DCWP requires navigating English-only bureaucratic forms
- There's no one to ask at 11pm when you're trying to figure out if your paycheck is right

DeliverAssist closes that gap. It's not a lawyer, it's not a hotline with a 2-hour hold — it's the knowledgeable friend who speaks your language and knows the rules.

---

## What's Coming Next

**Emotion detection.** The next version will pick up on how you're feeling during the conversation — frustrated, confused, scared — and adjust how it responds. If someone sounds upset or overwhelmed, the agent slows down, offers simpler explanations, and leads with reassurance before diving into numbers. Gemini's native audio understands tone, not just words. We're going to use that.

---

## Architecture

```
Your Phone / Browser
  ├── Mic → raw PCM audio (16kHz)
  ├── Camera → JPEG frames
  └── Speaker ← audio playback (24kHz)
         │
         ▼ WebSocket (bidirectional, persistent)
  ┌─────────────────────────────────────────┐
  │  FastAPI Server (main.py)               │
  │  ├── WebSocket proxy                    │
  │  ├── Conversation history manager       │
  │  ├── Tool call handler                  │
  │  ├── POST /video-script                 │
  │  └── POST /generate-video              │
  └─────────────────────────────────────────┘
         │                        │
         ▼                        ▼
  Gemini 2.5 Flash          Gemini 2.5 Flash
  Native Audio               (text/JSON mode)
  (Live API)                      │
  ├── Real-time STT                ▼
  ├── 70+ language support   video_script.py
  ├── Voice response          structured scenes
  ├── Image understanding          │
  └── Function calling             ▼
         │                   Veo 3 (nano_banana.py)
         ▼                   parallel 8s clips
  tools.py                   → data URI → browser
  calculate_pay_compliance()
  └── NYC § 20-1522 logic
         │
         ▼
  data_loader.py
  └── DCWP survey (7,956 workers)
  └── Quarterly platform earnings
      (DoorDash, UberEats, Grubhub...)
```

**The key architectural decisions:**

- **Single persistent Gemini Live session per user** — we never break the session on turn complete. Context lives in the session, not re-injected every time. If the session drops (server-side timeout), we replay conversation history into the new session's system prompt so nothing is lost.

- **Barge-in support** — when you start talking while the agent is speaking, the browser stops audio playback immediately and Gemini's `interrupted` signal resets the response queue. No talking over each other.

- **Video as a side-channel** — the video explainer is generated separately from the voice conversation. The agent's last response becomes the query for the video script, which gets turned into a Veo prompt with character consistency and legibility constraints baked in.

---

## Stack

| Layer | Tech |
|---|---|
| Voice AI | Gemini 2.5 Flash Native Audio (Live API) |
| Text/JSON gen | Gemini 2.5 Flash |
| Video gen | Veo 3.0 Fast |
| Backend | FastAPI + WebSocket |
| Frontend | Vanilla JS, Web Audio API |
| Data | DCWP Open Data (NYC.gov) |

---

## Run It Locally

```bash
git clone https://github.com/YOUR_TEAM/deliver-assist.git
cd deliver-assist
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add your GOOGLE_API_KEY
python main.py
# → open http://localhost:8080 in Chrome, allow mic
```

